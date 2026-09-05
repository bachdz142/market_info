import tempfile
from pathlib import Path
from typing import List, Tuple
import urllib.request

from agent.crawler import _domain, _throttle
from agent.fetcher_registry import register_fetcher

from crawl4ai.processors.pdf.processor import NaivePDFProcessorStrategy

# SSI's own sector-reports listing page (khach-hang-ca-nhan/bao-cao-nganh)
# never exposes real per-report links even after a JS wait — its report
# rows aren't real <a> elements in the rendered DOM, confirmed live across
# multiple attempts. This is a single hand-verified PDF instead (same
# "explicit URL, not a scraper" approach as VCB_FEE_PDF_URLS), found via
# web search rather than the listing page. Its own host (ftp2.ssi.com.vn)
# 403s crawl4ai's PDFCrawlerStrategy specifically — a crawl4ai-side quirk,
# not a real site block: confirmed live that plain curl with no special
# headers gets a clean 200 on the same URL. Fetched via urllib directly
# instead, then handed to crawl4ai's own PDF text extractor
# (NaivePDFProcessorStrategy) so no new PDF-parsing dependency is
# introduced. Event-driven per source_plan_mvp0.md §5 — needs periodic
# manual re-discovery when a newer sector report is published, same as
# every other hand-verified URL list in this file.
SSI_BANKING_SECTOR_REPORT_URL = (
    "https://ftp2.ssi.com.vn/Customers/GDDT/Analyst_Report/Sector%20Report/"
    "Cap%20nhat%20nganh%20Ngan%20hang_Thong%20tu%2022_2026.05.05_SSIResearch.pdf"
)


async def _fetch_ssi_report_text(url: str) -> str:
    _throttle(_domain(url))
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(data)
        path = Path(f.name)

    try:
        # extract_images=False: only page.markdown is read below, so the
        # default image-decoding pass (per-page /XObject extraction +
        # base64 encoding) would just be wasted CPU/memory on a multi-page
        # PDF for no functional benefit.
        result = NaivePDFProcessorStrategy(extract_images=False).process_batch(path)
        return "\n".join(page.markdown for page in result.pages)
    finally:
        path.unlink(missing_ok=True)


@register_fetcher(SSI_BANKING_SECTOR_REPORT_URL, "single")
async def _fetch_ssi_banking_sector_report() -> Tuple[str, List[Tuple[str, str]]]:
    return await _fetch_ssi_report_text(SSI_BANKING_SECTOR_REPORT_URL), []
