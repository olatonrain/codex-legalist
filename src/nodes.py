from src.state import TrialState
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from src.security import detect_prompt_injection
from src.llm import get_llm, get_structured_llm
from src.config import AGENT_MODELS, DEFAULT_COUNTRY
from src.logger import get_logger
import src.prompts as p
from pydantic import BaseModel, Field
import re
import random
import uuid
import json
import threading
from pathlib import Path

logger = get_logger(__name__)

_no_objection_lock = threading.Lock()
_no_objection_counter: dict[str, int] = {}

# ── Pydantic Output Schemas ───────────────────────────────────────────────────

class MagistrateOutput(BaseModel):
    clarifying_questions: list[str] = Field(default_factory=list, description="Between 0 and 5 critical clarifying questions. Return an EMPTY list if the case facts are complete enough. Never ask about information already present in the facts.")
    witnesses: list[str] = Field(default_factory=list, description="Named individuals in the case facts who should be called as witnesses. Empty list if none are named. Do NOT invent names. List every named person with a specific role.")
    missing_evidence: list[str] = Field(default_factory=list, description="Evidence types that are NOT MENTIONED ANYWHERE in the case facts. If the facts describe or reference an evidence item, do NOT list it. Empty list if evidence seems sufficient (preferred).")
    missing_witnesses: list[str] = Field(default_factory=list, description="Witness types that are NOT MENTIONED ANYWHERE in the case facts. If the facts name an individual or describe a role, do NOT list it. Empty list if witnesses seem sufficient (preferred).")

class ClerkOutput(BaseModel):
    fact_sheet: str = Field(description="Compressed summary of established facts.")
    admitted_evidence: list[str] = Field(description="Formally admitted evidence items.")
    excluded_evidence: list[str] = Field(description="Excluded evidence items (inadmissible).")

class JudgeRuling(BaseModel):
    ruling: str = Field(description="Must be exactly 'SUSTAINED' or 'OVERRULED' or 'SUSTAINED IN PART'.")
    rationale: str = Field(default="", description="Legal basis for the ruling, citing the specific rule of evidence.")
    objection_type: str = Field(default="", description="The type of objection raised (e.g. hearsay, relevance, speculation, leading, foundation, etc.).")
    limiting_instruction: str = Field(default="", description="If the ruling is partial (SUSTAINED IN PART), provide a limiting instruction specifying what part is admissible and for what limited purpose. Empty string if not needed.")

class ObjectionOutput(BaseModel):
    objection_type: str = Field(description="The specific type of objection: hearsay, relevance, speculation, leading, compound, foundation, narrative, privilege, character, prejudice, best_evidence, authentication, or cumulative.")
    rule_cited: str = Field(description="The specific rule number or section from the governing evidence rules.")
    rationale: str = Field(description="Brief explanation of why the evidence should be excluded under this rule.")

class ExaminationObjection(BaseModel):
    should_object: bool = Field(default=False, description="Whether to raise an objection to this question during examination")
    objection_type: str = Field(default="", description="Type of objection: leading, hearsay, speculation, compound, relevance, foundation, argumentative, asked_and_answered, narrative, badgering, or none")
    rule_cited: str = Field(default="", description="The specific evidence rule being violated — only required if should_object is true")
    rationale: str = Field(default="", description="Brief legal basis for the objection — only required if should_object is true")

class EvidenceObjectionDecision(BaseModel):
    should_object: bool = Field(default=False, description="True only if the evidence has a genuine, clear admissibility defect. False if the evidence appears admissible — do NOT object just because it is unfavorable.")
    objection_type: str = Field(default="", description="The specific type of objection if should_object is True: hearsay, relevance, speculation, foundation, privilege, character, prejudice, best_evidence, authentication, or cumulative.")
    rule_cited: str = Field(default="", description="The specific rule from the governing evidence rules — required only if should_object is True.")
    rationale: str = Field(default="", description="Brief explanation of the admissibility defect — required only if should_object is True.")
    foundation_missing: str = Field(default="", description="If foundation is the objection, specify exactly what foundation step is missing (e.g. 'no chain of custody', 'witness cannot identify the document', 'no business records certification').")

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

class SentencingDecision(BaseModel):
    sentence: str = Field(description="The formal pronouncement of sentence by the judge.")
    rationale: str = Field(description="Legal basis for the sentence, citing aggravating and mitigating factors considered.")
    term: str = Field(default="", description="Specific concrete term e.g. '5 years imprisonment', '$50,000 in damages', '3 years probation'.")

class DiscoveryItems(BaseModel):
    items: list[str] = Field(description="List of disclosed evidence items, each described in one sentence.")

class MotionFiling(BaseModel):
    motion_type: str = Field(description="Type of motion: Motion to Suppress, Motion in Limine, or Motion to Dismiss.")
    relief_sought: str = Field(description="What relief is being requested.")
    legal_basis: str = Field(description="Legal rule or authority supporting the motion.")
    argument: str = Field(description="Factual justification for the motion.")

class MotionOpposition(BaseModel):
    argument: str = Field(description="Argument opposing the motion.")
    rule_cited: str = Field(description="Rule or authority supporting the opposition.")

class MotionRulingResult(BaseModel):
    ruling: str = Field(description="Must be exactly 'GRANTED' or 'DENIED'.")
    rationale: str = Field(description="Legal basis for the ruling.")

class TrialLogOutput(BaseModel):
    case_info: str = Field(description="Brief case identification.")
    procedural_timeline: list[str] = Field(description="Chronological list of phases completed.")
    witnesses: list[str] = Field(description="Witnesses called and testimony summaries.")
    evidence_log: str = Field(description="Admitted vs excluded evidence counts.")
    key_rulings: list[str] = Field(description="Most important judicial rulings, 3-5 max.")
    verdict_summary: str = Field(description="Final verdict and basis.")


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


# ── Model Pool for Jurors ─────────────────────────────────────────────────────

_JUROR_MODEL_POOL = [
    AGENT_MODELS["Magistrate"],       # qwen-max
    AGENT_MODELS["Prosecutor"],       # qwen-plus-latest
    AGENT_MODELS["Jury Foreperson"],  # qwen-plus-latest
    AGENT_MODELS["Defense Counsel"],  # qwen-plus-latest
]


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
    case_type_raw = state.get("case_type", "Criminal")
    case_type = case_type_raw.title() if isinstance(case_type_raw, str) else "Criminal"
    country   = state.get("country", DEFAULT_COUNTRY)
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
        "evidence_rules": state.get("evidence_rules", "Evidence Act 2011; Administration of Criminal Justice Act 2015 (ACJA)"),
        "jury_enabled":  state.get("jury_enabled", False),
        "jury_profiles": state.get("jury_profiles") or [],
        "cross":         state.get("cross_examination", True),
        "address":       state.get("court_address", "My Lord / Your Lordship"),
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
    try:
        llm = get_structured_llm(JuryPanelOutput, temperature=0.4, model=AGENT_MODELS["Jury Foreperson"])
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
        # Assign random model to each juror for diversity
        for profile in profiles:
            profile["model"] = random.choice(_JUROR_MODEL_POOL)
        return profiles
    except Exception as e:
        logger.error(f"Jury Profile Generation Error: {e}", exc_info=True)
        fallback_profiles = [
            {
                "juror_id": juror_id,
                "name": f"Juror {juror_id}",
                "occupation": "Citizen juror",
                "persona": "Evidence-focused juror",
                "bias": "Reviews only admitted evidence and the legal standard",
            }
            for juror_id in range(1, n + 1)
        ]
        for profile in fallback_profiles:
            profile["model"] = random.choice(_JUROR_MODEL_POOL)
        return fallback_profiles


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
            logger.error(err, exc_info=True)
            return {"errors": [err]}
    return {"errors": []}


# ── Magistrate ────────────────────────────────────────────────────────────────

