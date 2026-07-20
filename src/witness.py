"""Witness examination nodes — direct examination, cross-examination, fact-checking."""
import json
import re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

import src.prompts as p
from src.config import AGENT_MODELS
from src.evidence import _no_objection_counter, _no_objection_lock
from src.llm import get_llm, get_structured_llm
from src.logger import get_logger
from src.schemas import ExaminationObjection, ExpertQualRuling, JudgeRuling
from src.state import TrialState
from src.trial_phases import _clerk_compression, _get_jx, _strip_ruling_preamble

logger = get_logger(__name__)

# ── Expert Qualification Helpers ──────────────────────────────────────────────

_EXPERT_KEYWORDS = [
    "Dr.",
    "dr.",
    "Doctor",
    "Prof.",
    "Professor",
    "MD",
    "PhD",
    "Expert",
    "Specialist",
    "Engineer",
    "Analyst",
]

_EXPERT_QUALIFICATION_PROMPT = (
    "You are examining a proposed expert witness. Ask ONE short question in 20 words or fewer "
    "to establish the witness's credentials, experience, or specialised knowledge relevant to this "
    "case. Do not ask about case facts — only qualifications."
)

_EXPERT_CHALLENGE_PROMPT = (
    "You are challenging the qualification of a proposed expert witness. Ask ONE short question in "
    "20 words or fewer that exposes a gap in the expert's credentials, bias, or methodology. "
    "Do not ask about case facts — only qualifications."
)


def _is_expert_candidate(witness_name: str) -> bool:
    return any(kw in witness_name for kw in _EXPERT_KEYWORDS)


def _qualify_expert(
    state: TrialState,
    witness_name: str,
    jx: dict,
    pros_llm,
    def_llm,
    judge_llm,
    transcript: list,
) -> bool:
    """Runs a mini voir dire to qualify a witness as an expert. Returns True if qualified."""
    logger.info(f"--- EXPERT QUALIFICATION for {witness_name} ---")
    facts = state.get("case_description", "")

    transcript.append(
        AIMessage(
            content=f"The prosecution seeks to qualify {witness_name} as an expert witness.",
            name="Prosecutor",
        )
    )

    try:
        q = pros_llm.invoke(
            [
                SystemMessage(content=p.prosecutor_prompt(jx)),
                HumanMessage(
                    content=(f"{_EXPERT_QUALIFICATION_PROMPT}\nProposed expert: {witness_name}\nCase facts: {facts}")
                ),
            ]
        )
        transcript.append(AIMessage(content=q.content, name="Prosecutor"))

        try:
            expert_llm = get_llm(temperature=0.5, model=AGENT_MODELS["Witness"])
        except Exception:
            expert_llm = get_llm(temperature=0.5, model="qwen-flash")

        a = expert_llm.invoke(
            [
                SystemMessage(
                    content=(
                        f"You are {witness_name}, a professional being offered as an expert witness. "
                        f"Describe your relevant credentials concisely in 20 words or fewer. "
                        f"Ground your qualifications in what the case facts imply about your role."
                    )
                ),
                HumanMessage(content=(f"Question: {q.content}\nCase facts: {facts}")),
            ]
        )
        transcript.append(AIMessage(content=a.content, name="Witness"))

        challenge = def_llm.invoke(
            [
                SystemMessage(content=p.defense_prompt(jx)),
                HumanMessage(
                    content=(
                        f"{_EXPERT_CHALLENGE_PROMPT}\n"
                        f'The proposed expert {witness_name} testified: "{a.content}"\n'
                        f"Case facts: {facts}"
                    )
                ),
            ]
        )
        transcript.append(AIMessage(content=challenge.content, name="Defense Counsel"))

        judge_structured = get_structured_llm(ExpertQualRuling, temperature=0.1, model=AGENT_MODELS["Judge"])
        ruling = judge_structured.invoke(
            [
                SystemMessage(content=p.judge_prompt(jx)),
                HumanMessage(
                    content=(
                        f"Prosecution seeks to qualify {witness_name} as an expert.\n"
                        f'Credentials: "{a.content}"\n'
                        f'Defence challenge: "{challenge.content}"\n\n'
                        f"Rule on expert qualification under {jx['evidence_rules']}. "
                        f"Return JSON with 'qualified' (true/false) and 'rationale'."
                    )
                ),
            ]
        )
        result_text = "QUALIFIED" if ruling.qualified else "NOT QUALIFIED"
        transcript.append(
            AIMessage(
                content=f"Expert qualification of {witness_name}: {result_text}. {ruling.rationale}",
                name="Judge",
            )
        )
        return ruling.qualified
    except Exception as e:
        logger.error(f"Expert qualification error: {e}", exc_info=True)
        transcript.append(
            AIMessage(
                content=f"Expert qualification could not be completed: {e}",
                name="System",
            )
        )
        return False


# ── Witness Examination ───────────────────────────────────────────────────────


def _parse_json_robustly(text: str) -> dict:
    """
    Attempts to extract and parse a JSON object from text, handling common LLM formatting issues
    such as markdown code blocks, leading/trailing text, and single quotes.
    """
    text = text.strip()
    # Try finding the first '{' and last '}'
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        json_str = text[start : end + 1]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            try:
                # Replace single quotes with double quotes
                cleaned = json_str.replace("'", '"')
                # Remove trailing commas before closing braces/brackets
                cleaned = re.sub(r",\s*([\]}])", r"\1", cleaned)
                return json.loads(cleaned)
            except Exception:
                pass

    # Brute-force regex attempt for should_object
    result = {}
    if "should_object" in text:
        match_true = re.search(r'"should_object"\s*:\s*true', text, re.IGNORECASE)
        match_false = re.search(r'"should_object"\s*:\s*false', text, re.IGNORECASE)
        if match_true:
            result["should_object"] = True
        elif match_false:
            result["should_object"] = False

    for key in ["objection_type", "rule_cited", "rationale"]:
        match = re.search(rf'"{key}"\s*:\s*"([^"]*)"', text)
        if match:
            result[key] = match.group(1)

    return result


