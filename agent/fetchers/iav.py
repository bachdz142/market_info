import logging
from typing import List, Tuple
from urllib.parse import urljoin

from agent.crawler import _domain, _throttle
from agent.fetcher_registry import register_fetcher

from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig
from crawl4ai.async_crawler_strategy import AsyncHTTPCrawlerStrategy

logger = logging.getLogger(__name__)

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


@register_fetcher(IAV_BANCASSURANCE_URL, "parts")
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
