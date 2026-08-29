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
| v0.5 — Web crawler (JS-heavy sources) | 🚧 Planned, not yet built |
| Live end-to-end `/trigger` run (real spend) | ⬜ Not run |

## Known temporary state (fix before a real full run)

- **`service.py` currently limits `TOPICS` to the last 10 entries** (a `# TEMP` line testing the incremental-save/rate-limit fix on a smaller batch) — out of 21 real topics, only 10 run. Delete that one line once you're ready for a full run.
  - *Plain terms: right now a real trigger only checks 10 of the 21 topics on the list, on purpose, to keep test runs cheap. Someone needs to remove that limit before the real thing runs for real.*

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

## v0.5 — Web crawler for JS-heavy sources (🚧 planned, not yet built)

Full design in `MVP0_PLAN.md`'s matching revision section. Short version: `customs.gov.vn` (and future sites like it) need real browser rendering, which `TavilyExtract` can't do. `enhance.md` (repo root, user's own research notes) is the design basis — a tiered crawler: cheap static fetch + `trafilatura` first, Playwright (headless Chromium) fallback only when needed, with optional per-site `SITE_CONFIGS` overrides.

**Simplified during planning:** since the crawler's tiered fetch is a strict superset of `TavilyExtract`'s job for a known URL (and free instead of costing credits), `TavilyExtract` is retired rather than kept alongside it — every `SOURCES` entry routes through the crawler uniformly, no `method` field needed. Trade-off: gives up Tavily's managed anti-bot/proxy handling — accepted since the 3 current sources are plain government pages with no anti-bot fighting back.

- [ ] Install `playwright`, `trafilatura`, `beautifulsoup4`, `lxml` + `playwright install chromium` — **blocked, install command was rejected; reason not yet given**
- [ ] `agent/crawler.py` (new) — `crawl(url)`, `SITE_CONFIGS`, static/Playwright fetch helpers
- [ ] `agent/graph.py` — remove `TavilyExtract` import, `_extract_node`, `build_extract_graph()`; add `_crawl_node` + `build_crawl_graph()`
- [ ] `service.py` — `SOURCES` loop uses `build_crawl_graph()` for every entry, no branching
- [ ] `requirements.txt` — add the 4 new dependencies

### Verification (once built)
- [ ] Import/build sanity check
- [ ] Cheap check: `crawl()` against a plain static page (e.g. Wikipedia) — confirms static+trafilatura path before touching Playwright
- [ ] Live check against `customs.gov.vn` — confirms the Playwright fallback actually returns real text
- [ ] Live check that the 3 already-confirmed sources (SBV rates, SBV FX, GSO CPI) still work via the crawler's static path — confirms retiring `TavilyExtract` didn't lose coverage
- [ ] Decide with the user what fact to pull from `customs.gov.vn` before adding it as a permanent `SOURCES` entry

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
