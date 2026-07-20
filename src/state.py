"""Trial state schema — TypedDict defining the LangGraph state graph shape."""
from typing import Any, Dict, List, Optional, TypedDict

from langchain_core.messages import BaseMessage


def create_initial_state(
    case_description: str = "",
    country: str = "Nigeria",
    jurisdiction_system: str = "Common Law",
    jurisdiction_procedure: str = "adversarial",
    criminal_standard: str = "Beyond reasonable doubt",
    civil_standard: str = "Balance of probabilities",
    evidence_rules: str = "Evidence Act 2011; Administration of Criminal Justice Act 2015 (ACJA)",
    jury_enabled: bool = False,
    cross_examination: bool = True,
    court_address: str = "My Lord / Your Lordship",
    case_type: str = "Criminal",
    shadow_jury_count: int = 20,
    jury_count: int = 12,
    **overrides,
) -> dict:
    """Build a fresh TrialState dict with defaults for a new trial.

    Args:
        case_description: Plain-text facts describing the case.
        country: Jurisdiction country name.
        case_type: "Criminal" or "Civil".
        shadow_jury_count: Number of shadow juries to run (5-50).
        jury_count: Number of main-jury panelists (6-15).
        **overrides: Any additional state keys to set.

    Returns:
        A TrialState-compatible dict ready for the LangGraph.
    """
    state = {
        "case_description": case_description,
        "transcript": [],
        "fact_sheet": "",
        "admitted_evidence": [],
        "excluded_evidence": [],
        "clarifying_questions": [],
        "human_answers": {},
        "missing_evidence_answers": {},
        "missing_witnesses_answers": {},
        "pending_human_question": None,
        "human_input_buffer": [],
        "witness_queue": [],
        "declined_witnesses": [],
        "current_witness": None,
        "examination_phase": None,
        "witness_direct_qa": [],
        "shadow_jury_count": shadow_jury_count,
        "shadow_jury_model": "qwen-plus-latest",
        "jury_count": jury_count,
        "audio_enabled": False,
        "deliberation_rounds": 0,
        "jury_profiles": [],
        "deliberation_snapshot": {},
        "main_verdict": None,
        "shadow_jury_results": {},
        "errors": [],
        "sentence": None,
        "rebuttal_rounds": 0,
        "objection_history": [],
        "impeachment_attempts": [],
        "expert_witnesses": [],
        "motion_rulings": [],
        "disclosed_prosecution": [],
        "disclosed_defense": [],
        "trial_log": {},
        "country": country,
        "jurisdiction_system": jurisdiction_system,
        "jurisdiction_procedure": jurisdiction_procedure,
        "criminal_standard": criminal_standard,
        "civil_standard": civil_standard,
        "evidence_rules": evidence_rules,
        "jury_enabled": jury_enabled,
        "cross_examination": cross_examination,
        "court_address": court_address,
        "case_type": case_type,
    "multimodal_evidence": [],  # list of base64 data URIs (uploaded evidence images)
    }
    state.update(overrides)
    return state


class TrialState(TypedDict):
    # ── Core Data ─────────────────────────────────────────────────
    case_description: str
    transcript: List[BaseMessage]

    # ── Jurisdiction ──────────────────────────────────────────────
    country: str  # e.g. "Nigeria"
    jurisdiction_system: str  # e.g. "Common Law"
    jurisdiction_procedure: str  # "adversarial" or "inquisitorial"
    criminal_standard: str  # e.g. "Beyond reasonable doubt"
    civil_standard: str  # e.g. "Balance of probabilities"
    evidence_rules: str  # e.g. "Evidence Act 2011; ACJA 2015"
    jury_enabled: bool  # True = jury trial; False = bench/panel
    cross_examination: bool  # True = adversarial cross; False = judge-led
    court_address: str  # How to address the Judge
    case_type: str  # "Criminal" or "Civil" — set by user

    # ── State Compression (Clerk's Domain) ───────────────────────
    fact_sheet: str
    admitted_evidence: List[str]
    excluded_evidence: List[str]

    # ── Pre-trial ─────────────────────────────────────────────────
    clarifying_questions: List[Dict[str, str]]
    human_answers: Dict[str, str]
    missing_evidence_answers: Dict[str, str]
    missing_witnesses_answers: Dict[str, str]

    # ── Live Human Input ──────────────────────────────────────────
    pending_human_question: Optional[Dict[str, str]]  # {agent, question, context}
    human_input_buffer: List[Dict[str, str]]  # History of human inputs during trial

    # ── Trial Tracking ────────────────────────────────────────────
    witness_queue: List[str]
    declined_witnesses: List[str]
    current_witness: Optional[str]
    examination_phase: Optional[str]  # 'direct', 'cross', or 'redirect'
    witness_direct_qa: List[Dict[str, str]]  # Q&A log from direct, passed to cross-examination
    rebuttal_rounds: int  # 0 or 1 — rebuttal runs once
    objection_history: List[Dict[str, Any]]  # log of objections and rulings
    impeachment_attempts: List[Dict[str, Any]]  # impeachment log per witness
    expert_witnesses: List[str]  # witnesses qualified as experts
    motion_rulings: List[Dict[str, Any]]  # pre-trial motion rulings
    disclosed_prosecution: List[str]  # prosecution's disclosed evidence
    disclosed_defense: List[str]  # defence's disclosed evidence
    trial_log: Dict[str, Any]  # court reporter's structured trial log

    # ── Configurations ────────────────────────────────────────────
    shadow_jury_count: int
    shadow_jury_model: str
    jury_count: int  # Main jury panel size (default 12, set at setup)
    audio_enabled: bool

    # ── Outcomes ──────────────────────────────────────────────────
    deliberation_rounds: int
    jury_profiles: List[Dict[str, Any]]
    deliberation_snapshot: Dict[str, Any]
    main_verdict: Optional[str]
    shadow_jury_results: Dict[str, Any]
    sentence: Optional[str]  # Judge's sentence after Guilty/Liable verdict

    # ── Image Evidence ────────────────────────────────────────────
    multimodal_evidence: List[str]  # base64 data URIs of uploaded evidence images

    # ── Error Handling ────────────────────────────────────────────
    errors: List[str]
