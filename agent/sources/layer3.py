# Layer 3 — Strategic profile per bank

LAYER3_SOURCES = [
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
    # comment in agent/fetchers/vcbs.py. BSC's own plan-listed URL
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
        # agent/fetchers/ssi.py for the full discovery story (listing page
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
        # agent/fetchers/vcbs.py for the full discovery story: VCBS's report
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
        "id": "techcombank_annual_report",
        "kind": "qualitative",
        "role": "citable",
        "tier": "tier_1",
        "multi_pdf": True,
        # First of source_plan_mvp0.md's 5-bank Layer 3 annual-report/AGM
        # row (.scratch/layer3-annual-reports/spec.md, ready-for-agent,
        # parked mid-discovery in an earlier session on exactly this
        # source's own chunking problem). Techcombank's investors page
        # links directly to its real 2025 annual report PDF — confirmed
        # live: 196 pages, real extractable text, not a scan. Scoped to
        # just Chapter 1 (Chairman's message / CEO Report) and Chapter 4
        # (Data & Analytics / Digital Office / Technology(IT) / Talent(HR)
        # transformation) by real page range — see agent/fetchers/techcombank.py's
        # _fetch_techcombank_annual_report_parts() for exactly how those
        # boundaries were found and why the rest (About Us boilerplate,
        # Governance/Risk/ESG, and the audited financial statements —
        # redundant with techcombank_vas_statements) is excluded.
        "url": "https://techcombank.com/content/dam/techcombank/public-site/documents/techcombank-2025-annual-report-eng-vf.pdf",
        "prompt": (
            "This is an excerpt from Techcombank's 2025 Annual Report — "
            "specifically the Chairman's/CEO's messages and the "
            "technology-transformation chapter (Data & Analytics, Digital "
            "Office, Technology/IT, Talent). Extract concrete strategic "
            "signals: named technology initiatives (core banking, open "
            "API, digital platforms, AI/data capabilities), leadership's "
            "stated strategic priorities and outlook, and any concrete "
            "figures given (customer counts, digital adoption rates, "
            "headcount/talent figures). Since this is the bank's own "
            "official disclosure, tag a directly stated fact as \"fact\" "
            "and a forward-looking strategic statement or leadership "
            "opinion as \"opinion\" — don't default everything to one "
            "value. source_code for these signals is \"TCB\"."
        ),
    },
    {
        "id": "vietcombank_annual_report",
        "kind": "qualitative",
        "role": "citable",
        "tier": "tier_1",
        "multi_pdf": True,
        # Second of the 5-bank Layer 3 annual-report row. VCB's own
        # domain has a genuine, confirmed Akamai wall for Layer 1
        # quantitative filings (per source_plan_mvp0.md §8, routed to
        # manual ingestion, not attempted here). Updated 2026-09-03 to
        # the FY2025 edition — the original "2025 doesn't exist yet"
        # conclusion was a lazy filename guess, not a real search (caught
        # by a user follow-up after the same gap had already been found
        # for BIDV/MBBank). Found via a real Vietstock disclosure-filing
        # article (needs a browser User-Agent — a plain `requests` GET
        # with no headers gets a 403 from vietstock.vn's own site).
        # Confirmed live: 113 pages, 419K chars, 111/113 non-empty,
        # Vietnamese-only (no English variant found — the LLM handles
        # Vietnamese natively throughout this pipeline). No dedicated
        # "Technology" chapter exists in this report — scoped to the
        # Chairman/CEO leadership message and the "Report of the Board
        # of Directors - Executive Board" chapter (investment/project
        # situation, 2025 business-results assessment — including real
        # content on the VCB CashUp Mobile / VCB Tablet digital
        # products, 2026 business orientation, and the BOD's own
        # activity assessment) — see agent/fetchers/vietcombank.py's
        # _fetch_vietcombank_annual_report_parts().
        "url": "https://static2.vietstock.vn/vietstock/2026/4/17/20260416___vcb___bao_cao_thuong_nien_nam_2025.pdf",
        "prompt": (
            "This is an excerpt from Vietcombank's 2025 Annual Report "
            "(Vietnamese) — specifically the Chairman's/CEO's leadership "
            "message and the Report of the Board of Directors - "
            "Executive Board chapter (investment/project situation, "
            "2025 business-results assessment, 2026 business "
            "orientation, and the Board's own activity assessment). "
            "Extract concrete strategic signals: leadership's stated "
            "strategic priorities and outlook, named business/"
            "technology initiatives (digital products, digital "
            "platforms), and any concrete figures given (financial "
            "performance figures, shareholding structure, "
            "customer/business metrics). Since this is the bank's own "
            "official disclosure, tag a directly stated fact as "
            "\"fact\" and a forward-looking strategic statement or "
            "leadership opinion as \"opinion\" — don't default "
            "everything to one value. source_code for these signals is "
            "\"VCB\"."
        ),
    },
    {
        "id": "bidv_annual_report",
        "kind": "qualitative",
        "role": "citable",
        "tier": "tier_1",
        "multi_pdf": True,
        # Third of the 5-bank Layer 3 annual-report row. Unlike BIDV's
        # Layer 1 financial-STATEMENT filings (confirmed elsewhere in
        # this project to be scan-only, needing the OCR fallback), this
        # specific annual report PDF is a real, extractable text layer.
        # Updated 2026-09-03 to the FY2025 edition (user-supplied the
        # real page URL) — confirmed live: 95 pages, 402K chars, 94/95
        # non-empty. This year's report restructured — no standalone
        # "Digital Banking operations" section exists anymore (last
        # year's edition had one); technology content is now woven into
        # the Management's Report chapter instead. Scoped to the
        # Chairman's message and 4 pages of the Management's Report
        # chapter (Board's operational assessment, assessment of Board
        # of Management activities, an executive-management assessment
        # that includes real IT-operations detail, and the 2026 business
        # orientation) — see agent/fetchers/bidv.py's
        # _fetch_bidv_annual_report_parts() for the real page ranges.
        "url": "https://bidv.com.vn/wps/wcm/connect/f6519b5f-3abf-4694-a32c-d3057f8d75bc/BIDV_BCTN_2025_EN_%28Interactive%29.pdf?MOD=AJPERES&CACHEID=ROOTWORKSPACE-f6519b5f-3abf-4694-a32c-d3057f8d75bc-pYsQuS-",
        "prompt": (
            "This is an excerpt from BIDV's 2025 Annual Report — "
            "specifically the Chairman's message and the Management's "
            "Report chapter (Board of Directors' operational assessment, "
            "assessment of Board of Management activities, an "
            "executive-management assessment, and 2026 business "
            "orientation). Extract concrete strategic signals: named "
            "technology/IT initiatives, leadership's stated strategic "
            "priorities and outlook, and any concrete figures given "
            "(IT/operational metrics, financial performance figures). "
            "Since this is the bank's own official disclosure, tag a "
            "directly stated fact as \"fact\" and a forward-looking "
            "strategic statement or leadership opinion as \"opinion\" — "
            "don't default everything to one value. source_code for "
            "these signals is \"BIDV\"."
        ),
    },
    {
        "id": "mbbank_annual_report",
        "kind": "qualitative",
        "role": "citable",
        "tier": "tier_1",
        "multi_pdf": True,
        # Fourth of the 5-bank Layer 3 annual-report row. Updated
        # 2026-09-03 to the FY2025 edition (user-supplied the real page
        # URL) — turned out reachable directly on mbbank.com.vn itself
        # (its own JS-rendered PDF link), not needing the Vietstock
        # aggregator fallback the 2024 edition used. This edition is
        # Vietnamese-only — no English variant found — the LLM handles
        # Vietnamese content natively throughout this pipeline. Confirmed
        # live: 186 pages, 738K chars, 184/186 non-empty pages. Scoped to
        # the Chairman/CEO messages, the real "Chiến lược và định hướng
        # phát triển" (Strategy and development orientation) section, and
        # "Tình hình đầu tư và thực hiện các dự án" (Project investment
        # and implementation — real content on MB's 2,500+ IT staff and
        # RPA/AI/Machine Learning/OCR applications, directly matching
        # this source's "technology disclosures" target) — see
        # agent/fetchers/mbbank.py's _fetch_mbbank_annual_report_parts() for the
        # real page ranges.
        "url": "https://www.mbbank.com.vn/resources/files/NhaDauTu/2026/DHCD-2026/20260330---mbb---bao-cao-thuong-nien-2025.pdf",
        "prompt": (
            "This is an excerpt from MB Bank's 2025 Annual Report "
            "(Vietnamese) — specifically the Chairman's/CEO's messages, "
            "the Strategy and development orientation section, and the "
            "Project investment and implementation section. Extract "
            "concrete strategic signals: named technology initiatives "
            "(IT infrastructure investment, AI/RPA/machine-learning "
            "applications, digital platforms), leadership's stated "
            "strategic priorities and outlook, and any concrete figures "
            "given (investment amounts, IT headcount, business "
            "performance figures). Since this is the bank's own "
            "official disclosure, tag a directly stated fact as "
            "\"fact\" and a forward-looking strategic statement or "
            "leadership opinion as \"opinion\" — don't default "
            "everything to one value. source_code for these signals is "
            "\"MBB\"."
        ),
    },
    {
        "id": "acb_annual_report",
        "kind": "qualitative",
        "role": "citable",
        "tier": "tier_1",
        "multi_pdf": True,
        # Fifth and last of the 5-bank Layer 3 annual-report row. ACB's
        # own investors page is client-side API-rendered like its other
        # Layer 1/2 pages and didn't surface a direct PDF on a plain
        # fetch — used Vietstock's static document CDN instead (same
        # aggregator convention as MBBank above). Confirmed live: 89
        # pages, 157K chars, 88/89 non-empty — a real text layer (though
        # noisier extraction than the other 4 banks', with visible
        # OCR/ligature artifacts). Filed 24 March 2025 covering fiscal
        # year 2024. No dedicated Technology chapter exists here either —
        # scoped to the Chairman's Message, the "1.4 Development
        # strategy" section (2025 financial targets plus an explicit
        # digital-transformation commitment), and the Board of
        # Directors' 2025 business-plans/vision section (includes a
        # digitalization commitment) — see agent/fetchers/acb.py's
        # _fetch_acb_annual_report_parts() for the real page ranges.
        # Smallest of the 5 banks' selections (~13K chars) since ACB's
        # report dedicates less space to technology specifics than the
        # other 4 banks' reports do.
        "url": "https://static2.vietstock.vn/vietstock/2025/3/26/20250325_acb_250325_annual_report_2025.pdf",
        "prompt": (
            "This is an excerpt from ACB's 2024 Annual Report — "
            "specifically the Chairman's Message, the Development "
            "Strategy section, and the Board of Directors' 2025 "
            "business plans and vision section. Extract concrete "
            "strategic signals: leadership's stated strategic priorities "
            "and outlook, named 2025 financial targets, and any "
            "digital-transformation or technology commitments mentioned. "
            "Since this is the bank's own official disclosure, tag a "
            "directly stated fact as \"fact\" and a forward-looking "
            "strategic statement or leadership opinion as \"opinion\" — "
            "don't default everything to one value. Any explicit 2025 "
            "target figure must have actual_proxy_forecast set to "
            "\"forecast\" with forecast_org set to \"ACB\". source_code "
            "for these signals is \"ACB\"."
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
    {
        "id": "cimigo_consumer_trends",
        "kind": "qualitative",
        "role": "citable",
        "tier": "tier_2",
        # cimigo.com's "trends" blog is free — a separate thing from its
        # askcimigo.com report catalog, which IS paywalled (checked live:
        # its one banking-specific report, "Vietnam retail banking", is a
        # full paywall, no readable content). This annual flagship trends
        # article is not: confirmed live, real retail/spending/e-commerce
        # stats (modern trade share, livestream-shopping adoption, etc.),
        # no login gate. A single hardcoded URL, like this project's other
        # Layer 3 sources — will need re-pointing to next year's edition by
        # hand (2027 etc.) once this one goes stale.
        "url": "https://www.cimigo.com/en/trends/vietnam-consumer-trends-2026/",
        "prompt": (
            "This is Cimigo's Vietnam Consumer Trends 2026 article. "
            "Extract concrete survey/market findings — retail channel "
            "shift (modern trade vs. traditional trade share), "
            "e-commerce/livestream-shopping adoption rates, and any other "
            "concrete consumer-spending-behavior statistic given. Since "
            "these are Cimigo's own research findings, not an official "
            "disclosure, tag every signal's fact_or_opinion as \"opinion\" "
            "unless it's Cimigo directly citing an official statistic "
            "(e.g. GSO data), in which case use \"fact\". data_basis is "
            "\"not_applicable\". source_code for these signals is "
            "\"CIMIGO\"."
        ),
    },
    {
        "id": "decisionlab_connected_consumer",
        "kind": "qualitative",
        "role": "citable",
        "tier": "tier_2",
        "multi_pdf": True,
        # 3 most recent editions of Decision Lab's recurring "Connected
        # Consumer" quarterly report (Vietnam Digital 2025, Q1 2025, Q4
        # 2024) — picked by hand from decisionlab.co's real sitemap.xml
        # (2026-09-03), see agent/fetchers/decisionlab.py's
        # _fetch_decisionlab_connected_consumer_parts(). Confirmed live:
        # real digital/consumer-behavior findings, no login gate.
        "url": "https://www.decisionlab.co/blog/the-connected-consumer-vietnam-digital-2025",
        "prompt": (
            "These are 3 editions of Decision Lab's \"Connected Consumer\" "
            "quarterly report on Vietnamese digital behavior. Extract "
            "concrete survey findings — platform/app usage rates, digital "
            "spending or payment behavior, and any named shift between "
            "editions. Since these are Decision Lab's own survey-based "
            "findings, tag every signal's fact_or_opinion as \"opinion\" "
            "and note which edition (quarter/report name) each finding is "
            "from in the summary. data_basis is \"not_applicable\". "
            "source_code for these signals is \"DECISIONLAB\"."
        ),
    },
    {
        "id": "decisionlab_genz_behavior",
        "kind": "qualitative",
        "role": "citable",
        "tier": "tier_2",
        "multi_pdf": True,
        # 4 articles on generational (mostly Gen Z, one Gen X) consumer
        # behavior — picked by hand from decisionlab.co's real sitemap.xml
        # (2026-09-03), see agent/fetchers/decisionlab.py's
        # _fetch_decisionlab_genz_behavior_parts(). Confirmed live: real
        # content, no login gate.
        "url": "https://www.decisionlab.co/blog/vietnam-what-brands-must-know-about-generation-z",
        "prompt": (
            "These are 4 Decision Lab articles on Vietnamese Gen Z/Gen X "
            "consumer behavior. Extract concrete survey findings — stated "
            "behavior, preferences, or platform/app usage patterns by "
            "generation, and any named shift or trend. Since these are "
            "Decision Lab's own survey-based findings, tag every signal's "
            "fact_or_opinion as \"opinion\" and note which article each "
            "finding is from in the summary. data_basis is "
            "\"not_applicable\". source_code for these signals is "
            "\"DECISIONLAB\"."
        ),
    },
    {
        "id": "decisionlab_fintech_ewallet_behavior",
        "kind": "qualitative",
        "role": "citable",
        "tier": "tier_2",
        "multi_pdf": True,
        # 3 articles on e-wallet/fintech adoption and bank/payment
        # consideration behavior — picked by hand from decisionlab.co's
        # real sitemap.xml (2026-09-03), see agent/fetchers/decisionlab.py's
        # _fetch_decisionlab_fintech_ewallet_parts(). The closest of the 3
        # new decisionlab.co sources to direct banking relevance (one is
        # literally a YouGov bank/payment-system consideration ranking).
        # Confirmed live: real content, no login gate.
        "url": "https://www.decisionlab.co/blog/demystifying-the-rise-of-e-wallets-in-vietnam",
        "prompt": (
            "These are 3 Decision Lab articles on Vietnamese e-wallet and "
            "fintech adoption behavior, including a YouGov bank/payment-"
            "system consideration ranking. Extract concrete survey "
            "findings — adoption/usage rates, stated user concerns (e.g. "
            "loyalty, security), and bank/payment-provider consideration "
            "rankings where given. Since these are Decision Lab's own "
            "survey-based findings, tag every signal's fact_or_opinion as "
            "\"opinion\" and note which article each finding is from in "
            "the summary. data_basis is \"not_applicable\". source_code "
            "for these signals is \"DECISIONLAB\"."
        ),
    },
]
