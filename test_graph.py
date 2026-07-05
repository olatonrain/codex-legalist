import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

from src.graph import app
from src.state import TrialState

async def test_graph():
    print("Testing Graph Execution...")
    
    initial_state = TrialState(
        case_description="The defendant, John Doe, is accused of stealing a loaf of bread from a bakery on June 1st. The shop owner, Mary Smith, claims she saw him do it. John Doe claims he was at home.",
        transcript=[],
        fact_sheet="",
        admitted_evidence=[],
        excluded_evidence=[],
        clarifying_questions=[],
        human_answers={},
        missing_evidence_answers={},
        missing_witnesses_answers={},
        pending_human_question=None,
        human_input_buffer=[],
        witness_queue=[],
        current_witness=None,
        examination_phase=None,
        shadow_jury_count=3,
        shadow_jury_model="qwen-flash",
        jury_count=12,
        audio_enabled=False,
        deliberation_rounds=0,
        jury_profiles=[],
        deliberation_snapshot={},
        main_verdict=None,
        shadow_jury_results={},
        multimodal_evidence=[],
        errors=[],
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
    )
    
    # Run the graph synchronously for testing purposes, but shadow_jury has an async internal loop
    # Wait, graph.invoke is sync.
    result = app.invoke(initial_state)
    
    print("\n\n--- FINAL RESULT ---")
    print(f"Verdict: {result.get('main_verdict')}")
    print(f"Shadow Jury Win Prob: {result.get('shadow_jury_results', {}).get('win_probability')}")
    print(f"Errors: {result.get('errors')}")
    print("\nTranscript Length:", len(result.get("transcript", [])))
    
if __name__ == "__main__":
    asyncio.run(test_graph())
