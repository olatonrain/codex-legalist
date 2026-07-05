from src.state import TrialState
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from src.security import detect_prompt_injection
from src.llm import get_llm, get_structured_llm
from src.config import AGENT_MODELS
from src.logger import get_logger
import src.prompts as p
from pydantic import BaseModel, Field
import asyncio
import re

logger = get_logger(__name__)

# ── Pydantic Output Schemas ───────────────────────────────────────────────────

class MagistrateOutput(BaseModel):
    clarifying_questions: list[str] = Field(description="Between 1 and 5 critical clarifying questions about the case. Generate fewer questions for simple cases, up to 5 for complex cases.")
    witnesses: list[str] = Field(description="Named individuals in the case facts who should be called as witnesses. Empty list if none are named.")
    missing_evidence: list[str] = Field(default_factory=list, description="Types of evidence that are missing from the case facts but would be needed to prove the case (e.g., 'CCTV footage', 'financial records', 'DNA evidence'). Empty list if evidence seems sufficient.")
    missing_witnesses: list[str] = Field(default_factory=list, description="Types of witnesses that are missing from the case facts but would be needed (e.g., 'eyewitness', 'forensic expert', 'medical examiner'). Empty list if witnesses seem sufficient.")

class ClerkOutput(BaseModel):
    fact_sheet: str = Field(description="Compressed summary of established facts.")
    admitted_evidence: list[str] = Field(description="Formally admitted evidence items.")
    excluded_evidence: list[str] = Field(description="Excluded evidence items (inadmissible).")

class JudgeRuling(BaseModel):
    ruling: str = Field(description="Must be exactly 'SUSTAINED' or 'OVERRULED'.")
    rationale: str = Field(default="", description="Legal basis for the ruling, citing the specific rule of evidence.")

class JuryVerdict(BaseModel):
    verdict: str = Field(description="'Guilty', 'Not Guilty', 'Liable', or 'Not Liable'.")
    rationale: str = Field(description="Which admitted evidence led to this verdict and whether the legal standard was met.")

class JurorProfile(BaseModel):
    juror_id: int = Field(description="Juror number, starting from 1.")
    name: str = Field(description="A plausible juror name.")
    occupation: str = Field(description="Occupation or life experience tied to a case issue.")
    persona: str = Field(description="Short persona label grounded in admitted case issues.")
    bias: str = Field(description="Case-specific lens or concern. Must not invent facts.")

class JuryPanelOutput(BaseModel):
    jurors: list[JurorProfile] = Field(description="Juror profiles for a jury trial — exact count specified in the prompt.")

class JurorPosition(BaseModel):
    juror_id: int = Field(description="Juror number matching the generated jury panel.")
    stance: str = Field(description="'Guilty', 'Not Guilty', 'Liable', 'Not Liable', or 'Undecided'.")
    quote: str = Field(description="One concise deliberation statement based only on admitted evidence.")

class DeliberationOutput(BaseModel):
    positions: list[JurorPosition] = Field(description="Exactly one position for each juror profile.")
    guilty_or_liable_count: int = Field(description="Number voting Guilty or Liable.")
    not_guilty_or_not_liable_count: int = Field(description="Number voting Not Guilty or Not Liable.")
    undecided_count: int = Field(description="Number still undecided.")
    verdict: str = Field(description="'Guilty', 'Not Guilty', 'Liable', 'Not Liable', or 'Hung'.")
    rationale: str = Field(description="Consensus or deadlock rationale using admitted evidence only.")


# ── Ruling Preamble Stripper ──────────────────────────────────────────────────

_PREAMBLE_PATTERNS = [
    r"^(?:the\s+)?objection\s+is\s+(?:sustained|overruled)[\.\s:;,-]*",
    r"^(?:the\s+)?motion\s+is\s+(?:sustained|overruled|granted|denied)[\.\s:;,-]*",
    r"^(?:sustained|overruled)[\.\s:;,-]+",
]

def _strip_ruling_preamble(rationale: str, ruling: str) -> str:
    """Remove redundant ruling preamble from rationale to avoid duplication."""
    if not rationale:
        return ""
    text = rationale.strip()
    ruling_upper = ruling.upper()
    for pattern in _PREAMBLE_PATTERNS:
        text = re.sub(pattern, "", text, count=1, flags=re.IGNORECASE)
    if text.startswith(ruling_upper):
        text = text[len(ruling_upper):].lstrip(".:;,- ").strip()
    return text


# ── Fact Sufficiency Helpers ─────────────────────────────────────────────────

_MIN_FACT_WORDS = 8


def _has_actionable_case_facts(facts: str) -> bool:
    """Return True only when the record has enough detail for advocacy."""
    words = re.findall(r"[A-Za-z0-9]+", facts or "")
    return len(words) >= _MIN_FACT_WORDS


def _pydantic_to_dict(model: BaseModel) -> dict:
    """Support both Pydantic v1 and v2 in local/dev environments."""
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _insufficient_record_opening(jx: dict) -> dict:
    address = jx["address"].split(";")[0]
    return {"transcript": [
        AIMessage(
            content=(
                f"{address}, the prosecution cannot responsibly open on the present record. "
                "The case facts provided are too limited to identify the alleged offence, parties, "
                "timeline, witnesses, or evidence. The prosecution requests fuller particulars before proceeding."
            ),
            name="Prosecutor",
        ),
        AIMessage(
            content=(
                f"{address}, the defence also cannot respond to a case that has not been particularised. "
                "No factual allegation or evidence should be assumed from the current record."
            ),
            name="Defense Counsel",
        ),
    ]}


def _insufficient_record_evidence(jx: dict) -> dict:
    address = jx["address"].split(";")[0]
    return {
        "transcript": [
            AIMessage(
                content=(
                    f"{address}, No exhibit is tendered. The prosecution has not been given enough "
                    "case facts to identify a specific item of evidence or lay a proper foundation."
                ),
                name="Prosecutor",
            ),
            AIMessage(
                content=(
                    f"{address}, the defence objects to any attempt to infer evidence from an incomplete record."
                ),
                name="Defense Counsel",
            ),
            AIMessage(
                content=(
                    "The objection is SUSTAINED. No evidence is admitted because the record contains "
                    "insufficient facts to authenticate or assess relevance."
                ),
                name="Judge",
            ),
        ],
        "admitted_evidence": [],
        "excluded_evidence": [],
    }