def _extract_evidence_fallback(text: str) -> list[str]:
    """Extract evidence items from case text when the LLM doesn't identify them."""
    evidence = []

    # Pattern 1: Explicit "Exhibit X: description" (handles leading dashes and newlines)
    for match in re.finditer(
        r'(?:^|\n)\s*[-•*]?\s*(?:Exhibit|EXHIBIT)\s+[A-Z]\s*[:—]\s*(.+?)(?=\n\s*[-•*]?\s*(?:Exhibit|EXHIBIT)|(?:\n\s*[-•*]?\s*(?:AT&T|Key|Witness|Judge|Prosecut|Defen))|\Z)',
        text, re.DOTALL
    ):
        full = match.group(0).strip().lstrip("-•* \t").rstrip(".,;")
        desc = match.group(1).strip().rstrip(".,;")
        if desc and len(desc) > 5:
            evidence.append(full[:150])

    # Pattern 2: Generic evidence phrases as simple type labels
    evidence_types = [
        (r'(?:CCTV|security|camera)\s+(?:camera\s+)?footage|parking-lot\s+camera', "Security camera footage"),
        (r'cell\s+(?:tower|phone)\s+records?\s+', "Cell tower records"),
        (r'(?:phone|telephone)\s+records?\s+', "Phone records"),
        (r'(?:bank|financial)\s+(?:records?|statements?)\s+', "Bank/Financial records"),
        (r'medical\s+(?:examiner|report|records?)\s+(?:report|from|confirming)\s*', "Medical examiner report"),
        (r'(?:forensic|lab)\s+report\s+', "Forensic lab report"),
        (r'(?:email|e-mail)\s+(?:from|sent|dated|attaching)\s*', "Email correspondence"),
        (r'(?:NDA|contract|agreement)\s+(?:between|signed|dated)\s*', "Contract/Agreement"),
        (r'(?:fingerprint|DNA)\s+evidence\s*', "Forensic/DNA evidence"),
        (r'(?:autopsy|coroner)\s+report\s*', "Autopsy/Coroner report"),
        (r'(?:notaris|notariz)ed\s+(?:deed|document|act)\s+', "Notarised document"),
        (r'(?:owner|witness)\s+statement\s+', "Written statement"),
        (r'(?:schematics|blueprints|technical\s+(?:spec|drawing))', "Technical documents"),
        (r'(?:receipt|purchase\s+record)\s+', "Purchase receipt"),
        (r'(?:handwriting|ink)\s+analysis', "Handwriting analysis"),
        (r'(?:credit\s+card|payment)\s+(?:receipt|record|statement)', "Payment records"),
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
        r'(?:Dr\.|Detective|Officer|Inspector|Professor|Lt\.|Sgt\.|Capt\.|Mr\.|Mrs\.|Ms\.)\s+((?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+))',
        # "X testified as Y" or "X will testify"
        r'([A-Z][a-z]+\s+[A-Z][a-z]+)\s+(?:will |(?:is|was)\s+)\w+\s+testif',
        # "call[s] X." or "call[s] X, Y." or "calls Dr. X"
        r'calls?\s+(?:Dr\.\s+)?([A-Z][a-z]+\s+[A-Z][a-z]+)',
        # Standard capitalized name patterns near witness/defendant/victim keywords
        r'(?:witness|defendant|victim|guard|engineer|investigator|accountant|expert|brother|sister|mother|father|bartender|manager|director|employee)\s*,?\s*([A-Z][a-z]+\s+[A-Z][a-z]+)',
        # "X:" or "X —" introducing testimony or description
        r'([A-Z][a-z]+\s+[A-Z][a-z]+)\s*[:—]',
        # Explicitly listed as separate line with a dash prefix (like "- Dr. X:" or "- X:")
        r'-\s*(?:Dr\.|Detective|Officer|Inspector|Professor|Lt\.|Sgt\.|Capt\.|Mr\.|Mrs\.|Ms\.)\s+((?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+))',
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, text):
            name = match.group(1).strip()
            if len(name.split()) >= 2:
                witnesses.add(name)

    # Remove common false positives (months, legal terms)
    # Filter out common non-name words
    common_words = {
        "The", "This", "They", "That", "There", "Their", "These", "Those",
        "With", "From", "Were", "Have", "Been", "Would", "Could", "Should",
        "About", "After", "Before", "Under", "Because", "Without", "Within",
        "First", "Second", "Third", "Fourth", "Fifth", "Sixth",
        "No", "Not", "Any", "All", "Each", "Some", "More", "Only",
        "Code", "Act", "Law", "Rules", "Evidence", "Civil", "Common",
        "Court", "Trial", "Case", "State", "United", "Federal",
        "Grand", "Jury", "Bench", "Honor", "Motion", "Order", "Ruling",
        "Exhibit", "Objection", "Sustained", "Overruled", "Admitted",
        "North", "South", "East", "West", "Oakdale", "Saint",
        "Park", "Street", "Avenue", "Road", "Drive", "Lane",
        "Model", "Tesla", "Porsche", "Toyota", "Blue",
        "Once", "Then", "When", "What", "Which", "While", "Where",
        "Non", "Coupable", "Coupable", "Liable",
    }

    # Remove entries where the first word is a common word
    witnesses = {w for w in witnesses if w.split()[0] not in common_words}
    
    false_positives = {
        "March 14th", "September 12th", "Your Honor", "Monsieur Président",
        "United States", "Los Angeles", "New York", "San Francisco", "Santa Monica",
        "Northside Storage", "Not Guilty", "Not Liable", "Grand Theft",
        "Federal Rules", "Common Law", "Civil Law", "Code Civil",
        "Banque Populaire", "PowerCell Inc", "Nexus Corp", "Aether Labs",
        "Fire Investigator", "Fire Marshal", "Security Guard", "Bartender",
        "Materials Engineer", "Electrical Engineer", "Arson Investigat",
        "Oakdale Drive", "California State", "State Fire",
        "Double Homicide", "Chief Fire", "National Association",
        "Combustion Chemistry", "Arson Investigation",
        "Detective Paula",
        "Information Security Officer", "Security Officer", "Inspector Grace",
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
        result = llm.invoke([
            SystemMessage(content=p.magistrate_prompt(jx)),
            HumanMessage(content=f"Case facts:\n{case_description}")
        ])
        questions = [{"question": q} for q in result.clarifying_questions]
        witnesses = list(result.witnesses) if result.witnesses else []
        missing_evidence = result.missing_evidence if hasattr(result, 'missing_evidence') else []
        missing_witnesses = result.missing_witnesses if hasattr(result, 'missing_witnesses') else []

        # Fallback: if LLM returned empty witnesses but the text clearly names people, extract them
        if not witnesses and case_description:
            extracted = _extract_witnesses_fallback(case_description)
            if extracted:
                logger.info(f"Magistrate LLM returned empty witnesses — regex fallback found {len(extracted)}: {extracted}")
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
    transcript_str = "\n".join(
        [_format_transcript_msg(m) for m in state.get("transcript", [])[-12:]]
    )
    if not transcript_str:
        return {}
    try:
        llm = get_structured_llm(ClerkOutput, temperature=0.1, model=AGENT_MODELS["Clerk"])
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
    except Exception as e:
        logger.error(f"Clerk compression error: {e}", exc_info=True)
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
                "Deliver your opening statement in 80 words or fewer.\n\n"
                "CRITICAL — This is an OPENING STATEMENT, NOT a closing argument. "
                "You are previewing what the evidence WILL show, not arguing what has been proven. "
                "Use phrases like 'the evidence will show that...' or 'you will hear testimony that...'\n"
                "Do NOT state alleged facts as if they have already been established. "
                "The defence has not yet cross-examined. No witness has testified yet.\n\n"
                "Ground every claim in the case facts provided. "
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
                "Respond in 80 words or fewer.\n\n"
                "CRITICAL — This is an OPENING STATEMENT, NOT a closing argument. "
                "You are previewing what the evidence WILL show, not arguing what has been proven. "
                "Use phrases like 'the evidence will show that...'\n"
                "Do NOT state facts as if they have already been established. "
                "No witness has testified yet.\n\n"
                "Ground every claim in the case facts provided. "
                "Do not use Markdown, bullet points, or invented details.\n\n"
                f"Case facts:\n{facts}"
            ))
        ])

        return {"transcript": [
            AIMessage(content=pros_msg.content, name="Prosecutor"),
            AIMessage(content=def_msg.content, name="Defense Counsel"),
        ]}
    except Exception as e:
        logger.error(f"Opening Statements Error: {e}", exc_info=True)
        return {"transcript": [
            AIMessage(content=f"[Opening statements could not be generated: {e}]", name="System"),
        ]}


# ── Evidence ──────────────────────────────────────────────────────────────────

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
        obj = llm.invoke([
            SystemMessage(content=prompt_func(jx)),
            HumanMessage(content=(
                f"Evidence presented:\n\"{evidence_text}\"\n\n"
                f"Case facts:\n{facts}\n\n"
                f"Raise ONE objection. Choose from these types: {', '.join(_OBJECTION_TYPE_NAMES.keys())}.\n"
                f"Cite a specific rule from: {jx['evidence_rules']}.\n"
                f"Return a JSON object with keys: objection_type, rule_cited, rationale."
            ))
        ])
        return obj
    except Exception as e:
        logger.error(f"Structured objection error: {e}", exc_info=True)
        return ObjectionOutput(objection_type="relevance", rule_cited=jx["evidence_rules"], rationale="Objection — the evidence is not relevant.")


def _argue_hearsay_exception(llm, prompt_func, jx: dict, objection: ObjectionOutput, evidence_text: str) -> str:
    """When hearsay is objected, the offering party argues a specific exception."""
    try:
        resp = llm.invoke([
            SystemMessage(content=prompt_func(jx)),
            HumanMessage(content=(
                f"Opposing counsel objected: {objection.objection_type.upper()} — {objection.rationale}\n"
                f"Your evidence: \"{evidence_text}\"\n\n"
                f"Argue ONE specific hearsay exception from {jx['evidence_rules']} in 25 words or fewer. "
                f"Possible exceptions: excited utterance, present sense impression, statement for medical diagnosis, "
                f"business records, public records, dying declaration, statement against interest, then-existing mental/emotional condition."
            ))
        ])
        return resp.content
    except Exception:
        return "The evidence falls within an applicable exception under the governing rules."


def _judge_rule_on_objection(judge_llm, jx: dict, evidence: str, objection: ObjectionOutput, exception_arg: str = "") -> JudgeRuling:
    """Judge rules on a structured objection, optionally considering a hearsay exception argument."""
    exception_block = f"\nThe offering party argues the following exception: {exception_arg}" if exception_arg else ""
    result = judge_llm.invoke([
        SystemMessage(content=p.judge_prompt(jx)),
        HumanMessage(content=(
            f"Evidence: {evidence}\n\n"
            f"Objection — Type: {_OBJECTION_TYPE_NAMES.get(objection.objection_type, objection.objection_type)}\n"
            f"Rule cited: {objection.rule_cited}\n"
            f"Rationale: {objection.rationale}{exception_block}\n\n"
            f"Rule on this objection under {jx['evidence_rules']}. If the objection is 'hearsay' and a valid "
            f"exception was argued, OVERRULE."
            f"If the evidence is admissible for one purpose but not another (e.g. not for the truth of the matter but for showing notice or state of mind), "
            f"rule 'SUSTAINED IN PART' and provide a limiting_instruction specifying exactly what use is permissible."
            f"Return a JSON object with ruling, rationale, objection_type, and limiting_instruction (empty string if not needed)."
        ))
    ])
    return result


