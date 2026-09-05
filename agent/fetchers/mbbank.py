import logging
from typing import List, Tuple
from urllib.parse import urljoin

from agent.crawler import (
    _fetch_annual_report_page_ranges,
    _fetch_pdf_text,
    _fetch_vietstock_statement_text,
    _domain,
    _throttle,
)
from agent.fetcher_registry import register_fetcher

from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig
from crawl4ai.processors.pdf import PDFCrawlerStrategy

logger = logging.getLogger(__name__)

# MBBank's own site (mbbank.com.vn, bare domain) is Akamai-blocked
# comprehensively — every path returns the identical near-empty block,
# confirmed live and already documented for Layer 1. But the "www."
# subdomain is NOT behind the same wall (confirmed live, 2026-09-01) —
# this isn't evasion, just a different, legitimately-reachable subdomain
# the bank itself owns and publishes on. Both pages below are Angular-
# templated and need JS rendering, but a plain CSS `wait_for` (the
# SITE_CONFIGS mechanism everywhere else in this file) proved unreliable
# here: confirmed live it matched after only 1 of 7 real links had
# rendered on one run, 4 of 7 on another — a race, not a fluke. A
# JS-predicate wait (poll until a real link count threshold is met, not
# just "one exists") is reliable instead, which is why these two sources
# use bespoke fetch functions rather than a SITE_CONFIGS entry (the
# generic `_fetch_html`/SITE_CONFIGS path only supports `css:` waits).
MBBANK_FEE_URL = "https://www.mbbank.com.vn/Fee"
MBBANK_FEE_WAIT_JS = "js:() => document.querySelectorAll(\"a[href*='.pdf']\").length > 10"
# #rate-info4 is "BIỂU PHÍ DỊCH VỤ ÁP DỤNG ĐỐI VỚI KHCN & KHÁCH HÀNG HỘ
# KINH DOANH" (individual + business-household customers) — one of ~10
# numbered sections on this page (KHCN, SME, CIB, FI, cards, app, etc.);
# picked as the single most broadly-relevant section rather than fetching
# all of them, matching the light-effort call for this pass. Confirmed
# live: a genuine, current, itemized fee table (account/deposit/treasury
# fees with real VND amounts).
MBBANK_FEE_CONTENT_SELECTOR = "#rate-info4"
MBBANK_FEE_PDF_SELECTOR = "a[href*='.pdf']"

MBBANK_NEWS_URL = "https://www.mbbank.com.vn/news/tin-tuc"
# Scoping the wait condition to the container itself (not just "does a
# matching link exist anywhere on the page") was necessary — confirmed
# live that a page-wide wait condition raced with this container's own
# content still being empty (3 separate runs: 1 of 7 links wide, then 4 of
# 7, then the container itself came back with 0 chars despite the
# page-wide condition passing). Scoped to the container, 3/3 runs reliable.
MBBANK_NEWS_WAIT_JS = "js:() => document.querySelectorAll(\".col-sm-9 a[href*='/chi-tiet/']\").length > 3"
MBBANK_NEWS_CONTENT_SELECTOR = ".col-sm-9"


async def _fetch_mbbank_fee_text() -> str:
    _throttle(_domain(MBBANK_FEE_URL))
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url=MBBANK_FEE_URL,
            config=CrawlerRunConfig(cache_mode=CacheMode.BYPASS, wait_for=MBBANK_FEE_WAIT_JS, page_timeout=30000),
        )
        if not result.success:
            raise RuntimeError(f"Failed to fetch MBBank fee page: {result.error_message}")

        soup = BeautifulSoup(result.html, "lxml")
        node = soup.select_one(MBBANK_FEE_CONTENT_SELECTOR)
        if node is None:
            raise ValueError("MBBank fee page's expected content section not found")

        links = [a for a in node.select(MBBANK_FEE_PDF_SELECTOR) if a.get("href")][:1]
        if not links:
            raise ValueError("No fee-schedule PDF link found in MBBank's fee section")
        pdf_url = urljoin(MBBANK_FEE_URL, links[0]["href"])
        list_text = node.get_text(separator="\n", strip=True)

    async with AsyncWebCrawler(crawler_strategy=PDFCrawlerStrategy()) as crawler:
        pdf_text = await _fetch_pdf_text(crawler, pdf_url)
    return f"{list_text}\n\n--- {pdf_url} ---\n{pdf_text}"


@register_fetcher(MBBANK_FEE_URL, "single")
async def _fetch_mbbank_fee() -> Tuple[str, List[Tuple[str, str]]]:
    return await _fetch_mbbank_fee_text(), []


# Fixed 2026-09-03 (user review: "you did not click inside the actual
# article right?" — confirmed: it didn't). The listing's own teaser text
# per item is real, not just a bare title (unlike iav_bancassurance's
# pre-fix case) — its own WAIT_JS condition already scopes to
# "a[href*='/chi-tiet/']", meaning the article-detail links were known to
# exist and simply never followed. Confirmed live: an article detail page
# fetched with no JS wait comes back as a "Nội dung này không tồn tại!"
# (content doesn't exist) placeholder shell — these pages need their own
# render wait, not just the listing's. A JS-predicate wait condition
# wasn't needed here (unlike the listing) — delay_before_return_html=3.0
# was confirmed live to reliably let the real article text (real numbers:
# visitor counts, attendance figures) render in. .mb-news-details-content
# scopes past the site-wide nav/footer chrome to just the article body.
MBBANK_NEWS_ARTICLE_SELECTOR = ".mb-news-details-content"
MBBANK_NEWS_ARTICLE_LIMIT = 3


