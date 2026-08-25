import logging

logger = logging.getLogger(__name__)

MAX_QUERY_LENGTH = 2000


def checkpoint_gate(state: dict) -> dict:
    """Pre-call validation gate. Runs before any model call — rejects bad
    input at the boundary instead of baking validation into the agent's
    reasoning loop."""
    query = (state.get("query") or "").strip()

    if not query:
        logger.warning("Gate rejected: empty query")
        return {"gate_passed": False, "gate_reason": "Query is empty."}

    if len(query) > MAX_QUERY_LENGTH:
        logger.warning("Gate rejected: query exceeds %d chars (%d)", MAX_QUERY_LENGTH, len(query))
        return {
            "gate_passed": False,
            "gate_reason": f"Query exceeds max length of {MAX_QUERY_LENGTH} characters.",
        }

    logger.info("Gate passed: %s", query[:80])
    return {"gate_passed": True, "gate_reason": None, "query": query}
