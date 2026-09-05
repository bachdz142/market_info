# Layer 4 — Macro, government & PEST

LAYER4_SOURCES = [
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
        # NSO_GDP_KEY_INDICATORS_URL's own comment in agent/fetchers/nso.py for
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
        "id": "nso_vhlss_income",
        "kind": "quant",
        "role": "citable",
        # Same PxWeb server/mechanism as nso_gdp_key_indicators — see
        # NSO_VHLSS_INCOME_URL's comment in agent/fetchers/nso.py: confirmed
        # live the same fetch function works unchanged. This is the
        # household income half of source_plan_mvp0.md §6.3's VHLSS row
        # (found under NSO's "Health, Culture, Sport, Living standards..."
        # category, not a dedicated "VHLSS" page). Confirmed live: real
        # monthly average income per capita, whole-country + urban/rural +
        # 6 regions, thousand-dong figures for the 3 latest available
        # years.
        "url": "https://pxweb.nso.gov.vn/pxweb/en/Health%2C%20Culture%2C%20Sport%20and%20Living%20standard/Health%2C%20Culture%2C%20Sport%20and%20Living%20standard/E14.26.px/",
        "prompt": (
            "This is NSO's (Vietnam National Statistics Office) 'Monthly "
            "average income per capita' table (VHLSS — Vietnam Household "
            "Living Standards Survey), covering the 3 most recent "
            "available years. Extract each concrete figure as its own "
            "signal — the income per capita for the whole country, and "
            "separately for urban/rural and each named region — with the "
            "exact year as reference_period and the geography named in "
            "the summary. Note when a year is marked 'Prel.' "
            "(preliminary) in the summary. data_basis is "
            "\"not_applicable\". actual_proxy_forecast is \"actual\" for "
            "every figure here. source_code for these signals is "
            "\"NSO\"."
        ),
    },
    {
        "id": "nso_vhlss_expenditure",
        "kind": "quant",
        "role": "citable",
        # Same PxWeb server/mechanism as nso_gdp_key_indicators — see
        # NSO_VHLSS_EXPENDITURE_URL's comment in agent/fetchers/nso.py. The
        # household expenditure half of the VHLSS row. Confirmed live:
        # real monthly average expenditure per capita, whole-country +
        # urban/rural + 6 regions, thousand-dong figures.
        "url": "https://pxweb.nso.gov.vn/pxweb/en/Health%2C%20Culture%2C%20Sport%20and%20Living%20standard/Health%2C%20Culture%2C%20Sport%20and%20Living%20standard/E14.40.px/",
        "prompt": (
            "This is NSO's (Vietnam National Statistics Office) 'Monthly "
            "average expenditure per capita' table (VHLSS — Vietnam "
            "Household Living Standards Survey), covering the 3 most "
            "recent available years. Extract each concrete figure as its "
            "own signal — the expenditure per capita for the whole "
            "country, and separately for urban/rural and each named "
            "region — with the exact year as reference_period and the "
            "geography named in the summary. data_basis is "
            "\"not_applicable\". actual_proxy_forecast is \"actual\" for "
            "every figure here. source_code for these signals is "
            "\"NSO\"."
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
]
