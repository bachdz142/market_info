import agent.ssl_bootstrap  # noqa: F401  — must import-run before crawl4ai/aiohttp below (see that module's docstring)

import asyncio
import json
import logging
import re
import tempfile
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig
from crawl4ai.async_crawler_strategy import AsyncHTTPCrawlerStrategy
from crawl4ai.processors.pdf import PDFContentScrapingStrategy, PDFCrawlerStrategy
from crawl4ai.processors.pdf.processor import NaivePDFProcessorStrategy

logger = logging.getLogger(__name__)

# Minimum gap between any two requests to the same domain, enforced
# per-process regardless of caller (the /trigger loop's own pacing only
# covers gaps *between* topics/sources — it doesn't cover multiple
# requests within one crawl(), like a list page + its PDF, or ad-hoc
# manual calls). A real block from sbv.gov.vn (a WAF rejection page)
# happened during rapid manual testing — this is the fix.
MIN_REQUEST_INTERVAL_SECONDS = 5
_last_request_at: dict = {}


def _throttle(domain: str) -> None:
    last = _last_request_at.get(domain)
    now = time.monotonic()
    if last is not None:
        wait = MIN_REQUEST_INTERVAL_SECONDS - (now - last)
        if wait > 0:
            logger.info("Throttling request to %s, waiting %.1fs", domain, wait)
            time.sleep(wait)
    _last_request_at[domain] = time.monotonic()


