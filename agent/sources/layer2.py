# Layer 2 — CVP, offerings & segment sales

LAYER2_SOURCES = [
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
        # guess — see agent/fetchers/acb.py's _fetch_acb_promotions_text() for
        # the two-step API (a promo-id list, then each item's real content
        # from the Vietnamese-locale detail endpoint — the English one
        # returns nulls for these Vietnamese-only posts). Confirmed live: 8
        # real, current promotions (0-fee transfers, cashback offers,
        # savings-rate boosts), several with explicit validity date ranges.
        # 2026-09-03 follow-up (user-flagged, same click-through gap as
        # mbbank_news): the detail API's own description fields are a stub
        # (long_description null, short_description ~70 chars). Now also
        # fetches each promo's real public detail page
        # (acb.com.vn/vi/uu-dai/{slug}, server-rendered, no JS needed) and
        # uses its real body text when longer — confirmed live, 358-14758
        # real chars per promo vs. ~70 before.
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
        # The listing page's "newest promotions" widget has real,
        # followable links straight in its raw HTML — but non-
        # deterministically: confirmed live (2026-09-05) 3 of 4 fetches
        # returned 8 real links, the 4th an empty widget (a caching/render
        # race, same class as bidv.com.vn's Layer 1 page). See
        # agent/fetchers/vietcombank.py's _fetch_vcb_promotions_text():
        # retries the listing fetch on an empty widget, then follows the 3
        # newest real links directly — reverted from an earlier sitemap.xml
        # <lastmod>-based discovery mechanism (2026-09-01) that turned out
        # to be solving a problem that mostly didn't exist while adding a
        # real cost: 2 of the sitemap's 3 "newest" entries were dead when
        # live-checked, one 302-redirecting to VCB's own soft-404. VCB's
        # separate fee schedule page is NOT solved this way — its fee
        # table is an embedded image, not JS-gapped content, so no amount
        # of crawling fixes it; needs OCR (same category as BIDV's/VCB's
        # own Layer 1 scan-only filings).
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
        # agent/fetchers/acb.py's _fetch_acb_fee_schedule_text(). Category
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
        # agent/fetchers/mbbank.py's _fetch_mbbank_fee_text(): a plain CSS wait
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
        # bare domain doesn't. See agent/fetchers/mbbank.py's
        # _fetch_mbbank_news_parts(): needed the same JS-predicate wait
        # fix, additionally scoped to the target container itself (not
        # just "does a matching link exist on the page anywhere") since
        # even the page-wide version raced with this container's own
        # content settling — confirmed live across several runs before
        # landing on a reliable condition. Confirmed live: real, dated
        # news items (a minigame results announcement, a CSR sustainability
        # partnership, procurement notices).
        # Fixed 2026-09-03 (user review: "you did not click inside the
        # actual article right?"): confirmed it didn't -- only the
        # listing's own teaser text per item was ever read. This listing's
        # teaser is a genuine 1-2 sentence summary, not a bare title, so
        # signals were already informative (who a partnership was with,
        # roughly what it covered) -- just missing the real depth
        # (attendance figures, exact terms) only in the full article. See
        # agent/fetchers/mbbank.py's _fetch_mbbank_news_parts(): follows the 3
        # most recent /chi-tiet/ article links already known to exist
        # (the listing's own wait-condition already checks for them).
        # multi_pdf: these are genuinely separate documents.
        "url": "https://www.mbbank.com.vn/news/tin-tuc",
        "multi_pdf": True,
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
        # agent/fetchers/vietcombank.py's VCB_FEE_PDF_URLS comment: dynamically
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
