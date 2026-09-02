import csv
import json
import logging
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

VIETNAM_TZ = timezone(timedelta(hours=7))

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SIGNALS_FILE = DATA_DIR / "signals.jsonl"
SIGNALS_CSV = DATA_DIR / "signals.csv"
RAW_CONTENT_CSV = DATA_DIR / "raw_content.csv"
OCR_JOBS_FILE = DATA_DIR / "ocr_jobs.jsonl"

CSV_HEADERS = [
    "run_id",
    "triggered_at",
    "topic_id",
    "kind",
    "topic_seconds",
    "gate_passed",
    "gate_reason",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "error",
    "signal_type",
    "summary",
    "source_url",
    "observed_at",
    "confidence",
    "source_code",
    "reference_period",
    "data_basis",
    "actual_proxy_forecast",
    "forecast_org",
    "fact_or_opinion",
    "query",
    "generated_at",
]

RAW_CONTENT_CSV_HEADERS = ["run_id", "triggered_at", "id", "kind", "raw_content"]

# Guards the check-then-rename in _prepare_csv: without it, two concurrent
# callers can both see a stale header, both decide to archive, and race on
# the rename/rewrite — corrupting the file. One process-wide lock is enough
# since all writers run in this process (service.py's /trigger loop).
_csv_prepare_lock = threading.Lock()


def _prepare_csv(path: Path, headers: list) -> None:
    """Ensure path is ready to append to with the given header. If the file
    already exists with a different header (schema changed since it was
    created), archive the old file under a timestamped name instead of
    silently appending rows that would misalign against the stale header."""
    with _csv_prepare_lock:
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        if path.exists():
            with path.open("r", newline="", encoding="utf-8") as f:
                existing_header = next(csv.reader(f), None)
            if existing_header == headers:
                return
            timestamp = datetime.now(VIETNAM_TZ).strftime("%Y%m%dT%H%M%S")
            archive_path = path.with_name(f"{path.stem}.{timestamp}{path.suffix}")
            path.rename(archive_path)
            logger.warning("%s schema changed — archived old file to %s", path.name, archive_path)

        with path.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(headers)


def append_topic_jsonl(triggered_at: str, run_id: str, topic_result: dict) -> None:
    """Full-fidelity log: one JSON line per topic, written as soon as that topic
    finishes (success or failure) — so a crash mid-run doesn't lose earlier
    results. Excludes raw_content — see append_raw_content() for that,
    joinable back via (run_id, id)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    record = {k: v for k, v in topic_result.items() if k != "raw_content"}
    with SIGNALS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"run_id": run_id, "triggered_at": triggered_at, **record}, ensure_ascii=False) + "\n")


def append_topic_csv(triggered_at: str, run_id: str, topic_result: dict) -> None:
    """Flattened log: one CSV row per signal (or one row per topic if it had no
    signals or errored), written as soon as that topic finishes."""
    _prepare_csv(SIGNALS_CSV, CSV_HEADERS)

    with SIGNALS_CSV.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        result = topic_result.get("result")
        signals = (result or {}).get("signals") or []
        usage = topic_result.get("token_usage") or {}
        common = [
            run_id,
            triggered_at,
            topic_result["id"],
            topic_result["kind"],
            topic_result.get("topic_seconds"),
            topic_result.get("gate_passed"),
            topic_result.get("gate_reason"),
            usage.get("input_tokens", ""),
            usage.get("output_tokens", ""),
            usage.get("total_tokens", ""),
            topic_result.get("error") or "",
        ]

        if not signals:
            writer.writerow(
                common
                + [
                    "", "", "", "", "", "", "", "", "", "", "",
                    (result or {}).get("query", ""),
                    (result or {}).get("generated_at", ""),
                ]
            )
            return

        for signal in signals:
            writer.writerow(
                common
                + [
                    signal.get("signal_type", ""),
                    signal.get("summary", ""),
                    signal.get("source_url", ""),
                    signal.get("observed_at", ""),
                    signal.get("confidence", ""),
                    signal.get("source_code", ""),
                    signal.get("reference_period", ""),
                    signal.get("data_basis", ""),
                    signal.get("actual_proxy_forecast", ""),
                    signal.get("forecast_org", "") or "",
                    signal.get("fact_or_opinion", ""),
                    result.get("query", ""),
                    result.get("generated_at", ""),
                ]
            )


def append_ocr_job(record: dict) -> None:
    """Append-only log of Mistral OCR batch job submissions/completions —
    same pattern as append_topic_jsonl() (this project's storage is flat
    append-only files, not a database, so a job's lifecycle is a sequence
    of lines — e.g. one on submission, another once polling finds it
    done — rather than a row updated in place). Expected record shape:
    {"job_id", "source_id", "pdf_name", "event" ("submitted"/"completed"/
    "failed"), "timestamp", and, once known, "page_count"/
    "estimated_cost_usd"/"status"} — callers decide exactly which fields
    apply to a given event; this just appends whatever dict it's given."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with OCR_JOBS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def append_raw_content(triggered_at: str, run_id: str, topic_result: dict) -> None:
    """Separate log of the raw content fetched for each topic/source, before
    it was handed to the LLM to structure. One CSV row per topic. Joinable
    back to signals.jsonl/signals.csv via (run_id, id)."""
    _prepare_csv(RAW_CONTENT_CSV, RAW_CONTENT_CSV_HEADERS)

    with RAW_CONTENT_CSV.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(
            [
                run_id,
                triggered_at,
                topic_result["id"],
                topic_result["kind"],
                topic_result.get("raw_content") or "",
            ]
        )
