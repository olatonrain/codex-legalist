import unittest
from unittest.mock import patch

from legalis.agents import run_trial_step
from src.nodes import evidence_node, opening_statements_node


def _state(case_description="hello", live_step="opening"):
    return {
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
        "current_witness": None,
        "examination_phase": None,
        "shadow_jury_count": 1,
        "shadow_jury_model": "qwen-plus-latest",
        "jury_count": 12,
        "audio_enabled": False,
        "deliberation_rounds": 0,
        "jury_profiles": [],
        "deliberation_snapshot": {},
        "main_verdict": None,
        "shadow_jury_results": {},
        "multimodal_evidence": [],
        "errors": [],
        "country": "Nigeria",
        "jurisdiction_system": "Common Law",
        "jurisdiction_procedure": "adversarial",
        "criminal_standard": "Beyond reasonable doubt",
        "civil_standard": "Balance of probabilities",
        "evidence_rules": "Evidence Act 2011; Administration of Criminal Justice Act 2015 (ACJA)",
        "jury_enabled": False,
        "cross_examination": True,
        "court_address": "My Lord / Your Lordship",
        "case_type": "Criminal",
        "live_step": live_step,
    }


class TrialSafetyTests(unittest.TestCase):
    def test_opening_statements_do_not_call_llm_for_minimal_facts(self):
        def fail_get_llm(*args, **kwargs):
            raise AssertionError("LLM should not be called for insufficient facts")

        with patch("src.nodes.get_llm", fail_get_llm):
            result = opening_statements_node(_state("hello"))

        transcript = result["transcript"]

        self.assertEqual([msg.name for msg in transcript], ["Prosecutor", "Defense Counsel"])
        self.assertIn("too limited", transcript[0].content)
        self.assertIn("cannot responsibly open", transcript[0].content)
        self.assertNotIn("robbery", transcript[0].content.lower())
        self.assertNotIn("*", transcript[0].content)
        self.assertNotIn("—", transcript[0].content)

    def test_evidence_node_does_not_call_llm_for_minimal_facts(self):
        def fail_get_llm(*args, **kwargs):
            raise AssertionError("LLM should not be called for insufficient facts")

        with patch("src.nodes.get_llm", fail_get_llm), patch("src.nodes.get_structured_llm", fail_get_llm):
            result = evidence_node(_state("hello"))

        transcript = result["transcript"]

        self.assertEqual([msg.name for msg in transcript], ["Prosecutor", "Defense Counsel", "Judge"])
        self.assertIn("No exhibit is tendered", transcript[0].content)
        self.assertEqual(result["admitted_evidence"], [])
        self.assertEqual(result["excluded_evidence"], [])

    def test_run_trial_step_rejects_unknown_phase(self):
        with self.assertRaisesRegex(ValueError, "Unknown trial phase"):
            run_trial_step("phase_2", _state())

    def test_bench_trial_routes_to_judge_instructions_before_verdict(self):
        from legalis.agents import _next_step_after

        self.assertEqual(_next_step_after("closing", _state()), "jury_instructions")


if __name__ == "__main__":
    unittest.main()
