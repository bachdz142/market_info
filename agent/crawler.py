import agent.ssl_bootstrap  # noqa: F401  — must import-run before crawl4ai/aiohttp below (see that module's docstring)

import asyncio
import logging
import time
from typing import Any, List, Optional, Tuple
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
}
DEFAULT_CONFIG = {
    "needs_js": False,
    "wait_selector": None,
    "content_selector": None,
    "pdf_link_selector": None,
    "pdf_link_limit": 1,
}


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
    config = SITE_CONFIGS.get(_domain(url), DEFAULT_CONFIG)
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


async def _crawl_async(url: str) -> str:
    config = SITE_CONFIGS.get(_domain(url), DEFAULT_CONFIG)

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
