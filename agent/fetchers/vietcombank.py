import logging
import re
import urllib.request
from typing import List, Tuple

from agent.crawler import (
    _fetch_annual_report_page_ranges,
    _fetch_pdf_text,
    _domain,
    _throttle,
)
from agent.fetcher_registry import register_fetcher

from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig
from crawl4ai.processors.pdf import PDFCrawlerStrategy

logger = logging.getLogger(__name__)

# Vietcombank's promotions listing page is a different kind of problem than
# ACB/VPBank's AJAX-gap: its homepage showed *zero* fetch/XHR calls under
# JS-injection capture (confirmed live, 2026-09-01) — this site is mostly
# server-rendered, not a client-side SPA, so the listing's real links are
# most likely populated via a WebCenter/Liferay-style portlet postback, not
# a plain client-side call this technique can see. But individual promo
# article pages ARE real and fully extractable (confirmed live: detailed,
# dated promo terms with real VND figures) — the sitemap is the discovery
# mechanism instead of the listing page, using its real <lastmod> dates to
# pick the most recent few. crawl4ai's own fetch fails on this specific
# sitemap's XML encoding declaration ("Unicode strings with encoding
# declaration are not supported"); raw urllib works fine and is used only
# for this one bootstrap step — every actual promo page fetch still goes
# through crawl4ai normally.
VCB_PROMOTIONS_URL = "https://www.vietcombank.com.vn/KHCN/Truy-cap-nhanh/KHCN---Danh-sach-uu-dai"
VCB_SITEMAP_URL = "https://www.vietcombank.com.vn/sitemap.xml"
VCB_PROMOTIONS_LIMIT = 3
VCB_PROMOTION_RE = re.compile(
    r"<url>\s*<loc>(https?://www\.vietcombank\.com\.vn/KHCN/Truy-cap-nhanh/KHCN---Danh-sach-uu-dai/[^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>"
)


