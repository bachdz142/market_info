# Predefined URL-based sources for official/structured data — an alternative
# to search, for pages where the exact fact reliably lives at a stable URL.
# Each entry: {"id", "kind", "role", "url", "prompt"}. Fetched via
# agent/crawler.py's crawl() — crawl4ai's lightweight HTTP strategy by
# default, falling back to its Playwright-based strategy for JS-heavy sites
# (see SITE_CONFIGS there).
#
# Only add URLs confirmed to work via a live crawl() test.
#
# "role" (citable/aggregator, per source_plan_mvp0.md §2) is deliberately
# metadata-only right now — no code reads it yet. Enforcement for Layer 1
# is by construction (this list is hand-curated and never includes a
# banned domain), not a runtime check; a real consumer (e.g. citation
# formatting, a compliance-checking module) is future work, not an
# oversight — see .scratch/layer-1-quant-benchmarks/spec.md.
#
# "tier" (tier_1/tier_2, per source_plan_mvp0.md's Tier 1/Tier 2 distinction
# within Citable) IS read at runtime — agent/graph.py's _finalize_payload
# forces every signal's fact_or_opinion to "fact" when tier is "tier_1".
# Only ever set explicitly to "tier_2" on a source whose content is
# genuinely analyst opinion/interpretation rather than raw disclosure
# (matching "chunked"'s own set-only-when-true convention below); every
# other source defaults to "tier_1" via .get("tier", "tier_1") and needs no
# explicit key — see .scratch/tier2-fact-opinion-field/spec.md.
#
# Note: ids below are suffixed "_official" because agent/topics.py already
# has search-based quant topics covering the same facts (sbv_policy_rate,
# usdvnd_rate, vietnam_cpi) — both run in the same /trigger call for now,
# giving two independent looks at the same numbers. Worth revisiting later
# whether to retire the search-based versions once these are proven out.

