import pytest
from unittest.mock import MagicMock, patch
from langchain_core.messages import AIMessage
from src.state import create_initial_state


@pytest.fixture
def mock_state():
    """Base trial state for testing."""
    return create_initial_state(
        case_description="The defendant stole a car from the parking lot.",
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


@pytest.fixture
def mock_llm():
    """Mock LLM that returns predictable responses.
    Patches src.nodes.get_llm because src.nodes imports it via
    'from src.llm import get_llm', creating a separate namespace binding.
    """
    with patch("src.nodes.get_llm") as mock:
        mock_instance = MagicMock()
        mock_instance.invoke.return_value = AIMessage(content="Mocked LLM response")
        mock.return_value = mock_instance
        yield mock


@pytest.fixture
def mock_structured_llm():
    """Mock structured LLM that returns Pydantic models.
    Patches src.nodes.get_structured_llm because src.nodes imports it via
    'from src.llm import get_structured_llm', creating a separate namespace binding.
    """
    with patch("src.nodes.get_structured_llm") as mock:
        mock_instance = MagicMock()
        mock.return_value = mock_instance
        yield mock, mock_instance
