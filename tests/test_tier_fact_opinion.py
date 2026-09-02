"""Targeted, fully offline tests for the Tier 1/Tier 2 fact_or_opinion
field (see .scratch/tier2-fact-opinion-field/spec.md). _finalize_payload
is pure data-shaping code — no network or LLM call needed to test the
override behavior itself, matching agent/graph.py's own "known metadata
beats the LLM's guess" precedent already applied to source_url.
"""

import csv

import pytest
from pydantic import ValidationError

from agent import store
from agent.graph import _finalize_payload
from agent.schema import MarketSignal, MarketSignalBatch

BASE_SIGNAL_KWARGS = dict(
    signal_type="other",
    summary="A test signal.",
    observed_at="2026-01-01",
    confidence="high",
    source_code="TEST",
    reference_period="Q1 2026",
    data_basis="not_applicable",
    actual_proxy_forecast="actual",
)


def _batch_with_fact_or_opinion(value: str) -> MarketSignalBatch:
    signal = MarketSignal(fact_or_opinion=value, **BASE_SIGNAL_KWARGS)
    return MarketSignalBatch(query="q", signals=[signal], generated_at="")


def test_tier_1_forces_fact_regardless_of_model_output():
    """A tier_1 source's signal must come back "fact" even if the model
    itself produced "opinion" — known source metadata overrides the
    model's own guess, the same principle already applied to source_url."""
    batch = _batch_with_fact_or_opinion("opinion")

    payload = _finalize_payload("q", batch, url=None, tier="tier_1")

    assert payload["signals"][0]["fact_or_opinion"] == "fact"


def test_tier_2_leaves_model_output_untouched():
    """A tier_2 source's signal is left exactly as the model produced it —
    tier_2 content can genuinely mix fact and opinion in one document, so
    only the model's own per-signal judgment (guided by that source's own
    prompt) can tell them apart."""
    batch = _batch_with_fact_or_opinion("opinion")

    payload = _finalize_payload("q", batch, url=None, tier="tier_2")

    assert payload["signals"][0]["fact_or_opinion"] == "opinion"


def test_unset_tier_leaves_model_output_untouched():
    """tier=None (e.g. agent/topics.py's search-based queries, which never
    set tier) must not be silently treated as tier_1 — only an explicit
    "tier_1" triggers the override."""
    batch = _batch_with_fact_or_opinion("opinion")

    payload = _finalize_payload("q", batch, url=None, tier=None)

    assert payload["signals"][0]["fact_or_opinion"] == "opinion"


def test_market_signal_requires_fact_or_opinion():
    """fact_or_opinion has no legitimate "not applicable" case — every
    signal is unambiguously one or the other, so it must be required."""
    with pytest.raises(ValidationError):
        MarketSignal(**BASE_SIGNAL_KWARGS)


def test_market_signal_rejects_invalid_fact_or_opinion_value():
    with pytest.raises(ValidationError):
        MarketSignal(fact_or_opinion="maybe", **BASE_SIGNAL_KWARGS)


def test_signals_csv_includes_fact_or_opinion_column(tmp_path, monkeypatch):
    """Regression guard: a schema field is only really "added" if every
    consumer of MarketSignal reflects it — append_topic_csv() flattens
    signals into data/signals.csv independently of signals.jsonl, and
    silently dropped fact_or_opinion from it the first time this field was
    added (caught by code review, not by a test) until CSV_HEADERS and the
    per-signal row were updated to match."""
    csv_path = tmp_path / "signals.csv"
    monkeypatch.setattr(store, "SIGNALS_CSV", csv_path)

    topic_result = {
        "id": "test_source",
        "kind": "qualitative",
        "gate_passed": True,
        "gate_reason": None,
        "result": {
            "query": "q",
            "generated_at": "2026-01-01T00:00:00+07:00",
            "signals": [
                {**BASE_SIGNAL_KWARGS, "fact_or_opinion": "fact"},
            ],
        },
        "token_usage": None,
        "error": None,
    }

    store.append_topic_csv("2026-01-01T00:00:00+07:00", "run-1", topic_result)

    with csv_path.open("r", newline="") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 1
    assert rows[0]["fact_or_opinion"] == "fact"