def evidence_node(state: TrialState) -> dict:
    """
    Multi-round adversarial evidence exchange with structured objections.
    Prosecution presents → Defence objects (typed) → Prosecution argues exception if hearsay → Judge rules.
    Then Defence presents → Prosecution objects (typed) → Defence argues exception if hearsay → Judge rules.
    """
    logger.info("--- EVIDENCE PRESENTATION ---")
    jx    = _get_jx(state)
    facts = state.get("case_description", "")
    transcript = []
    objection_log = list(state.get("objection_history", []))
    if not _has_actionable_case_facts(facts):
        return _insufficient_record_evidence(jx)

    pros_llm  = get_llm(temperature=0.6, model=AGENT_MODELS["Prosecutor"])
    def_llm   = get_llm(temperature=0.6, model=AGENT_MODELS["Defense Counsel"])
    judge_llm = get_structured_llm(JudgeRuling, temperature=0.1, model=AGENT_MODELS["Judge"])
    def_decision_llm  = get_structured_llm(EvidenceObjectionDecision, temperature=0.3, model=AGENT_MODELS["Defense Counsel"])
    pros_decision_llm = get_structured_llm(EvidenceObjectionDecision, temperature=0.3, model=AGENT_MODELS["Prosecutor"])

    # ── Round 1: Prosecution presents, Defence OPTIONALLY objects ─────────────
    pros_ev = pros_llm.invoke([
        SystemMessage(content=p.prosecutor_prompt(jx)),
        HumanMessage(content=(
            f"Present ONE piece of evidence in 40 words or fewer.\n"
            f"For EACH exhibit you MUST include AUTHENTICATION: name the exhibit by its letter, "
            f"state who created/received/maintained it, how it was obtained, and whether it is a "
            f"business record, direct observation, or other admissible form.\n"
            f"Example: 'The prosecution tenders Exhibit D, an internal email from X to Y dated Z, "
            f"obtained from the company server and identified by the IT custodian. It is a business record.'\n"
            f"Ground every detail in the case facts. Do NOT invent dates or names not in the facts.\n"
            f"Case facts:\n{facts}"
        ))
    ])
    transcript.append(AIMessage(content=pros_ev.content, name="Prosecutor"))

    # Defence decides whether to object
    try:
        def_decision = def_decision_llm.invoke([
            SystemMessage(content=p.defense_objection_prompt(jx)),
            HumanMessage(content=(
                f"The prosecution has presented this evidence:\n\"{pros_ev.content}\"\n\n"
                f"Case facts:\n{facts}\n\n"
                f"Does this evidence have a GENUINE, CLEAR admissibility defect under {jx['evidence_rules']}? "
                f"If yes, set should_object=true and specify the defect. "
                f"If the evidence appears admissible (even if unfavourable), set should_object=false. "
                f"Return a JSON object with: should_object, objection_type, rule_cited, rationale."
            ))
        ])
    except Exception as e:
        logger.error(f"Evidence objection decision error (defence): {e}", exc_info=True)
        def_decision = EvidenceObjectionDecision(should_object=False)

    if def_decision.should_object and def_decision.objection_type:
        transcript.append(AIMessage(
            content=f"Objection — {_OBJECTION_TYPE_NAMES.get(def_decision.objection_type, def_decision.objection_type).upper()}. {def_decision.rule_cited}: {def_decision.rationale}",
            name="Defense Counsel",
        ))
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
        ruling1 = _judge_rule_on_objection(judge_llm, jx, pros_ev.content, obj_for_ruling, exception_arg if def_decision.objection_type == "hearsay" else "")
        objection_log.append({
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
        })
        ruling1_text = f"The objection is {ruling1.ruling}." + (f" {_strip_ruling_preamble(ruling1.rationale, ruling1.ruling)}" if ruling1.rationale else "")
        if ruling1.limiting_instruction:
            ruling1_text += f" Limiting instruction: {ruling1.limiting_instruction}"
        transcript.append(AIMessage(content=ruling1_text, name="Judge"))
    else:
        # No objection — evidence stands without challenge
        transcript.append(AIMessage(
            content=f"No objection. The evidence is admitted.",
            name="Defense Counsel",
        ))

    # ── Round 2: Defence presents, Prosecution OPTIONALLY objects ─────────────
    def_ev = def_llm.invoke([
        SystemMessage(content=p.defense_prompt(jx)),
        HumanMessage(content=(
            f"Present ONE piece of evidence for the defence in 40 words or fewer.\n"
            f"For EACH exhibit you MUST include AUTHENTICATION: name the exhibit by its letter, "
            f"state who created/received/maintained it, how it was obtained, and whether it is a "
            f"business record, direct observation, or other admissible form.\n"
            f"Ground every detail in the case facts. Do NOT invent details.\n"
            f"Case facts:\n{facts}"
        ))
    ])
    transcript.append(AIMessage(content=def_ev.content, name="Defense Counsel"))

    # Prosecution decides whether to object
    try:
        pros_decision = pros_decision_llm.invoke([
            SystemMessage(content=p.prosecution_objection_prompt(jx)),
            HumanMessage(content=(
                f"The defence has presented this evidence:\n\"{def_ev.content}\"\n\n"
                f"Case facts:\n{facts}\n\n"
                f"Does this evidence have a GENUINE, CLEAR admissibility defect under {jx['evidence_rules']}? "
                f"If yes, set should_object=true and specify the defect. "
                f"If the evidence appears admissible (even if unfavourable), set should_object=false. "
                f"Return a JSON object with: should_object, objection_type, rule_cited, rationale."
            ))
        ])
    except Exception as e:
        logger.error(f"Evidence objection decision error (prosecution): {e}", exc_info=True)
        pros_decision = EvidenceObjectionDecision(should_object=False)

    if pros_decision.should_object and pros_decision.objection_type:
        transcript.append(AIMessage(
            content=f"Objection — {_OBJECTION_TYPE_NAMES.get(pros_decision.objection_type, pros_decision.objection_type).upper()}. {pros_decision.rule_cited}: {pros_decision.rationale}",
            name="Prosecutor",
        ))
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
        ruling2 = _judge_rule_on_objection(judge_llm, jx, def_ev.content, obj_for_ruling2, exception_arg2 if pros_decision.objection_type == "hearsay" else "")
        objection_log.append({
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
        })
        ruling2_text = f"The objection is {ruling2.ruling}." + (f" {_strip_ruling_preamble(ruling2.rationale, ruling2.ruling)}" if ruling2.rationale else "")
        if ruling2.limiting_instruction:
            ruling2_text += f" Limiting instruction: {ruling2.limiting_instruction}"
        transcript.append(AIMessage(content=ruling2_text, name="Judge"))
    else:
        transcript.append(AIMessage(
            content="No objection. The evidence is admitted.",
            name="Prosecutor",
        ))

    # Update clerk state immediately with the new rulings
    updated_state = {**state, "transcript": state.get("transcript", []) + transcript}
    clerk_update = _clerk_compression(updated_state)
    return {"transcript": transcript, "objection_history": objection_log, **clerk_update}


# ── Discovery ──────────────────────────────────────────────────────────────────

def discovery_node(state: TrialState) -> dict:
    """Each side discloses its list of evidence items before trial."""
    logger.info("--- DISCOVERY ---")
    jx = _get_jx(state)
    facts = state.get("case_description", "")
    transcript = []

    if not _has_actionable_case_facts(facts):
        transcript.append(AIMessage(
            content="The record is insufficient for meaningful discovery. Both sides reserve the right to supplement.",
            name="Clerk",
        ))
        return {"transcript": transcript}

    try:
        pros_llm = get_structured_llm(DiscoveryItems, temperature=0.3, model=AGENT_MODELS["Prosecutor"])
        def_llm  = get_structured_llm(DiscoveryItems, temperature=0.3, model=AGENT_MODELS["Defense Counsel"])

        pros_disc = pros_llm.invoke([
            SystemMessage(content=p.prosecutor_discovery_prompt(jx)),
            HumanMessage(content=f"Case facts:\n{facts}")
        ])
        transcript.append(AIMessage(
            content=f"Prosecution disclosure: {'; '.join(pros_disc.items[:4])}",
            name="Prosecutor",
        ))

        def_disc = def_llm.invoke([
            SystemMessage(content=p.defense_discovery_prompt(jx)),
            HumanMessage(content=f"Case facts:\n{facts}")
        ])
        transcript.append(AIMessage(
            content=f"Defence disclosure: {'; '.join(def_disc.items[:3])}",
            name="Defense Counsel",
        ))

        transcript.append(AIMessage(
            content="Discovery complete. The Court acknowledges the disclosed evidence lists.",
            name="Judge",
        ))

        return {
            "transcript": transcript,
            "disclosed_prosecution": list(pros_disc.items),
            "disclosed_defense": list(def_disc.items),
        }
    except Exception as e:
        logger.error(f"Discovery Error: {e}", exc_info=True)
        return {"transcript": [
            AIMessage(content=f"[Discovery could not be completed: {e}]", name="System"),
        ]}


# ── Motion Practice ────────────────────────────────────────────────────────────

