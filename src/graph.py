from langgraph.graph import StateGraph, END
from typing import Literal

from src.state import TrialState
from src.nodes import (
    security_check_node,
    magistrate_node,
    discovery_node,
    human_input_node,
    motion_practice_node,
    opening_statements_node,
    evidence_node,
    witness_node,
    rebuttal_evidence_node,
    closing_arguments_node,
    jury_instructions_node,
    jury_deliberation_node,
    shadow_jury_node,
    sentencing_node,
    reporter_node,
    archivist_node
)

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
workflow.add_node("witness_examination", witness_node)
workflow.add_node("rebuttal_evidence", rebuttal_evidence_node)
workflow.add_node("closing_arguments", closing_arguments_node)
workflow.add_node("jury_instructions", jury_instructions_node)
workflow.add_node("jury_deliberation", jury_deliberation_node)
workflow.add_node("shadow_jury", shadow_jury_node)
workflow.add_node("sentencing", sentencing_node)
workflow.add_node("reporter", reporter_node)
workflow.add_node("archivist", archivist_node)

# Add Conditional Edge Logic

def check_security(state: TrialState) -> Literal["magistrate", "archivist"]:
    if state.get("errors"):
        # If any errors exist, jump to end (security breach or fatal failure)
        return "archivist"
    return "magistrate"


def check_more_witnesses(state: TrialState) -> Literal["witness_examination", "rebuttal_evidence"]:
    if len(state.get("witness_queue", [])) > 0:
        return "witness_examination"
    return "rebuttal_evidence"

def check_closing(state: TrialState) -> Literal["jury_instructions", "shadow_jury"]:
    if state.get("main_verdict"):
        return "shadow_jury"
    return "jury_instructions"

def check_verdict(state: TrialState) -> Literal["jury_deliberation", "shadow_jury"]:
    if state.get("main_verdict") or state.get("deliberation_rounds", 0) >= 3:
        return "shadow_jury"
    return "jury_deliberation"

def check_sentencing(state: TrialState) -> Literal["sentencing", "reporter"]:
    if state.get("main_verdict") in ("Guilty", "Liable"):
        return "sentencing"
    return "reporter"

# Add Edges
workflow.set_entry_point("security_check")

workflow.add_conditional_edges(
    "security_check",
    check_security,
    {
        "magistrate": "magistrate",
        "archivist": "archivist"
    }
)

workflow.add_edge("magistrate", "discovery")
workflow.add_edge("discovery", "human_input")
workflow.add_edge("human_input", "motions")
workflow.add_edge("motions", "opening_statements")
workflow.add_edge("opening_statements", "evidence")
workflow.add_edge("evidence", "witness_examination")

# Witness Loop → Rebuttal Evidence
workflow.add_conditional_edges(
    "witness_examination",
    check_more_witnesses,
    {
        "witness_examination": "witness_examination",
        "rebuttal_evidence": "rebuttal_evidence"
    }
)

workflow.add_edge("rebuttal_evidence", "closing_arguments")

workflow.add_conditional_edges(
    "closing_arguments",
    check_closing,
    {
        "jury_instructions": "jury_instructions",
        "shadow_jury": "shadow_jury"
    }
)

workflow.add_edge("jury_instructions", "jury_deliberation")

# Jury Deliberation Loop
workflow.add_conditional_edges(
    "jury_deliberation",
    check_verdict,
    {
        "jury_deliberation": "jury_deliberation",
        "shadow_jury": "shadow_jury"
    }
)

workflow.add_conditional_edges(
    "shadow_jury",
    check_sentencing,
    {
        "sentencing": "sentencing",
        "reporter": "reporter"
    }
)
workflow.add_edge("sentencing", "reporter")
workflow.add_edge("reporter", "archivist")
workflow.add_edge("archivist", END)

# Compile the graph
app = workflow.compile()
