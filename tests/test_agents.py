from unittest.mock import patch, MagicMock
from legalis.agents import run_trial_step, generate_dramatic_opening, norm_agent, sanitise_content


class TestNormAgent:
    def test_norm_agent_none(self):
        assert norm_agent(None) == "System"

    def test_norm_agent_juror(self):
        assert norm_agent("Juror 1") == "Juror"
        assert norm_agent("Juror 5") == "Juror"

    def test_norm_agent_defense_counsel(self):
        assert norm_agent("Defense Counsel") == "Defense"

    def test_norm_agent_passthrough(self):
        assert norm_agent("Judge") == "Judge"
        assert norm_agent("Prosecutor") == "Prosecutor"


class TestSanitiseContent:
    def test_sanitise_plain_text(self):
        result = sanitise_content("Hello world")
        assert result == "Hello world"

    def test_sanitise_json_ruling(self):
        result = sanitise_content('{"ruling": "SUSTAINED", "rationale": "Relevant evidence"}')
        assert "SUSTAINED" in result
        assert "Relevant evidence" in result

    def test_sanitise_json_verdict(self):
        result = sanitise_content('{"verdict": "Guilty", "rationale": "Evidence proves guilt"}')
        assert "Guilty" in result

    def test_sanitise_strips_markdown(self):
        result = sanitise_content("**Bold** text with *italics*")
        assert "**" not in result
        assert "*" not in result


class TestRunTrialStep:
    def test_unknown_phase_raises_error(self, mock_state):
        import pytest
        with pytest.raises(ValueError, match="Unknown trial phase"):
            run_trial_step("invalid_phase", mock_state)

    def test_valid_phase_returns_messages(self, mock_state):
        with patch("src.nodes.opening_statements_node") as mock_node:
            from langchain_core.messages import AIMessage
            mock_node.return_value = {
                "transcript": [AIMessage(content="Opening statement", name="Prosecutor")]
            }
            messages, state, next_step = run_trial_step("opening", mock_state)
            assert len(messages) > 0
            assert next_step == "evidence"


class TestGenerateDramaticOpening:
    def test_generates_opening_lines(self):
        with patch("legalis.agents.get_llm") as mock_llm:
            mock_instance = MagicMock()
            mock_instance.invoke.return_value = MagicMock(
                content='[{"agent": "Bailiff", "text": "All rise"}]'
            )
            mock_llm.return_value = mock_instance
            result = generate_dramatic_opening(
                case_title="Test Case",
                country="United States",
                system="Common Law",
                procedure="adversarial",
                case_type="Criminal",
                address="Your Honor"
            )
            assert len(result) > 0
            assert result[0]["agent"] == "Bailiff"

    def test_fallback_on_llm_error(self):
        with patch("legalis.agents.get_llm", side_effect=Exception("API Error")):
            result = generate_dramatic_opening(
                case_title="Test Case",
                country="United States",
                system="Common Law",
                procedure="adversarial",
                case_type="Criminal",
                address="Your Honor"
            )
            assert len(result) > 0
            assert result[0]["agent"] == "Bailiff"