SOURCES = [
    # {
    #     "id": "sbv_policy_rate_official",
    #     "kind": "quant",
    #     "url": "https://sbv.gov.vn/en/l%C3%A3i-su%E1%BA%A5t1",
    #     "prompt": (
    #         "Extract the current SBV rediscount rate (lãi suất tái chiết khấu) "
    #         "and refinancing rate (lãi suất tái cấp vốn) from the rate table on "
    #         "this page, including the values and the date they apply from. Also "
    #         "extract the current interbank market rates table if present, with "
    #         "its as-of date."
    #     ),
    # },
    # {
    #     "id": "usdvnd_rate_official",
    #     "kind": "quant",
    #     "url": "https://sbv.gov.vn/t%E1%BB%B7-gi%C3%A1",
    #     "prompt": (
    #         "Extract the current USD/VND central exchange rate (tỷ giá trung "
    #         "tâm) published by the State Bank of Vietnam on this page, "
    #         "including the date it applies to."
    #     ),
    # },
    # Revived for Layer 4 (source_plan_mvp0.md §6.3) — this domain (formerly
    # nso.gov.vn, GSO's predecessor site) was assumed stale by a prior note
    # in DEVELOPMENT_PLAN.md (GSO reorganized under the Ministry of Finance),
    # but confirmed live during Layer 3/4 recon that gso.gov.vn itself is
    # unreachable (ECONNREFUSED, no response at all) while this URL is live
    # right now with real, current CPI releases — the domain assumed
    # superseded turned out to be the one still actually serving.
    {
        "id": "vietnam_cpi_official",
        "kind": "quant",
        "role": "citable",
        "url": "https://www.nso.gov.vn/en/cpi/",
        "prompt": (
            "Extract the most recent Vietnam Consumer Price Index (CPI) report "
            "from this page: the month-on-month change, the change compared to "
            "December of the previous year, and the year-on-year change, plus "
            "the reference period and date of issue. source_code for these "
            "signals is \"GSO\"."
        ),
    },
    {
        "id": "sbv_press_releases_official",
        "kind": "qualitative",
        "role": "citable",
        "url": "https://sbv.gov.vn/en/press-release",
        # multi_pdf: this source's SITE_CONFIGS entry fetches 3 PDFs
        # (pdf_link_limit=3), too much for one combined structure call to
        # stay under Groq's per-request token ceiling. Routes through
        # build_multi_pdf_graph() instead: one structure call per PDF, then
        # a synthesis call to combine them.
        "multi_pdf": True,
        "prompt": (
            "Extract concrete market signals from the full press release "
            "content below — specific interest rates, exchange rates, "
            "transaction volumes, and how they changed versus the previous "
            "period. The list of titles and dates is only for context on "
            "which report this is; the actual facts must come from the "
            "full report text, not just its title."
        ),
    },
    # --- Layer 1 (quant bank benchmarks, source_plan_mvp0.md) ---
    # Techcombank, BIDV, ACB, and MBBank are confirmed working. Still open:
    #   - Vietcombank (portal.vietcombank.com.vn): real Akamai anti-bot
    #     wall on the bank's own site (confirmed live) — same category as
    #     dttktt.sbv.gov.vn. Per source_plan_mvp0.md §8 ("switch entirely
    #     to the manual ingestion path — no workarounds"), this is not an
    #     evasion problem to solve; route to data/manual, don't try
    #     stealth/proxy techniques against it. The Vietstock static-CDN
    #     fallback that unblocked MBBank (see below) doesn't help here
    #     either: confirmed live that VCB's mirrored copy there is a
    #     55-page scan with zero extractable text — a different, also
    #     closed dead end, not the Akamai wall.
    #   - Vietstock's own JS-rendered document table
    #     (finance.vietstock.vn/{ticker}/tai-tai-lieu.htm): didn't render
    #     even after 60s of waiting, suggesting it may be gated behind
    #     login. Its static CDN (static2.vietstock.vn) is a separate,
    #     unrelated mechanism that DOES work — see MBBank below.
    # Two fixes worth noting for how the blocked ones above got solved:
    #   - ACB (see agent/crawler.py's _fetch_acb_statement_text): its
    #     "Download" controls have no href/onclick at all — turned out not
    #     to be an anti-bot problem, just a React app whose PDF links only
    #     exist after a JS click fires an API call. Network-capturing a
    #     simulated click found that call is a plain, unauthenticated JSON
    #     API (acb.com.vn/api/en/front/v1/posts) — calling it directly is
    #     simpler and more stable than click-simulation.
    #   - MBBank (see agent/crawler.py's VIETSTOCK_FALLBACK_TICKERS): its
    #     own site is Akamai-blocked, but its filed statement is also
    #     mirrored on Vietstock's static CDN (a predictable, direct PDF
    #     URL, confirmed outside whatever blocks the JS-rendered document
    #     table) — a genuine Aggregator source per source_plan_mvp0.md §2,
    #     not a workaround for the bank's own block.
    # All open follow-up work, not silently dropped.
    {
        "id": "techcombank_vas_statements",
        "kind": "quant",
        "role": "citable",
        "url": "https://techcombank.com/en/investors/financial-information/financial-statements-vas",
        # A full VAS financial statement PDF (~180K chars) blows Groq's
        # free-tier 8,000-tokens-per-request ceiling in one shot (confirmed
        # live: 413 rate_limit_exceeded). "chunked" routes this through
        # build_multi_pdf_graph()'s per-chunk structure + merge flow
        # instead of a single structure call.
        "chunked": True,
        "prompt": (
            "Extract Techcombank's quarterly quantitative benchmarks from "
            "the consolidated VAS financial statement notes below — "
            "cumulative CASA growth (customer demand/non-term deposit "
            "balance), CASA ratio, term deposit and certificate-of-deposit "
            "growth, and credit growth (customer loan balance), including "
            "the reference period each figure covers (e.g. the period "
            "ending date stated in the notes) and whether growth is vs. "
            "start-of-year or vs. prior period. These are consolidated "
            "(not standalone) figures. source_code for these signals is "
            "\"TCB\"."
        ),
    },
    {
        "id": "bidv_financial_statements",
        "kind": "quant",
        "role": "citable",
        "url": "https://bidv.com.vn/vn/quan-he-nha-dau-tu/bao-cao-va-tai-lieu/",
        "prompt": (
            "Extract BIDV's quarterly quantitative benchmarks from the "
            "consolidated financial statement content below — customer "
            "deposit balances (demand/CASA vs. term, if broken out), "
            "credit growth (customer loan balance), and any disclosed "
            "growth rates, including the reference period each figure "
            "covers. Per source_plan_mvp0.md: BIDV has NO standardized "
            "quarterly retail/CASA breakout — if only a whole-bank figure "
            "is available (not retail-only), still report it but set "
            "actual_proxy_forecast to \"proxy\" rather than \"actual\" for "
            "that figure. These are consolidated (not standalone) "
            "figures. source_code for these signals is \"BID\"."
        ),
    },
    {
        "id": "acb_financial_statements",
        "kind": "quant",
        "role": "citable",
        "url": "https://acb.com.vn/en/investors/financial-statements",
        # Full consolidated interim statement PDF (~194K chars) — same
        # Groq free-tier ceiling as Techcombank's. See agent/crawler.py's
        # _fetch_acb_statement_text: the actual fetch bypasses this page
        # entirely (goes straight to ACB's own documents API), but this
        # human-readable IR page URL is kept for citation/reference.
        "chunked": True,
        "prompt": (
            "Extract ACB's quarterly quantitative benchmarks from the "
            "consolidated interim financial statement notes below — "
            "customer deposit balances (demand/CASA vs. term, if broken "
            "out), CASA ratio, credit growth (customer loan balance), NIM, "
            "and any disclosed growth rates, including the reference "
            "period each figure covers. These are consolidated (not "
            "standalone) figures. source_code for these signals is "
            "\"ACB\"."
        ),
    },
    {
        "id": "mbb_financial_statements",
        "kind": "quant",
        "role": "citable",
        "url": "https://mbbank.com.vn/Investor/thong-bao-nha-dau-tu",
        # MBBank's own site is Akamai-blocked (see the Layer 1 comment
        # above). See agent/crawler.py's VIETSTOCK_FALLBACK_TICKERS/
        # _fetch_vietstock_statement_text: the actual fetch goes through
        # Vietstock's static-CDN mirror of MBB's own filed statement
        # instead — a genuine Aggregator source per source_plan_mvp0.md
        # §2, not a bot-evasion technique, and metadata still attributes
        # the figures to MBBank's own disclosure, not Vietstock. Confirmed
        # live: this specific mirrored copy has a real (if imperfectly
        # OCR'd/encoded) text layer — VCB's equivalent copy does not (a
        # 55-page scan with zero extractable text) and was NOT added for
        # that reason.
        "chunked": True,
        "prompt": (
            "Extract MB Bank's quarterly quantitative benchmarks from the "
            "consolidated financial statement content below — customer "
            "deposit balances (demand/CASA vs. term, if broken out), CASA "
            "ratio, credit growth (customer loan balance), and any "
            "disclosed growth rates, including the reference period each "
            "figure covers. The Vietnamese text may have minor encoding "
            "artifacts (garbled diacritics) from PDF extraction — the "
            "numeric figures themselves are reliable; use surrounding "
            "context to interpret garbled labels rather than skipping "
            "them. These are consolidated (not standalone) figures. "
            "source_code for these signals is \"MBB\"."
        ),
    },
    {
        "id": "sbv_portal_statistics",
        "kind": "quant",
        "role": "citable",
        "url": "https://sbv.gov.vn/en/statistics",
        # Confirmed live: this page's generic-markdown text alone (42K+
        # chars) exceeds Groq's free-tier 8,000-tokens-per-request ceiling
        # in a single structure call (413 rate_limit_exceeded).
        "chunked": True,
        "prompt": (
            "Extract concrete system-wide monetary/banking statistics from "
            "the content below — interest rates, credit institution system "
            "figures, balance of payments, exchange rates, or credit growth "
            "— including the reference period and date of issue for each "
            "figure. source_code for these signals is \"SBV\"."
        ),
    },
    {
        "id": "iav_bancassurance",
        "kind": "quant",
        "role": "citable",
        "url": "https://iav.vn/News/Listtt/202?page=1",
        # Confirmed live: this page's fetched text exceeds Groq's free-tier
        # 8,000-tokens-per-request ceiling in a single structure call (413
        # rate_limit_exceeded).
        "chunked": True,
        # Per source_plan_mvp0.md §3.4: no source discloses per-bank APE —
        # that figure is out of agent scope entirely (manual/internal only,
        # via data/manual). iav.vn only ever publishes the TOTAL market
        # figure, used as a benchmark denominator, not a per-bank number —
        # the prompt is deliberately scoped to match, so the LLM doesn't
        # fabricate a per-bank breakdown that doesn't exist on this page.
        "prompt": (
            "Extract the total Vietnam life insurance market figures from "
            "the content below — total premium revenue and growth rates "
            "for the market as a whole — including the reference period "
            "each figure covers and the date the report was published. Do "
            "NOT report per-bank or per-insurer figures even if the text "
            "mentions specific companies; only total-market numbers are in "
            "scope here. source_code for these signals is \"IAV\"."
        ),
    },
    # --- Layer 3 journals + Layer 4 macro/gov (source_plan_mvp0.md §5, §6) ---
    # First slice of the still-open Layer 2-4 work — see
    # .scratch/layer-3-4-easy-wins/spec.md for the full spec and CONTEXT.md
    # for the Layer/Role/Tier/spot-checked-vs-live-verified vocabulary this
    # slice was designed against. Chosen first because every domain here was
    # either already reachability spot-checked (DEVELOPMENT_PLAN.md v0.6) or,
    # in tapchitaichinh.vn's case, a follow-up check contradicted that
    # spot-check (got a real 403) but crawl4ai itself was confirmed live to
    # get through fine — a different fetcher/UA than whatever hit the 403.
    {
        "id": "sbv_legal_directives_official",
        "kind": "qualitative",
        "role": "citable",
        # Reuses SITE_CONFIGS["sbv.gov.vn"] unchanged (same domain as
        # sbv_press_releases_official) — confirmed live that "ul.doc-list"
        # correctly matches this page's real document list (unlike
        # /en/legal-documents, which was tried first and found to be an
        # empty nav shell — not used). Same WAF flakiness as the
        # press-release source: one live check got real content (a document
        # list plus one successful PDF fetch, "Quyết định 1382" on office
        # space standards) immediately followed by a genuine WAF rejection
        # page on the next call — "multi_pdf" is set for the same reason the
        # press-release source needs it (pdf_link_limit=3 on this domain can
        # return several substantial PDFs).
        "url": "https://sbv.gov.vn/en/văn-bản-quản-lý-hành-chính",
        "multi_pdf": True,
        "prompt": (
            "Extract concrete regulatory content from SBV's administrative "
            "documents and directives listed below — circulars, decisions, "
            "and directives relevant to banking operations, credit policy, "
            "or digital transformation — including each document's "
            "reference number, date, and what it covers. Also extract any "
            "green-credit figures (outstanding balance, or references to "
            "green-taxonomy or environmental-risk regulations) if present, "
            "since SBV's own official statements are a valid green-credit "
            "source per source_plan_mvp0.md §6.4. Do not fabricate specific "
            "named documents (e.g. a particular circular or official "
            "letter) if they aren't actually present in the content below — "
            "only report what's genuinely there. source_code for these "
            "signals is \"SBV\"."
        ),
    },
    {
        "id": "nso_data_and_statistics_official",
        "kind": "quant",
        "role": "citable",
        # source_plan_mvp0.md §6.3 names gso.gov.vn — that domain is now
        # genuinely dead (confirmed live: DNS/ping succeed but a raw TCP
        # connect on port 443 times out, unlike sbv.gov.vn from the same
        # check — a dead host, not a block). GSO was renamed NSO (National
        # Statistics Office); nso.gov.vn is the real, live successor.
        # .archive-container (SITE_CONFIGS["nso.gov.vn"]) scopes past a
        # large nav/category-tree menu down to this page's 5 real dated
        # entries. Confirmed live: real, current (Aug 2026) releases —
        # CPI, industrial production index, exports/imports, socio-economic
        # performance. CPI itself is already covered by vietnam_cpi_official
        # elsewhere; this source is for the other named figures (GDP,
        # household income/VHLSS, labor data) whenever this general feed
        # happens to carry them — a general feed of ALL NSO releases, not
        # scoped to one category, so most entries will be off-topic.
        "url": "https://www.nso.gov.vn/en/data-and-statistics/",
        "prompt": (
            "Extract concrete household income/expenditure (VHLSS) or "
            "labor/employment figures from the statistical releases "
            "below — including the reference period each figure covers "
            "and the date of issue. This is a general feed of all NSO "
            "releases (industrial production, trade, prices, agriculture, "
            "etc.), so most entries will be unrelated — skip those and "
            "only report genuinely relevant ones; if none are relevant, "
            "return an empty signals list rather than reporting unrelated "
            "figures. Do not report CPI/inflation figures here even if "
            "present — those are covered by a separate source. Do not "
            "report GDP figures here either — those are covered by a "
            "dedicated source (nso_gdp_key_indicators). source_code for "
            "these signals is \"NSO\"."
        ),
    },
    {
        "id": "nso_gdp_key_indicators",
        "kind": "quant",
        "role": "citable",
        # NSO's GDP data lives behind a genuine PxWeb statistical-database
        # UI (classic ASP.NET WebForms), not a plain HTML page — see
        # NSO_GDP_KEY_INDICATORS_URL's own comment in agent/crawler.py for
        # the full discovery story (a raw JS click resets the selection to
        # 0 cells instead of submitting; real Playwright select_option
        # calls are needed; the resulting table URL's rxid is a
        # server-side session id, not a stable link, so the table text is
        # read from the live session that just submitted the form, not
        # re-fetched afterward). Confirmed live: real, current "Key
        # indicators on national accounts" table — GDP at current prices,
        # per-capita GDP, growth rate, gross capital formation, and more,
        # for the 3 latest available years (2022, 2023, 2024 Prel. as of
        # writing).
        "url": "https://pxweb.nso.gov.vn/pxweb/en/National%20Accounts%20and%20State%20budget/National%20Accounts%20and%20State%20budget/E03.01.px/",
        "prompt": (
            "This is NSO's (Vietnam National Statistics Office) 'Key "
            "indicators on national accounts' table, covering the 3 most "
            "recent available years. Extract each concrete figure as its "
            "own signal — GDP at current prices, per-capita GDP, GDP "
            "growth rate, gross capital formation, final consumption, "
            "exports/imports, gross national income, and the "
            "percent-of-GDP breakdowns — with the exact year each figure "
            "covers as reference_period. Note when a year is marked "
            "'Prel.' (preliminary, not yet finalized) in the summary. "
            "data_basis is \"not_applicable\". actual_proxy_forecast is "
            "\"actual\" for every figure here — these are NSO's own "
            "official statistics, not forecasts. source_code for these "
            "signals is \"NSO\"."
        ),
    },
    {
        "id": "chinhphu_legal_documents_official",
        "kind": "qualitative",
        "role": "citable",
        # vanban.chinhphu.vn's homepage is ~80% nav/weather-widget
        # boilerplate — content_selector scopes to the real document-list
        # container. Confirmed live: real, current (28/08/2026) government
        # document feed, ~9.6K chars once scoped, well under the chunking
        # threshold.
        "url": "https://vanban.chinhphu.vn",
        "prompt": (
            "Extract concrete government decrees, resolutions, and official "
            "documents from the list below that are relevant to fintech, "
            "digital economy, national data policy, banking, or "
            "e-identification (for example, topics like a fintech sandbox "
            "regulation, a national data law, or an e-identification "
            "scheme) — including each document's reference number, date "
            "issued, and a summary of what it covers. This is a general feed "
            "of all government documents, so most entries will be unrelated "
            "(personnel appointments, infrastructure projects, etc.) — skip "
            "those and only report genuinely relevant ones; if none are "
            "relevant, return an empty signals list rather than reporting "
            "unrelated documents. source_code for these signals is "
            "\"CHINHPHU\"."
        ),
    },
    {
        "id": "vnba_banking_news",
        "kind": "qualitative",
        "role": "citable",
        # .main-content scopes past VNBA's nav/sidebar. Confirmed live: real,
        # dated (24/08/2026) content, ~4.6K chars, static fetch works fine
        # (no JS needed).
        "url": "https://vnba.org.vn",
        "prompt": (
            "Extract concrete open-banking, AI-in-banking, or "
            "fintech-policy developments reported by VNBA (Vietnam Banks "
            "Association) from the content below — announcements, industry "
            "positions, or training programs on topics like open banking, "
            "data governance, or fintech-sandbox regulation — including the "
            "date reported. This page also carries general bank news and "
            "internal-association items (personnel, internal training "
            "logistics) — skip those and only report genuine open-banking/"
            "AI/fintech-policy content; if none is present, return an empty "
            "signals list. source_code for these signals is \"VNBA\"."
        ),
    },
    {
        "id": "banking_review_journal",
        "kind": "qualitative",
        "role": "citable",
        # tapchinganhang.gov.vn needs a full browser fetch: its static HTTP
        # response is a genuine 410, but a full render works fine and
        # returns real, current (01/09/2026) content. IMPORTANT: no "www."
        # prefix — that vhost is a distinct, unrelated misconfiguration
        # ("Chưa cài đặt Site Domain", not an anti-bot block), confirmed
        # live. .col-left.f-collumn.row-g25 scopes to the real article
        # list, ~9K chars, under the chunking threshold.
        "url": "https://tapchinganhang.gov.vn",
        "prompt": (
            "Extract concrete monetary-policy analysis, banking-sector "
            "commentary, or credit-risk/CASA-related research findings from "
            "the Banking Review Journal articles below, including each "
            "article's date and its main finding. Also extract any "
            "green-credit figures or references to green-taxonomy/"
            "environmental-risk regulation if present, since this journal "
            "is a valid green-credit source alongside SBV's own statements "
            "per source_plan_mvp0.md §6.4. Report only what the articles "
            "themselves state as fact — do not add your own interpretation "
            "or recommendation. source_code for these signals is \"TCNH\"."
        ),
    },
    {
        "id": "finance_review_journal",
        "kind": "qualitative",
        "role": "citable",
        # A prior spot-check (DEVELOPMENT_PLAN.md v0.6) claimed this domain
        # had zero anti-bot walls; a follow-up check during Layer 3/4 recon
        # got a real 403 — but that check used a different fetcher, and
        # crawl4ai itself was confirmed live to get through fine (both
        # static and JS strategies work). .siteCenter.flex-0 scopes past the
        # weather-widget nav to the real article list, ~10.7K chars, under
        # the chunking threshold.
        "url": "https://tapchitaichinh.vn",
        "prompt": (
            "Extract concrete economic/finance/banking policy analysis from "
            "the Finance Review Journal articles below — budget figures, "
            "banking-sector capital-raising activity, stock-market "
            "developments, or other concrete financial figures/events "
            "reported, including each item's date. Report only what the "
            "articles themselves state as fact, not your own "
            "interpretation. source_code for these signals is \"TCTC\"."
        ),
    },
    # --- Layer 2 (CVP/offerings/segment sales models, source_plan_mvp0.md
    # §4) — bank news/promotions + fee/T&C pages, 5 banks + VPBank. Much
    # tougher domain than Layer 1's IR pages: 4 of 5 candidates hit real
    # dead ends within a light-effort pass — VPBank (both pages: real page
    # shells exist but the actual listing is AJAX-loaded and never resolves,
    # even with crawl4ai's JS strategy), Vietcombank (fee page's actual
    # table is an embedded image, no extractable text; promo page URL never
    # located), ACB (promotions page's listing widget explicitly says "no
    # products" — same AJAX-gap as VPBank), MBBank (its own site is
    # Akamai-blocked site-wide, already known from Layer 1). Only BIDV
    # solved so far, and non-obviously — see below. Still open: an
    # ACB-style network-capture/API-discovery pass on the AJAX-gapped ones,
    # not yet attempted for Layer 2.
    {
        "id": "bidv_card_promotions",
        "kind": "qualitative",
        "role": "citable",
        # bidvinfo.com.vn is BIDV's dedicated news/media portal — a
        # different domain from bidv.com.vn (the transactional site) and
        # from bidvinfo's own homepage/general-news pages, which weren't
        # tried. The "Khuyến mãi thẻ" (Card Promotions) sub-section is
        # cleanly on-topic (confirmed live: real, dated card-partner offers
        # — Trip.com, Agoda discounts — not just nav). No SITE_CONFIGS entry
        # needed: DEFAULT_CONFIG's static fetch already returns real content
        # without a selector, unlike bidv.com.vn's own pages.
        "url": "https://bidvinfo.com.vn/chinh-sach-va-san-pham/khuyen-mai-the",
        "chunked": True,
        "prompt": (
            "Extract concrete card promotions and partner offers from the "
            "content below — the specific card product, the partner/"
            "merchant involved, the discount or benefit amount, and the "
            "promotion's validity period if stated. source_code for these "
            "signals is \"BID\"."
        ),
    },
    {
        "id": "bidv_personal_fee_schedule",
        "kind": "quant",
        "role": "citable",
        # Same domain as the existing Layer 1 bidv_financial_statements
        # source but a different page needing its own selector — this is
        # exactly why agent/crawler.py's SITE_CONFIGS is now URL-keyed for
        # bidv.com.vn (see _resolve_site_config()), not domain-keyed; a
        # domain-wide lookup would have applied Layer 1's selector here by
        # mistake. This listing page itself is a full-site mega-menu
        # (114K+ chars unscoped) with the real fee-schedule PDF list buried
        # inside one small accordion container — SITE_CONFIGS scopes to
        # that container and takes just the newest (first) PDF; the other
        # 11 linked PDFs are mostly older versions of the same card-fee
        # schedule, not distinct categories. Confirmed live: a genuine,
        # extractable fee table segmented by customer tier (regular retail
        # vs. Premier/Private).
        "url": "https://bidv.com.vn/vn/ca-nhan/cong-cu-tien-ich/bieu-phi",
        "chunked": True,
        "prompt": (
            "Extract concrete fee amounts and conditions from BIDV's "
            "personal-customer fee schedule below — service fees (card "
            "issuance, annual fees, transaction fees, etc.), segmented by "
            "customer tier where the table distinguishes them (e.g. regular "
            "retail vs. Premier/Private banking), including which service "
            "each figure applies to and the effective date stated in the "
            "document. data_basis is \"not_applicable\" — these are fee "
            "figures, not financial-statement data. source_code for these "
            "signals is \"BID\"."
        ),
    },
    {
        "id": "acb_promotions",
        "kind": "qualitative",
        "role": "citable",
        # Same class of problem as ACB's Layer 1 financial-statements page:
        # the rendered listing explicitly says "No products" — the real
        # content loads via API calls the static/JS fetch never captures.
        # Solved via real Playwright network capture (2026-09-01), not a
        # guess — see agent/crawler.py's _fetch_acb_promotions_text() for
        # the two-step API (a promo-id list, then each item's real content
        # from the Vietnamese-locale detail endpoint — the English one
        # returns nulls for these Vietnamese-only posts). Confirmed live: 8
        # real, current promotions (0-fee transfers, cashback offers,
        # savings-rate boosts), several with explicit validity date ranges.
        "url": "https://acb.com.vn/en/promotions",
        "prompt": (
            "Extract concrete promotional offers from the content below — "
            "the specific offer or campaign, the product it applies to, the "
            "benefit or discount amount, and the validity dates where "
            "stated. source_code for these signals is \"ACB\"."
        ),
    },
    {
        "id": "vpbank_news",
        "kind": "qualitative",
        "role": "citable",
        # Same AJAX-gap as ACB's promotions page above — solved the same
        # way, via real Playwright network capture (2026-09-01): the page
        # calls VPBank's own "uiux-api", returning real JSON directly (no
        # separate detail-fetch step needed, unlike ACB's two-step case).
        # Confirmed live: real, dated press releases.
        "url": "https://www.vpbank.com.vn/tin-tuc",
        "prompt": (
            "Extract concrete news/press-release items from the content "
            "below — product launches, digital-banking initiatives, "
            "partnerships, or events, including each item's date and a "
            "brief summary. source_code for these signals is \"VPB\"."
        ),
    },
    {
        "id": "vpbank_fee_documents",
        "kind": "qualitative",
        "role": "citable",
        # Same technique as vpbank_news above. Note: "tai-lieu-bieu-mau"
        # (Documents & Forms) has "Biểu phí" (Fee Schedule) as a *separate
        # sibling* category from "Biểu mẫu" (Forms) — the first network
        # capture drilled into Forms > individual-customer (the page's own
        # default tab), the wrong one; confirmed via the category/children
        # endpoint that fee schedules live at a different path. Using the
        # top-level "bieu-phi" path (not one customer segment) returns real,
        # dated fee-schedule documents across segments (individual,
        # business households, SME, large corporate) in one call. This API
        # only returns document titles/dates/segment, not the figures
        # inside each linked PDF — deliberately not also fetching those PDFs
        # for this pass (matching the light-effort call for this round of
        # Layer 2 sources); the prompt is scoped to match what's actually
        # available.
        "url": "https://www.vpbank.com.vn/tai-lieu-bieu-mau",
        "prompt": (
            "The content below lists VPBank's fee-schedule documents by "
            "customer segment — titles, publish dates, and which segment "
            "each applies to — but NOT the fee figures inside those "
            "documents. Extract which segments had a fee schedule "
            "published or updated, the document title, and the effective/"
            "publish date, as a signal that a fee schedule changed — do "
            "NOT invent specific fee amounts, since none are present here. "
            "source_code for these signals is \"VPB\"."
        ),
    },
    {
        "id": "vcb_promotions",
        "kind": "qualitative",
        "role": "citable",
        # Different problem than ACB/VPBank's AJAX-gap: VCB's homepage
        # showed zero fetch/XHR calls under JS-injection capture (confirmed
        # live, 2026-09-01) — mostly server-rendered, not a client-side SPA,
        # so the listing's real links are likely populated via a
        # WebCenter/Liferay-style portlet postback this technique can't see.
        # Individual promo article pages ARE real and fully extractable
        # (confirmed live: detailed, dated terms with real VND figures) —
        # see agent/crawler.py's _fetch_vcb_promotions_text(): uses the
        # sitemap's real <lastmod> dates to pick the 3 most recent, since
        # the listing page itself never surfaces them. VCB's separate fee
        # schedule page is NOT solved this way — its fee table is an
        # embedded image, not JS-gapped content, so no amount of crawling
        # fixes it; needs OCR (same category as BIDV's/VCB's own Layer 1
        # scan-only filings).
        "url": "https://www.vietcombank.com.vn/KHCN/Truy-cap-nhanh/KHCN---Danh-sach-uu-dai",
        "prompt": (
            "Extract concrete promotional offers from the content below — "
            "the specific offer or campaign, the product/card it applies "
            "to, the benefit or discount amount, and the validity dates "
            "where stated. source_code for these signals is \"VCB\"."
        ),
    },
    {
        "id": "acb_fee_schedule",
        "kind": "quant",
        "role": "citable",
        # Same AJAX-gap as ACB's promotions page, needed its own separate
        # network capture (the promo API pattern didn't transfer) — see
        # agent/crawler.py's _fetch_acb_fee_schedule_text(). Category
        # "Summary of fee schedule" holds 11 real fee documents, one per
        # product line (cards, accounts, cash transactions, etc.); this
        # picks whichever was most recently updated rather than hardcoding
        # one, so the source adapts as ACB updates different schedules over
        # time. Same two-locale quirk as promotions: the real PDF only
        # shows up via the Vietnamese-locale detail endpoint. Confirmed
        # live on two different picks across this session: a segmented
        # credit-card fee table (Visa Infinite Privilege through ACB
        # Express tiers) and a real account-services fee list (statements,
        # balance confirmations, savings-book loss, inheritance
        # processing) — both genuine, dated, real VND figures.
        "url": "https://acb.com.vn/en/forms-and-fee-schedules-for-individual-customers",
        "chunked": True,
        "prompt": (
            "Extract concrete fee amounts and conditions from ACB's "
            "fee-schedule document below — service fees, segmented by card "
            "or account tier where the table distinguishes them, including "
            "which service each figure applies to and the effective date "
            "if stated. data_basis is \"not_applicable\" — these are fee "
            "figures, not financial-statement data. source_code for these "
            "signals is \"ACB\"."
        ),
    },
    {
        "id": "mbbank_fee_schedule",
        "kind": "quant",
        "role": "citable",
        # MBBank's own site (mbbank.com.vn, bare domain) is Akamai-blocked
        # comprehensively — every path returns the identical near-empty
        # block, confirmed live and already documented for Layer 1. The
        # "www." subdomain is NOT behind the same wall (confirmed live,
        # 2026-09-01) — not evasion, just a different, legitimately-
        # reachable subdomain the bank itself owns and publishes on. See
        # agent/crawler.py's _fetch_mbbank_fee_text(): a plain CSS wait
        # condition proved unreliable on this page (confirmed live, a real
        # race between "a link exists" and the container's full content
        # settling), so this uses a JS-predicate wait instead. Scoped to
        # the "individual + business-household customer" section (one of
        # ~10 segments on this page — KHCN, SME, CIB, FI, cards, app —
        # picked as the single most broadly-relevant one for this pass).
        # Confirmed live: a genuine, current, itemized fee table
        # (account/deposit/treasury fees with real VND amounts).
        "url": "https://www.mbbank.com.vn/Fee",
        "chunked": True,
        "prompt": (
            "Extract concrete fee amounts and conditions from MBBank's "
            "fee-schedule document below — service fees for accounts, "
            "deposits, and treasury services, including which service each "
            "figure applies to. data_basis is \"not_applicable\" — these "
            "are fee figures, not financial-statement data. source_code "
            "for these signals is \"MBB\"."
        ),
    },
    {
        "id": "mbbank_news",
        "kind": "qualitative",
        "role": "citable",
        # Same www.mbbank.com.vn discovery as mbbank_fee_schedule above —
        # see that source's comment for why this subdomain works when the
        # bare domain doesn't. See agent/crawler.py's
        # _fetch_mbbank_news_text(): needed the same JS-predicate wait
        # fix, additionally scoped to the target container itself (not
        # just "does a matching link exist on the page anywhere") since
        # even the page-wide version raced with this container's own
        # content settling — confirmed live across several runs before
        # landing on a reliable condition. Confirmed live: real, dated
        # news items (a minigame results announcement, a CSR sustainability
        # partnership, procurement notices).
        "url": "https://www.mbbank.com.vn/news/tin-tuc",
        "prompt": (
            "Extract concrete news items from the content below — product/"
            "service announcements, partnerships, campaigns, or corporate "
            "news, including each item's title. source_code for these "
            "signals is \"MBB\"."
        ),
    },
    {
        "id": "vcb_fee_schedule",
        "kind": "quant",
        "role": "citable",
        # Reopened after being wrongly judged "needs OCR" on an earlier
        # pass — that conclusion came from one fetch that happened to
        # return a near-empty shell. The real picture, per
        # agent/crawler.py's VCB_FEE_PDF_URLS comment: dynamically
        # scraping this page's accordion was tried and abandoned after
        # finding a real correctness bug (all 3 of VCB's transfer-type
        # categories render with the SAME "Biểu phí" content in the
        # initial HTML — international transfer's PDFs under every
        # category heading, not each one's own documents; same failure
        # shape as BIDV's Layer 1 bug #6). This uses a hand-verified,
        # explicit URL list instead, built from real Playwright click
        # simulation (ACB-style network capture) rather than guessing:
        # international transfer's 2 real PDFs, and domestic transfer's 1
        # real PDF (a user-provided URL turned out to be the same document
        # in a different language, not a separate one — confirmed by
        # click-verifying domestic's own Vietnamese PDF and comparing
        # figures). Remittance was also click-verified directly: its panel
        # has only a "Biểu mẫu" (forms) heading and genuinely no "Biểu phí"
        # section — VCB doesn't charge a fee to *receive* a remittance, so
        # there's no third document to find, not a gap. Confirmed live:
        # all 3 included documents are genuine, current, itemized fee
        # schedules (percentages and USD/VND min/max amounts, split by
        # counter vs. internet-banking channel).
        "url": "https://www.vietcombank.com.vn/vi-VN/KHCN/Cong-cu-Tien-ich/KHCN---Bieu-mau-va-bieu-phi",
        "multi_pdf": True,
        "prompt": (
            "Extract concrete fee amounts and conditions from VCB's "
            "fee-schedule document below — the specific transfer/service "
            "type, the fee (percentage or fixed amount, with any minimum/"
            "maximum), and which channel it applies to (counter vs. "
            "internet banking) where the document distinguishes them. "
            "data_basis is \"not_applicable\" — these are fee figures, "
            "not financial-statement data. source_code for these signals "
            "is \"VCB\"."
        ),
    },

    # ------------------------------------------------------------------
    # Layer 4 — the 9 named documents in source_plan_mvp0.md §6.1-6.4's
    # watchlist, looked up via LuatVietnam (the "Thư viện Pháp luật /
    # LuatVietnam" aggregator row in §6.1). thuvienphapluat.vn is skipped
    # entirely — its robots.txt has a dedicated "User-agent: ClaudeBot /
    # Disallow: /" block (also GPTBot, CCBot, etc.), separate from its
    # general Content-Signal declaration; luatvietnam.vn has no such
    # per-bot rule. Role is "aggregator" (first real use of that role
    # value — see this file's own top-of-file note that it's
    # metadata-only) since luatvietnam.vn is not the issuing authority;
    # source_code in each prompt instead names the actual issuing body,
    # matching the MBBank Layer 1 convention (attribute the original
    # document, not the aggregator that surfaced it). All 9 confirmed live
    # via SITE_CONFIGS["luatvietnam.vn"]/["english.luatvietnam.vn"]'s
    # .content-left selector — the page's own "Bạn chưa Đăng nhập thành
    # viên" notice gates only a "watch this document" convenience feature,
    # not the document text itself; full text including appendices is
    # present in the static HTML for every one of these 9 pages.
    {
        "id": "sbv_circular_08_2026_tt_nhnn",
        "kind": "qualitative",
        "role": "aggregator",
        # 25.7K chars scoped — over MAX_CHUNK_CHARS (12K), chunked.
        "url": "https://english.luatvietnam.vn/circular-no-08-2026-tt-nhnn-dated-may-15-2026-of-the-state-bank-of-vietnam-amending-and-supplementing-point-a-clause-4-article-20-of-circular-no-22-434688-doc1.html",
        "chunked": True,
        "prompt": (
            "This is Circular 08/2026/TT-NHNN, issued May 15, 2026 by the "
            "State Bank of Vietnam, amending Circular 22/2019/TT-NHNN's "
            "prudential ratios for banks and foreign bank branches. Extract "
            "the concrete amendment(s) it makes — which limit or ratio "
            "changes, the new value, and which lending category it applies "
            "to (e.g. real estate lending safety limits). Note the "
            "reference number, issuing authority, and effective date "
            "exactly as given; do not fabricate provisions not actually "
            "present in the text below. source_code for these signals is "
            "\"SBV\"."
        ),
    },
    {
        "id": "sbv_official_letter_4551_nhnn_cstt",
        "kind": "qualitative",
        "role": "aggregator",
        # 7.9K chars scoped — fits in a single call, not chunked.
        "url": "https://luatvietnam.vn/tai-chinh/cong-van-4551-nhnn-cstt-2026-tang-truong-tin-dung-nam-2026-436547-d6.html",
        "prompt": (
            "This is Official Letter 4551/NHNN-CSTT, issued May 29, 2026 by "
            "the State Bank of Vietnam, on 2026 credit growth. Extract the "
            "concrete rule it sets — that social housing loans and "
            "industrial-park/export-processing-zone loans are excluded from "
            "real estate credit growth calculations, the effective period "
            "(Jan 1 - Dec 31, 2026), and any other concrete condition "
            "stated. Note the reference number, issuing authority, and "
            "effective period exactly as given; do not fabricate anything "
            "not actually present in the text below. source_code for these "
            "signals is \"SBV\"."
        ),
    },
    {
        "id": "sbv_circular_21_2025_tt_nhnn",
        "kind": "qualitative",
        "role": "aggregator",
        # source_plan_mvp0.md §6.1 names "Circular 52/2018" as the credit
        # institution-rating regulation feeding into SBV's credit-room
        # allocation mechanism — confirmed live that Circular 52/2018/
        # TT-NHNN is genuinely that regulation (xếp hạng tổ chức tín
        # dụng), but also confirmed live it was replaced by Circular
        # 21/2025/TT-NHNN effective 2025-11-01, before this source was
        # even added (today: 2026-09-02). Sourcing 21/2025 instead of the
        # plan's stale reference — tracking the plan's *intent* (the
        # currently-effective rating regulation), not its now-outdated
        # document number. 74.8K chars scoped — chunked.
        "url": "https://luatvietnam.vn/tai-chinh/thong-tu-21-2025-tt-nhnn-quy-dinh-xep-hang-to-chuc-tin-dung-va-chi-nhanh-ngan-hang-nuoc-ngoai-412754-d1.html",
        "chunked": True,
        "prompt": (
            "This is Circular 21/2025/TT-NHNN, issued July 31, 2025 by the "
            "State Bank of Vietnam (effective November 1, 2025), "
            "replacing Circular 52/2018/TT-NHNN on rating credit "
            "institutions and foreign bank branches. Extract the concrete "
            "rating methodology described — the rating groups (e.g. large "
            "commercial banks, small commercial banks, foreign bank "
            "branches), the quantitative/qualitative criteria used, and how "
            "this feeds into SBV's credit growth room allocation if stated. "
            "Note the reference number, issuing authority, and effective "
            "date exactly as given; do not fabricate anything not actually "
            "present in the text below. source_code for these signals is "
            "\"SBV\"."
        ),
    },
    {
        "id": "decree_94_2025_nd_cp_fintech_sandbox",
        "kind": "qualitative",
        "role": "aggregator",
        # 124.1K chars scoped (includes full appendices/report-form
        # templates) — chunked.
        "url": "https://luatvietnam.vn/tai-chinh/nghi-dinh-942025nd-cp-co-che-thu-nghiem-co-kiem-soat-trong-linh-vuc-ngan-hang-399142-d1.html",
        "chunked": True,
        "prompt": (
            "This is Decree 94/2025/ND-CP, issued April 29, 2025 by the "
            "Government of Vietnam (effective July 1, 2025), on a "
            "controlled testing mechanism (sandbox) for fintech in "
            "banking. Extract concrete provisions on: which fintech "
            "solutions are covered (credit scoring, Open API data sharing, "
            "peer-to-peer lending), who can participate (credit "
            "institutions, foreign bank branches, licensed fintech "
            "companies), the maximum testing duration, and any reporting "
            "obligations. Note the reference number, issuing authority, "
            "and effective date exactly as given; do not fabricate "
            "anything not actually present in the text below. source_code "
            "for these signals is \"CHINHPHU\"."
        ),
    },
    {
        "id": "resolution_57_nq_tw_digital_transformation",
        "kind": "qualitative",
        "role": "aggregator",
        # 36.6K chars scoped — chunked. Issued by the Politburo (Bộ Chính
        # trị), not the Government — source_code "TW" distinguishes this
        # from CHINHPHU-issued documents.
        "url": "https://luatvietnam.vn/khoa-hoc/nghi-quyet-57-nq-tw-2024-dot-pha-phat-trien-khcn-doi-moi-sang-tao-va-chuyen-doi-so-quoc-gia-381835-d1.html",
        "chunked": True,
        "prompt": (
            "This is Resolution 57-NQ/TW, issued December 22, 2024 by the "
            "Politburo, on breakthrough development of science, "
            "technology, innovation, and national digital transformation. "
            "Extract concrete targets and directions relevant to banking "
            "or fintech — for example cashless-transaction targets, "
            "digital-economy targets, digital-infrastructure directions, "
            "or e-government/e-identification goals. Note the reference "
            "number, issuing authority, and date exactly as given; do not "
            "fabricate anything not actually present in the text below. "
            "source_code for these signals is \"TW\"."
        ),
    },
    {
        "id": "resolution_110_2025_ubtvqh15_pit_deduction",
        "kind": "qualitative",
        "role": "aggregator",
        # 10.2K chars scoped — fits in a single call, not chunked. Issued
        # by the National Assembly Standing Committee.
        "url": "https://luatvietnam.vn/thue/nghi-quyet-110-2025-ubtvqh15-dieu-chinh-muc-giam-tru-gia-canh-thue-thu-nhap-ca-nhan-418037-d1.html",
        "prompt": (
            "This is Resolution 110/2025/UBTVQH15, issued October 17, 2025 "
            "by the National Assembly Standing Committee, adjusting the "
            "personal income tax family deduction level, effective January "
            "1, 2026. Extract the exact new deduction figures — the "
            "taxpayer's own deduction (15.5 million VND/month) and the "
            "per-dependent deduction (6.2 million VND/month) — and the "
            "prior levels being replaced, if stated. Note the reference "
            "number, issuing authority, and effective date exactly as "
            "given; do not fabricate anything not actually present in the "
            "text below. source_code for these signals is \"UBTVQH\"."
        ),
    },
    {
        "id": "pit_law_109_2025_qh15",
        "kind": "qualitative",
        "role": "aggregator",
        # 59.4K chars scoped — chunked. Issued by the National Assembly.
        "url": "https://english.luatvietnam.vn/law-on-personal-income-tax-no-109-2025-qh15-dated-december-10-2025-of-the-national-assembly-422733-doc1.html",
        "chunked": True,
        "prompt": (
            "This is the Law on Personal Income Tax No. 109/2025/QH15, "
            "passed December 10, 2025 by the National Assembly (effective "
            "July 1, 2026). Extract concrete provisions relevant to "
            "disposable income and consumer banking — the 5-tier tax "
            "schedule and its bracket thresholds/rates, the revenue "
            "threshold below which individual/household businesses are "
            "exempt (500 million VND/year), new taxable-income categories "
            "added (e.g. e-commerce/digital-platform income, gold-bar "
            "transfers), and any other concrete new rule. Note the "
            "reference number, issuing authority, and effective date "
            "exactly as given; do not fabricate anything not actually "
            "present in the text below. source_code for these signals is "
            "\"QH\"."
        ),
    },
    {
        "id": "decision_21_2025_qd_ttg_green_taxonomy",
        "kind": "qualitative",
        "role": "aggregator",
        # 72.2K chars scoped — chunked. Issued by the Prime Minister
        # (Thủ tướng), not the full Government — source_code "TTG"
        # distinguishes this from CHINHPHU-issued decrees.
        "url": "https://luatvietnam.vn/dau-tu/quyet-dinh-21-2025-qd-ttg-tieu-chi-moi-truong-va-xac-nhan-du-an-dau-tu-xanh-404821-d1.html",
        "chunked": True,
        "prompt": (
            "This is Decision 21/2025/QD-TTg, issued July 4, 2025 by the "
            "Prime Minister (effective August 22, 2025), setting Vietnam's "
            "national green taxonomy — environmental criteria and "
            "confirmation procedure for a project to qualify as a green "
            "investment. Extract the concrete dual-criteria test described "
            "(environmental compliance approval plus genuine environmental "
            "benefit/sector match) and which sectors or project types "
            "qualify. Note the reference number, issuing authority, and "
            "effective date exactly as given; do not fabricate anything "
            "not actually present in the text below. source_code for "
            "these signals is \"TTG\"."
        ),
    },
    {
        "id": "sbv_circular_17_2022_tt_nhnn_environmental_risk",
        "kind": "qualitative",
        "role": "aggregator",
        # 32.6K chars scoped — chunked.
        "url": "https://english.luatvietnam.vn/circular-no-17-2022-tt-nhnn-providing-guidance-on-environmental-risk-management-in-credit-extens-239592-doc1.html",
        "chunked": True,
        "prompt": (
            "This is Circular 17/2022/TT-NHNN, issued December 23, 2022 by "
            "the State Bank of Vietnam, on environmental risk management "
            "in credit extension by credit institutions and foreign bank "
            "branches. Extract concrete provisions — what environmental "
            "risk assessment credit institutions must perform, which "
            "lending activities it applies to, and any specific "
            "obligations or timelines. Note the reference number, issuing "
            "authority, and date exactly as given; do not fabricate "
            "anything not actually present in the text below. source_code "
            "for these signals is \"SBV\"."
        ),
    },

    # ------------------------------------------------------------------
    # Layer 3/6.3 — Tier 2 sources (securities-firm research §5, consumer
    # research §6.3), the two rows unblocked by the tier2-fact-opinion-field
    # work (.scratch/tier2-fact-opinion-field/spec.md). role stays
    # "citable" (both rows are "Citable (Tier 2)" per source_plan_mvp0.md,
    # not "aggregator" — these are each firm's own published research, not
    # a third-party aggregator); "tier": "tier_2" is what actually matters
    # at runtime, leaving fact_or_opinion to the model's own per-signal
    # judgment (agent/graph.py's _finalize_payload only forces "fact" for
    # tier_1). Each prompt below spells out the fact/opinion boundary
    # explicitly, since these documents genuinely mix both in one place.
    #
    # Of the plan's 4 named securities firms, SSI, VCBS, and BSC are all
    # included here — VNDirect (vndirect.com.vn) is the only one skipped,
    # for a compliance reason (its robots.txt has a dedicated
    # "User-agent: ClaudeBot / Disallow: /" block, the same pattern
    # already found on thuvienphapluat.vn — see agent/sources.py's Layer 4
    # legal-document comment above), not a technical one. VCBS's report
    # list only resolves after clicking its "Báo cáo ngành" tab, and a
    # plain synthetic .click() on the report's own title/icon did nothing
    # — a genuinely trusted Playwright click on that same icon did
    # trigger real navigation, but to an intermediate discovery page
    # that's genuinely bot-gated (confirmed live: loads an invisible
    # reCAPTCHA, stays blank even after a 15s wait). The underlying PDF
    # file itself carries no gate at all — only the page used to discover
    # it does — confirmed by the user's own manual click surfacing the
    # working direct file URL. See VCBS_BANKING_SECTOR_REPORT_URL's
    # comment in agent/crawler.py. BSC's own plan-listed URL
    # (chi-tiet-bao-cao/714250, "Báo cáo phân tích ngành Ngân Hàng") is
    # simply dead — confirmed live it's not linked from anywhere on the
    # current site — but its real, current report listing (found via
    # BSC's own "Industry & Business Report" nav link, a different URL
    # pattern than the plan's dead link) does have real, live analyst
    # content; see bsc_mbb_report below.
    #
    # Of the plan's 3 named consumer-research firms, Cimigo is skipped.
    # Its "evergreen" trends page republishes 2022 GDP/COVID-era figures
    # under a non-dated URL, and its 2024 report's landing page is
    # email-gated and now 404s regardless. Paginating its full article
    # feed (not just the homepage's first page) did surface a genuinely
    # free Dec 2024 article — but by the time this was checked (Sept
    # 2026) that's already ~21 months old, well past the plan's quarterly
    # cadence, and its competitive-ranking claims could easily have
    # reversed since; explicit user call to still skip rather than add
    # stale-but-less-stale data. Decision Lab and Q&Me both cover this
    # row's real content need (Gen X/Y/Z lifestyle/banking behavior,
    # satisfaction rankings) with genuinely current data.
    {
        "id": "ssi_banking_sector_report",
        "kind": "qualitative",
        "role": "citable",
        "tier": "tier_2",
        # See SSI_BANKING_SECTOR_REPORT_URL's own comment in
        # agent/crawler.py for the full discovery story (listing page
        # never exposes real report links; this hand-verified PDF found
        # via web search instead; ftp2.ssi.com.vn 403s crawl4ai's own PDF
        # downloader specifically — a crawl4ai quirk, not a real site
        # block, confirmed live that plain curl gets a clean 200 — fetched
        # via direct urllib instead). 19.5K chars, real content: SSI
        # Research's analysis of NHNN's draft circular replacing Circular
        # 22/2019/TT-NHNN (Basel III-aligned prudential ratios).
        "url": "https://ftp2.ssi.com.vn/Customers/GDDT/Analyst_Report/Sector%20Report/Cap%20nhat%20nganh%20Ngan%20hang_Thong%20tu%2022_2026.05.05_SSIResearch.pdf",
        "prompt": (
            "This is an SSI Research (SSI Securities) banking-sector "
            "analyst report. Extract concrete signals — both directly "
            "reported facts (e.g. what a regulator has proposed or "
            "disclosed) and SSI's own analyst views (e.g. forecasts, "
            "sector comparisons, expected impact on specific banks). Tag "
            "each signal's fact_or_opinion carefully: \"fact\" only for a "
            "directly disclosed/reported development (e.g. a regulator's "
            "own draft circular or a bank's own disclosed figure quoted in "
            "the report); \"opinion\" for SSI's own analysis, "
            "interpretation, forecast, or expected-impact assessment — "
            "this report contains plenty of both, so do not default "
            "everything to one value. Any forecast figure must have "
            "actual_proxy_forecast set to \"forecast\" with forecast_org "
            "set to \"SSI Research\". source_code for these signals is "
            "\"SSI\"."
        ),
    },
    {
        "id": "vcbs_banking_sector_report",
        "kind": "qualitative",
        "role": "citable",
        "tier": "tier_2",
        # See VCBS_BANKING_SECTOR_REPORT_URL's own comment in
        # agent/crawler.py for the full discovery story: VCBS's report
        # list only resolves after clicking its "Báo cáo ngành" tab, and
        # a plain synthetic .click() on the report's own title/icon did
        # nothing (no navigation) — a genuinely trusted Playwright click
        # on the exact same download icon (confirmed via the user's own
        # browser inspector — same element) did trigger real navigation,
        # but to an intermediate discovery page that's genuinely
        # bot-gated (confirmed live: loads an invisible reCAPTCHA, stays
        # blank even after a 15s wait — not a timing issue). The user's
        # own manual click bypassed that page and surfaced this direct
        # file URL, which itself carries no gate at all — only the page
        # used to discover it does. 73.1K chars, real, current content:
        # VCBS Research's 2026 banking-sector outlook (credit growth
        # 17.87% as of 25/12/2025 vs. 13.82% the same period a year
        # earlier).
        "url": "https://www.vcbs.com.vn/storage/ttpt_reports/20260109/bao-cao-nganh-ngan-hang-2026.pdf",
        "chunked": True,
        "prompt": (
            "This is a VCBS Research (Vietcombank Securities) "
            "banking-sector analyst report. Extract concrete signals — "
            "both directly reported facts (e.g. system-wide credit growth "
            "figures reported by NHNN/banks) and VCBS's own analyst views "
            "(e.g. sector outlook, forecasts, bank-specific comparisons). "
            "Tag each signal's fact_or_opinion carefully: \"fact\" only "
            "for a directly disclosed/reported figure (e.g. NHNN's own "
            "credit growth statistic quoted in the report); \"opinion\" "
            "for VCBS's own analysis, interpretation, forecast, or "
            "sector-outlook assessment — this report contains plenty of "
            "both, so do not default everything to one value. Any "
            "forecast figure must have actual_proxy_forecast set to "
            "\"forecast\" with forecast_org set to \"VCBS Research\". "
            "source_code for these signals is \"VCBS\"."
        ),
    },
    {
        "id": "bsc_mbb_report",
        "kind": "qualitative",
        "role": "citable",
        "tier": "tier_2",
        # BSC's plan-listed URL (chi-tiet-bao-cao/714250, "Báo cáo phân
        # tích ngành Ngân Hàng") is dead — confirmed live it's not linked
        # from anywhere on the current site (a 3.3MB scan of its
        # by-company report listing found zero matches for that report ID
        # or title), and its own detail page renders the same generic
        # stock-ticker dashboard regardless. The real, current report
        # listing lives at bsc.com.vn/bao-cao-nganh-doanh-nghiep/ (found
        # via "Industry & Business Report" in BSC's own nav — a different
        # URL pattern than the plan's dead link, bao-cao/{id}-{slug} not
        # chi-tiet-bao-cao/{id}). No dedicated whole-sector banking report
        # was found there at time of writing, but a real, current,
        # substantive bank-specific analyst report was (BSC's own "X-Alpha"
        # research line) — confirmed live: a genuine BUY recommendation on
        # MBB with target price, ROAE analysis, and 2026-2027F forecasts,
        # dated 20/08/2026. 18.2K chars (chunked) — a content_selector
        # (.detail) was tried but truncates real content, so left unscoped.
        "url": "https://www.bsc.com.vn/bao-cao/15801-x-alpha-mbb-25700-29-tiep-them-nhien-lieu-tang-toc-tren-duong-bang",
        "chunked": True,
        "prompt": (
            "This is a BSC Research (BIDV Securities) equity analyst "
            "report on MBB (Military Commercial Joint Stock Bank). "
            "Extract concrete signals — both directly reported facts "
            "(e.g. disclosed financial figures quoted in the report) and "
            "BSC's own analyst views (the BUY/SELL/HOLD call, target "
            "price, valuation multiples, ROAE outlook, growth forecasts, "
            "named catalysts). Tag each signal's fact_or_opinion "
            "carefully: \"fact\" only for a directly disclosed/reported "
            "figure; \"opinion\" for BSC's own analysis, recommendation, "
            "valuation, or forecast — this report is mostly analyst "
            "opinion, so most signals should be \"opinion\", but don't "
            "default everything to one value if a genuine disclosed fact "
            "is present. Any forecast figure (target price, forecast "
            "ROAE/profit growth) must have actual_proxy_forecast set to "
            "\"forecast\" with forecast_org set to \"BSC Research\". "
            "source_code for these signals is \"BSC\"."
        ),
    },
    {
        "id": "decisionlab_bank_satisfaction_rankings",
        "kind": "qualitative",
        "role": "citable",
        "tier": "tier_2",
        # Confirmed live: real, current (2026 rankings, published 2026)
        # content, no login/email gate — a public blog post, not a
        # downloadable report.
        "url": "https://www.decisionlab.co/blog/bank-satisfaction-rankings-2026-vietcombank-returns-to-the-top-spot-as-competition-tightens-amongst-top-players",
        "prompt": (
            "This is Decision Lab's Bank Satisfaction Rankings 2026 "
            "(drawn from YouGov BrandIndex daily consumer research). "
            "Extract concrete signals — each bank's Net Satisfaction "
            "Score and ranking position, and any named driver of a "
            "bank's rise or fall. Since these rankings are Decision Lab's "
            "own survey-based measurement of customer sentiment, not an "
            "official disclosure, tag every signal's fact_or_opinion as "
            "\"opinion\" and note the survey basis (YouGov BrandIndex) in "
            "the summary. data_basis is \"not_applicable\". source_code "
            "for these signals is \"DECISIONLAB\"."
        ),
    },
    {
        "id": "qandme_online_banking_usage",
        "kind": "qualitative",
        "role": "citable",
        "tier": "tier_2",
        # Confirmed live: real, substantive report-summary content (91%
        # weekly online-banking-app usage, 52% security concern figure),
        # no login/email gate.
        "url": "https://qandme.net/en/report/Vietnamese-usage-of-online-banking-services.html",
        "prompt": (
            "This is a Q&Me market-research report on Vietnamese usage of "
            "online banking services. Extract concrete survey findings — "
            "usage rates, frequency, and stated concerns (e.g. security) "
            "by demographic group where given. Since these are Q&Me's own "
            "survey findings, not an official disclosure, tag every "
            "signal's fact_or_opinion as \"opinion\" and note the survey "
            "sample/method in the summary if the page states it. "
            "data_basis is \"not_applicable\". source_code for these "
            "signals is \"QANDME\"."
        ),
    },

    # ------------------------------------------------------------------
    # Layer 2 — app-store release notes (source_plan_mvp0.md §4), all 6
    # named apps. Google Play's app detail page no longer has a "What's
    # New" section at all — confirmed live: absent from the entire
    # ~1.2MB rendered page for a real, live app. This is a genuine Play
    # Store redesign (Google appears to have removed the public-facing
    # changelog), not a fetch/rendering problem — so Apple's App Store is
    # used instead for all 6, via SITE_CONFIGS["apps.apple.com"]'s
    # #mostRecentVersion selector. Confirmed live for every app: real,
    # current version history with dates — content quality varies by
    # bank (BIDV and ACB give genuinely specific per-version feature
    # notes; Techcombank/VCB/MB mostly repeat generic "faster, more
    # secure" boilerplate release over release — both are the bank's own
    # authentic self-disclosure either way, so both are included as-is).
    {
        "id": "techcombank_mobile_release_notes",
        "kind": "qualitative",
        "role": "citable",
        "url": "https://apps.apple.com/vn/app/techcombank-mobile/id1548623362",
        "prompt": (
            "This is Techcombank Mobile's App Store version history. "
            "Extract concrete release notes — the version number, "
            "release date, and any specific new feature or change named "
            "(not just generic \"faster and more secure\" boilerplate, "
            "if a specific feature is also mentioned). If a version's "
            "notes are pure generic boilerplate with no specific feature "
            "named, still report it as a signal (it's the bank's genuine "
            "self-disclosed update cadence) but keep the summary honest "
            "about there being no specific feature disclosed. "
            "data_basis is \"not_applicable\". source_code for these "
            "signals is \"TCB\"."
        ),
    },
    {
        "id": "vcb_digibank_release_notes",
        "kind": "qualitative",
        "role": "citable",
        "url": "https://apps.apple.com/vn/app/vcb-digibank/id561433133",
        "prompt": (
            "This is VCB Digibank's App Store version history. Extract "
            "concrete release notes — the version number, release date, "
            "and any specific new feature or change named (not just "
            "generic performance-improvement boilerplate, if a specific "
            "feature is also mentioned). If a version's notes are pure "
            "generic boilerplate with no specific feature named, still "
            "report it as a signal (it's the bank's genuine self-"
            "disclosed update cadence) but keep the summary honest about "
            "there being no specific feature disclosed. data_basis is "
            "\"not_applicable\". source_code for these signals is "
            "\"VCB\"."
        ),
    },
    {
        "id": "bidv_smartbanking_release_notes",
        "kind": "qualitative",
        "role": "citable",
        "url": "https://apps.apple.com/vn/app/bidv-smartbanking/id1061867449",
        "prompt": (
            "This is BIDV SmartBanking's App Store version history. "
            "Extract concrete release notes — the version number, "
            "release date, and each specific new feature or product "
            "named (e.g. a new insurance product, certificate of "
            "deposit, or transfer feature) — this app's release notes "
            "tend to be genuinely specific, not generic boilerplate. "
            "data_basis is \"not_applicable\". source_code for these "
            "signals is \"BID\"."
        ),
    },
    {
        "id": "mbbank_app_release_notes",
        "kind": "qualitative",
        "role": "citable",
        "url": "https://apps.apple.com/vn/app/mb-bank/id1205807363",
        "prompt": (
            "This is the MBBank app's App Store version history. Extract "
            "concrete release notes — the version number, release date, "
            "and any specific new feature or change named (not just "
            "generic boilerplate, if a specific feature is also "
            "mentioned). If a version's notes are pure generic "
            "boilerplate with no specific feature named, still report it "
            "as a signal (it's the bank's genuine self-disclosed update "
            "cadence) but keep the summary honest about there being no "
            "specific feature disclosed. data_basis is \"not_applicable\". "
            "source_code for these signals is \"MBB\"."
        ),
    },
    {
        "id": "acb_one_release_notes",
        "kind": "qualitative",
        "role": "citable",
        "url": "https://apps.apple.com/vn/app/acb-one/id950141024",
        "prompt": (
            "This is ACB ONE's App Store version history. Extract "
            "concrete release notes — the version number, release date, "
            "and each specific new feature named (e.g. smart term "
            "deposit, eSIM top-up, train reservations, online sign-up "
            "improvements) — this app's release notes tend to be "
            "genuinely specific, not generic boilerplate. data_basis is "
            "\"not_applicable\". source_code for these signals is "
            "\"ACB\"."
        ),
    },
    {
        "id": "vpbank_neo_release_notes",
        "kind": "qualitative",
        "role": "citable",
        "url": "https://apps.apple.com/vn/app/vpbank-neo/id1209349510",
        "prompt": (
            "This is VPBank NEO's App Store version history. Extract "
            "concrete release notes — the version number, release date, "
            "and each specific new feature or change named (e.g. a "
            "transfer improvement, QR scanning change, deposit-rate "
            "tracking feature). data_basis is \"not_applicable\". "
            "source_code for these signals is \"VPB\"."
        ),
    },
]
