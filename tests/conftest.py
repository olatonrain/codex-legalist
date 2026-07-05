import pytest
from unittest.mock import MagicMock, patch
from langchain_core.messages import AIMessage


@pytest.fixture
def mock_state():
    """Base trial state for testing."""
    return {
        "case_description": "The defendant stole a car from the parking lot.",
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
        "shadow_jury_count": 3,
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
        "country": "United States",
        "jurisdiction_system": "Common Law",
        "jurisdiction_procedure": "adversarial",
        "criminal_standard": "Beyond a reasonable doubt",
        "civil_standard": "Preponderance of the evidence",
        "evidence_rules": "Federal Rules of Evidence",
        "jury_enabled": True,
        "cross_examination": True,
        "court_address": "Your Honor",
        "case_type": "Criminal",
    }


@pytest.fixture
def mock_llm():
    """Mock LLM that returns predictable responses."""
    with patch("src.llm.get_llm") as mock:
        mock_instance = MagicMock()
        mock_instance.invoke.return_value = AIMessage(content="Mocked LLM response")
        mock.return_value = mock_instance
        yield mock


@pytest.fixture
def mock_structured_llm():
    """Mock structured LLM that returns Pydantic models."""
    with patch("src.llm.get_structured_llm") as mock:
        mock_instance = MagicMock()
        mock.return_value = mock_instance
        yield mock, mock_instance
