# Changelog

Dated, terse technical record of this project's revisions. Not strict
semver — this is an internal MVP0 demo, versioned by milestone rather than
package release. For plain-English progress tracking see
`DEVELOPMENT_PLAN.md`; for architecture/design rationale see `MVP0_PLAN.md`.

## Unreleased — LLM provider fallback chain

- Added `agent/llm_fallback.py`: the structuring step's model call is now
  Groq (primary) → Gemini → Mistral → OpenRouter, via LangChain's
  `.with_fallbacks()`, instead of a bare `ChatGroq` call — so a Groq
  outage (rate limit, network-level block, anything) no longer blocks
  extraction entirely. Drop-in: `agent/graph.py`'s `_structure_one()` is
  the only caller and its own contract/logic is unchanged; every
  extraction node above it needed no changes at all.
- A schema-validation failure (not just an HTTP/rate-limit exception) now
  also triggers the next provider — `ExtractionValidationError`, raised
  when `with_structured_output(...)`'s `parsed` comes back `None`, since
  providers differ in how strictly they honor JSON/tool-calling mode and a
  "successful" call with unparseable output is still a failure.
- Each provider call now logs to `data/llm_provider_calls.csv`
  (timestamp, provider, model, success, query preview, error) — which
  provider actually served (or attempted) each call, for tracing
  extraction-quality shifts between providers later.
- Real findings from live-testing each provider before trusting the
  chain, not just picking from descriptions:
  - `gemini-2.5-flash` (the originally-planned default) is dead — Google's
    API 404s and points at `gemini-3.6-flash` instead.
  - OpenRouter's free tier needed 3 real attempts: `minimax/minimax-m2.7:free`
    wraps JSON in markdown fences and fails strict validation every time;
    `inclusionai/ling-3.0-flash-fin:free` (looked like the best fit on
    paper — finance-focused) has a backing provider that rejects
    structured-output requests outright; `nvidia/nemotron-3-super-120b-a12b:free`
    works, but only with `method="json_mode"` *and* the schema spelled out
    directly in the prompt — `json_mode` alone still returned `parsed=None`
    every time without that.
  - Every provider call now has a 30s timeout and no internal retries — an
    OpenRouter free-tier model sat with zero output for 4+ minutes with no
    timeout set; a hung provider must fail fast into the next one, not
    block the whole chain.
  - A live Groq `403 Access denied. Please check your network settings`
    was traced to the developer's VPN being on, not a real service issue —
    confirmed by turning it off. Unrelated to the fallback feature itself,
    but a good real test: the chain correctly fell through to Gemini while
    this was happening, without needing to know why Groq was failing.
- New dependencies: `langchain-google-genai`, `langchain-mistralai`,
  `langchain-openai` (the last one used for OpenRouter too, via its
  OpenAI-compatible endpoint — no separate OpenRouter package needed).
- Added `tests/test_llm_fallback.py`: deterministic tests of the cascade
  and validation logic using fake chat models (fully offline) — a
  different thing than mocking away real provider behavior, which was
  separately live-verified for all four providers by hand first.

## Unreleased — crawl4ai migration + Layer 1 quant benchmarks

Supersedes the previous "Web crawler for JS-heavy sources" entry below
before it ever shipped — `agent/crawler.py`'s tiered fetch stack was
replaced with `crawl4ai` rather than built on `requests`/`trafilatura`/
direct Playwright/`pypdf`. See `docs/adr/0002-crawl4ai-adopted-
unconditionally.md` (supersedes `docs/adr/0001-...`) and
`.scratch/layer-1-quant-benchmarks/spec.md`.

