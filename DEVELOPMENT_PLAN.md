# Development Plan — Market Insight Agent MVP0

Progress tracker for the MVP0 build. Architecture/design rationale lives in
`MVP0_PLAN.md`; dated technical history lives in `CHANGELOG.md`; this file
tracks build status phase by phase. Version labels match `CHANGELOG.md`.

**In plain terms:** this thing researches a standing list of Vietnam
banking-sector topics (rates, inflation, competitor moves, seasonal
campaigns...) and hands back a clean, organized list of facts — no
opinions or recommendations, since a separate downstream tool is the one
that interprets and acts on them.

## Status at a glance

| Phase | Status |
|---|---|
| v0.1 — Initial MVP0 | ✅ Done |
| v0.2 — Trigger-based execution | ✅ Done |
| v0.3 — Logging + token tracking | ✅ Done |
| v0.4 — URL-based extraction (official sources) | ✅ Done |
| v0.5 — Web crawler (`crawl4ai`, not the originally-planned `trafilatura` design) | ✅ Done |
| v0.6 — Layer 1 quant bank benchmarks (`source_plan_mvp0.md`) | 🚧 Partial — 2 of ~9 new sources verified |
| Live end-to-end `/trigger` run (real spend) | ⬜ Not run |

## Known temporary state (fix before a real full run)

- **`service.py` currently limits `TOPICS` to the last 10 entries** (a `# TEMP` line testing the incremental-save/rate-limit fix on a smaller batch) — out of 21 real topics, only 10 run. Delete that one line once you're ready for a full run.
  - *Plain terms: right now a real trigger only checks 10 of the 21 topics on the list, on purpose, to keep test runs cheap. Someone needs to remove that limit before the real thing runs for real.*
- **`GROQ_API_KEY` in `.env` is expired** (`groq.AuthenticationError: 401 — expired_api_key`) — blocks every LLM-dependent check: the new pytest suite's source tests, and live-verifying any further Layer 1 sources. Rotate the key before continuing v0.6 work.

---

## v0.1 — Initial MVP0

- [x] `.env` — Groq + Tavily API keys written (gitignored, not committed)
  - *Plain terms: your two access keys/passwords are stored in a private file that never gets shared or uploaded anywhere.*
- [x] `agent/schema.py` — `MarketSignal` (signal_type, summary, source_url, observed_at, confidence) + `MarketSignalBatch` (query, signals, generated_at) Pydantic models
  - *Plain terms: a fixed, predictable format for results — every fact found gets recorded the same way every time.*
- [x] `agent/gate.py` — `checkpoint_gate()`: rejects empty or >2000-char queries before any model call
  - *Plain terms: a gatekeeper that checks your question before anything else happens — a bad question gets stopped right there, no time or money wasted.*
- [x] `agent/graph.py` — initial `StateGraph` wiring: `checkpoint_gate → agent (ChatGroq + Tavily) ↔ tools → structure → END`, compiled with `MemorySaver`
  - *Plain terms: the research brain — reads your question, searches the web, writes up findings, converts that into the clean structured format.*
- [x] `main.py` — CLI (`python main.py "<query>" [--thread-id ID]`), prints structured JSON or gate-rejection reason
  - *Plain terms: type one line with your question, get results printed back.*
- [x] Model provider: Groq (cheapest option, chosen over Anthropic/OpenAI/Gemini/DeepSeek)
- [x] Fixed Python 3.9 incompatibility (`str | None` syntax needs 3.10+) — switched to `typing.Optional`/`typing.List`
  - *Plain terms: this computer's Python version is older than the code first assumed; a couple of lines needed rewriting in an older-compatible style.*
- [x] Fixed broken `pip` shebang in `.venv` (stale path from a differently-named old project) — worked around with `python -m pip install`

### Verification
- [x] Import/build sanity check
- [x] Empty-query rejection path
- [x] Golden path (live Groq + Tavily call) — confirmed working
- [x] Thread-id session isolation spot check

---

## v0.2 — Trigger-based execution

Full rationale/diagram in `MVP0_PLAN.md`. Short version: the CLI needed a human to type a question and watch the screen. Real usage is unattended — fired on a schedule, over a fixed list of banking-macro topics, results saved instead of printed.

- [x] `agent/topics.py` — fixed list of banking-macro questions for the **Vietnam** market (started at 11 topics — later expanded, see v0.3)
  - *Plain terms: instead of typing a question every time, there's a standing list of Vietnam banking topics it always checks.*
- [x] `agent/store.py` — saves each run's results as JSON lines (`data/signals.jsonl`)
  - *Plain terms: since nobody's watching a screen on a timer, results get saved to a file, so nothing is lost.*
