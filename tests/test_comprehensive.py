"""
tests/test_comprehensive.py
───────────────────────────
Integration tests for the full Codex Legalis pipeline covering all 12 phases,
conditional features, and the comprehensive Vance demo case.
"""
from unittest.mock import MagicMock, patch
from langchain_core.messages import AIMessage
import pytest


# ═══════════════════════════════════════════════════════════════════════
# Live Step Coverage and Routing
# ═══════════════════════════════════════════════════════════════════════

class TestLiveSteps:
    def test_all_steps_have_node_mappings(self):
        from legalis.agents import _LIVE_STEPS, run_trial_step
        assert len(_LIVE_STEPS) >= 12
        assert "discovery" in _LIVE_STEPS
        assert "motions" in _LIVE_STEPS
        assert "opening" in _LIVE_STEPS
        assert "evidence" in _LIVE_STEPS
        assert "witness" in _LIVE_STEPS
        assert "rebuttal" in _LIVE_STEPS
        assert "closing" in _LIVE_STEPS
        assert "jury_instructions" in _LIVE_STEPS
        assert "jury_deliberation" in _LIVE_STEPS
        assert "shadow_jury" in _LIVE_STEPS
        assert "sentencing" in _LIVE_STEPS
        assert "reporter" in _LIVE_STEPS

    def test_all_steps_have_labels(self):
        from legalis.agents import _LIVE_STEPS, _STEP_LABELS
        for step in _LIVE_STEPS:
            assert step in _STEP_LABELS, f"Missing label for {step}"
            assert _STEP_LABELS[step], f"Empty label for {step}"


