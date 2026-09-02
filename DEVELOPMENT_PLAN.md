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
| v0.6 — Layer 1 quant bank benchmarks (`source_plan_mvp0.md`) | 🚧 Partial — 5 of 9 new sources actually usable (3/5 banks + SBV + IAV; BIDV downgraded — fetch works but every filing checked is scan-only, no usable data) |
| Live end-to-end `/trigger` run (real spend) | ✅ Run for real — mostly hit Groq's daily quota mid-run (expected, see below), but confirmed the full pipeline (fetch → structure → persist, including the schema-migration and raw-content-preservation fixes) working end-to-end with real output in `data/signals.csv` |
| v0.7 — LLM provider fallback chain (Groq → Gemini → Mistral → OpenRouter) | ✅ Done |
| v0.8 — Layer 3 journals + Layer 4 macro/gov sources (first Layer 2-4 increment) | 🚧 Partial — 5 of 6 sources usable; `sbv_legal_directives_official` fetches and passes tests but its documents are scan-only (same category as BIDV/Vietcombank), needs OCR |
| v0.9 — Content-usability gate | ✅ Done |
| v0.10 — Layer 2 (CVP/offerings), first sources + 3 real bugs found and fixed | ✅ Done — all 10 bank news/fee sources solved (BIDV news+fee, ACB promo+fee, VPBank news+fee, VCB promo+fee, MBBank news+fee) |

## Known temporary state (fix before a real full run)

- **`service.py` currently limits `TOPICS` to the last 10 entries** (a `# TEMP` line testing the incremental-save/rate-limit fix on a smaller batch) — out of 21 real topics, only 10 run. Delete that one line once you're ready for a full run. (Moot right now: `TOPICS = []` is separately hardcoded to `[]` a few lines below, disabling this entirely — see that line's own comment.)
  - *Plain terms: right now a real trigger only checks 10 of the 21 topics on the list, on purpose, to keep test runs cheap. Someone needs to remove that limit before the real thing runs for real.*