# ── Jurisdiction Helper ───────────────────────────────────────────────────────

def _get_jx(state: TrialState) -> dict:
    """Extracts jurisdiction context from state into the dict used by prompts."""
    case_type = state.get("case_type", "Criminal")
    country   = state.get("country", "United Kingdom")
    return {
        "country":       country,
        "system":        state.get("jurisdiction_system", "Common Law"),
        "procedure":     state.get("jurisdiction_procedure", "adversarial"),
        "case_type":     case_type,
        "legal_standard": (
            state.get("criminal_standard", "Beyond reasonable doubt")
            if case_type == "Criminal"
            else state.get("civil_standard", "Balance of probabilities")
        ),
        "evidence_rules": state.get("evidence_rules", "Applicable rules of evidence"),
        "jury_enabled":  state.get("jury_enabled", True),
        "jury_profiles": state.get("jury_profiles", []),
        "cross":         state.get("cross_examination", True),
        "address":       state.get("court_address", "Your Honour"),
    }


def generate_dynamic_jury_profiles(state: TrialState) -> list[dict]:
    """Generate case-specific juror profiles for jury jurisdictions.
    Panel size is read from state['jury_count'] (default 12).
    """
    jx = _get_jx(state)
    if not jx["jury_enabled"]:
        return []

    existing = state.get("jury_profiles", [])
    if existing:
        return existing

    n = state.get("jury_count", 12)
    facts = state.get("case_description", "")
    admitted = state.get("admitted_evidence", [])
    fact_sheet = state.get("fact_sheet", "")
    llm = get_structured_llm(JuryPanelOutput, temperature=0.4, model=AGENT_MODELS["Jury Foreperson"])
    try:
        result = llm.invoke([
            SystemMessage(content=p.jury_panel_prompt(jx, n)),
            HumanMessage(content=(
                f"Generate exactly {n} juror profiles for this case. Each profile must be tied to "
                "issues visible in the case facts, fact sheet, or admitted evidence. Do not invent "
                "new case facts, new witnesses, excluded evidence, or external research.\n\n"
                f"Case facts:\n{facts}\n\n"
                f"Fact sheet:\n{fact_sheet}\n\n"
                f"Admitted evidence:\n{admitted}"
            ))
        ])
        profiles = [_pydantic_to_dict(profile) for profile in result.jurors[:n]]
        if len(profiles) < n:
            # Pad with generic profiles if LLM didn't generate enough
            for juror_id in range(len(profiles) + 1, n + 1):
                profiles.append({
                    "juror_id": juror_id,
                    "name": f"Juror {juror_id}",
                    "occupation": "Citizen juror",
                    "persona": "Evidence-focused juror",
                    "bias": "Reviews only admitted evidence and the legal standard",
                })
        return profiles
    except Exception as e:
        logger.error(f"Jury Profile Generation Error: {e}")
        return [
            {
                "juror_id": juror_id,
                "name": f"Juror {juror_id}",
                "occupation": "Citizen juror",
                "persona": "Evidence-focused juror",
                "bias": "Reviews only admitted evidence and the legal standard",
            }
            for juror_id in range(1, n + 1)
        ]


# ── Security Check ────────────────────────────────────────────────────────────

def security_check_node(state: TrialState) -> dict:
    """Scans case facts and any pre-trial answers for prompt injection."""
    logger.info("--- SECURITY CHECK ---")
    texts_to_scan = [
        state.get("case_description", ""),
        *[str(v) for v in state.get("human_answers", {}).values()]
    ]
    for text in texts_to_scan:
        if detect_prompt_injection(text):
            err = "[CONTEMPT OF COURT] Malicious input detected. Trial aborted."
            logger.error(err)
            return {"errors": [err]}
    return {"errors": []}


# ── Magistrate ────────────────────────────────────────────────────────────────

def magistrate_node(state: TrialState) -> dict:
    """Analyses case facts, drafts clarifying questions, extracts witness names, identifies missing items."""
    logger.info("--- MAGISTRATE NODE ---")
    jx = _get_jx(state)
    case_description = state.get("case_description", "")

    try:
        llm = get_structured_llm(MagistrateOutput, temperature=0.1, model=AGENT_MODELS["Magistrate"])
        result = llm.invoke([
            SystemMessage(content=p.magistrate_prompt(jx)),
            HumanMessage(content=f"Case facts:\n{case_description}")
        ])
        questions = [{"question": q} for q in result.clarifying_questions]
        witnesses = result.witnesses
        missing_evidence = result.missing_evidence if hasattr(result, 'missing_evidence') else []
        missing_witnesses = result.missing_witnesses if hasattr(result, 'missing_witnesses') else []
        return {
            "clarifying_questions": questions,
            "witness_queue": witnesses,
            "missing_evidence": missing_evidence,
            "missing_witnesses": missing_witnesses,
        }
    except Exception as e:
        logger.error(f"Magistrate Error: {e}")
        return {
            "clarifying_questions": [{"question": "Can you provide more details about the key events?"}],
            "witness_queue": [],
            "missing_evidence": [],
            "missing_witnesses": [],
        }


# ── Human Input ───────────────────────────────────────────────────────────────

def human_input_node(state: TrialState) -> dict:
    """Placeholder — human answers are injected by the UI before graph runs."""
    logger.info("--- HUMAN INPUT NODE ---")
    return {}


def _format_transcript_msg(m) -> str:
    """Safely format transcript entries that may be AIMessage objects or dicts."""
    if isinstance(m, dict):
        name = m.get("name") or m.get("agent") or "System"
        content = m.get("content") or m.get("text") or ""
        return f"[{name}]: {content}"
    name = getattr(m, "name", getattr(m, "type", "System"))
    content = getattr(m, "content", "")
    return f"[{name}]: {content}"


# ── Clerk Compression ─────────────────────────────────────────────────────────

