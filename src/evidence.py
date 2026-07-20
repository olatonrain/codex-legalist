"""Evidence submission and ruling nodes — exhibits, objections, judge rulings."""
import threading

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

import src.prompts as p
from src.config import AGENT_MODELS
from src.llm import get_llm, get_structured_llm
from src.logger import get_logger
from src.schemas import EvidenceObjectionDecision, JudgeRuling, ObjectionOutput
from src.state import TrialState
from src.trial_phases import (
    _clerk_compression,
    _get_jx,
    _has_actionable_case_facts,
    _insufficient_record_evidence,
    _strip_ruling_preamble,
)

logger = get_logger(__name__)

_no_objection_lock = threading.Lock()
_no_objection_counter: dict[str, int] = {}


def _human_msg_with_images(text: str, image_uris: list[str]) -> list:
    """Build a HumanMessage content list, appending image_url blocks if image_uris is non-empty.

    When no images are present, returns a plain string for backward-compatible message construction.
    """
    if not image_uris:
        return text
    content: list = [{"type": "text", "text": text}]
    for uri in image_uris:
        content.append({"type": "image_url", "image_url": {"url": uri}})
    return content

_OBJECTION_TYPE_NAMES = {
    "hearsay": "Hearsay",
    "relevance": "Relevance",
    "speculation": "Speculation",
    "leading": "Leading Question",
    "compound": "Compound Question",
    "foundation": "Lack of Foundation",
    "narrative": "Narrative",
    "privilege": "Privilege",
    "character": "Improper Character Evidence",
    "prejudice": "Prejudicial / Unfairly Prejudicial",
    "best_evidence": "Best Evidence Rule",
    "authentication": "Lack of Authentication",
    "cumulative": "Cumulative / Waste of Time",
}


def _issue_structured_objection(llm, prompt_func, jx: dict, evidence_text: str, facts: str) -> ObjectionOutput:
    """Have counsel issue a structured objection with a specific type and rule citation."""
    try:
        obj = llm.invoke(
            [
                SystemMessage(content=prompt_func(jx)),
                HumanMessage(
                    content=(
                        f'Evidence presented:\n"{evidence_text}"\n\n'
                        f"Case facts:\n{facts}\n\n"
                        f"Raise ONE objection. Choose from these types: {', '.join(_OBJECTION_TYPE_NAMES.keys())}.\n"
                        f"Cite a specific rule from: {jx['evidence_rules']}.\n"
                        f"Return a JSON object with keys: objection_type, rule_cited, rationale."
                    )
                ),
            ]
        )
        return obj
    except Exception as e:
        logger.error(f"Structured objection error: {e}", exc_info=True)
        return ObjectionOutput(
            objection_type="relevance",
            rule_cited=jx["evidence_rules"],
            rationale="Objection — the evidence is not relevant.",
        )


def _argue_hearsay_exception(llm, prompt_func, jx: dict, objection: ObjectionOutput, evidence_text: str) -> str:
    """When hearsay is objected, the offering party argues a specific exception."""
    try:
        resp = llm.invoke(
            [
                SystemMessage(content=prompt_func(jx)),
                HumanMessage(
                    content=(
                        f"Opposing counsel objected: {objection.objection_type.upper()} — {objection.rationale}\n"
                        f'Your evidence: "{evidence_text}"\n\n'
                        f"Argue ONE specific hearsay exception from {jx['evidence_rules']} in 25 words or fewer. "
                        f"Possible exceptions: excited utterance, present sense impression, statement for medical diagnosis, "
                        f"business records, public records, dying declaration, statement against interest, then-existing mental/emotional condition."
                    )
                ),
            ]
        )
        return resp.content
    except Exception:
        return "The evidence falls within an applicable exception under the governing rules."