- **Groq's free-tier daily quota (200,000 tokens/day) is easy to exhaust** — hit twice on 2026-08-31 from this session's own testing (two full pytest runs + a live `/trigger` run). No longer a hard stop: v0.7's LLM fallback chain (Groq → Gemini → Mistral → OpenRouter) now falls through automatically when this happens — confirmed live, including once for an unrelated Groq `403` (a VPN issue, not Groq itself).

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
- [x] **Techcombank** (`techcombank_vas_statements`) — solved: JS-rendered document list (`SITE_CONFIGS["techcombank.com"]`), targets the "-searchable" (OCR'd) PDF twin over the scanned original.
- [x] **BIDV** (`bidv_financial_statements`) — solved: Angular-templated tab content, needs full JS render every time (a static fetch non-deterministically returns the unrendered template shell).
- [x] **ACB** (`acb_financial_statements`) — solved differently: its "Download" controls have no `href`/`onclick` at all — not an anti-bot problem, a React app whose PDF link only exists after a JS click fires an API call. Network-capturing a simulated click found that call is a plain, unauthenticated JSON API (`acb.com.vn/api/en/front/v1/posts`) — `agent/crawler.py`'s `_fetch_acb_statement_text` calls it directly instead of simulating a click.
- [x] **MBBank** (`mbb_financial_statements`) — solved via a fallback: own site is Akamai-blocked, but its filed statement is mirrored on Vietstock's static CDN (`static2.vietstock.vn`, a genuine Aggregator source per spec §2) outside whatever blocks both the bank's own site and Vietstock's own JS document table. `agent/crawler.py`'s `VIETSTOCK_FALLBACK_TICKERS`/`_fetch_vietstock_statement_text`.
- [ ] **Vietcombank** — closed, not added. Own site: real Akamai wall (same category as `dttktt.sbv.gov.vn`; per spec §8, route to manual ingestion, don't attempt evasion). Vietstock static-CDN fallback: file exists but is a 55-page scan with zero extractable text (confirmed on 2 different quarters) — a separate, also-closed dead end.
- [ ] **Vietstock's own JS-rendered document table** (`finance.vietstock.vn/{ticker}/tai-tai-lieu.htm`) — never solved directly; superseded for MBBank by the static-CDN fallback above, which is a different, unrelated mechanism.
- [ ] `dttktt.sbv.gov.vn` — confirmed bot-blocked (both independently and per the spec); intentionally excluded, manual-only.
- [x] `tests/` (new) — first automated test suite for this project (`pytest`), at the direct-graph-invocation seam. `test_sources.py` (one test per Layer 1 source), `test_bug_fixes.py` (targeted tests for the bugs above).
- [x] **Bug #5 (found live)**: `graph.invoke()` runs crawl→structure as one atomic call — when structuring failed (confirmed live via a real Groq daily-quota 429) after crawling already fetched real content, `service.py`'s `_run_item` was throwing that content away along with the exception. Fixed: recovers the checkpointed crawl output via `graph.get_state()` instead. Regression test added (`test_run_item_preserves_raw_content_when_structuring_fails`, deterministic via a monkeypatched structure step — no LLM cost).
- [x] **Bug #6 (found live)**: BIDV's `content_selector` (`#pills-taichinh`) contained 6 nested year-tab panes all present in the DOM at once, and BIDV's site shows the same document set under every one — the raw fetched content was the same listing repeated 6x (4,313 chars for what should have been 713). Fixed: scoped to `#pills-taichinh .tab-pane.active` (just the current year). Confirmed live: 11,099 → 7,523 chars, same real data, no duplication.
- [x] **BIDV downgraded from "working" to "fetch works, data unusable"**: user-reported ("holy shit from page 3 onward it is scanned") and confirmed by page-by-page inspection — the "reviewed" filing is a 56-page PDF with real text on only pages 1-2 (a cover letter); a second, plainer Q2 2026 filing checked is a 36-page PDF with **zero** extractable text on any page. BIDV appears to scan all its regulatory filings as signed paper documents. No OCR built (see Further Notes) — BIDV is effectively in the same practical category as Vietcombank now: reachable, but not usable without OCR.

### Verification
- [x] Import/build sanity check
- [x] Full `pytest` suite: **11/11 passing** (4 bug-fix tests + one per Layer 1 source, all live network + live Groq calls, run twice for real)
- [x] Live `/trigger` run against the real running service — confirmed the full pipeline end-to-end: fetch → structure → persist, including the CSV schema-migration (old file auto-archived, new file has the extended header) and the new raw-content-preservation fix, both observed working in the actual `data/signals.csv`/`data/raw_content.csv` output, not just in tests
- [x] `sbv_press_releases_official` flagged as **not actually part of `source_plan_mvp0.md`'s Layer 1** — it's a pre-existing source from before the spec existed (closest match is Layer 4 §6.1's "SBV legal documents and directives," a different page and a different layer). Kept running since it already works, but doesn't check a Layer 1 box.

### Further Notes
- **OCR — user (Bach) is implementing.** BIDV and VCB's Vietstock-mirror both need OCR to be usable (BIDV: scan-only filings, confirmed on 2 of them; VCB: same, on its Vietstock static-CDN mirror). Options laid out earlier: local/free (Tesseract — real setup risk on this machine, real accuracy risk on financial tables/Vietnamese diacritics) vs. cloud/paid (Google Document AI / AWS Textract / Azure — roughly $0.015–$0.15/page). No vision-capable model available on Groq to skip OCR entirely (checked live — Groq's current lineup is text/audio only). **Decision (2026-09-01): the user is building/wiring in an OCR-capable model themselves** rather than this agent picking a path — once that lands, BIDV and VCB's Vietstock mirror should both be re-checked as candidate Layer 1 sources.
- **BIDV in `agent/sources.py` — still an open call.** Left wired in as-is for now (fetch works, LLM sees only a 2-page cover letter, no real financial data) pending the OCR work above; revisit whether to pull it from `SOURCES` entirely or tighten its prompt once OCR lands and it's clear whether BIDV becomes usable that way.
- **Layer 2-3-4 reachability spot-checked**, not properly tested. `chinhphu.vn`, `tapchinganhang.gov.vn`, `tapchitaichinh.vn`, `vnba.org.vn`, `thuvienphapluat.vn`, `luatvietnam.vn` all reachable immediately, real substantial content (40K–200K+ chars), zero anti-bot walls — a genuinely good sign that government/journal sites are far less protected than bank sites. Layer 2 (bank news/promo pages — same domains as the Akamai-blocked Layer 1 IR pages) and the rest of Layer 3/4 are untested.

---

## v0.7 — LLM provider fallback chain (✅ done)

Groq's free-tier daily quota was hit repeatedly this session, and separately a `403 Access denied` (traced to a VPN, not a real Groq issue) also knocked it out mid-session — both real demonstrations of the actual problem this solves. The structuring step now falls through Groq → Gemini → Mistral → OpenRouter instead of hard-depending on one provider.

- [x] `agent/llm_fallback.py` (new) — `build_structuring_model()`: Groq → Gemini → Mistral → OpenRouter via LangChain's `.with_fallbacks()`. Drop-in for `agent/graph.py`'s `_structure_one()` (its only caller) — no extraction node needed any changes.
- [x] `ExtractionValidationError` — a "successful" call whose output fails schema validation (`parsed is None`) now also triggers the next provider, not just HTTP/rate-limit exceptions. Required since providers differ in how strictly they honor JSON/tool-calling mode.
- [x] `data/llm_provider_calls.csv` (new) — logs which provider/model actually served (or attempted) each structuring call, for tracing quality shifts between providers later.
- [x] Real per-provider findings from live testing (not just picking from docs/descriptions):
  - `gemini-2.5-flash` (originally planned) is dead — 404, Google's API points at `gemini-3.6-flash`.
  - `mistral-small-2603` (the exact pinned version requested) — works as-is.
  - OpenRouter free tier: 3 candidates tested, 2 failed differently (`minimax/minimax-m2.7:free` wraps JSON in markdown fences; `inclusionai/ling-3.0-flash-fin:free`'s backing provider rejects structured-output requests outright) before `nvidia/nemotron-3-super-120b-a12b:free` worked — but only with `method="json_mode"` plus the schema spelled out directly in the prompt (confirmed live: `json_mode` alone still returned `parsed=None`).
  - Every provider now has a 30s timeout + no internal retries — an OpenRouter free-tier model sat with zero output for 4+ minutes with no timeout set.
- [x] `tests/test_llm_fallback.py` (new) — deterministic cascade/validation tests using fake chat models (no real API calls); each real provider was separately live-verified by hand first.
- [x] Fixed a stale pre-existing script, `test_llm.py` (repo root, predates the `tests/` convention) — referenced the now-removed `_build_model()`; updated to use `build_structuring_model()`.
- [x] `requirements.txt`: added `langchain-google-genai`, `langchain-mistralai`, `langchain-openai`.
- [x] `.env`: fixed — 3 new keys were present but unparseable (`KEY: value` instead of `KEY=value`, plus `GOOGLE_API_KEY`/`OPEN_ROUTER_API_KEY` named differently than what was actually there). Now `GEMINI_API_KEY`, `MISTRAL_API_KEY`, `OPENROUTER_API_KEY` all load correctly.

### Verification
- [x] Import/build sanity check
- [x] All 4 providers live-verified individually before being trusted in the chain
- [x] Full cascade verified for real, not just simulated: Groq was genuinely down (VPN-related 403) during testing, and `_structure_one()` correctly fell through to Gemini, which served the call — logged correctly in `data/llm_provider_calls.csv`
- [x] `pytest tests/test_llm_fallback.py tests/test_bug_fixes.py`: **11/11 passing**

---

## v0.8 — Layer 3 journals + Layer 4 macro/gov sources (✅ done)

First slice of the still-open Layer 2-4 work (Layer 1 covered `source_plan_mvp0.md`'s 5 quant banks + SBV + IAV; Layers 2-4 were deferred, not dropped). Scoped down via a grilling session to the lowest-risk slice: Layer 4 in full (Tier 1 Citable only) plus Layer 3's two journals — see `.scratch/layer-3-4-easy-wins/spec.md` for the full spec and the new root `CONTEXT.md` for the vocabulary that session produced (Layer/Role/Tier 1-2/spot-checked vs. live-verified/watchlist document).

- [x] `agent/sources.py` — 6 new sources added, all `role: "citable"`, all live-verified (`pytest tests/test_sources.py -k <id>`, real network + real LLM structuring call):
  - **`vietnam_cpi_official`** — revived from a commented-out pre-Layer-1 entry. The domain assumed stale (`gso.gov.vn`, per an earlier reorg note in this file) turned out to be unreachable (`ECONNREFUSED`, no response), while the old `nso.gov.vn/en/cpi/` URL is live right now with real, current CPI releases.
  - **`chinhphu_legal_documents_official`** — `vanban.chinhphu.vn`, scoped past ~80% nav/weather-widget boilerplate to the real government document-list container.
  - **`vnba_banking_news`** — `vnba.org.vn`, real open-banking/AI-in-banking content confirmed, static fetch (no JS needed).
  - **`banking_review_journal`** — `tapchinganhang.gov.vn` (no `www.` — that vhost is separately misconfigured, a distinct issue from any anti-bot concern). Needs a full browser fetch: the static path returns a genuine HTTP 410, not a block.
  - **`finance_review_journal`** — `tapchitaichinh.vn`. A prior spot-check (this file, below) claimed zero anti-bot walls; a different fetcher later got a real 403, but `crawl4ai` itself was confirmed live to get through fine on the static path — the 403 didn't carry over.
  - **`sbv_legal_directives_official`** — reuses `SITE_CONFIGS["sbv.gov.vn"]` unchanged (same domain as `sbv_press_releases_official`). The `/en/legal-documents` URL guessed first was an empty nav shell (not used); `/en/văn-bản-quản-lý-hành-chính` is the real one, and the fetch mechanism genuinely works (document list + PDFs download successfully, test passes). **But downgraded to scan-only, same as BIDV/Vietcombank** — see Further Notes below; the documents themselves aren't usable data until OCR lands. Also carries green-credit figures in its prompt (folded in alongside `banking_review_journal`, per the spec's own dual-sourcing) rather than becoming a 7th source.
- [x] `agent/crawler.py` — 4 new `SITE_CONFIGS` entries (`vanban.chinhphu.vn`, `vnba.org.vn`, `tapchinganhang.gov.vn`, `tapchitaichinh.vn`) for content-selector scoping and, for `tapchinganhang.gov.vn`, forcing the full-browser strategy past a static-path 410.
- [x] No `agent/schema.py` changes — every field this slice needs (`source_code`, `reference_period`, `data_basis`, `actual_proxy_forecast`, `forecast_org`) already existed from Layer 1; `data_basis` is `"not_applicable"` for all six (none are bank financial-statement figures).
- [x] `CONTEXT.md` (new) — Layer/Role/Tier 1-2/spot-checked-vs-live-verified/watchlist-document vocabulary, written during the design session that produced this increment.

### Verification
- [x] Each of the 6 sources individually live-verified (`pytest tests/test_sources.py -k <id>`) before being trusted.
- [x] Full `pytest tests/` run — all green (11 existing + 6 new = 17/17).

### Further Notes
- **SBV directives shares its domain's known WAF flakiness** with `sbv_press_releases_official` — one live check got real content immediately followed by a genuine WAF rejection page on the very next call. Not a new problem, same documented behavior this domain has always had.
- **New problem found via `fetch_preview.py` (2026-09-01): `sbv_legal_directives_official`'s source page is scan-only across the board, not just one bad PDF.** User manually clicked through the documents listed on `https://sbv.gov.vn/en/văn-bản-quản-lý-hành-chính` and confirmed every PDF there is a scanned document — same underlying problem as BIDV's and Vietcombank's scan-only filings (see v0.6's OCR note below), just on a different bank/domain. One of the 3 fetched PDFs ("CT 02_2026.pdf", Chỉ thị 02/CT-NHNN on digital transformation/cybersecurity) came back with visibly garbled, nonsensical extracted text (e.g. "ctrAm di6m", "chri d$ng") — a broken OCR layer. The other 2 (`qd_1382_2606.signed.pdf`, `Van ban het hieu luc SBV.pdf`) extracted as coherent, readable text — but since the source document itself is also a scan, that's OCR output too, not born-digital text; it happening to read cleanly this time doesn't make it a reliable text source going forward, just a scan whose OCR came out legible on this occasion. **This is a gap in `agent/crawler.py`'s existing near-empty-content check** (`_fetch_pdf_text`'s `len(text) < 50` guard): it only catches text that's too *short*, not text that's present but wrong (broken OCR) or merely happens to be readable OCR from a scan rather than a genuinely reliable born-digital document — neither is something the current check can distinguish. **This source is downgraded to the same practical category as BIDV/Vietcombank**: fetch works, but the underlying documents need the user's in-progress OCR work before this source is actually trustworthy, not just re-checked for one bad document.
- **Explicitly deferred, not dropped** (see `.scratch/layer-3-4-easy-wins/spec.md`'s Out of Scope for the full reasoning):
  - Layer 2 entirely (bank news/promo pages, fee/T&C pages, app-store release notes).
  - Layer 3's bank annual reports/AGM docs and the 4 securities firms' research PDFs (Tier 2).
  - Thư viện Pháp luật / LuatVietnam document-by-reference lookups for the 9 named watchlist documents (Circular 08/2026, Official Letter 4551, Circular 52/2018, Decree 94/2025, Resolution 57-NQ/TW, Decision 21/2025, Circular 17/2022, Resolution 110/2025, Law 109/2025) — needs a one-time manual URL-discovery pass per document.
  - Consumer research (Cimigo/Decision Lab/Q&Me, Tier 2) — needs a new `[Opinion]`/`[Fact]` schema distinction (R-F04/R-F07) not yet built into `agent/schema.py`.

## v0.9 — Content-usability gate (✅ done)

Phase 2 of the three-phase Layer 2-4 direction set earlier this session (fetch/save raw content → **a content-usability gate** → reasoning/structuring prompt quality). Motivated directly by two real failures hit while building v0.8: a WAF/security-appliance block page served with HTTP 200 (real text, not real content), and a scanned PDF with a broken OCR/font-encoding layer (`sbv_legal_directives_official`'s "CT 02_2026.pdf") — both would have cleared every existing check and gotten spent on a real Groq call before this. Full spec: `.scratch/content-usability-gate/spec.md`.

- [x] `agent/content_gate.py` (new) — `check_content_usable(text)`: near-empty check, known block-page fingerprint match (2 real strings, captured live), and a corrupted-token-ratio heuristic (fraction of tokens mixing a lowercase letter with a digit — validated live to cleanly separate real garbled OCR (0.23), real clean content's normal markdown-noise floor (0.0–0.006), and this project's own legitimate financial period codes like Q2/H1/FY2025/9M2025/3M26, which never trip it since they're always upper-case-led).
  - *Plain terms: a cheap, instant check that runs on every fetched page before any AI call — it catches "this is actually a block page" or "this is a scan with garbled text" for free, so money and quota aren't wasted feeding garbage to the AI.*
- [x] `agent/graph.py` — two new nodes, `content_gate`/`content_gate_multi`, wired between fetch and structure in both `build_crawl_graph()` and `build_multi_pdf_graph()`. Multi-document sources are checked per-document (one bad PDF doesn't block the good ones, same principle as Layer 1's existing partial-PDF-failure handling) — only rejecting the whole item if nothing usable survives, including the fallback listing text.
- [x] Rejections reuse the existing `gate_passed`/`gate_reason` fields (prefixed `"Content gate: ..."`) rather than a new field pair — zero changes needed to `service.py`, the CSV schema, or existing tests to surface a content-gate rejection. A deliberate trade-off (documented in the spec), not an oversight.
- [x] `CONTEXT.md` — new "Checkpoint gate vs content gate" entry distinguishing the two validation stages.
- [x] `tests/test_content_gate.py` (new, 11 tests) — this project's first fully offline/mock-free test file (alongside the existing `test_bug_fixes.py`/`test_llm_fallback.py`), using real captured fixtures (the actual garbled PDF excerpt, the actual WAF block page, a real clean fetch) rather than invented text. Includes a specific regression guard for the financial-period-code false-positive risk.

### Verification
- [x] Import/build sanity check — all 3 graphs (`build_graph`, `build_crawl_graph`, `build_multi_pdf_graph`) compile cleanly with the new nodes, no network/LLM spend.
- [x] Full `pytest tests/test_content_gate.py`: 11/11 passing, zero network/LLM calls.
- [x] Validated against real data, not just synthetic fixtures: ran the gate against the actual previously-captured `sbv_legal_directives_official` fetch output — correctly rejected 2 of its 3 real PDFs as scan-corrupted (only the office-space-standards PDF passed), independently reproducing the same finding the user got by manually opening the PDFs, without spending any LLM call.

### Further Notes
- Deliberately did **not** re-run the full LLM-inclusive `tests/test_sources.py` suite to "prove" this works end-to-end in production — per this session's own established direction (don't spend real Groq/LLM calls verifying fetch-layer work by default), the offline tests plus the real-data validation above were treated as sufficient.
- Explicitly out of scope for this pass (see spec's Out of Scope): a nav-boilerplate/selector-mismatch heuristic, a language-aware/dictionary-based corrupted-text check, and any LLM-based self-critique or reflection step — the last one was specifically considered and rejected, since it would reintroduce the exact LLM-cost problem this gate exists to avoid.
- Phase 3 of the Layer 2-4 direction (fixing the structuring prompts for better consolidation/summarization/insight) remains a separate, not-yet-started effort.

## v0.10 — Layer 2 (CVP/offerings/segment sales models) (✅ done)

First real work on Layer 2 (`source_plan_mvp0.md` §4) — bank news/promotions pages and fee/T&C pages, 5 banks (VCB, BIDV, MBB, ACB, VPBank). Fetch-only development throughout, per the fetch-dev-no-llm-by-default direction set earlier — no Groq/LLM calls spent verifying any of this, only `agent.crawler.crawl()`/`crawl_chunked()` + `agent.content_gate.check_content_usable()`, both free.

- [x] **`bidv_card_promotions`** — solved via `bidvinfo.com.vn` (BIDV's dedicated news/media portal, a different domain from `bidv.com.vn`), "Khuyến mãi thẻ" section. Real, dated card-partner offers (Trip.com, Agoda discounts). No `SITE_CONFIGS` entry needed.
- [x] **`bidv_personal_fee_schedule`** — solved via `bidv.com.vn/vn/ca-nhan/cong-cu-tien-ich/bieu-phi`, a mega-menu page (114K+ chars unscoped) with a real, dated, 12-PDF fee-schedule index buried in one small accordion container. Scoped selector + `pdf_link_limit: 1` picks the newest (the other 11 are mostly older versions of the same card-fee document). Confirmed live: a genuine fee table segmented by customer tier (regular retail vs. Premier/Private).
- [x] **`vpbank_news`** / **`vpbank_fee_documents`** — same AJAX-gap as ACB, solved the same way (real Playwright network capture): both pages call VPBank's own `uiux-api`, returning real JSON directly (no separate detail-fetch step needed, simpler than ACB's two-step case). The fee-documents API needed a correction after the first capture: it drilled into "Biểu mẫu" (Forms) > individual-customer, the page's own default tab, not "Biểu phí" (Fee Schedule) — a genuinely separate sibling category, found via VPBank's own `category/children` endpoint. Using the top-level fee-schedule path (not one segment) returns real, dated documents across segments (individual, business households, SME, large corporate) in one call — but only titles/dates/segment, not the figures inside each linked PDF; not fetching those PDFs this pass (light-effort call), prompt scoped to match.
- [x] **`vcb_promotions`** — a genuinely different problem than ACB/VPBank's AJAX-gap: VCB's homepage showed *zero* fetch/XHR calls under JS-injection capture — mostly server-rendered, not a client-side SPA, so the listing's real links are likely populated via a WebCenter/Liferay-style portlet postback this technique can't see. Solved differently: individual promo article pages ARE real and fully extractable, so the sitemap (with real `<lastmod>` dates, since `crawl4ai` itself fails on this sitemap's XML encoding — raw `urllib` used for just this one bootstrap step) picks the 3 most recent. Confirmed live: detailed, dated promos with real VND figures (a 4-billion-VND prize pool program, specific cashback amounts).
- [x] **`vcb_fee_schedule`** — reopened after being wrongly judged "needs OCR" on an earlier pass (that conclusion came from one fetch that happened to return a near-empty shell). Solving it properly then surfaced a second, more serious problem: this page is server-side rendered, and a dynamic per-category scrape of its accordion was built and then **abandoned after finding a real correctness bug**, not just a flakiness one — confirmed live that all 3 of VCB's transfer-type categories (international, domestic, remittance) render with the *same* "Biểu phí" content in the initial HTML (international transfer's PDFs appear under every category heading), the same failure shape as BIDV's Layer 1 bug #6 (same document set repeated under every tab). Scraping "whichever category's heading you find" would have silently mislabeled international-transfer fees as domestic-transfer or remittance fees. Fixed by using a hand-verified, explicit URL list instead of the scraper, built from **real Playwright click simulation** (ACB-style network capture, not guessing): clicking each category tab surfaced VCB's actual document-search API (Sitecore's `sxa/FileDocumentApi/FileDocumentResults`) and each category's own real PDFs. International transfer has 2 real fee PDFs; domestic transfer has 1 (a user-provided URL turned out to be the same document in a different language, not a second one, confirmed by click-verifying domestic's own Vietnamese PDF and comparing figures); remittance was also click-verified directly and genuinely has **no fee document at all** — its panel shows only a "Biểu mẫu" (forms) heading, consistent with VCB not charging to *receive* a remittance. So the 3-PDF list is complete, not a partial result.
- [x] **`acb_promotions`** — solved via real Playwright network capture (not a guess): the rendered listing said "Không có sản phẩm" (no products), same AJAX-gap as VPBank, but capturing the page's actual network requests revealed a two-step API — `map/posts?type=uu-dai` lists promo ids, then each id's real content only comes back from the **Vietnamese-locale** detail endpoint (`/api/vi/front/v1/posts/{id}` — the English one returns nulls for these Vietnamese-only posts). Confirmed live: 8 real, current promotions with validity dates. (ACB's fee page needed a separate, different network capture — see `acb_fee_schedule` below.)
- [x] **`mbbank_fee_schedule`** / **`mbbank_news`** — reopened and solved after initially being marked blocked-by-design. The bare `mbbank.com.vn` domain genuinely is Akamai-walled site-wide (every path returns the identical "0 chars visible" block, re-confirmed live) — but the **`www.` subdomain is not behind the same wall** (confirmed live), a different, legitimately-reachable host the bank itself owns, not evasion. Both pages are Angular-templated and needed a JS-predicate wait condition rather than a plain CSS wait — confirmed live that a plain CSS wait (the mechanism every other `SITE_CONFIGS` entry uses) raced unreliably on both pages (the news page in particular needed the wait scoped to the target container itself, not just "does a matching link exist anywhere on the page," after 3 separate runs showed the page-wide version racing with the container's own content still settling). Confirmed live: real, current fee tables (account/deposit/treasury fees, real VND amounts) and real, dated news items (a minigame results announcement, a CSR partnership, procurement notices).
- [x] **`acb_fee_schedule`** — solved on a second pass. The real fee page turned out not to be the guessed `/en/fees` (a generic empty-search shell) but `/en/forms-and-fee-schedules-for-individual-customers`, found via ACB's own homepage nav. Needed its own separate network capture — the promo API pattern didn't transfer — which found the standard `posts` endpoint filtered by `search[type:like]=bieu-mau-bieu-phi`. Category "Summary of fee schedule" holds 11 real fee documents (one per product line); this picks whichever was most recently updated rather than hardcoding one. Same two-locale quirk as promotions: the real PDF only shows up via the Vietnamese-locale detail endpoint. Confirmed live on two different picks across this session: a segmented credit-card fee table (Visa Infinite Privilege through ACB Express tiers) and a real account-services fee list (statements, balance confirmations, savings-book loss) — both genuine, dated, real VND figures.
- [x] **3 real bugs found and fixed while doing this work** (none were regressions from this session's own earlier changes — all pre-existing, surfaced by touching this code for the first time since Layer 1):
  1. **Content gate false positive on CDN image URLs** — `agent/content_gate.py`'s corrupted-token heuristic was tripped by UUID/hash fragments in markdown image URLs (`e6039a2a-a43f-4860-bbdb...`), nearly rejecting a completely legitimate BIDV news article (ratio 0.054, just over the 0.05 threshold) for URL noise, not real text corruption. Fixed by stripping URLs before computing the ratio; added a regression test using the real triggering content.
  2. **ACB/MBBank domain-wide routing hijack** — `agent/crawler.py`'s `_crawl_async` checked `_domain(url) == "acb.com.vn"` (and similarly for MBBank's Vietstock fallback) rather than the specific Layer 1 URL, so *any* other URL on those two domains got silently redirected to the Layer 1 financial-statement fetch instead of the actually-requested page. Confirmed live: a sitemap request to both domains returned financial-statement content instead of the sitemap. Fixed by keying both special-cased routes to the exact Layer 1 source URL (`ACB_FINANCIAL_STATEMENTS_URL`, `MBBANK_FINANCIAL_STATEMENTS_URL`) instead of the domain.
  3. **`SITE_CONFIGS` domain-only keying** — the general selector-lookup mechanism (`SITE_CONFIGS.get(_domain(url), DEFAULT_CONFIG)`) had the same class of bug as #2, one level up: any second source added on an already-configured domain (BIDV's new fee-schedule page, same domain as its Layer 1 financial-statements page) would silently get the *wrong* selector. Fixed with `_resolve_site_config(url)`: checks for an exact-URL-keyed entry first, falls back to domain, then to `DEFAULT_CONFIG`. BIDV's existing Layer 1 entry re-keyed from `"bidv.com.vn"` to its specific URL as part of this fix.

### Verification
- [x] Import/build sanity check — all 3 graphs compile cleanly, `SOURCES` imports with all 10 new entries (23 total sources).
- [x] Every new source's full fetch → (chunk/multi-doc) → content-gate pipeline verified live, fetch-only (zero LLM cost) — each confirmed with real, current, on-topic content as documented in its own bullet above.
- [x] The `SITE_CONFIGS` fix verified directly: BIDV's Layer 1 URL and new fee-schedule URL now resolve to their own distinct selectors; an unconfigured `bidv.com.vn` URL correctly falls through to `DEFAULT_CONFIG`.
- [x] The ACB/MBBank routing fix verified directly: a non-financial-statement URL on each domain now fetches normally (confirmed MBBank's homepage correctly surfaces its real, already-known Akamai block instead of being silently masked by the old hijack).
- [x] `tests/test_content_gate.py`: 12/12 passing (11 + 1 new regression test for the CDN-URL false positive).
- [ ] Full LLM-inclusive `pytest tests/test_sources.py` **not** run for any of the 10 new sources, per the fetch-dev-no-llm-by-default direction — fetch-only verification was treated as sufficient; real LLM verification deferred to whenever a full-pipeline check is actually wanted.

## v0.11 — Layer 4 legal-document watchlist (LuatVietnam) (✅ done)

First real work on the "Thư viện Pháp luật / LuatVietnam" aggregator row (`source_plan_mvp0.md` §6.1) — the 9 named documents scattered across §6.1-6.4's watchlist (real estate credit rules, the fintech sandbox decree, the digital-transformation resolution, the 2026 PIT deduction/law changes, the green taxonomy decision, environmental-risk-management circular). Annual reports/AGM documents (the other open Layer 3 item) were deliberately parked mid-discovery to do this smaller, more self-contained slice first — see this session's own note in that spec. Fetch-only throughout, per the fetch-dev-no-llm-by-default direction — zero Groq/LLM calls spent verifying any of this.

- [x] **thuvienphapluat.vn skipped entirely** — its `robots.txt` has a dedicated `User-agent: ClaudeBot` / `Disallow: /` block (also GPTBot, CCBot, Bytespider, Google-Extended, etc.), distinct from its general `Content-Signal` declaration. Since this fetch is genuinely Claude-driven, using it anyway on the technicality that `crawl4ai`'s browser doesn't literally send that UA string would be exactly the kind of workaround this project's own compliance rule (§8: "sources that block bots... switch entirely to the manual ingestion path — no workarounds") already forbids. `luatvietnam.vn` (the plan's own listed alternative) has no bot-specific rule — used exclusively instead.
- [x] All 9 documents located on `luatvietnam.vn`/`english.luatvietnam.vn` via external web search (their own internal search pages are separately `Disallow`'d in robots.txt, so this doesn't touch that) and confirmed live: correct reference number, issuing authority, and date for each.
- [x] `agent/crawler.py` — new `SITE_CONFIGS["luatvietnam.vn"]` / `["english.luatvietnam.vn"]` entries, `.content-left` selector. Confirmed live this scopes past a large sidebar taxonomy nav (~30-50K chars of unscoped boilerplate on a typical page) while keeping the real document text. Also confirmed live: the page's own "Bạn chưa Đăng nhập thành viên... Vui lòng Đăng nhập để xem chi tiết" notice gates only a "watch this document" convenience feature, not the document text — full legal text including appendices/report-form templates is present in the static HTML for every one of these 9 pages, no login and no JS needed.
- [x] **One stale-reference correction**: the plan names "Circular 52/2018" as the credit-institution-rating regulation feeding SBV's credit-room allocation mechanism — confirmed live that's genuinely what Circular 52/2018/TT-NHNN covers, but also confirmed live it was replaced by **Circular 21/2025/TT-NHNN**, effective 2025-11-01 (before this source was even added). Sourced 21/2025 instead of the plan's now-outdated document number — tracking the plan's intent (the *currently effective* rating regulation), not a stale reference. Documented inline in `agent/sources.py`.
- [x] 9 new sources added, `role: "aggregator"` (first real use of that role value — previously documented but unused; matches the plan's own categorization of this row, since luatvietnam.vn is not the issuing authority). Each prompt's `source_code` instead names the actual issuing body (`SBV`, `CHINHPHU`, `TW` for the Politburo-issued resolution, `UBTVQH` for the Standing Committee resolution, `QH` for the National Assembly law, `TTG` for the PM-issued decision) — same "attribute the original document, not the aggregator" convention already established for MBBank's Layer 1 source.
- [x] 7 of 9 marked `chunked: true` (over `MAX_CHUNK_CHARS`'s 12K threshold once scoped: 25.7K-124.1K chars); the 2 shortest (the SBV official letter, 7.9K; the PIT-deduction resolution, 10.2K) fit in one call, left unchunked.

### Verification
- [x] Import/build sanity check — `SOURCES` imports cleanly with all 9 new entries (32 total sources), no id collisions.
- [x] Every new source's full fetch → content-gate pipeline verified live via `fetch_preview.py`, fetch-only (zero LLM cost) — all 9 pass `check_content_usable()`, real dated legal text confirmed for each (not nav boilerplate, not a login wall).
- [x] `tests/test_content_gate.py`: 12/12 passing (no changes needed to this suite for this pass).
- [ ] Full LLM-inclusive `pytest tests/test_sources.py` **not** run for any of the 9 new sources, per the fetch-dev-no-llm-by-default direction — fetch-only verification was treated as sufficient; real LLM verification deferred to whenever a full-pipeline check is actually wanted.

### Further Notes
- Annual reports/AGM documents (Layer 3, 5 banks) remains open — parked mid-discovery (Techcombank's PDF found, chapter-boundary slicing not yet solved; VCB's real annual-report link found behind a non-deterministic AJAX tab, not yet reliably re-extracted) in favor of this smaller slice. Resume there next if picked back up.
- Still open per the Layer 3/4 source plan: securities-firm research + consumer research (both Tier 2, blocked on a `[Opinion]`/`[Fact]` schema field not yet built), app-store release notes (6 apps), Phase 3 (structuring-prompt quality).

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
