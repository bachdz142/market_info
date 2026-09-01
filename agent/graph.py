import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_tavily import TavilySearch
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agent.content_gate import check_content_usable
from agent.gate import checkpoint_gate
from agent.llm_fallback import build_structuring_model, log_provider_call
from agent.schema import MarketSignalBatch

logger = logging.getLogger(__name__)

VIETNAM_TZ = timezone(timedelta(hours=7))

SIGNAL_TYPE_INSTRUCTION = (
    "signal_type must be exactly one of these five values — never invent a "
    "new one: \"price_change\", \"demand_shift\", \"competitor_activity\", "
    "\"availability\", \"other\". A rate or price moving up or down is "
    "\"price_change\", even if it's an interest rate, not a product price."
)

METADATA_INSTRUCTION = (
    "Every signal also needs this metadata: "
    "source_code is a short identifier for where the figure came from — a "
    "bank ticker (TCB, VCB, BID, MBB, ACB), or SBV/IAV/VIETSTOCK/GSO, or "
    "another short code appropriate to the source; infer it from the "
    "content or the query if it isn't stated outright. "
    "reference_period is the period the DATA ITSELF covers (e.g. \"Q2 "
    "2026\", \"FY2025\") — this is distinct from observed_at, which is when "
    "the figure was reported or observed; use \"unknown\" only if the "
    "content gives no period at all. "
    "data_basis is \"standalone\" or \"consolidated\" for bank financial-"
    "statement figures, or \"not_applicable\" for anything else (rates, "
    "macro indicators, non-financial-statement data). "
    "actual_proxy_forecast is \"actual\" for a disclosed/reported value, "
    "\"proxy\" for a stand-in estimate drawn from related data, or "
    "\"forecast\" for an explicit projection. "
    "forecast_org is the organization that produced the forecast — set it "
    "ONLY when actual_proxy_forecast is \"forecast\"; leave it unset "
    "otherwise."
)

STRUCTURE_SYSTEM_PROMPT = (
    "You are the Market Insight Agent. Your sole job is to extract raw, "
    "factual market signals (pricing changes, demand shifts, competitor "
    "activity, availability, etc.) from the search results below. Do not "
    "interpret, categorize, score, or recommend — that is handled by a "
    "downstream agent. Report only what the search results support, and "
    "cite source URLs where possible. If nothing relevant was found, "
    "return an empty signals list. " + SIGNAL_TYPE_INSTRUCTION + " " + METADATA_INSTRUCTION
)

# Pacing between the multiple LLM calls in _structure_multi_node — Groq's
# free tier caps tokens-per-minute; firing several structure calls back to
# back for one source would trigger the same rate limit the /trigger loop's
# own TOPIC_DELAY_SECONDS pacing protects against between different items.
MULTI_CALL_DELAY_SECONDS = 30


class AgentState(TypedDict):
    query: str
    gate_passed: bool
    gate_reason: Optional[str]
    search_results: Optional[str]
    result: Optional[dict]
    token_usage: Optional[dict]
    url: Optional[str]
    pdf_texts: Optional[list]
    chunked: Optional[bool]




def _route_after_gate(state: AgentState) -> str:
    return "search" if state.get("gate_passed") else END


def _search_node(state: AgentState) -> dict:
    start = time.perf_counter()
    tool = TavilySearch(max_results=5)
    results = tool.invoke({"query": state["query"]})
    elapsed = round(time.perf_counter() - start, 2)
    logger.info("Search done in %ss for query: %s", elapsed, state["query"][:80])
    return {"search_results": str(results)}


def _crawl_node(state: AgentState) -> dict:
    start = time.perf_counter()
    from agent.crawler import crawl

    text = crawl(state["url"])
    elapsed = round(time.perf_counter() - start, 2)
    logger.info("Crawl done in %ss for url: %s", elapsed, state["url"])
    return {"search_results": text}


def _content_gate_node(state: AgentState) -> dict:
    """Runs after a single-fetch crawl, before the structuring LLM call —
    rejects unusable content (near-empty, a WAF block page, a scan with a
    broken OCR layer) for free, before any model spend. Reuses gate_passed/
    gate_reason rather than a separate field pair: the rest of the pipeline
    (service.py's reporting, the CSV schema) already knows how to surface a
    gate rejection, and the reason text itself says which gate rejected it."""
    result = check_content_usable(state.get("search_results") or "")
    if not result["usable"]:
        logger.warning("Content gate rejected %s: %s", state.get("url"), result["reason"])
        return {"gate_passed": False, "gate_reason": f"Content gate: {result['reason']}"}
    return {}