def _clerk_compression(state: TrialState) -> dict:
    """Compresses transcript into fact sheet and evidence logs between phases."""
    jx = _get_jx(state)
    transcript_str = "\n".join(
        [_format_transcript_msg(m) for m in state.get("transcript", [])[-12:]]
    )
    if not transcript_str:
        return {}
    llm = get_structured_llm(ClerkOutput, temperature=0.1, model=AGENT_MODELS["Clerk"])
    try:
        res = llm.invoke([
            SystemMessage(content=p.clerk_prompt(jx)),
            HumanMessage(content=(
                f"Current Fact Sheet:\n{state.get('fact_sheet', '')}\n\n"
                f"Recent Transcript:\n{transcript_str}"
            ))
        ])
        return {
            "fact_sheet": res.fact_sheet,
            "admitted_evidence": res.admitted_evidence,
            "excluded_evidence": res.excluded_evidence,
        }
    except Exception:
        return {}


# ── Opening Statements ────────────────────────────────────────────────────────

def opening_statements_node(state: TrialState) -> dict:
    """Prosecution and Defence deliver opening statements."""
    logger.info("--- OPENING STATEMENTS ---")
    jx  = _get_jx(state)
    facts = state.get("case_description", "")
    if not _has_actionable_case_facts(facts):
        return _insufficient_record_opening(jx)

    try:
        # Prosecution opens first
        pros_llm = get_llm(temperature=0.7, model=AGENT_MODELS["Prosecutor"])
        pros_msg = pros_llm.invoke([
            SystemMessage(content=p.prosecutor_prompt(jx)),
            HumanMessage(content=(
                "Deliver your opening statement in 60 words or fewer. Be direct and punchy. "
                "State what you will prove and why. Ground every claim in the case facts. "
                "Do not use Markdown, bullet points, or invented details.\n\n"
                f"Case facts:\n{facts}"
            ))
        ])

        # Defence responds, having heard the prosecution's opening
        def_llm = get_llm(temperature=0.7, model=AGENT_MODELS["Defense Counsel"])
        def_msg = def_llm.invoke([
            SystemMessage(content=p.defense_prompt(jx)),
            HumanMessage(content=(
                f"The prosecution just said:\n\"{pros_msg.content}\"\n\n"
                "Respond in 60 words or fewer. Be direct. Challenge only what the facts don't support. "
                "Do not use Markdown, bullet points, or invented details.\n\n"
                f"Case facts:\n{facts}"
            ))
        ])

        return {"transcript": [
            AIMessage(content=pros_msg.content, name="Prosecutor"),
            AIMessage(content=def_msg.content, name="Defense Counsel"),
        ]}
    except Exception as e:
        logger.error(f"Opening Statements Error: {e}")
        return {"transcript": [
            AIMessage(content=f"[Opening statements could not be generated: {e}]", name="System"),
        ]}


# ── Evidence ──────────────────────────────────────────────────────────────────

def evidence_node(state: TrialState) -> dict:
    """
    Multi-round adversarial evidence exchange.
    Prosecution presents → Defence objects with specific rule → Judge rules.
    Then Defence presents evidence → Prosecution objects → Judge rules.
    """
    logger.info("--- EVIDENCE PRESENTATION ---")
    jx    = _get_jx(state)
    facts = state.get("case_description", "")
    transcript = []
    if not _has_actionable_case_facts(facts):
        return _insufficient_record_evidence(jx)

    pros_llm  = get_llm(temperature=0.6, model=AGENT_MODELS["Prosecutor"])
    def_llm   = get_llm(temperature=0.6, model=AGENT_MODELS["Defense Counsel"])
    judge_llm = get_structured_llm(JudgeRuling, temperature=0.1, model=AGENT_MODELS["Judge"])

    # ── Round 1: Prosecution presents, Defence objects ────────────
    pros_ev = pros_llm.invoke([
        SystemMessage(content=p.prosecutor_prompt(jx)),
        HumanMessage(content=(
            f"Present ONE piece of evidence in 40 words or fewer. Name it, describe it briefly, "
            f"and state why it's admissible under {jx['evidence_rules']}.\n"
            f"Case facts:\n{facts}"
        ))
    ])
    
    multimodal_evidence = state.get("multimodal_evidence", [])
        
    witnesses_called = list(state.get("witness_queue", []))
    if state.get("current_witness"):
        witnesses_called.append(state.get("current_witness"))
        
    for exhibit in multimodal_evidence:
        if exhibit.get("requires_author") and exhibit.get("name", "").lower() in pros_ev.content.lower():
            if exhibit.get("author") not in witnesses_called:
                transcript.append(AIMessage(content=f"You must call {exhibit['author']} to the stand first.", name="System"))
                return {"transcript": transcript}

    transcript.append(AIMessage(content=pros_ev.content, name="Prosecutor"))

    def_obj = def_llm.invoke([
        SystemMessage(content=p.defense_prompt(jx)),
        HumanMessage(content=(
            f"Prosecution presented:\n\"{pros_ev.content}\"\n\n"
            f"Object in 30 words or fewer. Cite the specific rule from {jx['evidence_rules']}."
        ))
    ])
    transcript.append(AIMessage(content=def_obj.content, name="Defense Counsel"))

    ruling1 = judge_llm.invoke([
        SystemMessage(content=p.judge_prompt(jx)),
        HumanMessage(content=(
            f"Prosecution presents: {pros_ev.content}\n"
            f"Defence objects: {def_obj.content}\n\n"
            f"Rule on the objection under {jx['evidence_rules']}.\n"
            f"Return JSON with two keys: \"ruling\" (either 'SUSTAINED' or 'OVERRULED') "
            f"and \"rationale\" (your legal basis citing the specific rule)."
        ))
    ])
    ruling1_text = f"The objection is {ruling1.ruling}." + (f" {_strip_ruling_preamble(ruling1.rationale, ruling1.ruling)}" if ruling1.rationale else "")
    transcript.append(AIMessage(content=ruling1_text, name="Judge"))

    # ── Round 2: Defence presents counter-evidence ────────────────
    def_ev = def_llm.invoke([
        SystemMessage(content=p.defense_prompt(jx)),
        HumanMessage(content=(
            f"Present ONE piece of evidence for the defence in 40 words or fewer. "
            f"Name it and state why it's admissible under {jx['evidence_rules']}.\n"
            f"Case facts:\n{facts}"
        ))
    ])
    transcript.append(AIMessage(content=def_ev.content, name="Defense Counsel"))

    pros_obj = pros_llm.invoke([
        SystemMessage(content=p.prosecutor_prompt(jx)),
        HumanMessage(content=(
            f"Defence presented:\n\"{def_ev.content}\"\n\n"
            f"Object in 30 words or fewer. Cite the specific rule from {jx['evidence_rules']}."
        ))
    ])
    transcript.append(AIMessage(content=pros_obj.content, name="Prosecutor"))

    ruling2 = judge_llm.invoke([
        SystemMessage(content=p.judge_prompt(jx)),
        HumanMessage(content=(
            f"Defence presents: {def_ev.content}\n"
            f"Prosecution objects: {pros_obj.content}\n\n"
            f"Rule on the objection under {jx['evidence_rules']}.\n"
            f"Return JSON with two keys: \"ruling\" (either 'SUSTAINED' or 'OVERRULED') "
            f"and \"rationale\" (your legal basis citing the specific rule)."
        ))
    ])
    ruling2_text = f"The objection is {ruling2.ruling}." + (f" {_strip_ruling_preamble(ruling2.rationale, ruling2.ruling)}" if ruling2.rationale else "")
    transcript.append(AIMessage(content=ruling2_text, name="Judge"))

    # Update clerk state immediately with the new rulings
    updated_state = {**state, "transcript": state.get("transcript", []) + transcript}
    clerk_update = _clerk_compression(updated_state)
    return {"transcript": transcript, **clerk_update}