class TestPhaseTransitionRouting:
    """Test _next_step_after for every live step."""

    def get_state(self, verdict=None, witness_queue=None):
        from src.state import create_initial_state
        state = create_initial_state(
            case_description="Test case",
            country="United States",
            case_type="Criminal",
            jury_enabled=True,
        )
        if verdict is not None:
            state["main_verdict"] = verdict
        if witness_queue is not None:
            state["witness_queue"] = witness_queue
        return state

    def test_discovery_to_motions(self):
        from legalis.agents import _next_step_after
        assert _next_step_after("discovery", self.get_state()) == "motions"

    def test_motions_to_opening(self):
        from legalis.agents import _next_step_after
        assert _next_step_after("motions", self.get_state()) == "opening"

    def test_opening_to_evidence(self):
        from legalis.agents import _next_step_after
        assert _next_step_after("opening", self.get_state()) == "evidence"

    def test_evidence_to_witness(self):
        from legalis.agents import _next_step_after
        state = self.get_state(witness_queue=["Dr. Chen"])
        assert _next_step_after("evidence", state) == "witness"

    def test_witness_loops_with_queue(self):
        from legalis.agents import _next_step_after
        state = self.get_state(witness_queue=["Dr. Chen", "Paul Brennan"])
        assert _next_step_after("witness", state) == "witness"

    def test_witness_to_rebuttal_empty_queue(self):
        from legalis.agents import _next_step_after
        state = self.get_state(witness_queue=[])
        assert _next_step_after("witness", state) == "rebuttal"

    def test_rebuttal_to_closing(self):
        from legalis.agents import _next_step_after
        assert _next_step_after("rebuttal", self.get_state()) == "closing"

    def test_closing_to_jury_instructions_no_verdict(self):
        from legalis.agents import _next_step_after
        assert _next_step_after("closing", self.get_state()) == "jury_instructions"

    def test_closing_to_shadow_jury_with_verdict(self):
        from legalis.agents import _next_step_after
        assert _next_step_after("closing", self.get_state(verdict="Guilty")) == "shadow_jury"

    def test_jury_instructions_to_deliberation(self):
        from legalis.agents import _next_step_after
        assert _next_step_after("jury_instructions", self.get_state()) == "jury_deliberation"

    def test_deliberation_to_shadow_jury_with_verdict(self):
        from legalis.agents import _next_step_after
        assert _next_step_after("jury_deliberation", self.get_state(verdict="Guilty")) == "shadow_jury"

    def test_deliberation_loops_without_verdict(self):
        from legalis.agents import _next_step_after
        assert _next_step_after("jury_deliberation", self.get_state()) == "jury_deliberation"

    def test_shadow_jury_to_sentencing_guilty(self):
        from legalis.agents import _next_step_after
        assert _next_step_after("shadow_jury", self.get_state(verdict="Guilty")) == "sentencing"

    def test_shadow_jury_to_sentencing_liable(self):
        from legalis.agents import _next_step_after
        assert _next_step_after("shadow_jury", self.get_state(verdict="Liable")) == "sentencing"

    def test_shadow_jury_to_reporter_not_guilty(self):
        from legalis.agents import _next_step_after
        assert _next_step_after("shadow_jury", self.get_state(verdict="Not Guilty")) == "reporter"

    def test_sentencing_to_reporter(self):
        from legalis.agents import _next_step_after
        assert _next_step_after("sentencing", self.get_state()) == "reporter"

    def test_reporter_to_done(self):
        from legalis.agents import _next_step_after
        assert _next_step_after("reporter", self.get_state()) == "done"

    def test_unknown_step_returns_done(self):
        from legalis.agents import _next_step_after
        assert _next_step_after("nonexistent", self.get_state()) == "done"

    def test_complete_live_step_chain(self):
        """Verify the routing chain from discovery to done, simulating queue changes."""
        from legalis.agents import _next_step_after

        # Empty witness queue, no verdict set (deliberation loops unless rounds >= 3)
        state = self.get_state(witness_queue=[])

        # Verify linear segments without looping guards
        assert _next_step_after("discovery", state) == "motions"
        assert _next_step_after("motions", state) == "opening"
        assert _next_step_after("opening", state) == "evidence"
        assert _next_step_after("evidence", state) == "rebuttal"
        assert _next_step_after("rebuttal", state) == "closing"
        assert _next_step_after("closing", state) == "jury_instructions"
        assert _next_step_after("jury_instructions", state) == "jury_deliberation"
        # deliberation loops without verdict and rounds < 3
        assert _next_step_after("jury_deliberation", state) == "jury_deliberation"

    def test_linear_chain_with_verdict(self):
        """With a verdict set, deliberation exits and chain is fully linear."""
        from legalis.agents import _next_step_after

        state = self.get_state(witness_queue=[], verdict="Guilty")
        assert _next_step_after("closing", state) == "shadow_jury"
        assert _next_step_after("jury_deliberation", state) == "shadow_jury"
        assert _next_step_after("shadow_jury", state) == "sentencing"
        assert _next_step_after("sentencing", state) == "reporter"
        assert _next_step_after("reporter", state) == "done"

    def test_guilty_chain_includes_sentencing(self):
        """With a Guilty verdict, the chain includes sentencing."""
        from legalis.agents import _LIVE_STEPS, _next_step_after
        step = "discovery"
        state = self.get_state(verdict="Guilty")
        steps_visited = [step]
        for _ in range(len(_LIVE_STEPS) + 3):
            next_step = _next_step_after(step, state)
            if next_step == "done":
                break
            step = next_step
            steps_visited.append(step)
        assert "sentencing" in steps_visited
        assert steps_visited[-1] == "reporter"


# ═══════════════════════════════════════════════════════════════════════
# Demo Script Integrity
# ═══════════════════════════════════════════════════════════════════════

