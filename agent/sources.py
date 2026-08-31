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
    # Only the two sources below are confirmed working via a live crawl()
    # test as of this pass. The 5 bank investor-relations pages (Techcombank,
    # Vietcombank, BIDV, MBBank, ACB) and Vietstock's per-ticker document
    # aggregator were investigated but not added: each bank IR page's real
    # figures live behind a linked PDF report, and each site's CMS needs its
    # own custom content_selector/pdf_link_selector (the kind of per-site
    # discovery SBV's press-release source above needed) — none were nailed
    # down yet. Vietstock's document table didn't render even after 60s of
    # waiting with the JS-rendering strategy, suggesting it may be gated
    # behind login/anti-bot rather than just needing a longer wait. Follow-up
    # work, not silently dropped.
    {
        "id": "sbv_portal_statistics",
        "kind": "quant",
        "role": "citable",
        "url": "https://sbv.gov.vn/en/statistics",
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