# ── Witness Examination ───────────────────────────────────────────────────────

def witness_node(state: TrialState) -> dict:
    """
    Full examination protocol:
      Direct (3 Qs) → Fact Checker → Cross (2 Qs) → Redirect (if needed)
    Inquisitorial jurisdictions: Judge leads, counsel may suggest questions.
    """
    logger.info("--- WITNESS EXAMINATION ---")
    jx = _get_jx(state)
    witness_queue = list(state.get("witness_queue", []))
    if not witness_queue:
        return {}

    current_witness = witness_queue.pop(0)
    transcript = []
    facts = state.get("case_description", "")

    pros_llm = get_llm(temperature=0.6, model=AGENT_MODELS["Prosecutor"])
    def_llm  = get_llm(temperature=0.6, model=AGENT_MODELS["Defense Counsel"])
    wit_llm  = get_llm(temperature=0.5, model=AGENT_MODELS["Witness"])
    fc_llm   = get_llm(temperature=0.0, model=AGENT_MODELS["Fact Checker"])
    judge_llm = get_llm(temperature=0.1, model=AGENT_MODELS["Judge"])

    direct_qa = []  # Stores (question, answer) for cross-examination reference

    if jx["cross"]:
        # ── ADVERSARIAL: Direct Examination (3 questions) ─────────
        for q_num in range(1, 4):
            q = pros_llm.invoke([
                SystemMessage(content=p.prosecutor_prompt(jx)),
                HumanMessage(content=(
                    f"DIRECT — Q{q_num}/3 to {current_witness}.\n"
                    f"{'Prior: ' + str(direct_qa[-2:]) if direct_qa else ''}\n"
                    f"Ask ONE short question (under 20 words). Base it on the case facts.\n"
                    f"Facts:\n{facts}"
                ))
            ])
            transcript.append(AIMessage(content=q.content, name="Prosecutor"))

            a = wit_llm.invoke([
                SystemMessage(content=p.witness_prompt(jx)),
                HumanMessage(content=(
                    f"You are {current_witness}. Answer in 30 words or fewer.\n"
                    f"Q: {q.content}\n"
                    f"Case facts:\n{facts}"
                ))
            ])

            # Fact Checker gate (Two-Pass System)
            fc = fc_llm.invoke([
                SystemMessage(content=p.fact_checker_prompt(jx)),
                HumanMessage(content=(
                    f"Case facts:\n{facts}\n\n"
                    f"Witness answer:\n{a.content}"
                ))
            ])

            if not fc.content.strip().upper().startswith("PASS"):
                # Discard original witness answer and inject Teal Bubble correction
                transcript.append(AIMessage(content=fc.content, name="Fact Checker"))
                # Force regenerate
                a = wit_llm.invoke([
                    SystemMessage(content=p.witness_prompt(jx)),
                    HumanMessage(content=(
                        f"You are {current_witness}.\n"
                        f"Question: {q.content}\n"
                        f"Your previous answer was objected to: {fc.content}\n"
                        f"Acknowledge the correction and answer correctly based ONLY on these case facts:\n{facts}"
                    ))
                ])
                transcript.append(AIMessage(content=a.content, name="Witness"))
                direct_qa.append({"q": q.content, "a": a.content})
            else:
                transcript.append(AIMessage(content=a.content, name="Witness"))
                direct_qa.append({"q": q.content, "a": a.content})

        # ── ADVERSARIAL: Cross-Examination (2 questions) ──────────
        for q_num in range(1, 3):
            cross_q = def_llm.invoke([
                SystemMessage(content=p.defense_prompt(jx)),
                HumanMessage(content=(
                    f"CROSS — Q{q_num}/2 to {current_witness}.\n"
                    f"Their direct answers: {direct_qa}\n\n"
                    f"Ask ONE short leading question (under 20 words) that challenges their testimony."
                ))
            ])
            transcript.append(AIMessage(content=cross_q.content, name="Defense Counsel"))

            cross_a = wit_llm.invoke([
                SystemMessage(content=p.witness_prompt(jx)),
                HumanMessage(content=(
                    f"You are {current_witness}.\n"
                    f"The defence asks (cross-examination): {cross_q.content}\n"
                    f"Answer based ONLY on these case facts:\n{facts}"
                ))
            ])
            transcript.append(AIMessage(content=cross_a.content, name="Witness"))

    else:
        # ── INQUISITORIAL: Judge leads examination ─────────────────
        for q_num in range(1, 4):
            q = judge_llm.invoke([
                SystemMessage(content=p.judge_prompt(jx)),
                HumanMessage(content=(
                    f"JUDICIAL EXAMINATION — Question {q_num} of 3.\n"
                    f"Witness: {current_witness}.\n"
                    f"Ask a neutral, fact-finding question.\nCase facts:\n{facts}"
                ))
            ])
            transcript.append(AIMessage(content=f"Q (Judge): {q.content}", name="Judge"))

            a = wit_llm.invoke([
                SystemMessage(content=p.witness_prompt(jx)),
                HumanMessage(content=(
                    f"You are {current_witness}.\n"
                    f"The Judge asks: {q.content}\n"
                    f"Answer based ONLY on these case facts:\n{facts}"
                ))
            ])

            fc = fc_llm.invoke([
                SystemMessage(content=p.fact_checker_prompt(jx)),
                HumanMessage(content=f"Case facts:\n{facts}\n\nWitness answer:\n{a.content}")
            ])

            if not fc.content.strip().upper().startswith("PASS"):
                transcript.append(AIMessage(content=fc.content, name="Fact Checker"))
                a = wit_llm.invoke([
                    SystemMessage(content=p.witness_prompt(jx)),
                    HumanMessage(content=(
                        f"You are {current_witness}.\n"
                        f"The Judge asks: {q.content}\n"
                        f"Your previous answer was objected to: {fc.content}\n"
                        f"Acknowledge the correction and answer correctly based ONLY on these case facts:\n{facts}"
                    ))
                ])
                transcript.append(AIMessage(content=a.content, name="Witness"))
            else:
                transcript.append(AIMessage(content=a.content, name="Witness"))

    clerk_update = _clerk_compression(state)
    return {
        "witness_queue": witness_queue,
        "current_witness": current_witness,
        "transcript": transcript,
        **clerk_update
    }