def motion_practice_node(state: TrialState) -> dict:
    """Pre-trial motion practice. Each side may file a motion, opponent responds, judge rules."""
    logger.info("--- MOTION PRACTICE ---")
    jx = _get_jx(state)
    facts = state.get("case_description", "")
    transcript = []
    motion_log = list(state.get("motion_rulings", []))

    if not _has_actionable_case_facts(facts):
        transcript.append(AIMessage(
            content="The record is insufficient for substantive motions. The court will proceed to trial.",
            name="Judge",
        ))
        return {"transcript": transcript}

    try:
        pros_llm = get_structured_llm(MotionFiling, temperature=0.3, model=AGENT_MODELS["Prosecutor"])
        def_llm  = get_structured_llm(MotionFiling, temperature=0.3, model=AGENT_MODELS["Defense Counsel"])
        def_opp_llm = get_structured_llm(MotionOpposition, temperature=0.3, model=AGENT_MODELS["Defense Counsel"])
        pros_opp_llm = get_structured_llm(MotionOpposition, temperature=0.3, model=AGENT_MODELS["Prosecutor"])
        judge_llm = get_structured_llm(MotionRulingResult, temperature=0.1, model=AGENT_MODELS["Judge"])

        pros_movant = "Prosecution" if jx["case_type"] == "Criminal" else "Plaintiff"
        def_movant  = "Defence"

        # Round 1: Prosecution motion
        pros_motion = pros_llm.invoke([
            SystemMessage(content=p.motion_prompt(jx, pros_movant)),
            HumanMessage(content=f"Case facts:\n{facts}")
        ])
        transcript.append(AIMessage(
            content=f"MOTION: {pros_motion.motion_type}. {pros_motion.relief_sought}. {pros_motion.argument}",
            name="Prosecutor",
        ))

        def_opp = def_opp_llm.invoke([
            SystemMessage(content=p.opposition_prompt(jx, def_movant)),
            HumanMessage(content=(
                f"Motion: {pros_motion.motion_type}\n"
                f"Relief sought: {pros_motion.relief_sought}\n"
                f"Argument: {pros_motion.argument}\n"
                f"Case facts:\n{facts}"
            ))
        ])
        transcript.append(AIMessage(
            content=f"OPPOSITION: {def_opp.argument} [Rule: {def_opp.rule_cited}]",
            name="Defense Counsel",
        ))

        ruling1 = judge_llm.invoke([
            SystemMessage(content=p.judge_motion_prompt(jx)),
            HumanMessage(content=(
                f"Motion: {pros_motion.motion_type}\n"
                f"Proponent argues: {pros_motion.argument}\n"
                f"Opponent argues: {def_opp.argument}\n\n"
                f"Rule on this motion. Return JSON with 'ruling' (GRANTED or DENIED) and 'rationale'."
            ))
        ])
        motion_log.append({
            "motion_type": pros_motion.motion_type,
            "movant": pros_movant,
            "arguing": pros_motion.argument,
            "opposition": def_opp.argument,
            "ruling": ruling1.ruling,
            "rationale": ruling1.rationale,
        })
        transcript.append(AIMessage(
            content=f"Motion {ruling1.ruling}. {ruling1.rationale}",
            name="Judge",
        ))

        # Round 2: Defence motion
        def_motion = def_llm.invoke([
            SystemMessage(content=p.motion_prompt(jx, def_movant)),
            HumanMessage(content=f"Case facts:\n{facts}")
        ])
        transcript.append(AIMessage(
            content=f"MOTION: {def_motion.motion_type}. {def_motion.relief_sought}. {def_motion.argument}",
            name="Defense Counsel",
        ))

        pros_opp = pros_opp_llm.invoke([
            SystemMessage(content=p.opposition_prompt(jx, pros_movant)),
            HumanMessage(content=(
                f"Motion: {def_motion.motion_type}\n"
                f"Relief sought: {def_motion.relief_sought}\n"
                f"Argument: {def_motion.argument}\n"
                f"Case facts:\n{facts}"
            ))
        ])
        transcript.append(AIMessage(
            content=f"OPPOSITION: {pros_opp.argument} [Rule: {pros_opp.rule_cited}]",
            name="Prosecutor",
        ))

        ruling2 = judge_llm.invoke([
            SystemMessage(content=p.judge_motion_prompt(jx)),
            HumanMessage(content=(
                f"Motion: {def_motion.motion_type}\n"
                f"Proponent argues: {def_motion.argument}\n"
                f"Opponent argues: {pros_opp.argument}\n\n"
                f"Rule on this motion. Return JSON with 'ruling' (GRANTED or DENIED) and 'rationale'."
            ))
        ])
        motion_log.append({
            "motion_type": def_motion.motion_type,
            "movant": def_movant,
            "arguing": def_motion.argument,
            "opposition": pros_opp.argument,
            "ruling": ruling2.ruling,
            "rationale": ruling2.rationale,
        })
        transcript.append(AIMessage(
            content=f"Motion {ruling2.ruling}. {ruling2.rationale}",
            name="Judge",
        ))

        transcript.append(AIMessage(
            content="Motion practice concluded. The court will now proceed to opening statements.",
            name="Judge",
        ))

        return {"transcript": transcript, "motion_rulings": motion_log}
    except Exception as e:
        logger.error(f"Motion Practice Error: {e}", exc_info=True)
        return {"transcript": [
            AIMessage(content=f"[Motion practice could not be completed: {e}]", name="System"),
        ]}


# ── Expert Qualification Helpers ──────────────────────────────────────────────

_EXPERT_KEYWORDS = ["Dr.", "dr.", "Doctor", "Prof.", "Professor", "MD", "PhD", "Expert", "Specialist", "Engineer", "Analyst"]

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

    transcript.append(AIMessage(
        content=f"The prosecution seeks to qualify {witness_name} as an expert witness.",
        name="Prosecutor",
    ))

    try:
        q = pros_llm.invoke([
            SystemMessage(content=p.prosecutor_prompt(jx)),
            HumanMessage(content=(
                f"{_EXPERT_QUALIFICATION_PROMPT}\n"
                f"Proposed expert: {witness_name}\n"
                f"Case facts: {facts}"
            ))
        ])
        transcript.append(AIMessage(content=q.content, name="Prosecutor"))

        try:
            expert_llm = get_llm(temperature=0.5, model=AGENT_MODELS["Witness"])
        except Exception:
            expert_llm = get_llm(temperature=0.5, model="qwen-flash")

        a = expert_llm.invoke([
            SystemMessage(content=(
                f"You are {witness_name}, a professional being offered as an expert witness. "
                f"Describe your relevant credentials concisely in 20 words or fewer. "
                f"Ground your qualifications in what the case facts imply about your role."
            )),
            HumanMessage(content=(
                f"Question: {q.content}\n"
                f"Case facts: {facts}"
            ))
        ])
        transcript.append(AIMessage(content=a.content, name="Witness"))

        challenge = def_llm.invoke([
            SystemMessage(content=p.defense_prompt(jx)),
            HumanMessage(content=(
                f"{_EXPERT_CHALLENGE_PROMPT}\n"
                f"The proposed expert {witness_name} testified: \"{a.content}\"\n"
                f"Case facts: {facts}"
            ))
        ])
        transcript.append(AIMessage(content=challenge.content, name="Defense Counsel"))

        class ExpertQualRuling(BaseModel):
            qualified: bool = Field(description="True if the witness qualifies as an expert.")
            rationale: str = Field(description="Legal basis for the ruling.")

        judge_structured = get_structured_llm(ExpertQualRuling, temperature=0.1, model=AGENT_MODELS["Judge"])
        ruling = judge_structured.invoke([
            SystemMessage(content=p.judge_prompt(jx)),
            HumanMessage(content=(
                f"Prosecution seeks to qualify {witness_name} as an expert.\n"
                f"Credentials: \"{a.content}\"\n"
                f"Defence challenge: \"{challenge.content}\"\n\n"
                f"Rule on expert qualification under {jx['evidence_rules']}. "
                f"Return JSON with 'qualified' (true/false) and 'rationale'."
            ))
        ])
        result_text = "QUALIFIED" if ruling.qualified else "NOT QUALIFIED"
        transcript.append(AIMessage(
            content=f"Expert qualification of {witness_name}: {result_text}. {ruling.rationale}",
            name="Judge",
        ))
        return ruling.qualified
    except Exception as e:
        logger.error(f"Expert qualification error: {e}", exc_info=True)
        transcript.append(AIMessage(
            content=f"Expert qualification could not be completed: {e}",
            name="System",
        ))
        return False


# ── Witness Examination ───────────────────────────────────────────────────────

def _parse_json_robustly(text: str) -> dict:
    """
    Attempts to extract and parse a JSON object from text, handling common LLM formatting issues
    such as markdown code blocks, leading/trailing text, and single quotes.
    """
    text = text.strip()
    # Try finding the first '{' and last '}'
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        json_str = text[start:end+1]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            try:
                # Replace single quotes with double quotes
                cleaned = json_str.replace("'", '"')
                # Remove trailing commas before closing braces/brackets
                cleaned = re.sub(r',\s*([\]}])', r'\1', cleaned)
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
        match = re.search(fr'"{key}"\s*:\s*"([^"]*)"', text)
        if match:
            result[key] = match.group(1)
            
    return result