class TestDemoScript:
    def test_vance_case_loads(self):
        from legalis.data import DEMO_CASES
        assert "vance" in DEMO_CASES
        case = DEMO_CASES["vance"]
        assert case["title"] == "State v. Emilia Vance — Double Homicide by Arson"
        assert case["verdict"] == "GUILTY"
        assert len(case["questions"]) == 5

    def test_vance_script_has_all_phases(self):
        from legalis.data import DEMO_CASES
        script = DEMO_CASES["vance"]["trial_script"]
        phases = set(m["phase"] for m in script)
        expected = {
            "Discovery", "Motions", "Opening", "Evidence", "Witness",
            "Rebuttal", "Closing", "Jury Instructions", "Jury Deliberation",
            "Shadow Jury", "Sentencing", "Court Reporter Log", "Adjourned",
        }
        assert phases == expected, f"Missing: {expected - phases}, Extra: {phases - expected}"

    def test_vance_script_phases_in_order(self):
        from legalis.data import DEMO_CASES
        script = DEMO_CASES["vance"]["trial_script"]
        seen = []
        expected_order = [
            "Discovery", "Motions", "Opening", "Evidence", "Witness",
            "Rebuttal", "Closing", "Jury Instructions", "Jury Deliberation",
            "Shadow Jury", "Sentencing", "Court Reporter Log", "Adjourned",
        ]
        for msg in script:
            phase = msg["phase"]
            if not seen or phase != seen[-1]:
                seen.append(phase)
        assert seen == expected_order

    def test_vance_script_has_bailiff_announcements(self):
        from legalis.data import DEMO_CASES
        script = DEMO_CASES["vance"]["trial_script"]
        bailiff_count = sum(1 for m in script if m["agent"] == "Bailiff")
        assert bailiff_count >= 12, f"Expected >=12 Bailiff announcements, got {bailiff_count}"

    def test_vance_script_has_expert_qualification(self):
        from legalis.data import DEMO_CASES
        script = DEMO_CASES["vance"]["trial_script"]
        # Look for expert qualification dialogue: Dr. Chen stating credentials
        has_credentials = any(
            "22 years of experience" in m["text"] for m in script
        )
        has_voir_dire = any(
            "voir dire" in m["text"].lower() for m in script
        )
        has_qualified = any(
            "qualified as an expert" in m["text"].lower() for m in script
        )
        assert has_credentials, "Missing expert credentials"
        assert has_voir_dire, "Missing voir dire"
        assert has_qualified, "Missing expert qualification ruling"

    def test_vance_script_has_impeachment(self):
        from legalis.data import DEMO_CASES
        script = DEMO_CASES["vance"]["trial_script"]
        has_perjury = any(
            "perjury" in m["text"].lower() for m in script
        )
        has_fired = any(
            "fired by" in m["text"].lower() or "terminated" in m["text"].lower()
            for m in script
        )
        has_credibility = any(
            "credibility" in m["text"].lower() for m in script
        )
        assert has_perjury, "Missing perjury impeachment reference"
        assert has_fired, "Missing bias impeachment reference"
        assert has_credibility, "Missing credibility challenge"

    def test_vance_script_has_structured_objections(self):
        from legalis.data import DEMO_CASES
        script = DEMO_CASES["vance"]["trial_script"]
        # Should have at least 3 objection types
        objection_types = []
        for m in script:
            text = m["text"]
            if "foundation" in text.lower() and m["agent"] in ("Defense", "Judge"):
                objection_types.append("foundation")
            elif "hearsay" in text.lower() and m["agent"] in ("Defense", "Judge"):
                objection_types.append("hearsay")
            elif "prejudicial" in text.lower() or "403" in text:
                objection_types.append("prejudicial")
        assert "foundation" in objection_types, "Missing foundation objection"
        assert "hearsay" in objection_types, "Missing hearsay objection"
        assert "prejudicial" in objection_types, "Missing prejudicial objection"

    def test_vance_script_has_hearsay_exception(self):
        from legalis.data import DEMO_CASES
        script = DEMO_CASES["vance"]["trial_script"]
        has_business_records = any(
            "803(6)" in m["text"] for m in script
        )
        assert has_business_records, "Missing business records hearsay exception"

    def test_vance_script_has_redirect_examination(self):
        from legalis.data import DEMO_CASES
        script = DEMO_CASES["vance"]["trial_script"]
        has_redirect = any(
            "redirect" in m["text"].lower() for m in script
        )
        assert has_redirect, "Missing redirect examination"

    def test_vance_script_has_rebuttal_and_surrebuttal(self):
        from legalis.data import DEMO_CASES
        script = DEMO_CASES["vance"]["trial_script"]
        rebuttal_msgs = [m for m in script if m["phase"] == "Rebuttal"]
        assert len(rebuttal_msgs) >= 4, f"Expected >=4 rebuttal messages, got {len(rebuttal_msgs)}"
        has_surrebuttal = any(
            "surrebuttal" in m["text"].lower() for m in script
        )
        assert has_surrebuttal, "Missing surrebuttal"

    def test_vance_script_has_sentencing(self):
        from legalis.data import DEMO_CASES
        script = DEMO_CASES["vance"]["trial_script"]
        sentencing_msgs = [m for m in script if m["phase"] == "Sentencing"]
        assert len(sentencing_msgs) >= 3, f"Expected >=3 sentencing messages, got {len(sentencing_msgs)}"
        has_aggravation = any(
            "aggravation" in m["text"].lower() for m in sentencing_msgs
        )
        has_mitigation = any(
            "mitigation" in m["text"].lower() for m in sentencing_msgs
        )
        assert has_aggravation, "Missing aggravation argument"
        assert has_mitigation, "Missing mitigation argument"

    def test_vance_script_has_shadow_jury(self):
        from legalis.data import DEMO_CASES
        script = DEMO_CASES["vance"]["trial_script"]
        shadow_msgs = [m for m in script if m["phase"] == "Shadow Jury"]
        # 5 shadow jurors + bailiff announcements
        assert len(shadow_msgs) >= 6, f"Expected >=6 shadow jury messages, got {len(shadow_msgs)}"

    def test_vance_verdict_is_guilty(self):
        from legalis.data import DEMO_CASES
        assert DEMO_CASES["vance"]["verdict"] == "GUILTY"

    def test_vance_has_sentence_dict(self):
        from legalis.data import DEMO_CASES
        sentence = DEMO_CASES["vance"]["sentence"]
        assert "term" in sentence
        assert "rationale" in sentence
        assert len(sentence["rationale"]) > 50


