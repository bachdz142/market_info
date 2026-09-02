# Changelog

Dated, terse technical record of this project's revisions. Not strict
semver — this is an internal MVP0 demo, versioned by milestone rather than
package release. For plain-English progress tracking see
`DEVELOPMENT_PLAN.md`; for architecture/design rationale see `MVP0_PLAN.md`.

## Unreleased — Automatic OCR fallback in the live graph

- Reverses the earlier "consume-only, never auto-submit" OCR decision,
  per explicit user direction. `agent/content_gate.py`'s
  `check_content_usable()` gains a machine-readable `"code"` field
  (`near_empty`/`block_page`/`scan`/`None`); `agent/graph.py`'s
  `_content_gate_multi_node` now gives a `"scan"`-coded piece one more
  chance via `agent/ocr.py`'s new `ensure_ocr_text()` before dropping it
  — real, billed Mistral OCR, run automatically, no CLI step. Guarded by
  a per-document cache (`data/ocr_cache/`, tracked in git) so the same
  PDF is never OCR'd twice across repeated `/trigger` runs.
- Scoped to the multi-PDF path only (`sbv_legal_directives_official`,
  `sbv_press_releases_official`) — the single-fetch path (BIDV, etc.)
  needs a separate `agent/crawler.py` refactor to expose each source's
  resolved PDF URL first; not done this pass, flagged directly.
- Real bug found and fixed live: the new raw-bytes downloader rejected
  sbv.gov.vn's actual document URLs (`InvalidURL`) — their paths carry a
  literal unescaped space, not percent-encoding. Fixed with
  `urllib.parse.quote()`.
- `tests/test_content_gate.py`'s existing multi-node tests now mock
  `agent.ocr.ensure_ocr_text` (previously an accidental unmocked real
  HTTP call on every offline test run) + 2 new tests for the recovery
  path itself. 24/24 passing.
- Live end-to-end run attempted 3x against the real source; sbv.gov.vn's
  already-documented WAF flakiness blocked every attempt before OCR
  could fire — did confirm live that `"block_page"` rejections correctly
  never trigger OCR (only `"scan"` does). Full recovery logic covered by
  the new offline tests; live confirmation pending a future `/trigger`
  run.

## Unreleased — OCR result -> structured signal wiring

- Added `agent/graph.py`'s `build_ocr_structure_graph()`: a minimal
  `checkpoint_gate -> structure -> END` graph (no crawl/content_gate node
  — an already-completed OCR job's text has nothing left to fetch or
  gate) and `ocr_structure.py`, a new CLI that takes a `source_id` plus
  `--job-id` or `--markdown-file`, runs the OCR text through that graph
  using the source's own `prompt`/`url`/`tier`, and logs the result via
  the same `agent/store.py` functions `/trigger` uses — OCR-derived
  signals land in `data/signals.jsonl`/`data/signals.csv` indistinguishable
  from normal crawl output, keeping the source's own id.
- Scoped explicitly to "consume an already-submitted result" only — still
  no automatic OCR submission on a content_gate rejection; that stays a
  separate, deliberate action via `ocr_preview.py`.
- Verified live end-to-end reusing the already-completed OCR job from the
  entry below (no new OCR spend): 6 real, correctly-dated regulatory
  signals produced from `sbv_legal_directives_official`'s recovered text.