def _content_gate_multi_node(state: AgentState) -> dict:
    """Same purpose as _content_gate_node, but per-document: one bad PDF
    among several shouldn't discard the rest (same principle as the
    existing partial-PDF-failure handling in agent/crawler.py). Drops each
    unusable piece individually; only rejects the whole item if nothing
    usable survives — including the list/page text _structure_multi_node
    would otherwise fall back to."""
    documents = state.get("pdf_texts") or []
    kept = []
    for piece_url, piece_text in documents:
        result = check_content_usable(piece_text)
        if result["usable"]:
            kept.append((piece_url, piece_text))
        else:
            logger.warning("Content gate dropped a piece from %s: %s", piece_url, result["reason"])

    if not kept:
        list_result = check_content_usable(state.get("search_results") or "")
        if not list_result["usable"]:
            logger.warning("Content gate rejected %s: %s", state.get("url"), list_result["reason"])
            return {
                "gate_passed": False,
                "gate_reason": f"Content gate: {list_result['reason']}",
                "pdf_texts": [],
            }

    return {"pdf_texts": kept}


def _route_after_content_gate(state: AgentState) -> str:
    return "continue" if state.get("gate_passed") else END


def _crawl_multi_node(state: AgentState) -> dict:
    start = time.perf_counter()
    from agent.crawler import crawl_chunked, crawl_parts

    # Two different reasons a source ends up needing several structure
    # calls instead of one: multiple distinct PDFs (crawl_parts) vs. one
    # document/page whose own text is too large for a single Groq call
    # (crawl_chunked) — both return the same (list_text, [(url, text), ...])
    # shape, so the rest of this flow doesn't need to know which it is.
    fetch = crawl_chunked if state.get("chunked") else crawl_parts
    list_text, documents = fetch(state["url"])
    elapsed = round(time.perf_counter() - start, 2)
    logger.info(
        "Multi-crawl done in %ss for url: %s (%d documents)", elapsed, state["url"], len(documents)
    )
    # documents is [(pdf_url, pdf_text), ...] — each PDF's own URL travels
    # alongside its text so _structure_multi_node can stamp signals with
    # their real provenance instead of the listing page's URL.
    return {"search_results": list_text, "pdf_texts": documents}


def _structure_one(query: str, label: str, text: str, system_prompt: str = STRUCTURE_SYSTEM_PROMPT):
    """One structure LLM call over one chunk of raw text, via the
    Groq -> Gemini -> Mistral -> OpenRouter fallback chain (see
    agent/llm_fallback.py). Returns (MarketSignalBatch, usage_dict_or_None)."""
    start = time.perf_counter()
    logger.info("Raw content fed to LLM for query: %s\n%s", query[:80], text)
    model = build_structuring_model()
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Query: {query}\n\n{label}:\n{text}"),
    ]
    try:
        response = model.invoke(messages)
    except Exception as exc:
        elapsed = round(time.perf_counter() - start, 2)
        logger.error("All providers failed for query: %s (%ss) | %s", query[:80], elapsed, exc)
        log_provider_call(provider="none", model="none", success=False, query=query, error=str(exc))
        raise

    elapsed = round(time.perf_counter() - start, 2)

    raw = response.get("raw")
    batch: Optional[MarketSignalBatch] = response.get("parsed")
    usage = getattr(raw, "usage_metadata", None) if raw is not None else None
    provider = response.get("_provider", "unknown")
    model_name = response.get("_model", "unknown")

    logger.info(
        "Structure LLM call done in %ss for query: %s | provider: %s/%s | tokens: %s",
        elapsed, query[:80], provider, model_name, usage,
    )
    log_provider_call(provider=provider, model=model_name, success=True, query=query)

    if batch is None:
        # Shouldn't happen — _validated() in llm_fallback.py already raises
        # rather than returning parsed=None — but stay defensive in case a
        # provider's response slips through some edge case.
        logger.warning(
            "Structured output parsing failed for query: %s | error: %s",
            query[:80],
            response.get("parsing_error"),
        )
        batch = MarketSignalBatch(query=query, signals=[], generated_at="")

    return batch, usage


def _finalize_payload(query: str, batch: MarketSignalBatch, url: Optional[str] = None) -> dict:
    payload = batch.model_dump()
    payload["query"] = query
    payload["generated_at"] = datetime.now(VIETNAM_TZ).isoformat()

    # For crawl-based sources with one known URL, every signal unambiguously
    # came from it — fill it in deterministically rather than relying on
    # the LLM to guess a URL it was never shown.
    if url:
        for signal in payload["signals"]:
            signal["source_url"] = url
    return payload


def _structure_node(state: AgentState) -> dict:
    batch, usage = _structure_one(state["query"], "Search results", state["search_results"])
    payload = _finalize_payload(state["query"], batch, state.get("url"))
    return {"result": payload, "token_usage": usage}


