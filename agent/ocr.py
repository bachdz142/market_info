"""Mistral OCR — a fallback path for scanned/no-text-layer PDFs that
agent/content_gate.py's check_content_usable() already flags as "likely a
scan with a broken OCR/font-encoding layer" (BIDV's and Vietcombank's
Layer 1 filings, sbv_legal_directives_official — all downgraded to that
same category this project, per DEVELOPMENT_PLAN.md). Isolated here the
same way agent/llm_fallback.py isolates the LLM structuring fallback
chain from the rest of the graph — no other module's logic changes.

Uses Mistral's raw `mistralai` SDK, not `langchain-mistralai` (the
chat-only LangChain wrapper already used for the structuring fallback
chain, confirmed live to expose only ChatMistralAI/MistralAIEmbeddings) —
OCR/Batch/Files are Mistral-platform features outside LangChain's
chat-model abstraction, so they need the vendor SDK directly. Same
MISTRAL_API_KEY, same billing account, a second Python package.

Import note: `mistralai` 2.9.4's top-level package has no __init__.py
(a namespace package) — confirmed live that `from mistralai import
Mistral` fails; the real client class lives at `mistralai.client.Mistral`.

Runs in BATCH mode, not sync: a scanned bank statement can be 50+ pages,
and this isn't a real-time path — per the user's own framing, a job is
submitted, queued, and its result picked up later, not awaited inline in
the same request that found the scan. Batch API pricing is roughly $2 per
1,000 pages for the current OCR model (mistral.ai/pricing, checked live
2026-09-02) — half of sync pricing, and the whole reason to use batch
here even for jobs that could technically run sync.

See ocr_preview.py for a CLI that runs this against one local PDF file
end to end (submit + poll + fetch), to validate real output quality
before this gets wired into the live crawl -> content_gate -> structure
graph as an automatic fallback.
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from mistralai.client import Mistral

from agent.store import append_ocr_job

logger = logging.getLogger(__name__)

VIETNAM_TZ = timezone(timedelta(hours=7))

OCR_MODEL = os.environ.get("MISTRAL_OCR_MODEL", "mistral-ocr-latest")

# Signed URLs need to outlive the batch queue wait, not just the upload —
# a batch job can sit queued for a while before Mistral's own workers
# actually fetch the document. 24h is the SDK's own default and the
# practical ceiling for a single document's signed URL anyway.
SIGNED_URL_EXPIRY_HOURS = 24
BATCH_TIMEOUT_HOURS = 24

# mistral.ai/pricing (checked live 2026-09-02): Batch API OCR pricing is
# ~$2 per 1,000 pages for the current OCR model. A rough estimate only —
# labelled as such wherever it's surfaced, not treated as a real invoice
# figure (Mistral's actual price could change without this constant
# being updated).
ESTIMATED_USD_PER_PAGE_BATCH = 0.002


def _client() -> Mistral:
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        raise RuntimeError("MISTRAL_API_KEY is not set")
    return Mistral(api_key=api_key)


def submit_ocr_batch_job(pdf_path: Path, source_id: str) -> str:
    """Uploads one local PDF, wraps it in a 1-line OCR batch request, and
    submits the batch job. Returns the batch job id immediately — the job
    runs async server-side; poll_ocr_batch_job()/fetch_ocr_batch_result()
    check on it later, this call does not wait."""
    client = _client()

    pdf_upload = client.files.upload(
        file={"file_name": pdf_path.name, "content": pdf_path.read_bytes()},
        purpose="ocr",
    )
    signed_url = client.files.get_signed_url(file_id=pdf_upload.id, expiry=SIGNED_URL_EXPIRY_HOURS)

    batch_line = {
        "custom_id": source_id,
        "body": {
            "model": OCR_MODEL,
            "document": {"type": "document_url", "document_url": signed_url.url},
        },
    }
    batch_jsonl = (json.dumps(batch_line) + "\n").encode("utf-8")
    batch_upload = client.files.upload(
        file={"file_name": f"{source_id}_ocr_batch.jsonl", "content": batch_jsonl},
        purpose="batch",
    )

    job = client.batch.jobs.create(
        input_files=[batch_upload.id],
        endpoint="/v1/ocr",
        model=OCR_MODEL,
        timeout_hours=BATCH_TIMEOUT_HOURS,
        metadata={"source_id": source_id, "pdf_name": pdf_path.name},
    )
    logger.info("Submitted OCR batch job %s for %s (%s)", job.id, source_id, pdf_path.name)
    append_ocr_job(
        {
            "event": "submitted",
            "job_id": job.id,
            "source_id": source_id,
            "pdf_name": pdf_path.name,
            "timestamp": datetime.now(VIETNAM_TZ).isoformat(),
        }
    )
    return job.id


def poll_ocr_batch_job(job_id: str) -> dict:
    """One status check — deliberately not a blocking loop (see module
    docstring: this is meant to be checked back on later, not awaited on
    the request that found the scan). Returns a plain dict, not the raw
    SDK model, so callers/logging don't need mistralai imported just to
    read a status."""
    client = _client()
    job = client.batch.jobs.get(job_id=job_id)
    return {
        "id": job.id,
        "status": job.status,
        "total_requests": job.total_requests,
        "succeeded_requests": job.succeeded_requests,
        "failed_requests": job.failed_requests,
        "output_file": job.output_file,
    }


def _parse_batch_result_line(line: str) -> Optional[dict]:
    """Pure parsing of one line of a batch result file into
    {"markdown": str, "page_count": int} — split out from
    fetch_ocr_batch_result() so it can be unit-tested without a real
    network call. Batch result lines wrap the underlying OCR response —
    defensive about the exact wrapping (result["response"]["body"] vs.
    result["body"]) since research into the batch result shape found the
    docs inconsistent about it; unwrap whichever is present. Returns None
    if the line has no usable pages."""
    result = json.loads(line)
    body = (result.get("response") or {}).get("body") or result.get("body") or {}
    pages = body.get("pages") or []
    markdown = "\n\n".join(page.get("markdown", "") for page in pages if page.get("markdown"))
    if not markdown:
        return None
    return {"markdown": markdown, "page_count": len(pages)}


def fetch_ocr_batch_result(job_id: str) -> Optional[dict]:
    """Once a job's status is SUCCESS, downloads its output file and
    returns {"markdown": str, "page_count": int} for the (single)
    document in that batch — None if the job isn't done yet, or
    produced no usable result."""
    client = _client()
    job = client.batch.jobs.get(job_id=job_id)
    if job.status != "SUCCESS" or not job.output_file:
        return None

    response = client.files.download(file_id=job.output_file)
    lines = [line for line in response.text.splitlines() if line.strip()]
    if not lines:
        return None

    return _parse_batch_result_line(lines[0])


def run_ocr_sync(
    pdf_path: Path,
    source_id: str,
    poll_interval_seconds: int = 10,
    timeout_seconds: int = 600,
) -> str:
    """Blocking convenience wrapper for manual/CLI use (ocr_preview.py):
    submits, polls until done or timeout_seconds elapses, returns the
    markdown text. Not used by the live pipeline (see module docstring)
    — that path submits and checks back later instead of blocking a
    request on a queue-dependent job."""
    job_id = submit_ocr_batch_job(pdf_path, source_id)
    status: dict = {"status": "QUEUED"}
    start = time.monotonic()
    while time.monotonic() - start < timeout_seconds:
        status = poll_ocr_batch_job(job_id)
        logger.info("OCR job %s status: %s", job_id, status["status"])
        if status["status"] in ("SUCCESS", "FAILED", "TIMEOUT_EXCEEDED", "CANCELLED"):
            break
        time.sleep(poll_interval_seconds)
    else:
        raise TimeoutError(f"OCR job {job_id} did not finish within {timeout_seconds}s")

    if status["status"] != "SUCCESS":
        append_ocr_job(
            {
                "event": "failed",
                "job_id": job_id,
                "source_id": source_id,
                "status": status["status"],
                "timestamp": datetime.now(VIETNAM_TZ).isoformat(),
            }
        )
        raise RuntimeError(f"OCR job {job_id} did not succeed: {status}")

    result = fetch_ocr_batch_result(job_id)
    if not result:
        append_ocr_job(
            {
                "event": "failed",
                "job_id": job_id,
                "source_id": source_id,
                "status": "SUCCESS_BUT_NO_TEXT",
                "timestamp": datetime.now(VIETNAM_TZ).isoformat(),
            }
        )
        raise RuntimeError(f"OCR job {job_id} succeeded but produced no usable text")

    page_count = result["page_count"]
    append_ocr_job(
        {
            "event": "completed",
            "job_id": job_id,
            "source_id": source_id,
            "status": "SUCCESS",
            "page_count": page_count,
            "estimated_cost_usd": round(page_count * ESTIMATED_USD_PER_PAGE_BATCH, 4),
            "timestamp": datetime.now(VIETNAM_TZ).isoformat(),
        }
    )
    return result["markdown"]