- `tests/test_ocr.py` gains 2 offline tests (mocked `_structure_one`,
  same pattern as `test_bug_fixes.py`'s bug #5 test) covering the new
  graph's shape: OCR text reaches structuring directly, and an empty
  query is still rejected by `checkpoint_gate` first.

## Unreleased — OCR fallback for scan-only PDFs (Mistral, Batch mode, POC)

- Added `agent/ocr.py`, a new isolated module (mirrors `agent/llm_
  fallback.py`) wrapping Mistral's OCR product in Batch mode, using the
  raw `mistralai` SDK (not `langchain-mistralai`, confirmed live to only
  expose `ChatMistralAI`/`MistralAIEmbeddings` — OCR/Batch/Files are
  outside LangChain's chat-model abstraction entirely). Gotcha: `mistralai`
  2.9.4's top-level package has no `__init__.py` — the real import is
  `from mistralai.client import Mistral`, not `from mistralai import
  Mistral`.
- Flow: upload PDF (`purpose="ocr"`) -> signed URL -> 1-line Batch JSONL
  request -> upload that (`purpose="batch"`) -> create batch job against
  `/v1/ocr` -> poll -> download + parse result into markdown (table
  structure preserved).
- New `ocr_preview.py` CLI (mirrors `fetch_preview.py`) is the *only* way
  an OCR job gets submitted right now — deliberately not auto-wired into
  the live graph, so a routine `/trigger` never silently spends real,
  billed OCR money on a known-scan-only source.
- `agent/store.py` gains `append_ocr_job()` + `data/ocr_jobs.jsonl` (same
  append-only pattern as every other log here, no SQLite introduced).
  Logs submission/completion/failure, with a page-count-based cost
  estimate (~$2/1,000 pages, Mistral's Batch pricing) on completion.
- No schema change — OCR-derived signals reuse the source's own id and
  the existing `confidence` field.
- New `tests/test_ocr.py` (5 tests, fully offline) covers the pure
  batch-result-line parsing logic and job logging — the real network
  calls are deliberately untested, same precedent as `fetch_preview.py`.
- Designed via `/grill-with-docs` + `/to-spec` —
  `.scratch/ocr-scan-fallback/spec.md`.

## Unreleased — VHLSS household income/expenditure (same PxWeb mechanism)

- Added `nso_vhlss_income` and `nso_vhlss_expenditure` — found on the
  same `pxweb.nso.gov.vn` server as GDP, under a different theme
  ("Health, Culture, Sport, Living standards...", not a dedicated
  "VHLSS" page).
- `_fetch_nso_pxweb_table_text` (renamed from `_fetch_nso_gdp_table_
  text`, since it turned out to need zero changes for these) worked
  unchanged for both — PxWeb's selection-form shape is generic across
  every table on the server, not GDP-specific.
- Closes every named source-discovery item in `source_plan_mvp0.md`
  except annual reports/AGM (still parked). 47 total sources.

## Unreleased — NSO GDP figures via PxWeb (real click simulation)

- Closes the PxWeb gap left open in the previous NSO entry. Added
  `nso_gdp_key_indicators` — real GDP figures via NSO's genuine PxWeb
  statistical-database UI (classic ASP.NET WebForms), not a plain HTML
  page.
- Two gotchas: (1) the "Continue" button looks like a plain link, but
  a raw JS-level `.click()` resets the selection to 0 cells instead of
  submitting — ASP.NET's postback needs the listbox's real selection
  state set via Playwright's `select_option` (fires a proper `change`
  event), not just a DOM click; (2) the resulting table URL's `rxid`
  is a server-side session id, not a stable link — a fresh session
  just redirects back to the form, so the table text is read from the
  live session that just submitted it, not fetched again afterward.
- New `_fetch_nso_gdp_table_text` uses crawl4ai's
  `on_page_context_created` hook to get a real Playwright `page`
  handle — the only fetch function in this file needing it (every
  other custom fetch only needs `js_code`).
- `nso_data_and_statistics_official`'s prompt updated to exclude GDP
  (now covered by the dedicated source) alongside the existing CPI
  exclusion.

## Unreleased — App-store release notes, all 6 named apps (Google Play dead end found)

- Google Play's app detail page no longer has a public "What's New"
  section at all — confirmed live: absent from the entire ~1.2MB
  rendered page for a real, live app. A genuine Play Store redesign,
  not a fetch/rendering issue. Apple's App Store still has one, so all
  6 apps (Techcombank Mobile, VCB Digibank, BIDV SmartBanking, MBBank,
  ACB ONE, VPBank NEO) are sourced from there instead. New
  `SITE_CONFIGS["apps.apple.com"]` entry, `#mostRecentVersion`
  selector.
- Gotcha: the section's actual heading uses a curly right-single-quote
  ("What's New" with `’`), not a straight apostrophe — a first
  plain-text keyword search missed it and looked like a dead end that
  wasn't real.
- Content quality varies by bank (confirmed live): BIDV and ACB give
  specific per-version feature notes; Techcombank/VCB/MB mostly repeat
  generic boilerplate. Both included as-is — either way it's the
  bank's own genuine self-disclosed update cadence.

## Unreleased — GSO/NSO stats source (domain migration found)

- The plan's listed domain (`gso.gov.vn`) is genuinely dead — confirmed
  live: DNS/ping succeed, but a raw TCP connect on port 443 times out
  (not a WAF block, not an environment issue — `sbv.gov.vn` connects
  fine from the same check). GSO was renamed NSO (National Statistics
  Office); the real site is `nso.gov.vn`.
- Added `nso_data_and_statistics_official`, a general releases-archive
  feed (same "general feed + LLM filters" pattern as
  `chinhphu_legal_documents_official`). New
  `SITE_CONFIGS["nso.gov.vn"]` entry, `.archive-container` selector.
  Real, current (Aug 2026) content confirmed live. NSO's dedicated GDP
  page uses a PxWeb data-table interface — out of scope for this pass.

## Unreleased — Tier 2 sources: securities-firm research + consumer research (partial)

- Added `ssi_banking_sector_report` (SSI, a hand-verified PDF found via
  web search after SSI's own listing page proved to never expose real
  report links; its host 403s crawl4ai's PDF downloader specifically —
  confirmed a crawl4ai-side quirk via a clean `curl` 200 on the same
  URL — fetched via direct `urllib` + crawl4ai's own
  `NaivePDFProcessorStrategy` instead), `vcbs_banking_sector_report`
  (see below), `bsc_mbb_report` (see below),
  `decisionlab_bank_satisfaction_rankings`, and
  `qandme_online_banking_usage` (both solved directly, no gating). All
  five use the new `"tier": "tier_2"` config.
- `vcbs_banking_sector_report`: reopened after being wrongly judged
  blocked-by-design. A genuinely *trusted* Playwright click (not a
  JS-level `.click()`, which this site's handler ignores as untrusted)
  did trigger real navigation — but to an intermediate discovery page
  that's genuinely bot-gated (confirmed live: loads an invisible
  reCAPTCHA, stays blank even after a 15s wait). The underlying PDF
  file itself carries no gate at all, confirmed by the user's own
  manual click surfacing the working direct file URL. Net effect: this
  report's URL can be refetched automatically now, but discovering
  future reports this way still needs a human click.
- `bsc_mbb_report`: the plan's own listed URL was simply dead (not
  linked from anywhere on the current site) — the real report listing
  lives at a different URL, found via BSC's own nav. A real, current
  BUY-rated MBB analyst report (target price, ROAE outlook,
  2026-2027F forecasts) was found there.
- VNDirect skipped: same dedicated `User-agent: ClaudeBot` robots.txt
  block found on thuvienphapluat.vn in the previous entry. Cimigo
  skipped as stale after a full pagination check (best available was a
  ~21-month-old article) rather than blocked.
- `agent/content_gate.py`: fixed a second URL-scheme false positive in
  `_corrupted_token_ratio` — inline `data:image/svg+xml;...` URIs
  weren't stripped before the ratio check, same failure mode as the
  earlier CDN-image-URL bug. Broadened `URL_RE` to also match `data:`
  URIs; new regression test added.
- Bugs found by `/code-review` and fixed in `_fetch_ssi_report_text`:
  missing per-domain throttle before the `urllib` request, a leaked
  temp PDF file on every fetch, and wasted image-decoding work in
  `NaivePDFProcessorStrategy` for a field that's never read.

## Unreleased — Tier 2 [Fact]/[Opinion] schema field

- Added `MarketSignal.fact_or_opinion: Literal["fact", "opinion"]`
  (required) and an optional `"tier"` key on source configs
  (`"tier_1"`/`"tier_2"`, defaulting to `"tier_1"`), implementing rule
  R-F07 ahead of either Tier 2 source row (securities-firm research,
  consumer research) actually being built. R-F04 (forecast tagging)
  was already fully covered by the existing `actual_proxy_forecast`/
  `forecast_org` fields.
- `agent/graph.py`'s `_finalize_payload` forces every signal's
  `fact_or_opinion` to `"fact"` when a request's `tier` is `"tier_1"` —
  the same "known metadata beats the model's guess" principle already
  used there for `source_url`. Only exactly `"tier_1"` triggers the
  override; unset (`None`, e.g. `agent/topics.py`'s search-based
  queries) and `"tier_2"` both leave the model's own per-signal
  judgment untouched, since a Tier 2 document can genuinely mix fact
  and opinion in one place.
- Zero changes needed to any of the 32 existing sources — `tier`
  defaults to `"tier_1"` via `.get("tier", "tier_1")`, matching
  `chunked`'s own set-only-when-true convention.
- New `tests/test_tier_fact_opinion.py`, fully offline (`_finalize_
  payload` is pure data-shaping code, no network/LLM needed).
- Bug found by `/code-review` and fixed: `agent/store.py`'s
  `CSV_HEADERS`/`append_topic_csv()` were never updated, so
  `fact_or_opinion` was silently dropped from the flattened
  `data/signals.csv` (still present in `signals.jsonl`). Fixed, with
  a new offline regression test round-tripping a synthetic result
  through `append_topic_csv()`.
- Designed via `/grill-with-docs` + `/to-spec` —
  `.scratch/tier2-fact-opinion-field/spec.md`.

## Unreleased — Layer 4 legal-document watchlist added via LuatVietnam (9 documents)

- Added 9 new sources for the 9 named documents across `source_plan_mvp0.md`
  §6.1-6.4's watchlist (real estate credit rules, the fintech sandbox
  decree, the digital-transformation resolution, 2026 PIT deduction/law
  changes, the green taxonomy decision, environmental-risk-management
  circular). Fetch-only development, zero LLM calls spent verifying any
  of it.
