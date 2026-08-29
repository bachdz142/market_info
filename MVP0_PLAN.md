# MVP0 — Market Insight Agent Demo

## Context

`market_insight_agent.md` defines this project as the entry point of a multi-agent pipeline built on LangGraph: it surfaces raw, factual market signals (no interpretation/tagging) for a downstream combo/offer agent. Today the repo is just that brief plus PyCharm boilerplate `main.py` — nothing is implemented and no packages are installed. This plan builds the smallest working slice (MVP0) that proves the architecture end-to-end: checkpoint-gate → tool-calling model → structured output, on `MemorySaver` with `thread_id` isolation, runnable from the CLI.

Decisions confirmed with the user for this MVP0:
- **Model provider: Groq-hosted open model** (not Anthropic, despite `.env.example`/`requirements.txt` currently assuming it) — cheapest option, chosen explicitly over Claude/OpenAI/Gemini/DeepSeek.
- **Checkpoint gate: basic real content checks**, not a no-op stub — reject empty and excessively long queries before any model call happens.
- **API keys**: user will populate `.env` themselves (Groq + Tavily) — build against live calls, no dry-run/mock mode needed.

## Architecture (MVP0)

```
START → checkpoint_gate → (reject) → END
                 ↓ (pass)
              agent (ChatGroq + Tavily tool bound)
                 ↓ tool_calls?  → tools (ToolNode) → agent (loop)
                 ↓ no tool_calls
              structure (parses final answer into MarketSignalBatch)
                 ↓
                END
```

- **Framework:** LangGraph `StateGraph`, hand-rolled nodes (not `create_react_agent`) so the checkpoint gate is visibly a separate node wrapping the model call, matching the brief's "middleware wraps model calls without modifying core agent logic."
- **Model:** `langchain-groq` `ChatGroq`, default model `openai/gpt-oss-120b` (tool-calling capable, low cost), overridable via `GROQ_MODEL` env var for even cheaper/faster options like `openai/gpt-oss-20b`. (Originally `llama-3.3-70b-versatile`/`llama-3.1-8b-instant` — Groq decommissioned both on 2026-08-16; these are the vendor-recommended replacements.)
- **Tool:** `langchain-tavily` `TavilySearch`, executed via `langgraph.prebuilt.ToolNode`; routing via `langgraph.prebuilt.tools_condition`.
- **State/persistence:** `langgraph.checkpoint.memory.MemorySaver`, graph compiled with `checkpointer=`, invoked with `config={"configurable": {"thread_id": ...}}`.
- **Structured output:** Pydantic `MarketSignal`/`MarketSignalBatch` schema, produced via a final `.with_structured_output(...)` call over the agent's synthesized answer — this is the "clean, verifiable output" downstream agents consume.

## Files

**New package `agent/`:**
- `agent/schema.py` — `MarketSignal` (signal_type: price_change/demand_shift/competitor_activity/availability/other, summary, source_url, observed_at, confidence: low/medium/high) and `MarketSignalBatch` (query, signals, generated_at).
- `agent/gate.py` — `checkpoint_gate(state)`: rejects empty/whitespace-only query and queries over a max length (e.g. 2000 chars), setting `gate_passed`/`gate_reason` on state rather than raising — keeps the rejection path visible in the graph/output instead of a bare exception.
- `agent/graph.py` — builds `AgentState` (TypedDict: `messages` w/ `add_messages` reducer, `query`, `gate_passed`, `gate_reason`, `result`), wires the 4 nodes (`checkpoint_gate`, `agent`, `tools`, `structure`) and conditional edges described above, compiles with `MemorySaver`. Exposes `build_graph()`.

