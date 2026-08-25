import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langchain_tavily import TavilyExtract, TavilySearch
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agent.gate import checkpoint_gate
from agent.schema import MarketSignalBatch

logger = logging.getLogger(__name__)

STRUCTURE_SYSTEM_PROMPT = (
    "You are the Market Insight Agent. Your sole job is to extract raw, "
    "factual market signals (pricing changes, demand shifts, competitor "
    "activity, availability, etc.) from the search results below. Do not "
    "interpret, categorize, score, or recommend — that is handled by a "
    "downstream agent. Report only what the search results support, and "
    "cite source URLs where possible. If nothing relevant was found, "
    "return an empty signals list."
)


class AgentState(TypedDict):
    query: str
    gate_passed: bool
    gate_reason: Optional[str]
    search_results: Optional[str]
    result: Optional[dict]
    token_usage: Optional[dict]
    url: Optional[str]


def _build_model() -> ChatGroq:
    model_name = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
    return ChatGroq(model=model_name, temperature=0)


def _route_after_gate(state: AgentState) -> str:
    return "search" if state.get("gate_passed") else END


def _search_node(state: AgentState) -> dict:
    start = time.perf_counter()
    tool = TavilySearch(max_results=5)
    results = tool.invoke({"query": state["query"]})
    elapsed = round(time.perf_counter() - start, 2)
    logger.info("Search done in %ss for query: %s", elapsed, state["query"][:80])
    return {"search_results": str(results)}


def _extract_node(state: AgentState) -> dict:
    start = time.perf_counter()
    tool = TavilyExtract()
    results = tool.invoke({"urls": [state["url"]]})
    elapsed = round(time.perf_counter() - start, 2)
    logger.info("Extract done in %ss for url: %s", elapsed, state["url"])
    return {"search_results": str(results)}


def _structure_node(state: AgentState) -> dict:
    start = time.perf_counter()
    model = _build_model().with_structured_output(MarketSignalBatch, include_raw=True)
    response = model.invoke(
        [
            SystemMessage(content=STRUCTURE_SYSTEM_PROMPT),
            HumanMessage(
                content=f"Query: {state['query']}\n\nSearch results:\n{state['search_results']}"
            ),
        ]
    )
    elapsed = round(time.perf_counter() - start, 2)

    raw = response.get("raw")
    batch: Optional[MarketSignalBatch] = response.get("parsed")
    usage = getattr(raw, "usage_metadata", None) if raw is not None else None

    logger.info(
        "Structure LLM call done in %ss for query: %s | tokens: %s",
        elapsed,
        state["query"][:80],
        usage,
    )

    if batch is None:
        logger.warning(
            "Structured output parsing failed for query: %s | error: %s",
            state["query"][:80],
            response.get("parsing_error"),
        )
        batch = MarketSignalBatch(query=state["query"], signals=[], generated_at="")

    payload = batch.model_dump()
    payload["query"] = state["query"]
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    return {"result": payload, "token_usage": usage}


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("checkpoint_gate", checkpoint_gate)
    graph.add_node("search", _search_node)
    graph.add_node("structure", _structure_node)

    graph.add_edge(START, "checkpoint_gate")
    graph.add_conditional_edges(
        "checkpoint_gate", _route_after_gate, {"search": "search", END: END}
    )
    graph.add_edge("search", "structure")
    graph.add_edge("structure", END)

    return graph.compile(checkpointer=MemorySaver())


def build_extract_graph():
    """Same shape as build_graph(), but fetches a known URL (TavilyExtract)
    instead of running an open-ended search — for official/structured
    sources where the fact reliably lives at one stable page."""
    graph = StateGraph(AgentState)

    graph.add_node("checkpoint_gate", checkpoint_gate)
    graph.add_node("extract", _extract_node)
    graph.add_node("structure", _structure_node)

    graph.add_edge(START, "checkpoint_gate")
    graph.add_conditional_edges(
        "checkpoint_gate", _route_after_gate, {"search": "extract", END: END}
    )
    graph.add_edge("extract", "structure")
    graph.add_edge("structure", END)

    return graph.compile(checkpointer=MemorySaver())