def _ask_with_objection_gate(
    question_text,
    asking_name,
    opposing_name,
    opposing_model,
    witness_name,
    witness_llm,
    fc_llm,
    judge_ruling_llm,
    facts,
    jx,
    phase_type,
    transcript,
    objection_log,
    qa_log=None,
    answer_key="a",
    qa_wrapper=False,
):
    """
    Single-question Q&A with opposing counsel objection check.
    Used for impeachment and redirect examination.

    If the opposing counsel objects and the judge SUSTAINS, the witness
    does not answer — the question is struck. If OVERRULED or no objection,
    the witness answers with Fact Checker gating.
    """
    # ── Objection Check ───────────────────────────────────────
    obj = ExaminationObjection(should_object=False)
    try:
        opposing_llm = get_llm(temperature=0.1, model=opposing_model)
        resp = opposing_llm.invoke(
            [
                SystemMessage(content=p.examination_objection_prompt(jx, opposing_name, phase_type)),
                HumanMessage(
                    content=(
                        f"Opposing counsel ({asking_name}) asked this question to {witness_name} "
                        f'during {phase_type}:\n"{question_text}"\n\n'
                        f"Case facts:\n{facts}\n\n"
                        f'Respond with a JSON object: {{"should_object": false}} if you do NOT object, '
                        f'or {{"should_object": true, "objection_type": "...", "rule_cited": "...", "rationale": "..."}} if you DO object.'
                    )
                ),
            ]
        )
        text = resp.content.strip()
        data = _parse_json_robustly(text)
        obj = ExaminationObjection(**{k: v for k, v in data.items() if hasattr(ExaminationObjection, k)})
    except Exception as e:
        logger.error(f"Objection check error in {phase_type}: {e}", exc_info=True)
        obj = ExaminationObjection(should_object=False)

    question_struck = False
    if obj.should_object:
        transcript.append(
            AIMessage(
                content=f"Objection — {obj.objection_type.upper()}. {obj.rule_cited}: {obj.rationale}",
                name=opposing_name,
            )
        )

        try:
            ruling = judge_ruling_llm.invoke(
                [
                    SystemMessage(content=p.judge_prompt(jx)),
                    HumanMessage(
                        content=(
                            f"During {phase_type}, {opposing_name} objects to this question to {witness_name}:\n"
                            f'"{question_text}"\n\n'
                            f"Objection type: {obj.objection_type}\n"
                            f"Rule cited: {obj.rule_cited}\n"
                            f"Rationale: {obj.rationale}\n\n"
                            f"Rule on this objection under {jx['evidence_rules']}. Return a JSON object."
                        )
                    ),
                ]
            )
        except Exception as e:
            logger.error(f"Judge ruling error in {phase_type}: {e}", exc_info=True)
            transcript.append(AIMessage(content="[Judge ruling unavailable — the question stands]", name="System"))
        else:
            objection_log.append(
                {
                    "phase": f"witness_{phase_type}",
                    "objector": opposing_name,
                    "examiner": asking_name,
                    "witness": witness_name,
                    "question": question_text,
                    "objection_type": obj.objection_type,
                    "rule_cited": obj.rule_cited,
                    "rationale": obj.rationale,
                    "ruling": ruling.ruling,
                    "ruling_rationale": ruling.rationale,
                }
            )

            ruling_text = f"OBJECTION {ruling.ruling}." + (
                f" {_strip_ruling_preamble(ruling.rationale, ruling.ruling)}" if ruling.rationale else ""
            )
            if getattr(ruling, "limiting_instruction", ""):
                ruling_text += f" Limiting instruction: {ruling.limiting_instruction}"
            transcript.append(AIMessage(content=ruling_text, name="Judge"))

            if ruling.ruling.upper() == "SUSTAINED":
                question_struck = True
                if qa_log is not None and qa_wrapper:
                    qa_log.append({"question": question_text, answer_key: "[OBJECTION SUSTAINED — QUESTION STRUCK]"})

    if question_struck:
        return

    # ── Witness Answer ───────────────────────────────────────
    try:
        a = witness_llm.invoke(
            [
                SystemMessage(content=p.witness_prompt(jx)),
                HumanMessage(
                    content=(
                        f"You are {witness_name}. Answer in 40 words or fewer.\n"
                        f"Q: {question_text}\n"
                        f"Case facts:\n{facts}"
                    )
                ),
            ]
        )
    except Exception as e:
        logger.error(f"Witness LLM error in {phase_type}: {e}", exc_info=True)
        transcript.append(AIMessage(content="[Witness could not respond]", name="System"))
        return

    try:
        fc = fc_llm.invoke(
            [
                SystemMessage(content=p.fact_checker_prompt(jx)),
                HumanMessage(content=f"Case facts:\n{facts}\n\nWitness answer:\n{a.content}"),
            ]
        )
    except Exception:
        fc = AIMessage(content="PASS")

    if not fc.content.strip().upper().startswith("PASS"):
        transcript.append(AIMessage(content=fc.content, name="Fact Checker"))
        try:
            a = witness_llm.invoke(
                [
                    SystemMessage(content=p.witness_prompt(jx)),
                    HumanMessage(
                        content=(
                            f"You are {witness_name}.\n"
                            f"Question: {question_text}\n"
                            f"Your previous answer was objected to: {fc.content}\n"
                            f"Acknowledge the correction and answer correctly based ONLY on these case facts:\n{facts}"
                        )
                    ),
                ]
            )
        except Exception:
            pass
        transcript.append(AIMessage(content=a.content, name="Witness"))
        if qa_log is not None and qa_wrapper:
            qa_log.append({"question": question_text, answer_key: a.content})
    else:
        transcript.append(AIMessage(content=a.content, name="Witness"))
        if qa_log is not None and qa_wrapper:
            qa_log.append({"question": question_text, answer_key: a.content})


