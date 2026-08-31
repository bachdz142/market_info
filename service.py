import agent.ssl_bootstrap  # noqa: F401  — must import-run before anything below (see that module's docstring)

import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

VIETNAM_TZ = timezone(timedelta(hours=7))

from dotenv import load_dotenv
from fastapi import FastAPI
from tqdm import tqdm

load_dotenv()

from agent.graph import build_crawl_graph, build_graph, build_multi_pdf_graph
from agent.logging_config import setup_logging
from agent.sources import SOURCES
from agent.store import append_raw_content, append_topic_csv, append_topic_jsonl
from agent.topics import TOPICS

# TEMP: Tavily search disabled for now to avoid spending search credits —
# /trigger only runs the free SOURCES/crawler flow. Revert (delete this
# line) to bring the search-based topics back.
TOPICS = []

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Market Insight Agent")

# Groq's free/on-demand tier caps tokens-per-minute (TPM) — each topic's
# structure call alone can use 2,000-6,000 tokens, so firing topics
# back-to-back blows through that cap and crashes the run. Pace requests
# instead of relying solely on the client's built-in retry-on-429 behavior.
TOPIC_DELAY_SECONDS = 30


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


def _combined_raw_content(final_state: dict) -> Optional[str]:
    """The listing/page text alone (final_state["search_results"]) is
    incomplete for multi-PDF sources — it drops every per-document PDF text
    that _crawl_multi_node fetched. Combine it with each document's own
    text (labeled by its URL) so raw_content.csv captures everything that
    was actually fed to the LLM."""
    parts = []
    search_results = final_state.get("search_results")
    if search_results:
        parts.append(search_results)
    for pdf_url, pdf_text in final_state.get("pdf_texts") or []:
        parts.append(f"--- {pdf_url} ---\n{pdf_text}")
    return "\n\n".join(parts) if parts else None


def _run_item(graph, item: dict, index: int, total: int, extra_state: dict = None) -> dict:
    """Run one topic or source through its graph, catching errors so one
    failure doesn't crash the whole /trigger request."""
    item_start = time.perf_counter()
    thread_id = f"{item['id']}-{uuid.uuid4()}"
    state = {
        "query": item["prompt"],
        "gate_passed": False,
        "gate_reason": None,
        "search_results": None,
        "result": None,
        "token_usage": None,
        "url": None,
        "pdf_texts": None,
    }
    if extra_state:
        state.update(extra_state)

    try:
        final_state = graph.invoke(state, config={"configurable": {"thread_id": thread_id}})
        item_result = {
            "id": item["id"],
            "kind": item["kind"],
            "gate_passed": final_state.get("gate_passed"),
            "gate_reason": final_state.get("gate_reason"),
            "result": final_state.get("result"),
            "token_usage": final_state.get("token_usage"),
            "raw_content": _combined_raw_content(final_state),
            "error": None,
        }
    except Exception as exc:
        logger.exception("[%d/%d] %s raised an error", index, total, item["id"])
        item_result = {
            "id": item["id"],
            "kind": item["kind"],
            "gate_passed": None,
            "gate_reason": None,
            "result": None,
            "token_usage": None,
            "raw_content": None,
            "error": str(exc),
        }

    item_result["topic_seconds"] = round(time.perf_counter() - item_start, 2)
    logger.info(
        "[%d/%d] %s done in %ss (gate_passed=%s, error=%s)",
        index, total, item["id"], item_result["topic_seconds"],
        item_result["gate_passed"], item_result["error"],
    )
    return item_result


@app.post("/trigger")
def trigger() -> dict:
    search_graph = build_graph()
    crawl_graph = build_crawl_graph()
    multi_pdf_graph = build_multi_pdf_graph()
    run_id = str(uuid.uuid4())
    triggered_at = datetime.now(VIETNAM_TZ).isoformat()
    start = time.perf_counter()
    total = len(TOPICS) + len(SOURCES)

    logger.info("Trigger started (run_id=%s): %d topics, %d sources", run_id, len(TOPICS), len(SOURCES))
    all_results = []
    pbar = tqdm(total=total, desc="Trigger", unit="item")
    index = 0

    for topic in TOPICS:
        index += 1
        pbar.set_postfix_str(topic["id"])
        result = _run_item(search_graph, topic, index, total)
        # Save immediately — if a later item crashes or the process dies,
        # everything completed so far (and already paid for in tokens) is kept.
        append_topic_jsonl(triggered_at, run_id, result)
        append_topic_csv(triggered_at, run_id, result)
        append_raw_content(triggered_at, run_id, result)
        all_results.append(result)
        pbar.update(1)
        if index < total:
            time.sleep(TOPIC_DELAY_SECONDS)

    for source in SOURCES:
        index += 1
        pbar.set_postfix_str(source["id"])
        graph = multi_pdf_graph if source.get("multi_pdf") else crawl_graph
        result = _run_item(graph, source, index, total, extra_state={"url": source["url"]})
        append_topic_jsonl(triggered_at, run_id, result)
        append_topic_csv(triggered_at, run_id, result)
        append_raw_content(triggered_at, run_id, result)
        all_results.append(result)
        pbar.update(1)
        if index < total:
            time.sleep(TOPIC_DELAY_SECONDS)

    pbar.close()
    run_seconds = round(time.perf_counter() - start, 2)
    logger.info("Trigger finished in %ss", run_seconds)
    return {"run_id": run_id, "triggered_at": triggered_at, "run_seconds": run_seconds, "topics": all_results}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
