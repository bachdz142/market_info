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
]
