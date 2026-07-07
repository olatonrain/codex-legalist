"""
legalis/agents.py
─────────────────
Orchestrates AI agent calls for live trials.

Responsibilities:
  - generate_dramatic_opening(): prompts the AI to write jurisdiction-aware
    courtroom opening formalities (All rise, readiness check, etc.)
  - run_trial_step(): calls the appropriate src.nodes function for each
    phase of the trial and returns serialisable transcript entries.
  - norm_agent() / sanitise_content(): shared helpers used by the server.
"""
from __future__ import annotations

import json as _json
import re as _re
from typing import Any

from src.llm import get_llm
from src.config import AGENT_MODELS
from src.logger import get_logger

logger = get_logger(__name__)


# ── Agent normalisation helpers ───────────────────────────────────────────────

def norm_agent(name: str | None) -> str:
    """Map raw LLM agent names to canonical render keys."""
    if not name:
        return "System"
    if name.startswith("Juror"):
        return "Juror"
    if name == "Defense Counsel":
        return "Defense"
    return name


def sanitise_content(content: Any) -> str:
    """If the LLM returned raw JSON, convert it to readable prose."""
    if not isinstance(content, str):
        content = str(content)
    stripped = content.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            data = _json.loads(stripped)
            # Structured ruling / verdict
            if "ruling" in data and "rationale" in data:
                return f"The objection is {data['ruling']}. {data.get('rationale', '')}".strip()
            if "verdict" in data and "rationale" in data:
                return f"Verdict: {data['verdict']}. {data.get('rationale', '')}".strip()
            # Agent speech — prefer explicit text/content/statement keys
            for key in ("statement", "speech", "text", "content", "dialogue", "argument", "response"):
                if key in data and isinstance(data[key], str) and data[key].strip():
                    return data[key].strip()
            # Fallback: join all non-empty string values in a readable way
            parts = [str(v) for v in data.values() if isinstance(v, str) and str(v).strip()]
            if parts:
                return " ".join(parts)
        except Exception:
            pass
    if stripped.startswith("[") and stripped.endswith("]"):
        try:
            entries = _json.loads(stripped)
            if isinstance(entries, list):
                parts = []
                for entry in entries:
                    if isinstance(entry, dict):
                        for key in ("text", "content", "statement", "speech"):
                            if key in entry and entry[key]:
                                parts.append(str(entry[key]).strip())
                                break
                    elif isinstance(entry, str):
                        parts.append(entry.strip())
                if parts:
                    return " | ".join(parts)
        except Exception:
            pass
    return (
        content
        .replace("**", "")
        .replace("*", "")
        .replace("—", "-")
        .replace("–", "-")
    )


# ── Dramatic Opening Generator ────────────────────────────────────────────────

_OPENING_PROMPT = """\
You are the Court Clerk / Bailiff for a formal {case_type} trial in {country} \
({system} system, {procedure} procedure).

Generate the authentic, dramatic courtroom opening sequence that happens \
BEFORE opening statements. Use the jurisdiction's exact terminology and \
judicial address forms.

Return ONLY a JSON array of objects. Each object has:
  "agent":  one of ["Bailiff", "Judge", "Prosecutor", "Defense"]
  "text":   what that person says (no stage directions, no markdown)

Rules:
- Bailiff calls the court to order and announces the judge by full title.
- Judge greets the court, names the case: "{case_title}", asks if both \
  sides are ready.
- Prosecutor confirms readiness using the correct address form for {country}.
- Defense confirms readiness using the correct address form for {country}.
- Judge invites the prosecution to proceed with opening statements.
- Use the exact judicial address: {address}
- 5–7 exchanges total. Be dramatic and formal.

Example format:
[
  {{"agent": "Bailiff", "text": "All rise..."}},
  {{"agent": "Judge",   "text": "You may be seated..."}}
]
"""


