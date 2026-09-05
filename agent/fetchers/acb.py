# ACB's custom fetchers — financial statements, promotions, fee schedule,
# and annual report. Grouped in one file since they share ACB's own
# AJAX-API discovery pattern (see each URL's own comment below) and the
# PDF-page-range annual-report helper.
import json
import logging
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
from crawl4ai.async_crawler_strategy import AsyncHTTPCrawlerStrategy
from crawl4ai.processors.pdf import PDFCrawlerStrategy

logger = logging.getLogger(__name__)

# ACB's financial-statements page has no PDF links anywhere in its
# rendered DOM at all — the "Download" controls are plain <div>/<span>
# elements with no href and no inline onclick; the actual URL only exists
# after a JS click handler fires. Confirmed live (network capture of a
# simulated click) that the click just calls this same public, unauthenticated
# JSON API the page itself loads on render — going straight to the API is
# simpler and more stable than click-simulation + network-response capture.
# category_id=1656 is "Financial Statements 2026"; results are newest-first.
ACB_DOCUMENTS_API = (
    "https://acb.com.vn/api/en/front/v1/posts"
    "?search[categories.category_id:in]=1656&search[is_active:in]=1&page=1&limit=20"
)

# _crawl_async keys this special-cased fetch to this *specific* URL, not
# acb.com.vn as a whole — a domain-wide check would hijack every other page
# on the domain, not just Layer 1's financial-statements page. Confirmed
# live (2026-09-01, building Layer 2) that this was a real bug: fetching
# acb.com.vn's sitemap.xml through a domain-keyed check returned ACB's
# financial statement instead of the sitemap.
ACB_FINANCIAL_STATEMENTS_URL = "https://acb.com.vn/en/investors/financial-statements"


async def _fetch_acb_statement_text() -> str:
    _throttle(_domain(ACB_DOCUMENTS_API))
    async with AsyncWebCrawler(crawler_strategy=AsyncHTTPCrawlerStrategy()) as crawler:
        result = await crawler.arun(url=ACB_DOCUMENTS_API, config=CrawlerRunConfig(cache_mode=CacheMode.BYPASS))
    if not result.success:
        raise RuntimeError(f"Failed to fetch ACB documents API: {result.error_message}")

    posts = json.loads(result.html).get("data", [])
    # Picks the newest consolidated ("hợp nhất") statement in its
    # searchable (OCR'd, extractable-text) form — the "signed" twin is a
    # scanned image with no usable text layer, same reasoning as
    # Techcombank's SITE_CONFIGS entry.
    match = next(
        (
            post for post in posts
            if "consolidated" in post.get("title", "").lower()
            and "searchable" in (post.get("featured_image") or {}).get("filename", "").lower()
        ),
        None,
    )
    if not match:
        raise ValueError("No consolidated searchable statement found in ACB's documents API response")

    pdf_url = match["featured_image"]["path"]
    logger.info("Fetching ACB PDF -> %s", pdf_url)
    async with AsyncWebCrawler(crawler_strategy=PDFCrawlerStrategy()) as crawler:
        return await _fetch_pdf_text(crawler, pdf_url)


@register_fetcher(ACB_FINANCIAL_STATEMENTS_URL, "single")
async def _fetch_acb_financial_statements() -> Tuple[str, List[Tuple[str, str]]]:
    return await _fetch_acb_statement_text(), []


# ACB's /en/promotions page (Layer 2) has the exact same problem as its
# financial-statements page: the rendered listing widget explicitly shows
# "No products" — the real content loads via API calls the static/JS fetch
# never captures. Confirmed live (2026-09-01) via real Playwright network
# capture (not a guess): the page calls
# /api/en/front/v1/map/categories?type=uu-dai (a category index, not used
# here) and /api/en/front/v1/map/posts?type=uu-dai (the real promo-post id
# list). Two-step fetch, unlike the single-call financial-statements case:
# the list endpoint only returns id/slug, and the English-locale detail
# endpoint (/api/en/front/v1/posts/{id}) returns null title/description for
# these Vietnamese-locale posts — the real content only comes back from the
# /api/vi/... detail endpoint, matching each post's own "locale": "vi" field.
ACB_PROMOTIONS_URL = "https://acb.com.vn/en/promotions"
ACB_PROMOTIONS_LIST_API = "https://acb.com.vn/api/en/front/v1/map/posts?type=uu-dai&limit=20"
ACB_PROMOTIONS_DETAIL_API = "https://acb.com.vn/api/vi/front/v1/posts/{post_id}"
# The detail API's own "short_description"/"long_description" fields are a
# stub (long_description is null on every real promo checked; the ~70-char
# short_description is just a listing teaser) — confirmed live (2026-09-03,
# user-flagged: "you also didn't click actual promotion detail"). The real
# terms/conditions body only exists on the public, server-rendered detail
# page (https://acb.com.vn/vi/uu-dai/{slug}, a Next.js SSR page — no JS
# wait needed, same AsyncHTTPCrawlerStrategy as the API calls). Confirmed
# live across all 8 promos: real body text scoped to the parent of the
# page's first `id="block-id-N"` element (offer terms + validity window +
# contact info, no nav/footer), 358-14758 chars vs. ~70 chars before.
ACB_PROMOTIONS_DETAIL_PAGE = "https://acb.com.vn/vi/uu-dai/{slug}"
# Keeps the eventual structuring call reasonably sized — the list endpoint
# doesn't expose dates to sort by, so this just takes the first N as given.
ACB_PROMOTIONS_LIMIT = 8