- [x] `service.py` — FastAPI service, `POST /trigger` (fires a full run) + `GET /health`
  - *Plain terms: hitting one web address kicks off a full research run across every topic and hands back the results.*
- [x] `agent/graph.py` reworked — AI no longer decides *whether* to search; it always searches each topic directly, then reads results once to write up findings (`checkpoint_gate → search → structure`)
  - *Plain terms: token budget is tight, so this cuts the AI "thinking about whether to search" step — since the topic list already says what to look up, there's nothing to decide.*
- [x] `requirements.txt` / `.gitignore` updated (`fastapi`, `uvicorn`, `data/` ignored)

### Verification
- [x] Import/build sanity check — graph builds with 3 nodes, no live calls
- [x] Empty-query gate rejection re-verified against new graph shape
- [ ] **Live end-to-end trigger run** — real Groq + Tavily spend. Superseded by the same open item under v0.3 (topic list grew since this was written).

---

## v0.3 — Logging + token tracking

No new framework added (evaluated and skipped MLflow/Langtrace/LangSmith as overkill for MVP0) — built on Python's built-in `logging` module and LangChain's built-in per-call token counts.

- [x] `agent/logging_config.py` — `setup_logging()`: logs to terminal + `data/app.log`
  - *Plain terms: progress used to be scattered `print()` lines that vanished when the terminal closed. Now everything's timestamped and saved to a file.*
- [x] `agent/gate.py` — logs every gate pass/reject with the reason
- [x] `agent/graph.py` — logs search/AI-call timing, captures exact token count (input/output/total) per AI call
  - *Plain terms: every AI call now reports back exactly how many tokens it cost, instead of that being invisible.*
- [x] `main.py` / `service.py` — logging on at startup; `service.py` logs one-line progress per topic
- [x] `agent/store.py` (`append_topic_jsonl`/`append_topic_csv`) — **rewritten for incremental, per-item saving** instead of once at the end of the whole run, plus extra CSV columns (per-topic seconds, token counts, error)
  - *Plain terms: this was a real bug fix — a live 21-topic run crashed partway through on a Groq rate limit and lost every result computed so far, because saving only happened at the very end. Now each topic/source saves immediately as it finishes.*
- [x] `service.py` — try/except around each item so one failure doesn't crash the whole `/trigger` request; 30s pacing delay between items (`TOPIC_DELAY_SECONDS`) to reduce how often the rate limit gets hit
- [x] `tqdm` progress bar added to `/trigger` — live progress bar in the console instead of only scrolling log lines
- [x] `agent/topics.py` expanded from 11 → 21 topics (added 10 seasonal/product-launch topics: Tết campaigns, digital banking launches, card promotions, savings products, SME/mortgage/agricultural lending, green finance, bancassurance, year-end bonus effects)
- [x] Import/build sanity check — all modules import cleanly, graph compiles

### Verification
- [x] Confirmed root cause of a real rate-limit crash (Groq's 8,000 tokens-per-minute cap on the free tier) via the actual error message and service logs — documented in `CONCEPTS.md`
- [ ] **Live 21-topic (or fewer, per the TEMP slice) `/trigger` run with the fix in place** — not yet run

---

## v0.4 — URL-based extraction for official sources

- [x] `agent/sources.py` (new) — `SOURCES` list, same shape as `agent/topics.py` (`{"id", "kind", "url", "prompt"}`), for pages where a fact reliably lives at one stable URL instead of needing a search
- [x] `agent/graph.py` — `_extract_node` (`TavilyExtract`, deterministic URL fetch) + `build_extract_graph()`, reusing `checkpoint_gate`/`_structure_node` unchanged
- [x] `service.py` — `/trigger` runs `SOURCES` alongside `TOPICS` in the same call, refactored into a shared `_run_item()` helper
- [x] 3 real sources added, each confirmed via a live `TavilyExtract` test before being committed:
  - `sbv_policy_rate_official` — SBV rediscount/refinancing rate page
  - `usdvnd_rate_official` — SBV USD/VND central exchange rate page
  - `vietnam_cpi_official` — GSO/NSO CPI report page (needed `extract_depth="advanced"`)
  - *Plain terms: instead of guessing these numbers might show up in a web search, the agent now reads them straight from the government's own official page.*
- [x] `customs.gov.vn` tested live and **confirmed `TavilyExtract` cannot read it** (JS-rendered, no content in raw HTML, confirmed with both `"basic"` and `"advanced"` depth) — excluded from `SOURCES`; this became the motivating case for v0.5.
- [x] Import/build sanity check — extract graph compiles, sources import cleanly
- **Superseded by v0.5**: `_extract_node`/`build_extract_graph()`/`TavilyExtract` are being retired once `agent/crawler.py` exists — its tiered design covers everything `TavilyExtract` did, for free instead of costing Tavily credits. See v0.5's design note for the trade-off accepted (losing Tavily's managed anti-bot/proxy handling).