def _judge_rule_on_objection(
    judge_llm, jx: dict, evidence: str, objection: ObjectionOutput, exception_arg: str = "",
    image_uris: list[str] | None = None,
) -> JudgeRuling:
    """Judge rules on a structured objection, optionally considering a hearsay exception argument."""
    exception_block = f"\nThe offering party argues the following exception: {exception_arg}" if exception_arg else ""
    result = judge_llm.invoke(
        [
            SystemMessage(content=p.judge_prompt(jx)),
            HumanMessage(
                content=_human_msg_with_images(
                    f"Evidence: {evidence}\n\n"
                    f"Objection — Type: {_OBJECTION_TYPE_NAMES.get(objection.objection_type, objection.objection_type)}\n"
                    f"Rule cited: {objection.rule_cited}\n"
                    f"Rationale: {objection.rationale}{exception_block}\n\n"
                    f"Rule on this objection under {jx['evidence_rules']}. If the objection is 'hearsay' and a valid "
                    f"exception was argued, OVERRULE."
                    f"If the evidence is admissible for one purpose but not another (e.g. not for the truth of the matter but for showing notice or state of mind), "
                    f"rule 'SUSTAINED IN PART' and provide a limiting_instruction specifying exactly what use is permissible."
                    f"Return a JSON object with ruling, rationale, objection_type, and limiting_instruction (empty string if not needed).",
                    image_uris or [],
                )
            ),
        ]
    )
    return result


