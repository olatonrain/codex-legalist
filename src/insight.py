"""
src/insight.py
──────────────
Post-trial counsel insight generation.

Extracts a truncated trial context from the full TrialState and calls the LLM
with perspective-specific prompts (defense, prosecution, judge) at low temperature
for consistent, fact-grounded advice.
"""

import hashlib
import json as _json

import src.prompts as p
from src.config import AGENT_MODELS
from src.llm import get_structured_llm
from src.logger import get_logger
from src.schemas import CounselInsight
from src.trial_phases import _get_jx

logger = get_logger(__name__)

_INSIGHT_TEMPERATURE = 0.35

_PERSPECTIVE_PROMPTS = {
    "defense": p.defense_counsel_insight_prompt,
    "prosecution": p.prosecution_counsel_insight_prompt,
    "judge": p.judge_counsel_insight_prompt,
}


def extract_trial_context(state: dict) -> dict:
    """Extract a truncated, LLM-ready context dict from a full TrialState.

    Caps each field to keep token usage reasonable for 3 parallel calls.
    """
    case_desc = (state.get("case_description") or "")[:3000]

    admitted = state.get("admitted_evidence") or []
    excluded = state.get("excluded_evidence") or []

    trial_log = state.get("trial_log") or {}
    closing_arguments = trial_log.get("closing_arguments", "")
    if isinstance(closing_arguments, list):
        closing_arguments = "\n".join(closing_arguments)
    closing_arguments = str(closing_arguments)[:2000]

    deliberation = state.get("deliberation_snapshot") or {}
    rationale = deliberation.get("rationale") or ""
    if not rationale:
        sjr = state.get("shadow_jury_results") or {}
        narrative = sjr.get("narrative") or []
        if narrative:
            rationale = narrative[-1].get("content", "") if isinstance(narrative[-1], dict) else str(narrative[-1])
    rationale = str(rationale)[:1000]

    verdict = state.get("main_verdict") or "No Verdict Reached"

    return {
        "case_description": case_desc,
        "admitted_evidence": admitted[-10:],
        "excluded_evidence": excluded[-5:],
        "closing_arguments": closing_arguments,
        "verdict": verdict,
        "deliberation_rationale": rationale,
    }


def _compute_cache_key(state: dict, perspective: str) -> str:
    """Deterministic cache key from case facts + evidence + perspective."""
    raw = (
        (state.get("case_description") or "")[:200]
        + "|"
        + _json.dumps((state.get("admitted_evidence") or [])[-5:], sort_keys=True)
        + "|"
        + (state.get("main_verdict") or "")
        + "|"
        + perspective
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def generate_one(state: dict, perspective: str) -> CounselInsight | dict:
    """Generate counsel insight for a single perspective.

    Returns a CounselInsight on success, or a dict with 'error' on failure.
    """
    if perspective not in _PERSPECTIVE_PROMPTS:
        return {"error": f"Unknown perspective: {perspective}"}

    ctx = extract_trial_context(state)
    jx = _get_jx(state)
    prompt_fn = _PERSPECTIVE_PROMPTS[perspective]
    prompt = prompt_fn(ctx, jx)

    try:
        llm = get_structured_llm(
            CounselInsight,
            temperature=_INSIGHT_TEMPERATURE,
            model=AGENT_MODELS.get("Jury Foreperson", "qwen-plus-latest"),
        )
        result = llm.invoke([("human", prompt)])
        return result
    except Exception as exc:
        logger.error("[insight] %s generation failed: %s", perspective, exc, exc_info=True)
        return {"error": str(exc)}


def generate_all(state: dict, perspectives: list[str]) -> dict[str, CounselInsight | dict]:
    """Generate insights for multiple perspectives.

    Each perspective runs independently with its own try/except so a single
    failure doesn't block the other perspectives.
    """
    results: dict[str, CounselInsight | dict] = {}
    for p_name in perspectives:
        results[p_name] = generate_one(state, p_name)
    return results