def _structure_multi_node(state: AgentState) -> dict:
    """For sources whose content arrives as several pieces — either several
    distinct PDFs (agent/crawler.py's crawl_parts) or one oversized
    document/page split into chunks (crawl_chunked) — structure each piece
    on its own call, small enough to stay well under Groq's per-request
    token ceiling, then merge the per-piece batches deterministically (no
    LLM call; see comment below on why an LLM synthesis step doesn't
    actually solve this). Paced with MULTI_CALL_DELAY_SECONDS between the
    per-piece calls to stay under the tokens-per-minute rate limit across
    this node's own multiple calls."""
    query = state["query"]
    documents = state.get("pdf_texts") or []  # [(url, piece_text), ...]
    total_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    def _add_usage(usage):
        if usage:
            for k in total_usage:
                total_usage[k] += usage.get(k, 0)

    if not documents:
        # No PDFs found — fall back to structuring the list/page text alone.
        batch, usage = _structure_one(query, "Content", state["search_results"])
        _add_usage(usage)
        return {"result": _finalize_payload(query, batch, state.get("url")), "token_usage": total_usage}

    batches = []
    for i, (piece_url, text) in enumerate(documents, start=1):
        try:
            batch, usage = _structure_one(query, f"Content piece {i} of {len(documents)}", text)
        except Exception:
            # A single piece's LLM call can fail outright (confirmed live:
            # Groq's gpt-oss-120b occasionally emits a malformed tool call
            # on a large batch of chunks, raising groq.BadRequestError
            # rather than just returning an unparseable response — that
            # softer case is already handled inside _structure_one). Skip
            # this piece rather than losing every other piece's
            # already-obtained results — same partial-failure principle as
            # the PDF-fetch resilience above.
            logger.exception("Structure call failed for piece %d/%d, skipping", i, len(documents))
            if i < len(documents):
                time.sleep(MULTI_CALL_DELAY_SECONDS)
            continue

        # Stamp each signal with the document it actually came from — not
        # the listing page's URL — before merging (bug fix: previously
        # _finalize_payload stamped every merged signal with the listing
        # page's URL regardless of which PDF it was extracted from).
        for signal in batch.signals:
            signal.source_url = piece_url
        batches.append(batch)
        _add_usage(usage)
        logger.info("Per-piece structure call %d/%d done", i, len(documents))
        if i < len(documents):
            time.sleep(MULTI_CALL_DELAY_SECONDS)

    # Combine deterministically — no LLM call. Each per-document batch
    # already succeeded and is valid structured data; merging is just
    # concatenation (+ dedup on exact-duplicate summaries). An LLM
    # "synthesis" call here was tried first but just moved the same
    # token-ceiling problem up a level: combining ~20+ already-extracted
    # signals into one output is itself often too large for one call.
    seen_summaries = set()
    merged_signals = []
    for batch in batches:
        for signal in batch.signals:
            if signal.summary not in seen_summaries:
                seen_summaries.add(signal.summary)
                merged_signals.append(signal)
    final_batch = MarketSignalBatch(query=query, signals=merged_signals, generated_at="")

    # url=None here: signals already carry their own per-document URL above,
    # and _finalize_payload only overwrites source_url when a url is given.
    return {
        "result": _finalize_payload(query, final_batch, None),
        "token_usage": total_usage,
    }


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


def build_crawl_graph():
    """Same shape as build_graph(), but fetches a known URL (agent/crawler.py:
    crawl4ai's lightweight HTTP strategy, falling back to its Playwright-based
    strategy for JS-heavy sites) instead of running an open-ended search —
    for official/structured sources where the fact reliably lives at one
    stable page. A content_gate stage sits between the fetch and the
    structuring call, rejecting unusable content (near-empty, a WAF block
    page, a scan with a broken OCR layer) for free before any LLM spend."""
    graph = StateGraph(AgentState)

    graph.add_node("checkpoint_gate", checkpoint_gate)
    graph.add_node("crawl", _crawl_node)
    graph.add_node("content_gate", _content_gate_node)
    graph.add_node("structure", _structure_node)

    graph.add_edge(START, "checkpoint_gate")
    graph.add_conditional_edges(
        "checkpoint_gate", _route_after_gate, {"search": "crawl", END: END}
    )
    graph.add_edge("crawl", "content_gate")
    graph.add_conditional_edges(
        "content_gate", _route_after_content_gate, {"continue": "structure", END: END}
    )
    graph.add_edge("structure", END)

    return graph.compile(checkpointer=MemorySaver())


def build_multi_pdf_graph():
    """Same shape as build_crawl_graph(), but for sources whose content
    would blow Groq's per-request token ceiling as a single structure call
    — either several documents (agent/crawler.py's SITE_CONFIGS
    pdf_link_limit > 1, source config's "multi_pdf": True) or one oversized
    document/page split into chunks (source config's "chunked": True).
    Fetches/splits into pieces, structures each on its own call, then
    merges into one final result. A content_gate_multi stage drops each
    unusable piece individually before structuring (one bad PDF shouldn't
    block the rest), only rejecting the whole item if nothing usable
    survives."""
    graph = StateGraph(AgentState)

    graph.add_node("checkpoint_gate", checkpoint_gate)
    graph.add_node("crawl_multi", _crawl_multi_node)
    graph.add_node("content_gate_multi", _content_gate_multi_node)
    graph.add_node("structure_multi", _structure_multi_node)

    graph.add_edge(START, "checkpoint_gate")
    graph.add_conditional_edges(
        "checkpoint_gate", _route_after_gate, {"search": "crawl_multi", END: END}
    )
    graph.add_edge("crawl_multi", "content_gate_multi")
    graph.add_conditional_edges(
        "content_gate_multi", _route_after_content_gate, {"continue": "structure_multi", END: END}
    )
    graph.add_edge("structure_multi", END)

    return graph.compile(checkpointer=MemorySaver())