def evidence_node(state: TrialState) -> dict:
    """
    Multi-round adversarial evidence exchange with structured objections.
    Prosecution presents → Defence objects (typed) → Prosecution argues exception if hearsay → Judge rules.
    Then Defence presents → Prosecution objects (typed) → Defence argues exception if hearsay → Judge rules.
    """
    logger.info("--- EVIDENCE PRESENTATION ---")
    jx = _get_jx(state)
    facts = state.get("case_description", "")
    image_uris = state.get("multimodal_evidence", [])
    has_images = bool(image_uris)
    transcript = []
    objection_log = list(state.get("objection_history", []))
    if not _has_actionable_case_facts(facts):
        return _insufficient_record_evidence(jx)

    pros_model = AGENT_MODELS["Evidence"] if has_images else AGENT_MODELS["Prosecutor"]
    def_model = AGENT_MODELS["Evidence"] if has_images else AGENT_MODELS["Defense Counsel"]
    pros_llm = get_llm(temperature=0.6, model=pros_model)
    def_llm = get_llm(temperature=0.6, model=def_model)
    judge_llm = get_structured_llm(JudgeRuling, temperature=0.1, model=AGENT_MODELS["Judge"])
    def_decision_llm = get_structured_llm(
        EvidenceObjectionDecision, temperature=0.3, model=def_model
    )
    pros_decision_llm = get_structured_llm(EvidenceObjectionDecision, temperature=0.3, model=pros_model)
    # ── Round 1: Prosecution presents, Defence OPTIONALLY objects ─────────────
    pros_ev = pros_llm.invoke(
        [
            SystemMessage(content=p.prosecutor_prompt(jx)),
            HumanMessage(
                content=_human_msg_with_images(
                    f"Present ONE piece of evidence in 40 words or fewer.\n"
                    f"For EACH exhibit you MUST include AUTHENTICATION: name the exhibit by its letter, "
                    f"state who created/received/maintained it, how it was obtained, and whether it is a "
                    f"business record, direct observation, or other admissible form.\n"
                    f"Example: 'The prosecution tenders Exhibit D, an internal email from X to Y dated Z, "
                    f"obtained from the company server and identified by the IT custodian. It is a business record.'\n"
                    f"Ground every detail in the case facts. Do NOT invent dates or names not in the facts.\n"
                    f"Case facts:\n{facts}",
                    image_uris,
                )
            ),
        ]
    )
    transcript.append(AIMessage(content=pros_ev.content, name="Prosecutor"))

    # Defence decides whether to object
    try:
        def_decision = def_decision_llm.invoke(
            [
                SystemMessage(content=p.defense_objection_prompt(jx)),
                HumanMessage(
                    content=_human_msg_with_images(
                        f'The prosecution has presented this evidence:\n"{pros_ev.content}"\n\n'
                        f"Case facts:\n{facts}\n\n"
                        f"Does this evidence have a GENUINE, CLEAR admissibility defect under {jx['evidence_rules']}? "
                        f"If yes, set should_object=true and specify the defect. "
                        f"If the evidence appears admissible (even if unfavourable), set should_object=false. "
                        f"Return a JSON object with: should_object, objection_type, rule_cited, rationale.",
                        image_uris,
                    )
                ),
            ]
        )
    except Exception as e:
        logger.error(f"Evidence objection decision error (defence): {e}", exc_info=True)
        def_decision = EvidenceObjectionDecision(should_object=False)

    if def_decision.should_object and def_decision.objection_type:
        transcript.append(
            AIMessage(
                content=f"Objection — {_OBJECTION_TYPE_NAMES.get(def_decision.objection_type, def_decision.objection_type).upper()}. {def_decision.rule_cited}: {def_decision.rationale}",
                name="Defense Counsel",
            )
        )
        exception_arg = ""
        if def_decision.objection_type == "hearsay":
            obj_out = ObjectionOutput(
                objection_type=def_decision.objection_type,
                rule_cited=def_decision.rule_cited,
                rationale=def_decision.rationale,
            )
            exception_arg = _argue_hearsay_exception(pros_llm, p.prosecutor_prompt, jx, obj_out, pros_ev.content)
            transcript.append(AIMessage(content=f"Response — {exception_arg}", name="Prosecutor"))

        obj_for_ruling = ObjectionOutput(
            objection_type=def_decision.objection_type,
            rule_cited=def_decision.rule_cited,
            rationale=def_decision.rationale,
        )
        ruling1 = _judge_rule_on_objection(
            judge_llm,
            jx,
            pros_ev.content,
            obj_for_ruling,
            exception_arg if def_decision.objection_type == "hearsay" else "",
            image_uris=image_uris,
        )
        objection_log.append(
            {
                "phase": "evidence",
                "round": 1,
                "objector": "Defense Counsel",
                "evidence": pros_ev.content,
                "objection_type": def_decision.objection_type,
                "rule_cited": def_decision.rule_cited,
                "rationale": def_decision.rationale,
                "hearsay_exception_argued": exception_arg if def_decision.objection_type == "hearsay" else None,
                "ruling": ruling1.ruling,
                "ruling_rationale": ruling1.rationale,
            }
        )
        ruling1_text = f"The objection is {ruling1.ruling}." + (
            f" {_strip_ruling_preamble(ruling1.rationale, ruling1.ruling)}" if ruling1.rationale else ""
        )
        if ruling1.limiting_instruction:
            ruling1_text += f" Limiting instruction: {ruling1.limiting_instruction}"
        transcript.append(AIMessage(content=ruling1_text, name="Judge"))
    else:
        # No objection — evidence stands without challenge
        transcript.append(
            AIMessage(
                content="No objection. The evidence is admitted.",
                name="Defense Counsel",
            )
        )

    # ── Round 2: Defence presents, Prosecution OPTIONALLY objects ─────────────
    def_ev = def_llm.invoke(
        [
            SystemMessage(content=p.defense_prompt(jx)),
            HumanMessage(
                content=_human_msg_with_images(
                    f"Present ONE piece of evidence for the defence in 40 words or fewer.\n"
                    f"For EACH exhibit you MUST include AUTHENTICATION: name the exhibit by its letter, "
                    f"state who created/received/maintained it, how it was obtained, and whether it is a "
                    f"business record, direct observation, or other admissible form.\n"
                    f"Ground every detail in the case facts. Do NOT invent details.\n"
                    f"Case facts:\n{facts}",
                    image_uris,
                )
            ),
        ]
    )
    transcript.append(AIMessage(content=def_ev.content, name="Defense Counsel"))

    # Prosecution decides whether to object
    try:
        pros_decision = pros_decision_llm.invoke(
            [
                SystemMessage(content=p.prosecution_objection_prompt(jx)),
                HumanMessage(
                    content=_human_msg_with_images(
                        f'The defence has presented this evidence:\n"{def_ev.content}"\n\n'
                        f"Case facts:\n{facts}\n\n"
                        f"Does this evidence have a GENUINE, CLEAR admissibility defect under {jx['evidence_rules']}? "
                        f"If yes, set should_object=true and specify the defect. "
                        f"If the evidence appears admissible (even if unfavourable), set should_object=false. "
                        f"Return a JSON object with: should_object, objection_type, rule_cited, rationale.",
                        image_uris,
                    )
                ),
            ]
        )
    except Exception as e:
        logger.error(f"Evidence objection decision error (prosecution): {e}", exc_info=True)
        pros_decision = EvidenceObjectionDecision(should_object=False)

    if pros_decision.should_object and pros_decision.objection_type:
        transcript.append(
            AIMessage(
                content=f"Objection — {_OBJECTION_TYPE_NAMES.get(pros_decision.objection_type, pros_decision.objection_type).upper()}. {pros_decision.rule_cited}: {pros_decision.rationale}",
                name="Prosecutor",
            )
        )
        exception_arg2 = ""
        if pros_decision.objection_type == "hearsay":
            obj_out2 = ObjectionOutput(
                objection_type=pros_decision.objection_type,
                rule_cited=pros_decision.rule_cited,
                rationale=pros_decision.rationale,
            )
            exception_arg2 = _argue_hearsay_exception(def_llm, p.defense_prompt, jx, obj_out2, def_ev.content)
            transcript.append(AIMessage(content=f"Response — {exception_arg2}", name="Defense Counsel"))

        obj_for_ruling2 = ObjectionOutput(
            objection_type=pros_decision.objection_type,
            rule_cited=pros_decision.rule_cited,
            rationale=pros_decision.rationale,
        )
        ruling2 = _judge_rule_on_objection(
            judge_llm,
            jx,
            def_ev.content,
            obj_for_ruling2,
            exception_arg2 if pros_decision.objection_type == "hearsay" else "",
            image_uris=image_uris,
        )
        objection_log.append(
            {
                "phase": "evidence",
                "round": 2,
                "objector": "Prosecutor",
                "evidence": def_ev.content,
                "objection_type": pros_decision.objection_type,
                "rule_cited": pros_decision.rule_cited,
                "rationale": pros_decision.rationale,
                "hearsay_exception_argued": exception_arg2 if pros_decision.objection_type == "hearsay" else None,
                "ruling": ruling2.ruling,
                "ruling_rationale": ruling2.rationale,
            }
        )
        ruling2_text = f"The objection is {ruling2.ruling}." + (
            f" {_strip_ruling_preamble(ruling2.rationale, ruling2.ruling)}" if ruling2.rationale else ""
        )
        if ruling2.limiting_instruction:
            ruling2_text += f" Limiting instruction: {ruling2.limiting_instruction}"
        transcript.append(AIMessage(content=ruling2_text, name="Judge"))
    else:
        transcript.append(
            AIMessage(
                content="No objection. The evidence is admitted.",
                name="Prosecutor",
            )
        )

    # Update clerk state immediately with the new rulings
    updated_state = {**state, "transcript": state.get("transcript", []) + transcript}
    clerk_update = _clerk_compression(updated_state)
    return {"transcript": transcript, "objection_history": objection_log, **clerk_update}