def _examination_loop(
    examiner_llm,
    examiner_prompt_fn,
    examiner_name,
    witness_name,
    witness_llm,
    fc_llm,
    facts,
    jx,
    phase_type,
    max_q,
    prior_context="",
    transcript=None,
    judge_ruling_llm=None,
    objection_log=None,
) -> list[dict]:
    """
    Dynamic examination loop — asks questions until the examiner says DONE
    or hits max_q. Fact-checker gates every witness answer.
    If judge_ruling_llm is provided, opposing counsel gets an opportunity
    to object to every question before the witness answers.

    Returns list of {"q": ..., "a": ...} dicts for cross-examination reference.
    Appends AIMessages to transcript in-place.
    """
    if transcript is None:
        transcript = []
    if objection_log is None:
        objection_log = []

    qa_log = []
    phase_objectives = {
        "direct": "Establish facts favorable to your case. Draw out the key evidence this witness can provide. Ask clear, focused questions.",
        "cross": "Challenge the witness's direct testimony. Expose weaknesses, contradictions, or gaps. Use leading questions.",
        "inquisitorial_prosecution": "The Judge has examined this witness. Ask supplementary questions to strengthen your case. Do NOT repeat the Judge's questions. If you have nothing meaningful to add, respond DONE.",
        "inquisitorial_defense": "The Judge has examined this witness. Ask supplementary questions to challenge their testimony or support your defence. Do NOT repeat the Judge's questions. If you have nothing meaningful to add, respond DONE.",
    }
    phase_rules = {
        "direct": "QUESTION TYPE: Open-ended questions ONLY (who, what, where, when, why, how). Do NOT ask leading questions (questions that suggest or imply the answer, e.g. 'You were at the scene, weren't you?'). Leading questions during direct examination are PROHIBITED.",
        "cross": "QUESTION TYPE: Leading questions are PERMITTED and encouraged during cross-examination. Ask questions that suggest the answer and challenge the witness. Use tag questions ('isn't that correct?', 'did you not?'). Be confrontational.",
        "inquisitorial_prosecution": "QUESTION TYPE: Open-ended supplementary questions. Do NOT ask leading questions. Do NOT repeat the Judge's questions.",
        "inquisitorial_defense": "QUESTION TYPE: Open-ended supplementary questions. Do NOT ask leading questions. Do NOT repeat the Judge's questions.",
    }
    objective = phase_objectives.get(phase_type, phase_objectives["direct"])
    question_rule = phase_rules.get(phase_type, phase_rules["direct"])

    # Determine opposing counsel for objection checks
    if judge_ruling_llm is not None:
        if examiner_name == "Prosecutor":
            opposing_name = "Defense Counsel"
            opposing_model = AGENT_MODELS["Defense Counsel"]
        elif examiner_name == "Defense Counsel":
            opposing_name = "Prosecutor"
            opposing_model = AGENT_MODELS["Prosecutor"]
        else:
            opposing_name = examiner_name
            opposing_model = AGENT_MODELS.get("Judge", "qwen-max")
        try:
            opposing_llm = get_llm(temperature=0.1, model=opposing_model)
        except Exception:
            opposing_llm = None
    else:
        opposing_llm = None
        opposing_name = ""

    # Use while loop so sustained objections don't consume question budget
    q_num = 1
    sustained_in_a_row = 0
    total_attempts = 0
    max_total_attempts = max_q * 3
    max_sustained_streak = 3
    last_fc_correction = ""
    fc_repeat_count = 0

    while q_num <= max_q and total_attempts < max_total_attempts:
        total_attempts += 1
        history = str(qa_log[-4:]) if qa_log else "(no prior questions)"
        if prior_context and q_num == 1:
            history = prior_context

        try:
            q = examiner_llm.invoke(
                [
                    SystemMessage(content=examiner_prompt_fn(jx)),
                    HumanMessage(
                        content=(
                            f"{phase_type.upper().replace('_', ' ')} — Q{q_num} (max {max_q}) to {witness_name}.\n"
                            f"Objective: {objective}\n"
                            f"{question_rule}\n"
                            f"Prior Q&A: {history}\n\n"
                            f"If you have fully established your points and have nothing meaningful left to ask, "
                            f"respond with exactly the word 'DONE' and nothing else.\n"
                            f"Otherwise, ask ONE short question (under 25 words). Base it on these case facts:\n\n{facts}"
                        )
                    ),
                ]
            )
        except Exception as e:
            logger.error(f"Examiner LLM error in {phase_type} Q{q_num}: {e}", exc_info=True)
            transcript.append(AIMessage(content="[Examiner error — proceeding to next witness]", name="System"))
            break

        content = q.content.strip()
        if content.upper() == "DONE" or content.upper().startswith("DONE"):
            break

        transcript.append(AIMessage(content=content, name=examiner_name))

        # ── Opposing Counsel Objection Check ──────────────────────────
        if opposing_llm is not None and judge_ruling_llm is not None:
            obj = ExaminationObjection(should_object=False)
            try:
                resp = opposing_llm.invoke(
                    [
                        SystemMessage(content=p.examination_objection_prompt(jx, opposing_name, phase_type)),
                        HumanMessage(
                            content=(
                                f"Opposing counsel ({examiner_name}) asked this question to {witness_name} "
                                f'during {phase_type} examination:\n"{content}"\n\n'
                                f"Case facts:\n{facts}\n\n"
                                f'Respond with a JSON object: {{"should_object": false}} if you do NOT object, '
                                f'or {{"should_object": true, "objection_type": "...", "rule_cited": "...", "rationale": "..."}} if you DO object.'
                            )
                        ),
                    ]
                )
                text = resp.content.strip()
                data = _parse_json_robustly(text)
                obj = ExaminationObjection(**{k: v for k, v in data.items() if hasattr(ExaminationObjection, k)})
            except Exception as e:
                logger.error(f"Opposing counsel objection check error in {phase_type}: {e}", exc_info=True)

            if not obj.should_object:
                key = f"{phase_type}_{opposing_name}"
                with _no_objection_lock:
                    _no_objection_counter[key] = _no_objection_counter.get(key, 0) + 1

            if obj.should_object:
                logger.info(
                    f"[OBJECTION] {opposing_name} objects during {phase_type}: {obj.objection_type} — Q: {content[:60]}..."
                )
                transcript.append(
                    AIMessage(
                        content=f"Objection — {obj.objection_type.upper()}. {obj.rule_cited}: {obj.rationale}",
                        name=opposing_name,
                    )
                )

                try:
                    ruling = judge_ruling_llm.invoke(
                        [
                            SystemMessage(content=p.judge_prompt(jx)),
                            HumanMessage(
                                content=(
                                    f"During {phase_type} examination of {witness_name}, {opposing_name} objects to this question:\n"
                                    f'"{content}"\n\n'
                                    f"Objection type: {obj.objection_type}\n"
                                    f"Rule cited: {obj.rule_cited}\n"
                                    f"Rationale: {obj.rationale}\n\n"
                                    f"Rule on this objection under {jx['evidence_rules']}. Return a JSON object."
                                )
                            ),
                        ]
                    )
                except Exception as e:
                    logger.error(f"Judge ruling error in {phase_type}: {e}", exc_info=True)
                    transcript.append(
                        AIMessage(
                            content="[Judge ruling unavailable — objection noted but question stands]", name="System"
                        )
                    )
                    q_num += 1
                    sustained_in_a_row = 0
                    continue

                objection_log.append(
                    {
                        "phase": f"witness_{phase_type}",
                        "objector": opposing_name,
                        "examiner": examiner_name,
                        "witness": witness_name,
                        "question": content,
                        "objection_type": obj.objection_type,
                        "rule_cited": obj.rule_cited,
                        "rationale": obj.rationale,
                        "ruling": ruling.ruling,
                        "ruling_rationale": ruling.rationale,
                    }
                )

                ruling_text = f"OBJECTION {ruling.ruling}." + (
                    f" {_strip_ruling_preamble(ruling.rationale, ruling.ruling)}" if ruling.rationale else ""
                )
                if getattr(ruling, "limiting_instruction", ""):
                    ruling_text += f" Limiting instruction: {ruling.limiting_instruction}"
                transcript.append(AIMessage(content=ruling_text, name="Judge"))

                if ruling.ruling.upper() == "SUSTAINED":
                    sustained_in_a_row += 1
                    qa_log.append({"q": content, "a": "[OBJECTION SUSTAINED — QUESTION STRUCK]"})
                    if sustained_in_a_row >= max_sustained_streak:
                        transcript.append(
                            AIMessage(content="Counsel, please rephrase your line of questioning.", name="Judge")
                        )
                        sustained_in_a_row = 0
                        q_num += 1  # force progress after repeated sustained objections
                        continue
                    # Don't increment q_num — examiner gets another attempt
                    continue
                else:
                    sustained_in_a_row = 0
                    # Objection OVERRULED — witness answers

        # ── Witness Answer ────────────────────────────────────────────
        try:
            a = witness_llm.invoke(
                [
                    SystemMessage(content=p.witness_prompt(jx)),
                    HumanMessage(
                        content=(
                            f"You are {witness_name}. Answer in 40 words or fewer.\nQ: {content}\nCase facts:\n{facts}"
                        )
                    ),
                ]
            )
        except Exception as e:
            logger.error(f"Witness LLM error in {phase_type} Q{q_num}: {e}", exc_info=True)
            transcript.append(AIMessage(content="[Witness could not respond — continuing]", name="System"))
            q_num += 1
            sustained_in_a_row = 0
            continue

        try:
            fc = fc_llm.invoke(
                [
                    SystemMessage(content=p.fact_checker_prompt(jx)),
                    HumanMessage(content=f"Case facts:\n{facts}\n\nWitness answer:\n{a.content}"),
                ]
            )
        except Exception as e:
            logger.error(f"Fact checker error in {phase_type} Q{q_num}: {e}", exc_info=True)
            transcript.append(AIMessage(content=a.content, name="Witness"))
            qa_log.append({"q": content, "a": a.content})
            q_num += 1
            sustained_in_a_row = 0
            continue

        if not fc.content.strip().upper().startswith("PASS"):
            fc_text = fc.content.strip()[:80]
            if fc_text == last_fc_correction:
                fc_repeat_count += 1
            else:
                fc_repeat_count = 0
                last_fc_correction = fc_text
            if fc_repeat_count >= 3:
                transcript.append(
                    AIMessage(
                        content=f"[{witness_name} skipped — unable to provide admissible testimony]",
                        name="System",
                    )
                )
                qa_log.append({"q": content, "a": "[Witness skipped]"})
                break
            transcript.append(AIMessage(content=fc.content, name="Fact Checker"))
            try:
                a = witness_llm.invoke(
                    [
                        SystemMessage(content=p.witness_prompt(jx)),
                        HumanMessage(
                            content=(
                                f"You are {witness_name}.\n"
                                f"Question: {content}\n"
                                f"Your previous answer was objected to: {fc.content}\n"
                                f"Acknowledge the correction and answer correctly based ONLY on these case facts:\n{facts}"
                            )
                        ),
                    ]
                )
            except Exception as e:
                logger.error(f"Witness correction error in {phase_type} Q{q_num}: {e}", exc_info=True)
            transcript.append(AIMessage(content=a.content, name="Witness"))
            qa_log.append({"q": content, "a": a.content})
        else:
            transcript.append(AIMessage(content=a.content, name="Witness"))
            qa_log.append({"q": content, "a": a.content})

        q_num += 1
        sustained_in_a_row = 0

    return qa_log


