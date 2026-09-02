import agent.ssl_bootstrap  # noqa: F401  — must import-run before agent.graph below (see that module's docstring)

import argparse
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

VIETNAM_TZ = timezone(timedelta(hours=7))


def main() -> None:
    load_dotenv()

    from agent.graph import build_ocr_structure_graph
    from agent.ocr import fetch_ocr_batch_result
    from agent.sources import SOURCES
    from agent.store import append_raw_content, append_topic_csv, append_topic_jsonl

    parser = argparse.ArgumentParser(
        description=(
            "Structure an already-completed Mistral OCR batch job's text "
            "through the same LLM extraction step every other source uses, "
            "then log the result into data/signals.jsonl and "
            "data/signals.csv exactly like a normal /trigger run. This "
            "never submits or waits on an OCR job itself — that only "
            "happens via ocr_preview.py, a separate, deliberate action. "
            "Pass either --job-id (fetches the result fresh from Mistral) "
            "or --markdown-file (reads text already saved locally, e.g. by "
            "ocr_preview.py)."
        )
    )
    parser.add_argument(
        "source_id",
        help="An id from agent/sources.py — its prompt, url, and tier are "
        "reused so the OCR text is judged by that source's own extraction "
        "criteria, exactly like a normal crawl of it would be",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--job-id", help="A completed Mistral OCR batch job id")
    group.add_argument("--markdown-file", help="Path to a local .md file of already-recovered OCR text")
    args = parser.parse_args()

    source = next((s for s in SOURCES if s["id"] == args.source_id), None)
    if source is None:
        print(f"No source with id {args.source_id!r} in agent/sources.py", file=sys.stderr)
        sys.exit(1)

    if args.job_id:
        result = fetch_ocr_batch_result(args.job_id)
        if result is None:
            print(f"OCR job {args.job_id} isn't done yet, or produced no usable text", file=sys.stderr)
            sys.exit(1)
        markdown = result["markdown"]
    else:
        markdown_path = Path(args.markdown_file)
        if not markdown_path.is_file():
            print(f"Not a file: {markdown_path}", file=sys.stderr)
            sys.exit(1)
        markdown = markdown_path.read_text(encoding="utf-8")

    graph = build_ocr_structure_graph()
    run_id = str(uuid.uuid4())
    triggered_at = datetime.now(VIETNAM_TZ).isoformat()
    thread_id = f"{source['id']}-{uuid.uuid4()}"
    state = {
        "query": source["prompt"],
        "gate_passed": False,
        "gate_reason": None,
        "search_results": markdown,
        "result": None,
        "token_usage": None,
        "url": source.get("url"),
        "pdf_texts": None,
        "chunked": False,
        "tier": source.get("tier", "tier_1"),
    }

    print(f"Structuring OCR text for {source['id']} ({len(markdown)} chars)...")
    try:
        final_state = graph.invoke(state, config={"configurable": {"thread_id": thread_id}})
        item_result = {
            "id": source["id"],
            "kind": source["kind"],
            "gate_passed": final_state.get("gate_passed"),
            "gate_reason": final_state.get("gate_reason"),
            "result": final_state.get("result"),
            "token_usage": final_state.get("token_usage"),
            "raw_content": markdown,
            "error": None,
        }
    except Exception as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        item_result = {
            "id": source["id"],
            "kind": source["kind"],
            "gate_passed": None,
            "gate_reason": None,
            "result": None,
            "token_usage": None,
            "raw_content": markdown,
            "error": str(exc),
        }

    append_topic_jsonl(triggered_at, run_id, item_result)
    append_topic_csv(triggered_at, run_id, item_result)
    append_raw_content(triggered_at, run_id, item_result)

    if item_result["error"]:
        sys.exit(1)

    signals = (item_result["result"] or {}).get("signals") or []
    print(f"gate_passed={item_result['gate_passed']} | {len(signals)} signal(s) -> data/signals.jsonl, data/signals.csv")


if __name__ == "__main__":
    main()
