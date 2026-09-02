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
so this blocks (poll loop, real wall-clock minutes) rather than being a
fire-and-forget async job — acceptable because it only ever runs inside
service.py's already-long, already-paced /trigger loop, never on a
latency-sensitive path. Batch API pricing is roughly $2 per 1,000 pages
for the current OCR model (mistral.ai/pricing, checked live 2026-09-02) —
half of sync pricing, and the whole reason to use batch here even for
jobs that could technically run sync.

See ocr_preview.py for a CLI that runs this against one local PDF file
end to end (submit + poll + fetch) — the way real output quality was
first validated, and still the only way to test one document manually
without going through a full /trigger run.

Auto-wired into the live graph (2026-09-02, per explicit user direction —
originally deferred, deliberately reversed): agent/graph.py's
_content_gate_multi_node and _content_gate_node both call
ensure_ocr_text() below whenever a piece is flagged with code "scan" (the
corrupted-token heuristic) or "partial_scan" (agent/content_gate.py's
check_pdf_page_density() — real text on a couple of pages, blank scans
for the rest; BIDV's actual live failure mode, confirmed 2026-09-02: a
57-page filing with real text on exactly 2 pages, 0 chars on the other
55). Real, billed Mistral spend happens automatically now;
ensure_ocr_text()'s local cache (data/ocr_cache/) is the only thing
standing between that and re-paying for the same PDF on every single
/trigger run, so it is load-bearing, not an optimization.

download_pdf_bytes() below uses `requests` (not `urllib.request`) to
re-fetch a flagged PDF's raw bytes — confirmed live that BIDV's WCM-served
PDF URLs (wps/wcm/connect/...?MOD=AJPERES&CACHEID=...) reject a plain
urllib.request GET outright (an HTML "<!DOC..." error page, or the
connection gets closed mid-response) but succeed via `requests` with no
special headers at all — the same library and call shape crawl4ai's own
PDFContentScrapingStrategy already uses internally to fetch these same
URLs successfully. Matching that proven-working approach mattered more
here than any theory about why urllib specifically fails.
"""

import hashlib
import json
import logging
import os
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import requests

from mistralai.client import Mistral

from agent.store import append_ocr_job

logger = logging.getLogger(__name__)

# Recovered OCR text, cached by (source_id, pdf_url) — the only thing
# preventing ensure_ocr_text() from re-submitting (and re-paying for) the
# same document on every /trigger run. Flat files, same append-nothing-
# just-write pattern as the rest of this project's data/ storage; content
# rather than a log, since callers need the actual markdown back, not just
# a record that a job happened (see data/ocr_jobs.jsonl for that).
OCR_CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "ocr_cache"

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

    # download() deliberately returns a streaming httpx.Response
    # (stream=True internally) without reading it — confirmed live that
    # accessing .text directly raises "Attempted to access streaming
    # response content, without having called `read()`."; .read() loads
    # the full body first, same pattern the SDK's own error-handling
    # branches use internally (utils.stream_to_text) for this same
    # response type.
    response = client.files.download(file_id=job.output_file)
    response.read()
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


def _cache_path(source_id: str, pdf_url: str) -> Path:
    # Hash the URL rather than sanitizing it into a filename directly —
    # several of these URLs carry Vietnamese diacritics/percent-encoding
    # (e.g. sbv.gov.vn's document paths) that would need their own
    # escaping logic for no real benefit; a short hash is unambiguous and
    # filesystem-safe regardless of what the URL looks like.
    digest = hashlib.sha1(pdf_url.encode("utf-8")).hexdigest()[:12]
    return OCR_CACHE_DIR / f"{source_id}_{digest}.md"


def download_pdf_bytes(url: str) -> bytes:
    """Re-downloads a PDF's raw bytes for OCR submission. crawl4ai's own
    PDF strategy (the normal fetch path) only returns extracted text, not
    the source file, so a document content_gate flags needs a fresh direct
    download before it can be handed to Mistral.

    Uses `requests`, not `urllib.request` — confirmed live (2026-09-02)
    that BIDV's WCM-served PDF URLs reject a plain urllib GET (an HTML
    error page back, or the connection closed mid-response) but succeed
    via `requests` with no special headers, exactly matching what
    crawl4ai's own PDFContentScrapingStrategy does internally (see
    site-packages/crawl4ai/processors/pdf/__init__.py's _get_pdf_path) —
    reusing a call shape already proven to work against these exact URLs
    beats guessing at headers. `requests` also handles a literal
    unescaped space in the URL path (confirmed on sbv.gov.vn's document
    URLs) without needing manual percent-encoding, unlike urllib."""
    response = requests.get(url, stream=True, timeout=(20, 600))
    response.raise_for_status()
    return response.content


def ensure_ocr_text(source_id: str, pdf_url: str) -> Optional[str]:
    """Automatic OCR fallback, called from agent/graph.py's
    _content_gate_multi_node only when check_content_usable() has already
    flagged a piece with code "scan" (see that function's own docstring
    for why only "scan" is safe to auto-OCR, not "near_empty"/
    "block_page"). Real, billed Mistral spend happens here — guarded by a
    local cache keyed on (source_id, pdf_url) so the SAME document is
    never OCR'd twice across repeated /trigger runs; only a document seen
    for the first time (or whose cache file was deleted) actually costs
    money. Never raises: a failed download or OCR job just means this
    piece stays dropped, exactly as it was before this fallback existed,
    rather than crashing the whole item mid-/trigger."""
    cache_file = _cache_path(source_id, pdf_url)
    if cache_file.is_file():
        logger.info("OCR cache hit for %s (%s)", source_id, pdf_url)
        return cache_file.read_text()

    logger.info(
        "content_gate flagged a scan for %s (%s) -- submitting a real, billed OCR batch job",
        source_id, pdf_url,
    )
    try:
        pdf_bytes = download_pdf_bytes(pdf_url)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(pdf_bytes)
            tmp_path = Path(f.name)
        try:
            markdown = run_ocr_sync(tmp_path, source_id)
        finally:
            tmp_path.unlink(missing_ok=True)
    except Exception:
        logger.exception("Automatic OCR fallback failed for %s (%s)", source_id, pdf_url)
        return None

    OCR_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(markdown)
    return markdown