# Per-site overrides for sites needing JS rendering or precise selectors.
# Most sites don't need an entry here — DEFAULT_CONFIG (crawl4ai's
# lightweight HTTP strategy + its generic markdown extraction) is tried
# first for everything.
SITE_CONFIGS = {
    "customs.gov.vn": {
        "needs_js": True,
        "wait_selector": None,
        "content_selector": None,
        "pdf_link_selector": None,
        "pdf_link_limit": 1,
    },
    # Generic extraction pulls pure nav-menu boilerplate on this domain's
    # listing pages (e.g. /en/press-release) — the real content lives in a
    # Liferay portlet, <ul class="doc-list">. Confirmed safe for the other
    # sbv.gov.vn pages too: if this selector doesn't match, content
    # selection falls through to the generic extraction.
    #
    # pdf_link_selector: the listing's own "article page" link is just a
    # viewer shell with no real content — the actual report text lives in
    # a linked PDF attachment (the "doc-icon" download link next to each
    # entry). Confirmed live: the article page itself has only UI chrome
    # (audio-player controls, category tag), the PDF has the real report.
    # pdf_link_limit: how many of the most recent entries' PDFs to fetch in
    # full (list is already newest-first). WARNING: confirmed live that 3
    # PDFs blows Groq's free-tier 8000-tokens-per-request ceiling (413
    # error), and even 2 PDFs made the model unreliable (returned plain
    # JSON instead of properly calling the required tool — likely
    # input-size-related model flakiness, not just a token-budget issue).
    # Only 1 has worked reliably across multiple real runs. Set to 3 here
    # deliberately for another test — expect it to likely fail again the
    # same way; drop back to 1 if so.
    "sbv.gov.vn": {
        "needs_js": False,
        "wait_selector": None,
        "content_selector": "ul.doc-list",
        "pdf_link_selector": "a.doc-icon",
        "pdf_link_limit": 3,
    },
    # sbv_portal_statistics's real fix (2026-09-02): the previous URL
    # (sbv.gov.vn/en/statistics) was ALWAYS pure nav/footer boilerplate —
    # confirmed live the real statistic content was never in that page's
    # text at all, not just too large to chunk (the "chunked: True" flag
    # was masking a content problem, not solving a size one). Found via
    # real hover on the Vietnamese site's own "Dữ liệu thống kê" nav item
    # (not the English one, which has no equivalent dropdown): this URL is
    # one of ~199 monthly/quarterly system-wide banking statistics reports
    # under "Hoạt động của hệ thống các TCTD" (basic indicators — total
    # assets, charter capital, short-term-funds-for-long-term-lending
    # ratio, loan-to-deposit ratio, per institution type). Client-side
    # rendered (needs_js) — the real data lives in the page's first
    # <article> element; a second <article> right after it is just a
    # "related reports" list (CAR, ROA/ROE, other months) — bare `article`
    # as a selector picks the first one only (BeautifulSoup's
    # select_one()), which is the one with real data. Confirmed live:
    # 2,286 chars once scoped — small enough that this no longer needs
    # chunking either (see agent/sources.py — chunked: True removed).
    "https://sbv.gov.vn/vi/thong-ke-mot-so-chi-tieu-co-ban": {
        "needs_js": True,
        "wait_selector": "article",
        "content_selector": "article",
        "pdf_link_selector": None,
        "pdf_link_limit": 1,
    },
    # The document list (AEM "list-view-documents" component) is empty in
    # the raw static HTML — it's populated client-side, so this needs the
    # full browser strategy even though the page itself isn't otherwise
    # JS-heavy. Each statement is published as two files, a scanned PDF and
    # a "-searchable" OCR'd twin with a real text layer; pdf_link_selector
    # targets only the searchable one so PDFContentScrapingStrategy gets
    # extractable text instead of a scanned image. Confirmed live: newest
    # quarter's consolidated VAS statement is always first in the list.
    "techcombank.com": {
        "needs_js": True,
        "wait_selector": None,
        "content_selector": ".list-view-documents",
        "pdf_link_selector": "a[href*='searchable']",
        "pdf_link_limit": 1,
    },
    # Bootstrap tabs (year × category), populated via Angular templating
    # ({{item.title}} bindings) — the static fetch is non-deterministic:
    # sometimes returns a cache-warmed, already-rendered page, sometimes
    # the raw unrendered template shell. needs_js:True forces the full
    # render every time. #pills-taichinh is the "Báo cáo tài chính"
    # (Financial Reports) tab. Vietnamese filenames encode report type:
    # "BCTC+HN" = hợp nhất (consolidated), "BCTC+RL" = riêng (separate/
    # standalone) — selector targets the consolidated one. Confirmed live:
    # newest-first ordering.
    #
    # #pills-taichinh itself contains 6 nested year-tab panes (2026, 2025,
    # 2024, 2023, 2022, "Khác"), all present in the DOM at once (only
    # CSS-hidden for inactive years) — and BIDV's own site shows the same
    # document set under every one of them. Selecting the bare container
    # pulled all 6 copies (confirmed live: 4,313 chars, 6x duplicated —
    # every document title/date repeated 6 times). Scoping to just
    # ".tab-pane.active" (the current year) gives the same real content
    # once: confirmed live, 713 chars, 4 consolidated links instead of 24.
    # Keyed by this specific URL, not the bare "bidv.com.vn" domain — BIDV
    # now has a second source on this domain (the Layer 2 fee-schedule page
    # below) needing a completely different selector. See
    # _resolve_site_config()'s own comment for why URL-keyed entries exist
    # alongside domain-keyed ones.
    "https://bidv.com.vn/vn/quan-he-nha-dau-tu/bao-cao-va-tai-lieu/": {
        "needs_js": True,
        "wait_selector": None,
        "content_selector": "#pills-taichinh .tab-pane.active",
        "pdf_link_selector": "a[href*='BCTC+HN']",
        "pdf_link_limit": 1,
    },
    # vanban.chinhphu.vn's homepage is ~80% nav/weather-widget boilerplate —
    # .document-content scopes to the real government document-list
    # container. Confirmed live: static fetch already returns real, current
    # content, no JS needed.
    "vanban.chinhphu.vn": {
        "needs_js": False,
        "wait_selector": None,
        "content_selector": ".document-content",
        "pdf_link_selector": None,
        "pdf_link_limit": 1,
    },
    # .main-content scopes past VNBA's nav/sidebar. Confirmed live: static
    # fetch works fine, real dated content.
    "vnba.org.vn": {
        "needs_js": False,
        "wait_selector": None,
        "content_selector": ".main-content",
        "pdf_link_selector": None,
        "pdf_link_limit": 1,
    },
    # Confirmed live: this domain's static HTTP response is a genuine 410
    # (not an anti-bot block) — needs_js forces the full browser strategy,
    # which returns real, current content. .col-left.f-collumn.row-g25
    # scopes to the real article list, skipping nav/sidebar chrome. IMPORTANT:
    # the "www." vhost is separately broken ("Chưa cài đặt Site Domain" — a
    # misconfigured host, not a block) — sources must use the bare domain.
    "tapchinganhang.gov.vn": {
        "needs_js": True,
        "wait_selector": None,
        "content_selector": ".col-left.f-collumn.row-g25",
        "pdf_link_selector": None,
        "pdf_link_limit": 1,
    },
    # A prior spot-check (DEVELOPMENT_PLAN.md v0.6) claimed zero anti-bot
    # walls here; a different fetcher (not crawl4ai) later got a real 403 —
    # confirmed live that crawl4ai itself gets through fine on the static
    # path. .siteCenter.flex-0 scopes past the weather-widget nav to the
    # real article list.
    "tapchitaichinh.vn": {
        "needs_js": False,
        "wait_selector": None,
        "content_selector": ".siteCenter.flex-0",
        "pdf_link_selector": None,
        "pdf_link_limit": 1,
    },
    # Layer 2 fee-schedule source, same domain as BIDV's Layer 1 source
    # above but a different page needing its own selector — why this entry
    # is keyed by URL, not domain. #accordionPanelsStayOpenExample scopes
    # past BIDV's full-site mega-menu (114K+ chars unscoped) down to just
    # the fee-schedule PDF list (982 chars, 12 real dated PDFs). Confirmed
    # live: the first (newest) PDF alone is a genuine, extractable fee
    # table (~41K chars, segmented by customer tier) — pdf_link_limit=1
    # picks that one; the other 11 are mostly older versions of the same
    # card-fee schedule, not distinct categories worth also fetching.
    "https://bidv.com.vn/vn/ca-nhan/cong-cu-tien-ich/bieu-phi": {
        "needs_js": True,
        "wait_selector": None,
        "content_selector": "#accordionPanelsStayOpenExample",
        "pdf_link_selector": "a[href*='.pdf']",
        "pdf_link_limit": 1,
    },
    # Layer 4 legal-document lookups (thuvienphapluat.vn is skipped — its
    # robots.txt has a dedicated "User-agent: ClaudeBot / Disallow: /"
    # block, distinct from its general Content-Signal declaration, so
    # luatvietnam.vn is used exclusively). .content-left scopes past a
    # large sidebar taxonomy nav (~30K chars unscoped on a typical decree
    # page). Confirmed live: the visible "Bạn chưa Đăng nhập thành viên"
    # notice on these pages gates only a "watch this document" convenience
    # feature, not the document text itself — full decree/circular/law
    # text including appendices is present in the static HTML, no JS
    # needed. Same selector confirmed live on both this domain and its
    # english.luatvietnam.vn sibling below.
    "luatvietnam.vn": {
        "needs_js": False,
        "wait_selector": None,
        "content_selector": ".content-left",
        "pdf_link_selector": None,
        "pdf_link_limit": 1,
    },
    "english.luatvietnam.vn": {
        "needs_js": False,
        "wait_selector": None,
        "content_selector": ".content-left",
        "pdf_link_selector": None,
        "pdf_link_limit": 1,
    },
    # GSO (General Statistics Office) was renamed NSO (National Statistics
    # Office); gso.gov.vn itself is now genuinely unreachable (confirmed
    # live: DNS/ping succeed but a raw TCP connect on port 443 times out —
    # a dead host, not a WAF/anti-bot block, and not an environment-wide
    # issue since sbv.gov.vn connects fine from the same check). The real,
    # current site is nso.gov.vn. .archive-container scopes past a large
    # nav/category-tree menu (~85K chars unscoped on the archive listing)
    # down to just that page's 5 real dated entries. Confirmed live: static
    # fetch already returns real, current (Aug 2026) content, no JS needed.
    "nso.gov.vn": {
        "needs_js": False,
        "wait_selector": None,
        "content_selector": ".archive-container",
        "pdf_link_selector": None,
        "pdf_link_limit": 1,
    },
    # Layer 2 app-store release notes (source_plan_mvp0.md §4). Google
    # Play's app detail page no longer has a "What's New" section at all —
    # confirmed live: absent from the entire ~1.2MB rendered page for a
    # real, live app (not a fetch/rendering issue, a real Play Store
    # redesign). Apple's App Store still has one — #mostRecentVersion
    # scopes to just that section (a curly-quote "What's New" heading, not
    # a straight apostrophe — an earlier plain-text keyword search for
    # "what's new" missed it for exactly this reason). Confirmed live
    # across all 6 named apps: real, current version history with dates.
    "apps.apple.com": {
        "needs_js": False,
        "wait_selector": None,
        "content_selector": "#mostRecentVersion",
        "pdf_link_selector": None,
        "pdf_link_limit": 1,
    },
}
DEFAULT_CONFIG = {
    "needs_js": False,
    "wait_selector": None,
    "content_selector": None,
    "pdf_link_selector": None,
    "pdf_link_limit": 1,
}