# ── Closing Arguments ─────────────────────────────────────────────────────────

def closing_arguments_node(state: TrialState) -> dict:
    """Prosecution and Defence deliver closing arguments based on admitted facts."""
    logger.info("--- CLOSING ARGUMENTS ---")
    jx = _get_jx(state)
    fact_sheet = state.get("fact_sheet", state.get("case_description", ""))
    admitted   = state.get("admitted_evidence", [])
    excluded   = state.get("excluded_evidence", [])
    transcript = []

    try:
        # No-Case Submission
        def_llm = get_llm(temperature=0.7, model=AGENT_MODELS["Defense Counsel"])
        no_case_motion = def_llm.invoke([
            SystemMessage(content=p.defense_prompt(jx)),
            HumanMessage(content=(
                f"The prosecution has rested its case.\n"
                f"Admitted evidence:\n{admitted}\n"
                f"Fact sheet:\n{fact_sheet}\n\n"
                f"Evaluate if a prima facie case exists. If not, briefly move for acquittal (No-Case Submission). "
                f"If there is a case to answer, say 'The defence will proceed with closing arguments.'"
            ))
        ])
        
        if "acquittal" in no_case_motion.content.lower() or "no case" in no_case_motion.content.lower():
            transcript.append(AIMessage(content=no_case_motion.content, name="Defense Counsel"))
            judge_llm = get_structured_llm(JudgeRuling, temperature=0.1, model=AGENT_MODELS["Judge"])
            ruling = judge_llm.invoke([
                SystemMessage(content=p.judge_prompt(jx)),
                HumanMessage(content=(
                    f"The defence has made a No-Case Submission:\n{no_case_motion.content}\n\n"
                    f"Based on the admitted evidence: {admitted}, rule on the motion.\n"
                    f"Return 'SUSTAINED' to acquit, or 'OVERRULED' to proceed. Return your answer as a JSON object."
                ))
            ])
            transcript.append(AIMessage(content=f"Ruling on No-Case Submission: {ruling.ruling}. {_strip_ruling_preamble(ruling.rationale, ruling.ruling)}", name="Judge"))
            if ruling.ruling == "SUSTAINED":
                # Early termination
                transcript.append(AIMessage(content="The case is dismissed. The defendant is acquitted.", name="Judge"))
                return {"transcript": transcript, "main_verdict": "Not Guilty"}

        pros_llm = get_llm(temperature=0.7, model=AGENT_MODELS["Prosecutor"])
        pros_msg = pros_llm.invoke([
            SystemMessage(content=p.prosecutor_prompt(jx)),
            HumanMessage(content=(
                f"Closing argument in 80 words or fewer. Be direct and persuasive.\n\n"
                f"Admitted evidence:\n{admitted}\n\n"
                f"Do NOT reference excluded evidence: {excluded}\n\n"
                f"Standard: {jx['legal_standard']}"
            ))
        ])
        transcript.append(AIMessage(content=pros_msg.content, name="Prosecutor"))

        def_msg = def_llm.invoke([
            SystemMessage(content=p.defense_prompt(jx)),
            HumanMessage(content=(
                f"Prosecution argued:\n\"{pros_msg.content}\"\n\n"
                f"Respond in 80 words or fewer. Be direct.\n\n"
                f"Admitted evidence:\n{admitted}\n\n"
                f"Do NOT reference excluded evidence: {excluded}\n\n"
                f"Standard: {jx['legal_standard']}"
            ))
        ])
        transcript.append(AIMessage(content=def_msg.content, name="Defense Counsel"))

        return {"transcript": transcript}
    except Exception as e:
        logger.error(f"Closing Arguments Error: {e}")
        return {"transcript": [
            AIMessage(content=f"[Closing arguments could not be generated: {e}]", name="System"),
        ]}


# ── Jury Instructions ─────────────────────────────────────────────────────────

def jury_instructions_node(state: TrialState) -> dict:
    """Judge instructs the jury (or, in bench trials, summarises the law for themselves)."""
    logger.info("--- JURY INSTRUCTIONS ---")
    jx = _get_jx(state)
    try:
        judge_llm = get_llm(temperature=0.1, model=AGENT_MODELS["Judge"])
        msg = judge_llm.invoke([
            SystemMessage(content=p.judge_prompt(jx)),
            HumanMessage(content=(
                f"{'Instruct the jury' if jx['jury_enabled'] else 'Summarise the applicable law for the bench deliberation'}. "
                f"Clearly state:\n"
                f"1. The applicable standard of proof: {jx['legal_standard']}\n"
                f"2. The specific elements that must be proven\n"
                f"3. That the {'jury' if jx['jury_enabled'] else 'court'} must consider ONLY the admitted evidence\n"
                f"4. The excluded evidence that must be disregarded\n\n"
                f"Case facts summary:\n{state.get('fact_sheet', state.get('case_description', ''))}"
            ))
        ])
        return {"transcript": [AIMessage(content=msg.content, name="Judge")]}
    except Exception as e:
        logger.error(f"Jury Instructions Error: {e}")
        return {"transcript": [
            AIMessage(content=f"[Jury instructions could not be generated: {e}]", name="System"),
        ]}


