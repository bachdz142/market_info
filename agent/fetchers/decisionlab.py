import logging
from typing import List, Tuple

from agent.crawler import _domain, _throttle
from agent.fetcher_registry import register_fetcher

from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig
from crawl4ai.async_crawler_strategy import AsyncHTTPCrawlerStrategy

logger = logging.getLogger(__name__)

# decisionlab.co's blog has no per-topic category filter that survives a
# plain fetch (checked live) — the URLs below were picked by hand from its
# real sitemap.xml (2026-09-03), grouped into 3 sources by theme (Connected
# Consumer quarterly series / Gen X-Y-Z behavior / fintech-e-wallet
# behavior) rather than one source per article, matching this project's
# "one source_id, several real documents" pattern (see IAV/mbbank_news
# above). Confirmed live: a plain static fetch (AsyncHTTPCrawlerStrategy,
# no JS) already returns the real article — decisionlab.co is HubSpot-CMS
# hosted, .pwr-post-content scopes past its nav/related-posts noise, same
# selector confirmed working across all 3 groups' articles. Refreshing this
# list to newer articles later means re-checking the sitemap by hand, same
# as this project's other Layer 3 sources (SSI/VCBS/decisionlab rankings)
# already being single hardcoded URLs, not auto-discovered.
DECISIONLAB_POST_SELECTOR = ".pwr-post-content"

DECISIONLAB_CONNECTED_CONSUMER_URLS = [
    "https://www.decisionlab.co/blog/the-connected-consumer-vietnam-digital-2025",
    "https://www.decisionlab.co/blog/connected-consumer-report-q12025",
    "https://www.decisionlab.co/blog/the-connected-consumer-q4-2024-blog",
]

DECISIONLAB_GENZ_BEHAVIOR_URLS = [
    "https://www.decisionlab.co/blog/vietnam-what-brands-must-know-about-generation-z",
    "https://www.decisionlab.co/blog/gen-z-wants-to-disconnect",
    "https://www.decisionlab.co/blog/gen-x-driving-grab-towards-vietnams-4-billion-ride-hailing-future",
    "https://www.decisionlab.co/blog/tiktok-grows-beyond-gen-z-while-old-habits-persist-despite-divided-attention",
]

DECISIONLAB_FINTECH_EWALLET_URLS = [
    "https://www.decisionlab.co/blog/demystifying-the-rise-of-e-wallets-in-vietnam",
    "https://www.decisionlab.co/blog/e-wallet-in-vietnam-solving-the-user-disloyalty-puzzle",
    "https://www.decisionlab.co/blog/fintech-and-mobile-banking-lead-yougovs-bank-and-payment-system-consideration-rankings-in-vietnam",
]


async def _fetch_decisionlab_article_parts(urls: List[str]) -> Tuple[str, List[Tuple[str, str]]]:
    documents: List[Tuple[str, str]] = []
    async with AsyncWebCrawler(crawler_strategy=AsyncHTTPCrawlerStrategy()) as crawler:
        for url in urls:
            _throttle(_domain(url))
            result = await crawler.arun(url=url, config=CrawlerRunConfig(cache_mode=CacheMode.BYPASS))
            if not result.success:
                logger.info("Failed to fetch decisionlab.co article %s, skipping", url)
                continue
            soup = BeautifulSoup(result.html, "lxml")
            node = soup.select_one(DECISIONLAB_POST_SELECTOR)
            text = node.get_text(separator="\n", strip=True) if node else ""
            if len(text) < 50:
                logger.info("Near-empty decisionlab.co article %s, skipping", url)
                continue
            documents.append((url, text))

    if not documents:
        raise ValueError("No decisionlab.co articles found with real content")
    list_text = "\n\n".join(f"--- {url} ---\n{text}" for url, text in documents)
    return list_text, documents


@register_fetcher(DECISIONLAB_CONNECTED_CONSUMER_URLS[0], "parts")
async def _fetch_decisionlab_connected_consumer_parts() -> Tuple[str, List[Tuple[str, str]]]:
    return await _fetch_decisionlab_article_parts(DECISIONLAB_CONNECTED_CONSUMER_URLS)


@register_fetcher(DECISIONLAB_GENZ_BEHAVIOR_URLS[0], "parts")
async def _fetch_decisionlab_genz_behavior_parts() -> Tuple[str, List[Tuple[str, str]]]:
    return await _fetch_decisionlab_article_parts(DECISIONLAB_GENZ_BEHAVIOR_URLS)


@register_fetcher(DECISIONLAB_FINTECH_EWALLET_URLS[0], "parts")
async def _fetch_decisionlab_fintech_ewallet_parts() -> Tuple[str, List[Tuple[str, str]]]:
    return await _fetch_decisionlab_article_parts(DECISIONLAB_FINTECH_EWALLET_URLS)