# ═══════════════════════════════════════════════════════════════════════
# Graph Routing Functions
# ═══════════════════════════════════════════════════════════════════════

class TestGraphRouting:
    def get_state(self, **overrides):
        from src.state import create_initial_state
        state = create_initial_state(
            case_description="Test case",
            country="United States",
            case_type="Criminal",
            jury_enabled=True,
        )
        state.update(overrides)
        return state

    def test_security_check_passes_to_magistrate(self):
        from src.graph import check_security
        state = self.get_state()
        assert check_security(state) == "magistrate"

    def test_security_check_fails_to_archivist(self):
        from src.graph import check_security
        state = self.get_state(errors=["CONTEMPT OF COURT"])
        assert check_security(state) == "archivist"

    def test_witness_loop_continues(self):
        from src.graph import check_more_witnesses
        state = self.get_state(witness_queue=["Dr. Chen", "Paul Brennan"])
        assert check_more_witnesses(state) == "witness_examination"

    def test_witness_loop_ends(self):
        from src.graph import check_more_witnesses
        state = self.get_state(witness_queue=[])
        assert check_more_witnesses(state) == "rebuttal_evidence"

    def test_check_closing_with_verdict(self):
        from src.graph import check_closing
        assert check_closing(self.get_state(main_verdict="Guilty")) == "shadow_jury"

    def test_check_closing_without_verdict(self):
        from src.graph import check_closing
        assert check_closing(self.get_state()) == "jury_instructions"

    def test_check_verdict_reached(self):
        from src.graph import check_verdict
        assert check_verdict(self.get_state(main_verdict="Guilty")) == "shadow_jury"

    def test_check_verdict_max_rounds(self):
        from src.graph import check_verdict
        assert check_verdict(self.get_state(deliberation_rounds=3)) == "shadow_jury"

    def test_check_verdict_continue(self):
        from src.graph import check_verdict
        state = self.get_state(deliberation_rounds=1)
        assert check_verdict(state) == "jury_deliberation"

    def test_check_sentencing_guilty(self):
        from src.graph import check_sentencing
        assert check_sentencing(self.get_state(main_verdict="Guilty")) == "sentencing"

    def test_check_sentencing_liable(self):
        from src.graph import check_sentencing
        assert check_sentencing(self.get_state(main_verdict="Liable")) == "sentencing"

    def test_check_sentencing_not_guilty(self):
        from src.graph import check_sentencing
        state = self.get_state(main_verdict="Not Guilty")
        assert check_sentencing(state) == "reporter"

    def test_check_sentencing_no_verdict(self):
        from src.graph import check_sentencing
        assert check_sentencing(self.get_state()) == "reporter"


