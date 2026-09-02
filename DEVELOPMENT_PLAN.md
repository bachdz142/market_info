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
| v0.23 — `mbbank_news` + `acb_promotions` click-through fixes (4th/5th user-found content bugs) | ✅ Done — verified live, real signals now surface article/detail-page-only content (prize amounts, cashback terms) |

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
- **OCR — built, see v0.18.** BIDV and VCB's Vietstock-mirror both need OCR to be usable (BIDV: scan-only filings, confirmed on 2 of them; VCB: same, on its Vietstock static-CDN mirror). Options laid out earlier: local/free (Tesseract — real setup risk on this machine, real accuracy risk on financial tables/Vietnamese diacritics) vs. cloud/paid (Google Document AI / AWS Textract / Azure — roughly $0.015–$0.15/page). No vision-capable model available on Groq to skip OCR entirely (checked live — Groq's current lineup is text/audio only). **Update: Mistral OCR (Batch mode) built in v0.18** — a standalone capability (`agent/ocr.py` + `ocr_preview.py`), not yet auto-wired into the live graph; BIDV and VCB's Vietstock mirror should both be re-checked as candidate Layer 1 sources once real output quality is validated against one of them.
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

## v0.12 — Tier 2 `[Fact]`/`[Opinion]` schema field (✅ done)

Prep work, not a new source: makes `agent/schema.py` and the graph ready for R-F07 (every Tier 2 figure tagged `[Opinion]` vs `[Fact]`) before either of the two Tier 2 rows in `source_plan_mvp0.md` (securities-firm research §5, consumer research §6.3) gets built — so neither of those future efforts has to invent this plumbing itself. Designed via `/grill-with-docs` + `/to-spec` (`.scratch/tier2-fact-opinion-field/spec.md`); R-F04, the separate forecast-tagging rule, turned out to already be fully covered by the existing `actual_proxy_forecast`/`forecast_org` fields — nothing to do there.

- [x] `agent/schema.py` — new required `MarketSignal.fact_or_opinion: Literal["fact", "opinion"]` field. No `"not_applicable"` case needed (unlike `data_basis`) since every signal is unambiguously one or the other.
- [x] `agent/sources.py` — new optional `"tier"` key per source (`"tier_1"`/`"tier_2"`), documented in the file's own top-of-file convention note alongside `"role"`. Left unset (implicit `"tier_1"`) on all 32 existing sources, matching `"chunked"`'s own set-only-when-true convention — zero changes needed to any existing source.
- [x] `agent/graph.py` — `AgentState` gains a `tier: Optional[str]` field, threaded the same way `chunked` already is. `_finalize_payload` (the one place both the single-piece and multi-piece structuring paths already funnel through) forces every signal's `fact_or_opinion` to `"fact"` when `tier == "tier_1"` — the same "known metadata beats the LLM's guess" principle already applied there to `source_url`. Only exactly `"tier_1"` triggers the override; `tier=None` (e.g. `agent/topics.py`'s search-based queries, which never set `tier`) and `"tier_2"` both leave the model's own output untouched. `METADATA_INSTRUCTION` gets one added line describing the field, since it's now required on every structure call regardless of tier.
- [x] `service.py` / `tests/test_sources.py` — both now set `"tier": source.get("tier", "tier_1")` alongside the existing `"chunked"` line, keeping the FastAPI path and the direct-test-invocation seam consistent.
- [x] `CONTEXT.md`'s Tier 1/Tier 2 entry updated — no longer says the distinction "isn't represented in `agent/schema.py`."
- [x] New `tests/test_tier_fact_opinion.py` (5 tests, fully offline — `_finalize_payload` is pure data-shaping code, no network/LLM needed to test the override itself): tier_1 forces fact even when the model said opinion; tier_2 and unset-tier both leave the model's output untouched; the schema rejects a signal missing `fact_or_opinion` or given an invalid value.
- [x] `tests/test_sources.py` — `fact_or_opinion` added to `REQUIRED_METADATA_FIELDS`, plus a real-pipeline assertion that every tier_1 source's signals come back `fact_or_opinion == "fact"` (not run this pass — real-LLM, see Verification below).
- [x] **1 real bug found by `/code-review` and fixed**: `agent/store.py`'s `CSV_HEADERS`/`append_topic_csv()` — the flattened `data/signals.csv` writer — were never updated for the new field, so `fact_or_opinion` was silently dropped from the CSV (though still present in `signals.jsonl`, which serializes the whole result dict). Not caught by any test, since `tests/test_sources.py`'s new assertion only checks the in-memory graph result, never the CSV output. Fixed (new 11th metadata column, both the no-signals and per-signal row paths), with a new offline regression test (`test_signals_csv_includes_fact_or_opinion_column`) writing a synthetic result through `append_topic_csv()` and reading the CSV back.

### Verification
- [x] Import/build sanity check — all 3 graphs compile cleanly, `SOURCES` imports unchanged (32 sources), `MarketSignal` carries the new field.
- [x] `tests/test_tier_fact_opinion.py`: 6/6 passing (fully offline, including the CSV regression test above).
- [x] `tests/test_content_gate.py` + the pure-code subset of `tests/test_bug_fixes.py`: 14/14 passing, unaffected by this change.
- [ ] Full LLM-inclusive `pytest tests/test_sources.py` **not** run, per the fetch-dev-no-llm-by-default direction — the override logic itself is fully covered offline; a real-LLM run across all 32 sources is deferred to whenever a full-pipeline check is actually wanted.

### Further Notes
- This unblocks, but does not build, either Tier 2 source row — whoever picks up securities-firm research or consumer research next writes that source's own prompt with fact/opinion judgment guidance on top of this baseline, not new schema plumbing.
- Still open, unrelated to this pass: annual reports/AGM documents (Layer 3, parked mid-discovery — see `.scratch/layer3-annual-reports/spec.md`), GSO stats, app-store release notes (6 apps), Phase 3 structuring-prompt quality.

## v0.13 — Tier 2 sources: securities-firm research + consumer research (partial)