def _is_defendant_witness(witness_name: str, case_description: str) -> bool:
    """Check if the witness being called is the defendant/accused in the case facts."""
    if not witness_name or not case_description:
        return False
    name_parts = witness_name.lower().split()
    desc_lower = case_description.lower()
    # The defendant's name typically appears near "defendant", "the accused", or "charged with"
    defendant_patterns = [
        r"(?:the\s+)?defendant\s*,?\s*" + re.escape(witness_name)[:40],
        r"(?:the\s+)?accused\s*,?\s*" + re.escape(witness_name)[:40],
        r"charged\s+(?:with|under).{0,80}" + re.escape(witness_name)[:40],
        r"exercising\s+(?:his|her|their)\s+right\s+to\s+silence",
        r"has\s+not\s+testified\s+directly",
    ]
    for pattern in defendant_patterns:
        if re.search(pattern, desc_lower, re.IGNORECASE):
            return True
    # Also check if the defendant is named in the first paragraph
    if len(name_parts) >= 2:
        for i in range(len(name_parts)):
            for j in range(i + 1, len(name_parts) + 1):
                partial = " ".join(name_parts[i:j])
                # Look for defendant context near this partial name
                for context in ["defendant", "accused", "charged"]:
                    idx = desc_lower.find(context)
                    if 0 <= idx < len(desc_lower):
                        # Check within 100 chars of defendant mention
                        window = desc_lower[max(0, idx - 50) : min(len(desc_lower), idx + 150)]
                        if partial in window:
                            return True
    return False


