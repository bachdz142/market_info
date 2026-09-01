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
    # {
    #     "id": "vietnam_cpi_official",
    #     "kind": "quant",
    #     "url": "https://www.nso.gov.vn/en/cpi/",
    #     "prompt": (
    #         "Extract the most recent Vietnam Consumer Price Index (CPI) report "
    #         "from this page: the month-on-month change, the change compared to "
    #         "December of the previous year, and the year-on-year change, plus "
    #         "the reference period and date of issue."
    #     ),
    # },
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
]