def _ask_with_objection_gate(
    question_text, asking_name, opposing_name, opposing_model,
    witness_name, witness_llm, fc_llm, judge_ruling_llm,
    facts, jx, phase_type,
    transcript, objection_log,
    qa_log=None, answer_key="a", qa_wrapper=False,
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
        resp = opposing_llm.invoke([
            SystemMessage(content=p.examination_objection_prompt(jx, opposing_name, phase_type)),
            HumanMessage(content=(
                f"Opposing counsel ({asking_name}) asked this question to {witness_name} "
                f"during {phase_type}:\n\"{question_text}\"\n\n"
                f"Case facts:\n{facts}\n\n"
                f"Respond with a JSON object: {{\"should_object\": false}} if you do NOT object, "
                f"or {{\"should_object\": true, \"objection_type\": \"...\", \"rule_cited\": \"...\", \"rationale\": \"...\"}} if you DO object."
            ))
        ])
        text = resp.content.strip()
        data = _parse_json_robustly(text)
        obj = ExaminationObjection(**{k: v for k, v in data.items() if hasattr(ExaminationObjection, k)})
    except Exception as e:
        logger.error(f"Objection check error in {phase_type}: {e}", exc_info=True)
        obj = ExaminationObjection(should_object=False)

    question_struck = False
    if obj.should_object:
        transcript.append(AIMessage(
            content=f"Objection — {obj.objection_type.upper()}. {obj.rule_cited}: {obj.rationale}",
            name=opposing_name,
        ))

        try:
            ruling = judge_ruling_llm.invoke([
                SystemMessage(content=p.judge_prompt(jx)),
                HumanMessage(content=(
                    f"During {phase_type}, {opposing_name} objects to this question to {witness_name}:\n"
                    f"\"{question_text}\"\n\n"
                    f"Objection type: {obj.objection_type}\n"
                    f"Rule cited: {obj.rule_cited}\n"
                    f"Rationale: {obj.rationale}\n\n"
                    f"Rule on this objection under {jx['evidence_rules']}. Return a JSON object."
                ))
            ])
        except Exception as e:
            logger.error(f"Judge ruling error in {phase_type}: {e}", exc_info=True)
            transcript.append(AIMessage(content="[Judge ruling unavailable — the question stands]", name="System"))
        else:
            objection_log.append({
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
            })

            ruling_text = f"OBJECTION {ruling.ruling}." + (
                f" {_strip_ruling_preamble(ruling.rationale, ruling.ruling)}"
                if ruling.rationale else ""
            )
            if getattr(ruling, 'limiting_instruction', ''):
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
        a = witness_llm.invoke([
            SystemMessage(content=p.witness_prompt(jx)),
            HumanMessage(content=(
                f"You are {witness_name}. Answer in 40 words or fewer.\n"
                f"Q: {question_text}\n"
                f"Case facts:\n{facts}"
            ))
        ])
    except Exception as e:
        logger.error(f"Witness LLM error in {phase_type}: {e}", exc_info=True)
        transcript.append(AIMessage(content="[Witness could not respond]", name="System"))
        return

    try:
        fc = fc_llm.invoke([
            SystemMessage(content=p.fact_checker_prompt(jx)),
            HumanMessage(content=f"Case facts:\n{facts}\n\nWitness answer:\n{a.content}")
        ])
    except Exception:
        fc = AIMessage(content="PASS")

    if not fc.content.strip().upper().startswith("PASS"):
        transcript.append(AIMessage(content=fc.content, name="Fact Checker"))
        try:
            a = witness_llm.invoke([
                SystemMessage(content=p.witness_prompt(jx)),
                HumanMessage(content=(
                    f"You are {witness_name}.\n"
                    f"Question: {question_text}\n"
                    f"Your previous answer was objected to: {fc.content}\n"
                    f"Acknowledge the correction and answer correctly based ONLY on these case facts:\n{facts}"
                ))
            ])
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
    examiner_llm, examiner_prompt_fn, examiner_name,
    witness_name, witness_llm, fc_llm,
    facts, jx, phase_type, max_q,
    prior_context="", transcript=None,
    judge_ruling_llm=None, objection_log=None,
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
    MAX_TOTAL_ATTEMPTS = max_q * 3  # hard safety cap — prevents infinite loops
    MAX_SUSTAINED_STREAK = 3

    while q_num <= max_q and total_attempts < MAX_TOTAL_ATTEMPTS:
        total_attempts += 1
        history = str(qa_log[-4:]) if qa_log else "(no prior questions)"
        if prior_context and q_num == 1:
            history = prior_context

        try:
            q = examiner_llm.invoke([
                SystemMessage(content=examiner_prompt_fn(jx)),
                HumanMessage(content=(
                    f"{phase_type.upper().replace('_', ' ')} — Q{q_num} (max {max_q}) to {witness_name}.\n"
                    f"Objective: {objective}\n"
                    f"{question_rule}\n"
                    f"Prior Q&A: {history}\n\n"
                    f"If you have fully established your points and have nothing meaningful left to ask, "
                    f"respond with exactly the word 'DONE' and nothing else.\n"
                    f"Otherwise, ask ONE short question (under 25 words). Base it on these case facts:\n\n{facts}"
                ))
            ])
        except Exception as e:
            logger.error(f"Examiner LLM error in {phase_type} Q{q_num}: {e}", exc_info=True)
            transcript.append(AIMessage(content=f"[Examiner error — proceeding to next witness]", name="System"))
            break

        content = q.content.strip()
        if content.upper() == "DONE" or content.upper().startswith("DONE"):
            break

        transcript.append(AIMessage(content=content, name=examiner_name))

        # ── Opposing Counsel Objection Check ──────────────────────────
        if opposing_llm is not None and judge_ruling_llm is not None:
            obj = ExaminationObjection(should_object=False)
            try:
                resp = opposing_llm.invoke([
                    SystemMessage(content=p.examination_objection_prompt(jx, opposing_name, phase_type)),
                    HumanMessage(content=(
                        f"Opposing counsel ({examiner_name}) asked this question to {witness_name} "
                        f"during {phase_type} examination:\n\"{content}\"\n\n"
                        f"Case facts:\n{facts}\n\n"
                        f"Respond with a JSON object: {{\"should_object\": false}} if you do NOT object, "
                        f"or {{\"should_object\": true, \"objection_type\": \"...\", \"rule_cited\": \"...\", \"rationale\": \"...\"}} if you DO object."
                    ))
                ])
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
                logger.info(f"[OBJECTION] {opposing_name} objects during {phase_type}: {obj.objection_type} — Q: {content[:60]}...")
                transcript.append(AIMessage(
                    content=f"Objection — {obj.objection_type.upper()}. {obj.rule_cited}: {obj.rationale}",
                    name=opposing_name,
                ))

                try:
                    ruling = judge_ruling_llm.invoke([
                        SystemMessage(content=p.judge_prompt(jx)),
                        HumanMessage(content=(
                            f"During {phase_type} examination of {witness_name}, {opposing_name} objects to this question:\n"
                            f"\"{content}\"\n\n"
                            f"Objection type: {obj.objection_type}\n"
                            f"Rule cited: {obj.rule_cited}\n"
                            f"Rationale: {obj.rationale}\n\n"
                            f"Rule on this objection under {jx['evidence_rules']}. Return a JSON object."
                        ))
                    ])
                except Exception as e:
                    logger.error(f"Judge ruling error in {phase_type}: {e}", exc_info=True)
                    transcript.append(AIMessage(content="[Judge ruling unavailable — objection noted but question stands]", name="System"))
                    q_num += 1
                    sustained_in_a_row = 0
                    continue

                objection_log.append({
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
                })

                ruling_text = f"OBJECTION {ruling.ruling}." + (
                    f" {_strip_ruling_preamble(ruling.rationale, ruling.ruling)}"
                    if ruling.rationale else ""
                )
                if getattr(ruling, 'limiting_instruction', ''):
                    ruling_text += f" Limiting instruction: {ruling.limiting_instruction}"
                transcript.append(AIMessage(content=ruling_text, name="Judge"))

                if ruling.ruling.upper() == "SUSTAINED":
                    sustained_in_a_row += 1
                    qa_log.append({"q": content, "a": "[OBJECTION SUSTAINED — QUESTION STRUCK]"})
                    if sustained_in_a_row >= MAX_SUSTAINED_STREAK:
                        transcript.append(AIMessage(
                            content=f"Counsel, please rephrase your line of questioning.",
                            name="Judge"
                        ))
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
            a = witness_llm.invoke([
                SystemMessage(content=p.witness_prompt(jx)),
                HumanMessage(content=(
                    f"You are {witness_name}. Answer in 40 words or fewer.\n"
                    f"Q: {content}\n"
                    f"Case facts:\n{facts}"
                ))
            ])
        except Exception as e:
            logger.error(f"Witness LLM error in {phase_type} Q{q_num}: {e}", exc_info=True)
            transcript.append(AIMessage(content="[Witness could not respond — continuing]", name="System"))
            q_num += 1
            sustained_in_a_row = 0
            continue

        try:
            fc = fc_llm.invoke([
                SystemMessage(content=p.fact_checker_prompt(jx)),
                HumanMessage(content=f"Case facts:\n{facts}\n\nWitness answer:\n{a.content}")
            ])
        except Exception as e:
            logger.error(f"Fact checker error in {phase_type} Q{q_num}: {e}", exc_info=True)
            transcript.append(AIMessage(content=a.content, name="Witness"))
            qa_log.append({"q": content, "a": a.content})
            q_num += 1
            sustained_in_a_row = 0
            continue

        if not fc.content.strip().upper().startswith("PASS"):
            transcript.append(AIMessage(content=fc.content, name="Fact Checker"))
            try:
                a = witness_llm.invoke([
                    SystemMessage(content=p.witness_prompt(jx)),
                    HumanMessage(content=(
                        f"You are {witness_name}.\n"
                        f"Question: {content}\n"
                        f"Your previous answer was objected to: {fc.content}\n"
                        f"Acknowledge the correction and answer correctly based ONLY on these case facts:\n{facts}"
                    ))
                ])
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
        r'(?:the\s+)?defendant\s*,?\s*' + re.escape(witness_name)[:40],
        r'(?:the\s+)?accused\s*,?\s*' + re.escape(witness_name)[:40],
        r'charged\s+(?:with|under).{0,80}' + re.escape(witness_name)[:40],
        r'exercising\s+(?:his|her|their)\s+right\s+to\s+silence',
        r'has\s+not\s+testified\s+directly',
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
                        window = desc_lower[max(0, idx - 50):min(len(desc_lower), idx + 150)]
                        if partial in window:
                            return True
    return False


def _extract_witness_context(witness_name: str, case_description: str) -> str:
    """Extract case-fact context lines relevant to a specific witness for topic filtering."""
    if not witness_name or not case_description:
        return case_description[:200]
    parts = witness_name.split()
    if len(parts) < 2:
        return case_description[:200]
    
    sentences = re.split(r'(?<=[.!?])\s+', case_description)
    relevant = []
    search_terms = [
        witness_name.lower(),
        parts[0].lower(),
        parts[-1].lower(),
    ]
    # Also include role terms if found in nearby sentences
    role_terms = []
    
    for s in sentences:
        s_lower = s.lower()
        if any(term in s_lower for term in search_terms):
            relevant.append(s)
            # Try to capture the witness role
            for role_kw in ["witness", "will testify", "testified", "investigator", "expert", 
                          "accountant", "inspector", "whistleblower", "officer", "analyst",
                          "defendant", "victim", "manager", "director", "employee"]:
                if role_kw in s_lower and role_kw not in role_terms:
                    role_terms.append(role_kw)
    
    if len(relevant) < 2:
        return case_description[:300]
    
    context = " ".join(relevant[:5])
    role_hint = ""
    if role_terms:
        role_hint = f"\nThis witness's role: {', '.join(role_terms[:3])}. "
    
    return (
        f"{role_hint}Focus your examination on the following case facts relevant to {witness_name} "
        f"and their stated role. Do NOT ask about topics that another witness is better positioned to address:\n\n{context}"
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
        transcript.append(AIMessage(
            content=f"The court calls {current_witness} to the stand.",
            name="Clerk"
        ))
        transcript.append(AIMessage(
            content=f"I exercise my right to remain silent under applicable law. I will not testify in these proceedings.",
            name="Witness"
        ))
        transcript.append(AIMessage(
            content=f"Understood. The court respects the witness's right to silence. "
                    f"The fact-finder shall draw no adverse inference from this election. "
                    f"Counsel, call your next witness.",
            name="Judge"
        ))
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
            **clerk_update
        }
    
    pros_llm = get_llm(temperature=0.6, model=AGENT_MODELS["Prosecutor"])
    def_llm  = get_llm(temperature=0.6, model=AGENT_MODELS["Defense Counsel"])
    wit_llm  = get_llm(temperature=0.5, model=AGENT_MODELS["Witness"])
    fc_llm   = get_llm(temperature=0.0, model=AGENT_MODELS["Fact Checker"])
    judge_llm = get_llm(temperature=0.1, model=AGENT_MODELS["Judge"])
    judge_ruling_llm = get_structured_llm(JudgeRuling, temperature=0.1, model=AGENT_MODELS["Judge"])
    
    expert_witnesses = list(state.get("expert_witnesses", []))
    objection_log = list(state.get("objection_history", []))
    
    # Voir Dire (Expert qualification)
    expert_qualified = False
    if _is_expert_candidate(current_witness) and jx["cross"]:
        expert_qualified = _qualify_expert(
            state, current_witness, jx, pros_llm, def_llm, judge_llm, transcript
        )
        if expert_qualified:
            expert_witnesses.append(current_witness)
            
    direct_qa = []
    
    # ── Oath / Swearing-In Ceremony ────────────────────────────
    oath_phrases = {
        "judeo_christian": {
            "clerk": f"Do you solemnly swear that the testimony you are about to give in this matter shall be the truth, the whole truth, and nothing but the truth, so help you God?",
            "witness": "I do.",
        },
        "secular": {
            "clerk": f"Do you solemnly affirm, under penalty of perjury, that the testimony you are about to give shall be the truth, the whole truth, and nothing but the truth?",
            "witness": "I do.",
        },
    }
    # Use secular oath for civil law / inquisitorial systems
    is_islamic = "Islamic" in jx["system"]
    is_civil = "Civil Law" in jx["system"]
    oath = oath_phrases["secular"] if (is_civil or is_islamic) else oath_phrases["judeo_christian"]
    court_address = jx["address"].split(";")[0].strip()
    transcript.append(AIMessage(
        content=f"The Clerk administers the oath to {current_witness}.",
        name="Clerk"
    ))
    transcript.append(AIMessage(content=oath["clerk"], name="Clerk"))
    transcript.append(AIMessage(content=oath["witness"], name="Witness"))
    transcript.append(AIMessage(
        content=f"Please be seated. {court_address}, your witness is sworn.",
        name="Judge"
    ))
    
    # Visual phase transition banner
    if jx["cross"]:
        transcript.append(AIMessage(
            content=f"⚖️ Witness Examination of {current_witness} — Direct Examination begins.",
            name="Judge"
        ))
        
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
        transcript.append(AIMessage(
            content=f"⚖️ Inquisitorial Witness Examination of {current_witness} — Judicial Inquiry begins.",
            name="Judge"
        ))
        
        # ── INQUISITORIAL: Judge leads (3 Qs) ────
        for q_num in range(1, 4):
            try:
                q = judge_llm.invoke([
                    SystemMessage(content=p.judge_prompt(jx)),
                    HumanMessage(content=(
                        f"JUDICIAL EXAMINATION — Question {q_num} of 3.\n"
                        f"Witness: {current_witness}.\n"
                        f"Ask a neutral, fact-finding question.\nCase facts:\n{facts}"
                    ))
                ])
            except Exception as e:
                logger.error(f"Judge question error in inquisitorial Q{q_num}: {e}", exc_info=True)
                continue

            transcript.append(AIMessage(content=f"Q (Judge): {q.content}", name="Judge"))

            try:
                a = wit_llm.invoke([
                    SystemMessage(content=p.witness_prompt(jx)),
                    HumanMessage(content=(
                        f"You are {current_witness}.\n"
                        f"The Judge asks: {q.content}\n"
                        f"Answer based ONLY on these case facts:\n{facts}"
                    ))
                ])
            except Exception as e:
                logger.error(f"Witness answer error in inquisitorial Q{q_num}: {e}", exc_info=True)
                transcript.append(AIMessage(content="[Witness could not respond]", name="System"))
                continue

            try:
                fc = fc_llm.invoke([
                    SystemMessage(content=p.fact_checker_prompt(jx)),
                    HumanMessage(content=f"Case facts:\n{facts}\n\nWitness answer:\n{a.content}")
                ])
            except Exception:
                fc = AIMessage(content="PASS")

            if not fc.content.strip().upper().startswith("PASS"):
                transcript.append(AIMessage(content=fc.content, name="Fact Checker"))
                try:
                    a = wit_llm.invoke([
                        SystemMessage(content=p.witness_prompt(jx)),
                        HumanMessage(content=(
                            f"You are {current_witness}.\n"
                            f"The Judge asks: {q.content}\n"
                            f"Your previous answer was objected to: {fc.content}\n"
                            f"Acknowledge the correction and answer correctly based ONLY on these case facts:\n{facts}"
                        ))
                    ])
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
        **clerk_update
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
    def_llm  = get_llm(temperature=0.6, model=AGENT_MODELS["Defense Counsel"])
    wit_llm  = get_llm(temperature=0.5, model=AGENT_MODELS["Witness"])
    fc_llm   = get_llm(temperature=0.0, model=AGENT_MODELS["Fact Checker"])
    judge_ruling_llm = get_structured_llm(JudgeRuling, temperature=0.1, model=AGENT_MODELS["Judge"])
    
    objection_log = list(state.get("objection_history", []))
    direct_qa = state.get("witness_direct_qa", [])
    
    if jx["cross"]:
        transcript.append(AIMessage(
            content=f"⚖️ Witness Examination of {current_witness} — Defense Cross-Examination begins.",
            name="Judge"
        ))
        
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
        transcript.append(AIMessage(
            content=f"⚖️ Inquisitorial Witness Examination of {current_witness} — Prosecution supplementary questioning begins.",
            name="Judge"
        ))
        transcript.append(AIMessage(
            content=f"Madame/Monsieur le Procureur — any supplementary questions for {current_witness}?",
            name="Judge"
        ))
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
    
    return {
        "transcript": transcript,
        "objection_history": objection_log,
        **clerk_update
    }


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
    def_llm  = get_llm(temperature=0.6, model=AGENT_MODELS["Defense Counsel"])
    wit_llm  = get_llm(temperature=0.5, model=AGENT_MODELS["Witness"])
    fc_llm   = get_llm(temperature=0.0, model=AGENT_MODELS["Fact Checker"])
    judge_ruling_llm = get_structured_llm(JudgeRuling, temperature=0.1, model=AGENT_MODELS["Judge"])
    
    impeachment_log = list(state.get("impeachment_attempts", []))
    objection_log = list(state.get("objection_history", []))
    direct_qa = state.get("witness_direct_qa", [])
    
    if jx["cross"]:
        transcript.append(AIMessage(
            content=f"⚖️ Witness Examination of {current_witness} — Impeachment and Redirect begins.",
            name="Judge"
        ))
        
        # ── ADVERSARIAL: Structured Impeachment (4-step sequence) ──
        impeachment_step_labels = ["Foundation", "Commitment", "Confrontation", "Closing"]
        try:
            impeach_resp = def_llm.invoke([
                SystemMessage(content=p.defense_impeachment_prompt(jx)),
                HumanMessage(content=(
                    f"IMPEACHMENT — Structured 4-step sequence to {current_witness}.\n"
                    f"Their direct answers: {direct_qa}\n\n"
                    f"Challenge the witness's credibility. Base it on the case facts.\n"
                    f"Facts:\n{facts}"
                ))
            ])
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
            step_label = impeachment_step_labels[i] if i < len(impeachment_step_labels) else f"Step {i+1}"
            logger.info(f"[IMPEACH] Step {i+1}/{len(impeach_questions)} ({step_label}): {q_text[:60]}...")
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
            redirect_resp = pros_llm.invoke([
                SystemMessage(content=p.prosecution_redirect_prompt(jx)),
                HumanMessage(content=(
                    f"REDIRECT — rehabilitate {current_witness} after impeachment.\n"
                    f"Their direct Q&A: {direct_qa}\n\n"
                    f"Case facts:\n{facts}"
                ))
            ])
            redirect_questions = _parse_json_robustly(redirect_resp.content.strip())
            if isinstance(redirect_questions, list) and len(redirect_questions) >= 1:
                redirect_questions = [str(q) for q in redirect_questions[:3]]
            else:
                redirect_questions = [redirect_resp.content.strip()] if redirect_resp.content.strip() else []
        except Exception as e:
            logger.error(f"Redirect question error: {e}", exc_info=True)
            redirect_questions = []

        for i, q_text in enumerate(redirect_questions):
            logger.info(f"[REDIRECT] Q{i+1}/{len(redirect_questions)}: {q_text[:60]}...")
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
        transcript.append(AIMessage(
            content=f"⚖️ Inquisitorial Witness Examination of {current_witness} — Defence supplementary questioning begins.",
            name="Judge"
        ))
        transcript.append(AIMessage(
            content=f"Maître — any supplementary questions for {current_witness}?",
            name="Judge"
        ))
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
        logger.error(f"Closing Arguments Error: {e}", exc_info=True)
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
        logger.error(f"Jury Instructions Error: {e}", exc_info=True)
        return {"transcript": [
            AIMessage(content=f"[Jury instructions could not be generated: {e}]", name="System"),
        ]}


# ── Jury Deliberation ─────────────────────────────────────────────────────────


def _parse_juror_vote(raw_text: str) -> tuple[str, str]:
    """
    Parse a juror's response to extract their statement and vote.
    Returns (statement, vote) where vote is one of:
    'Guilty', 'Not Guilty', 'Liable', 'Not Liable', 'Undecided'
    """
    lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
    vote = "Undecided"
    statement = raw_text

    vote_patterns = [
        r"vote:\s*(.+)$",
        r"^(guilty|not guilty|liable|not liable|undecided)\s*[.!?]?\s*$",
        r"i\s+(?:find\s+the\s+defendant\s+)?(guilty|not guilty|liable|not liable)",
        r"(?:my\s+vote\s+is|i\s+vote\s*:?)\s*(guilty|not guilty|liable|not liable|undecided)",
        r"(?:i\s+(?:believe|conclude|determine)\s+(?:the\s+defendant\s+is|that\s+the\s+defendant\s+is))\s*(guilty|not guilty|liable|not liable)",
        r"(?:the\s+(?:defendant|accused)\s+is)\s*(guilty|not guilty|liable|not liable)",
        r"(?:burden\s+(?:met|not\s+met|satisfied|not\s+satisfied))",
        r"(?:evidence\s+(?:sufficient|insufficient|meets\s+the\s+standard|does\s+not\s+meet))",
    ]

    for line in reversed(lines):
        line_lower = line.lower()

        for pattern in vote_patterns:
            match = re.search(pattern, line_lower)
            if match:
                vote_text = match.group(1) if match.lastindex else line_lower
                vote_text = vote_text.strip()

                if "not guilty" in vote_text or "not liable" in vote_text:
                    if "not guilty" in vote_text:
                        vote = "Not Guilty"
                    else:
                        vote = "Not Liable"
                elif "guilty" in vote_text:
                    vote = "Guilty"
                elif "liable" in vote_text:
                    vote = "Liable"
                elif "undecided" in vote_text:
                    vote = "Undecided"
                elif "not met" in vote_text or "insufficient" in vote_text or "does not meet" in vote_text:
                    vote = "Not Guilty"
                elif "met" in vote_text or "sufficient" in vote_text or "meets" in vote_text:
                    vote = "Guilty"

                statement = "\n".join(
                    l for l in lines if not re.search(pattern, l.lower())
                ).strip()
                if not statement:
                    statement = raw_text
                return statement, vote

    for line in lines:
        line_lower = line.lower()
        if "not guilty" in line_lower:
            return raw_text, "Not Guilty"
        if "not liable" in line_lower:
            return raw_text, "Not Liable"

    return statement, vote


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
    juror_llm = get_llm(temperature=0.4, model=juror_profile.get("model", AGENT_MODELS.get("Jury Foreperson", "qwen-plus-latest")))

    prior_block = ""
    if prior_statements:
        prior_block = "\n\nFellow jurors have said:\n" + "\n".join(
            f"  - {s}" for s in prior_statements[-8:]
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
                f"Then on a new line, clearly state your vote as: Vote: Guilty / Not Guilty / Liable / Not Liable / Undecided"
            ))
        ])
        raw = resp.content.strip()
        return _parse_juror_vote(raw)
    except Exception as e:
        logger.error(f"[Juror {juror_profile.get('juror_id')} call error] {e}", exc_info=True)
        return "Based on the admitted evidence, I am deliberating carefully.", "Undecided"


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
                "jury_profiles": snapshot.get("positions", []),
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
                    "model": random.choice(_JUROR_MODEL_POOL),
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

        prior_statements: list[str] = []
        juror_votes: dict[int, str] = {}
        juror_positions: list[dict] = []

        prev_positions = prev_snapshot.get("positions", [])
        for pp in prev_positions:
            prior_statements.append(f"{pp.get('name', 'Juror')}: {pp.get('quote', '')} [Vote: {pp.get('stance', 'Undecided')}]")

        for i, profile in enumerate(profiles):
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

        all_votes = list(juror_votes.values())
        guilty_count = sum(1 for v in all_votes if v in ["Guilty", "Liable"])
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

        reached_verdict = final_verdict != "Hung"
        if rounds >= 3 and final_verdict == "Hung":
            if guilty_count > not_guilty_count:
                final_verdict = "Guilty" if jx.get("case_type") == "Criminal" else "Liable"
                reached_verdict = True
            elif not_guilty_count > guilty_count:
                final_verdict = "Not Guilty" if jx.get("case_type") == "Criminal" else "Not Liable"
                reached_verdict = True
            else:
                final_verdict = "Hung"

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
        logger.error(f"Jury Deliberation Error: {e}", exc_info=True)
        fallback_msg = AIMessage(content=f"[Jury deliberation error: {e}]", name="System")
        return {
            "deliberation_rounds": rounds,
            "transcript": transcript + [fallback_msg],
        }