# ── Jury Deliberation ─────────────────────────────────────────────────────────

# How many individual juror LLM calls to make before handing off to Foreperson
_MAX_INDIVIDUAL_JUROR_CALLS = 8


def _call_single_juror(
    juror_profile: dict,
    jx: dict,
    admitted: list,
    excluded: list,
    fact_sheet: str,
    prior_statements: list[str],
    round_num: int,
) -> tuple[str, str]:
    """
    Call a single juror as their own LLM agent.
    Returns (statement_text, vote_string).
    """
    from src.llm import get_llm
    juror_llm = get_llm(temperature=0.7, model=AGENT_MODELS.get("Witness", "qwen-flash"))

    prior_block = ""
    if prior_statements:
        prior_block = "\n\nFellow jurors have said:\n" + "\n".join(
            f"  - {s}" for s in prior_statements[-4:]  # last 4 to keep prompt lean
        )

    name = juror_profile.get("name", f"Juror {juror_profile.get('juror_id', '?')}")
    occupation = juror_profile.get("occupation", "Citizen juror")
    persona = juror_profile.get("persona", "Impartial juror")
    bias = juror_profile.get("bias", "Evidence-focused")

    try:
        resp = juror_llm.invoke([
            SystemMessage(content=p.juror_prompt(jx, juror_profile)),
            HumanMessage(content=(
                f"Round {round_num} of jury deliberation.\n\n"
                f"Your profile: {name}, {occupation}. Persona: {persona}. Lens: {bias}\n\n"
                f"Admitted evidence:\n{admitted}\n\n"
                f"Excluded evidence (do NOT consider):\n{excluded}\n\n"
                f"Case summary:\n{fact_sheet}"
                f"{prior_block}\n\n"
                f"In 2-4 sentences, state your deliberation position grounded in the admitted evidence. "
                f"Then on a new line state: Vote: Guilty / Not Guilty / Liable / Not Liable / Undecided"
            ))
        ])
        raw = resp.content.strip()
        # Extract vote from last line
        lines = [l.strip() for l in raw.split("\n") if l.strip()]
        vote = "Undecided"
        statement = raw
        for line in reversed(lines):
            if line.lower().startswith("vote:"):
                vote_raw = line[5:].strip().upper()
                if "NOT GUILTY" in vote_raw:
                    vote = "Not Guilty"
                elif "NOT LIABLE" in vote_raw:
                    vote = "Not Liable"
                elif "GUILTY" in vote_raw:
                    vote = "Guilty"
                elif "LIABLE" in vote_raw:
                    vote = "Liable"
                # Remove vote line from statement
                statement = "\n".join(l for l in lines if not l.lower().startswith("vote:")).strip()
                break
        return statement, vote
    except Exception as e:
        logger.error(f"[Juror {juror_profile.get('juror_id')} call error] {e}")
        return f"Based on the admitted evidence, I am deliberating carefully.", "Undecided"


