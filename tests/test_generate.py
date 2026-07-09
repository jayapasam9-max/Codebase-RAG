"""Tests for RAG prompt construction and answer generation.

The Anthropic client class itself is patched out (not just the network call),
so these tests never attempt real credential resolution and never spend API
credit, regardless of whether ANTHROPIC_API_KEY is set in the environment.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from codebase_rag import generate as generate_module
from codebase_rag.generate import SYSTEM_PROMPT, _format_context, answer_question


@pytest.fixture(autouse=True)
def reset_cumulative_usage():
    """The module tracks cumulative session cost in a global dict — reset it
    between tests so one test's spend doesn't leak into another's assertions.
    """
    generate_module._cumulative_usage["input_tokens"] = 0
    generate_module._cumulative_usage["output_tokens"] = 0
    yield


def _fake_query_results():
    return {
        "metadatas": [[
            {"file_path": "src/app.py", "start_line": 10, "end_line": 20, "chunk_type": "function", "name": "do_thing"},
            {"file_path": "README.md", "start_line": 1, "end_line": 5, "chunk_type": "lines", "name": ""},
        ]],
        "documents": [[
            "def do_thing():\n    return 42",
            "# App\nThis app does things.",
        ]],
    }


def _fake_anthropic_response(text="The answer is 42.", input_tokens=100, output_tokens=20):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


def test_format_context_labels_code_vs_non_code():
    context = _format_context(_fake_query_results())

    assert "src/app.py:10-20 (function do_thing)" in context
    assert "README.md:1-5 (non-code)" in context


def test_system_prompt_documents_the_code_priority_decision():
    # Regression guard for the design decision in README "Design decisions":
    # prioritize source code over docs/changelog when both are retrieved.
    assert "PRIORITIZE source code" in SYSTEM_PROMPT


@patch("codebase_rag.generate.query_repo")
@patch("codebase_rag.generate.anthropic.Anthropic")
def test_answer_question_returns_text_and_usage(mock_anthropic_cls, mock_query_repo):
    mock_query_repo.return_value = _fake_query_results()
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _fake_anthropic_response()
    mock_anthropic_cls.return_value = mock_client

    result = answer_question("some-repo", "What does do_thing return?")

    assert result.text == "The answer is 42."
    assert result.usage.input_tokens == 100
    assert result.usage.output_tokens == 20
    assert result.usage.cost_usd == pytest.approx(100 * 1.00 / 1_000_000 + 20 * 5.00 / 1_000_000)

    mock_client.messages.create.assert_called_once()
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-haiku-4-5-20251001"  # pinned — never Sonnet/Opus


@patch("codebase_rag.generate.query_repo")
@patch("codebase_rag.generate.anthropic.Anthropic")
def test_session_cost_accumulates_across_calls(mock_anthropic_cls, mock_query_repo):
    mock_query_repo.return_value = _fake_query_results()
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _fake_anthropic_response(
        input_tokens=1000, output_tokens=100
    )
    mock_anthropic_cls.return_value = mock_client

    first = answer_question("some-repo", "question one")
    second = answer_question("some-repo", "question two")

    assert second.session_cost_usd == pytest.approx(first.session_cost_usd * 2)
