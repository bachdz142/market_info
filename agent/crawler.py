import agent.ssl_bootstrap  # noqa: F401  — must import-run before crawl4ai/aiohttp below (see that module's docstring)

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any, Iterator, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig
from crawl4ai.async_crawler_strategy import AsyncHTTPCrawlerStrategy
from crawl4ai.processors.pdf import PDFContentScrapingStrategy, PDFCrawlerStrategy

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


async def _fetch_vietstock_statement_text(ticker: str) -> str:
    last_error: Optional[Exception] = None
    async with AsyncWebCrawler(crawler_strategy=PDFCrawlerStrategy()) as crawler:
        for url in _vietstock_statement_candidates(ticker):
            try:
                return await _fetch_pdf_text(crawler, url)
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


async def _crawl_async(url: str) -> str:
    if url == ACB_FINANCIAL_STATEMENTS_URL:
        return await _fetch_acb_statement_text()
    if url in VIETSTOCK_FALLBACK_TICKERS:
        return await _fetch_vietstock_statement_text(VIETSTOCK_FALLBACK_TICKERS[url])

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
        return generic_text or html

    node, text = selected
    for pdf_url, pdf_text in await _fetch_selected_pdfs(url, node, config):
        text = f"{text}\n\n--- Full content of {pdf_url} ---\n{pdf_text}"
    return text


def crawl(url: str) -> str:
    """Fetch a URL's main text content. Tries the cheap path first (crawl4ai's
    lightweight HTTP strategy + generic markdown extraction); escalates to a
    real headless browser only when SITE_CONFIGS says the site needs JS, or
    the cheap path comes back with suspiciously little content."""
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
    text = await _crawl_async(url)
    return "", [(url, chunk) for chunk in _chunk_text(text, MAX_CHUNK_CHARS)]


def crawl_chunked(url: str) -> Tuple[str, List[Tuple[str, str]]]:
    """Like crawl_parts(), but for a single-document source whose fetched
    text is too large for one Groq structure call: splits crawl()'s output
    into <= MAX_CHUNK_CHARS pieces instead of fetching several distinct
    PDFs. Returns ("", [(url, chunk), ...]) — the same shape as
    crawl_parts(), so it reuses build_multi_pdf_graph()'s per-piece
    structuring + deterministic merge unchanged; every chunk shares the
    source's one real URL since they're all pieces of the same document."""
    return asyncio.run(_crawl_chunked_async(url))