def jury_deliberation_node(state: TrialState) -> dict:
    """
    Standards-based deliberation.
    - Jury trials: each juror is called as an INDIVIDUAL LLM agent (up to _MAX_INDIVIDUAL_JUROR_CALLS).
      Each reads what prior jurors said, building a real debate. Foreperson then summarises.
    - Bench trials: Judge renders a single reasoned verdict.
    """
    logger.info("--- JURY DELIBERATION ---")
    jx     = _get_jx(state)
    rounds = state.get("deliberation_rounds", 0) + 1
    admitted   = state.get("admitted_evidence", [])
    excluded   = state.get("excluded_evidence", [])
    fact_sheet = state.get("fact_sheet", state.get("case_description", ""))
    transcript = []
    prev_snapshot = state.get("deliberation_snapshot", {})

    try:
        # ── BENCH TRIAL ───────────────────────────────────────────────────────
        if not jx["jury_enabled"]:
            judge_llm = get_structured_llm(JuryVerdict, temperature=0.1, model=AGENT_MODELS["Judge"])
            verdict_res = judge_llm.invoke([
                SystemMessage(content=p.judge_prompt(jx)),
                HumanMessage(content=(
                    "Render the bench verdict as the finder of fact. Apply only the admitted evidence "
                    f"to the standard of {jx['legal_standard']}. Do not consider excluded evidence.\n\n"
                    f"Admitted evidence:\n{admitted}\n\n"
                    f"Excluded evidence:\n{excluded}\n\n"
                    f"Case summary:\n{fact_sheet}\n\n"
                    "Return your verdict as a JSON object."
                ))
            ])
            snapshot = {
                "type": "bench",
                "round": rounds,
                "total": 1,
                "guilty_or_liable_count": 1 if verdict_res.verdict in ["Guilty", "Liable"] else 0,
                "not_guilty_or_not_liable_count": 1 if verdict_res.verdict in ["Not Guilty", "Not Liable"] else 0,
                "undecided_count": 0,
                "verdict": verdict_res.verdict,
                "rationale": verdict_res.rationale,
                "positions": [{
                    "juror_id": 1,
                    "name": "Bench",
                    "occupation": "Presiding judge",
                    "persona": "Finder of fact",
                    "bias": "Bound by admitted evidence and the governing standard",
                    "stance": verdict_res.verdict,
                    "quote": verdict_res.rationale,
                }],
            }
            transcript.append(AIMessage(
                content=f"Bench verdict: {verdict_res.verdict}. {verdict_res.rationale}",
                name="Judge",
            ))
            return {
                "deliberation_rounds": rounds,
                "deliberation_snapshot": snapshot,
                "main_verdict": verdict_res.verdict,
                "transcript": transcript,
            }

        # ── JURY TRIAL — Individual juror calls ───────────────────────────────
        n = state.get("jury_count", 12)
        profiles = generate_dynamic_jury_profiles(state)
        if not profiles:
            profiles = [
                {
                    "juror_id": juror_id,
                    "name": f"Juror {juror_id}",
                    "occupation": "Citizen juror",
                    "persona": "Evidence-focused juror",
                    "bias": "Reviews only admitted evidence and the governing standard",
                }
                for juror_id in range(1, n + 1)
            ]
        jx["jury_profiles"] = profiles

        # Announce deliberation round
        if rounds == 1:
            transcript.append(AIMessage(
                content=(
                    f"Members of the jury, we will now deliberate. Remember the Judge's instructions: "
                    f"apply ONLY the admitted evidence to the standard of '{jx['legal_standard']}'. "
                    f"We have {len(profiles)} jurors. Let us hear each voice."
                ),
                name="Foreperson",
            ))
        else:
            prev_verdict = prev_snapshot.get("verdict", "Hung")
            prev_guilty = prev_snapshot.get("guilty_or_liable_count", 0)
            prev_not_guilty = prev_snapshot.get("not_guilty_or_not_liable_count", 0)
            prev_undecided = prev_snapshot.get("undecided_count", 0)
            transcript.append(AIMessage(
                content=(
                    f"The jury is deliberating further. Round {rounds}. "
                    f"Previous tally: {prev_guilty} for burden met, {prev_not_guilty} for burden not met, "
                    f"{prev_undecided} undecided. Jurors, please reconsider your positions in light of "
                    f"the discussion so far. If you remain unconvinced, state why clearly."
                ),
                name="Foreperson",
            ))

        # ── Individual juror calls (capped at _MAX_INDIVIDUAL_JUROR_CALLS) ───
        individual_count = min(len(profiles), _MAX_INDIVIDUAL_JUROR_CALLS)
        prior_statements: list[str] = []
        juror_votes: dict[int, str] = {}
        juror_positions: list[dict] = []

        # Include previous round positions for context
        prev_positions = prev_snapshot.get("positions", [])
        for pp in prev_positions:
            prior_statements.append(f"{pp.get('name', 'Juror')}: {pp.get('quote', '')} [Vote: {pp.get('stance', 'Undecided')}]")

        for i, profile in enumerate(profiles[:individual_count]):
            juror_id = profile.get("juror_id", i + 1)
            name = profile.get("name", f"Juror {juror_id}")
            statement, vote = _call_single_juror(
                profile, jx, admitted, excluded, fact_sheet, prior_statements, rounds
            )
            prior_statements.append(f"{name}: {statement} [Vote: {vote}]")
            juror_votes[juror_id] = vote
            juror_positions.append({
                **profile,
                "stance": vote,
                "quote": statement,
            })
            transcript.append(AIMessage(
                content=statement,
                name=f"Juror {juror_id}",
            ))

        # ── For remaining jurors (beyond cap), Foreperson summarises ─────────
        remaining = profiles[individual_count:]
        remaining_votes: dict[int, str] = {}
        if remaining:
            foreperson_llm = get_structured_llm(DeliberationOutput, temperature=0.2, model=AGENT_MODELS["Jury Foreperson"])
            try:
                remaining_delib = foreperson_llm.invoke([
                    SystemMessage(content=p.jury_foreperson_prompt(jx)),
                    HumanMessage(content=(
                        f"The first {individual_count} jurors have spoken. Now summarise the remaining {len(remaining)} "
                        f"jurors' positions based on the admitted evidence.\n\n"
                        f"Remaining juror profiles:\n{remaining}\n\n"
                        f"Admitted evidence:\n{admitted}\n\n"
                        f"Fact sheet:\n{fact_sheet}\n\n"
                        f"Prior statements from other jurors:\n{prior_statements}\n\n"
                        f"Apply standard: {jx['legal_standard']}. Return your answer as a JSON object."
                    ))
                ])
                for pos in remaining_delib.positions:
                    pos_dict = _pydantic_to_dict(pos)
                    profile_match = next((p2 for p2 in remaining if p2.get("juror_id") == pos_dict["juror_id"]), {})
                    juror_positions.append({**profile_match, **pos_dict})
                    remaining_votes[pos_dict["juror_id"]] = pos_dict.get("stance", "Undecided")
                    name = profile_match.get("name", f"Juror {pos_dict['juror_id']}")
                    transcript.append(AIMessage(
                        content=f"{pos_dict.get('quote', 'Deliberating.')} Vote: {pos_dict.get('stance', 'Undecided')}.",
                        name=f"Juror {pos_dict['juror_id']}",
                    ))
            except Exception as e:
                logger.error(f"[Remaining jurors summary error] {e}")
                for profile in remaining:
                    jid = profile.get("juror_id", 0)
                    juror_positions.append({**profile, "stance": "Undecided", "quote": "Still deliberating."})
                    remaining_votes[jid] = "Undecided"

        # ── Tally votes ───────────────────────────────────────────────────────
        all_votes = list(juror_votes.values()) + list(remaining_votes.values())
        guilty_count   = sum(1 for v in all_votes if v in ["Guilty", "Liable"])
        not_guilty_count = sum(1 for v in all_votes if v in ["Not Guilty", "Not Liable"])
        undecided_count = sum(1 for v in all_votes if v == "Undecided")

        # Determine verdict from tally
        total = len(all_votes) or n
        # Supermajority required (75% threshold)
        threshold = max(int(total * 0.75), 1)
        if guilty_count >= threshold:
            final_verdict = "Guilty" if jx.get("case_type") == "Criminal" else "Liable"
        elif not_guilty_count >= threshold:
            final_verdict = "Not Guilty" if jx.get("case_type") == "Criminal" else "Not Liable"
        else:
            final_verdict = "Hung"

        # After 3 rounds, accept simple majority if still hung
        reached_verdict = final_verdict != "Hung" and undecided_count == 0
        if rounds >= 3 and final_verdict == "Hung":
            if guilty_count > not_guilty_count and undecided_count == 0:
                final_verdict = "Guilty" if jx.get("case_type") == "Criminal" else "Liable"
                reached_verdict = True
            elif not_guilty_count > guilty_count and undecided_count == 0:
                final_verdict = "Not Guilty" if jx.get("case_type") == "Criminal" else "Not Liable"
                reached_verdict = True

        # ── Foreperson delivers verdict ────────────────────────────────────────
        vote_summary = (
            f"{guilty_count} for burden met, "
            f"{not_guilty_count} for burden not met, "
            f"{undecided_count} undecided."
        )
        if reached_verdict:
            verdict_msg = f"Round {rounds}: {vote_summary} The jury reaches a verdict: {final_verdict}."
        elif rounds >= 3:
            verdict_msg = f"Round {rounds} (final): {vote_summary} The jury remains deadlocked. Declaring mistrial due to hung jury."
            final_verdict = "Hung"
        else:
            verdict_msg = f"Round {rounds}: {vote_summary} The jury continues deliberation."

        transcript.append(AIMessage(
            content=verdict_msg,
            name="Foreperson",
        ))

        snapshot = {
            "type": "jury",
            "round": rounds,
            "total": total,
            "guilty_or_liable_count": guilty_count,
            "not_guilty_or_not_liable_count": not_guilty_count,
            "undecided_count": undecided_count,
            "verdict": final_verdict,
            "rationale": verdict_msg,
            "positions": juror_positions,
        }

        return {
            "deliberation_rounds": rounds,
            "jury_profiles": profiles,
            "deliberation_snapshot": snapshot,
            "main_verdict": final_verdict if reached_verdict else None,
            "transcript": transcript,
        }

    except Exception as e:
        logger.error(f"Jury Deliberation Error: {e}")
        fallback_msg = AIMessage(content=f"[Jury deliberation error: {e}]", name="System")
        return {
            "deliberation_rounds": rounds,
            "transcript": transcript + [fallback_msg],
        }


