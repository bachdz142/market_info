import agent.ssl_bootstrap  # noqa: F401  — must import-run before crawl4ai/aiohttp below (see that module's docstring)

import argparse
import sys
from pathlib import Path

from agent.crawler import crawl, crawl_chunked, crawl_parts
from agent.sources import SOURCES

PREVIEW_DIR = Path("data/fetch_preview")


def _fetch_source(source: dict) -> str:
    """Routes to the same crawl function service.py/_run_item and
    tests/test_sources.py use for a given source's flags, but stops after
    the fetch — no structuring/LLM call, so this can be run freely to
    validate a source's raw content without spending any Groq/LLM quota."""
    if source.get("chunked"):
        list_text, pieces = crawl_chunked(source["url"])
    elif source.get("multi_pdf"):
        list_text, pieces = crawl_parts(source["url"])
    else:
        return crawl(source["url"])

    parts = [list_text] if list_text else []
    for piece_url, piece_text in pieces:
        parts.append(f"--- {piece_url} ---\n{piece_text}")
    return "\n\n".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch one or more sources' raw content (crawl4ai only, no LLM) "
            "and save it to data/fetch_preview/<id>.txt for manual review — "
            "use this to validate a source's fetch before trusting it in "
            "the real fetch -> structure pipeline."
        )
    )
    parser.add_argument(
        "source_ids", nargs="*",
        help="Source id(s) from agent/sources.py's SOURCES list; omit to fetch every source",
    )
    args = parser.parse_args()

    sources_by_id = {s["id"]: s for s in SOURCES}
    ids = args.source_ids or list(sources_by_id)

    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    for source_id in ids:
        source = sources_by_id.get(source_id)
        if not source:
            print(f"Unknown source id: {source_id}", file=sys.stderr)
            continue
        try:
            text = _fetch_source(source)
        except Exception as exc:
            print(f"[{source_id}] FAILED: {exc}")
            continue
        out_path = PREVIEW_DIR / f"{source_id}.txt"
        out_path.write_text(text)
        print(f"[{source_id}] {len(text)} chars -> {out_path}")


if __name__ == "__main__":
    main()
