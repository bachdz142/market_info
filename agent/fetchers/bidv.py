from typing import List, Tuple

from agent.crawler import _fetch_annual_report_page_ranges
from agent.fetcher_registry import register_fetcher

# Third of the 5-bank Layer 3 annual-report row. Unlike BIDV's Layer 1
# financial-STATEMENT filings (confirmed elsewhere in this project to be
# scan-only, needing the OCR fallback), this specific annual report PDF —
# found via its own investors page — is a real, extractable text layer.
# Updated 2026-09-03 to the FY2025 edition (user-supplied real page URL:
# bidv.com.vn/bidv_en/quan-he-nha-dau-tu/bao-cao-va-tai-lieu/annualreport/
# 2026/bctn+2025 — the 2024 edition originally used here was only what a
# first web search surfaced, not confirmed to be the newest available;
# checking for a fresher one wasn't done consistently across all 5 banks
# the first time). Confirmed live: 95 pages, 402K chars, 94/95 non-empty.
# This year's report restructured — no standalone "Digital Banking
# operations" section exists anymore (last year's did); technology
# content is now woven into the Management's Report chapter instead.
# Scoped to the Chairman's message (PDF pages 4-5) and 4 pages of the
# Management's Report chapter (PDF pages 44, 46, 49-50 — the Board's
# operational assessment, its assessment of Board of Management
# activities, an executive-management assessment that includes real IT-
# operations detail, and the 2026 business orientation) — excluding the
# much larger BIDV-overview/governance/risk and subsidiaries/investments
# chapters. ~48K real chars, ~4-5 chunks.
BIDV_ANNUAL_REPORT_URL = "https://bidv.com.vn/wps/wcm/connect/f6519b5f-3abf-4694-a32c-d3057f8d75bc/BIDV_BCTN_2025_EN_%28Interactive%29.pdf?MOD=AJPERES&CACHEID=ROOTWORKSPACE-f6519b5f-3abf-4694-a32c-d3057f8d75bc-pYsQuS-"
BIDV_ANNUAL_REPORT_PAGE_RANGES = [(4, 5), (44, 44), (46, 46), (49, 50)]  # 0-indexed, inclusive


@register_fetcher(BIDV_ANNUAL_REPORT_URL, "parts")
async def _fetch_bidv_annual_report_parts() -> Tuple[str, List[Tuple[str, str]]]:
    return await _fetch_annual_report_page_ranges(
        BIDV_ANNUAL_REPORT_URL, BIDV_ANNUAL_REPORT_PAGE_RANGES, "BIDV"
    )