def _resolve_site_config(url: str) -> dict:
    """SITE_CONFIGS entries are keyed by either a specific URL (when a
    domain hosts multiple sources needing different selectors — e.g.
    bidv.com.vn's Layer 1 financial-statements page vs. its Layer 2
    fee-schedule page) or a bare domain (the common case: one distinct
    fetch pattern per site). URL match takes precedence over domain match,
    which falls back to DEFAULT_CONFIG. Using domain alone everywhere would
    let a second source on an already-configured domain silently reuse the
    wrong selector — confirmed live as a real bug (2026-09-01, building
    Layer 2) before this function existed."""
    if url in SITE_CONFIGS:
        return SITE_CONFIGS[url]
    return SITE_CONFIGS.get(_domain(url), DEFAULT_CONFIG)


def _domain(url: str) -> str:
    netloc = urlparse(url).netloc
    return netloc[4:] if netloc.startswith("www.") else netloc


async def _fetch_html(url: str, needs_js: bool, wait_selector: Optional[str] = None) -> Tuple[str, str]:
    """Fetch url and return (raw_html, generic_markdown_text). Uses
    crawl4ai's lightweight HTTP strategy unless needs_js is set, in which
    case it falls back to crawl4ai's default (Playwright-based) strategy."""
    _throttle(_domain(url))
    config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        wait_for=f"css:{wait_selector}" if wait_selector else None,
    )
    strategy = None if needs_js else AsyncHTTPCrawlerStrategy()
    async with AsyncWebCrawler(crawler_strategy=strategy) as crawler:
        result = await crawler.arun(url=url, config=config)
    if not result.success:
        raise RuntimeError(f"Failed to fetch {url}: {result.error_message}")
    return result.html, (result.markdown or "")


