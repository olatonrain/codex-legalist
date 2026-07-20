"""LangGraph StateGraph construction — ties all trial phase nodes together."""
from typing import Literal

from langgraph.graph import END, StateGraph

from src.evidence import evidence_node, rebuttal_evidence_node
from src.jury import (
    jury_deliberation_node,
    jury_instructions_node,
    sentencing_node,
    shadow_jury_node,
)
from src.state import TrialState
from src.trial_phases import (
    archivist_node,
    closing_arguments_node,
    discovery_node,
    human_input_node,
    magistrate_node,
    motion_practice_node,
    no_case_node,
    opening_statements_node,
    reporter_node,
    security_check_node,
)
from src.witness import witness_cross, witness_direct, witness_redirect

# Initialize Graph
workflow = StateGraph(TrialState)

# Add Nodes
workflow.add_node("security_check", security_check_node)
workflow.add_node("magistrate", magistrate_node)
workflow.add_node("discovery", discovery_node)
workflow.add_node("human_input", human_input_node)
workflow.add_node("motions", motion_practice_node)
workflow.add_node("opening_statements", opening_statements_node)
workflow.add_node("evidence", evidence_node)
workflow.add_node("witness_direct", witness_direct)
workflow.add_node("witness_cross", witness_cross)
workflow.add_node("witness_redirect", witness_redirect)
workflow.add_node("rebuttal_evidence", rebuttal_evidence_node)
workflow.add_node("closing_arguments", closing_arguments_node)
workflow.add_node("no_case", no_case_node)
workflow.add_node("jury_instructions", jury_instructions_node)
workflow.add_node("jury_deliberation", jury_deliberation_node)
workflow.add_node("shadow_jury", shadow_jury_node)
workflow.add_node("sentencing", sentencing_node)
workflow.add_node("reporter", reporter_node)
workflow.add_node("archivist", archivist_node)

# Add Conditional Edge Logic


def check_security(state: TrialState) -> Literal["magistrate", "archivist"]:
    """Route to magistrate if security passes, archivist if errors exist."""
    if state.get("errors"):
        # If any errors exist, jump to end (security breach or fatal failure)
        return "archivist"
    return "magistrate"


def check_has_witnesses(state: TrialState) -> Literal["witness_direct", "rebuttal_evidence"]:
    """Route to witness examination if witnesses remain, else skip to rebuttal."""
    if len(state.get("witness_queue", [])) > 0 or state.get("current_witness"):
        return "witness_direct"
    return "rebuttal_evidence"


def check_closing(state: TrialState) -> Literal["no_case"]:
    """After closing arguments, always proceed to no-case submission."""
    return "no_case"


def check_no_case(state: TrialState) -> Literal["jury_instructions", "shadow_jury"]:
    """Route to jury instructions if no-case overruled, or shadow jury if acquitted."""
    if state.get("main_verdict"):
        return "shadow_jury"
    return "jury_instructions"


def check_verdict(state: TrialState) -> Literal["jury_deliberation", "shadow_jury"]:
    """Route back to deliberation if no verdict after 3+ rounds, or to shadow jury."""
    if state.get("main_verdict") or state.get("deliberation_rounds", 0) >= 3:
        return "shadow_jury"
    return "jury_deliberation"


def check_sentencing(state: TrialState) -> Literal["sentencing", "reporter"]:
    """Route to sentencing if guilty/liable, or skip to reporter if acquitted."""
    if state.get("main_verdict") in ("Guilty", "Liable"):
        return "sentencing"
    return "reporter"


# Add Edges
workflow.set_entry_point("security_check")

workflow.add_conditional_edges("security_check", check_security, {"magistrate": "magistrate", "archivist": "archivist"})

workflow.add_edge("magistrate", "discovery")
workflow.add_edge("discovery", "human_input")
workflow.add_edge("human_input", "motions")
workflow.add_edge("motions", "opening_statements")
workflow.add_edge("opening_statements", "evidence")

# Evidence conditional branch
workflow.add_conditional_edges(
    "evidence", check_has_witnesses, {"witness_direct": "witness_direct", "rebuttal_evidence": "rebuttal_evidence"}
)

# Witness Loop: Direct -> Cross -> Redirect -> Check more
workflow.add_edge("witness_direct", "witness_cross")
workflow.add_edge("witness_cross", "witness_redirect")
workflow.add_conditional_edges(
    "witness_redirect",
    check_has_witnesses,
    {"witness_direct": "witness_direct", "rebuttal_evidence": "rebuttal_evidence"},
)

workflow.add_edge("rebuttal_evidence", "closing_arguments")

workflow.add_conditional_edges(
    "closing_arguments", check_closing, {"no_case": "no_case"}
)

workflow.add_conditional_edges(
    "no_case", check_no_case, {"jury_instructions": "jury_instructions", "shadow_jury": "shadow_jury"}
)

workflow.add_edge("jury_instructions", "jury_deliberation")

# Jury Deliberation Loop
workflow.add_conditional_edges(
    "jury_deliberation", check_verdict, {"jury_deliberation": "jury_deliberation", "shadow_jury": "shadow_jury"}
)

workflow.add_conditional_edges("shadow_jury", check_sentencing, {"sentencing": "sentencing", "reporter": "reporter"})
workflow.add_edge("sentencing", "reporter")
workflow.add_edge("reporter", "archivist")
workflow.add_edge("archivist", END)

# Compile the graph
app = workflow.compile()