### Verification
- [x] Each of the 3 sources individually confirmed via a real one-off `TavilyExtract` call before being added to code
- [ ] Live `/trigger` run including these sources — not yet run (same open item as v0.3, now covers `TOPICS` + `SOURCES` together)

### Open question
- `agent/topics.py` still has search-based `sbv_policy_rate`, `usdvnd_rate`, `vietnam_cpi` topics covering the same facts as the new `_official` sources — both currently run in the same trigger. Not yet decided whether to retire the search-based versions.

---

## v0.5 — Web crawler for JS-heavy sources (✅ done, via `crawl4ai` — not the originally-planned `trafilatura` design)

Original design (below, historical) was a hand-rolled tiered crawler: static fetch + `trafilatura` first, Playwright fallback when needed. That got built, then replaced mid-flight with `crawl4ai` as the sole fetch mechanism (`docs/adr/0002-crawl4ai-adopted-unconditionally.md`) — the intent to use `crawl4ai` was a standing preference independent of any single incident, not something the `trafilatura` version's shortcomings forced.

<details>
<summary>Original v0.5 design (superseded)</summary>

Full design in `MVP0_PLAN.md`'s matching revision section. Short version: `customs.gov.vn` (and future sites like it) need real browser rendering, which `TavilyExtract` can't do. `enhance.md` (repo root, user's own research notes) is the design basis — a tiered crawler: cheap static fetch + `trafilatura` first, Playwright (headless Chromium) fallback only when needed, with optional per-site `SITE_CONFIGS` overrides.

**Simplified during planning:** since the crawler's tiered fetch is a strict superset of `TavilyExtract`'s job for a known URL (and free instead of costing credits), `TavilyExtract` is retired rather than kept alongside it — every `SOURCES` entry routes through the crawler uniformly, no `method` field needed. Trade-off: gives up Tavily's managed anti-bot/proxy handling — accepted since the 3 current sources are plain government pages with no anti-bot fighting back.

</details>

- [x] Project-wide Python upgrade to 3.11 (from 3.9) — `crawl4ai` needs 3.10+ in practice despite claiming `>=3.9` in its own metadata; built from source via Homebrew (no bottle for this old Intel Mac/macOS 13.2.1), including OpenSSL. `playwright` pinned to `1.60.0` (1.62+ dropped macOS 13 support).
- [x] `agent/crawler.py` rewritten on `crawl4ai` — `AsyncHTTPCrawlerStrategy` (static), default Playwright-based strategy (JS-heavy), `PDFCrawlerStrategy`/`PDFContentScrapingStrategy` (PDFs). `crawl()`/`crawl_parts()`'s public shape unchanged (`crawl_parts()` now also returns each PDF's own URL).
- [x] Found and fixed a real environment bug: this machine's from-source Python 3.11 build never wires OpenSSL to a trust store, and `aiohttp` (used by `crawl4ai`) caches its default SSL context at its own import time — `SSL_CERT_FILE` has to be set before `langchain_groq`/`langchain_tavily` import `aiohttp`, not just before `crawl4ai` runs. Fixed at the top of `service.py` and in a new root `conftest.py`.
- [x] Folded in 4 known bugs while touching this code: multi-PDF signals now carry their own document's URL (not the listing page's); one failed PDF fetch no longer discards the rest; `raw_content` now captures every fetched document, not just the listing page; `agent/store.py`'s `_prepare_csv` is now thread-safe.
- [x] `requirements.txt` — added `crawl4ai`; removed `requests`, `trafilatura`, `pypdf`.
- [x] `docs/adr/0002-crawl4ai-adopted-unconditionally.md` written; `docs/adr/0001-...` marked superseded.

