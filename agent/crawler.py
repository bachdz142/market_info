import logging
import time
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
import trafilatura
from bs4 import BeautifulSoup

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
# Most sites don't need an entry here — DEFAULT_CONFIG (static fetch +
# trafilatura's generic extraction) is tried first for everything.
SITE_CONFIGS = {
    "customs.gov.vn": {
        "needs_js": True,
        "wait_selector": None,
        "content_selector": None,
        "pdf_link_selector": None,
        "pdf_link_limit": 1,
    },
    # trafilatura's generic extraction pulls pure nav-menu boilerplate on
    # this domain's listing pages (e.g. /en/press-release) — the real
    # content lives in a Liferay portlet, <ul class="doc-list">. Confirmed
    # safe for the other sbv.gov.vn pages too: if this selector doesn't
    # match, _apply_selector() falls through to the generic extraction.
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

USER_AGENT = "Mozilla/5.0 (compatible; MarketInsightAgent/1.0)"


def _domain(url: str) -> str:
    netloc = urlparse(url).netloc
    return netloc[4:] if netloc.startswith("www.") else netloc


def _fetch_static(url: str) -> str:
    _throttle(_domain(url))
    resp = requests.get(url, timeout=15, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    return resp.text


def _fetch_js(url: str, wait_selector: Optional[str] = None) -> str:
    _throttle(_domain(url))
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=USER_AGENT)
        page.goto(url, wait_until="networkidle", timeout=30000)
        if wait_selector:
            page.wait_for_selector(wait_selector, timeout=15000)
        html = page.content()
        browser.close()
        return html


def _fetch_pdf_text(url: str) -> str:
    _throttle(_domain(url))
    from io import BytesIO

    from pypdf import PdfReader

    resp = requests.get(url, timeout=20, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    if not resp.content.startswith(b"%PDF"):
        # Not a real PDF — most likely a WAF/rate-limit block page (HTML)
        # served instead of the file. Fail with a clear message rather
        # than letting pypdf throw a confusing internal parsing error.
        raise ValueError(
            f"Expected a PDF from {url} but got non-PDF content "
            f"(starts with {resp.content[:20]!r}) — likely blocked or rate-limited."
        )
    reader = PdfReader(BytesIO(resp.content))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _apply_selector(html: str, url: str, config: dict) -> Optional[str]:
    if not config.get("content_selector"):
        return None
    soup = BeautifulSoup(html, "lxml")
    node = soup.select_one(config["content_selector"])
    if not node:
        return None
    text = node.get_text(separator="\n", strip=True)

    pdf_selector = config.get("pdf_link_selector")
    if pdf_selector:
        limit = config.get("pdf_link_limit", 1)
        links = [a for a in node.select(pdf_selector) if a.get("href")][:limit]
        for link in links:
            pdf_url = urljoin(url, link["href"])
            logger.info("Fetching PDF for %s -> %s", url, pdf_url)
            pdf_text = _fetch_pdf_text(pdf_url)
            text = f"{text}\n\n--- Full content of {pdf_url} ---\n{pdf_text}"

    return text


def crawl_parts(url: str):
    """Like crawl(), but for sources with multiple PDFs to process
    separately: returns (list_text, [pdf_text, ...]) instead of one
    concatenated string, so each PDF can go through its own LLM structuring
    call and stay comfortably within Groq's per-request token ceiling."""
    config = SITE_CONFIGS.get(_domain(url), DEFAULT_CONFIG)
    html = _fetch_js(url, config["wait_selector"]) if config["needs_js"] else _fetch_static(url)

    soup = BeautifulSoup(html, "lxml")
    node = soup.select_one(config["content_selector"]) if config.get("content_selector") else None
    list_text = node.get_text(separator="\n", strip=True) if node else (trafilatura.extract(html) or html)

    pdf_texts = []
    pdf_selector = config.get("pdf_link_selector")
    if node and pdf_selector:
        limit = config.get("pdf_link_limit", 1)
        links = [a for a in node.select(pdf_selector) if a.get("href")][:limit]
        for link in links:
            pdf_url = urljoin(url, link["href"])
            logger.info("Fetching PDF for %s -> %s", url, pdf_url)
            pdf_texts.append(_fetch_pdf_text(pdf_url))

    return list_text, pdf_texts


def crawl(url: str) -> str:
    """Fetch a URL's main text content. Tries the cheap path first (plain
    HTTP + trafilatura's generic content extraction); escalates to a real
    headless browser only when SITE_CONFIGS says the site needs JS, or the
    cheap path comes back with suspiciously little content."""
    config = SITE_CONFIGS.get(_domain(url), DEFAULT_CONFIG)

    if not config["needs_js"]:
        html = _fetch_static(url)
        text = trafilatura.extract(html)
        if text and len(text) > 200:
            return _apply_selector(html, url, config) or text
        logger.info("Static fetch yielded little content for %s, escalating to Playwright", url)

    html = _fetch_js(url, config["wait_selector"])
    return _apply_selector(html, url, config) or trafilatura.extract(html) or html
