"""
src/nodes.py — Compatibility re-export shim.

All node functions have been split into domain modules:
  - src/schemas.py       Pydantic models
  - src/trial_phases.py  Trial flow phases (security, magistrate, discovery, motions,
                         opening, closing, reporter, archivist)
  - src/evidence.py      Evidence presentation, objections, rebuttal
  - src/witness.py       Witness examination (direct, cross, redirect)
  - src/jury.py          Jury profiles, deliberation, shadow jury, sentencing

This file re-exports everything for backward compatibility.
"""

from src.evidence import (
    _argue_hearsay_exception,
    _issue_structured_objection,
    _judge_rule_on_objection,
    _no_objection_counter,
    _no_objection_lock,
    evidence_node,
    rebuttal_evidence_node,
)
from src.jury import (
    _JUROR_MODEL_POOL,
    _call_single_juror,
    _parse_juror_vote,
    generate_dynamic_jury_profiles,
    jury_deliberation_node,
    jury_instructions_node,
    sentencing_node,
    shadow_jury_node,
)
from src.schemas import (
    ClerkOutput,
    DeliberationOutput,
    DiscoveryItems,
    EvidenceObjectionDecision,
    ExaminationObjection,
    ExpertQualRuling,
    JudgeRuling,
    JurorPosition,
    JurorProfile,
    JuryPanelOutput,
    JuryVerdict,
    MagistrateOutput,
    MotionFiling,
    MotionOpposition,
    MotionRulingResult,
    ObjectionOutput,
    SentencingDecision,
    TrialLogOutput,
    _pydantic_to_dict,
)
from src.trial_phases import (
    _clerk_compression,
    _extract_evidence_fallback,
    _extract_witnesses_fallback,
    _format_transcript_msg,
    _get_jx,
    _has_actionable_case_facts,
    _insufficient_record_evidence,
    _insufficient_record_opening,
    _strip_ruling_preamble,
    archivist_node,
    closing_arguments_node,
    discovery_node,
    human_input_node,
    magistrate_node,
    motion_practice_node,
    opening_statements_node,
    reporter_node,
    security_check_node,
)
from src.witness import (
    _ask_with_objection_gate,
    _examination_loop,
    _extract_witness_context,
    _is_defendant_witness,
    _is_expert_candidate,
    _parse_json_robustly,
    _qualify_expert,
    witness_cross,
    witness_direct,
    witness_redirect,
)

__all__ = [
    # schemas
    "_pydantic_to_dict",
    "MagistrateOutput",
    "ClerkOutput",
    "JudgeRuling",
    "ObjectionOutput",
    "ExaminationObjection",
    "EvidenceObjectionDecision",
    "JuryVerdict",
    "JurorProfile",
    "JuryPanelOutput",
    "JurorPosition",
    "DeliberationOutput",
    "SentencingDecision",
    "DiscoveryItems",
    "MotionFiling",
    "MotionOpposition",
    "MotionRulingResult",
    "TrialLogOutput",
    "ExpertQualRuling",
    # trial_phases
    "_strip_ruling_preamble",
    "_has_actionable_case_facts",
    "_insufficient_record_opening",
    "_insufficient_record_evidence",
    "_get_jx",
    "security_check_node",
    "_extract_evidence_fallback",
    "_extract_witnesses_fallback",
    "magistrate_node",
    "human_input_node",
    "_format_transcript_msg",
    "_clerk_compression",
    "opening_statements_node",
    "discovery_node",
    "motion_practice_node",
    "closing_arguments_node",
    "reporter_node",
    "archivist_node",
    # evidence
    "_no_objection_lock",
    "_no_objection_counter",
    "_issue_structured_objection",
    "_argue_hearsay_exception",
    "_judge_rule_on_objection",
    "evidence_node",
    "rebuttal_evidence_node",
    # witness
    "_is_expert_candidate",
    "_qualify_expert",
    "_parse_json_robustly",
    "_ask_with_objection_gate",
    "_examination_loop",
    "_is_defendant_witness",
    "_extract_witness_context",
    "witness_direct",
    "witness_cross",
    "witness_redirect",
    # jury
    "_JUROR_MODEL_POOL",
    "generate_dynamic_jury_profiles",
    "jury_instructions_node",
    "_parse_juror_vote",
    "_call_single_juror",
    "jury_deliberation_node",
    "shadow_jury_node",
    "sentencing_node",
]