### Verification
- [x] Import/build sanity check — all modified modules import cleanly
- [x] Live check: `crawl()` against a plain static page (GSO CPI, no selector) — real content
- [x] Live check: `crawl()` with `needs_js=True` (`customs.gov.vn`) — Playwright path still works post-migration
- [x] Live check: `crawl_parts()` against the SBV press-release multi-PDF source — real content, and survives 2 of 3 PDFs failing (bug #2 fix confirmed under real WAF flakiness)
- [x] End-to-end live run through `build_multi_pdf_graph()` (fetch → structure → merge) — confirmed working once the SSL fix and a valid Groq key were in place
- [ ] The 3 already-confirmed v0.4 sources (SBV rates, SBV FX, GSO CPI) are currently commented out in `agent/sources.py` (predates this migration, reason not re-verified this pass) — not re-tested via the new crawler

---

## v0.6 — Layer 1 quant bank benchmarks (`source_plan_mvp0.md`) (🚧 partial)

`source_plan_mvp0.md` (formal MVP0 spec) defines 4 data layers for Annual Planning's Competitor & Market Analysis section. Decided to build **Layer 1 only** (quant bank benchmarks), fully verified, rather than a shallow pass across all 4 — each source needs real per-site verification work (confirmed ~10-20 tool calls per source). Full spec: `.scratch/layer-1-quant-benchmarks/spec.md`. Layers 2-4 explicitly deferred, not dropped.

- [x] `agent/schema.py` — `MarketSignal` extended with `source_code`, `reference_period`, `data_basis` (`standalone`/`consolidated`/`not_applicable`), `actual_proxy_forecast` (`actual`/`proxy`/`forecast`), `forecast_org` (required only when forecast) — the mandatory audit metadata the spec requires.
- [x] `agent/graph.py`'s `STRUCTURE_SYSTEM_PROMPT` — added `METADATA_INSTRUCTION` covering the new fields.
- [x] `agent/store.py` — CSV output gained matching columns.
- [x] `agent/sources.py` — added `role` field (`citable`/`aggregator`, orthogonal to the existing `kind`) to all entries.
- [x] 2 new Layer 1 sources added, live-verified: `sbv_portal_statistics`, `iav_bancassurance`.
- [ ] **5 bank investor-relations pages** (Techcombank, Vietcombank, BIDV, MBBank, ACB) — investigated, not added. Each bank's real figures live behind linked PDF reports; each site's CMS needs its own `content_selector`/`pdf_link_selector` (the same kind of per-site discovery `sbv.gov.vn`'s press-release source needed). Not yet nailed down for any of the 5.
- [ ] **Vietstock aggregator** (per-ticker document pages, ×5 banks) — investigated, not added. Document table didn't render even after 60s with JS-rendering enabled; may be gated behind login/anti-bot rather than just needing a longer wait. Possible dead end — worth a fresh look before sinking more time in.
- [ ] `dttktt.sbv.gov.vn` — confirmed bot-blocked (both independently and per the spec); intentionally excluded, manual-only.
- [x] `tests/` (new) — first automated test suite for this project (`pytest`), at the direct-graph-invocation seam. `test_sources.py` (one test per Layer 1 source), `test_bug_fixes.py` (targeted tests for the 4 bugs above — 3 of 4 are pure/offline and passing; the network+LLM ones are blocked, see below).

### Verification
- [x] Import/build sanity check
- [x] `pytest` collection — all 7 tests collected with no import errors
- [x] 3 of 7 tests run and pass: `crawl_parts` PDF-failure resilience (real network, no LLM), `raw_content` combining (pure function), `_prepare_csv` thread-safety under 20 concurrent threads (pure function)
- [ ] **Blocked on `GROQ_API_KEY`**: the remaining 4 tests (one per Layer 1 source + the multi-PDF source-URL bug test) need a live LLM call and fail with `groq.AuthenticationError: expired_api_key`. Rerun once the key is rotated.
- [ ] Full `/trigger` run limited to Layer 1 sources — not yet run (same blocker)

---

## Maintenance fixes

- [x] Swapped AI model: Groq shut down `llama-3.3-70b-versatile` (and `llama-3.1-8b-instant`) on 2026-08-16. Now defaults to `openai/gpt-oss-120b` (overridable via `GROQ_MODEL`).
  - *Plain terms: the specific AI model this was built on got discontinued by its provider right after setup. Swapped to the provider's official suggested replacement.*
- [x] Fixed stale comment in `.env.example` still referencing the deprecated `llama-3.3-70b-versatile` as the default.

## Docs added along the way

- [x] `README.md` — setup/run/output overview
- [x] `CONCEPTS.md` — deep-dive explanations (structured output mechanism, rate limiting, `.venv`/`uv`/`conda`)
- [x] `CHANGELOG.md` — dated technical history (v0.1–v0.4 + unreleased v0.5)

## Open follow-ups (not in current scope)

- Persistence backend: `MemorySaver` only (in-RAM, resets each run). SQLite/Postgres deferred until signals need to survive restarts.
  - *Plain terms: results only exist while the program is running — nothing is saved permanently at the database level yet.*
- MCP-based tool integration (noted as a future goal in `market_insight_agent.md`, not part of MVP0).
- Whether to retire the search-based quant topics now that official-source equivalents exist (see v0.4's open question).
- Real deployment target has shifted: user plans to deploy this at their company as a **Databricks App**, using a **Databricks-hosted LLM endpoint** (likely Claude Haiku/Sonnet) instead of Groq, and Unity Catalog/Delta storage instead of local files. Not yet started — noted here so future work heads in the right direction. See conversation history for the full breakdown of what changes (model provider, auth, storage) vs. what stays the same (FastAPI app shape, `.with_structured_output` usage, graph structure).