async def _fetch_pdf_text(crawler: AsyncWebCrawler, url: str) -> str:
    _throttle(_domain(url))
    config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, scraping_strategy=PDFContentScrapingStrategy())
    result = await crawler.arun(url=url, config=config)
    text = (result.markdown or "").strip()
    if len(text) < 50:
        # crawl4ai's generic "near-empty content" anti-bot check runs
        # against the PDF strategy's placeholder html (always ~30 bytes,
        # by design — see PDFCrawlerStrategy.crawl()), not the extracted
        # markdown, so result.success is unreliable for PDF fetches.
        # Checking the real extracted text length is the correct signal.
        raise ValueError(
            f"Expected real PDF content from {url} but got near-empty "
            f"extraction ({len(text)} chars) — likely blocked or rate-limited."
        )
    return text


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


async def _fetch_api_json_text(api_url: str) -> str:
    _, text = await _fetch_html(api_url, needs_js=False)
    return text


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


# SSI's own sector-reports listing page (khach-hang-ca-nhan/bao-cao-nganh)
# never exposes real per-report links even after a JS wait — its report
# rows aren't real <a> elements in the rendered DOM, confirmed live across
# multiple attempts. This is a single hand-verified PDF instead (same
# "explicit URL, not a scraper" approach as VCB_FEE_PDF_URLS above), found
# via web search rather than the listing page. Its own host
# (ftp2.ssi.com.vn) 403s crawl4ai's PDFCrawlerStrategy specifically — a
# crawl4ai-side quirk, not a real site block: confirmed live that plain
# curl with no special headers gets a clean 200 on the same URL. Fetched
# via urllib directly instead, then handed to crawl4ai's own PDF text
# extractor (NaivePDFProcessorStrategy) so no new PDF-parsing dependency is
# introduced. Event-driven per source_plan_mvp0.md §5 — needs periodic
# manual re-discovery when a newer sector report is published, same as
# every other hand-verified URL list in this file.
SSI_BANKING_SECTOR_REPORT_URL = (
    "https://ftp2.ssi.com.vn/Customers/GDDT/Analyst_Report/Sector%20Report/"
    "Cap%20nhat%20nganh%20Ngan%20hang_Thong%20tu%2022_2026.05.05_SSIResearch.pdf"
)


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


# NSO's GDP data (source_plan_mvp0.md §6.3) lives behind a genuine PxWeb
# statistical-database UI (classic ASP.NET WebForms, not the general
# WordPress feed nso_data_and_statistics_official reuses) — a different
# integration than anything else in this file. Its "Continue" button
# looked like a plain link but isn't: a raw JS-level .click() reset the
# selection to 0 cells instead of submitting (confirmed live) — ASP.NET's
# postback needs the listbox's actual selection state set via a real
# browser selection API (Playwright's select_option, which fires a proper
# change event), not just a DOM click. The resulting table URL's `rxid`
# is a server-side session id, not a stable/shareable link — confirmed
# live that re-fetching it in a fresh browser session just redirects back
# to the selection form — so the real table text has to be read from the
# very page that just submitted the form, in the same session, not
# fetched again afterward. This is why this function uses crawl4ai's
# on_page_context_created hook to get a real Playwright `page` handle,
# unlike every other custom fetch function in this file (which only need
# js_code) — genuinely necessary here, not a stylistic choice.
NSO_GDP_KEY_INDICATORS_URL = (
    "https://pxweb.nso.gov.vn/pxweb/en/National%20Accounts%20and%20State%20budget/"
    "National%20Accounts%20and%20State%20budget/E03.01.px/"
)
# Same PxWeb instance, VHLSS (household income/expenditure) tables —
# confirmed live that _fetch_nso_pxweb_table_text works unchanged for these
# too, no new logic needed: PxWeb's selection-form shape (2 listboxes +
# a "Continue" button with this exact element id) is generic across every
# table on this server, not something specific to the GDP one.
NSO_VHLSS_INCOME_URL = (
    "https://pxweb.nso.gov.vn/pxweb/en/Health%2C%20Culture%2C%20Sport%20and%20Living%20standard/"
    "Health%2C%20Culture%2C%20Sport%20and%20Living%20standard/E14.26.px/"
)
NSO_VHLSS_EXPENDITURE_URL = (
    "https://pxweb.nso.gov.vn/pxweb/en/Health%2C%20Culture%2C%20Sport%20and%20Living%20standard/"
    "Health%2C%20Culture%2C%20Sport%20and%20Living%20standard/E14.40.px/"
)


