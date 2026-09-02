"""Targeted, fully offline tests for the OCR fallback (see
.scratch/ocr-scan-fallback/spec.md). Deliberately does NOT test the real
network-calling functions in agent/ocr.py (submit/poll/fetch, and
run_ocr_sync) — those hit Mistral's real, billed Batch OCR API, and per
this project's standing rule against spending real money/quota during
routine development or CI, that path is validated manually via
ocr_preview.py instead (the same role fetch_preview.py already plays for
crawl4ai work), not by the automated suite. This file covers the pure,
non-network logic only: parsing a batch result line, and the job-tracking
log.
"""

import json

from agent import store
from agent.ocr import _parse_batch_result_line


def test_parse_batch_result_line_response_wrapping():
    """Confirmed-ambiguous-in-docs shape #1: result["response"]["body"]."""
    line = json.dumps(
        {
            "custom_id": "bidv_financial_statements",
            "response": {
                "status_code": 200,
                "body": {
                    "pages": [
                        {"index": 0, "markdown": "# Page one\nSome text."},
                        {"index": 1, "markdown": "## Page two\nMore text."},
                    ]
                },
            },
        }
    )
    result = _parse_batch_result_line(line)
    assert result is not None
    assert result["page_count"] == 2
    assert "Page one" in result["markdown"]
    assert "Page two" in result["markdown"]


def test_parse_batch_result_line_bare_body_wrapping():
    """Confirmed-ambiguous-in-docs shape #2: result["body"] directly, no
    "response" wrapper — the parser must handle both."""
    line = json.dumps(
        {
            "custom_id": "sbv_legal_directives_official",
            "body": {"pages": [{"index": 0, "markdown": "Some scanned text."}]},
        }
    )
    result = _parse_batch_result_line(line)
    assert result is not None
    assert result["page_count"] == 1
    assert result["markdown"] == "Some scanned text."


def test_parse_batch_result_line_no_pages_returns_none():
    line = json.dumps({"custom_id": "x", "response": {"body": {"pages": []}}})
    assert _parse_batch_result_line(line) is None


def test_parse_batch_result_line_pages_with_empty_markdown_returns_none():
    """A page object can exist with no markdown (e.g. a blank scanned
    page) — must not produce a result that's technically non-None but
    carries zero real text."""
    line = json.dumps(
        {"custom_id": "x", "response": {"body": {"pages": [{"index": 0, "markdown": ""}]}}}
    )
    assert _parse_batch_result_line(line) is None


def test_append_ocr_job_writes_and_reads_back(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "OCR_JOBS_FILE", tmp_path / "ocr_jobs.jsonl")

    store.append_ocr_job({"event": "submitted", "job_id": "job-1", "source_id": "bidv_financial_statements"})
    store.append_ocr_job(
        {
            "event": "completed",
            "job_id": "job-1",
            "source_id": "bidv_financial_statements",
            "page_count": 56,
            "estimated_cost_usd": 0.112,
        }
    )

    lines = store.OCR_JOBS_FILE.read_text().strip().split("\n")
    assert len(lines) == 2
    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first["event"] == "submitted"
    assert second["event"] == "completed"
    assert second["page_count"] == 56