- Rewrote `agent/crawler.py` on `crawl4ai`: `AsyncHTTPCrawlerStrategy` for
  static pages, `crawl4ai`'s default Playwright-based strategy for
  JS-heavy ones, `PDFCrawlerStrategy`/`PDFContentScrapingStrategy` for
  PDFs — `crawl()`/`crawl_parts()`'s public shape kept the same
  (`crawl_parts()` now returns each PDF's own URL alongside its text).
  Kept `beautifulsoup4`/`lxml` for CSS-selector extraction, per `crawl4ai`'s
  own recommendation.
- Fixed 4 bugs while rewriting the same code: merged multi-PDF signals now
  carry their own document's URL instead of the listing page's; one failed
  PDF fetch no longer discards the rest of a source's results;
  `raw_content` now includes every fetched document's text, not just the
  listing page (`service.py`'s `_combined_raw_content`); `agent/store.py`'s
  `_prepare_csv` is now thread-safe under concurrent schema changes.
- Found and fixed a real environment bug: this machine's from-source
  Homebrew Python 3.11 build never wires OpenSSL to a trust store, and
  `aiohttp` (which `crawl4ai` uses) caches its default verified SSL
  context as a module-level global at `aiohttp`'s own import time — so
  setting `SSL_CERT_FILE` anywhere after `langchain_groq`/
  `langchain_tavily` import `aiohttp` is too late. Fixed by setting it as
  the first lines of `service.py` and in a new root `conftest.py`.
- Extended `MarketSignal` (`agent/schema.py`) with `source_code`,
  `reference_period`, `data_basis`, `actual_proxy_forecast`,
  `forecast_org` — the mandatory audit metadata `source_plan_mvp0.md`
  requires for Layer 1 (quant bank benchmarks). `agent/store.py`'s CSV
  output gained matching columns.
- Added 6 new live-verified Layer 1 sources: `sbv_portal_statistics`,
  `iav_bancassurance`, `techcombank_vas_statements`, `bidv_financial_statements`,
  `acb_financial_statements`, `mbb_financial_statements` — 4 of the 5 target
  banks. Vietcombank is closed (not added): its own site has a real Akamai
  wall (per spec §8, routed to manual ingestion, not evasion), and its
  Vietstock static-CDN mirror is a 55-page scan with zero extractable text
  on two different quarters checked.
- Added `crawl_chunked()`/`MAX_CHUNK_CHARS` (`agent/crawler.py`) and the
  `chunked` source flag: some fetched documents (a full financial
  statement PDF, a dense listing page) exceed Groq's free-tier
  8,000-tokens-per-request ceiling on their own, not just when several
  documents are combined — chunks a single large text into pieces and
  reuses `build_multi_pdf_graph()`'s existing per-piece-structure +
  deterministic-merge flow.
- Fixed a 5th bug, found live post-migration: `graph.invoke()` runs
  crawl→structure as one atomic call, so a structure-step failure (a real
  Groq daily-quota 429, confirmed live) was discarding the crawl step's
  already-fetched content along with the exception. `service.py`'s
  `_run_item` now recovers the checkpointed crawl output via
  `graph.get_state()` instead.
- Fixed a 6th bug, found live in the same `/trigger` run: BIDV's
  `content_selector` (`#pills-taichinh`) contained 6 nested year-tab panes
  (2026-2022 + "Khác"), all present in the DOM at once — and BIDV's site
  shows the same document set under every one, so the raw fetched content
  was the same document list repeated 6 times (confirmed: 4,313 chars for
  what should have been 713). Scoped the selector to
  `#pills-taichinh .tab-pane.active` (just the current year) — total
  fetched content for this source dropped from 11,099 to 7,523 chars with
  no loss of real data, confirmed live.
- Two bespoke per-bank fetch paths, each solving a different kind of
  block: `_fetch_acb_statement_text` (ACB's "Download" controls have no
  href/onclick at all — the real PDF URL only exists after a JS click
  fires an API call; calls that same public JSON API directly instead of
  simulating a click) and `VIETSTOCK_FALLBACK_TICKERS`/
  `_fetch_vietstock_statement_text` (MBBank's own site is Akamai-blocked;
  fetches its filed statement from Vietstock's static CDN instead, a
  genuine Aggregator source per spec §2, not a workaround for the block).
- Centralized the `SSL_CERT_FILE` bootstrap (previously duplicated in
  `service.py`, `agent/crawler.py`, and `conftest.py`) into one shared
  `agent/ssl_bootstrap.py`, imported first everywhere it's needed —
  a code-review finding.
- Added the project's first automated test suite (`tests/`, `pytest`), at
  the direct-graph-invocation seam agreed in the Layer 1 spec — 11/11
  tests passing (verified twice, live, real network + Groq calls).
- Confirmed the full pipeline end-to-end against the actual running
  service (`POST /trigger`), not just tests: real fetch → structure →
  persist, with the CSV schema-migration and raw-content-preservation
  fixes both observed working in the real `data/signals.csv`/
  `data/raw_content.csv` output.
- `requirements.txt`: added `crawl4ai`, `certifi` (explicit — was only
  arriving transitively before), `pytest`; removed `requests` (crawl4ai's
  own), `trafilatura`, `pypdf` (crawl4ai now covers PDF fetch too).
- Project-wide Python upgrade to 3.11 (from 3.9) — `crawl4ai` needs 3.10+
  in practice despite claiming `>=3.9`.
- `sbv_press_releases_official` (pre-existing) confirmed to not actually
  be part of `source_plan_mvp0.md`'s Layer 1 — kept since it already
  works, documented as not checking a spec box.

## v0.4 — URL-based extraction for official sources

- Added `agent/sources.py` + `build_extract_graph()`: `TavilyExtract`-based
  fetch for known official URLs, alongside the existing search-based
  topics — for pages where the fact reliably lives at one stable URL.
- Added 3 real, live-verified sources: SBV rediscount/refinancing rate
  page, SBV USD/VND central rate page, GSO/NSO CPI page.
- Confirmed via live test that `TavilyExtract` cannot read `customs.gov.vn`
  (JS-rendered, no content in raw HTML) — excluded from `SOURCES`.

## v0.3 — Logging and token-usage tracking

- Added `agent/logging_config.py` (console + file logging via `data/app.log`).
- Per-call token usage captured (`agent/graph.py`, via
  `.with_structured_output(..., include_raw=True)`) and surfaced in CSV
  output (`agent/store.py`).
- Added incremental per-topic saving (`append_topic_jsonl`/
  `append_topic_csv`) and per-item try/except in `service.py`, after a live
  21-topic run crashed on a Groq tokens-per-minute rate limit and lost all
  results computed before the crash.
- Added a 30s pacing delay between items (`TOPIC_DELAY_SECONDS`) to reduce
  how often the rate limit gets hit at all.
- Added a `tqdm` progress bar for `/trigger` runs.
- Expanded `agent/topics.py` from 11 to 21 topics (added 10 seasonal/
  product-launch topics: Tết campaigns, digital banking launches, card
  promotions, savings products, SME/mortgage/agricultural lending
  campaigns, green finance, bancassurance, year-end bonus effects).

## v0.2 — Trigger-based execution

- Replaced the CLI-only, human-typed-question flow with an HTTP trigger
  (`service.py`, `POST /trigger`) over a predefined topic list
  (`agent/topics.py` — Vietnam banking-sector macro topics).
- Simplified the graph: the agentic tool-calling loop was replaced with
  deterministic search (`checkpoint_gate → search → structure`) —
  token-cost-driven, since the topic list already fixes what to search.
- Output persisted to `data/signals.jsonl` instead of printed to stdout.

## v0.1 — Initial MVP0

- First working end-to-end pipeline: `checkpoint_gate → agent (ChatGroq +
  Tavily tool) → structure`, CLI entry point (`main.py`).
- Model provider: Groq (`openai/gpt-oss-120b`, later swapped from
  `llama-3.3-70b-versatile` after Groq deprecated it).
- Search tool: Tavily (`TavilySearch`).
- `MarketSignal`/`MarketSignalBatch` Pydantic structured-output schema.
- `MemorySaver` checkpointing with `thread_id` session isolation.