async def _fetch_nso_pxweb_table_text(url: str) -> str:
    _throttle(_domain(url))
    captured_page: dict = {}

    async def _on_page_ready(page, **kwargs):
        captured_page["page"] = page

    async with AsyncWebCrawler() as crawler:
        crawler.crawler_strategy.set_hook("on_page_context_created", _on_page_ready)
        await crawler.arun(url=url, config=CrawlerRunConfig(cache_mode=CacheMode.BYPASS))
        page = captured_page.get("page")
        if not page:
            raise RuntimeError(f"Failed to capture a page handle for {url}")

        selects = await page.query_selector_all("select[id*='ValuesListBox']")
        if len(selects) < 2:
            raise RuntimeError(f"Expected 2 PxWeb selection listboxes on {url}, found {len(selects)}")
        item_select, year_select = selects[0], selects[1]

        item_values = [await o.get_attribute("value") for o in await item_select.query_selector_all("option")]
        await item_select.select_option(value=item_values)

        # Latest 3 years only — keeps the selection well under PxWeb's
        # 100,000-cell limit and matches this project's "pull the latest
        # figures, not a historical archive" convention used elsewhere.
        year_values = [await o.get_attribute("value") for o in await year_select.query_selector_all("option")]
        await year_select.select_option(value=year_values[-3:])

        await page.click(
            "#ctl00_ContentPlaceHolderMain_VariableSelector1_VariableSelector1_ButtonViewTable"
        )
        await asyncio.sleep(3)
        text = await page.inner_text("body")

    if len(text.strip()) < 50:
        raise RuntimeError(f"Near-empty content submitting PxWeb selection at {url}")
    return text


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


# iav.vn's listing page (Layer 1 bancassurance) was only ever scraped for
# its own text — real article titles/dates, never the article bodies
# themselves (confirmed live 2026-09-02, user review of the fetched
# content: "you loaded the news homepage and only the text from there").
# The current URL already points at the right category (202, "Tổng quan,
# số liệu thị trường Bảo hiểm" — Insurance Market Overview/Data) per
# source_plan_mvp0.md §3.4's total-market-only scope; the real fix is
# following into the article links this page already lists, not finding
# a different page. Confirmed live: real, dated quarterly/semi-annual/
# annual "Tổng quan thị trường bảo hiểm Việt Nam ..." reports — exactly
# the total premium/growth figures the prompt asks for.
IAV_BANCASSURANCE_URL = "https://iav.vn/News/Listtt/202?page=1"
IAV_ARTICLE_LIMIT = 3


async def _fetch_iav_market_overview_parts() -> Tuple[str, List[Tuple[str, str]]]:
    async with AsyncWebCrawler(crawler_strategy=AsyncHTTPCrawlerStrategy()) as crawler:
        _throttle(_domain(IAV_BANCASSURANCE_URL))
        listing = await crawler.arun(url=IAV_BANCASSURANCE_URL, config=CrawlerRunConfig(cache_mode=CacheMode.BYPASS))
        if not listing.success:
            raise RuntimeError(f"Failed to fetch {IAV_BANCASSURANCE_URL}: {listing.error_message}")

        # Real overview-article links carry this URL slug (confirmed live:
        # /tong-quan,-so-lieu-thi-truong-bao-hiem/{id}-{slug}), distinct
        # from the ~190 nav/category/partner-site links on the same page.
        # The listing is already newest-first, so the first
        # IAV_ARTICLE_LIMIT distinct matches are the most recent reports.
        soup = BeautifulSoup(listing.html, "lxml")
        seen = set()
        article_urls: List[str] = []
        for a in soup.select("a[href*='tong-quan-so-lieu-thi-truong-bao-hiem'], a[href*='tong-quan,-so-lieu-thi-truong-bao-hiem']"):
            href = a.get("href")
            if not href:
                continue
            article_url = urljoin(IAV_BANCASSURANCE_URL, href)
            if article_url in seen:
                continue
            seen.add(article_url)
            article_urls.append(article_url)
            if len(article_urls) >= IAV_ARTICLE_LIMIT:
                break

        documents: List[Tuple[str, str]] = []
        for article_url in article_urls:
            _throttle(_domain(article_url))
            article = await crawler.arun(url=article_url, config=CrawlerRunConfig(cache_mode=CacheMode.BYPASS))
            if not article.success:
                logger.info("Failed to fetch iav article %s, skipping", article_url)
                continue
            text = (article.markdown or "").strip()
            if len(text) < 50:
                logger.info("Near-empty iav article %s, skipping", article_url)
                continue
            documents.append((article_url, text))

    list_text = (listing.markdown or "").strip()
    return list_text, documents


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


