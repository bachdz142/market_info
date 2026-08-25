# Predefined URL-based sources for official/structured data — an alternative
# to search, for pages where the exact fact reliably lives at a stable URL.
# Empty until real official source URLs are identified (e.g. SBV's own rate
# page, GSO's CPI page); each entry: {"id", "kind", "url", "prompt"}.
#
# Only add URLs confirmed (or reasonably assumed, e.g. plain government stat
# pages) to work with TavilyExtract. customs.gov.vn was tested live and
# confirmed to need real browser rendering (Selenium) instead — do not add
# JS-heavy portal sites here; that's separate, deferred work.

SOURCES = []
