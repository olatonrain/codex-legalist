from langgraph.graph import StateGraph, END
from typing import Literal

from src.state import TrialState
from src.nodes import (
    security_check_node,
    magistrate_node,
    human_input_node,
    opening_statements_node,
    evidence_node,
    witness_node,
    closing_arguments_node,
    jury_instructions_node,
    jury_deliberation_node,
    shadow_jury_node,
    archivist_node
)

# Initialize Graph
workflow = StateGraph(TrialState)

# Add Nodes
workflow.add_node("security_check", security_check_node)
workflow.add_node("magistrate", magistrate_node)
workflow.add_node("human_input", human_input_node)
workflow.add_node("opening_statements", opening_statements_node)
workflow.add_node("evidence", evidence_node)
workflow.add_node("witness_examination", witness_node)
workflow.add_node("closing_arguments", closing_arguments_node)
workflow.add_node("jury_instructions", jury_instructions_node)
workflow.add_node("jury_deliberation", jury_deliberation_node)
workflow.add_node("shadow_jury", shadow_jury_node)
workflow.add_node("archivist", archivist_node)

# Add Conditional Edge Logic
def check_security(state: TrialState) -> Literal["magistrate", "archivist"]:
    if state.get("errors") and any("CONTEMPT OF COURT" in err for err in state.get("errors")):
        # If security fails, jump to end
        return "archivist"
    return "magistrate"

def check_more_witnesses(state: TrialState) -> Literal["witness_examination", "closing_arguments"]:
    if len(state.get("witness_queue", [])) > 0:
        return "witness_examination"
    return "closing_arguments"

def check_verdict(state: TrialState) -> Literal["jury_deliberation", "shadow_jury"]:
    # If verdict reached or max rounds hit (3)
    if state.get("main_verdict") or state.get("deliberation_rounds", 0) >= 3:
        return "shadow_jury"
    return "jury_deliberation"

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

workflow.add_edge("magistrate", "human_input")
workflow.add_edge("human_input", "opening_statements")
workflow.add_edge("opening_statements", "evidence")
workflow.add_edge("evidence", "witness_examination")

# Witness Loop
workflow.add_conditional_edges(
    "witness_examination",
    check_more_witnesses,
    {
        "witness_examination": "witness_examination",
        "closing_arguments": "closing_arguments"
    }
)

workflow.add_edge("closing_arguments", "jury_instructions")
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

workflow.add_edge("shadow_jury", "archivist")
workflow.add_edge("archivist", END)

# Compile the graph
app = workflow.compile()
