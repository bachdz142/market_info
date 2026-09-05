# A URL that needs bespoke fetch logic (an API call, a click-through
# interaction, PDF page-range slicing — anything SITE_CONFIGS's generic
# selector-based extraction can't express) registers its custom fetcher
# here instead of being wired into agent/crawler.py's dispatch by hand.
# This replaced a manual per-URL conditional branch duplicated across
# agent/crawler.py's two dispatchers (_crawl_async/_crawl_parts_async) —
# real bug, caught 2026-09-03: a fetcher wired into only one of the two
# chains silently ran through the wrong (generic) extraction path instead
# of its intended custom logic, with no error. A single registration here
# makes that class of mistake structurally harder: one URL maps to exactly
# one (shape, function) pair, and registering the same URL twice is a
# loud failure instead of a silent overwrite.
#
# shape is "single" (the function's result is consumed via
# agent/crawler.py's _crawl_async — used by both plain and "chunked"
# sources) or "parts" (consumed via _crawl_parts_async — used by
# "multi_pdf" sources). See .scratch/source-fetcher-refactor/spec.md and
# tests/test_fetcher_registry.py, which cross-checks every registration's
# shape against its source's own agent/sources/ configuration.
from typing import Awaitable, Callable, Dict, List, Tuple

FetchResult = Tuple[str, List[Tuple[str, str]]]
CUSTOM_FETCHERS: Dict[str, Tuple[str, Callable[[], Awaitable[FetchResult]]]] = {}


def register_fetcher(url: str, shape: str):
    """Decorator: registers fn as the custom fetcher for url. fn must be an
    async, zero-argument callable returning (text, documents) — the same
    (str, List[Tuple[str, str]]) shape agent/crawler.py's dispatchers
    themselves return to their own callers."""
    if shape not in ("single", "parts"):
        raise ValueError(f"register_fetcher shape must be 'single' or 'parts', got {shape!r}")

    def decorator(fn):
        if url in CUSTOM_FETCHERS:
            raise ValueError(f"A custom fetcher is already registered for {url!r}")
        CUSTOM_FETCHERS[url] = (shape, fn)
        return fn

    return decorator