async def _fetch_mbbank_news_text() -> str:
    _throttle(_domain(MBBANK_NEWS_URL))
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url=MBBANK_NEWS_URL,
            config=CrawlerRunConfig(cache_mode=CacheMode.BYPASS, wait_for=MBBANK_NEWS_WAIT_JS, page_timeout=30000),
        )
    if not result.success:
        raise RuntimeError(f"Failed to fetch MBBank news page: {result.error_message}")

    soup = BeautifulSoup(result.html, "lxml")
    node = soup.select_one(MBBANK_NEWS_CONTENT_SELECTOR)
    if node is None:
        raise ValueError("MBBank news page's expected content section not found")
    text = node.get_text(separator="\n", strip=True)
    if not text:
        raise ValueError("MBBank news section had no usable content")
    return text


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


# Vietstock's static CDN serves each bank's filed financial statement at a
# direct, predictable URL — confirmed live to sit outside whatever wall
# blocks finance.vietstock.vn's JS-rendered document table (never rendered
# even after 60s) AND outside the Akamai walls on Vietcombank/MBBank's own
# sites. Used as a genuine Aggregator source per source_plan_mvp0.md §2
# ("the source recorded in metadata is the bank's original document, not
# the aggregator site") for banks whose own IR site is unreachable — not a
# bot-evasion technique, just a different, less-protected official mirror
# of the same filing.
#
# Not every filing has a text layer: confirmed live that VCB's Q2 2026
# copy here is a 55-page scan with zero extractable text, while MBB's is
# real, extractable Vietnamese text. That's a per-document limitation
# (surfaces as _fetch_pdf_text's existing near-empty-content check), not
# something this function can fix — MBB is wired in below; VCB is not,
# since its only available copy right now genuinely has nothing to
# extract.
def _vietstock_statement_candidates(ticker: str) -> Iterator[str]:
    """Yields candidate PDF URLs for ticker's consolidated quarterly
    statement, most-recent-quarter first, walking back a few quarters.
    Reports lag their period-end by ~20-40 days, so "today's calendar
    quarter" is rarely the latest one actually filed."""
    now = datetime.now()
    year, quarter = now.year, (now.month - 1) // 3 + 1
    for _ in range(4):
        yield (
            f"https://static2.vietstock.vn/data/HOSE/{year}/BCTC/VN/"
            f"QUY%20{quarter}/{ticker}_Baocaotaichinh_Q{quarter}_{year}_Hopnhat.pdf"
        )
        quarter -= 1
        if quarter == 0:
            quarter, year = 4, year - 1


async def _fetch_vietstock_statement_text(ticker: str) -> Tuple[str, str]:
    """Returns (text, pdf_url) — the winning candidate's own URL is
    surfaced now (previously discarded, text-only) so content_gate can run
    OCR-eligibility checks against a specific PDF, the same way the
    multi-PDF path's pdf_texts already lets it."""
    last_error: Optional[Exception] = None
    async with AsyncWebCrawler(crawler_strategy=PDFCrawlerStrategy()) as crawler:
        for url in _vietstock_statement_candidates(ticker):
            try:
                return await _fetch_pdf_text(crawler, url), url
            except Exception as exc:
                logger.info("No usable statement at %s (%s), trying an earlier quarter", url, exc)
                last_error = exc
    raise last_error or RuntimeError(f"No Vietstock statement found for {ticker}")


def _select_content(html: str, config: dict) -> Optional[Tuple[Any, str]]:
    """Returns (matched node, extracted text) for config's content_selector,
    or None if there's no selector configured or it didn't match."""
    if not config.get("content_selector"):
        return None
    soup = BeautifulSoup(html, "lxml")
    node = soup.select_one(config["content_selector"])
    if not node:
        return None
    return node, node.get_text(separator="\n", strip=True)


async def _fetch_selected_pdfs(url: str, node: Any, config: dict) -> List[Tuple[str, str]]:
    """Fetch the PDFs linked from node per config's pdf_link_selector/limit.
    Returns [(pdf_url, pdf_text), ...] — one bad PDF (blocked, malformed,
    rate-limited) is logged and skipped rather than discarding the rest."""
    documents: List[Tuple[str, str]] = []
    pdf_selector = config.get("pdf_link_selector")
    if not (node and pdf_selector):
        return documents

    limit = config.get("pdf_link_limit", 1)
    links = [a for a in node.select(pdf_selector) if a.get("href")][:limit]
    if not links:
        return documents

    # One shared crawler for every PDF in this batch, instead of paying
    # AsyncWebCrawler's session/setup cost per PDF.
    async with AsyncWebCrawler(crawler_strategy=PDFCrawlerStrategy()) as crawler:
        for link in links:
            pdf_url = urljoin(url, link["href"])
            logger.info("Fetching PDF for %s -> %s", url, pdf_url)
            try:
                pdf_text = await _fetch_pdf_text(crawler, pdf_url)
            except Exception:
                logger.exception("Failed to fetch PDF %s, skipping", pdf_url)
                continue
            documents.append((pdf_url, pdf_text))
    return documents