# ═══════════════════════════════════════════════════════════════════════
# TrialState & State Creation
# ═══════════════════════════════════════════════════════════════════════

class TestTrialState:
    def test_state_has_all_required_fields(self):
        from src.state import create_initial_state
        state = create_initial_state(
            case_description="Test case",
            country="United States",
            case_type="Criminal",
            jury_enabled=True,
        )
        required = [
            "case_description", "transcript", "fact_sheet", "admitted_evidence",
            "excluded_evidence", "clarifying_questions", "human_answers",
            "witness_queue", "current_witness", "examination_phase",
            "shadow_jury_count", "jury_count", "deliberation_rounds",
            "jury_profiles", "deliberation_snapshot", "main_verdict",
            "shadow_jury_results", "errors", "sentence", "rebuttal_rounds",
            "objection_history", "impeachment_attempts", "expert_witnesses",
            "motion_rulings", "disclosed_prosecution", "disclosed_defense",
            "trial_log", "country", "case_type",
        ]
        for field in required:
            assert field in state, f"Missing field: {field}"

    def test_state_with_vance_case(self):
        from src.state import create_initial_state
        from legalis.data import DEMO_CASES
        case = DEMO_CASES["vance"]
        state = create_initial_state(
            case_description=case["description"],
            country="United States",
            case_type="Criminal",
            jury_enabled=True,
            shadow_jury_count=5,
        )
        assert state["case_description"] == case["description"]
        assert state["shadow_jury_count"] == 5
        assert state["transcript"] == []
        assert state["trial_log"] == {}


# ═══════════════════════════════════════════════════════════════════════
# Graph Compilation
# ═══════════════════════════════════════════════════════════════════════

class TestGraphCompilation:
    def test_graph_compiles(self):
        from src.graph import app
        assert app is not None

    def test_graph_has_all_nodes(self):
        from src.graph import app
        nodes = app.get_graph().nodes
        expected_nodes = [
            "security_check", "magistrate", "discovery", "human_input",
            "motions", "opening_statements", "evidence", "witness_examination",
            "rebuttal_evidence", "closing_arguments", "jury_instructions",
            "jury_deliberation", "shadow_jury", "sentencing", "reporter",
            "archivist", "__start__", "__end__",
        ]
        for node in expected_nodes:
            assert node in nodes, f"Missing graph node: {node}"

    def test_graph_entry_point(self):
        from src.graph import app
        graph = app.get_graph()
        # Verify start edges go to security_check
        edges = list(graph.edges)
        start_edges = [e for e in edges if e[0] == "__start__"]
        assert len(start_edges) == 1


# ═══════════════════════════════════════════════════════════════════════
# Dynamic Examination Loop
# ═══════════════════════════════════════════════════════════════════════

