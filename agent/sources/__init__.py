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


# Example entry shape (kept as illustrative documentation, not an active
# source):
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

from agent.sources.layer1 import LAYER1_SOURCES
from agent.sources.layer2 import LAYER2_SOURCES
from agent.sources.layer3 import LAYER3_SOURCES
from agent.sources.layer4 import LAYER4_SOURCES

SOURCES = LAYER1_SOURCES + LAYER2_SOURCES + LAYER3_SOURCES + LAYER4_SOURCES
