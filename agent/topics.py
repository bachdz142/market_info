# Predefined research topics for the Vietnam banking-sector macro monitor.
# `kind` doesn't affect execution yet — both kinds run through the same
# search+structure flow. It's metadata for a future deterministic data-fetch
# node (e.g. a rates/FX API) to claim the "quant" topics without a redesign.

TOPICS = [
    {
        "id": "sbv_policy_rate",
        "kind": "quant",
        "prompt": "Latest State Bank of Vietnam (SBV) refinancing rate and rediscount rate, and any recent changes.",
    },
    {
        "id": "vnibor",
        "kind": "quant",
        "prompt": "Latest VND interbank offered rate (VNIBOR) levels across overnight, 1-week, and 1-month tenors.",
    },
    {
        "id": "usdvnd_rate",
        "kind": "quant",
        "prompt": "Latest USD/VND exchange rate and SBV's daily central rate (tỷ giá trung tâm), and any recent moves.",
    },
    {
        "id": "vietnam_cpi",
        "kind": "quant",
        "prompt": "Latest Vietnam CPI / inflation print from the General Statistics Office (GSO).",
    },
    {
        "id": "vgb_yields",
        "kind": "quant",
        "prompt": "Latest Vietnam government bond yields across key tenors and any notable recent moves.",
    },
    {
        "id": "sbv_credit_room",
        "kind": "quant",
        "prompt": "Latest SBV credit growth quota ('room') decisions or adjustments for Vietnamese banks.",
    },
    {
        "id": "peer_bank_earnings",
        "kind": "qualitative",
        "prompt": "Recent earnings results or management guidance commentary from major Vietnamese banks (Vietcombank, Techcombank, VPBank, MB, ACB, BIDV, VietinBank).",
    },
    {
        "id": "sbv_regulatory",
        "kind": "qualitative",
        "prompt": "Recent State Bank of Vietnam regulatory developments affecting banks: Basel II/III implementation, NPL/bad-debt resolution circulars, foreign ownership limit changes.",
    },
    {
        "id": "vietnam_bank_ratings",
        "kind": "qualitative",
        "prompt": "Recent credit rating agency actions (Moody's, S&P, Fitch) on Vietnam's sovereign rating or on Vietnamese banks.",
    },
    {
        "id": "foreign_investment_ma",
        "kind": "qualitative",
        "prompt": "Recent foreign strategic investment or M&A activity involving Vietnamese banks.",
    },
    {
        "id": "real_estate_bond_stress",
        "kind": "qualitative",
        "prompt": "Recent signals of stress or recovery in Vietnam's real estate and corporate bond markets, and implications for Vietnamese bank asset quality.",
    },
    {
        "id": "tet_campaign",
        "kind": "qualitative",
        "prompt": "Recent or upcoming Tết (Lunar New Year) promotional campaigns from Vietnamese banks: lì xì-themed cards, cashback offers, personal loan or gold-savings promotions, credit card sign-up bonuses.",
    },
    {
        "id": "digital_banking_launches",
        "kind": "qualitative",
        "prompt": "Recent digital banking or super-app feature launches by Vietnamese banks: e-wallet integration, QR payment, buy-now-pay-later (BNPL), new mobile app capabilities.",
    },
    {
        "id": "card_promotions",
        "kind": "qualitative",
        "prompt": "Recent credit or debit card promotions from Vietnamese banks tied to shopping festivals or seasonal events (e.g. back-to-school, 11/11, 12/12), excluding Tết.",
    },
    {
        "id": "savings_product_launches",
        "kind": "qualitative",
        "prompt": "Recent new savings or deposit product launches and interest rate changes from Vietnamese banks, including tiered or flexible savings products.",
    },
    {
        "id": "sme_lending_campaigns",
        "kind": "qualitative",
        "prompt": "Recent SME lending campaigns or credit packages launched by Vietnamese banks, including any tied to government stimulus programs.",
    },
    {
        "id": "mortgage_campaigns",
        "kind": "qualitative",
        "prompt": "Recent mortgage or home-loan promotional campaigns from Vietnamese banks, including developer-linked partnership offers.",
    },
    {
        "id": "green_finance_products",
        "kind": "qualitative",
        "prompt": "Recent green finance or ESG-linked product launches by Vietnamese banks: green bonds, sustainability-linked loans, environmental financing programs.",
    },
    {
        "id": "bancassurance_campaigns",
        "kind": "qualitative",
        "prompt": "Recent bancassurance partnership announcements or insurance cross-sell campaigns from Vietnamese banks.",
    },
    {
        "id": "year_end_bonus_effects",
        "kind": "qualitative",
        "prompt": "Recent Vietnamese bank marketing campaigns targeting year-end bonus season: savings promotions, wealth management offers timed to salary/bonus payouts.",
    },
    {
        "id": "agricultural_lending_cycles",
        "kind": "qualitative",
        "prompt": "Recent agricultural lending campaigns or seasonal credit programs from Vietnamese banks tied to planting or harvest cycles.",
    },
]