class TestExaminationLoop:
    def _mock_llm(self, responses):
        """Create a mock LLM that returns each response in sequence then repeats the last."""
        mock = MagicMock()
        call_count = [0]
        def side_effect(*args, **kwargs):
            idx = min(call_count[0], len(responses) - 1)
            call_count[0] += 1
            return MagicMock(content=responses[idx])
        mock.invoke = MagicMock(side_effect=side_effect)
        return mock

    def get_jx(self):
        return {
            "country": "United States", "system": "Common Law",
            "procedure": "adversarial", "case_type": "Criminal",
            "legal_standard": "Beyond a reasonable doubt",
            "evidence_rules": "Federal Rules of Evidence",
            "jury_enabled": True, "cross": True,
            "address": "Your Honor",
        }

    def test_loop_terminates_on_done(self):
        """Examiner says DONE after 1 question — loop stops."""
        from src.nodes import _examination_loop
        import src.prompts as p

        examiner = self._mock_llm([
            "What did you see on March 14th?",
            "DONE"
        ])
        witness = self._mock_llm(["I saw the defendant near the vehicle."])
        fc = self._mock_llm(["PASS"])

        transcript = []
        qa = _examination_loop(
            examiner_llm=examiner,
            examiner_prompt_fn=p.prosecutor_prompt,
            examiner_name="Prosecutor",
            witness_name="Officer Daniels",
            witness_llm=witness,
            fc_llm=fc,
            facts="The defendant stole a car.",
            jx=self.get_jx(),
            phase_type="direct",
            max_q=20,
            transcript=transcript,
        )

        assert len(qa) == 1
        assert qa[0]["q"] == "What did you see on March 14th?"
        assert len(transcript) == 2
        assert transcript[0].name == "Prosecutor"
        assert transcript[1].name == "Witness"

    def test_loop_caps_at_max(self):
        """Examiner never says DONE — loop stops at max_q."""
        from src.nodes import _examination_loop
        import src.prompts as p

        max_q = 3
        examiner = self._mock_llm(["Q1", "Q2", "Q3", "Q4", "Q5"])
        witness = self._mock_llm(["A1", "A2", "A3", "A4", "A5"])
        fc = self._mock_llm(["PASS"] * 10)

        transcript = []
        qa = _examination_loop(
            examiner_llm=examiner,
            examiner_prompt_fn=p.defense_prompt,
            examiner_name="Defense Counsel",
            witness_name="Sarah Lin",
            witness_llm=witness,
            fc_llm=fc,
            facts="The defendant was at a bar.",
            jx=self.get_jx(),
            phase_type="cross",
            max_q=max_q,
            transcript=transcript,
        )

        assert len(qa) == max_q
        assert len(transcript) == max_q * 2

    def test_loop_fact_checker_fail_regenerates(self):
        """When fact checker fails, witness answer is regenerated."""
        from src.nodes import _examination_loop
        import src.prompts as p

        examiner = self._mock_llm(["What happened?", "DONE"])
        witness = self._mock_llm([
            "I saw aliens steal the car.",
            "I saw the defendant near the vehicle at 11:47 PM."
        ])
        fc = self._mock_llm(["OBJECTION: Not in Evidence", "PASS"])

        transcript = []
        qa = _examination_loop(
            examiner_llm=examiner,
            examiner_prompt_fn=p.prosecutor_prompt,
            examiner_name="Prosecutor",
            witness_name="Daniels",
            witness_llm=witness,
            fc_llm=fc,
            facts="The defendant stole a car at 11:47 PM.",
            jx=self.get_jx(),
            phase_type="direct",
            max_q=20,
            transcript=transcript,
        )

        assert len(qa) == 1
        assert len(transcript) == 3
        assert transcript[0].name == "Prosecutor"
        assert transcript[1].name == "Fact Checker"
        assert transcript[2].name == "Witness"
        assert "11:47 PM" in transcript[2].content

    def test_inquisitorial_phase_objective(self):
        """Inquisitorial follow-up phase uses the correct objective text."""
        from src.nodes import _examination_loop
        import src.prompts as p

        examiner = self._mock_llm(["DONE"])
        witness = self._mock_llm(["No answer"])
        fc = self._mock_llm(["PASS"])

        transcript = []
        qa = _examination_loop(
            examiner_llm=examiner,
            examiner_prompt_fn=p.defense_prompt,
            examiner_name="Defense Counsel",
            witness_name="Dubois",
            witness_llm=witness,
            fc_llm=fc,
            facts="The defendant ran a Ponzi scheme.",
            jx=self.get_jx(),
            phase_type="inquisitorial_defense",
            max_q=8,
            transcript=transcript,
        )

        assert len(qa) == 0
        assert len(transcript) == 0


# ═══════════════════════════════════════════════════════════════════════
# Reporter Node
# ═══════════════════════════════════════════════════════════════════════

class TestReporterNode:
    def test_reporter_schema_has_expected_fields(self):
        from src.nodes import TrialLogOutput
        fields = TrialLogOutput.model_fields
        assert "case_info" in fields
        assert "procedural_timeline" in fields
        assert "witnesses" in fields
        assert "evidence_log" in fields
        assert "key_rulings" in fields
        assert "verdict_summary" in fields

    def test_reporter_node_runs(self, mock_state, mock_llm):
        from src.nodes import reporter_node
        mock_state["main_verdict"] = "Guilty"
        mock_state["witness_queue"] = ["Dr. Chen"]
        mock_state["admitted_evidence"] = ["Exhibit A", "Exhibit B"]
        mock_state["objection_history"] = [
            {"type": "foundation", "ruling": "SUSTAINED"}
        ]
        result = reporter_node(mock_state)
        assert "trial_log" in result
        assert isinstance(result["trial_log"], dict)