def _extract_witness_context(witness_name: str, case_description: str) -> str:
    """Format case facts for a specific witness with role hint, passing the full context."""
    if not witness_name or not case_description:
        return (case_description or "")[:2000]

    parts = witness_name.split()
    if len(parts) < 2:
        return case_description[:2000]

    # Identify the witness's role from the case facts
    sentences = re.split(r"(?<=[.!?])\s+", case_description)
    role_terms = []
    for s in sentences:
        s_lower = s.lower()
        for role_kw in [
            "witness", "will testify", "testified", "investigator",
            "expert", "accountant", "inspector", "whistleblower",
            "officer", "analyst", "defendant", "victim",
            "manager", "director", "employee",
        ]:
            if role_kw in s_lower and role_kw not in role_terms:
                role_terms.append(role_kw)

    role_hint = ""
    if role_terms:
        role_hint = f"Your role: {', '.join(role_terms[:3])}. "

    return (
        f"{role_hint}Below are the full case facts for context. "
        f"Answer based ONLY on what is stated or directly implied in this record. "
        f"Do NOT invent details, dates, names, or events that are not present.\n\n"
        f"Full Case Record:\n{case_description}"
    )


def witness_direct(state: TrialState) -> dict:
    """
    Step 1 of Witness Examination:
    Pops a witness from the queue (if current_witness is not set), performs expert qualification if necessary,
    and runs the Direct Examination (adversarial) or Judge leads questioning (inquisitorial).
    """
    logger.info("--- WITNESS EXAMINATION: DIRECT ---")
    jx = _get_jx(state)
    witness_queue = list(state.get("witness_queue", []))
    current_witness = state.get("current_witness")

    # If starting a new witness, pop from queue
    if not current_witness:
        if not witness_queue:
            return {}
        current_witness = witness_queue.pop(0)

    transcript = []
    facts = state.get("case_description", "")
    declined_witnesses = list(state.get("declined_witnesses", []))

    # ── Right to Silence Check ──────────────────────────────────
    # If this witness is the defendant and has invoked right to silence,
    # or the case facts explicitly state the defendant will not testify,
    # end the examination immediately.
    if current_witness and _is_defendant_witness(current_witness, facts):
        transcript.append(AIMessage(content=f"The court calls {current_witness} to the stand.", name="Clerk"))
        transcript.append(
            AIMessage(
                content="I exercise my right to remain silent under applicable law. I will not testify in these proceedings.",
                name="Witness",
            )
        )
        transcript.append(
            AIMessage(
                content="Understood. The court respects the witness's right to silence. "
                "The fact-finder shall draw no adverse inference from this election. "
                "Counsel, call your next witness.",
                name="Judge",
            )
        )
        declined_witnesses.append(current_witness)
        updated_state = {**state, "transcript": state.get("transcript", []) + transcript}
        clerk_update = _clerk_compression(updated_state)
        return {
            "witness_queue": witness_queue,
            "current_witness": None,
            "examination_phase": None,
            "witness_direct_qa": [],
            "transcript": transcript,
            "declined_witnesses": declined_witnesses,
            **clerk_update,
        }

    pros_llm = get_llm(temperature=0.6, model=AGENT_MODELS["Prosecutor"])
    def_llm = get_llm(temperature=0.6, model=AGENT_MODELS["Defense Counsel"])
    wit_llm = get_llm(temperature=0.5, model=AGENT_MODELS["Witness"])
    fc_llm = get_llm(temperature=0.0, model=AGENT_MODELS["Fact Checker"])
    judge_llm = get_llm(temperature=0.1, model=AGENT_MODELS["Judge"])
    judge_ruling_llm = get_structured_llm(JudgeRuling, temperature=0.1, model=AGENT_MODELS["Judge"])

    expert_witnesses = list(state.get("expert_witnesses", []))
    objection_log = list(state.get("objection_history", []))

    # Voir Dire (Expert qualification)
    expert_qualified = False
    if _is_expert_candidate(current_witness) and jx["cross"]:
        expert_qualified = _qualify_expert(state, current_witness, jx, pros_llm, def_llm, judge_llm, transcript)
        if expert_qualified:
            expert_witnesses.append(current_witness)

    direct_qa = []

    # ── Oath / Swearing-In Ceremony ────────────────────────────
    oath_phrases = {
        "judeo_christian": {
            "clerk": "Do you solemnly swear that the testimony you are about to give in this matter shall be the truth, the whole truth, and nothing but the truth, so help you God?",
            "witness": "I do.",
        },
        "secular": {
            "clerk": "Do you solemnly affirm, under penalty of perjury, that the testimony you are about to give shall be the truth, the whole truth, and nothing but the truth?",
            "witness": "I do.",
        },
    }
    # Use secular oath for civil law / inquisitorial systems
    is_islamic = "Islamic" in jx["system"]
    is_civil = "Civil Law" in jx["system"]
    oath = oath_phrases["secular"] if (is_civil or is_islamic) else oath_phrases["judeo_christian"]
    transcript.append(AIMessage(content=f"The Clerk administers the oath to {current_witness}.", name="Clerk"))
    transcript.append(AIMessage(content=oath["clerk"], name="Clerk"))
    transcript.append(AIMessage(content=oath["witness"], name="Witness"))
    transcript.append(AIMessage(content="Please be seated. Counsel, your witness is sworn.", name="Judge"))

    # Visual phase transition banner
    if jx["cross"]:
        transcript.append(
            AIMessage(content=f"⚖️ Witness Examination of {current_witness} — Direct Examination begins.", name="Judge")
        )

        # ── ADVERSARIAL: Direct Examination (dynamic, up to 20 Qs) ──
        # Extract topic-filtered facts for this specific witness
        topic_facts = _extract_witness_context(current_witness, facts)
        direct_qa = _examination_loop(
            examiner_llm=pros_llm,
            examiner_prompt_fn=p.prosecutor_prompt,
            examiner_name="Prosecutor",
            witness_name=current_witness,
            witness_llm=wit_llm,
            fc_llm=fc_llm,
            facts=topic_facts,
            jx=jx,
            phase_type="direct",
            max_q=20,
            transcript=transcript,
            judge_ruling_llm=judge_ruling_llm,
            objection_log=objection_log,
        )
    else:
        transcript.append(
            AIMessage(
                content=f"⚖️ Inquisitorial Witness Examination of {current_witness} — Judicial Inquiry begins.",
                name="Judge",
            )
        )

        # ── INQUISITORIAL: Judge leads (3 Qs) ────
        for q_num in range(1, 4):
            try:
                q = judge_llm.invoke(
                    [
                        SystemMessage(content=p.judge_prompt(jx)),
                        HumanMessage(
                            content=(
                                f"JUDICIAL EXAMINATION — Question {q_num} of 3.\n"
                                f"Witness: {current_witness}.\n"
                                f"Ask a neutral, fact-finding question.\nCase facts:\n{facts}"
                            )
                        ),
                    ]
                )
            except Exception as e:
                logger.error(f"Judge question error in inquisitorial Q{q_num}: {e}", exc_info=True)
                continue

            transcript.append(AIMessage(content=f"Q (Judge): {q.content}", name="Judge"))

            try:
                a = wit_llm.invoke(
                    [
                        SystemMessage(content=p.witness_prompt(jx)),
                        HumanMessage(
                            content=(
                                f"You are {current_witness}.\n"
                                f"The Judge asks: {q.content}\n"
                                f"Answer based ONLY on these case facts:\n{facts}"
                            )
                        ),
                    ]
                )
            except Exception as e:
                logger.error(f"Witness answer error in inquisitorial Q{q_num}: {e}", exc_info=True)
                transcript.append(AIMessage(content="[Witness could not respond]", name="System"))
                continue

            try:
                fc = fc_llm.invoke(
                    [
                        SystemMessage(content=p.fact_checker_prompt(jx)),
                        HumanMessage(content=f"Case facts:\n{facts}\n\nWitness answer:\n{a.content}"),
                    ]
                )
            except Exception:
                fc = AIMessage(content="PASS")

            if not fc.content.strip().upper().startswith("PASS"):
                transcript.append(AIMessage(content=fc.content, name="Fact Checker"))
                try:
                    a = wit_llm.invoke(
                        [
                            SystemMessage(content=p.witness_prompt(jx)),
                            HumanMessage(
                                content=(
                                    f"You are {current_witness}.\n"
                                    f"The Judge asks: {q.content}\n"
                                    f"Your previous answer was objected to: {fc.content}\n"
                                    f"Acknowledge the correction and answer correctly based ONLY on these case facts:\n{facts}"
                                )
                            ),
                        ]
                    )
                except Exception:
                    pass
                transcript.append(AIMessage(content=a.content, name="Witness"))
            else:
                transcript.append(AIMessage(content=a.content, name="Witness"))

    # Prepare next state updates
    updated_state = {**state, "transcript": state.get("transcript", []) + transcript}
    clerk_update = _clerk_compression(updated_state)

    return {
        "witness_queue": witness_queue,
        "current_witness": current_witness,
        "witness_direct_qa": direct_qa,
        "transcript": transcript,
        "expert_witnesses": expert_witnesses,
        "objection_history": objection_log,
        **clerk_update,
    }


