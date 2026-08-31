# Changelog

Dated, terse technical record of this project's revisions. Not strict
semver — this is an internal MVP0 demo, versioned by milestone rather than
package release. For plain-English progress tracking see
`DEVELOPMENT_PLAN.md`; for architecture/design rationale see `MVP0_PLAN.md`.

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
- Added 2 new live-verified Layer 1 sources: `sbv_portal_statistics`,
  `iav_bancassurance`. The 5 bank investor-relations pages (Techcombank,
  Vietcombank, BIDV, MBBank, ACB) and Vietstock's per-ticker document
  aggregator were investigated but not added — each needs its own
  content/PDF-link selector, not yet nailed down (see `agent/sources.py`).
- Added the project's first automated test suite (`tests/`, `pytest`), at
  the direct-graph-invocation seam agreed in the Layer 1 spec.
- `requirements.txt`: added `crawl4ai`, `pytest`; removed `requests`
  (crawl4ai's own), `trafilatura`, `pypdf` (crawl4ai now covers PDF fetch
  too).
- Project-wide Python upgrade to 3.11 (from 3.9) — `crawl4ai` needs 3.10+
  in practice despite claiming `>=3.9`.

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
