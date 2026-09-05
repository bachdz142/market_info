from typing import List, Tuple

from agent.fetcher_registry import register_fetcher

from crawl4ai import AsyncWebCrawler
from crawl4ai.processors.pdf import PDFCrawlerStrategy

from agent.crawler import _fetch_pdf_text

# VCBS's report list only resolves after clicking its "Báo cáo ngành" tab,
# and its individual report cards have no real href in the static/JS-
# rendered DOM (see agent/sources.py's Tier 2 comment for the discovery
# story: a genuine, trusted Playwright click was needed to find this,
# since a plain synthetic .click() did nothing). Once clicked, this
# specific direct storage URL was confirmed live — real, current (2026)
# content, no login/captcha gate on the file itself (a login-gated detail
# page was a red herring from one earlier click landing on a different
# navigation path, not a real access restriction on this report).
VCBS_BANKING_SECTOR_REPORT_URL = (
    "https://www.vcbs.com.vn/storage/ttpt_reports/20260109/bao-cao-nganh-ngan-hang-2026.pdf"
)


async def _fetch_vcbs_report_text(url: str) -> str:
    async with AsyncWebCrawler(crawler_strategy=PDFCrawlerStrategy()) as crawler:
        return await _fetch_pdf_text(crawler, url)


@register_fetcher(VCBS_BANKING_SECTOR_REPORT_URL, "single")
async def _fetch_vcbs_banking_sector_report() -> Tuple[str, List[Tuple[str, str]]]:
    return await _fetch_vcbs_report_text(VCBS_BANKING_SECTOR_REPORT_URL), []
