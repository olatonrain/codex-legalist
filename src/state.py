from typing import TypedDict, List, Dict, Any, Optional
from langchain_core.messages import BaseMessage

class TrialState(TypedDict):
    # ── Core Data ─────────────────────────────────────────────────
    case_description: str
    transcript: List[BaseMessage]

    # ── Jurisdiction ──────────────────────────────────────────────
    country: str                  # e.g. "Nigeria"
    jurisdiction_system: str      # e.g. "Common Law"
    jurisdiction_procedure: str   # "adversarial" or "inquisitorial"
    criminal_standard: str        # e.g. "Beyond reasonable doubt"
    civil_standard: str           # e.g. "Balance of probabilities"
    evidence_rules: str           # e.g. "Evidence Act 2011; ACJA 2015"
    jury_enabled: bool            # True = jury trial; False = bench/panel
    cross_examination: bool       # True = adversarial cross; False = judge-led
    court_address: str            # How to address the Judge
    case_type: str                # "Criminal" or "Civil" — set by user

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
    current_witness: Optional[str]
    examination_phase: Optional[str]   # 'direct', 'cross', or 'redirect'

    # ── Configurations ────────────────────────────────────────────
    shadow_jury_count: int
    shadow_jury_model: str
    jury_count: int            # Main jury panel size (default 12, set at setup)
    audio_enabled: bool

    # ── Outcomes ──────────────────────────────────────────────────
    deliberation_rounds: int
    jury_profiles: List[Dict[str, Any]]
    deliberation_snapshot: Dict[str, Any]
    main_verdict: Optional[str]
    shadow_jury_results: Dict[str, Any]

    # ── Evidence ──────────────────────────────────────────────────
    multimodal_evidence: list

    # ── Error Handling ────────────────────────────────────────────
    errors: List[str]
