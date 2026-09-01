# Changelog

Dated, terse technical record of this project's revisions. Not strict
semver — this is an internal MVP0 demo, versioned by milestone rather than
package release. For plain-English progress tracking see
`DEVELOPMENT_PLAN.md`; for architecture/design rationale see `MVP0_PLAN.md`.

## Unreleased — ACB promotions via real network-capture API discovery

- Added `acb_promotions` (`acb.com.vn/en/promotions`). Same class of
  problem as ACB's Layer 1 financial-statements page: the rendered
  listing explicitly said "Không có sản phẩm" (no products) — same
  AJAX-gap VPBank also hit. Solved this time with real Playwright network
  capture (not a guess): the page calls a two-step API —
  `map/posts?type=uu-dai` lists promo ids, then each id's actual content
  only comes back from the **Vietnamese-locale** detail endpoint
  (`/api/vi/front/v1/posts/{id}`) — the English-locale endpoint returns
  null title/description for these Vietnamese-only posts, which is why
  earlier guesses at the existing `posts?search[categories.category_id]`
  pattern (Layer 1's approach) never found it.
- `agent/crawler.py`: `_fetch_acb_promotions_text()`, a new custom
  multi-step fetch function (list then per-item detail), mirroring the
  style of the existing `_fetch_acb_statement_text()`. Routed via the
  same exact-URL-keyed pattern used for the ACB/MBBank fix above.
- Confirmed live: 8 real, current promotions (0-fee transfers, cashback
  offers, savings-rate boosts), several with explicit validity date
  ranges — fetch-only verified, zero LLM cost.

## Unreleased — Layer 2 (first sources) + 3 real bugs found and fixed

- Added `bidv_card_promotions` (`bidvinfo.com.vn`, BIDV's dedicated news/
  media portal — a different domain from `bidv.com.vn`) and
  `bidv_personal_fee_schedule` (`bidv.com.vn/vn/ca-nhan/cong-cu-tien-ich/
  bieu-phi`) — the first 2 of Layer 2's ~10 bank news/fee sources
  (`source_plan_mvp0.md` §4). Fetch-only development throughout — zero
  Groq/LLM calls spent verifying either, only `crawl()`/`crawl_chunked()`
  + `check_content_usable()`.
- VPBank, Vietcombank, ACB, and MBBank's Layer 2 pages remain unsolved —
  documented per-bank in `DEVELOPMENT_PLAN.md`'s new v0.10 section, not
  silently dropped. Several share a real AJAX-loaded-listing gap (the
  page shell renders, the actual list never does, even with crawl4ai's JS
  strategy) — the same category of problem ACB's Layer 1 fetch solved by
  finding the underlying JSON API instead of the rendered page. Not yet
  attempted for these.
- Fixed a real bug in `agent/content_gate.py`: the corrupted-token
  heuristic was tripped by UUID/hash fragments in markdown CDN image URLs
  (`e6039a2a-a43f-4860-bbdb...`), nearly rejecting a completely legitimate
  BIDV news article (ratio 0.054, just over the 0.05 threshold) for URL
  noise, not real corruption. Fixed by stripping URLs before computing
  the ratio; added a regression test using the real triggering content.
- Fixed a real bug in `agent/crawler.py`: `_crawl_async` special-cased ACB
  and MBBank by domain alone (`_domain(url) == "acb.com.vn"`), so *any*
  URL on those domains got silently hijacked into fetching Layer 1's
  financial statement instead of the actually-requested page — confirmed
  live (a sitemap request to both domains returned financial-statement
  content). Fixed by keying both routes to the exact Layer 1 source URL
  instead of the domain.
- Fixed the same class of bug one level up: `SITE_CONFIGS` was keyed by
  domain only, so a second source on an already-configured domain (BIDV's
  new fee-schedule page, same domain as its Layer 1 financial-statements
  page) would have silently gotten the wrong selector. Added
  `_resolve_site_config(url)`: URL match takes precedence over domain
  match, which falls back to `DEFAULT_CONFIG`. BIDV's existing Layer 1
  `SITE_CONFIGS` entry re-keyed from the bare domain to its specific URL.
- `tests/test_content_gate.py`: 12/12 passing (added a regression test
  for the CDN-URL false positive).

## Unreleased — Content-usability gate

- Added `agent/content_gate.py`: `check_content_usable()`, a deterministic,
  LLM-free check run after every fetch and before any structuring call.
  Motivated by two real failures hit while building the Layer 3/4 sources
  above: a WAF/security-appliance block page served with HTTP 200, and a
  scanned PDF with a broken OCR/font-encoding layer
  (`sbv_legal_directives_official`'s "CT 02_2026.pdf") — both would have
  cleared every existing check and been spent on a real Groq call.
- Three checks: near-empty content, a small set of known block-page
  fingerprint strings (captured live), and a corrupted-token-ratio
  heuristic — the fraction of tokens mixing a lowercase letter with a
  digit. Validated live: real garbled OCR text scores 0.23, real clean
  fetched content scores 0.0-0.006 (normal markdown-conversion noise), and
  this project's own legitimate financial period codes (Q2, H1, FY2025,
  9M2025, 3M26) score 0.0 and are never misclassified, since they're
  always upper-case-led — the heuristic is deliberately language-agnostic,
  not a Vietnamese-diacritic check, since several sources are
  English-language.
- `agent/graph.py`: two new nodes (`content_gate`/`content_gate_multi`)
  wired between fetch and structure in both `build_crawl_graph()` and
  `build_multi_pdf_graph()`. Multi-document sources are checked
  per-document — one bad PDF doesn't block the good ones, same principle
  as the existing partial-PDF-failure handling — only rejecting the whole
  item if nothing usable survives, including the fallback listing text.
- Rejections reuse the existing `gate_passed`/`gate_reason` fields
  (prefixed `"Content gate: ..."`) rather than a new field pair — no
  changes needed to `service.py`, the CSV schema, or existing tests.
- Added `tests/test_content_gate.py` (11 tests): this project's first
  fully offline/mock-free test file, using real captured fixtures (the
  actual garbled PDF excerpt, the actual WAF block page, real clean
  content) rather than invented text, plus a regression guard for the
  financial-period-code false-positive risk.
- Validated against real data post-hoc: ran the gate against the actual
  previously-captured `sbv_legal_directives_official` fetch output —
  correctly rejected 2 of its 3 real PDFs as scan-corrupted, independently
  reproducing what the user found by manually opening the PDFs, at zero
  LLM cost.
- New `CONTEXT.md` entry distinguishing the existing checkpoint gate
  (query validation) from this new content gate (fetched-content
  validation) — two different concepts sharing one field pair by
  deliberate choice, not by accident.
- Full spec: `.scratch/content-usability-gate/spec.md`.

## Unreleased — Layer 3 journals + Layer 4 macro/gov sources

- Added 6 new sources to `agent/sources.py`, all `role: "citable"`, live-
  verified against real network + real LLM structuring calls — the first
  slice of the still-open Layer 2-4 work (Layer 1 shipped the 5 quant
  banks + SBV + IAV; Layers 2-4 were deferred, not dropped). Scope decided
  through a grilling session that also produced a new root `CONTEXT.md`
  (Layer/Role/Tier 1-2/spot-checked-vs-live-verified/watchlist-document
  vocabulary) and `.scratch/layer-3-4-easy-wins/spec.md`.
- `vietnam_cpi_official` revived from a commented-out pre-Layer-1 entry —
  the domain assumed stale (`gso.gov.vn`) turned out unreachable
  (`ECONNREFUSED`), while the old `nso.gov.vn/en/cpi/` URL is live right
  now with real, current CPI data.
- `chinhphu_legal_documents_official` (`vanban.chinhphu.vn`),
  `vnba_banking_news` (`vnba.org.vn`), `banking_review_journal`
  (`tapchinganhang.gov.vn`), and `finance_review_journal`
  (`tapchitaichinh.vn`) added, each needing its own `SITE_CONFIGS` entry
  (`agent/crawler.py`) for content-selector scoping past nav/weather-widget
  boilerplate; `tapchinganhang.gov.vn` additionally needs the full-browser
  strategy forced on, since its static path returns a genuine HTTP 410.
- A prior spot-check (this file's own v0.6 notes) claimed `tapchitaichinh.vn`
  had zero anti-bot walls; a different fetcher used during this pass's
  design phase got a real 403 on the same domain — but `crawl4ai` itself
  was confirmed live to get through fine, so the source was kept rather
  than dropped on a signal from a different fetch mechanism.
- `sbv_legal_directives_official` reuses `SITE_CONFIGS["sbv.gov.vn"]`
  unchanged (same domain as the existing `sbv_press_releases_official`).
  The first guessed URL (`/en/legal-documents`) was an empty nav shell;
  `/en/văn-bản-quản-lý-hành-chính` is the real one. Shares this domain's
  known WAF flakiness — one live check got real content immediately
  followed by a genuine WAF rejection page on the next call. Also carries
  green-credit figures in its prompt (alongside `banking_review_journal`,
  per the source plan's own dual-sourcing) rather than becoming a 7th
  source.
- No `agent/schema.py` changes — every field this slice needs already
  existed from Layer 1.
- Full `pytest tests/` stays green: 11 existing + 6 new = 17/17.

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