def witness_cross(state: TrialState) -> dict:
    """
    Step 2 of Witness Examination:
    Runs Cross-Examination (adversarial) or Prosecutor follow-up (inquisitorial).
    """
    logger.info("--- WITNESS EXAMINATION: CROSS ---")
    jx = _get_jx(state)
    current_witness = state.get("current_witness")
    if not current_witness:
        return {}

    transcript = []
    facts = state.get("case_description", "")

    pros_llm = get_llm(temperature=0.6, model=AGENT_MODELS["Prosecutor"])
    def_llm = get_llm(temperature=0.6, model=AGENT_MODELS["Defense Counsel"])
    wit_llm = get_llm(temperature=0.5, model=AGENT_MODELS["Witness"])
    fc_llm = get_llm(temperature=0.0, model=AGENT_MODELS["Fact Checker"])
    judge_ruling_llm = get_structured_llm(JudgeRuling, temperature=0.1, model=AGENT_MODELS["Judge"])

    objection_log = list(state.get("objection_history", []))
    direct_qa = state.get("witness_direct_qa", [])

    if jx["cross"]:
        transcript.append(
            AIMessage(
                content=f"⚖️ Witness Examination of {current_witness} — Defense Cross-Examination begins.", name="Judge"
            )
        )

        # ── ADVERSARIAL: Cross-Examination (dynamic, up to 15 Qs) ──
        prior_str = str(direct_qa[-4:]) if direct_qa else ""
        topic_facts = _extract_witness_context(current_witness, facts)
        _examination_loop(
            examiner_llm=def_llm,
            examiner_prompt_fn=p.defense_prompt,
            examiner_name="Defense Counsel",
            witness_name=current_witness,
            witness_llm=wit_llm,
            fc_llm=fc_llm,
            facts=topic_facts,
            jx=jx,
            phase_type="cross",
            max_q=15,
            prior_context=prior_str,
            transcript=transcript,
            judge_ruling_llm=judge_ruling_llm,
            objection_log=objection_log,
        )
    else:
        transcript.append(
            AIMessage(
                content=f"⚖️ Inquisitorial Witness Examination of {current_witness} — Prosecution supplementary questioning begins.",
                name="Judge",
            )
        )
        transcript.append(
            AIMessage(
                content=f"Madame/Monsieur le Procureur — any supplementary questions for {current_witness}?",
                name="Judge",
            )
        )
        transcript.append(AIMessage(content="Oui, Monsieur le Président.", name="Prosecutor"))

        # ── INQUISITORIAL: Prosecutor follow-up (up to 8 Qs, with objection checks) ──
        _examination_loop(
            examiner_llm=pros_llm,
            examiner_prompt_fn=p.prosecutor_prompt,
            examiner_name="Prosecutor",
            witness_name=current_witness,
            witness_llm=wit_llm,
            fc_llm=fc_llm,
            facts=facts,
            jx=jx,
            phase_type="inquisitorial_prosecution",
            max_q=8,
            transcript=transcript,
            judge_ruling_llm=judge_ruling_llm,
            objection_log=objection_log,
        )

    updated_state = {**state, "transcript": state.get("transcript", []) + transcript}
    clerk_update = _clerk_compression(updated_state)

    return {"transcript": transcript, "objection_history": objection_log, **clerk_update}


