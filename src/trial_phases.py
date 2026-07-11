import re
import uuid
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

import src.prompts as p
from src.config import AGENT_MODELS, DEFAULT_COUNTRY
from src.llm import get_llm, get_structured_llm
from src.logger import get_logger
from src.schemas import (
    ClerkOutput,
    DiscoveryItems,
    JudgeRuling,
    MagistrateOutput,
    MotionFiling,
    MotionOpposition,
    MotionRulingResult,
    TrialLogOutput,
    _pydantic_to_dict,
)
from src.security import detect_prompt_injection
from src.state import TrialState

logger = get_logger(__name__)

# ── Ruling Preamble Stripper ──────────────────────────────────────────────────

_PREAMBLE_PATTERNS = [
    r"^(?:the\s+)?objection\s+is\s+sustained\s+in\s+part[\.\s:;,-]*",
    r"^(?:the\s+)?objection\s+is\s+(?:sustained|overruled)[\.\s:;,-]*",
    r"^(?:the\s+)?motion\s+is\s+(?:sustained\s+in\s+part|sustained|overruled|granted|denied)[\.\s:;,-]*",
    r"^(?:sustained\s+in\s+part|sustained|overruled)[\.\s:;,-]+",
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
        text = text[len(ruling_upper) :].lstrip(".:;,- ").strip()
    # Clean residual "in part" when the LLM repeats it after the preamble is stripped
    text = re.sub(r"^in\s+part[\.\s,:;]*", "", text, flags=re.IGNORECASE)
    text = text.strip()
    return text


# ── Fact Sufficiency Helpers ─────────────────────────────────────────────────

_MIN_FACT_WORDS = 8


def _has_actionable_case_facts(facts: str) -> bool:
    """Return True only when the record has enough detail for advocacy."""
    words = re.findall(r"[A-Za-z0-9]+", facts or "")
    return len(words) >= _MIN_FACT_WORDS


def _insufficient_record_opening(jx: dict) -> dict:
    address = jx["address"].split(";")[0]
    return {
        "transcript": [
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
        ]
    }


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
                content=(f"{address}, the defence objects to any attempt to infer evidence from an incomplete record."),
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
    case_type_raw = state.get("case_type", "Criminal")
    case_type = case_type_raw.title() if isinstance(case_type_raw, str) else "Criminal"
    country = state.get("country", DEFAULT_COUNTRY)
    return {
        "country": country,
        "system": state.get("jurisdiction_system", "Common Law"),
        "procedure": state.get("jurisdiction_procedure", "adversarial"),
        "case_type": case_type,
        "legal_standard": (
            state.get("criminal_standard", "Beyond reasonable doubt")
            if case_type == "Criminal"
            else state.get("civil_standard", "Balance of probabilities")
        ),
        "evidence_rules": state.get(
            "evidence_rules", "Evidence Act 2011; Administration of Criminal Justice Act 2015 (ACJA)"
        ),
        "jury_enabled": state.get("jury_enabled", False),
        "jury_profiles": state.get("jury_profiles") or [],
        "cross": state.get("cross_examination", True),
        "address": state.get("court_address", "My Lord / Your Lordship"),
    }


# ── Security Check ────────────────────────────────────────────────────────────


def security_check_node(state: TrialState) -> dict:
    """Scans case facts and any pre-trial answers for prompt injection."""
    logger.info("--- SECURITY CHECK ---")
    texts_to_scan = [state.get("case_description", ""), *[str(v) for v in state.get("human_answers", {}).values()]]
    for text in texts_to_scan:
        if detect_prompt_injection(text):
            err = "[CONTEMPT OF COURT] Malicious input detected. Trial aborted."
            logger.error(err, exc_info=True)
            return {"errors": [err]}
    return {"errors": []}


# ── Magistrate ────────────────────────────────────────────────────────────────


def _extract_evidence_fallback(text: str) -> list[str]:
    """Extract evidence items from case text when the LLM doesn't identify them."""
    evidence = []

    # Pattern 1: Explicit "Exhibit X: description" (handles leading dashes and newlines)
    for match in re.finditer(
        r"(?:^|\n)\s*[-•*]?\s*(?:Exhibit|EXHIBIT)\s+[A-Z]\s*[:—]\s*(.+?)(?=\n\s*[-•*]?\s*(?:Exhibit|EXHIBIT)|(?:\n\s*[-•*]?\s*(?:AT&T|Key|Witness|Judge|Prosecut|Defen))|\Z)",
        text,
        re.DOTALL,
    ):
        full = match.group(0).strip().lstrip("-•* \t").rstrip(".,;")
        desc = match.group(1).strip().rstrip(".,;")
        if desc and len(desc) > 5:
            evidence.append(full[:150])

    # Pattern 2: Generic evidence phrases as simple type labels
    evidence_types = [
        (r"(?:CCTV|security|camera)\s+(?:camera\s+)?footage|parking-lot\s+camera", "Security camera footage"),
        (r"cell\s+(?:tower|phone)\s+records?\s+", "Cell tower records"),
        (r"(?:phone|telephone)\s+records?\s+", "Phone records"),
        (r"(?:bank|financial)\s+(?:records?|statements?)\s+", "Bank/Financial records"),
        (r"medical\s+(?:examiner|report|records?)\s+(?:report|from|confirming)\s*", "Medical examiner report"),
        (r"(?:forensic|lab)\s+report\s+", "Forensic lab report"),
        (r"(?:email|e-mail)\s+(?:from|sent|dated|attaching)\s*", "Email correspondence"),
        (r"(?:NDA|contract|agreement)\s+(?:between|signed|dated)\s*", "Contract/Agreement"),
        (r"(?:fingerprint|DNA)\s+evidence\s*", "Forensic/DNA evidence"),
        (r"(?:autopsy|coroner)\s+report\s*", "Autopsy/Coroner report"),
        (r"(?:notaris|notariz)ed\s+(?:deed|document|act)\s+", "Notarised document"),
        (r"(?:owner|witness)\s+statement\s+", "Written statement"),
        (r"(?:schematics|blueprints|technical\s+(?:spec|drawing))", "Technical documents"),
        (r"(?:receipt|purchase\s+record)\s+", "Purchase receipt"),
        (r"(?:handwriting|ink)\s+analysis", "Handwriting analysis"),
        (r"(?:credit\s+card|payment)\s+(?:receipt|record|statement)", "Payment records"),
    ]
    for pattern, label in evidence_types:
        if re.search(pattern, text, re.IGNORECASE):
            if not any(label.lower() in e.lower() for e in evidence):
                evidence.append(label)

    # Deduplicate: remove shorter entries contained in longer ones
    unique = []
    for e in sorted(evidence, key=len, reverse=True):
        if not any(e.lower() != u.lower() and e.lower() in u.lower() for u in unique):
            unique.append(e)
    return unique


def _extract_witnesses_fallback(text: str) -> list[str]:
    """Regex-based extraction of named individuals when the LLM returns empty."""
    witnesses = set()

    patterns = [
        # Title-prefixed names: Dr. Marcus Chen, Detective Paula Reyes, Officer Daniels, Inspector Dubois
        r"(?:Dr\.|Detective|Officer|Inspector|Professor|Lt\.|Sgt\.|Capt\.|Mr\.|Mrs\.|Ms\.)\s+((?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+))",
        # "X testified as Y" or "X will testify"
        r"([A-Z][a-z]+\s+[A-Z][a-z]+)\s+(?:will |(?:is|was)\s+)\w+\s+testif",
        # "call[s] X." or "call[s] X, Y." or "calls Dr. X"
        r"calls?\s+(?:Dr\.\s+)?([A-Z][a-z]+\s+[A-Z][a-z]+)",
        # Standard capitalized name patterns near witness/defendant/victim keywords
        r"(?:witness|defendant|victim|guard|engineer|investigator|accountant|expert|brother|sister|mother|father|bartender|manager|director|employee)\s*,?\s*([A-Z][a-z]+\s+[A-Z][a-z]+)",
        # "X:" or "X —" introducing testimony or description
        r"([A-Z][a-z]+\s+[A-Z][a-z]+)\s*[:—]",
        # Explicitly listed as separate line with a dash prefix (like "- Dr. X:" or "- X:")
        r"-\s*(?:Dr\.|Detective|Officer|Inspector|Professor|Lt\.|Sgt\.|Capt\.|Mr\.|Mrs\.|Ms\.)\s+((?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+))",
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, text):
            name = match.group(1).strip()
            if len(name.split()) >= 2:
                witnesses.add(name)

    # Remove common false positives (months, legal terms)
    # Filter out common non-name words
    common_words = {
        "The",
        "This",
        "They",
        "That",
        "There",
        "Their",
        "These",
        "Those",
        "With",
        "From",
        "Were",
        "Have",
        "Been",
        "Would",
        "Could",
        "Should",
        "About",
        "After",
        "Before",
        "Under",
        "Because",
        "Without",
        "Within",
        "First",
        "Second",
        "Third",
        "Fourth",
        "Fifth",
        "Sixth",
        "No",
        "Not",
        "Any",
        "All",
        "Each",
        "Some",
        "More",
        "Only",
        "Code",
        "Act",
        "Law",
        "Rules",
        "Evidence",
        "Civil",
        "Common",
        "Court",
        "Trial",
        "Case",
        "State",
        "United",
        "Federal",
        "Grand",
        "Jury",
        "Bench",
        "Honor",
        "Motion",
        "Order",
        "Ruling",
        "Exhibit",
        "Objection",
        "Sustained",
        "Overruled",
        "Admitted",
        "North",
        "South",
        "East",
        "West",
        "Oakdale",
        "Saint",
        "Park",
        "Street",
        "Avenue",
        "Road",
        "Drive",
        "Lane",
        "Model",
        "Tesla",
        "Porsche",
        "Toyota",
        "Blue",
        "Once",
        "Then",
        "When",
        "What",
        "Which",
        "While",
        "Where",
        "Non",
        "Coupable",
        "Coupable",
        "Liable",
    }

    # Remove entries where the first word is a common word
    witnesses = {w for w in witnesses if w.split()[0] not in common_words}

    false_positives = {
        "March 14th",
        "September 12th",
        "Your Honor",
        "Monsieur Président",
        "United States",
        "Los Angeles",
        "New York",
        "San Francisco",
        "Santa Monica",
        "Northside Storage",
        "Not Guilty",
        "Not Liable",
        "Grand Theft",
        "Federal Rules",
        "Common Law",
        "Civil Law",
        "Code Civil",
        "Banque Populaire",
        "PowerCell Inc",
        "Nexus Corp",
        "Aether Labs",
        "Fire Investigator",
        "Fire Marshal",
        "Security Guard",
        "Bartender",
        "Materials Engineer",
        "Electrical Engineer",
        "Arson Investigat",
        "Oakdale Drive",
        "California State",
        "State Fire",
        "Double Homicide",
        "Chief Fire",
        "National Association",
        "Combustion Chemistry",
        "Arson Investigation",
        "Detective Paula",
        "Information Security Officer",
        "Security Officer",
        "Inspector Grace",
    }
    witnesses = witnesses - false_positives

    # Remove names that are subsets of longer names (e.g., "Paula" inside "Paula Reyes")
    short_names = set()
    for w in witnesses:
        parts_w = set(w.split())
        for other in witnesses:
            if w != other and parts_w.issubset(set(other.split())):
                short_names.add(w)
                break
    witnesses = witnesses - short_names

    return sorted(witnesses)


def magistrate_node(state: TrialState) -> dict:
    """Analyses case facts, drafts clarifying questions, extracts witness names, identifies missing items."""
    logger.info("--- MAGISTRATE NODE ---")
    jx = _get_jx(state)
    case_description = state.get("case_description", "")

    try:
        llm = get_structured_llm(MagistrateOutput, temperature=0.1, model=AGENT_MODELS["Magistrate"])
        result = llm.invoke(
            [SystemMessage(content=p.magistrate_prompt(jx)), HumanMessage(content=f"Case facts:\n{case_description}")]
        )
        questions = [{"question": q} for q in result.clarifying_questions]
        witnesses = list(result.witnesses) if result.witnesses else []
        missing_evidence = result.missing_evidence if hasattr(result, "missing_evidence") else []
        missing_witnesses = result.missing_witnesses if hasattr(result, "missing_witnesses") else []

        # Fallback: if LLM returned empty witnesses but the text clearly names people, extract them
        if not witnesses and case_description:
            extracted = _extract_witnesses_fallback(case_description)
            if extracted:
                logger.info(
                    f"Magistrate LLM returned empty witnesses — regex fallback found {len(extracted)}: {extracted}"
                )
                witnesses = extracted

        # Extract identified evidence from case text
        identified_evidence = _extract_evidence_fallback(case_description)

        return {
            "clarifying_questions": questions,
            "witness_queue": witnesses,
            "missing_evidence": missing_evidence,
            "missing_witnesses": missing_witnesses,
            "identified_evidence": identified_evidence,
        }
    except Exception as e:
        logger.error(f"Magistrate Error: {e}", exc_info=True)
        # Try regex fallback for everything
        case_description = state.get("case_description", "")
        return {
            "clarifying_questions": [{"question": "Can you provide more details about the key events?"}],
            "witness_queue": _extract_witnesses_fallback(case_description),
            "missing_evidence": [],
            "missing_witnesses": [],
            "identified_evidence": _extract_evidence_fallback(case_description),
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
    name = getattr(m, "name", None) or "System"
    content = getattr(m, "content", "")
    return f"[{name}]: {content}"


# ── Clerk Compression ─────────────────────────────────────────────────────────


def _clerk_compression(state: TrialState) -> dict:
    """Compresses transcript into fact sheet and evidence logs between phases."""
    jx = _get_jx(state)
    transcript_str = "\n".join([_format_transcript_msg(m) for m in state.get("transcript", [])[-12:]])
    if not transcript_str:
        return {}
    try:
        llm = get_structured_llm(ClerkOutput, temperature=0.1, model=AGENT_MODELS["Clerk"])
        res = llm.invoke(
            [
                SystemMessage(content=p.clerk_prompt(jx)),
                HumanMessage(
                    content=(
                        f"Current Fact Sheet:\n{state.get('fact_sheet', '')}\n\nRecent Transcript:\n{transcript_str}"
                    )
                ),
            ]
        )
        return {
            "fact_sheet": res.fact_sheet,
            "admitted_evidence": res.admitted_evidence,
            "excluded_evidence": res.excluded_evidence,
        }
    except Exception as e:
        logger.error(f"Clerk compression error: {e}", exc_info=True)
        return {}


# ── Opening Statements ────────────────────────────────────────────────────────


def opening_statements_node(state: TrialState) -> dict:
    """Prosecution and Defence deliver opening statements."""
    logger.info("--- OPENING STATEMENTS ---")
    jx = _get_jx(state)
    facts = state.get("case_description", "")
    if not _has_actionable_case_facts(facts):
        return _insufficient_record_opening(jx)

    try:
        # Prosecution opens first
        pros_llm = get_llm(temperature=0.7, model=AGENT_MODELS["Prosecutor"])
        pros_msg = pros_llm.invoke(
            [
                SystemMessage(content=p.prosecutor_prompt(jx)),
                HumanMessage(
                    content=(
                        "Deliver your opening statement in 80 words or fewer.\n\n"
                        "CRITICAL — This is an OPENING STATEMENT, NOT a closing argument. "
                        "You are previewing what the evidence WILL show, not arguing what has been proven. "
                        "Use phrases like 'the evidence will show that...' or 'you will hear testimony that...'\n"
                        "Do NOT state alleged facts as if they have already been established. "
                        "The defence has not yet cross-examined. No witness has testified yet.\n\n"
                        "Ground every claim in the case facts provided. "
                        "Do not use Markdown, bullet points, or invented details.\n\n"
                        f"Case facts:\n{facts}"
                    )
                ),
            ]
        )

        # Defence responds, having heard the prosecution's opening
        def_llm = get_llm(temperature=0.7, model=AGENT_MODELS["Defense Counsel"])
        def_msg = def_llm.invoke(
            [
                SystemMessage(content=p.defense_prompt(jx)),
                HumanMessage(
                    content=(
                        f'The prosecution just said:\n"{pros_msg.content}"\n\n'
                        "Respond in 80 words or fewer.\n\n"
                        "CRITICAL — This is an OPENING STATEMENT, NOT a closing argument. "
                        "You are previewing what the evidence WILL show, not arguing what has been proven. "
                        "Use phrases like 'the evidence will show that...'\n"
                        "Do NOT state facts as if they have already been established. "
                        "No witness has testified yet.\n\n"
                        "Ground every claim in the case facts provided. "
                        "Do not use Markdown, bullet points, or invented details.\n\n"
                        f"Case facts:\n{facts}"
                    )
                ),
            ]
        )

        return {
            "transcript": [
                AIMessage(content=pros_msg.content, name="Prosecutor"),
                AIMessage(content=def_msg.content, name="Defense Counsel"),
            ]
        }
    except Exception as e:
        logger.error(f"Opening Statements Error: {e}", exc_info=True)
        return {
            "transcript": [
                AIMessage(content=f"[Opening statements could not be generated: {e}]", name="System"),
            ]
        }


# ── Discovery ──────────────────────────────────────────────────────────────────


def discovery_node(state: TrialState) -> dict:
    """Each side discloses its list of evidence items before trial."""
    logger.info("--- DISCOVERY ---")
    jx = _get_jx(state)
    facts = state.get("case_description", "")
    transcript = []

    if not _has_actionable_case_facts(facts):
        transcript.append(
            AIMessage(
                content="The record is insufficient for meaningful discovery. Both sides reserve the right to supplement.",
                name="Clerk",
            )
        )
        return {"transcript": transcript}

    try:
        pros_llm = get_structured_llm(DiscoveryItems, temperature=0.3, model=AGENT_MODELS["Prosecutor"])
        def_llm = get_structured_llm(DiscoveryItems, temperature=0.3, model=AGENT_MODELS["Defense Counsel"])

        pros_disc = pros_llm.invoke(
            [SystemMessage(content=p.prosecutor_discovery_prompt(jx)), HumanMessage(content=f"Case facts:\n{facts}")]
        )
        transcript.append(
            AIMessage(
                content=f"Prosecution disclosure: {'; '.join(pros_disc.items[:4])}",
                name="Prosecutor",
            )
        )

        def_disc = def_llm.invoke(
            [SystemMessage(content=p.defense_discovery_prompt(jx)), HumanMessage(content=f"Case facts:\n{facts}")]
        )
        transcript.append(
            AIMessage(
                content=f"Defence disclosure: {'; '.join(def_disc.items[:3])}",
                name="Defense Counsel",
            )
        )

        transcript.append(
            AIMessage(
                content="Discovery complete. The Court acknowledges the disclosed evidence lists.",
                name="Judge",
            )
        )

        return {
            "transcript": transcript,
            "disclosed_prosecution": list(pros_disc.items),
            "disclosed_defense": list(def_disc.items),
        }
    except Exception as e:
        logger.error(f"Discovery Error: {e}", exc_info=True)
        return {
            "transcript": [
                AIMessage(content=f"[Discovery could not be completed: {e}]", name="System"),
            ]
        }


# ── Motion Practice ────────────────────────────────────────────────────────────


def motion_practice_node(state: TrialState) -> dict:
    """Pre-trial motion practice. Each side may file a motion, opponent responds, judge rules."""
    logger.info("--- MOTION PRACTICE ---")
    jx = _get_jx(state)
    facts = state.get("case_description", "")
    transcript = []
    motion_log = list(state.get("motion_rulings", []))

    if not _has_actionable_case_facts(facts):
        transcript.append(
            AIMessage(
                content="The record is insufficient for substantive motions. The court will proceed to trial.",
                name="Judge",
            )
        )
        return {"transcript": transcript}

    try:
        pros_llm = get_structured_llm(MotionFiling, temperature=0.3, model=AGENT_MODELS["Prosecutor"])
        def_llm = get_structured_llm(MotionFiling, temperature=0.3, model=AGENT_MODELS["Defense Counsel"])
        def_opp_llm = get_structured_llm(MotionOpposition, temperature=0.3, model=AGENT_MODELS["Defense Counsel"])
        pros_opp_llm = get_structured_llm(MotionOpposition, temperature=0.3, model=AGENT_MODELS["Prosecutor"])
        judge_llm = get_structured_llm(MotionRulingResult, temperature=0.1, model=AGENT_MODELS["Judge"])

        pros_movant = "Prosecution" if jx["case_type"] == "Criminal" else "Plaintiff"
        def_movant = "Defence"

        # Round 1: Prosecution motion
        pros_motion = pros_llm.invoke(
            [SystemMessage(content=p.motion_prompt(jx, pros_movant)), HumanMessage(content=f"Case facts:\n{facts}")]
        )
        transcript.append(
            AIMessage(
                content=f"MOTION: {pros_motion.motion_type}. {pros_motion.relief_sought}. {pros_motion.argument}",
                name="Prosecutor",
            )
        )

        def_opp = def_opp_llm.invoke(
            [
                SystemMessage(content=p.opposition_prompt(jx, def_movant)),
                HumanMessage(
                    content=(
                        f"Motion: {pros_motion.motion_type}\n"
                        f"Relief sought: {pros_motion.relief_sought}\n"
                        f"Argument: {pros_motion.argument}\n"
                        f"Case facts:\n{facts}"
                    )
                ),
            ]
        )
        transcript.append(
            AIMessage(
                content=f"OPPOSITION: {def_opp.argument} [Rule: {def_opp.rule_cited}]",
                name="Defense Counsel",
            )
        )

        ruling1 = judge_llm.invoke(
            [
                SystemMessage(content=p.judge_motion_prompt(jx)),
                HumanMessage(
                    content=(
                        f"Motion: {pros_motion.motion_type}\n"
                        f"Proponent argues: {pros_motion.argument}\n"
                        f"Opponent argues: {def_opp.argument}\n\n"
                        f"Rule on this motion. Return JSON with 'ruling' (GRANTED or DENIED) and 'rationale'."
                    )
                ),
            ]
        )
        motion_log.append(
            {
                "motion_type": pros_motion.motion_type,
                "movant": pros_movant,
                "arguing": pros_motion.argument,
                "opposition": def_opp.argument,
                "ruling": ruling1.ruling,
                "rationale": ruling1.rationale,
            }
        )
        transcript.append(
            AIMessage(
                content=f"Motion {ruling1.ruling}. {ruling1.rationale}",
                name="Judge",
            )
        )

        # Round 2: Defence motion
        def_motion = def_llm.invoke(
            [SystemMessage(content=p.motion_prompt(jx, def_movant)), HumanMessage(content=f"Case facts:\n{facts}")]
        )
        transcript.append(
            AIMessage(
                content=f"MOTION: {def_motion.motion_type}. {def_motion.relief_sought}. {def_motion.argument}",
                name="Defense Counsel",
            )
        )

        pros_opp = pros_opp_llm.invoke(
            [
                SystemMessage(content=p.opposition_prompt(jx, pros_movant)),
                HumanMessage(
                    content=(
                        f"Motion: {def_motion.motion_type}\n"
                        f"Relief sought: {def_motion.relief_sought}\n"
                        f"Argument: {def_motion.argument}\n"
                        f"Case facts:\n{facts}"
                    )
                ),
            ]
        )
        transcript.append(
            AIMessage(
                content=f"OPPOSITION: {pros_opp.argument} [Rule: {pros_opp.rule_cited}]",
                name="Prosecutor",
            )
        )

        ruling2 = judge_llm.invoke(
            [
                SystemMessage(content=p.judge_motion_prompt(jx)),
                HumanMessage(
                    content=(
                        f"Motion: {def_motion.motion_type}\n"
                        f"Proponent argues: {def_motion.argument}\n"
                        f"Opponent argues: {pros_opp.argument}\n\n"
                        f"Rule on this motion. Return JSON with 'ruling' (GRANTED or DENIED) and 'rationale'."
                    )
                ),
            ]
        )
        motion_log.append(
            {
                "motion_type": def_motion.motion_type,
                "movant": def_movant,
                "arguing": def_motion.argument,
                "opposition": pros_opp.argument,
                "ruling": ruling2.ruling,
                "rationale": ruling2.rationale,
            }
        )
        transcript.append(
            AIMessage(
                content=f"Motion {ruling2.ruling}. {ruling2.rationale}",
                name="Judge",
            )
        )

        transcript.append(
            AIMessage(
                content="Motion practice concluded. The court will now proceed to opening statements.",
                name="Judge",
            )
        )

        return {"transcript": transcript, "motion_rulings": motion_log}
    except Exception as e:
        logger.error(f"Motion Practice Error: {e}", exc_info=True)
        return {
            "transcript": [
                AIMessage(content=f"[Motion practice could not be completed: {e}]", name="System"),
            ]
        }


# ── Closing Arguments ─────────────────────────────────────────────────────────


def closing_arguments_node(state: TrialState) -> dict:
    """Prosecution and Defence deliver closing arguments based on admitted facts."""
    logger.info("--- CLOSING ARGUMENTS ---")
    jx = _get_jx(state)
    fact_sheet = state.get("fact_sheet", state.get("case_description", ""))
    admitted = state.get("admitted_evidence", [])
    excluded = state.get("excluded_evidence", [])
    transcript = []

    try:
        # No-Case Submission
        def_llm = get_llm(temperature=0.7, model=AGENT_MODELS["Defense Counsel"])
        no_case_motion = def_llm.invoke(
            [
                SystemMessage(content=p.defense_prompt(jx)),
                HumanMessage(
                    content=(
                        f"The prosecution has rested its case.\n"
                        f"Admitted evidence:\n{admitted}\n"
                        f"Fact sheet:\n{fact_sheet}\n\n"
                        f"Evaluate if a prima facie case exists. If not, briefly move for acquittal (No-Case Submission). "
                        f"If there is a case to answer, say 'The defence will proceed with closing arguments.'"
                    )
                ),
            ]
        )

        if "acquittal" in no_case_motion.content.lower() or "no case" in no_case_motion.content.lower():
            transcript.append(AIMessage(content=no_case_motion.content, name="Defense Counsel"))
            judge_llm = get_structured_llm(JudgeRuling, temperature=0.1, model=AGENT_MODELS["Judge"])
            ruling = judge_llm.invoke(
                [
                    SystemMessage(content=p.judge_prompt(jx)),
                    HumanMessage(
                        content=(
                            f"The defence has made a No-Case Submission:\n{no_case_motion.content}\n\n"
                            f"Based on the admitted evidence: {admitted}, rule on the motion.\n"
                            f"Return 'SUSTAINED' to acquit, or 'OVERRULED' to proceed. Return your answer as a JSON object."
                        )
                    ),
                ]
            )
            transcript.append(
                AIMessage(
                    content=f"Ruling on No-Case Submission: {ruling.ruling}. {_strip_ruling_preamble(ruling.rationale, ruling.ruling)}",
                    name="Judge",
                )
            )
            if ruling.ruling == "SUSTAINED":
                case_type = jx.get("case_type", "Criminal")
                early_verdict = "Not Guilty" if case_type == "Criminal" else "Not Liable"
                dismiss_msg = (
                    "The case is dismissed. The defendant is acquitted."
                    if case_type == "Criminal"
                    else "The case is dismissed. The defendant is found not liable."
                )
                transcript.append(AIMessage(content=dismiss_msg, name="Judge"))
                return {"transcript": transcript, "main_verdict": early_verdict}

        pros_llm = get_llm(temperature=0.7, model=AGENT_MODELS["Prosecutor"])
        pros_msg = pros_llm.invoke(
            [
                SystemMessage(content=p.prosecutor_prompt(jx)),
                HumanMessage(
                    content=(
                        f"Closing argument in 80 words or fewer. Be direct and persuasive.\n\n"
                        f"Admitted evidence:\n{admitted}\n\n"
                        f"Do NOT reference excluded evidence: {excluded}\n\n"
                        f"Standard: {jx['legal_standard']}"
                    )
                ),
            ]
        )
        transcript.append(AIMessage(content=pros_msg.content, name="Prosecutor"))

        def_msg = def_llm.invoke(
            [
                SystemMessage(content=p.defense_prompt(jx)),
                HumanMessage(
                    content=(
                        f'Prosecution argued:\n"{pros_msg.content}"\n\n'
                        f"Respond in 80 words or fewer. Be direct.\n\n"
                        f"Admitted evidence:\n{admitted}\n\n"
                        f"Do NOT reference excluded evidence: {excluded}\n\n"
                        f"Standard: {jx['legal_standard']}"
                    )
                ),
            ]
        )
        transcript.append(AIMessage(content=def_msg.content, name="Defense Counsel"))

        return {"transcript": transcript}
    except Exception as e:
        logger.error(f"Closing Arguments Error: {e}", exc_info=True)
        return {
            "transcript": [
                AIMessage(content=f"[Closing arguments could not be generated: {e}]", name="System"),
            ]
        }


# ── Court Reporter ─────────────────────────────────────────────────────────────


def reporter_node(state: TrialState) -> dict:
    """Produces a structured trial log from the complete transcript."""
    logger.info("--- COURT REPORTER ---")
    jx = _get_jx(state)
    transcript_text = "\n".join([_format_transcript_msg(m) for m in state.get("transcript", [])])
    if not transcript_text.strip():
        return {"trial_log": {}}

    try:
        reporter_llm = get_structured_llm(TrialLogOutput, temperature=0.1, model=AGENT_MODELS["Clerk"])
        result = reporter_llm.invoke(
            [
                SystemMessage(content=p.reporter_prompt(jx)),
                HumanMessage(
                    content=(
                        f"Case Facts:\n{state.get('case_description', '')}\n\n"
                        f"Admitted Evidence:\n{state.get('admitted_evidence', [])}\n"
                        f"Excluded Evidence:\n{state.get('excluded_evidence', [])}\n"
                        f"Witnesses Called:\n{state.get('witness_queue', [])}\n"
                        f"Expert Witnesses:\n{state.get('expert_witnesses', [])}\n"
                        f"Verdict:\n{state.get('main_verdict', 'Not yet reached')}\n\n"
                        f"Full Transcript:\n{transcript_text[:8000]}"
                    )
                ),
            ]
        )
        trial_log = _pydantic_to_dict(result)
        return {
            "trial_log": trial_log,
            "transcript": [
                AIMessage(content="Trial log compiled by the Court Reporter.", name="Court Reporter"),
            ],
        }
    except Exception as e:
        logger.error(f"Reporter Error: {e}", exc_info=True)
        return {
            "trial_log": {},
            "transcript": [
                AIMessage(content=f"[Reporter could not compile the log: {e}]", name="System"),
            ],
        }


# ── Archivist ─────────────────────────────────────────────────────────────────


def archivist_node(state: TrialState) -> dict:
    """Produces the official court record in Markdown."""
    logger.info("--- ARCHIVIST ---")
    jx = _get_jx(state)
    transcript_text = "\n".join([_format_transcript_msg(m) for m in state.get("transcript", [])])
    try:
        archivist_llm = get_llm(temperature=0.1, model=AGENT_MODELS["Archivist"])
        doc = archivist_llm.invoke(
            [
                SystemMessage(content=p.archivist_prompt(jx)),
                HumanMessage(
                    content=(
                        f"Produce the official court record.\n\n"
                        f"Case Facts:\n{state.get('case_description', '')}\n\n"
                        f"Fact Sheet:\n{state.get('fact_sheet', '')}\n\n"
                        f"Admitted Evidence:\n{state.get('admitted_evidence', [])}\n\n"
                        f"Excluded Evidence:\n{state.get('excluded_evidence', [])}\n\n"
                        f"Full Transcript:\n{transcript_text}\n\n"
                        f"Verdict: {state.get('main_verdict')}\n\n"
                        f"Shadow Jury Results: {state.get('shadow_jury_results', {})}"
                    )
                ),
            ]
        )
        try:
            output_dir = Path(__file__).parent.parent / "output"
            output_dir.mkdir(exist_ok=True)
            record_path = output_dir / f"official_court_record_{uuid.uuid4().hex[:8]}.md"
            with open(record_path, "w") as f:
                f.write(doc.content)
        except OSError as write_err:
            logger.error(f"Archivist write error: {write_err}", exc_info=True)
        return {"transcript": [AIMessage(content="Official Trial Record archived.", name="Archivist")]}
    except Exception as e:
        logger.error(f"Archivist Error: {e}", exc_info=True)
        return {
            "transcript": [
                AIMessage(content=f"[Archivist could not produce the record: {e}]", name="System"),
            ]
        }
