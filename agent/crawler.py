import agent.ssl_bootstrap  # noqa: F401  — must import-run before crawl4ai/aiohttp below (see that module's docstring)

import asyncio
import logging
import time
from datetime import datetime
from io import BytesIO
from typing import Any, Iterator, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig
from crawl4ai.async_crawler_strategy import AsyncHTTPCrawlerStrategy
from crawl4ai.processors.pdf import PDFContentScrapingStrategy, PDFCrawlerStrategy

from agent.fetcher_registry import CUSTOM_FETCHERS

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
    # cimigo's "trends" blog (free) vs. its askcimigo.com report catalog
    # (paywalled, 40pp PDFs) — confirmed live these are two separate things,
    # not the same content gated differently. div.post--content scopes past
    # the page's nav/related-posts/newsletter-CTA noise (checked: the wider
    # wrapper divs are 5-6x the size, mostly boilerplate). Static fetch
    # already returns the real article, no JS needed.
    "cimigo.com": {
        "needs_js": False,
        "wait_selector": None,
        "content_selector": "div.post--content",
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


async def _fetch_api_json_text(api_url: str) -> str:
    _, text = await _fetch_html(api_url, needs_js=False)
    return text


async def _fetch_annual_report_page_ranges(
    url: str, page_ranges: List[Tuple[int, int]], bank_name: str
) -> Tuple[str, List[Tuple[str, str]]]:
    """Shared by every bank's annual-report source: download the PDF,
    extract only the given 0-indexed inclusive page ranges (hand-found
    per bank — see each bank's own URL/page-range comment above), chunk
    the result through the existing generic mechanism."""
    _throttle(_domain(url))
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    reader = PdfReader(BytesIO(response.content))

    parts = []
    for start, end in page_ranges:
        text = "\n".join(
            (reader.pages[i].extract_text() or "") for i in range(start, min(end + 1, len(reader.pages)))
        ).strip()
        if text:
            parts.append(text)

    if not parts:
        raise ValueError(f"No real text extracted from {bank_name}'s annual report — check page ranges still match the current PDF")

    combined = "\n\n".join(parts)
    chunks = _chunk_text(combined, MAX_CHUNK_CHARS)
    return "", [(url, chunk) for chunk in chunks]


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


# A near-empty PDF extraction is often a transient anti-bot/rate-limit
# block (an HTML error page served instead of the PDF), not a permanently
# dead link — confirmed live for sbv_press_releases_official: fetching the
# exact same URL twice in a row got 3/3 real PDFs the first time, 2/3 the
# second. 3 attempts with a short pause gives that a real chance to clear.
PDF_FETCH_MAX_ATTEMPTS = 3
PDF_FETCH_RETRY_DELAY_SECONDS = 10


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
            pdf_text = None
            for attempt in range(1, PDF_FETCH_MAX_ATTEMPTS + 1):
                try:
                    pdf_text = await _fetch_pdf_text(crawler, pdf_url)
                    break
                except Exception:
                    if attempt < PDF_FETCH_MAX_ATTEMPTS:
                        # User-reported (2026-09-03, sbv_press_releases_official):
                        # this exact failure — an intermittent anti-bot/rate-limit
                        # block that returns an HTML error page instead of the
                        # PDF — confirmed live to be transient (back-to-back
                        # fetches of the same URL: one run got all 3 PDFs, the
                        # next got 2/3 with the 3rd blocked). A silent skip
                        # (previous behavior) meant one bad moment produced a
                        # title-only fallback that still spent real LLM tokens
                        # for 0 signals, with nothing distinguishing that from a
                        # genuinely empty source. Retrying gives the transient
                        # block a real chance to clear before giving up.
                        logger.info(
                            "PDF fetch failed for %s (attempt %d/%d), retrying in %ds",
                            pdf_url, attempt, PDF_FETCH_MAX_ATTEMPTS, PDF_FETCH_RETRY_DELAY_SECONDS,
                        )
                        await asyncio.sleep(PDF_FETCH_RETRY_DELAY_SECONDS)
                    else:
                        logger.exception("Failed to fetch PDF %s after %d attempts, skipping", pdf_url, PDF_FETCH_MAX_ATTEMPTS)
            if pdf_text is not None:
                documents.append((pdf_url, pdf_text))
    return documents


async def _crawl_parts_async(url: str) -> Tuple[str, List[Tuple[str, str]]]:
    custom = CUSTOM_FETCHERS.get(url)
    if custom is not None:
        _, fn = custom
        return await fn()

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


async def _crawl_async(url: str) -> Tuple[str, List[Tuple[str, str]]]:
    """Returns (flattened_text, [(pdf_url, pdf_text), ...]) — the second
    element is [] for sources with no PDF-fetching SITE_CONFIGS entry (a
    registered custom fetcher may still populate it — see
    agent/fetcher_registry.py), and carries each fetched PDF's own URL
    alongside its text otherwise (mirrors _crawl_parts_async's shape) —
    needed so agent/graph.py's _content_gate_node can run
    agent/content_gate.py's page-density/OCR checks against a specific PDF,
    not just the flattened blob. crawl() below is the plain-string-only
    wrapper every other caller still uses."""
    custom = CUSTOM_FETCHERS.get(url)
    if custom is not None:
        _, fn = custom
        return await fn()

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


# Triggers every agent/fetchers/<site>.py module's @register_fetcher(...)
# decorators, populating CUSTOM_FETCHERS above. Imported here — at the very
# end of this module, after every shared helper those modules import back
# from agent.crawler (_throttle, _domain, _fetch_html, _fetch_pdf_text,
# _fetch_annual_report_page_ranges, _fetch_vietstock_statement_text,
# _fetch_api_json_text, _chunk_text, MAX_CHUNK_CHARS) is already defined —
# since agent/fetchers/*.py's own "from agent.crawler import ..." would
# otherwise hit a circular-import error partway through this module's own
# initialization.
import agent.fetchers  # noqa: F401,E402