def rebuttal_evidence_node(state: TrialState) -> dict:
    """Prosecution rebuttal → defence surrebuttal after all witnesses."""
    logger.info("--- REBUTTAL EVIDENCE ---")
    jx = _get_jx(state)
    facts = state.get("case_description", "")
    image_uris = state.get("multimodal_evidence", [])
    has_images = bool(image_uris)
    transcript = []
    if not _has_actionable_case_facts(facts):
        return _insufficient_record_evidence(jx)

    try:
        pros_model = AGENT_MODELS["Evidence"] if has_images else AGENT_MODELS["Prosecutor"]
        def_model = AGENT_MODELS["Evidence"] if has_images else AGENT_MODELS["Defense Counsel"]
        pros_llm = get_llm(temperature=0.6, model=pros_model)
        def_llm = get_llm(temperature=0.6, model=def_model)
        judge_llm = get_structured_llm(JudgeRuling, temperature=0.1, model=AGENT_MODELS["Judge"])
    except Exception as e:
        logger.error("Rebuttal LLM init error: %s", e, exc_info=True)
        return {"transcript": [AIMessage(content=f"[Rebuttal Error: LLM init failed — {e}]", name="System")]}

    try:
        # Round 1: Prosecution rebuttal
        pros_rebut = pros_llm.invoke(
            [
                SystemMessage(content=p.prosecutor_prompt(jx)),
                HumanMessage(
                    content=_human_msg_with_images(
                        f"Present ONE rebuttal exhibit in 40 words or fewer. Name it and state why it rebuts "
                        f"the defence's case. Ground it in the case facts.\nCase facts:\n{facts}",
                        image_uris,
                    )
                ),
            ]
        )
        transcript.append(AIMessage(content=pros_rebut.content, name="Prosecutor"))

        def_obj = def_llm.invoke(
            [
                SystemMessage(content=p.defense_prompt(jx)),
                HumanMessage(
                    content=_human_msg_with_images(
                        f'Prosecution rebuttal:\n"{pros_rebut.content}"\n\n'
                        f"Object in 30 words or fewer. Cite the specific rule from {jx['evidence_rules']}.",
                        image_uris,
                    )
                ),
            ]
        )
        transcript.append(AIMessage(content=def_obj.content, name="Defense Counsel"))

        ruling1 = judge_llm.invoke(
            [
                SystemMessage(content=p.judge_prompt(jx)),
                HumanMessage(
                    content=_human_msg_with_images(
                        f"Prosecution rebuttal: {pros_rebut.content}\n"
                        f"Defence objects: {def_obj.content}\n\n"
                        f"Rule on the objection under {jx['evidence_rules']}.\n"
                        f"Return JSON with two keys: \"ruling\" (either 'SUSTAINED' or 'OVERRULED') "
                        f'and "rationale" (your legal basis citing the specific rule).',
                        image_uris,
                    )
                ),
            ]
        )
        ruling1_text = f"The objection is {ruling1.ruling}." + (
            f" {_strip_ruling_preamble(ruling1.rationale, ruling1.ruling)}" if ruling1.rationale else ""
        )
        transcript.append(AIMessage(content=ruling1_text, name="Judge"))

        # Round 2: Defence surrebuttal
        def_sur = def_llm.invoke(
            [
                SystemMessage(content=p.defense_prompt(jx)),
                HumanMessage(
                    content=_human_msg_with_images(
                        f"Present ONE surrebuttal exhibit in 40 words or fewer. Name it and state why it "
                        f"responds to the prosecution's rebuttal. Ground it in the case facts.\nCase facts:\n{facts}",
                        image_uris,
                    )
                ),
            ]
        )
        transcript.append(AIMessage(content=def_sur.content, name="Defense Counsel"))

        pros_obj = pros_llm.invoke(
            [
                SystemMessage(content=p.prosecutor_prompt(jx)),
                HumanMessage(
                    content=_human_msg_with_images(
                        f'Defence surrebuttal:\n"{def_sur.content}"\n\n'
                        f"Object in 30 words or fewer. Cite the specific rule from {jx['evidence_rules']}.",
                        image_uris,
                    )
                ),
            ]
        )
        transcript.append(AIMessage(content=pros_obj.content, name="Prosecutor"))

        ruling2 = judge_llm.invoke(
            [
                SystemMessage(content=p.judge_prompt(jx)),
                HumanMessage(
                    content=_human_msg_with_images(
                        f"Defence surrebuttal: {def_sur.content}\n"
                        f"Prosecution objects: {pros_obj.content}\n\n"
                        f"Rule on the objection under {jx['evidence_rules']}.\n"
                        f"Return JSON with two keys: \"ruling\" (either 'SUSTAINED' or 'OVERRULED') "
                        f'and "rationale" (your legal basis citing the specific rule).',
                        image_uris,
                    )
                ),
            ]
        )
        ruling2_text = f"The objection is {ruling2.ruling}." + (
            f" {_strip_ruling_preamble(ruling2.rationale, ruling2.ruling)}" if ruling2.rationale else ""
        )
        transcript.append(AIMessage(content=ruling2_text, name="Judge"))
    except Exception as e:
        logger.error("Rebuttal evidence processing error: %s", e, exc_info=True)
        transcript.append(AIMessage(content=f"[Rebuttal Error: {e}]", name="System"))

    updated_state = {**state, "transcript": state.get("transcript", []) + transcript}
    clerk_update = _clerk_compression(updated_state)
    return {"transcript": transcript, "rebuttal_rounds": 1, **clerk_update}