# ── Shadow Jury ───────────────────────────────────────────────────────────────

async def async_shadow_jury(jury_id: int, case_facts: str, admitted: list, legal_standard: str, model: str):
    """Async single shadow jury evaluation."""
    llm = get_structured_llm(JuryVerdict, temperature=0.4, model=model)
    try:
        res = await llm.ainvoke([
            SystemMessage(content=(
                f"You are an independent shadow juror in a {legal_standard} case. "
                f"Apply the standard '{legal_standard}' to the admitted evidence only. "
                f"Cite specific evidence items by name in your rationale. "
                f"Provide a clear rationale and return your verdict as a json object."
            )),
            HumanMessage(content=(
                f"Admitted evidence:\n{admitted}\n\n"
                f"Case summary:\n{case_facts}\n\n"
                f"Return your verdict as a JSON object."
            ))
        ])
        return {"vote": res.verdict, "rationale": res.rationale, "id": jury_id}
    except Exception as e:
        logger.error(f"Shadow Jury {jury_id} Error: {e}", exc_info=True)
        return {"vote": "Hung", "rationale": "I could not reach a decision.", "id": jury_id}


def shadow_jury_node(state: TrialState) -> dict:
    """Spawns N independent shadow juries to estimate verdict probability."""
    logger.info("--- SHADOW JURIES ---")
    jx = _get_jx(state)
    jury_count    = state.get("shadow_jury_count", 20)
    case_facts    = state.get("fact_sheet", state.get("case_description", ""))
    admitted      = state.get("admitted_evidence", [])
    legal_standard = jx["legal_standard"]

    import asyncio as _asyncio

    async def run_all():
        chunk_size = 5
        results = []
        for i in range(0, jury_count, chunk_size):
            chunk = range(i, min(i + chunk_size, jury_count))
            tasks = [
                async_shadow_jury(j, case_facts, admitted, legal_standard, random.choice(_JUROR_MODEL_POOL))
                for j in chunk
            ]
            results.extend(await _asyncio.gather(*tasks))
            await _asyncio.sleep(1)
        return results

    all_verdicts = _asyncio.run(run_all())
    burden_met_votes = sum(1 for v in all_verdicts if v["vote"] in ["Guilty", "Liable"])
    burden_not_met_votes = sum(1 for v in all_verdicts if v["vote"] in ["Not Guilty", "Not Liable"])
    hung_votes = sum(1 for v in all_verdicts if v["vote"] == "Hung")
    win_prob = burden_met_votes / jury_count if jury_count > 0 else 0.0

    narrative = []
    show_count = jury_count
    for v in all_verdicts[:show_count]:
        narrative.append({
            "name": f"Shadow Juror {v['id'] + 1}",
            "content": f"{v['rationale']} [Vote: {v['vote']}]"
        })

    return {"shadow_jury_results": {
        "win_probability": win_prob,
        "burden_met_votes": burden_met_votes,
        "burden_not_met_votes": burden_not_met_votes,
        "hung_votes": hung_votes,
        "total_juries": jury_count,
        "narrative": narrative
    }}