def witness_redirect(state: TrialState) -> dict:
    """
    Step 3 of Witness Examination:
    Runs Impeachment + Redirect (adversarial) or Defense follow-up (inquisitorial),
    then clears current_witness so the router knows to pull the next witness or move to rebuttal.
    """
    logger.info("--- WITNESS EXAMINATION: REDIRECT/IMPEACHMENT ---")
    jx = _get_jx(state)
    current_witness = state.get("current_witness")
    if not current_witness:
        return {}

    transcript = []
    facts = state.get("case_description", "")

    pros_llm = get_llm(temperature=0.6, model=AGENT_MODELS["Prosecutor"])
    def_llm = get_llm(temperature=0.6, model=AGENT_MODELS["Defense Counsel"])
    wit_llm = get_llm(temperature=0.5, model=AGENT_MODELS["Witness"])
    fc_llm = get_llm(temperature=0.0, model=AGENT_MODELS["Fact Checker"])
    judge_ruling_llm = get_structured_llm(JudgeRuling, temperature=0.1, model=AGENT_MODELS["Judge"])

    impeachment_log = list(state.get("impeachment_attempts", []))
    objection_log = list(state.get("objection_history", []))
    direct_qa = state.get("witness_direct_qa", [])

    if jx["cross"]:
        transcript.append(
            AIMessage(
                content=f"⚖️ Witness Examination of {current_witness} — Impeachment and Redirect begins.", name="Judge"
            )
        )

        # ── ADVERSARIAL: Structured Impeachment (4-step sequence) ──
        impeachment_step_labels = ["Foundation", "Commitment", "Confrontation", "Closing"]
        try:
            impeach_resp = def_llm.invoke(
                [
                    SystemMessage(content=p.defense_impeachment_prompt(jx)),
                    HumanMessage(
                        content=(
                            f"IMPEACHMENT — Structured 4-step sequence to {current_witness}.\n"
                            f"Their direct answers: {direct_qa}\n\n"
                            f"Challenge the witness's credibility. Base it on the case facts.\n"
                            f"Facts:\n{facts}"
                        )
                    ),
                ]
            )
            # Parse the JSON array of 4 questions
            impeach_questions = _parse_json_robustly(impeach_resp.content.strip())
            if isinstance(impeach_questions, list) and len(impeach_questions) >= 2:
                impeach_questions = [str(q) for q in impeach_questions[:4]]
            else:
                # Fallback: treat as single question
                impeach_questions = [impeach_resp.content.strip()]
        except Exception as e:
            logger.error(f"Impeachment question error: {e}", exc_info=True)
            impeach_questions = []

        for i, q_text in enumerate(impeach_questions):
            step_label = impeachment_step_labels[i] if i < len(impeachment_step_labels) else f"Step {i + 1}"
            logger.info(f"[IMPEACH] Step {i + 1}/{len(impeach_questions)} ({step_label}): {q_text[:60]}...")
            transcript.append(AIMessage(content=q_text, name="Defense Counsel"))
            _ask_with_objection_gate(
                question_text=q_text,
                asking_name="Defense Counsel",
                opposing_name="Prosecutor",
                opposing_model=AGENT_MODELS["Prosecutor"],
                witness_name=current_witness,
                witness_llm=wit_llm,
                fc_llm=fc_llm,
                judge_ruling_llm=judge_ruling_llm,
                facts=facts,
                jx=jx,
                phase_type="impeachment",
                transcript=transcript,
                objection_log=objection_log,
                qa_log=impeachment_log,
                answer_key="answer",
                qa_wrapper=True,
            )

        # ── ADVERSARIAL: Redirect Examination (up to 3 questions with objection check) ──
        try:
            redirect_resp = pros_llm.invoke(
                [
                    SystemMessage(content=p.prosecution_redirect_prompt(jx)),
                    HumanMessage(
                        content=(
                            f"REDIRECT — rehabilitate {current_witness} after impeachment.\n"
                            f"Their direct Q&A: {direct_qa}\n\n"
                            f"Case facts:\n{facts}"
                        )
                    ),
                ]
            )
            redirect_questions = _parse_json_robustly(redirect_resp.content.strip())
            if isinstance(redirect_questions, list) and len(redirect_questions) >= 1:
                redirect_questions = [str(q) for q in redirect_questions[:3]]
            else:
                redirect_questions = [redirect_resp.content.strip()] if redirect_resp.content.strip() else []
        except Exception as e:
            logger.error(f"Redirect question error: {e}", exc_info=True)
            redirect_questions = []

        for i, q_text in enumerate(redirect_questions):
            logger.info(f"[REDIRECT] Q{i + 1}/{len(redirect_questions)}: {q_text[:60]}...")
            transcript.append(AIMessage(content=q_text, name="Prosecutor"))
            _ask_with_objection_gate(
                question_text=q_text,
                asking_name="Prosecutor",
                opposing_name="Defense Counsel",
                opposing_model=AGENT_MODELS["Defense Counsel"],
                witness_name=current_witness,
                witness_llm=wit_llm,
                fc_llm=fc_llm,
                judge_ruling_llm=judge_ruling_llm,
                facts=facts,
                jx=jx,
                phase_type="redirect",
                transcript=transcript,
                objection_log=objection_log,
            )
    else:
        transcript.append(
            AIMessage(
                content=f"⚖️ Inquisitorial Witness Examination of {current_witness} — Defence supplementary questioning begins.",
                name="Judge",
            )
        )
        transcript.append(
            AIMessage(content=f"Maître — any supplementary questions for {current_witness}?", name="Judge")
        )
        transcript.append(AIMessage(content="Oui, Monsieur le Président.", name="Defense Counsel"))

        # ── INQUISITORIAL: Defense follow-up (up to 8 Qs, with objection checks) ──
        _examination_loop(
            examiner_llm=def_llm,
            examiner_prompt_fn=p.defense_prompt,
            examiner_name="Defense Counsel",
            witness_name=current_witness,
            witness_llm=wit_llm,
            fc_llm=fc_llm,
            facts=facts,
            jx=jx,
            phase_type="inquisitorial_defense",
            max_q=8,
            transcript=transcript,
            judge_ruling_llm=judge_ruling_llm,
            objection_log=objection_log,
        )

    # Examination of current witness complete — clear current_witness
    updated_state = {**state, "transcript": state.get("transcript", []) + transcript}
    clerk_update = _clerk_compression(updated_state)

    return {
        "current_witness": None,
        "witness_direct_qa": [],
        "transcript": transcript,
        "impeachment_attempts": impeachment_log,
        "objection_history": objection_log,
        **clerk_update,
    }