def generate_dramatic_opening(
    case_title: str,
    country: str,
    system: str,
    procedure: str,
    case_type: str,
    address: str,
) -> list[dict[str, str]]:
    """
    Call the Qwen LLM to produce jurisdiction-aware courtroom opening lines.
    Returns a list of {"agent": ..., "text": ...} dicts.
    Falls back to a static script if the LLM call fails.
    """
    prompt = _OPENING_PROMPT.format(
        case_title=case_title,
        country=country,
        system=system,
        procedure=procedure,
        case_type=case_type,
        address=address,
    )

    try:
        llm = get_llm(temperature=0.4, model=AGENT_MODELS.get("Judge", "qwen-max"))
        response = llm.invoke(prompt)
        raw = response.content if hasattr(response, "content") else str(response)

        # Strip markdown fences if present
        raw = raw.strip()
        fence_match = _re.match(r'^```(?:json)?\s*\n(.*?)\n```', raw, _re.DOTALL)
        if fence_match:
            raw = fence_match.group(1).strip()

        entries = _json.loads(raw)
        if isinstance(entries, list) and entries:
            return entries

    except Exception as exc:
        logger.error(f"[generate_dramatic_opening] LLM failed: {exc} — using fallback", exc_info=True)

    # ── Static fallback ──────────────────────────────────────────────────────
    return [
        {"agent": "Bailiff",    "text": f"All rise. The Honorable Justice presiding. This court is now in session for {case_title}."},
        {"agent": "Judge",      "text": f"You may be seated. Are the prosecution and defense ready to proceed with opening statements in the matter of {case_title}?"},
        {"agent": "Prosecutor", "text": f"Ready, {address}."},
        {"agent": "Defense",    "text": f"The defense is ready, {address}."},
        {"agent": "Judge",      "text": "Prosecution, you may begin your opening statement."},
    ]


# ── Live Trial Step Runner ────────────────────────────────────────────────────

_LIVE_STEPS = [
    "discovery", "motions", "opening", "evidence",
    "witness_direct", "witness_cross", "witness_redirect",
    "rebuttal", "closing", "jury_instructions", "jury_deliberation",
    "shadow_jury", "sentencing", "reporter",
]

_STEP_LABELS = {
    "discovery":         "Discovery Disclosure",
    "motions":           "Pre-Trial Motions",
    "opening":           "Opening Statements",
    "evidence":          "Evidence Presentation",
    "witness_direct":    "Witness Direct Examination",
    "witness_cross":     "Witness Cross-Examination",
    "witness_redirect":  "Witness Redirect & Impeachment",
    "rebuttal":          "Rebuttal Evidence",
    "closing":           "Closing Arguments",
    "jury_instructions": "Jury Instructions",
    "jury_deliberation": "Jury Deliberation",
    "shadow_jury":       "Shadow Jury Analysis",
    "sentencing":        "Sentencing Hearing",
    "reporter":          "Court Reporter Log",
}


def _bailiff_transition(next_step: str, graph_state: dict) -> str:
    """Generate a personalised Bailiff announcement for the next trial phase."""
    next_label = _STEP_LABELS.get(next_step, next_step)
    current_witness = graph_state.get("current_witness")
    wq = graph_state.get("witness_queue", [])
    next_witness = wq[0] if wq else None

    # Witness phases: include witness name
    if next_step == "witness_direct" and current_witness:
        return (
            f"The court will now proceed to the direct examination of {current_witness}. "
            f"Counsel, please proceed."
        )
    elif next_step == "witness_direct" and not current_witness and next_witness:
        return (
            f"The examination of the previous witness is complete. "
            f"The court will now call {next_witness} for direct examination."
        )
    elif next_step == "witness_cross" and current_witness:
        return (
            f"The court will now proceed to the cross-examination of {current_witness}. "
            f"Defence counsel, you may begin."
        )
    elif next_step == "witness_redirect" and current_witness:
        return (
            f"The court will now proceed to redirect and impeachment for {current_witness}. "
            f"Prosecution, you may proceed."
        )
    elif next_step == "evidence":
        admitted = graph_state.get("admitted_evidence", [])
        n = len(admitted)
        return (
            f"The court will now proceed to the presentation of evidence. "
            f"{n} item{'s' if n != 1 else ''} currently on record."
        )
    elif next_step == "done":
        return "All matters have been heard. The court will now adjourn."
    else:
        return f"The court will now proceed to the {next_label.lower()}."


def _phase_opening(live_step: str, graph_state: dict) -> str:
    """Generate a personalised opening line for the current phase."""
    phase_label = _STEP_LABELS.get(live_step, live_step)
    current_witness = graph_state.get("current_witness")

    if live_step == "witness_direct" and current_witness:
        return f"The court is now in session for the direct examination of {current_witness}."
    elif live_step == "witness_cross" and current_witness:
        return f"The court is now in session for the cross-examination of {current_witness}."
    elif live_step == "witness_redirect" and current_witness:
        return f"The court is now in session for the redirect examination of {current_witness}."
    elif live_step == "evidence":
        return (
            f"The court is now in session for evidence presentation. "
            f"Each side may tender exhibits in turn."
        )
    else:
        return f"The court is now in session for the {phase_label.lower()}."