async def _crawl_parts_async(url: str) -> Tuple[str, List[Tuple[str, str]]]:
    if url == VCB_FEE_URL:
        return await _fetch_vcb_fee_parts()
    if url == IAV_BANCASSURANCE_URL:
        return await _fetch_iav_market_overview_parts()
    if url == MBBANK_NEWS_URL:
        return await _fetch_mbbank_news_parts()

    config = _resolve_site_config(url)
    html, generic_text = await _fetch_html(url, config["needs_js"], config["wait_selector"])

    selected = _select_content(html, config)
    # selected is a (node, text) tuple, always truthy even when text is ""
    # (an empty-but-matched selector) — check the text itself, not the tuple.
    node, list_text = selected if selected and selected[1] else (None, generic_text or html)

    documents = await _fetch_selected_pdfs(url, node, config)
    return list_text, documents


def crawl_parts(url: str) -> Tuple[str, List[Tuple[str, str]]]:
    """Like crawl(), but for sources with multiple PDFs to process
    separately: returns (list_text, [(pdf_url, pdf_text), ...]) instead of
    one concatenated string, so each PDF can go through its own LLM
    structuring call — staying comfortably within Groq's per-request token
    ceiling — and keep its own provenance URL rather than the listing
    page's."""
    return asyncio.run(_crawl_parts_async(url))


# Banks whose own IR site is unreachable (Akamai-blocked — see
# agent/sources.py's Layer 1 comment) but whose filed statement happens to
# have a real text layer on Vietstock's static CDN. Keyed by the bank's own
# *specific* financial-statement URL (used as the source's citation URL in
# agent/sources.py), not the domain as a whole — a domain-wide key would
# hijack every other page on that domain, not just this one. Confirmed live
# (2026-09-01, building Layer 2): fetching mbbank.com.vn's sitemap.xml
# through a domain-keyed check returned MBB's financial statement instead
# of the sitemap, since the domain matched regardless of path.
MBBANK_FINANCIAL_STATEMENTS_URL = "https://mbbank.com.vn/Investor/thong-bao-nha-dau-tu"
VIETSTOCK_FALLBACK_TICKERS = {
    MBBANK_FINANCIAL_STATEMENTS_URL: "MBB",
}


async def _crawl_async(url: str) -> Tuple[str, List[Tuple[str, str]]]:
    """Returns (flattened_text, [(pdf_url, pdf_text), ...]) — the second
    element is [] for sources with no PDF-fetching SITE_CONFIGS entry (the
    dispatch branches below, and any source with pdf_link_selector unset),
    and carries each fetched PDF's own URL alongside its text otherwise
    (mirrors _crawl_parts_async's shape) — needed so agent/graph.py's
    _content_gate_node can run agent/content_gate.py's page-density/OCR
    checks against a specific PDF, not just the flattened blob. crawl()
    below is the plain-string-only wrapper every other caller still uses."""
    if url == ACB_FINANCIAL_STATEMENTS_URL:
        return await _fetch_acb_statement_text(), []
    if url == ACB_PROMOTIONS_URL:
        return await _fetch_acb_promotions_text(), []
    if url == ACB_FEE_SCHEDULE_URL:
        return await _fetch_acb_fee_schedule_text(), []
    if url == VPBANK_NEWS_URL:
        return await _fetch_api_json_text(VPBANK_NEWS_API), []
    if url == VPBANK_FEE_URL:
        return await _fetch_api_json_text(VPBANK_FEE_API), []
    if url == VCB_PROMOTIONS_URL:
        return await _fetch_vcb_promotions_text(), []
    if url == MBBANK_FEE_URL:
        return await _fetch_mbbank_fee_text(), []
    if url == MBBANK_NEWS_URL:
        return await _fetch_mbbank_news_text(), []
    if url == SSI_BANKING_SECTOR_REPORT_URL:
        return await _fetch_ssi_report_text(url), []
    if url == VCBS_BANKING_SECTOR_REPORT_URL:
        return await _fetch_vcbs_report_text(url), []
    if url in (NSO_GDP_KEY_INDICATORS_URL, NSO_VHLSS_INCOME_URL, NSO_VHLSS_EXPENDITURE_URL):
        return await _fetch_nso_pxweb_table_text(url), []
    if url in VIETSTOCK_FALLBACK_TICKERS:
        text, pdf_url = await _fetch_vietstock_statement_text(VIETSTOCK_FALLBACK_TICKERS[url])
        return text, [(pdf_url, text)]

    config = _resolve_site_config(url)

    if config["needs_js"]:
        html, generic_text = await _fetch_html(url, needs_js=True, wait_selector=config["wait_selector"])
    else:
        html, generic_text = await _fetch_html(url, needs_js=False)
        if not (generic_text and len(generic_text) > 200):
            logger.info("Static fetch yielded little content for %s, escalating to full browser fetch", url)
            html, generic_text = await _fetch_html(url, needs_js=True, wait_selector=config["wait_selector"])

    selected = _select_content(html, config)
    # selected is a (node, text) tuple, always truthy even when text is ""
    # (an empty-but-matched selector) — check the text itself, not the tuple.
    if not selected or not selected[1]:
        return generic_text or html, []

    node, text = selected
    documents = await _fetch_selected_pdfs(url, node, config)
    for pdf_url, pdf_text in documents:
        text = f"{text}\n\n--- Full content of {pdf_url} ---\n{pdf_text}"
    return text, documents