async def _fetch_acb_promotions_text() -> str:
    _throttle(_domain(ACB_PROMOTIONS_LIST_API))
    async with AsyncWebCrawler(crawler_strategy=AsyncHTTPCrawlerStrategy()) as crawler:
        result = await crawler.arun(url=ACB_PROMOTIONS_LIST_API, config=CrawlerRunConfig(cache_mode=CacheMode.BYPASS))
        if not result.success:
            raise RuntimeError(f"Failed to fetch ACB promotions list: {result.error_message}")

        items = json.loads(result.html).get("data", [])[:ACB_PROMOTIONS_LIMIT]
        parts = []
        for item in items:
            detail_url = ACB_PROMOTIONS_DETAIL_API.format(post_id=item["id"])
            _throttle(_domain(detail_url))
            detail_result = await crawler.arun(url=detail_url, config=CrawlerRunConfig(cache_mode=CacheMode.BYPASS))
            if not detail_result.success:
                logger.info("Failed to fetch ACB promotion detail %s, skipping", detail_url)
                continue
            data = json.loads(detail_result.html).get("data", {})
            title = data.get("title") or ""
            slug = data.get("slug") or ""
            if not title:
                continue
            start = data.get("published_start") or ""
            end = data.get("published_end") or ""

            body = data.get("short_description") or ""
            if slug:
                page_url = ACB_PROMOTIONS_DETAIL_PAGE.format(slug=slug)
                _throttle(_domain(page_url))
                page_result = await crawler.arun(url=page_url, config=CrawlerRunConfig(cache_mode=CacheMode.BYPASS))
                if page_result.success:
                    soup = BeautifulSoup(page_result.html, "lxml")
                    first_block = soup.find(id=lambda x: x and x.startswith("block-id-"))
                    if first_block is not None:
                        block_text = first_block.parent.get_text(" ", strip=True)
                        if block_text and len(block_text) > len(body):
                            body = block_text
                else:
                    logger.info("Failed to fetch ACB promotion detail page %s, using short_description", page_url)

            parts.append(f"{title}\n{body}\nValid: {start} to {end}")

    if not parts:
        raise ValueError("No ACB promotions found with real content")
    return "\n\n".join(parts)


@register_fetcher(ACB_PROMOTIONS_URL, "single")
async def _fetch_acb_promotions() -> Tuple[str, List[Tuple[str, str]]]:
    return await _fetch_acb_promotions_text(), []


# ACB's fee-schedule page (Layer 2, /en/forms-and-fee-schedules-for-
# individual-customers) has the same AJAX-gap as its promotions page above
# — confirmed live it needed its own separate network capture, since the
# API pattern that worked for promotions (map/posts?type=uu-dai) doesn't
# apply here. The real call found: the standard "posts" endpoint filtered
# by search[type:like]=bieu-mau-bieu-phi (no category_id needed — dropping
# it returns all 60 fee/form documents across every category in one call).
# Category 631 ("Summary of fee schedule") holds the actual consolidated
# fee-schedule documents (11 of them, one per product line — cards,
# accounts, cash transactions, etc.). Same two-locale quirk as promotions:
# the English-locale detail endpoint has featured_image: null; the real PDF
# only shows up via the Vietnamese-locale detail endpoint. Confirmed live:
# a genuine, current, segmented fee table (Visa Infinite Privilege through
# ACB Express card tiers). Picks whichever product line was most recently
# updated rather than hardcoding one, so this stays current as ACB updates
# different fee schedules over time.
ACB_FEE_SCHEDULE_URL = "https://acb.com.vn/en/forms-and-fee-schedules-for-individual-customers"
ACB_FEE_LIST_API = (
    "https://acb.com.vn/api/en/front/v1/posts"
    "?limit=all&search[type:like]=bieu-mau-bieu-phi&search[categories.category_id:in]=631"
)
ACB_FEE_DETAIL_VI_API = "https://acb.com.vn/api/vi/front/v1/posts/{post_id}"