def run_trial_step(live_step: str, graph_state: dict) -> tuple[list[dict], dict, str]:
    """
    Execute one phase of the live LLM-powered trial.

    Returns:
        messages   – list of {agent, text} dicts to send to the client
        graph_state – updated state dict
        next_step   – the key for the next phase, or "done"
    """
    from src.nodes import (
        discovery_node, motion_practice_node,
        opening_statements_node, evidence_node,
        witness_direct, witness_cross, witness_redirect,
        rebuttal_evidence_node, closing_arguments_node,
        jury_instructions_node, jury_deliberation_node,
        shadow_jury_node, sentencing_node, reporter_node,
    )

    node_map = {
        "discovery":         discovery_node,
        "motions":           motion_practice_node,
        "opening":           opening_statements_node,
        "evidence":          evidence_node,
        "witness_direct":    witness_direct,
        "witness_cross":     witness_cross,
        "witness_redirect":  witness_redirect,
        "rebuttal":          rebuttal_evidence_node,
        "closing":           closing_arguments_node,
        "jury_instructions": jury_instructions_node,
        "jury_deliberation": jury_deliberation_node,
        "shadow_jury":       shadow_jury_node,
        "sentencing":        sentencing_node,
        "reporter":          reporter_node,
    }

    node_fn = node_map.get(live_step)
    if node_fn is None:
        valid_steps = ", ".join(_LIVE_STEPS)
        raise ValueError(f"Unknown trial phase '{live_step}'. Expected one of: {valid_steps}.")

    try:
        result = node_fn(graph_state)
    except Exception as node_exc:
        error_text = f"[Phase error in {_STEP_LABELS.get(live_step, live_step)}] {node_exc}"
        logger.error(error_text, exc_info=True)
        phase_label = _STEP_LABELS.get(live_step, live_step)
        next_step = _next_step_after(live_step, graph_state)
        messages = [{"agent": "System", "text": error_text, "phase": phase_label}]

        transition = _bailiff_transition(next_step, graph_state)
        messages.append({"agent": "Bailiff", "text": transition, "phase": phase_label})
        if next_step == "done":
            messages.append({"agent": "Bailiff", "text": "This court is adjourned.", "phase": "done"})

        return messages, graph_state, next_step

    messages: list[dict] = []

    phase_label = _STEP_LABELS.get(live_step, live_step)

    messages.append({
        "agent": "Bailiff",
        "text": _phase_opening(live_step, graph_state),
        "phase": phase_label,
    })

    for key, val in result.items():
        if key == "transcript":
            graph_state["transcript"] = graph_state.get("transcript", []) + val
            for msg in val:
                if isinstance(msg, dict):
                    agent = norm_agent(msg.get("name") or msg.get("agent"))
                    text  = sanitise_content(msg.get("content") or msg.get("text", ""))
                else:
                    agent = norm_agent(getattr(msg, "name", None))
                    text  = sanitise_content(getattr(msg, "content", str(msg)))
                messages.append({
                    "agent": agent,
                    "text":  text,
                    "phase": phase_label,
                })
        else:
            graph_state[key] = val

    next_step = _next_step_after(live_step, graph_state)

    transition = _bailiff_transition(next_step, graph_state)
    messages.append({
        "agent": "Bailiff",
        "text": transition,
        "phase": phase_label,
    })
    if next_step == "done":
        messages.append({
            "agent": "Bailiff",
            "text": "This court is adjourned.",
            "phase": "done",
        })

    return messages, graph_state, next_step


def _next_step_after(live_step: str, graph_state: dict) -> str:
    """Pure routing: given the completed step, return the next phase key."""
    wq      = graph_state.get("witness_queue", [])
    rounds  = graph_state.get("deliberation_rounds", 0)
    verdict = graph_state.get("main_verdict")

    if live_step == "discovery":
        return "motions"
    elif live_step == "motions":
        return "opening"
    elif live_step == "opening":
        return "evidence"
    elif live_step == "evidence":
        return "witness_direct" if (wq or graph_state.get("current_witness")) else "rebuttal"
    elif live_step == "witness_direct":
        return "witness_cross"
    elif live_step == "witness_cross":
        return "witness_redirect"
    elif live_step == "witness_redirect":
        return "witness_direct" if wq else "rebuttal"
    elif live_step == "rebuttal":
        return "closing"
    elif live_step == "closing":
        return "shadow_jury" if verdict else "jury_instructions"
    elif live_step == "jury_instructions":
        return "jury_deliberation"
    elif live_step == "jury_deliberation":
        return "shadow_jury" if (verdict or rounds >= 3) else "jury_deliberation"
    elif live_step == "shadow_jury":
        return "sentencing" if verdict in ("Guilty", "Liable") else "reporter"
    elif live_step == "sentencing":
        return "reporter"
    elif live_step == "reporter":
        return "done"
    else:
        return "done"