def crawl(url: str) -> str:
    """Fetch a URL's main text content. Tries the cheap path first (crawl4ai's
    lightweight HTTP strategy + generic markdown extraction); escalates to a
    real headless browser only when SITE_CONFIGS says the site needs JS, or
    the cheap path comes back with suspiciously little content."""
    text, _ = asyncio.run(_crawl_async(url))
    return text


def crawl_with_pdf_urls(url: str) -> Tuple[str, List[Tuple[str, str]]]:
    """Like crawl(), but also returns each fetched PDF's own URL alongside
    its text — [(pdf_url, pdf_text), ...], empty for sources with no
    PDF-fetching SITE_CONFIGS entry. Used by agent/graph.py's
    _crawl_node so _content_gate_node can run OCR-fallback checks against
    a specific PDF's real URL, the same way the multi-PDF path's
    pdf_texts state already lets it."""
    return asyncio.run(_crawl_async(url))


# Groq's free tier caps a single request at 8,000 tokens/minute — confirmed
# live that a source's full fetched text can exceed that on its own (a
# large financial-statement PDF, or just a dense listing page), not just
# when several documents are combined. ~3.3 chars/token is a safe rough
# ratio for this mixed English/Vietnamese content (measured against real
# 413 responses); 12,000 chars leaves headroom for the system prompt and
# the model's own output tokens within the same per-minute budget.
MAX_CHUNK_CHARS = 12000


def _chunk_text(text: str, max_chars: int) -> List[str]:
    """Split text into <= max_chars pieces, preferring a paragraph or
    sentence boundary near the cut point so a chunk doesn't split a table
    row or sentence in half."""
    if len(text) <= max_chars:
        return [text] if text else []

    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        if end >= len(text):
            chunks.append(text[start:].strip())
            break
        cut = text.rfind("\n\n", start, end)
        if cut <= start:
            cut = text.rfind(". ", start, end)
        if cut <= start:
            cut = end
        else:
            cut += 1  # keep the boundary character with the chunk before it
        chunks.append(text[start:cut].strip())
        start = cut
    return [c for c in chunks if c]


async def _crawl_chunked_async(url: str) -> Tuple[str, List[Tuple[str, str]]]:
    # Real bug fixed here (2026-09-02): _crawl_async's return type changed
    # to (text, pdf_texts) for the single-fetch path's OCR wiring, but this
    # caller wasn't updated — `text = await _crawl_async(url)` bound the
    # whole tuple to `text`, breaking every chunked source (Techcombank,
    # ACB, MBB, BIDV/ACB/MBBank fee schedules) the moment it shipped.
    # Caught by mbb_financial_statements' own OCR-eligibility fix needing
    # to trace this same path, not by a test — there is no offline test
    # covering crawl_chunked()'s real behavior (see test_sources.py's own
    # "no mocking, real network" testing decision).
    text, pdf_texts = await _crawl_async(url)
    # If the fetch already resolved to one real document URL (not the
    # source's own landing page) — e.g. MBB's Vietstock mirror, or
    # Techcombank's own generic-SITE_CONFIGS PDF fetch — tag every chunk
    # with THAT real URL instead, so content_gate's per-piece OCR-
    # eligibility check has something real to download and OCR. Falls
    # back to the landing page URL (previous behavior, unchanged) when no
    # single real document URL is known.
    chunk_url = pdf_texts[0][0] if len(pdf_texts) == 1 else url
    return "", [(chunk_url, chunk) for chunk in _chunk_text(text, MAX_CHUNK_CHARS)]


def crawl_chunked(url: str) -> Tuple[str, List[Tuple[str, str]]]:
    """Like crawl_parts(), but for a single-document source whose fetched
    text is too large for one Groq structure call: splits crawl()'s output
    into <= MAX_CHUNK_CHARS pieces instead of fetching several distinct
    PDFs. Returns ("", [(url, chunk), ...]) — the same shape as
    crawl_parts(), so it reuses build_multi_pdf_graph()'s per-piece
    structuring + deterministic merge unchanged; every chunk shares the
    source's one real URL since they're all pieces of the same document."""
    return asyncio.run(_crawl_chunked_async(url))
