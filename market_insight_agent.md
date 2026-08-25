# Market Insight Agent — Project Brief

## Overview

The Market Insight Agent is the entry point of a multi-agent pipeline built with LangGraph. Its sole responsibility is to surface **raw, factual market signals** — it does not interpret, categorize, or package them. Downstream agents consume its output for further processing.

## Goals

- Continuously gather and structure factual market signals (pricing changes, demand shifts, competitor activity, availability, etc.)
- Provide clean, verifiable output that downstream agents can trust without re-validation
- Operate reliably as the first stage of a larger agent pipeline intended for eventual internal deployment

## Non-Goals

- **No interpretation or tagging** — demand category tagging and bundle/offer evaluation are handled by a separate **combo/offer agent** downstream
- Not a decision-making or recommendation engine — strictly signal surfacing

## Architecture

- **Framework:** LangGraph
- **Position in pipeline:** top of the stack — output feeds directly into the combo/offer agent
- **Middleware:** checkpoint gates wrap model calls without modifying core agent logic (validation/guardrails at the call boundary, not baked into the agent's reasoning)
- **State management:**
  - `MemorySaver` — in-RAM checkpointing for development
  - `SqliteSaver` / `PostgresSaver` — persistent checkpointing for production
  - `thread_id`-based session isolation across runs

## Tool Integration

- **Web search:** Tavily (chosen — LangChain-ecosystem default). Exa and Brave remain candidates if freshness/cost trade-offs demand a change.
- **MCP:** tools integrated via Model Context Protocol servers where possible, for reusable, standardized tool access across the pipeline

## Model Provider

- **MVP0: Groq-hosted open model** (`langchain-groq`, default `openai/gpt-oss-120b`, overridable via `GROQ_MODEL`) — chosen for lowest cost. Anthropic/OpenAI/Gemini/DeepSeek were considered and deferred.
  - Originally defaulted to `llama-3.3-70b-versatile`; Groq decommissioned it (and `llama-3.1-8b-instant`) on 2026-08-16. Switched to Groq's recommended replacements.

## Pipeline Flow

1. Ingest trigger — `POST /trigger` on `service.py` (called by a real scheduler/cron, or manually); `main.py` remains available for on-demand single-query runs
2. Query resolution — trigger runs every topic in `agent/topics.py` (a predefined, editable list; current starter set covers Vietnam banking-sector macro monitoring)
3. Checkpoint gate — pre-call validation/guardrail
4. Search — deterministic Tavily call per topic (no LLM decision on whether/what to search, since the topic list already fixes the query)
5. Structure — one LLM call synthesizes search results into the `MarketSignal`/`MarketSignalBatch` schema
6. Output persisted to `data/signals.jsonl` and returned as the HTTP response, ready to hand off to the combo/offer agent

## Open Questions

- Final choice of web search provider (latency vs. freshness trade-off)
- Inference parameter tuning (temperature, top-p, caching strategy)
- Production persistence backend (Sqlite vs. Postgres)
- Deployment surface and access pattern within the firm

## Status

Actively in development. Current focus: LangGraph middleware — specifically how checkpoint gates wrap model calls cleanly without touching core agent logic.

---
*This brief reflects the project as discussed so far — update as scope and architecture decisions solidify.*