# ── Shadow Jury ───────────────────────────────────────────────────────────────

async def async_shadow_jury(jury_id: int, case_facts: str, admitted: list, legal_standard: str, model: str):
    """Async single shadow jury evaluation."""
    llm = get_structured_llm(JuryVerdict, temperature=0.8, model=model)
    try:
        res = await llm.ainvoke([
            SystemMessage(content=(
                f"You are an independent shadow juror. Apply the standard '{legal_standard}' "
                f"to the admitted evidence only. Provide a rationale and return your verdict as a json object."
            )),
            HumanMessage(content=(
                f"Admitted evidence:\n{admitted}\n\n"
                f"Case summary:\n{case_facts}\n\n"
                f"Return your verdict as a JSON object."
            ))
        ])
        return {"vote": res.verdict, "rationale": res.rationale, "id": jury_id}
    except Exception as e:
        logger.error(f"Shadow Jury {jury_id} Error: {e}")
        return {"vote": "Hung", "rationale": "I could not reach a decision.", "id": jury_id}


def shadow_jury_node(state: TrialState) -> dict:
    """Spawns N independent shadow juries to estimate verdict probability."""
    logger.info("--- SHADOW JURIES ---")
    jx = _get_jx(state)
    jury_count    = state.get("shadow_jury_count", 20)
    jury_model    = state.get("shadow_jury_model", AGENT_MODELS["Jury Foreperson"])
    case_facts    = state.get("fact_sheet", state.get("case_description", ""))
    admitted      = state.get("admitted_evidence", [])
    legal_standard = jx["legal_standard"]

    async def run_all():
        chunk_size = 5
        results = []
        for i in range(0, jury_count, chunk_size):
            chunk = range(i, min(i + chunk_size, jury_count))
            tasks = [async_shadow_jury(j, case_facts, admitted, legal_standard, jury_model) for j in chunk]
            results.extend(await asyncio.gather(*tasks))
            await asyncio.sleep(1)
        return results

    all_verdicts = asyncio.run(run_all())
    guilty_votes = sum(1 for v in all_verdicts if v["vote"] in ["Guilty", "Liable"])
    not_guilty_votes = sum(1 for v in all_verdicts if v["vote"] in ["Not Guilty", "Not Liable"])
    hung_votes = sum(1 for v in all_verdicts if v["vote"] == "Hung")
    win_prob     = guilty_votes / jury_count if jury_count > 0 else 0.0

    narrative = []
    # Show up to 10 for narrative (or all if fewer)
    show_count = min(10, len(all_verdicts))
    for v in all_verdicts[:show_count]:
        narrative.append({
            "name": f"Shadow Juror {v['id'] + 1}",
            "content": f"{v['rationale']} [Vote: {v['vote']}]"
        })

    return {"shadow_jury_results": {
        "win_probability": win_prob,
        "guilty_votes": guilty_votes,
        "not_guilty_votes": not_guilty_votes,
        "hung_votes": hung_votes,
        "total_juries": jury_count,
        "narrative": narrative
    }}


# ── Archivist ─────────────────────────────────────────────────────────────────

def archivist_node(state: TrialState) -> dict:
    """Produces the official court record in Markdown."""
    logger.info("--- ARCHIVIST ---")
    jx = _get_jx(state)
    transcript_text = "\n".join(
        [_format_transcript_msg(m) for m in state.get("transcript", [])]
    )
    try:
        archivist_llm = get_llm(temperature=0.1, model=AGENT_MODELS["Archivist"])
        doc = archivist_llm.invoke([
            SystemMessage(content=p.archivist_prompt(jx)),
            HumanMessage(content=(
                f"Produce the official court record.\n\n"
                f"Case Facts:\n{state.get('case_description', '')}\n\n"
                f"Fact Sheet:\n{state.get('fact_sheet', '')}\n\n"
                f"Admitted Evidence:\n{state.get('admitted_evidence', [])}\n\n"
                f"Excluded Evidence:\n{state.get('excluded_evidence', [])}\n\n"
                f"Full Transcript:\n{transcript_text}\n\n"
                f"Verdict: {state.get('main_verdict')}\n\n"
                f"Shadow Jury Results: {state.get('shadow_jury_results', {})}"
            ))
        ])
        try:
            with open("official_court_record.md", "w") as f:
                f.write(doc.content)
        except OSError as write_err:
            logger.error(f"Archivist write error: {write_err}")
        return {"transcript": [AIMessage(content="Official Trial Record archived.", name="Archivist")]}
    except Exception as e:
        logger.error(f"Archivist Error: {e}")
        return {"transcript": [
            AIMessage(content=f"[Archivist could not produce the record: {e}]", name="System"),
        ]}
