# Layer 1 — Quantitative bank benchmarks

LAYER1_SOURCES = [
    # --- Layer 1 (quant bank benchmarks, source_plan_mvp0.md) ---
    # Techcombank, BIDV, ACB, and MBBank are live-verified. Still open:
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
    #   - ACB (see agent/fetchers/acb.py's _fetch_acb_statement_text): its
    #     "Download" controls have no href/onclick at all — turned out not
    #     to be an anti-bot problem, just a React app whose PDF links only
    #     exist after a JS click fires an API call. Network-capturing a
    #     simulated click found that call is a plain, unauthenticated JSON
    #     API (acb.com.vn/api/en/front/v1/posts) — calling it directly is
    #     simpler and more stable than click-simulation.
    #   - MBBank (see agent/fetchers/mbbank.py's MBBANK_FINANCIAL_STATEMENTS_URL): its
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
        # Groq free-tier ceiling as Techcombank's. See agent/fetchers/acb.py's
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
        # above). See agent/crawler.py's _fetch_vietstock_statement_text
        # (called from agent/fetchers/mbbank.py for this source): the actual fetch goes through
        # Vietstock's static-CDN mirror of MBB's own filed statement
        # instead — a genuine Aggregator source per source_plan_mvp0.md
        # §2, not a bot-evasion technique, and metadata still attributes
        # the figures to MBBank's own disclosure, not Vietstock. Confirmed
        # live: this specific mirrored copy has a real (if imperfectly
        # OCR'd/encoded) text layer — VCB's equivalent copy does not (a
        # 55-page scan with zero extractable text) and was NOT added for
        # that reason.
        "chunked": True,
        # Reopened 2026-09-02 (user review of the actual fetched text:
        # "Oja chi: s6 18 Le Van LLl'O'ngPhU'O'ng Yen Hoa..." — real
        # Vietnamese-diacritic mangling from this mirror's own OCR pass,
        # not born-digital text). Measured live: corrupted_token_ratio is
        # 0.0477 — just under content_gate's 0.05 "scan" threshold, so it
        # was silently passing as "usable" despite being a genuine re-OCR'd
        # scan (this Vietstock copy is itself an OCR'd mirror, per the
        # comment above, not a one-off measurement fluke). assume_scan
        # tells _content_gate_node to always try agent/ocr.py's
        # ensure_ocr_text() for this source regardless of what the generic
        # ratio check says, rather than lowering the shared 0.05 threshold
        # (validated against other sources, real risk of new false
        # positives elsewhere) or hardcoding a source-id check deep in
        # graph.py. Falls back to the existing (garbled but numerically-
        # usable, per this source's own prompt below) extraction if OCR
        # itself fails, same as any other OCR attempt.
        "assume_scan": True,
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
        # Reopened and fixed 2026-09-02 (user found it via a live hover on
        # the Vietnamese site's own "Dữ liệu thống kê" nav dropdown — the
        # previous URL, /en/statistics, was ALWAYS pure nav/footer
        # boilerplate, confirmed live, no real statistic content in it at
        # all; see SITE_CONFIGS's own comment on this URL in
        # agent/crawler.py for the full discovery). This one URL is one of
        # ~199 monthly/quarterly system-wide banking reports under this
        # nav section — basic indicators (total assets, charter capital,
        # funding ratios, loan-to-deposit ratio) per institution type, plus
        # a system-wide total row. Confirmed live: real, current (as of
        # 30/06/2026) data, only 2,286 chars once scoped — no longer needs
        # chunking either (removed below). Other report types under the
        # same nav section (CAR, ROA/ROE) are real too but not pulled in
        # this pass — deliberately scoped to one report, not a rewrite
        # into a multi-document source.
        "url": "https://sbv.gov.vn/vi/thong-ke-mot-so-chi-tieu-co-ban",
        "prompt": (
            "This is NHNN's (State Bank of Vietnam) 'Basic indicators "
            "statistics' report for the credit institution system, as of "
            "the date stated in the table. Extract each institution type's "
            "row as its own signal (or a combined one where that reads "
            "more naturally) — total assets (absolute value and growth "
            "rate), charter capital (absolute value and growth rate), the "
            "short-term-funds-for-medium/long-term-lending ratio, and the "
            "loan-to-deposit ratio — plus the 'Toàn hệ thống' (whole "
            "system) total row as its own signal. Note the as-of date "
            "exactly as given. data_basis is \"not_applicable\". "
            "source_code for these signals is \"SBV\"."
        ),
    },
    {
        "id": "iav_bancassurance",
        "kind": "quant",
        "role": "citable",
        "url": "https://iav.vn/News/Listtt/202?page=1",
        # Fixed 2026-09-02 (user review: "you loaded the news homepage and
        # only the text from there, you have to click into the article,
        # its just a summary of article headline"). The URL was always the
        # right category — real, dated "Tổng quan thị trường bảo hiểm Việt
        # Nam ..." (Insurance Market Overview) quarterly/semi-annual/annual
        # reports are listed right there — the bug was never following
        # into them. See agent/fetchers/iav.py's
        # _fetch_iav_market_overview_parts(): follows the 3 most recent
        # article links instead of just reading the listing's own text.
        # multi_pdf (not chunked — these are genuinely separate documents,
        # not one oversized page needing arbitrary splitting).
        "multi_pdf": True,
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