# ── Rebuttal Evidence ──────────────────────────────────────────────────────────

def rebuttal_evidence_node(state: TrialState) -> dict:
    """Prosecution rebuttal → defence surrebuttal after all witnesses."""
    logger.info("--- REBUTTAL EVIDENCE ---")
    jx    = _get_jx(state)
    facts = state.get("case_description", "")
    transcript = []
    if not _has_actionable_case_facts(facts):
        return _insufficient_record_evidence(jx)

    try:
        pros_llm  = get_llm(temperature=0.6, model=AGENT_MODELS["Prosecutor"])
        def_llm   = get_llm(temperature=0.6, model=AGENT_MODELS["Defense Counsel"])
        judge_llm = get_structured_llm(JudgeRuling, temperature=0.1, model=AGENT_MODELS["Judge"])
    except Exception as e:
        logger.error("Rebuttal LLM init error: %s", e, exc_info=True)
        return {"transcript": [AIMessage(content=f"[Rebuttal Error: LLM init failed — {e}]", name="System")]}

    try:
        # Round 1: Prosecution rebuttal
        pros_rebut = pros_llm.invoke([
            SystemMessage(content=p.prosecutor_prompt(jx)),
            HumanMessage(content=(
                f"Present ONE rebuttal exhibit in 40 words or fewer. Name it and state why it rebuts "
                f"the defence's case. Ground it in the case facts.\nCase facts:\n{facts}"
            ))
        ])
        transcript.append(AIMessage(content=pros_rebut.content, name="Prosecutor"))

        def_obj = def_llm.invoke([
            SystemMessage(content=p.defense_prompt(jx)),
            HumanMessage(content=(
                f"Prosecution rebuttal:\n\"{pros_rebut.content}\"\n\n"
                f"Object in 30 words or fewer. Cite the specific rule from {jx['evidence_rules']}."
            ))
        ])
        transcript.append(AIMessage(content=def_obj.content, name="Defense Counsel"))

        ruling1 = judge_llm.invoke([
            SystemMessage(content=p.judge_prompt(jx)),
            HumanMessage(content=(
                f"Prosecution rebuttal: {pros_rebut.content}\n"
                f"Defence objects: {def_obj.content}\n\n"
                f"Rule on the objection under {jx['evidence_rules']}.\n"
                f"Return JSON with two keys: \"ruling\" (either 'SUSTAINED' or 'OVERRULED') "
                f"and \"rationale\" (your legal basis citing the specific rule)."
            ))
        ])
        ruling1_text = f"The objection is {ruling1.ruling}." + (f" {_strip_ruling_preamble(ruling1.rationale, ruling1.ruling)}" if ruling1.rationale else "")
        transcript.append(AIMessage(content=ruling1_text, name="Judge"))

        # Round 2: Defence surrebuttal
        def_sur = def_llm.invoke([
            SystemMessage(content=p.defense_prompt(jx)),
            HumanMessage(content=(
                f"Present ONE surrebuttal exhibit in 40 words or fewer. Name it and state why it "
                f"responds to the prosecution's rebuttal. Ground it in the case facts.\nCase facts:\n{facts}"
            ))
        ])
        transcript.append(AIMessage(content=def_sur.content, name="Defense Counsel"))

        pros_obj = pros_llm.invoke([
            SystemMessage(content=p.prosecutor_prompt(jx)),
            HumanMessage(content=(
                f"Defence surrebuttal:\n\"{def_sur.content}\"\n\n"
                f"Object in 30 words or fewer. Cite the specific rule from {jx['evidence_rules']}."
            ))
        ])
        transcript.append(AIMessage(content=pros_obj.content, name="Prosecutor"))

        ruling2 = judge_llm.invoke([
            SystemMessage(content=p.judge_prompt(jx)),
            HumanMessage(content=(
                f"Defence surrebuttal: {def_sur.content}\n"
                f"Prosecution objects: {pros_obj.content}\n\n"
                f"Rule on the objection under {jx['evidence_rules']}.\n"
                f"Return JSON with two keys: \"ruling\" (either 'SUSTAINED' or 'OVERRULED') "
                f"and \"rationale\" (your legal basis citing the specific rule)."
            ))
        ])
        ruling2_text = f"The objection is {ruling2.ruling}." + (f" {_strip_ruling_preamble(ruling2.rationale, ruling2.ruling)}" if ruling2.rationale else "")
        transcript.append(AIMessage(content=ruling2_text, name="Judge"))
    except Exception as e:
        logger.error("Rebuttal evidence processing error: %s", e, exc_info=True)
        transcript.append(AIMessage(content=f"[Rebuttal Error: {e}]", name="System"))

    updated_state = {**state, "transcript": state.get("transcript", []) + transcript}
    clerk_update = _clerk_compression(updated_state)
    return {"transcript": transcript, "rebuttal_rounds": 1, **clerk_update}