# ═══════════════════════════════════════════════════════════════════════
# Bailiff Announcements in run_trial_step
# ═══════════════════════════════════════════════════════════════════════

class TestBailiffAnnouncements:
    def test_opening_phase_has_bailiff_begin(self, mock_state):
        from legalis.agents import run_trial_step
        with patch("src.nodes.opening_statements_node") as mock_node:
            mock_node.return_value = {
                "transcript": [AIMessage(content="Opening statement", name="Prosecutor")]
            }
            messages, _, _ = run_trial_step("opening", mock_state)
            begin_msg = messages[0]
            assert begin_msg["agent"] == "Bailiff"
            assert "court is now in session" in begin_msg["text"].lower()
            assert "opening statements" in begin_msg["text"].lower()

    def test_evidence_phase_has_bailiff_begin(self, mock_state):
        from legalis.agents import run_trial_step
        with patch("src.nodes.evidence_node") as mock_node:
            mock_node.return_value = {
                "transcript": [AIMessage(content="Evidence", name="Prosecutor")]
            }
            messages, _, _ = run_trial_step("evidence", mock_state)
            begin_msg = messages[0]
            assert begin_msg["agent"] == "Bailiff"

    def test_completion_has_bailiff_transition(self, mock_state):
        from legalis.agents import run_trial_step
        with patch("src.nodes.opening_statements_node") as mock_node:
            mock_node.return_value = {
                "transcript": [AIMessage(content="Opening", name="Prosecutor")]
            }
            messages, _, next_step = run_trial_step("opening", mock_state)
            assert next_step == "evidence"
            transition_msg = messages[-1]
            assert transition_msg["agent"] == "Bailiff"
            assert "proceed" in transition_msg["text"].lower()

    def test_done_step_has_bailiff_adjournment(self, mock_state):
        from legalis.agents import run_trial_step
        mock_state["main_verdict"] = None
        with patch("src.nodes.reporter_node") as mock_node:
            mock_node.return_value = {
                "transcript": [AIMessage(content="Report", name="System")],
                "trial_log": {"case_id": "test"},
            }
            messages, _, next_step = run_trial_step("reporter", mock_state)
            assert next_step == "done"
            # Find adjournment message
            adjourned = [m for m in messages if "adjourned" in m["text"].lower()]
            assert len(adjourned) >= 1


# ═══════════════════════════════════════════════════════════════════════
# All Demo Cases
# ═══════════════════════════════════════════════════════════════════════

class TestAllDemoCases:
    def test_count(self):
        from legalis.data import DEMO_CASES
        assert len(DEMO_CASES) == 3

    def test_all_have_required_fields(self):
        from legalis.data import DEMO_CASES
        required = ["title", "jurisdiction", "description", "questions",
                     "trial_script", "verdict", "win_probability", "sensitivity",
                     "shadow_jury_narrative"]
        for key, case in DEMO_CASES.items():
            for field in required:
                assert field in case, f"Case '{key}' missing field '{field}'"

    def test_all_trial_scripts_are_valid(self):
        from legalis.data import DEMO_CASES
        for key, case in DEMO_CASES.items():
            script = case["trial_script"]
            assert len(script) > 0, f"Case '{key}' has empty trial_script"
            for i, msg in enumerate(script):
                assert "agent" in msg, f"Case '{key}' msg #{i} missing 'agent'"
                assert "text" in msg, f"Case '{key}' msg #{i} missing 'text'"
                assert "phase" in msg, f"Case '{key}' msg #{i} missing 'phase'"
                assert msg["text"], f"Case '{key}' msg #{i} has empty text"

    def test_all_shadow_jury_narratives(self):
        from legalis.data import DEMO_CASES
        for key, case in DEMO_CASES.items():
            narratives = case["shadow_jury_narrative"]
            assert len(narratives) > 0, f"Case '{key}' has no shadow jury"
            for juror in narratives:
                assert "name" in juror
                assert "content" in juror
