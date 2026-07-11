import unittest
from unittest.mock import patch

from legalist.agents import run_trial_step
from src.nodes import evidence_node, opening_statements_node
from src.state import create_initial_state


def _state(case_description="hello", live_step="opening"):
    state = create_initial_state(case_description=case_description)
    state["live_step"] = live_step
    return state


class TrialSafetyTests(unittest.TestCase):
    def test_opening_statements_do_not_call_llm_for_minimal_facts(self):
        def fail_get_llm(*args, **kwargs):
            raise AssertionError("LLM should not be called for insufficient facts")

        with patch("src.trial_phases.get_llm", fail_get_llm):
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

        with patch("src.evidence.get_llm", fail_get_llm), patch("src.evidence.get_structured_llm", fail_get_llm):
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
        from legalist.agents import _next_step_after

        self.assertEqual(_next_step_after("closing", _state()), "jury_instructions")


if __name__ == "__main__":
    unittest.main()
