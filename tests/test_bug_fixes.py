"""Targeted tests for the bugs folded into the crawl4ai migration (see
.scratch/layer-1-quant-benchmarks/spec.md, Implementation Decisions).
Bugs #1/#2 are exercised at the graph/crawler seam (real network); bugs
#3/#4 live in pure data-shaping code (service.py/store.py) and are tested
directly with no network involved. Bug #5 (found live, post-migration) is
tested with a real crawl but a monkeypatched structure step, so the
failure is deterministic rather than depending on actually hitting a rate
limit — this tests our own resilience code, not crawl4ai/the LLM's real
behavior, which is a different thing than the "no mocking" call made for
the source-content tests in test_sources.py.
"""

import csv
import threading
import uuid
from pathlib import Path

import agent.graph
import agent.ocr
import service
from agent import store
from agent.crawler import crawl_parts
from agent.graph import build_crawl_graph, build_multi_pdf_graph
from agent.sources import SOURCES
from service import _combined_raw_content

SBV_PRESS_RELEASE_URL = "https://sbv.gov.vn/en/press-release"


def _no_ocr_spend(monkeypatch):
    # These tests hit real network/crawl4ai by design (see module
    # docstring) but were never meant to also exercise real, billed
    # Mistral OCR spend as a side effect — a real risk now that
    # agent/graph.py's content_gate nodes auto-trigger agent/ocr.py's
    # ensure_ocr_text() on a detected scan. Confirmed live (2026-09-02):
    # test_run_item_preserves_raw_content_when_structuring_fails below
    # actually did this once, unmocked, before this fixture existed —
    # bidv_financial_statements' real filing legitimately trips the new
    # partial-scan check, and a real ~$0.11 OCR job got submitted purely
    # as a side effect of running the test suite. Every test in this file
    # that reaches a content_gate node now guards against it.
    monkeypatch.setattr(agent.ocr, "ensure_ocr_text", lambda source_id, url: None)


def test_crawl_parts_survives_partial_pdf_failure():
    """Bug #2: one bad PDF must not discard the whole source's results.
    sbv.gov.vn's press-release source fetches 3 PDFs back-to-back and is
    documented (agent/crawler.py's SITE_CONFIGS comment) as flaky under
    that load — real-world conditions exercise this fix without needing to
    force a failure artificially."""
    list_text, documents = crawl_parts(SBV_PRESS_RELEASE_URL)

    assert list_text  # the listing page itself must always come through
    assert isinstance(documents, list)  # 0, 1, 2, or 3 docs — call must not raise
    for pdf_url, pdf_text in documents:
        assert pdf_url.startswith("http")
        assert pdf_text  # only successfully-fetched docs are ever included


def test_multi_pdf_signals_carry_their_own_document_url(monkeypatch):
    """Bug #1: merged multi-PDF signals must carry the URL of the document
    they actually came from, never the listing page's URL."""
    _no_ocr_spend(monkeypatch)
    state = {
        "query": (
            "Extract concrete market signals from the full press release "
            "content below — specific interest rates, exchange rates, "
            "transaction volumes, and how they changed versus the previous "
            "period."
        ),
        "gate_passed": False,
        "gate_reason": None,
        "search_results": None,
        "result": None,
        "token_usage": None,
        "url": SBV_PRESS_RELEASE_URL,
        "pdf_texts": None,
    }
    final_state = build_multi_pdf_graph().invoke(
        state, config={"configurable": {"thread_id": f"bug1-{uuid.uuid4()}"}}
    )
    signals = (final_state.get("result") or {}).get("signals") or []

    for signal in signals:
        assert signal.get("source_url") != SBV_PRESS_RELEASE_URL, (
            "signal was stamped with the listing page's URL instead of its own document's URL"
        )


def test_combined_raw_content_includes_listing_and_every_document():
    """Bug #3: raw_content must include every fetched document's text for
    multi-PDF sources, not just the listing page — this is a pure function
    of final_state, no network needed."""
    final_state = {
        "search_results": "listing page text",
        "pdf_texts": [
            ("https://example.com/a.pdf", "document A text"),
            ("https://example.com/b.pdf", "document B text"),
        ],
    }
    combined = _combined_raw_content(final_state)

    assert "listing page text" in combined
    assert "document A text" in combined
    assert "document B text" in combined
    assert "https://example.com/a.pdf" in combined
    assert "https://example.com/b.pdf" in combined


def test_prepare_csv_thread_safe_under_concurrent_schema_change(tmp_path, monkeypatch):
    """Bug #4: concurrent callers preparing the same CSV with a changed
    schema must not race on the check-then-rename and corrupt the file."""
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    path = tmp_path / "signals.csv"

    # Seed a file with a stale header, like a prior run with an older schema.
    with path.open("w", newline="") as f:
        csv.writer(f).writerow(["old", "header"])

    new_headers = ["run_id", "triggered_at", "signal_type"]
    errors = []

    def _prepare():
        try:
            store._prepare_csv(path, new_headers)
        except Exception as exc:  # pragma: no cover - failure surfaces via errors list
            errors.append(exc)

    threads = [threading.Thread(target=_prepare) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors

    with path.open("r", newline="") as f:
        header = next(csv.reader(f))
    assert header == new_headers

    # Exactly one archived copy of the stale file should exist — a race
    # would either lose it or produce a corrupted/duplicated mix.
    archives = list(tmp_path.glob("signals.*.csv"))
    assert len(archives) == 1


def test_run_item_preserves_raw_content_when_structuring_fails(monkeypatch):
    """Bug #5 (found live, post-migration): graph.invoke() runs
    crawl -> structure as one atomic call. When the structure step raises
    (confirmed live with a real Groq daily-quota 429) after the crawl step
    already fetched real content, service._run_item used to lose that
    content entirely along with the exception — thrown away even though
    fetching it was the expensive part. It must now recover the
    checkpointed crawl output instead."""

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated structure failure")

    monkeypatch.setattr(agent.graph, "_structure_one", _boom)
    # BIDV's real filing is a genuine partial scan (see check_pdf_page_density) —
    # content_gate correctly rejects it before structuring ever runs, which
    # would stop this test from reaching the code path it's actually
    # testing. Mock a plausible OCR recovery (not agent.ocr.ensure_ocr_text
    # -> None, which would leave the item correctly gate-rejected and never
    # call _structure_one at all) so the crawl -> gate -> structure chain
    # still runs for real up to the structuring step this test targets.
    monkeypatch.setattr(
        agent.ocr, "ensure_ocr_text",
        lambda source_id, url: "Mocked OCR-recovered text, long enough to clear the near-empty and corrupted-ratio content gate checks.",
    )

    source = next(s for s in SOURCES if s["id"] == "bidv_financial_statements")
    graph = build_crawl_graph()
    result = service._run_item(
        graph, source, 1, 1,
        extra_state={"url": source["url"], "chunked": False, "source_id": source["id"]},
    )

    assert result["error"] is not None
    assert "simulated structure failure" in result["error"]
    assert result["result"] is None
    assert result["raw_content"]
    assert len(result["raw_content"]) > 1000