def _vcb_promotion_urls() -> List[str]:
    req = urllib.request.Request(VCB_SITEMAP_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    pairs = VCB_PROMOTION_RE.findall(raw)
    pairs.sort(key=lambda pair: pair[1], reverse=True)
    # The sitemap lists these as plain http:// — confirmed live that
    # fetching over http specifically (not https) trips a genuine
    # net::ERR_HTTP2_PROTOCOL_ERROR against this domain, so normalize to
    # https first.
    return [url.replace("http://", "https://", 1) for url, _ in pairs[:VCB_PROMOTIONS_LIMIT]]


async def _fetch_vcb_promotions_text() -> str:
    urls = _vcb_promotion_urls()
    if not urls:
        raise ValueError("No VCB promotion URLs found in sitemap")

    parts = []
    async with AsyncWebCrawler() as crawler:
        for url in urls:
            _throttle(_domain(url))
            result = await crawler.arun(url=url, config=CrawlerRunConfig(cache_mode=CacheMode.BYPASS))
            if not result.success:
                logger.info("Failed to fetch VCB promotion %s, skipping", url)
                continue
            soup = BeautifulSoup(result.html, "lxml")
            node = soup.select_one(".promotion-detail__container")
            text = node.get_text(separator="\n", strip=True) if node else (result.markdown or "")
            if text:
                parts.append(f"--- {url} ---\n{text}")

    if not parts:
        raise ValueError("No VCB promotions had usable content")
    return "\n\n".join(parts)


@register_fetcher(VCB_PROMOTIONS_URL, "single")
async def _fetch_vcb_promotions() -> Tuple[str, List[Tuple[str, str]]]:
    return await _fetch_vcb_promotions_text(), []


# VCB's fee-schedule page was originally judged "needs OCR, not a crawling
# problem" after seeing a banner image and no fee data in one fetch — that
# conclusion turned out to be wrong. The real cause: this page's fee
# accordion is server-side rendered, and VCB's own server/CDN
# non-deterministically returns either a fully-rendered version or a
# near-empty shell (the same class of caching race already documented for
# bidv.com.vn) — but that's not the whole story. A real dynamic-scraping
# attempt was built and then abandoned after finding a genuine data-
# integrity bug, not just a flakiness problem: confirmed live (2026-09-01,
# via user-reported category counts that didn't match the scrape, then
# verified directly) that VCB's 3 transfer-type categories (international,
# domestic, remittance) all render with the SAME "Biểu phí" content in the
# initial HTML — the same 2 international-transfer PDFs under all three
# category headings, not each category's own real documents. This is the
# same failure shape as BIDV's Layer 1 bug #6 (same document set repeated
# under every tab), except here scraping "whichever category's heading you
# find" would silently mislabel international-transfer fees as domestic-
# transfer or remittance fees — a real correctness risk, not just noise.
# Each category's genuine distinct content only becomes available after an
# actual user click (a real client-side state change) — confirmed by
# ACB-style network capture of a real Playwright click, which surfaced
# VCB's actual document-search API (Sitecore's
# "sxa/FileDocumentApi/FileDocumentResults") and each category's own real
# PDFs. Domestic transfer's own fee PDF (BP-dich-vu-chuyen-tien-trong-
# nuoc.pdf) turned out to have identical figures to the one a user had
# separately found on the live page and provided directly (a Vietnamese/
# English twin of the same document, not a second document) — so only one
# is kept. Remittance's category was also click-verified directly: its
# accordion panel has only a "Biểu mẫu" (forms) heading — a withdrawal
# slip, a MoneyGram receive form — and genuinely no "Biểu phí" (fee
# schedule) section at all, consistent with VCB not charging a fee to
# *receive* a remittance. So this list is complete, not a partial result:
# international transfer's 2 real PDFs, domestic transfer's 1 real PDF,
# and no PDF for remittance because none exists.
VCB_FEE_URL = "https://www.vietcombank.com.vn/vi-VN/KHCN/Cong-cu-Tien-ich/KHCN---Bieu-mau-va-bieu-phi"
VCB_FEE_PDF_URLS = [
    "https://www.vietcombank.com.vn/-/media/Project/VCB-Sites/VCB/KHCN/Bieu-mau-Bieu-phi-KHCN/Update-30062026/BP-dich-vu-chuyen-tien-nuoc-ngoai.pdf",
    "https://www.vietcombank.com.vn/-/media/Project/VCB-Sites/VCB/KHCN/Bieu-mau-Bieu-phi-KHCN/Bieu-phi/Chuyen-tien/Chuyen-tien-nuoc-ngoai/Bieu-phi-DICH-VU-CHUYEN-TIEN-DI-nuoc-ngoai-VCB-DIGIBANK.pdf",
    "https://www.vietcombank.com.vn/-/media/Project/VCB-Sites/VCB/KHCN/Bieu-mau-Bieu-phi-KHCN/Update-30062026/Domestic-remittance-service-fee-schedule-for-individual-customer.pdf",
]


@register_fetcher(VCB_FEE_URL, "parts")
async def _fetch_vcb_fee_parts() -> Tuple[str, List[Tuple[str, str]]]:
    documents = []
    async with AsyncWebCrawler(crawler_strategy=PDFCrawlerStrategy()) as crawler:
        for pdf_url in VCB_FEE_PDF_URLS:
            _throttle(_domain(pdf_url))
            try:
                text = await _fetch_pdf_text(crawler, pdf_url)
            except Exception:
                logger.exception("Failed to fetch VCB fee PDF %s, skipping", pdf_url)
                continue
            documents.append((pdf_url, text))

    if not documents:
        raise ValueError("No VCB fee-schedule PDFs had usable content")
    return "", documents


# Vietcombank's own domain has a genuine, confirmed Akamai wall for Layer 1
# quantitative filings (source_plan_mvp0.md §8 — routed to manual ingestion,
# not attempted here either) — but the FY2024 PDF originally used here was
# served from the same www.vietcombank.com.vn media path already proven
# for VCB's Layer 2 fee-schedule/promotions sources, reachable directly.
#
# Updated 2026-09-03 to the FY2025 edition. The first check for a newer
# edition (a guessed 2025-dated URL at the same www.vietcombank.com.vn
# path — a fake-200 HTML error page, not a real PDF) was a lazy filename
# guess, not a real search — a user follow-up ("bruh vcb is 2024???",
# after the same gap had already been caught for BIDV/MBBank) prompted
# doing this properly: found via a real Vietstock disclosure-filing
# article (vietstock.vn's own site needs a browser User-Agent — a plain
# `requests` GET with no headers gets a 403), not vietcombank.com.vn
# itself. Confirmed live: 113 pages, 419K chars, 111/113 non-empty — a
# real text layer, Vietnamese-only (no English variant found at this
# path — same non-issue as MBBank's Vietnamese-only FY2025 edition).
#
# No dedicated "Technology" chapter exists in this report's own table of
# contents (unlike Techcombank's) — real chapter boundaries found the same
# way (direct text search for each TOC entry's actual page, not the
# printed page numbers). Scoped to the Chairman/CEO leadership message
# (PDF pages 4-5) and the "Báo cáo của Hội đồng Quản trị - Ban điều hành"
# (Report of the Board of Directors - Executive Board) chapter (PDF pages
# 15-23 — investment/project situation, 2025 business-results assessment
# — including real content on the VCB CashUp Mobile / VCB Tablet digital
# products, 2026 business orientation, and the BOD's own activity
# assessment), excluding Organization/HR, Corporate Governance/Risk
# Management, Sustainable Development, and the financial-statements
# chapter. ~38K real chars, ~4 chunks.
VIETCOMBANK_ANNUAL_REPORT_URL = "https://static2.vietstock.vn/vietstock/2026/4/17/20260416___vcb___bao_cao_thuong_nien_nam_2025.pdf"
VIETCOMBANK_ANNUAL_REPORT_PAGE_RANGES = [(4, 5), (15, 23)]  # 0-indexed, inclusive


@register_fetcher(VIETCOMBANK_ANNUAL_REPORT_URL, "parts")
async def _fetch_vietcombank_annual_report_parts() -> Tuple[str, List[Tuple[str, str]]]:
    return await _fetch_annual_report_page_ranges(
        VIETCOMBANK_ANNUAL_REPORT_URL, VIETCOMBANK_ANNUAL_REPORT_PAGE_RANGES, "Vietcombank"
    )
