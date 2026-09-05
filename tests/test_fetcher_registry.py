"""Fast, offline, structural checks for the agent/fetcher_registry.py
registration mechanism (.scratch/source-fetcher-refactor/spec.md). No
network, no LLM spend — safe to run on every change, unlike
test_sources.py's real-network suite.

The real bug this guards against (found live, 2026-09-03, building the
5-bank annual-report sources): a custom fetcher wired into only one of
agent/crawler.py's two dispatch chains, so its source silently ran through
the wrong (generic) extraction path instead of its intended custom logic,
with no error raised. A registered fetcher's "shape" ("single" -> consumed
via _crawl_async/crawl()/crawl_with_pdf_urls()/crawl_chunked(), "parts" ->
consumed via _crawl_parts_async()/crawl_parts()) must match which
dispatcher its own source is actually routed through by agent/graph.py —
"parts" sources are exactly the ones with multi_pdf set; everything else
(plain or chunked) goes through the "single" path.
"""

import agent.crawler  # noqa: F401 — populates CUSTOM_FETCHERS as a side effect
from agent.fetcher_registry import CUSTOM_FETCHERS
from agent.sources import SOURCES


def test_no_duplicate_or_dropped_sources():
    ids = [s["id"] for s in SOURCES]
    assert len(ids) == len(set(ids)), "duplicate source id in SOURCES"


def test_every_registered_url_matches_a_real_source():
    urls = {s["url"] for s in SOURCES}
    for url in CUSTOM_FETCHERS:
        assert url in urls, f"registered custom fetcher for {url!r} has no matching source"


def test_registered_shape_matches_source_configuration():
    sources_by_url = {s["url"]: s for s in SOURCES}
    mismatches = []
    for url, (shape, fn) in CUSTOM_FETCHERS.items():
        source = sources_by_url.get(url)
        if source is None:
            continue
        is_multi_pdf = bool(source.get("multi_pdf"))
        if shape == "parts" and not is_multi_pdf:
            mismatches.append(
                f"{source['id']!r} ({fn.__module__}.{fn.__name__}) is registered as "
                f"'parts' but its source isn't multi_pdf"
            )
        if shape == "single" and is_multi_pdf:
            mismatches.append(
                f"{source['id']!r} ({fn.__module__}.{fn.__name__}) is registered as "
                f"'single' but its source is multi_pdf"
            )
    assert not mismatches, "\n".join(mismatches)
