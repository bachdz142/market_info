import argparse
import json
import sys
import uuid

from dotenv import load_dotenv

from agent.graph import build_graph
from agent.logging_config import setup_logging


def main() -> None:
    load_dotenv()
    setup_logging()

    parser = argparse.ArgumentParser(description="Market Insight Agent — MVP0 demo")
    parser.add_argument("query", help="Market question to research, e.g. 'recent pricing changes in the cloud GPU market'")
    parser.add_argument("--thread-id", default=None, help="Session/thread id for checkpointing (defaults to a new uuid)")
    args = parser.parse_args()

    thread_id = args.thread_id or str(uuid.uuid4())
    graph = build_graph()

    final_state = graph.invoke(
        {
            "query": args.query,
            "gate_passed": False,
            "gate_reason": None,
            "search_results": None,
            "result": None,
            "token_usage": None,
        },
        config={"configurable": {"thread_id": thread_id}},
    )

    if not final_state.get("gate_passed"):
        print(f"Rejected by checkpoint gate: {final_state.get('gate_reason')}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(final_state["result"], indent=2))


if __name__ == "__main__":
    main()