# ── Sentencing ─────────────────────────────────────────────────────────────────

def sentencing_node(state: TrialState) -> dict:
    """Runs after a Guilty/Liable verdict. Prosecution argues aggravation,
    defence argues mitigation, and the Judge pronounces sentence."""
    verdict = state.get("main_verdict")
    if verdict not in ("Guilty", "Liable"):
        logger.info("--- SENTENCING SKIPPED (no guilty/liable verdict) ---")
        return {"transcript": []}

    logger.info("--- SENTENCING ---")
    jx = _get_jx(state)
    fact_sheet = state.get("fact_sheet", state.get("case_description", ""))
    admitted   = state.get("admitted_evidence", [])
    transcript = []

    try:
        pros_llm = get_llm(temperature=0.7, model=AGENT_MODELS["Prosecutor"])
        def_llm  = get_llm(temperature=0.7, model=AGENT_MODELS["Defense Counsel"])
        judge_llm = get_structured_llm(SentencingDecision, temperature=0.1, model=AGENT_MODELS["Judge"])

        pros_msg = pros_llm.invoke([
            SystemMessage(content=p.prosecutor_sentencing_prompt(jx)),
            HumanMessage(content=(
                f"Argue for the maximum sentence in 60 words or fewer.\n\n"
                f"Admitted evidence:\n{admitted}\n\n"
                f"Case summary:\n{fact_sheet}\n\n"
                f"Verdict: {verdict}"
            ))
        ])
        transcript.append(AIMessage(content=pros_msg.content, name="Prosecutor"))

        def_msg = def_llm.invoke([
            SystemMessage(content=p.defense_sentencing_prompt(jx)),
            HumanMessage(content=(
                f"Argue for the minimum sentence in 60 words or fewer.\n\n"
                f"Admitted evidence:\n{admitted}\n\n"
                f"Case summary:\n{fact_sheet}\n\n"
                f"Verdict: {verdict}\n\n"
                f"Prosecution argued:\n\"{pros_msg.content}\""
            ))
        ])
        transcript.append(AIMessage(content=def_msg.content, name="Defense Counsel"))

        result = judge_llm.invoke([
            SystemMessage(content=p.judge_sentencing_prompt(jx)),
            HumanMessage(content=(
                f"Prosecution aggravation: {pros_msg.content}\n\n"
                f"Defence mitigation: {def_msg.content}\n\n"
                f"Pronounce sentence. Return JSON with \"sentence\", \"rationale\", and \"term\"."
            ))
        ])
        sentence_text = result.sentence
        if result.term:
            sentence_text += f"\n\n{result.term}"
        transcript.append(AIMessage(content=sentence_text, name="Judge"))

        return {"transcript": transcript, "sentence": _pydantic_to_dict(result)}
    except Exception as e:
        logger.error(f"Sentencing Error: {e}", exc_info=True)
        return {"transcript": [
            AIMessage(content=f"[Sentencing could not be completed: {e}]", name="System"),
        ]}


# ── Court Reporter ─────────────────────────────────────────────────────────────

def reporter_node(state: TrialState) -> dict:
    """Produces a structured trial log from the complete transcript."""
    logger.info("--- COURT REPORTER ---")
    jx = _get_jx(state)
    transcript_text = "\n".join(
        [_format_transcript_msg(m) for m in state.get("transcript", [])]
    )
    if not transcript_text.strip():
        return {"trial_log": {}}

    try:
        reporter_llm = get_structured_llm(TrialLogOutput, temperature=0.1, model=AGENT_MODELS["Clerk"])
        result = reporter_llm.invoke([
            SystemMessage(content=p.reporter_prompt(jx)),
            HumanMessage(content=(
                f"Case Facts:\n{state.get('case_description', '')}\n\n"
                f"Admitted Evidence:\n{state.get('admitted_evidence', [])}\n"
                f"Excluded Evidence:\n{state.get('excluded_evidence', [])}\n"
                f"Witnesses Called:\n{state.get('witness_queue', [])}\n"
                f"Expert Witnesses:\n{state.get('expert_witnesses', [])}\n"
                f"Verdict:\n{state.get('main_verdict', 'Not yet reached')}\n\n"
                f"Full Transcript:\n{transcript_text[:8000]}"
            ))
        ])
        trial_log = _pydantic_to_dict(result)
        return {"trial_log": trial_log, "transcript": [
            AIMessage(content="Trial log compiled by the Court Reporter.", name="Court Reporter"),
        ]}
    except Exception as e:
        logger.error(f"Reporter Error: {e}", exc_info=True)
        return {"trial_log": {}, "transcript": [
            AIMessage(content=f"[Reporter could not compile the log: {e}]", name="System"),
        ]}


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
        return {"transcript": [
            AIMessage(content=f"[Archivist could not produce the record: {e}]", name="System"),
        ]}