First real work on the two Tier 2 rows unblocked by v0.12 (`source_plan_mvp0.md` §5 securities-firm research, §6.3 consumer research). Fetch-only development, zero LLM calls spent verifying any of it — each new source uses `"tier": "tier_2"` (leaving `fact_or_opinion` to the model's own per-signal judgment) with explicit fact/opinion guidance written into its own prompt.

Securities-firm research ends this pass at 3 of 4 named firms (SSI, VCBS, BSC), not the 1 of 4 first reported — VCBS was corrected mid-pass after the user pushed back on the "blocked-by-design" conclusion and did their own manual click-through, surfacing the real working URL; BSC turned out to just need finding its real report listing (the plan's own linked URL was dead) rather than any real blocking mechanism at all. Worth remembering: a JS-wait-only investigation concluding "blocked by design" isn't the same as an investigation that actually tried a genuinely trusted click or checked whether the plan's own source URL was still live.

- [x] **`ssi_banking_sector_report`** — solved after two dead ends. SSI's own sector-reports listing page never exposes real per-report links (confirmed live, even with a JS wait for `.pdf`/`ftp2` links to appear — times out). A specific, current banking-sector PDF was found directly via web search instead (SSI Research's analysis of NHNN's draft circular replacing Circular 22/2019/TT-NHNN); its host (`ftp2.ssi.com.vn`) 403s crawl4ai's own `PDFCrawlerStrategy` specifically — confirmed live this is a crawl4ai-side quirk, not a real site block, since plain `curl` with no special headers gets a clean 200 on the same URL. Fetched via direct `urllib` instead, text extracted with crawl4ai's own `NaivePDFProcessorStrategy` (no new PDF-parsing dependency). 19.5K chars, real mixed fact/analyst-opinion content.
- [x] **`vcbs_banking_sector_report`** — reopened and solved after being wrongly judged blocked-by-design on the first pass, though the automated discovery path remains genuinely blocked. VCBS's report list only resolves after clicking its "Báo cáo ngành" tab, and a plain synthetic `.click()` on the report's own title/icon did nothing — no navigation, same URL. A genuinely *trusted* Playwright click (via a captured `page` object, `page.locator(...).click()`, not JS-level `element.click()` — confirmed live this site's download handler ignores untrusted synthetic clicks, `event.isTrusted === false`) did open real navigation — but to an intermediate detail route (`/bao-cao-phan-tich/{id}?login=false`) that renders completely blank even after a 15s wait, confirmed live to load an invisible reCAPTCHA (`google.com/recaptcha/api2/anchor`) — a genuine anti-bot gate on that specific *discovery* page, not a timing issue or a misread. The user's own manual click bypassed this entirely and surfaced the actual direct-file URL (`storage/ttpt_reports/20260109/...`) — confirming the underlying PDF file itself carries no gate at all, only the page used to discover it does. Practical upshot: this specific report's URL can be refetched automatically going forward, but discovering *future* reports' URLs this same way will need a human click each time, the same limitation as any hand-verified URL in this file. 73.1K chars (chunked), real current content: 2026 credit growth of 17.87% (25/12/2025) vs. 13.82% a year earlier.
- [x] **`decisionlab_bank_satisfaction_rankings`** — solved directly, no gating: Decision Lab's Bank Satisfaction Rankings 2026 blog post (YouGov BrandIndex-based), real current content (Vietcombank leads at 86.8, Techcombank 85.9, MB 85.6).
- [x] **`qandme_online_banking_usage`** — solved directly, no gating: Q&Me's online-banking-usage report page, real current findings (91% weekly usage, 52% security-concern figure).
- [ ] **VNDirect** (securities firm) — skipped. Its `robots.txt` has a dedicated `User-agent: ClaudeBot` / `Disallow: /` block, the same pattern found on thuvienphapluat.vn in v0.11 — used exclusively for the wrong reason to route around, per this project's own no-workarounds rule.
- [x] **`bsc_mbb_report`** — solved. The plan's own listed URL (`chi-tiet-bao-cao/714250`, "Báo cáo phân tích ngành Ngân Hàng") turned out to simply be dead — confirmed live it's not linked from anywhere on the current site at all (a 3.3MB scan of BSC's by-company report listing found zero matches for that report ID or title). The real, current report listing lives at a completely different URL (`bao-cao-nganh-doanh-nghiep/`, found via BSC's own "Industry & Business Report" nav link — a different URL pattern than the plan's dead link, `bao-cao/{id}-{slug}` not `chi-tiet-bao-cao/{id}`). No dedicated whole-sector banking report was found there, but a real, current, substantive bank-specific analyst report was: BSC's own "X-Alpha" research line, a genuine BUY recommendation on MBB with target price, ROAE analysis, and 2026-2027F forecasts, dated 20/08/2026. 18.4K chars (chunked).
- [ ] **Cimigo** (consumer research) — skipped after a thorough check, not gated but genuinely stale. Its "evergreen" trends page republishes 2022 GDP/COVID-era figures under a non-dated URL; its 2024 research-report landing page is email-gated and now 404s regardless. Paginating its full article feed (`cimigo.com/en/page/2/` through `/5/`, not just the homepage's first page — a gap in the first pass) did surface a genuinely free, ungated **Dec 2024** article (`trends/vietnam-retail-banking-2024/`, real findings: "MBBank has emerged as the market leader in 2024, overtaking Vietcombank") — but by Sept 2026 that's already ~21 months old, well past the plan's quarterly cadence, and a competitive-ranking claim that old could easily have reversed since. User's explicit call: still skip rather than add stale-but-less-stale data. Its other current (2025/2026) trend articles contain zero banking/fintech-relevant content. Re-check `cimigo.com/en/page/1/` onward periodically for a genuinely current report before repeating this whole investigation.
- [x] `agent/content_gate.py` — **1 more false-positive bug found and fixed**, same class as the CDN-image-URL one from v0.9: `URL_RE` only stripped `http(s)://` links before computing the corrupted-token ratio, not inline `data:image/svg+xml;...` URIs. Confirmed live on `ssi.com.vn`'s sector-reports page: an SVG-icon-heavy nav menu inlined as base64/percent-encoded `data:` URIs scored 0.074 (a false rejection) purely from that encoded markup. Fixed by broadening the regex to `(?:https?|data):\S+`; new regression test added.
- [x] **3 real issues found by `/code-review` in `_fetch_ssi_report_text` and fixed**: (1) missing `_throttle(_domain(url))` before the `urllib` request — every other fetch function in this file calls it, and its absence here would bypass the exact WAF-protection mechanism this project added after a real sbv.gov.vn block; (2) the downloaded PDF's `NamedTemporaryFile(delete=False)` was never cleaned up, leaking a full PDF copy into the OS temp dir on every periodic fetch; (3) `NaivePDFProcessorStrategy()` defaulted to `extract_images=True`, decoding every page's images for no reason since only `page.markdown` is read. Fixed: throttle call added, temp file deleted in a `finally` block, `extract_images=False` passed explicitly. Verified live (no new leftover temp file after a fresh fetch; content still extracts correctly).

### Verification
- [x] Import/build sanity check — `SOURCES` imports cleanly with all 5 new entries (37 total sources), no id collisions.
- [x] Every new source's full fetch → content-gate pipeline verified live via `fetch_preview.py`, fetch-only (zero LLM cost) — all 5 pass `check_content_usable()`, real current content confirmed for each.
- [x] `tests/test_content_gate.py`: 13/13 passing (12 + 1 new regression test for the `data:` URI false positive).
- [ ] Full LLM-inclusive `pytest tests/test_sources.py` **not** run for any of the 5 new sources, per the fetch-dev-no-llm-by-default direction — this is now the single biggest gap before calling any of this session's source-discovery work "shippable."

### Further Notes
- This row remains partially open: 1 of 4 named securities firms solved (SSI), 2 of 3 named consumer-research firms solved (Decision Lab, Q&Me) — both rows are usable but not fully populated. VCBS/BSC's SPA-routing problem and Cimigo's staleness are documented above for whoever picks this back up, rather than silently dropped.
- Still open, unrelated to this pass: annual reports/AGM documents (Layer 3, parked mid-discovery — see `.scratch/layer3-annual-reports/spec.md`), GSO stats, app-store release notes (6 apps), Phase 3 structuring-prompt quality.

## v0.14 — GSO/NSO stats (✅ done, domain migration found)

First real work on `source_plan_mvp0.md` §6.3's GSO row. The plan's own listed domain (`gso.gov.vn`) turned out to be genuinely dead — confirmed live: DNS resolves and ICMP ping succeeds, but a raw TCP connect on port 443 times out (a dead host, not a WAF/anti-bot block, and not an environment-wide network issue, since `sbv.gov.vn` connects fine from the same check). GSO (General Statistics Office) was renamed NSO (National Statistics Office); the real, live successor site is `nso.gov.vn`.

- [x] **`nso_data_and_statistics_official`** — a general releases-archive feed (matching the `chinhphu_legal_documents_official` "general feed + LLM filters for relevant topics" pattern), since NSO's dedicated GDP category page uses a PxWeb data-table interface (out of scope for this pass — a genuinely different, more complex integration than a crawlable HTML page). `SITE_CONFIGS["nso.gov.vn"]`'s `.archive-container` selector scopes past a large nav/category-tree menu. Confirmed live: real, current (Aug 2026) releases — CPI, industrial production index, exports/imports, socio-economic performance. CPI itself is already covered by the existing `vietnam_cpi_official`; this source is for whenever this general feed happens to carry GDP/VHLSS/labor figures instead.

### Verification
- [x] Import/build sanity check — `SOURCES` imports cleanly with the new entry (38 total sources), no id collisions.
- [x] Full fetch → content-gate pipeline verified live via `fetch_preview.py`, fetch-only (zero LLM cost) — real, current, dated content confirmed.
- [x] Offline test suite (`test_content_gate.py` + `test_tier_fact_opinion.py` + the pure-code subset of `test_bug_fixes.py`): 21/21 passing, unaffected by this change.
- [ ] Full LLM-inclusive `pytest tests/test_sources.py` **not** run, per the fetch-dev-no-llm-by-default direction.

### Further Notes
- NSO's dedicated National Accounts (GDP) category page exists but serves data via PxWeb tables, not plain HTML — a genuinely different scraping problem (a structured statistical database interface) than anything else in this file. **Update: solved in v0.16 below**, not left open after all.
- VHLSS (household income/expenditure survey) has its own dedicated page under NSO's "Health, Culture, Sport, Living standards..." category, not yet investigated — the general feed may or may not surface VHLSS releases depending on publication cadence (annual).
- Still open: annual reports/AGM documents (Layer 3, parked mid-discovery — see `.scratch/layer3-annual-reports/spec.md`), app-store release notes (6 apps), Phase 3 structuring-prompt quality, and the single biggest cross-cutting gap — zero of this session's ~33 new sources have been LLM-verified yet.

## v0.15 — App-store release notes, all 6 named apps (✅ done, Google Play dead end found)

First real work on `source_plan_mvp0.md` §4's app-store release-notes row. Google Play's app detail page turned out to have genuinely lost its public "What's New" section — confirmed live: absent from the entire ~1.2MB rendered page for a real, live app (Techcombank Mobile), not a fetch/rendering problem. Apple's App Store still has one, so all 6 apps are sourced from there instead.

- [x] **All 6 apps solved directly**: `techcombank_mobile_release_notes`, `vcb_digibank_release_notes`, `bidv_smartbanking_release_notes`, `mbbank_app_release_notes`, `acb_one_release_notes`, `vpbank_neo_release_notes`. `SITE_CONFIGS["apps.apple.com"]`'s `#mostRecentVersion` selector scopes to just the version-history section. One real gotcha along the way: the page's actual heading uses a curly right-single-quote ("What's New" with `’`, not `'`) — a first plain-text keyword search for "what's new" (straight apostrophe) missed it entirely and wrongly looked like the section didn't exist there either.
- [x] Content quality genuinely varies by bank, confirmed live: BIDV and ACB give specific, real per-version feature notes (a new insurance product, certificate of deposit, smart term deposit, eSIM top-up); Techcombank/VCB/MB mostly repeat generic "faster, more stable, more secure" boilerplate release over release. Both kinds are included as-is — even the generic boilerplate is the bank's own genuine self-disclosed update cadence, which is what the plan's row actually asks for ("new features self-disclosed by the bank, update history").

### Verification
- [x] Import/build sanity check — `SOURCES` imports cleanly with all 6 new entries (44 total sources), no id collisions.
- [x] Every new source's full fetch → content-gate pipeline verified live via `fetch_preview.py`, fetch-only (zero LLM cost) — all 6 pass `check_content_usable()`, real current version history confirmed for each, none need chunking (2.1K-11.4K chars).
- [x] Offline test suite (`test_content_gate.py` + `test_tier_fact_opinion.py` + the pure-code subset of `test_bug_fixes.py`): 21/21 passing, unaffected by this change.
- [ ] Full LLM-inclusive `pytest tests/test_sources.py` **not** run, per the fetch-dev-no-llm-by-default direction.

### Further Notes
- This closes out every named source-discovery row in `source_plan_mvp0.md` except annual reports/AGM documents (Layer 3, still parked mid-discovery — see `.scratch/layer3-annual-reports/spec.md`) and Layer 4's VHLSS/GDP-specific figures (NSO's dedicated pages use a PxWeb data-table interface, see v0.14).
- The single biggest remaining cross-cutting gap: zero of this session's ~39 new sources have been LLM-verified yet — every one of them (this entry included) is fetch-only-confirmed. A real-LLM spot-check across a representative sample is the natural next step before calling any of this "shippable."

## v0.16 — NSO GDP figures via PxWeb (✅ done, real click simulation)

Closes out the PxWeb gap left open in v0.14. NSO's GDP data lives behind a genuine PxWeb statistical-database UI (classic ASP.NET WebForms) — a real, solvable integration, not a dead end, once approached with real click simulation instead of a plain fetch.

- [x] **`nso_gdp_key_indicators`** — the "Key indicators on national accounts" table (GDP at current prices, per-capita GDP, growth rate, gross capital formation, and more). Two real gotchas found and worked around: (1) the page's "Continue" button looks like a plain link, but a raw JS-level `.click()` reset the selection to 0 cells instead of submitting (confirmed live) — ASP.NET's postback needs the listbox's actual selection state set via a genuine browser selection API (Playwright's `select_option`, which fires a proper `change` event), not just a DOM click; (2) the resulting table URL's `rxid` is a server-side session id, not a stable/shareable link — confirmed live that re-fetching it in a fresh browser session just redirects back to the selection form, so the real table text has to be read from the very page that just submitted the form, in the same session. This is why `_fetch_nso_pxweb_table_text` (renamed in v0.17 below once it turned out to be fully generic, not GDP-specific) uses crawl4ai's `on_page_context_created` hook to get a real Playwright `page` handle — the only fetch function in this file that needs this, since every other custom fetch only needs `js_code`. Confirmed live: real, current GDP figures for the 3 latest available years (2022: 9,621,371.8 bn VND; 2023: 10,319,058.9 bn VND; 2024 Prel.: 11,510,328.9 bn VND; growth rates 8.5%/5.0%/7.0%).
- [x] `nso_data_and_statistics_official`'s prompt updated to explicitly exclude GDP (now covered by this dedicated source) alongside the CPI exclusion already there.

### Verification
- [x] Import/build sanity check — `SOURCES` imports cleanly with the new entry (45 total sources), no id collisions.
- [x] Full fetch → content-gate pipeline verified live via `fetch_preview.py`, fetch-only (zero LLM cost) — real, current GDP table confirmed, reproduced across multiple independent runs (not a one-off fluke).
- [x] Offline test suite (`test_content_gate.py` + `test_tier_fact_opinion.py` + the pure-code subset of `test_bug_fixes.py`): 21/21 passing, unaffected by this change.
- [ ] Full LLM-inclusive `pytest tests/test_sources.py` **not** run, per the fetch-dev-no-llm-by-default direction.

### Further Notes
- This closes essentially every named source-discovery item from `source_plan_mvp0.md` except annual reports/AGM documents (Layer 3, still parked — see `.scratch/layer3-annual-reports/spec.md`) and VHLSS (not yet investigated, separate from GDP). **Update: VHLSS solved in v0.17 below.**
- The single biggest remaining cross-cutting gap, unchanged: zero of this session's ~40 new sources have been LLM-verified yet.

## v0.17 — VHLSS household income/expenditure via the same PxWeb mechanism (✅ done)

Closes the last open item noted in v0.16. VHLSS (Vietnam Household Living Standards Survey) figures live on the same `pxweb.nso.gov.vn` server as GDP, just under a different theme ("Health, Culture, Sport, Living standards...", not a dedicated "VHLSS" page) — found by searching that category's own "Data" tab for "income"/"expenditure" keywords.

- [x] **`nso_vhlss_income`** / **`nso_vhlss_expenditure`** — confirmed live that `_fetch_nso_pxweb_table_text` (renamed from `_fetch_nso_gdp_table_text` here, since it turned out to need zero changes for a second and third table — PxWeb's selection-form shape is generic across every table on the server, not GDP-specific) works unchanged for both, no new logic. Real, current monthly average income/expenditure per capita, whole-country + urban/rural + 6 named regions, thousand-dong figures for the 3 latest available years.

### Verification
- [x] Import/build sanity check — `SOURCES` imports cleanly with both new entries (47 total sources), no id collisions.
- [x] Full fetch → content-gate pipeline verified live via `fetch_preview.py`, fetch-only (zero LLM cost) — both pass `check_content_usable()`, real current figures confirmed for each.
- [x] Offline test suite (`test_content_gate.py` + `test_tier_fact_opinion.py` + the pure-code subset of `test_bug_fixes.py`): 21/21 passing, unaffected by this change.
- [ ] Full LLM-inclusive `pytest tests/test_sources.py` **not** run, per the fetch-dev-no-llm-by-default direction.

### Further Notes
- This closes every named source-discovery item from `source_plan_mvp0.md` except annual reports/AGM documents (Layer 3, still parked — see `.scratch/layer3-annual-reports/spec.md`).
- The single biggest remaining cross-cutting gap, unchanged across every version this session: zero of the ~42 new sources added this session have been LLM-verified yet.

## v0.18 — OCR fallback for scan-only PDFs, standalone capability (✅ done, POC)

First work on the OCR gap noted since v0.6/v0.8: BIDV's and Vietcombank's Layer 1 filings, and `sbv_legal_directives_official`'s documents, are all scan-only PDFs that `agent/content_gate.py` correctly detects and rejects but can't recover. Built as a self-contained capability first (per `.scratch/ocr-scan-fallback/spec.md`), validated on real documents via a manual CLI, before anything automatic depends on it.

- [x] **`agent/ocr.py`** — a new isolated module (mirrors `agent/llm_fallback.py`'s role) wrapping Mistral's OCR product in Batch mode. Uses the raw `mistralai` SDK, not `langchain-mistralai` — confirmed live that the already-installed LangChain wrapper only exposes `ChatMistralAI`/`MistralAIEmbeddings`; OCR/Batch/Files are Mistral-platform features outside LangChain's chat-model abstraction entirely (different input shape — a whole document file, not a text message; different output shape — per-page structured markdown, not one reply; different pricing — per page, not per token). Same `MISTRAL_API_KEY`, a second Python package. One real SDK gotcha found during research: `mistralai` 2.9.4's top-level package has no `__init__.py` (a namespace package) — confirmed live `from mistralai import Mistral` fails; the real import is `from mistralai.client import Mistral`.
- [x] Core flow: upload a local PDF (`purpose="ocr"`) → get a signed URL → wrap it in a 1-line Batch JSONL request → upload that (`purpose="batch"`) → create the batch job against the `/v1/ocr` endpoint → poll for status → once `SUCCESS`, download and parse the result file into markdown (table structure preserved, per Mistral's own OCR output format). Batch mode (not sync) is a deliberate choice, not just a cost optimization (~half the price of sync per Mistral's pricing page, checked live 2026-09-02) — a 50+ page scanned bank filing isn't something to hold a live HTTP request open for.
- [x] Deliberately **not** auto-wired into the live `crawl → content_gate → structure` graph — OCR submission is only ever a separate, explicit action (`ocr_preview.py`, a new CLI mirroring `fetch_preview.py`'s role) for now, never an automatic side effect of a normal `/trigger` run's content-gate rejection. This matches the project's existing cost discipline (the same reasoning behind the fetch-dev-no-LLM-by-default rule) — a routine trigger of a known-scan-only source must never silently spend real, billed OCR money.
- [x] Job tracking: `agent/store.py` gains `append_ocr_job()` and a new `data/ocr_jobs.jsonl` log, same append-only-flat-file pattern as every other log this project already keeps (no SQLite introduced — an explicit decision, since this project has no database anywhere and the existing pattern already covers "durable, inspectable history" for a POC). One line per lifecycle event (submitted / completed / failed), including a page-count-based cost estimate on completion (~$2/1,000 pages, Mistral's Batch pricing checked live, explicitly labeled as a rough estimate, not an invoice figure).
- [x] No schema change — OCR-derived signals reuse the source's own existing id and the existing `confidence` field for OCR-specific uncertainty, per explicit user decision; no new "how was this obtained" marker.

### Verification
- [x] Import/build sanity check — `agent/ocr.py`, `agent/store.py`'s new function, and `ocr_preview.py` all import cleanly; all 3 existing graphs still build; 47 sources still import (unaffected).
- [x] `ocr_preview.py --help` and its not-a-file error path verified live — both exit cleanly with no network call, so no accidental cost from a malformed CLI invocation.
- [x] New `tests/test_ocr.py` (5 tests, fully offline — deliberately does **not** test the real network-calling functions, since those hit Mistral's real, billed API; matches this project's own precedent for `fetch_preview.py`'s equally-untested-by-`pytest` role): both documented-ambiguous batch-result-line wrapping shapes (`result["response"]["body"]` vs. bare `result["body"]`) parse correctly; an empty-pages result and a pages-with-blank-markdown result both correctly return "no usable text"; `append_ocr_job()` writes and reads back correctly.
- [x] Full offline suite (`test_content_gate.py` + `test_tier_fact_opinion.py` + `test_ocr.py` + the pure-code subset of `test_bug_fixes.py`): 26/26 passing.
- [ ] The real OCR call path (submit → poll → fetch against a real scanned PDF) **not** run as part of this pass — real money, and per the spec's own testing decision, validated manually via `ocr_preview.py` whenever a real document is actually run through it, not automatically.

### Further Notes
- Real output quality validated live (2026-09-02): `ocr_preview.py` run against `sbv_legal_directives_official`'s scanned "CT 02_2026.pdf" (previously documented above as producing garbled text — "ctrAm di6m", "chri d$ng") recovered 6 pages / 15,202 chars of coherent, readable Vietnamese legal text. Two real bugs found and fixed via this live run: `ocr_preview.py` was missing `load_dotenv()` (`MISTRAL_API_KEY` never loaded); `agent/ocr.py`'s `fetch_ocr_batch_result()` accessed a streaming `httpx.Response`'s `.text` without calling `.read()` first (confirmed via the SDK's own `files.py` source — `download()` returns the raw response with `stream=True`, never read).
- BIDV's and Vietcombank's Vietstock-mirror sources still need their own real OCR run before judging whether they become usable this way — not yet done, still open.
- See v0.19 for the "consume an already-completed OCR result" graph wiring — this closes the loop from a validated OCR result to a real structured signal, still without any automatic OCR submission.
- Still open, unrelated to this pass: annual reports/AGM documents (Layer 3, still parked — see `.scratch/layer3-annual-reports/spec.md`), and the standing cross-cutting gap — zero of this session's ~42 new sources have been LLM-verified yet.

## v0.19 — OCR result → structured signal wiring (✅ done, POC)

Closes the loop from v0.18: an already-completed OCR job's text now runs through the exact same LLM structuring step every other source uses, and the result lands in the same `data/signals.jsonl`/`data/signals.csv` as any normal `/trigger` output. Explicitly scoped by the user to the "consume" direction only — a normal `/trigger` run still never submits or waits on an OCR job; that stays a separate, deliberate action via `ocr_preview.py`.

- [x] **`agent/graph.py`: `build_ocr_structure_graph()`** — a third, minimal graph shape alongside `build_graph()`/`build_crawl_graph()`/`build_multi_pdf_graph()`: `checkpoint_gate → structure → END`, no crawl or content_gate node. There's nothing left to fetch (the text came from an OCR job's own result, not a live URL) and nothing left to gate (a successfully completed OCR job's markdown is, by construction, past the bar content_gate enforces for a normal crawl).
- [x] **`ocr_structure.py`** (new CLI, mirrors `ocr_preview.py`'s and `fetch_preview.py`'s role) — takes a `source_id` (looked up in `agent/sources.py` for its own `prompt`/`url`/`tier`, so OCR text is judged by that source's own extraction criteria) plus either `--job-id` (fetches the result fresh from Mistral) or `--markdown-file` (reads text already saved locally, e.g. by `ocr_preview.py`). Runs it through `build_ocr_structure_graph()` and logs via the exact same `agent/store.py` functions `service.py`'s `/trigger` loop uses (`append_topic_jsonl`, `append_topic_csv`, `append_raw_content`) — OCR-derived signals carry the source's own existing id, indistinguishable in the log from a normal crawl's output, per the same no-new-marker decision from v0.18.
- [x] Verified live end-to-end, reusing the already-completed OCR job from v0.18 (no new OCR spend): `ocr_structure.py sbv_legal_directives_official --markdown-file data/ocr_preview/sbv_ct_02_2026_test.md` produced 6 real signals — correct circular/decision numbers, dates, and subjects (e.g. "Circular No. 02/CT-NHNN dated 09 January 2026 directs the acceleration of digital transformation..."), `source_code: "SBV"`, no fabricated documents — matching `sbv_legal_directives_official`'s own prompt exactly as a normal crawl of it would.

### Verification
- [x] `tests/test_ocr.py` gains 2 new offline tests: `build_ocr_structure_graph()` feeds `search_results` straight to a mocked `_structure_one` with no crawl/content_gate step in between (same monkeypatch pattern as `test_bug_fixes.py`'s bug #5 test); an empty query is still rejected by `checkpoint_gate` before structuring runs, even with OCR text present. 7/7 passing.
- [x] Full offline-safe suite (everything except `test_sources.py`, which hits real network/LLM by design): 37/37 passing.
- [x] Live run against a real completed OCR result (above) — real signals produced, logged into `data/signals.jsonl`/`data/signals.csv` alongside normal `/trigger` output.

## v0.20 — Automatic OCR fallback in the live graph (✅ done, POC)

Reverses v0.18/v0.19's "consume-only, never auto-submit" decision, per explicit user direction: "u can trigger OCR by the graph itself dont need to run it by me, if detect scanned text use OCR fr." A normal `/trigger` run now submits and blocks on a real, billed OCR job automatically, the moment content_gate detects a scan — no CLI step in between anymore, for the sources this covers (see Out of Scope).

- [x] **`agent/content_gate.py`: `check_content_usable()` gains a `"code"` field** (`"near_empty"` / `"block_page"` / `"scan"` / `None`) alongside its existing `"reason"` prose — so the auto-OCR trigger keys off a stable value, not string-matching human-readable text. Only `"scan"` is safe to auto-OCR: it's the one rejection reason validated against a real scanned document; `"near_empty"`/`"block_page"` both fire for reasons OCR can't fix (a WAF page, a genuine fetch failure) and would just waste real money.
- [x] **`agent/ocr.py`: `ensure_ocr_text(source_id, pdf_url)`** — the automatic fallback entry point. Re-downloads the flagged PDF's raw bytes directly (crawl4ai's own PDF strategy only returns extracted text, not the source file — same `urllib` + browser User-Agent pattern already used for SSI's report fetch), submits a real Mistral Batch OCR job, blocks until it completes, and returns the recovered markdown. Guarded by a local cache (`data/ocr_cache/`, keyed by `source_id` + a hash of the PDF URL, **tracked in git** — not a `data/*_preview/` scratch dir) so the same document is never OCR'd, and never re-paid for, twice — the first `/trigger` run (or test run) to hit a given scanned document pays for it once; every run after reuses the cached text for free, on this machine or anyone else's clone of the repo. Never raises: a failed download or OCR job just leaves the piece dropped, exactly as before this fallback existed.
- [x] **`agent/graph.py`: `_content_gate_multi_node`** — a piece rejected with code `"scan"` now gets one more chance before being dropped: `ensure_ocr_text()` runs, and its result is re-checked through `check_content_usable()` before being trusted (an OCR result that's itself still unusable — e.g. empty — is dropped, not blindly kept). `AgentState` gains a `"source_id"` field (populated by `service.py`'s `/trigger` loop from `agent/sources.py`'s own id) so the OCR job/cache can be tagged and keyed correctly.
- [x] **Scope: only the multi-PDF path (`build_multi_pdf_graph`)** — its `pdf_texts` state already carries each document's exact, real PDF URL. The single-fetch path (`build_crawl_graph`, e.g. `bidv_financial_statements`) does **not** get this fallback yet: each of its per-site fetch functions in `agent/crawler.py` (one per bank/page — BIDV's own resolver, ACB's documents API, MBBank's Vietstock mirror, etc.) currently returns only extracted text, discarding the resolved PDF URL it fetched from internally. Threading that URL back through every one of those functions is a separate, real plumbing change, not done in this pass — flagged to the user directly, not silently skipped. In practice this means today's automatic fallback covers `sbv_legal_directives_official` and `sbv_press_releases_official` (both `multi_pdf: True`), not `bidv_financial_statements`.

### Verification
- [x] `tests/test_content_gate.py`'s 3 existing multi-node tests updated to monkeypatch `agent.ocr.ensure_ocr_text` (previously would have made a real, unmocked HTTP call to a fake `example.com/scan.pdf` URL on every offline test run — caught before landing). 2 new tests added: OCR recovering a piece keeps it with the recovered text; an OCR result that's still unusable after recovery is dropped, not trusted blindly. 24/24 passing.
- [x] Full offline-safe suite (everything except `test_sources.py`): 39/39 passing (re-confirmed after the bug fix below).
- [x] **Real bug found and fixed live**: `ensure_ocr_text()`'s raw-bytes downloader (`urllib.request`) rejected sbv.gov.vn's real document URLs outright (`InvalidURL: URL can't contain control characters`) — their PDF paths come back from the page with a literal, unescaped space (e.g. `.../CT 02_2026.pdf/...`), not percent-encoded. Fixed with `urllib.parse.quote()` before building the request; re-verified live against the real URL (no more `InvalidURL`, a real HTTP round-trip completes).
- [x] **Live end-to-end run attempted 3x against the real `sbv_legal_directives_official` source** (via `build_multi_pdf_graph()` + `service._run_item`, the actual `/trigger` code path) — did not reach a real OCR submission this session: sbv.gov.vn's WAF (already documented as flaky for this exact domain, see v0.8/v0.14) served a genuine "Request Rejected" block page on every attempt across all 3 documents' PDF paths *and*, on the 3rd attempt, the listing page itself — confirmed identically by two independent fetchers (crawl4ai's own PDF strategy and `ensure_ocr_text()`'s direct downloader), so this is the live site's own current state, not a bug. One useful thing this **did** prove live: `check_content_usable()`'s `"block_page"` code correctly does **not** trigger the OCR fallback (3rd attempt) — only `"scan"` does, exactly as designed; wasting no money on a rejection OCR can't fix. The actual `"scan"` → `ensure_ocr_text()` → recovery logic is fully covered by the 2 new offline tests above (mocked, deterministic, run every test pass) — pending a live confirmation the next time `/trigger` runs while sbv.gov.vn's WAF happens to be open (matches this domain's own established intermittent pattern).

### Out of Scope
- The single-fetch path's auto-OCR wiring (`bidv_financial_statements` and friends) — needs the `agent/crawler.py` URL-threading refactor noted above first. **Update: done in v0.21 below**, same session.
- BIDV's known worst case (a PDF with real text only on its first 2 of 56 pages) isn't caught by `check_content_usable()` at all today — clean cover-letter text doesn't trip the corrupted-token-ratio check, and isn't near-empty either. **Update: solved in v0.21 below** via a second, PDF-specific check.
- No spend-limit/kill-switch was added — every `/trigger` run (and, incidentally, every `tests/test_sources.py` run) can now trigger real OCR spend on first encounter with an un-cached scanned document. The per-document cache (tracked in git) means this is a one-time cost per document, not a recurring one, which was judged sufficient guardrail for this reversal rather than adding an unrequested toggle.

## v0.21 — BIDV's real failure mode: partial-scan detection + single-fetch path OCR wiring (✅ done, verified live)

Closes both items v0.20 left open. Before building anything, checked what BIDV's *actual current live filing* looks like (rather than assuming the corrupted-ratio "scan" check from v0.20 would apply) — it's the exact case DEVELOPMENT_PLAN.md already flagged as undetectable: a 57-page reviewed interim statement with real, clean cover-letter text on pages 1-2 and 0 chars of extractable text on the other 55. Clean text doesn't trip `"scan"`; a fundamentally different check was needed, not just wiring the existing one into a second graph path.

- [x] **`agent/content_gate.py`: `check_pdf_page_density(pdf_bytes)`** — a second, PDF-specific gate (needs real page count, which only a fresh download can give it, unlike `check_content_usable()`'s text-only check). Parses with `pypdf`, flags `"partial_scan"` when more than `MAX_BLANK_PAGE_RATIO` (0.6) of a document's pages have under `MIN_CHARS_PER_PAGE` (20) chars of extractable text — skipped entirely for documents under `MIN_PAGES_FOR_DENSITY_CHECK` (5) pages, to avoid flagging a genuinely short, legitimate document. Calibrated against one real live measurement: BIDV's actual filing scored 55/57 blank pages (96.5%) — comfortably clear of the 0.6 threshold.
- [x] **`agent/crawler.py`: `_crawl_async` now returns `(text, pdf_texts)`** instead of just `text` — the PDF URL info was already being computed via `_fetch_selected_pdfs` (shared with the multi-PDF path) and simply discarded 2 lines later. `crawl()` stays a thin wrapper unpacking just the text (backward compatible — `fetch_preview.py` untouched); new `crawl_with_pdf_urls()` exposes both. Only 2 real callers of `crawl()` existed in the whole codebase, confirmed via grep before touching the signature.
- [x] **`agent/graph.py`: `_crawl_node`/`_content_gate_node`** — `_crawl_node` now also returns `pdf_texts`; `_content_gate_node` runs two independent OCR-eligible checks (only when `pdf_texts` has exactly one piece, the only shape that exists today): the existing `"scan"` code (corrupted-ratio) from v0.20, and the new `check_pdf_page_density()` result when the text-level check *passes* but the PDF itself is mostly blank. Either failure gets one shot at `ensure_ocr_text()` before being rejected, substituting the recovered text into the flattened `search_results` string via the exact substring `_crawl_async` itself builds (`"--- Full content of {pdf_url} ---"`), then re-checking before trusting it.
- [x] **`agent/ocr.py`: `download_pdf_bytes()` switched from `urllib.request` to `requests`** — real bug found live: BIDV's WCM-served PDF URLs (`wps/wcm/connect/...?MOD=AJPERES&CACHEID=...`) reject a plain `urllib` GET outright (an HTML error page back, or the connection closed mid-response) but succeed via `requests` with no special headers — exactly matching what crawl4ai's own `PDFContentScrapingStrategy` does internally to fetch these same URLs. Renamed `_download_pdf_bytes` → `download_pdf_bytes` (public) since `_content_gate_node` now calls it too, for the page-density pre-check.
- [x] `requests>=2.31` and `pypdf>=4.0` added to `requirements.txt` explicitly (both were already transitive via crawl4ai; now directly imported).

### Verification
- [x] 7 new offline tests in `tests/test_content_gate.py` (4 for `check_pdf_page_density`, mocking `PdfReader` for deterministic control over page count/content; 3 for `_content_gate_node`'s new OCR wiring, both failure shapes). 46/46 offline-safe tests passing.
- [x] **Real safety issue found and fixed via this pass's own live testing**: `tests/test_bug_fixes.py` has 2 pre-existing real-network tests (by original design) that route through `build_crawl_graph`/`build_multi_pdf_graph` — neither mocked `ensure_ocr_text`, so a routine offline-suite run silently spent a real ~$0.11 OCR job against BIDV's real filing as an unintended side effect (confirmed: it happened, once, during this pass's own regression runs, before the fix). Both tests now mock `agent.ocr.ensure_ocr_text` via a shared `_no_ocr_spend()` helper; the one test that specifically needs content_gate to pass (to reach the structuring step it's actually testing) mocks a plausible recovered-text stand-in instead of `None`.
- [x] **Full live end-to-end run against the real `bidv_financial_statements` source** (via `build_crawl_graph()` + `service._run_item`, the real `/trigger` code path, no shortcuts): content_gate correctly flagged "55/57 pages (96.5%) have under 20 chars of extractable text"; `ensure_ocr_text()` automatically submitted a real Mistral Batch OCR job (57 pages, ~$0.114, job `116cac48-df7c-4b92-bfb4-2fcad61f90df`) with no manual step; OCR recovered real content including an actual profit table; Groq hit its per-request size ceiling (413) and Gemini timed out (504) on the large recovered text, and the existing Groq→Gemini→Mistral fallback chain correctly landed on Mistral chat (`mistral-small-2603`) for the actual structuring call. Final result: `gate_passed: True`, 3 real signals — BIDV's consolidated customer loan balance (2,501,807,043 million VND, up from 2,372,955,074), consolidated customer deposit balance (2,261,489,130 million VND, up from 2,222,991,628), and consolidated net interest income (33,537,974 million VND, up from 28,937,315) for the 6 months ended 30/06/2026. This source produced zero usable financial data before this pass.

### Out of Scope
- Vietcombank's own Vietstock-mirror filing (also a scan-only PDF, per v0.6/v0.18) not yet run through either OCR path — no source currently routes it through `build_crawl_graph`/`build_multi_pdf_graph` with a real PDF URL the way BIDV's does; not attempted this pass.
- `check_pdf_page_density()`'s thresholds are calibrated against exactly one real document (BIDV's). No counter-example (a real, legitimate multi-page document with some genuinely blank pages) was available to validate against — the 0.6 threshold was picked with a large margin below the 0.965 real measurement specifically to reduce that risk, but it's a judgment call, not a validated boundary the way the corrupted-ratio threshold is.
- Still no spend-limit/kill-switch, same call as v0.20 — the per-document cache remains the only guard against repeat spend.

## v0.22 — Three real, user-found content bugs: sbv_portal_statistics, iav_bancassurance, mbb_financial_statements (✅ done, verified live)

All three found by the user directly reviewing the Phase 1 review dashboard (raw vs. extracted, side by side) — not from a heuristic or a test. Each is a genuinely different failure shape, not one bug in three places.

- [x] **`sbv_portal_statistics` — was always pure nav/footer boilerplate, never real statistics.** The "chunked: True" flag on the old URL (`/en/statistics`) was masking a content bug as a size problem — confirmed live the 42K+ chars were 100% nav/menu/footer, zero real content, on every single fetch since this source was added. Found via a real hover (not click) on the Vietnamese site's own "Dữ liệu thống kê" nav dropdown (the English site has no equivalent) — surfaced ~199 real monthly/quarterly system-wide banking statistics reports. Swapped to one of them, `https://sbv.gov.vn/vi/thong-ke-mot-so-chi-tieu-co-ban` (basic indicators — total assets, charter capital, funding ratios, loan-to-deposit ratio, per institution type + a system-wide total row): needs a new URL-keyed `SITE_CONFIGS` entry (`needs_js: True`, `content_selector: "article"` — the page's first `<article>` is the real data table, a second one right after is just a "related reports" list, `select_one()` naturally picks the first). Confirmed live: 2,286 chars once scoped — no longer needs chunking either, `"chunked": True` removed.
- [x] **`iav_bancassurance` — only ever scraped the listing page's own text (titles + dates), never followed into articles.** The URL was already right (category 202, "Tổng quan, số liệu thị trường Bảo hiểm" — Insurance Market Overview, matching source_plan_mvp0.md §3.4's total-market-only scope exactly) — the bug was purely never clicking through. New `agent/crawler.py`: `_fetch_iav_market_overview_parts()` finds the 3 most recent real "Tổng quan thị trường bảo hiểm Việt Nam ..." article links already on that page and fetches each one's own body text. Switched from `"chunked": True` to `"multi_pdf": True` (these are genuinely separate documents now, not one page needing arbitrary splitting).
- [x] **`mbb_financial_statements` — a real, measured near-miss on the corrupted-ratio threshold.** User-reported garbled excerpt ("Oja chi: s6 18 Le Van LLl'O'ngPhU'O'ng...") measured live at `corrupted_token_ratio = 0.0477` — just under the 0.05 "scan" threshold, so it silently passed `content_gate` despite being a genuine re-OCR'd mirror (this Vietstock copy is itself already an OCR'd scan, per this source's own pre-existing comment). Two changes: (1) `_fetch_vietstock_statement_text()` now returns `(text, pdf_url)` instead of discarding the winning candidate's URL — needed regardless, since it was previously impossible for this source to become OCR-eligible at all; (2) a new declarative `"assume_scan": True` source flag, handled in `_content_gate_multi_node`, that tries `ensure_ocr_text()` **first**, before the normal per-piece check even runs — not gated on `check_content_usable()` flagging it, since the whole point is that it doesn't reliably flag this specific source. Deliberately not a global threshold change (real risk of new false positives elsewhere, no counter-example data to validate against) and not a hardcoded source-id check buried in `graph.py` (a declarative per-source flag, same pattern as `chunked`/`multi_pdf`/`tier`).
- [x] **Real regression found and fixed via this pass's own work, before it shipped**: `agent/crawler.py`'s `_crawl_chunked_async()` — used by every `"chunked": True` source (Techcombank, ACB, MBB, BIDV/ACB/MBBank fee schedules) — was still unpacking `_crawl_async()`'s OLD single-value return (`text = await _crawl_async(url)`) after v0.21 changed that function to return `(text, pdf_texts)`. Every chunked source would have crashed on its next real run. Fixed while implementing MBB's fix (which needed to trace this exact path) — no test caught it, since `test_sources.py`'s real-network sources tests weren't run between v0.21 and this fix; caught by direct live tracing instead. Also threads the real resolved PDF URL through chunked sources when one is known (not just the landing page), extending OCR-eligibility to Techcombank's chunked path too, as a side effect of the fix, not a separate change.

### Verification
- [x] Full offline-safe suite: 46/46 passing after the `_crawl_chunked_async` fix (unaffected by it directly, but re-run to confirm no fallout).
- [x] **All three fixes verified fully live, no shortcuts** — real `/trigger` code path, real network, real LLM calls:
  - `sbv_portal_statistics`: 9 real signals, one per institution type + a system-wide total, real 30/06/2026 data. Zero real signals possible before this fix.
  - `iav_bancassurance`: 3 real signals — total life-insurance premium revenue for 9M/6M/Q1 2025, each with a real YoY growth percentage. Previously only ever produced headline-only summaries.
  - `mbb_financial_statements`: real OCR job auto-submitted (assume_scan correctly bypassed content_gate's own borderline "usable" verdict), 5 real signals — loan balance (1,227,554,477M VND, +13.24%), deposit balance, demand/term deposit split, all internally consistent — a real, marked improvement over the pre-fix garbled/unreliable extraction.
- [x] `crawl_chunked()`'s regression fix verified live against a real chunked source (ACB fee schedule) — confirmed no crash, correct `(list_text, documents)` shape, existing (non-MBB) behavior unchanged (still cites the landing page URL when no single real document URL is known).

### Out of Scope
- `sbv_portal_statistics` only pulls one of the ~199 available report types (basic indicators). CAR and ROA/ROE are real, separate report pages under the same nav section — not pulled this pass, deliberately scoped to one report rather than a rewrite into a multi-document source.
- Techcombank's chunked path getting real PDF-URL threading (a side effect of the regression fix) was not separately live-verified for OCR-eligibility — only confirmed the crash is fixed and the shape is correct.

## v0.23 — Two more user-found click-through bugs: `mbbank_news`, `acb_promotions` (✅ done, verified live)

Both found by the user re-checking their own already-"solved" v0.10 sources: *"you did not click inside the actual article right?"* (mbbank_news), then *"you also didn't click actual promotion detail with acb_promotions"*. Less severe than IAV's original case (both listings already had real, informative teaser text — a depth problem, not a fabrication problem), but real, verifiable content gaps all the same. Same root cause both times: a source that looked "solved" (real fetch, real signals, real network capture for ACB) but stopped one hop short of the actual document.

- [x] **`mbbank_news` only ever extracted the listing page's own teaser text, never followed into the article.** New `agent/crawler.py`: `_fetch_mbbank_news_parts()` fetches the listing (same JS-predicate wait as v0.10's fix), pulls up to 3 `a[href*='/chi-tiet/']` article links, then fetches each detail page with `delay_before_return_html=3.0` — a fixed delay, not a JS-predicate wait, since the article template renders a literal `"Nội dung này không tồn tại!"` placeholder without one — scoped to `.mb-news-details-content`. `agent/sources.py`: swapped `"chunked": True` → `"multi_pdf": True` (separate documents, matching IAV's own precedent).
- [x] **`acb_promotions`'s own detail API call (added in v0.10) was hitting the wrong endpoint's field.** `long_description` is null on every real promo checked; the `short_description` field it was using is itself just a ~70-char listing teaser, not the real terms. The real body only exists on the public, server-rendered detail page (`acb.com.vn/vi/uu-dai/{slug}` — a Next.js SSR page, no JS wait needed, same lightweight `AsyncHTTPCrawlerStrategy` as the existing API calls). `_fetch_acb_promotions_text()` now also fetches that page per promo and uses the real body text (scoped to the parent of the page's first `id="block-id-N"` element — clean of nav/footer) whenever it's longer than the API's stub description.
- [x] **Real bug found and fixed in `review_dashboard.py`'s `_merge_runs()` while building the Phase 4 presentation**: it never copied `token_usage` into its merged output dict, silently breaking any downstream "was this a real run" check that relies on token spend (the dashboard's own display doesn't need it, so this went unnoticed). Fixed by adding `"token_usage": rec.get("token_usage")` to the merge; verified by confirming `sbv_press_releases_official` (a real run that spent tokens but found 0 new signals) went from wrongly-excluded to correctly-counted.

### Verification
- [x] Live end-to-end (`/trigger` code path, real network, real LLM calls), both sources:
  - `mbbank_news`: `gate_passed=True`, 3 real signals — exact prize amounts for a minigame (1,000,000 / 500,000 / 200,000 VND) with a claim deadline, the "Hoa va Rac" 2026 partnership, and a specific recycled-bag product tied to that partnership — the last of these was invisible in the pre-fix teaser-only extraction.
  - `acb_promotions`: `gate_passed=True`, 6 real signals (up from what a ~70-char-per-promo teaser could ever support) — a real 0.8% online-savings rate boost, a 50%-cashback offer with its exact eligible spending categories and first-30-days window, an iPhone 17 Pro Max reward tier, none of which existed in the API's short description.
- [x] Full offline-safe suite: 46/46 passing after the `mbbank_news` fix; re-run after the `acb_promotions` fix too.

### Out of Scope
- `run_todo_sources.py`'s live, user-run batch job may still process `mbbank_news` with the pre-fix code if it reached that source before this fix landed (Python doesn't hot-reload a running process) — a targeted re-run via `service.trigger(source_ids="mbbank_news")` covers that if needed.

## Maintenance fixes

- [x] Swapped AI model: Groq shut down `llama-3.3-70b-versatile` (and `llama-3.1-8b-instant`) on 2026-08-16. Now defaults to `openai/gpt-oss-120b` (overridable via `GROQ_MODEL`).
  - *Plain terms: the specific AI model this was built on got discontinued by its provider right after setup. Swapped to the provider's official suggested replacement.*
- [x] Fixed stale comment in `.env.example` still referencing the deprecated `llama-3.3-70b-versatile` as the default.
- [x] **Rebuilt `presentation.py`'s architecture diagram to remove crossing/overlapping edges** (user-flagged, 2026-09-03): two lanes now sit in fully separate row bands, `ensure_ocr_text()` moved into its own vertical lane directly between the two content_gate boxes (short symmetric arrows instead of long arcs), the LLM fallback chain got its own row below both structure nodes with straight vertical drops (structure's box shifted right of structure_multi's column so its drop line has a clear channel — the bottom lane's row is fully packed with boxes/wires otherwise). Purely visual — node content and the underlying graph are unchanged; verified analytically since this is a static SVG string, not a live render.
- [x] **Made UTF-8 encoding explicit on every file read/write in the codebase** (user-flagged mojibake report, 2026-09-03): every `open()`/`write_text()`/`read_text()` call across `agent/store.py`, `agent/llm_fallback.py`, `agent/ocr.py`, `service.py`, `presentation.py`, `review_dashboard.py`, and the preview scripts relied on Python's locale-default encoding instead of declaring `encoding="utf-8"` — harmless on this Mac (UTF-8 locale) but a real portability gap for any other locale. Also set `response.encoding="utf-8"` before reading Mistral's OCR batch-download response. Direct byte inspection found no actual corruption currently present (data files, generated HTML, and the live published artifact were all already valid UTF-8) — this is a defensive fix, not a data repair. Round-trip verified: Vietnamese diacritics + em dash + arrow written and read back byte-exact through the fixed `store.py` functions in an isolated temp dir.

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