async def _fetch_acb_fee_schedule_text() -> str:
    _throttle(_domain(ACB_FEE_LIST_API))
    async with AsyncWebCrawler(crawler_strategy=AsyncHTTPCrawlerStrategy()) as crawler:
        result = await crawler.arun(url=ACB_FEE_LIST_API, config=CrawlerRunConfig(cache_mode=CacheMode.BYPASS))
        if not result.success:
            raise RuntimeError(f"Failed to fetch ACB fee-schedule list: {result.error_message}")

        posts = json.loads(result.html).get("data", [])
        posts.sort(key=lambda p: p.get("updated_at") or "", reverse=True)
        if not posts:
            raise ValueError("No ACB fee-schedule posts found")

        detail_url = ACB_FEE_DETAIL_VI_API.format(post_id=posts[0]["id"])
        _throttle(_domain(detail_url))
        detail_result = await crawler.arun(url=detail_url, config=CrawlerRunConfig(cache_mode=CacheMode.BYPASS))
        if not detail_result.success:
            raise RuntimeError(f"Failed to fetch ACB fee-schedule detail: {detail_result.error_message}")

        data = json.loads(detail_result.html).get("data", {})
        pdf_url = (data.get("featured_image") or {}).get("path")
        if not pdf_url:
            raise ValueError("ACB's most-recently-updated fee-schedule post has no attached PDF")

    async with AsyncWebCrawler(crawler_strategy=PDFCrawlerStrategy()) as crawler:
        return await _fetch_pdf_text(crawler, pdf_url)


@register_fetcher(ACB_FEE_SCHEDULE_URL, "single")
async def _fetch_acb_fee_schedule() -> Tuple[str, List[Tuple[str, str]]]:
    return await _fetch_acb_fee_schedule_text(), []


# Fifth and last of the 5-bank Layer 3 annual-report row. ACB's own
# investors page (acb.com.vn/en/investors/annual-report-2024) is
# client-side API-rendered like its other Layer 1/2 pages and didn't
# surface a direct PDF link on a plain fetch — used Vietstock's static
# document CDN instead (same aggregator convention as MBBank above).
# Confirmed live: 89 pages, 157K chars, 88/89 non-empty — a real text
# layer, filed 24 March 2025 covering fiscal year 2024 (the "2025" in
# the filename is the filing/disclosure year, not the fiscal year covered
# — same convention as MBBank's own "20250423"-dated 2024 report).
# Real section boundaries found the same way (direct text search): no
# dedicated Technology chapter exists here either (this report's own
# extraction is noisier than the other 4 banks' — visible OCR/ligature
# artifacts like "l.l" for "1.1" — but still real, readable text).
# Scoped to the Chairman's Message (PDF pages 6-7), the "1.4 Development
# strategy" section (PDF pages 16-17 — 2025 financial targets plus an
# explicit "significant change in digital transformation" commitment),
# and the Board of Directors' 2025 business-plans/vision section (PDF
# pages 51-52 — includes a "boosting the digitization process" and
# "continue the digitalization of banking services" commitment) —
# excluding the much larger general-information/governance/risk,
# business-performance, and financial-statements chapters. ~13K real
# chars, ~1-2 chunks — the smallest of the 5 banks' selections, since
# ACB's report doesn't dedicate as much space to technology specifics as
# Techcombank/BIDV/MBBank's reports do.
ACB_ANNUAL_REPORT_URL = "https://static2.vietstock.vn/vietstock/2025/3/26/20250325_acb_250325_annual_report_2025.pdf"
ACB_ANNUAL_REPORT_PAGE_RANGES = [(6, 7), (16, 17), (51, 52)]  # 0-indexed, inclusive


@register_fetcher(ACB_ANNUAL_REPORT_URL, "parts")
async def _fetch_acb_annual_report_parts() -> Tuple[str, List[Tuple[str, str]]]:
    return await _fetch_annual_report_page_ranges(
        ACB_ANNUAL_REPORT_URL, ACB_ANNUAL_REPORT_PAGE_RANGES, "ACB"
    )
