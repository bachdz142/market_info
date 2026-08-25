import logging
import time
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI
from tqdm import tqdm

load_dotenv()

from agent.graph import build_graph
from agent.logging_config import setup_logging
from agent.store import append_topic_csv, append_topic_jsonl
from agent.topics import TOPICS

# TEMP: testing the incremental-save + rate-limit fix on a smaller batch first.
# Revert (delete this line) once verified.
TOPICS = TOPICS[-10:]

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


@app.post("/trigger")
def trigger() -> dict:
    graph = build_graph()
    triggered_at = datetime.now(timezone.utc).isoformat()
    start = time.perf_counter()

    logger.info("Trigger started: %d topics", len(TOPICS))
    topic_results = []
    pbar = tqdm(total=len(TOPICS), desc="Trigger", unit="topic")
    for i, topic in enumerate(TOPICS, start=1):
        pbar.set_postfix_str(topic["id"])
        topic_start = time.perf_counter()
        thread_id = f"{topic['id']}-{uuid.uuid4()}"

        try:
            final_state = graph.invoke(
                {
                    "query": topic["prompt"],
                    "gate_passed": False,
                    "gate_reason": None,
                    "search_results": None,
                    "result": None,
                    "token_usage": None,
                },
                config={"configurable": {"thread_id": thread_id}},
            )
            topic_result = {
                "id": topic["id"],
                "kind": topic["kind"],
                "gate_passed": final_state.get("gate_passed"),
                "gate_reason": final_state.get("gate_reason"),
                "result": final_state.get("result"),
                "token_usage": final_state.get("token_usage"),
                "error": None,
            }
        except Exception as exc:
            logger.exception("[%d/%d] %s raised an error", i, len(TOPICS), topic["id"])
            topic_result = {
                "id": topic["id"],
                "kind": topic["kind"],
                "gate_passed": None,
                "gate_reason": None,
                "result": None,
                "token_usage": None,
                "error": str(exc),
            }

        topic_result["topic_seconds"] = round(time.perf_counter() - topic_start, 2)
        logger.info(
            "[%d/%d] %s done in %ss (gate_passed=%s, error=%s)",
            i, len(TOPICS), topic["id"], topic_result["topic_seconds"],
            topic_result["gate_passed"], topic_result["error"],
        )

        # Save immediately — if a later topic crashes or the process dies,
        # everything completed so far (and already paid for in tokens) is kept.
        append_topic_jsonl(triggered_at, topic_result)
        append_topic_csv(triggered_at, topic_result)
        topic_results.append(topic_result)
        pbar.update(1)

        if i < len(TOPICS):
            time.sleep(TOPIC_DELAY_SECONDS)

    pbar.close()
    run_seconds = round(time.perf_counter() - start, 2)
    logger.info("Trigger finished in %ss", run_seconds)
    return {"triggered_at": triggered_at, "run_seconds": run_seconds, "topics": topic_results}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
