"""Tests at the seam agreed in .scratch/layer-1-quant-benchmarks/spec.md:
direct graph invocation — build the crawl graph for a source, invoke it,
and assert on the structured result. This is the same seam /trigger uses
in production (service.py's _run_item), and it exercises fetch → structure
→ merge end-to-end with no mocking of crawl4ai or the LLM.

These hit real network and Groq calls, so they're slow and cost real
tokens/time — that's an accepted tradeoff (see the spec's Testing
Decisions), not an oversight.
"""

import time
import uuid

import pytest

from agent.graph import build_crawl_graph, build_multi_pdf_graph
from agent.sources import SOURCES

# Mirrors service.py's TOPIC_DELAY_SECONDS pacing between items — without
# it, back-to-back parametrized test cases can trip Groq's free-tier
# tokens-per-minute limit the same way an unpaced /trigger run would.
INTER_SOURCE_DELAY_SECONDS = 15

REQUIRED_METADATA_FIELDS = ["source_code", "reference_period", "data_basis", "actual_proxy_forecast", "fact_or_opinion"]


def _run_source(source: dict) -> dict:
    uses_multi_graph = source.get("multi_pdf") or source.get("chunked")
    graph = build_multi_pdf_graph() if uses_multi_graph else build_crawl_graph()
    state = {
        "query": source["prompt"],
        "gate_passed": False,
        "gate_reason": None,
        "search_results": None,
        "result": None,
        "token_usage": None,
        "url": source["url"],
        "pdf_texts": None,
        "chunked": source.get("chunked", False),
        "tier": source.get("tier", "tier_1"),
        "source_id": source["id"],
        "assume_scan": source.get("assume_scan", False),
    }
    return graph.invoke(state, config={"configurable": {"thread_id": f"{source['id']}-{uuid.uuid4()}"}})


@pytest.fixture(autouse=True)
def _pace_requests():
    yield
    time.sleep(INTER_SOURCE_DELAY_SECONDS)


@pytest.mark.parametrize("source", SOURCES, ids=[s["id"] for s in SOURCES])
def test_source_produces_structured_signals_with_mandatory_metadata(source):
    """A Layer 1 source must: pass the gate, fetch real (non-empty) content,
    and — if it produced any signals — have every signal carry the
    mandatory audit metadata from source_plan_mvp0.md, with forecast_org
    set only when the figure is actually a forecast."""
    final_state = _run_source(source)

    assert final_state.get("gate_passed") is True, final_state.get("gate_reason")

    result = final_state.get("result")
    assert result is not None
    signals = result.get("signals")
    assert isinstance(signals, list)

    for signal in signals:
        for field in REQUIRED_METADATA_FIELDS:
            assert signal.get(field), f"{source['id']}: signal missing {field}: {signal}"
        if signal.get("actual_proxy_forecast") == "forecast":
            assert signal.get("forecast_org"), f"{source['id']}: forecast signal missing forecast_org: {signal}"
        else:
            assert not signal.get("forecast_org"), (
                f"{source['id']}: non-forecast signal has forecast_org set: {signal}"
            )
        if source.get("tier", "tier_1") == "tier_1":
            assert signal.get("fact_or_opinion") == "fact", (
                f"{source['id']}: tier_1 source signal not forced to fact: {signal}"
            )