- `thuvienphapluat.vn` (one of the plan's two named aggregator sites)
  skipped entirely: its `robots.txt` has a dedicated
  `User-agent: ClaudeBot` / `Disallow: /` block, separate from its
  general `Content-Signal` declaration. Used `luatvietnam.vn` (the
  plan's own listed alternative) exclusively instead — no bot-specific
  rule there.
- New `SITE_CONFIGS["luatvietnam.vn"]` / `["english.luatvietnam.vn"]`
  entries, `.content-left` selector, scoping past a large sidebar
  taxonomy nav. Confirmed live the pages' own "Bạn chưa Đăng nhập thành
  viên" notice gates only a "watch this document" feature, not the
  document text itself — full legal text is present in the static HTML,
  no login or JS needed.
- One stale-reference correction: the plan names "Circular 52/2018" as
  the credit-institution-rating regulation behind SBV's credit-room
  mechanism; confirmed live it was replaced by Circular 21/2025/TT-NHNN
  (effective 2025-11-01) before this was even added. Sourced the
  currently-effective circular instead of the plan's outdated number.
- All 9 use the new `role: "aggregator"` value (previously documented,
  never used) since luatvietnam.vn isn't the issuing authority; each
  prompt's `source_code` names the actual issuing body instead
  (SBV/CHINHPHU/TW/UBTVQH/QH/TTG), matching the MBBank attribution
  convention. 7 of 9 marked `chunked: true` (over the 12K-char
  single-call threshold once scoped).
- Annual reports/AGM documents (Layer 3, 5 banks) parked mid-discovery
  in favor of this smaller, more self-contained slice — see
  `DEVELOPMENT_PLAN.md` v0.11 for exact state to resume from.

## Unreleased — VCB fee schedule fully resolved via real click simulation

- Followed up on the correctness fix below by actually doing what should
  have been done from the start: real Playwright click simulation
  (ACB-style network capture), not guessing at filenames or relying on a
  user-provided URL. Clicking each of VCB's 3 category tabs surfaced its
  actual document-search API (Sitecore's
  `sxa/FileDocumentApi/FileDocumentResults`) and each category's own
  real PDFs.
- Domestic transfer's own fee PDF (`BP-dich-vu-chuyen-tien-trong-
  nuoc.pdf`, found via the click) turned out to have identical figures
  to the URL a user had separately found on the live page — the same
  document's Vietnamese/English twin, not a second document. Only one
  is kept.
- Remittance was also click-verified directly: its accordion panel has
  only a "Biểu mẫu" (forms) heading (a withdrawal slip, a MoneyGram
  receive form) and genuinely no "Biểu phí" (fee schedule) section —
  consistent with VCB not charging a fee to *receive* a remittance.
  This isn't a source we failed to find; it doesn't exist.
- Net result: the existing 3-PDF list (international ×2, domestic ×1)
  is confirmed complete, not partial. `VCB_FEE_PDF_URLS` and the source
  comment updated to record how this was actually verified.

## Unreleased — VCB fee schedule correctness fix: dynamic scraper had a real data-integrity bug

- Fixed `vcb_fee_schedule` (added in the previous entry below) after the
  user's own manual check of the live page caught something the
  automated scraper missed. Investigating the discrepancy found a real
  correctness bug, not just flakiness: all 3 of VCB's transfer-type
  categories (international transfer, domestic transfer, remittance)
  render with the *same* "Biểu phí" (fee schedule) content in the
  initial HTML — international transfer's 2 PDFs appear duplicated under
  every category heading, not each category's own real documents. Same
  failure shape as BIDV's Layer 1 bug #6 (the same document set repeated
  under every tab), except here it would have meant silently mislabeling
  international-transfer fees as domestic-transfer or remittance fees —
  a real correctness risk, not cosmetic noise.
- A retry-until-fully-rendered strategy (raising the bar from "found any
  PDFs" to "found more than one category's worth") did not fix this —
  it just retried into the same duplicated-content state more
  confidently, since the duplication happens inside a single otherwise-
  complete render, not as a symptom of partial rendering.
- Replaced the dynamic accordion scraper (`_vcb_fee_pdf_urls()`) with a
  hand-verified, explicit list of 3 PDF URLs in `agent/crawler.py`
  (`VCB_FEE_PDF_URLS`): international transfer's 2 real PDFs (found via
  the accordion before the duplication bug was understood) and domestic
  transfer's 1 real PDF (given directly by the user from the live page —
  several plausible filename guesses to find it independently all
  404'd). The third category (remittance) was not found and is left out
  rather than guessed at further; each category's genuinely distinct
  content likely only loads after a real user click, which would need
  ACB-style network capture to fetch properly.
- Fetch-only re-verified via `crawl_parts()`: all 3 pieces now correct
  and distinct, zero LLM cost.

## Unreleased — VCB fee schedule solved on a second pass (reopened from "needs OCR") — Layer 2 news/fee pass now complete, 10/10

- Added `vcb_fee_schedule`, reopening a source previously judged "needs
  OCR, not a crawling problem" — that conclusion turned out to be wrong.
  It came from one fetch that happened to return a near-empty page shell
  (an unrelated banner-image reference was misread as "the fee table is
  an image").
- The real cause: this page's fee accordion is genuinely server-side
  rendered, not client-JS populated — confirmed live that waiting on a
  JS predicate for an anchor to appear inside it timed out on every
  attempt, since no client-side code ever adds one. VCB's own server/CDN
  non-deterministically returns either the fully-rendered version or a
  near-empty shell — the same class of caching race already documented
  for `bidv.com.vn`. A client-side wait can't fix a server-side race;
  retrying the fetch can, and did (succeeded on attempt 1 of a 5-attempt
  budget when re-tested).
- Once rendered, the accordion has 3 transfer-type categories (outbound
  international transfer, domestic transfer, inbound remittance), each
  with a "Biểu mẫu" (forms) section and a separate "Biểu phí" (fee
  schedule) section — only the latter is used. Confirmed live: a
  genuine, current, itemized fee schedule (percentages and USD/VND
  min/max amounts, split by counter vs. internet-banking channel).
- `agent/crawler.py`: `_fetch_vcb_fee_parts()`, routed through
  `crawl_parts()` (not `crawl()`) since VCB has multiple distinct fee
  PDFs across its transfer categories, each kept as its own piece with
  its own provenance URL.
- Fetch-only verified via `crawl_parts()`, zero LLM cost.
- **This completes the full Layer 2 news/fee pass: 10 of 10 sources
  solved** (BIDV news+fee, ACB promotions+fee, VPBank news+fee, VCB
  promotions+fee, MBBank news+fee). `SOURCES` is now at 23 total.

## Unreleased — MBBank Layer 2 sources solved after all (reopened from blocked-by-design)

- Added `mbbank_fee_schedule` and `mbbank_news`, reopening what was
  previously documented as blocked-by-design. The bare `mbbank.com.vn`
  domain genuinely is Akamai-walled site-wide (re-confirmed live: every
  path returns the identical "0 chars visible" block) — but the **`www.`
  subdomain is not behind the same wall** (confirmed live). This is a
  different, legitimately-reachable host the bank itself owns and
  publishes on, not evasion of the wall on the bare domain — the same
  distinction that made Layer 1's Vietstock-mirror fix for MBBank
  acceptable under the spec's own rules.
- Both pages (`/Fee`, `/news/tin-tuc`) are Angular-templated and needed a
  JS-predicate wait condition rather than the plain CSS wait every other
  `SITE_CONFIGS` entry uses — confirmed live that a plain CSS wait raced
  unreliably here (one run returned 1 of 7 real links, another 4 of 7).
- The news page needed a further fix: even a page-wide JS-predicate wait
  (matching if a link exists *anywhere*) raced with the target
  container's own content still settling (confirmed live: container came
  back with 0 chars despite the page-wide condition passing). Scoping the
  wait condition to the container itself resolved it — verified reliable
  across 3 separate runs before finalizing.
- `agent/crawler.py`: `_fetch_mbbank_fee_text()` and
  `_fetch_mbbank_news_text()`, bespoke fetch functions (matching this
  project's existing pattern for tricky sites) since the generic
  `SITE_CONFIGS`/`_fetch_html` path only supports plain CSS waits.
- Confirmed live: a genuine, current, itemized fee table (account/
  deposit/treasury fees, real VND amounts) and real, dated news items (a
  minigame results announcement, a CSR sustainability partnership,
  procurement notices). Fetch-only verified end to end, zero LLM cost.
- Net for the Layer 2 news/fee pass: **9 of 10 sources now solved** — only
  VCB's fee page remains, still blocked on OCR (unrelated to this fix).

## Unreleased — ACB fee schedule solved on a second pass

- Added `acb_fee_schedule`. The real fee page turned out not to be the
  earlier guessed `/en/fees` (a generic empty-search shell that returns
  the same content regardless of path) but
  `/en/forms-and-fee-schedules-for-individual-customers`, found via ACB's
  own homepage navigation. Needed its own separate network capture — the
  `map/posts?type=uu-dai` pattern that solved promotions doesn't apply
  here.
- The real call found: the standard `posts` endpoint filtered by
  `search[type:like]=bieu-mau-bieu-phi` (dropping `category_id` entirely
  returns all 60 fee/form documents across every category in one call).
  Category 631 ("Summary of fee schedule") holds the 11 real consolidated
  fee documents, one per product line.
- Same two-locale quirk as ACB's promotions: the English-locale detail
  endpoint has `featured_image: null`; the real PDF only appears via the
  Vietnamese-locale detail endpoint.
- `_fetch_acb_fee_schedule_text()` picks whichever product line was most
  recently updated rather than hardcoding one slug, so the source stays
  current as ACB updates different schedules over time — confirmed live
  on two different picks across this session (credit-card fees, then
  account-services fees after ACB's own data changed mid-session), both
  genuine and dated.
- Fetch-only verified via `crawl_chunked()`, zero LLM cost.

## Unreleased — Layer 2 news/fee pass concluded: MBBank blocked by design, ACB fee still open

- Re-confirmed live that MBBank's Layer 2 pages are blocked the same way
  as Layer 1: every path on `mbbank.com.vn` returns the identical "0
  chars visible" WAF block — comprehensive and site-wide, not a
  JS-rendering gap the network-capture technique (which solved ACB/
  VPBank) could ever help with, since the page never loads enough to
  fire any JS. Per the source plan's explicit rule for Akamai-walled
  sites, not attempting evasion — same treatment as Vietcombank's own
  walled investor-relations portal. Vietstock's static-CDN mirror (the
  Layer 1 workaround for MBBank's financial statement) doesn't help
  here — it only has financial-statement PDFs, not news/promo/fee
  content.
- Checked ACB's fee/pricing page: the `map/*` API technique that solved
  its promotions page doesn't transfer (guessed fee-related `type`
  values all returned HTTP 422; network capture showed no fee-specific
  API call at all). Likely no single consolidated fee-schedule listing
  exists on this site — pricing appears scattered per-product page.
  Left genuinely open, not blocked by a wall — just not found within
  this pass's effort.
- Net for this Layer 2 news/fee pass: 6 of 10 candidate sources solved
  (BIDV news+fee, ACB promotions, VPBank news+fee, VCB promotions); 1
  needs OCR (VCB fee), 1 is a genuine wall (MBBank, both), 1 remains open
  (ACB fee).

## Unreleased — VCB promotions via sitemap discovery (a genuinely different fix than ACB/VPBank)

- Added `vcb_promotions` (`vietcombank.com.vn/KHCN/.../KHCN---Danh-sach-uu-dai`).
  A different problem than ACB/VPBank's AJAX-gap: VCB's homepage showed
  zero fetch/XHR calls under the same JS-injection capture technique —
  mostly server-rendered, not a client-side SPA, so the listing's real
  links are likely populated via a WebCenter/Liferay-style portlet
  postback that technique can't see.
- Solved differently: individual promo article pages ARE real and fully
  extractable (confirmed live: detailed, dated terms with real VND
  figures). The sitemap — using its real `<lastmod>` dates — picks the 3
  most recent, since the listing page itself never surfaces them.
  `crawl4ai` itself fails to parse this specific sitemap's XML encoding
  declaration; raw `urllib` is used for just that one bootstrap fetch,
  every actual promo page still goes through `crawl4ai` normally.
- A real bug caught and fixed along the way: the sitemap lists these URLs
  as plain `http://`, and fetching over `http` (not `https`) specifically
  trips a genuine `net::ERR_HTTP2_PROTOCOL_ERROR` against this domain —
  normalized to `https://` before fetching.
- VCB's separate fee-schedule page is explicitly NOT solved by this or
  any other crawling technique — its fee table is an embedded image, not
  JS-gapped content. Documented as needing OCR, same category as BIDV's/
  VCB's own Layer 1 scan-only filings.

## Unreleased — VPBank Layer 2 sources via the same network-capture technique

- Added `vpbank_news` (`vpbank.com.vn/tin-tuc`) and `vpbank_fee_documents`
  (`vpbank.com.vn/tai-lieu-bieu-mau`). Same AJAX-listing gap as ACB's
  promotions page, solved the same way: real Playwright network capture
  found both pages call VPBank's own `uiux-api`, which returns real JSON
  directly — simpler than ACB's case, no separate per-item detail fetch
  needed.
- The fee-documents API needed a real correction after the first capture:
  the captured call had drilled into "Biểu mẫu" (Forms) > individual-
  customer — the page's own default tab, not "Biểu phí" (Fee Schedule),
  a genuinely separate sibling category found via VPBank's own
  `category/children` endpoint. Using the top-level fee-schedule path
  (not one customer segment) returns real, dated fee documents across
  segments (individual, business households, SME, large corporate) in one
  call.
- That API only returns document titles/dates/segment, not the actual fee
  figures inside each linked PDF — not fetched this pass (a light-effort
  call for this round), prompt scoped to explicitly not fabricate amounts.
- `agent/crawler.py`: `_fetch_api_json_text()`, a small shared helper
  (unlike ACB's bespoke multi-step function) since both VPBank endpoints
  just need a single API call with no per-item detail fetch.

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
