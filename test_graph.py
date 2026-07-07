import os
from dotenv import load_dotenv

load_dotenv()

from src.graph import app
from src.state import create_initial_state

def test_graph():
    print("Testing Graph Execution...")

    initial_state = create_initial_state(
        case_description="The defendant, John Doe, is accused of stealing a loaf of bread from a bakery on June 1st. The shop owner, Mary Smith, claims she saw him do it. John Doe claims he was at home.",
        country="United States",
        jurisdiction_system="Common Law",
        jurisdiction_procedure="adversarial",
        criminal_standard="Beyond a reasonable doubt",
        civil_standard="Preponderance of the evidence",
        evidence_rules="Federal Rules of Evidence",
        jury_enabled=True,
        cross_examination=True,
        court_address="Your Honor",
        case_type="Criminal",
        shadow_jury_count=3,
    )
    initial_state["shadow_jury_model"] = "qwen-flash"

    result = app.invoke(initial_state)

    print("\n\n--- FINAL RESULT ---")
    print(f"Verdict: {result.get('main_verdict')}")
    print(f"Shadow Jury Win Prob: {result.get('shadow_jury_results', {}).get('win_probability')}")
    print(f"Errors: {result.get('errors')}")
    print("\nTranscript Length:", len(result.get("transcript", [])))

if __name__ == "__main__":
    test_graph()
