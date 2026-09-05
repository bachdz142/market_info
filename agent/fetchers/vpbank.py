# VPBank's news and fee/document listing pages (Layer 2) share the same
# AJAX-gap as ACB's above — the page shell/title renders, the real listing
# never does. Confirmed live (2026-09-01) via real Playwright network
# capture: both pages call VPBank's own "uiux-api", which returns real JSON
# content directly (no separate detail-fetch step needed, unlike ACB's
# two-step case) — a single request each. Citation URL stays the
# human-readable page; the actual fetch target is this API. The news API's
# captured call included a "publishYear=2026" param that would go stale —
# confirmed live it works identically without it (already sorted
# newest-first), so it's dropped here.
from typing import List, Tuple

from agent.crawler import _fetch_api_json_text
from agent.fetcher_registry import register_fetcher

VPBANK_NEWS_URL = "https://www.vpbank.com.vn/tin-tuc"
VPBANK_NEWS_API = (
    "https://www.vpbank.com.vn/uiux-api/api/article"
    "?categoryPath=%2Ftin-tuc%2Fthong-cao-bao-chi&pageSize=9&pageIndex=1&sort=displayDate,DESC&lang=vi"
)
VPBANK_FEE_URL = "https://www.vpbank.com.vn/tai-lieu-bieu-mau"
# The captured network call drilled into "bieu-mau" (Forms) > "khach-hang-
# ca-nhan" — the page's own default tab, not the fee schedule. "tai-lieu-
# bieu-mau" (Documents & Forms) has "Biểu phí" (Fee Schedule) as a
# *separate sibling* category, confirmed via its own category/children
# endpoint. Using the top-level "bieu-phi" path (not drilling into one
# customer segment) returns fee documents across segments at once
# (individual, business households, SME, large corporate) — better fit
# for "product conditions by segment" than any single segment's tab.
VPBANK_FEE_API = (
    "https://www.vpbank.com.vn/uiux-api/api/document"
    "?categoryPath=%2Ftai-lieu-bieu-mau%2Fbieu-phi"
    "&pageIndex=1&pageSize=10&sort=publishTime,DESC&lang=vi"
)


@register_fetcher(VPBANK_NEWS_URL, "single")
async def _fetch_vpbank_news() -> Tuple[str, List[Tuple[str, str]]]:
    return await _fetch_api_json_text(VPBANK_NEWS_API), []


@register_fetcher(VPBANK_FEE_URL, "single")
async def _fetch_vpbank_fee() -> Tuple[str, List[Tuple[str, str]]]:
    return await _fetch_api_json_text(VPBANK_FEE_API), []