**Modified:**
- `requirements.txt` — swap `langchain-anthropic` → `langchain-groq`.
- `.env.example` — swap `ANTHROPIC_API_KEY` → `GROQ_API_KEY`, keep `TAVILY_API_KEY`.
- `market_insight_agent.md` — update Architecture/Tool Integration sections to record the Groq decision (per the doc's own "update as scope and architecture decisions solidify" note).
- `main.py` — replace PyCharm boilerplate with a CLI: `python main.py "<query>" [--thread-id ID]`, loads `.env`, builds the graph, invokes it, pretty-prints the resulting `MarketSignalBatch` JSON (or the gate rejection reason if the query was rejected).

## Verification

1. `.venv/bin/pip install -r requirements.txt`
2. Sanity-import check without live keys: `.venv/bin/python -c "import agent.graph"` — catches wiring/syntax errors immediately.
3. Once the user has added `GROQ_API_KEY` and `TAVILY_API_KEY` to `.env`:
   - Empty-query rejection path: `python main.py ""` → should short-circuit at the gate, no model call, prints rejection reason.
   - Golden path: `python main.py "recent pricing changes in the cloud GPU market"` → should run gate → agent → tools → agent → structure, and print a JSON `MarketSignalBatch` with one or more signals.
   - Session isolation: run twice with the same `--thread-id` and confirm (via a quick checkpoint inspection or just distinct thread IDs behaving independently) that state doesn't bleed across threads.

---

## Revision: Trigger-Based Execution

### Why

The original MVP0 above ran as a CLI needing a human-typed question and a human watching stdout. That doesn't match the brief's own "Ingest trigger/query (**scheduled** or on-demand)" intent, or how this will actually be used: unattended, on a schedule/trigger, over a fixed set of banking-sector macro topics, with results persisted somewhere — not printed to a terminal nobody is watching.

This revision also simplifies the LangGraph pipeline itself (token-cost-driven — see design note below): `checkpoint_gate → agent ↔ tools → structure` becomes `checkpoint_gate → search → structure`.

### Decisions confirmed

- **Predefined topics, not free text** — the question comes from a fixed, editable list, not typed per-run.
- **All topics run per trigger** — one call researches every topic back-to-back, not one-at-a-time rotation.
- **Synchronous response** — the endpoint waits and returns full results (acceptable for MVP0; a call may take tens of seconds due to live search+LLM calls).
- **Output persisted** — each trigger run appends one record (all topics) to a local JSON-lines file.
- **Trigger mechanism = HTTP API** — a `POST /trigger` endpoint the user or a real external scheduler/cron calls; no in-session demo-scheduling wired up.
- **Topic domain: banking-sector macro monitoring** — user works at a bank. Market confirmed as **Vietnam** — State Bank of Vietnam (SBV) is the relevant central bank/regulator, not the Fed.

### Design note: search trigger is now deterministic, not agentic (cost-driven change)

Follow-up decision — user is token-constrained. Since every topic's query is already known in advance from `agent/topics.py`, there's no case here where an LLM needs to *decide* what/whether to search — that's only valuable for genuinely open-ended questions. So the agentic `agent ↔ tools` decision loop is removed from `agent/graph.py` and replaced with a direct, always-executed Tavily call per topic. The LLM still does exactly one job — reading raw search results and extracting them into the structured `MarketSignal` format — but that's now **one LLM call per topic**, not a multi-turn reasoning loop. Cuts Groq token usage substantially (Tavily's own cost is separate/unaffected).

This changes the **existing, already-built** `agent/graph.py` — `main.py`'s CLI shares the same graph, so it becomes cheaper/simpler too.

`agent/graph.py` changes:
- Remove `_agent_node`, `ToolNode`, `tools_condition`, and the tool-binding/loop.
- Add `_search_node(state)`: calls `TavilySearch(max_results=5).invoke(state["query"])` directly — no LLM, always runs once.
- `_structure_node(state)`: reads `state["search_results"]` and makes exactly one `.with_structured_output(MarketSignalBatch)` call.
- `AgentState`: drop `messages`/`add_messages`, add `search_results`.
- Edges: `START → checkpoint_gate → (reject) → END`, `checkpoint_gate → (pass) → search → structure → END`.

Still deferred, separate scope: a true deterministic *data* fetch (a real rates/FX data API instead of web search) for `quant`-tagged topics — needs a data-source decision and likely a new API key. The `kind` tag in `agent/topics.py` stays for that future step. What's changing now is only *how the search tool gets invoked* (always, directly — not LLM-decided), not *what source it hits*.

### Architecture

```
 caller (curl / cron / real scheduler)
        │  POST /trigger
        ▼
 service.py (FastAPI)
        │  for each topic in agent/topics.py:
        │      run build_graph() → checkpoint_gate → search (deterministic Tavily call) → structure (1 LLM call)
        ▼
 agent/store.py — append_run(): writes one JSON-line record
 (all topics' MarketSignalBatch + trigger timestamp) to data/signals.jsonl
        │
        ▼
 HTTP response: same JSON payload, returned to caller
```

### Files

**New:**
- `agent/topics.py` — `TOPICS: list[dict]`, each `{"id": str, "kind": "quant" | "qualitative", "prompt": str}`. Starter set (Vietnam market):
  - `quant`: SBV refinancing/rediscount rate · VND interbank rate (VNIBOR) · USD/VND exchange rate & SBV central rate · CPI/inflation (GSO) · Vietnam government bond yields · SBV credit-growth quota ("room")
  - `qualitative`: peer bank earnings/guidance commentary (Vietcombank, Techcombank, VPBank, MB, ACB, BIDV, VietinBank, etc.) · SBV regulatory developments (Basel II/III rollout, NPL circulars, foreign ownership limits) · credit rating agency actions on Vietnam sovereign/banks · foreign strategic investment/M&A in Vietnamese banks · real estate/corporate bond market stress signals
- `agent/store.py` — `append_run(record: dict)`: ensures `data/` exists, appends one JSON line to `data/signals.jsonl`.
- `service.py` — FastAPI app: `POST /trigger` runs `build_graph()` once per topic (fresh `thread_id` per topic per call), collects each `MarketSignalBatch`, persists via `agent.store.append_run(...)`, returns the same record as JSON. `GET /health` for liveness. Run via `python service.py` (binds `127.0.0.1:8000`).

**Modified:**
- `agent/graph.py` — agentic loop replaced with deterministic search, per the design note above.
- `requirements.txt` — add `fastapi`, `uvicorn[standard]`.
- `.gitignore` — add `data/`.
- `market_insight_agent.md` — update Pipeline Flow: trigger is now an HTTP endpoint driving a predefined topic list; search is deterministic, not agentic; CLI remains for on-demand use.

**Unchanged:** `agent/schema.py`, `agent/gate.py`, `main.py` (file itself — behavior changes only via the shared graph).

### Known caveat

`MemorySaver` keeps checkpoints in RAM for the life of the `service.py` process — memory grows slowly with each trigger over a long-running deployment. Fine for MVP0; revisit (thread cleanup or a persistent checkpointer) if this runs unattended long-term.

### Verification

1. `.venv/bin/python -m pip install -r requirements.txt`
2. Start the service: `.venv/bin/python service.py`
3. `curl -X POST http://127.0.0.1:8000/trigger` → JSON with one result per topic in `agent/topics.py`
4. Confirm `data/signals.jsonl` gained exactly one new line matching that response
5. `curl http://127.0.0.1:8000/health` → ok
6. Confirm `main.py` still works unchanged for a manual one-off query (regression check)

## Revision: Web Crawler for JS-Heavy Sources

### Why

`agent/sources.py` (added in a later revision, not yet documented here — see note below) only supports `TavilyExtract`, a paid API that fetches+cleans a URL. That covers official sources like SBV's rate pages and GSO's CPI page, but one confirmed counter-example exists: `customs.gov.vn` was tested live and `TavilyExtract` genuinely cannot read it — it's JavaScript-rendered with no content in the raw HTML. `enhance.md` (repo root) is the user's own consolidated research notes on solving this generically: a tiered crawling toolchain (cheap static fetch first, real headless browser only when needed) plus a per-site config system for sites needing precise extraction.

### Decisions confirmed

- **Full system per `enhance.md`**, not a one-off fix — `agent/crawler.py` with `SITE_CONFIGS`, `trafilatura` as the generic-extraction baseline, Playwright as the JS-rendering fallback.
- **Playwright over Selenium** — no existing Selenium infra to justify it, and Playwright's cleaner API fits better (per `enhance.md` §1). This supersedes the earlier "no Selenium" framing from the URL-extraction revision — the actual fallback choice made was Playwright.
- **Install Playwright + a real Chromium binary** — the heaviest dependency this project has added; required either way to handle JS-heavy sites.
- **`TavilyExtract` retired, not kept alongside the crawler** — `agent/crawler.py`'s tiered design (static fetch + Playwright fallback) is a strict superset of what `TavilyExtract` does for a known URL, and does it for free instead of costing Tavily credits. `build_extract_graph()`/`_extract_node()` (shipped in the URL-extraction revision) are removed as dead code once every `SOURCES` entry routes through the crawler instead. Trade-off accepted: Tavily's managed infra handles proxy rotation/anti-bot evasion the plain crawler doesn't — hasn't mattered for the 3 current sources (plain government pages), but could for a future site that actively blocks scrapers. The pattern is simple enough to re-add per-site later if needed.

**Explicitly out of scope** (escalation tiers `enhance.md` itself says aren't needed yet): Scrapy/scraping-frameworks, scraping-as-a-service, login walls/CAPTCHA/pagination handling, page-fetch caching, automated robots.txt/ToS checking (stays a manual per-site step).

### Architecture

```
 agent/sources.py entry: {"id", "kind", "url", "prompt"}  (unchanged shape)
        │
        ▼
 build_crawl_graph(): checkpoint_gate → crawl (agent/crawler.py) → structure
                                              │
                                              ▼
                          crawl(url): static fetch + trafilatura (cheap, default)
                          → escalate to Playwright only if SITE_CONFIGS says needs_js,
                            or the static path yields too little content
```

Every source goes through the same graph — `SITE_CONFIGS` inside `agent/crawler.py` decides static-vs-JS per site, so `service.py`'s `/trigger` loop needs no per-source branching.

### Files

**New:** `agent/crawler.py` — `crawl(url)`, `SITE_CONFIGS` (per-site `needs_js`/`wait_selector`/`content_selector` overrides), `_fetch_static`/`_fetch_js`/`_apply_selector` helpers.

**Modified:**
- `agent/graph.py` — remove `TavilyExtract` import, `_extract_node`, `build_extract_graph()`; add `_crawl_node`, `build_crawl_graph()`.
- `service.py` — `SOURCES` loop uses `build_crawl_graph()` for every entry, no branching.
- `requirements.txt` — add `playwright`, `trafilatura`, `beautifulsoup4`, `lxml`.

**Not changed:** `agent/sources.py` — no `method` field needed after all.

### Verification

1. Import/build sanity check (free): `build_crawl_graph()` compiles; `agent.crawler` imports cleanly.
2. Cheap check: `crawl()` against a plain static page (e.g. Wikipedia) confirms the static+trafilatura path works before touching Playwright.
3. Live check against `customs.gov.vn` (the confirmed JS-heavy case) — confirms the Playwright fallback returns real text instead of an empty shell.
4. `customs.gov.vn` is not added as a permanent `SOURCES` entry until its actual extraction prompt is decided — it wasn't part of the original topic list.

### Doc note

`MVP0_PLAN.md` was not updated for the two revisions between "Trigger-Based Execution" and this one (logging/token-tracking, and URL-based extraction via `agent/sources.py`/`TavilyExtract`) — only `DEVELOPMENT_PLAN.md` tracked those. See `CHANGELOG.md` for the full dated history including those gaps.
