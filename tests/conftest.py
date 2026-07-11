import pytest
from contextlib import ExitStack
from unittest.mock import MagicMock, patch
from langchain_core.messages import AIMessage
from src.state import create_initial_state

# Modules that import get_llm / get_structured_llm from src.llm
_LLM_TARGETS = [
    "src.trial_phases",
    "src.evidence",
    "src.witness",
    "src.jury",
]


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
    """Mock LLM across all domain modules."""
    mock_instance = MagicMock()
    mock_instance.invoke.return_value = AIMessage(content="Mocked LLM response")
    with ExitStack() as stack:
        for mod in _LLM_TARGETS:
            stack.enter_context(patch(f"{mod}.get_llm", return_value=mock_instance))
        yield mock_instance


@pytest.fixture
def mock_structured_llm():
    """Mock structured LLM across all domain modules."""
    mock_instance = MagicMock()
    with ExitStack() as stack:
        for mod in _LLM_TARGETS:
            stack.enter_context(patch(f"{mod}.get_structured_llm", return_value=mock_instance))
        yield mock_instance
