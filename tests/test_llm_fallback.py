"""Deterministic tests for the LLM provider fallback chain
(agent/llm_fallback.py). These test OUR OWN cascade/validation logic with
fake chat models — fully offline, no real API calls — which is a
different thing than mocking away a real provider's behavior: each real
provider integration (Groq, Gemini, Mistral, OpenRouter) was separately
live-verified by hand before this chain was trusted (see
DEVELOPMENT_PLAN.md / CHANGELOG.md), including the specific failure modes
that shaped this design:
  - OpenRouter's free-tier models needing method="json_mode" plus an
    explicit schema description in the prompt (confirmed live: 3 free
    models tested, each failed differently under the default method).
  - A provider that raises an outright exception (e.g. Groq's real 429
    daily-quota error, or the 403 network-level block also observed live)
    must trigger the fallback exactly the same way as a provider that
    "succeeds" but returns something that fails schema validation.
"""

import pytest
from langchain_core.runnables import RunnableLambda

from agent import llm_fallback
from agent.schema import MarketSignalBatch


class _FakeChatModel:
    """Minimal stand-in for a LangChain chat model — implements only
    with_structured_output(...), since that's all _validated() calls."""

    def __init__(self, response_or_exception):
        self._response_or_exception = response_or_exception

    def with_structured_output(self, schema, include_raw=True, method=None):
        def _respond(_messages):
            if isinstance(self._response_or_exception, Exception):
                raise self._response_or_exception
            return self._response_or_exception

        return RunnableLambda(_respond)


def _empty_batch() -> MarketSignalBatch:
    return MarketSignalBatch(query="q", signals=[], generated_at="")


def test_validated_raises_on_none_parsed():
    """Requirement: a 'successful' call (no exception) whose output fails
    schema validation must still count as a failure, not just HTTP/rate-
    limit-level exceptions."""
    fake = _FakeChatModel({"raw": None, "parsed": None, "parsing_error": "fake failure"})
    chain = llm_fallback._validated(fake, "fake_provider", "fake_model")

    with pytest.raises(llm_fallback.ExtractionValidationError):
        chain.invoke([])


def test_fallback_cascades_on_validation_failure():
    failing = _FakeChatModel({"raw": None, "parsed": None, "parsing_error": "bad"})
    succeeding = _FakeChatModel({"raw": None, "parsed": _empty_batch(), "parsing_error": None})

    chain = llm_fallback._validated(failing, "primary", "primary-model").with_fallbacks(
        [llm_fallback._validated(succeeding, "fallback", "fallback-model")]
    )

    result = chain.invoke([])
    assert result["_provider"] == "fallback"
    assert result["_model"] == "fallback-model"


def test_fallback_cascades_on_raised_exception():
    """Not just schema-validation failures — a genuine exception (a real
    rate limit, a network-level block, an auth error) from one provider
    must also trigger the next, same as validation failures do."""
    failing = _FakeChatModel(RuntimeError("simulated provider failure"))
    succeeding = _FakeChatModel({"raw": None, "parsed": _empty_batch(), "parsing_error": None})

    chain = llm_fallback._validated(failing, "primary", "primary-model").with_fallbacks(
        [llm_fallback._validated(succeeding, "fallback", "fallback-model")]
    )

    result = chain.invoke([])
    assert result["_provider"] == "fallback"


def test_cascades_through_multiple_failures_to_the_last_provider():
    """Mirrors the real chain's shape: several providers fail in a row
    (mixing exception and validation-failure modes) before the last one
    in the list succeeds."""
    groq = _FakeChatModel(RuntimeError("simulated 429"))
    gemini = _FakeChatModel({"raw": None, "parsed": None, "parsing_error": "bad json"})
    mistral = _FakeChatModel(RuntimeError("simulated network block"))
    openrouter = _FakeChatModel({"raw": None, "parsed": _empty_batch(), "parsing_error": None})

    chain = llm_fallback._validated(groq, "groq", "groq-model").with_fallbacks(
        [
            llm_fallback._validated(gemini, "gemini", "gemini-model"),
            llm_fallback._validated(mistral, "mistral", "mistral-model"),
            llm_fallback._validated(openrouter, "openrouter", "openrouter-model"),
        ]
    )

    result = chain.invoke([])
    assert result["_provider"] == "openrouter"


def test_all_providers_failing_raises():
    """When every provider in the chain fails, the caller must still see
    an exception — _structure_one() relies on this to log the failure and
    propagate it exactly like the pre-fallback single-provider behavior did."""
    failing1 = _FakeChatModel({"raw": None, "parsed": None, "parsing_error": "bad"})
    failing2 = _FakeChatModel(RuntimeError("also bad"))

    chain = llm_fallback._validated(failing1, "primary", "primary-model").with_fallbacks(
        [llm_fallback._validated(failing2, "fallback", "fallback-model")]
    )

    with pytest.raises(Exception):
        chain.invoke([])


def test_structure_one_logs_provider_and_returns_batch(monkeypatch, tmp_path):
    """Integration point with agent/graph.py: _structure_one() must log
    which provider served the call and still return (batch, usage) with
    the same shape callers relied on before this feature existed."""
    import agent.graph as graph_module

    monkeypatch.setattr(llm_fallback, "DATA_DIR", tmp_path)
    monkeypatch.setattr(llm_fallback, "PROVIDER_LOG_CSV", tmp_path / "llm_provider_calls.csv")

    batch = _empty_batch()

    class _FakeRaw:
        usage_metadata = {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3}

    fake_chain = RunnableLambda(
        lambda _messages: {
            "raw": _FakeRaw(),
            "parsed": batch,
            "parsing_error": None,
            "_provider": "fake_provider",
            "_model": "fake_model",
        }
    )
    monkeypatch.setattr(graph_module, "build_structuring_model", lambda: fake_chain)

    result_batch, usage = graph_module._structure_one("q", "Content", "some text")

    assert result_batch is batch
    assert usage == {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3}

    log_content = (tmp_path / "llm_provider_calls.csv").read_text()
    assert "fake_provider" in log_content
    assert "fake_model" in log_content