@register_fetcher(MBBANK_NEWS_URL, "parts")
async def _fetch_mbbank_news_parts() -> Tuple[str, List[Tuple[str, str]]]:
    _throttle(_domain(MBBANK_NEWS_URL))
    async with AsyncWebCrawler() as crawler:
        listing = await crawler.arun(
            url=MBBANK_NEWS_URL,
            config=CrawlerRunConfig(cache_mode=CacheMode.BYPASS, wait_for=MBBANK_NEWS_WAIT_JS, page_timeout=30000),
        )
        if not listing.success:
            raise RuntimeError(f"Failed to fetch MBBank news page: {listing.error_message}")

        soup = BeautifulSoup(listing.html, "lxml")
        list_node = soup.select_one(MBBANK_NEWS_CONTENT_SELECTOR)
        list_text = list_node.get_text(separator="\n", strip=True) if list_node else ""

        seen = set()
        article_urls: List[str] = []
        for a in (list_node.select("a[href*='/chi-tiet/']") if list_node else []):
            href = a.get("href")
            if not href:
                continue
            article_url = urljoin(MBBANK_NEWS_URL, href)
            if article_url in seen:
                continue
            seen.add(article_url)
            article_urls.append(article_url)
            if len(article_urls) >= MBBANK_NEWS_ARTICLE_LIMIT:
                break

        documents: List[Tuple[str, str]] = []
        for article_url in article_urls:
            _throttle(_domain(article_url))
            article = await crawler.arun(
                url=article_url,
                config=CrawlerRunConfig(cache_mode=CacheMode.BYPASS, page_timeout=30000, delay_before_return_html=3.0),
            )
            if not article.success:
                logger.info("Failed to fetch MBBank article %s, skipping", article_url)
                continue
            article_soup = BeautifulSoup(article.html, "lxml")
            article_node = article_soup.select_one(MBBANK_NEWS_ARTICLE_SELECTOR)
            text = article_node.get_text(separator="\n", strip=True) if article_node else ""
            if len(text) < 50:
                logger.info("Near-empty MBBank article %s, skipping", article_url)
                continue
            documents.append((article_url, text))

    return list_text, documents


# Fourth of the 5-bank Layer 3 annual-report row. Updated 2026-09-03 to
# the FY2025 edition (user-supplied real page URL:
# mbbank.com.vn/chi-tiet/thong-bao/bao-cao-thuong-nien-2025-... — found
# via that page's own JS-rendered PDF link, not a direct static fetch;
# the earlier 2024 edition used here came from Vietstock's aggregator
# since MBBank's own domain was known Akamai-walled, but this specific
# announcement-detail page turned out reachable directly on
# mbbank.com.vn itself, matching the "www subdomain vs. bare domain"
# pattern already established for this bank's other sources). This
# edition is Vietnamese-only — no English variant found on the same
# page — the LLM handles Vietnamese content natively throughout this
# pipeline, so no issue. Confirmed live: 186 pages, 738K chars, 184/186
# non-empty. Real chapter boundaries found the same way (direct text
# search on the Vietnamese section titles). Scoped to the Chairman/CEO
# messages (PDF pages 4-5), the real "Chiến lược và định hướng phát
# triển" / Strategy and development orientation section (PDF pages
# 17-19), and "Tình hình đầu tư và thực hiện các dự án" / Project
# investment and implementation (PDF page 39 — real content on MB's
# 2,500+ IT staff and RPA/AI/Machine Learning/OCR applications, directly
# matching this source's "technology disclosures" target) — excluding
# the much larger general-information/governance/risk-management and
# financial-performance chapters. ~29K real chars, ~3 chunks.
MBBANK_ANNUAL_REPORT_URL = "https://www.mbbank.com.vn/resources/files/NhaDauTu/2026/DHCD-2026/20260330---mbb---bao-cao-thuong-nien-2025.pdf"
MBBANK_ANNUAL_REPORT_PAGE_RANGES = [(4, 5), (17, 19), (39, 39)]  # 0-indexed, inclusive


@register_fetcher(MBBANK_ANNUAL_REPORT_URL, "parts")
async def _fetch_mbbank_annual_report_parts() -> Tuple[str, List[Tuple[str, str]]]:
    return await _fetch_annual_report_page_ranges(
        MBBANK_ANNUAL_REPORT_URL, MBBANK_ANNUAL_REPORT_PAGE_RANGES, "MBBank"
    )


# Banks whose own IR site is unreachable (Akamai-blocked — see
# agent/sources.py's Layer 1 comment) but whose filed statement happens to
# have a real text layer on Vietstock's static CDN (see
# agent.crawler._fetch_vietstock_statement_text). Keyed by the bank's own
# *specific* financial-statement URL (used as the source's citation URL in
# agent/sources.py), not the domain as a whole — a domain-wide key would
# hijack every other page on that domain, not just this one. Confirmed live
# (2026-09-01, building Layer 2): fetching mbbank.com.vn's sitemap.xml
# through a domain-keyed check returned MBB's financial statement instead
# of the sitemap.
MBBANK_FINANCIAL_STATEMENTS_URL = "https://mbbank.com.vn/Investor/thong-bao-nha-dau-tu"


@register_fetcher(MBBANK_FINANCIAL_STATEMENTS_URL, "single")
async def _fetch_mbbank_financial_statements() -> Tuple[str, List[Tuple[str, str]]]:
    text, pdf_url = await _fetch_vietstock_statement_text("MBB")
    return text, [(pdf_url, text)]
