import agent.ssl_bootstrap  # noqa: F401  — must import-run before crawl4ai/aiohttp below (see that module's docstring)

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from agent.ocr import run_ocr_sync

PREVIEW_DIR = Path("data/ocr_preview")


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description=(
            "Run Mistral OCR (Batch mode) against one local PDF file and save "
            "the resulting markdown to data/ocr_preview/<source_id>.md for "
            "manual review — this is the only way an OCR job gets submitted "
            "right now (see .scratch/ocr-scan-fallback/spec.md): a deliberate, "
            "explicit action, never an automatic side effect of a normal "
            "/trigger run. Blocks until the job finishes or times out — real "
            "money is spent per page, per Mistral's Batch OCR pricing."
        )
    )
    parser.add_argument("pdf_path", help="Path to a local scanned PDF file")
    parser.add_argument(
        "source_id",
        help="An id for this document (e.g. an existing agent/sources.py id, "
        "or any label) — used as the batch request's custom_id and in the "
        "output filename and OCR job log",
    )
    parser.add_argument(
        "--timeout-seconds", type=int, default=600,
        help="Give up waiting after this long (default: 600s = 10 minutes)",
    )
    parser.add_argument(
        "--poll-interval-seconds", type=int, default=10,
        help="How often to check job status while waiting (default: 10s)",
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf_path)
    if not pdf_path.is_file():
        print(f"Not a file: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Submitting {pdf_path} as OCR batch job (source_id={args.source_id})...")
    try:
        markdown = run_ocr_sync(
            pdf_path,
            args.source_id,
            poll_interval_seconds=args.poll_interval_seconds,
            timeout_seconds=args.timeout_seconds,
        )
    except Exception as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        sys.exit(1)

    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PREVIEW_DIR / f"{args.source_id}.md"
    out_path.write_text(markdown)
    print(f"{len(markdown)} chars -> {out_path}")


if __name__ == "__main__":
    main()
