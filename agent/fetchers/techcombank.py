from typing import List, Tuple

from agent.crawler import _fetch_annual_report_page_ranges
from agent.fetcher_registry import register_fetcher

# Layer 3 annual report/AGM work (.scratch/layer3-annual-reports/spec.md) —
# parked mid-discovery in an earlier session on exactly this problem:
# Techcombank's own investors page links directly to its full 2025 annual
# report PDF (confirmed live: 196 pages, ~804K chars of real extractable
# text, not a scan). Blindly chunking the whole thing at MAX_CHUNK_CHARS
# would produce ~67 pieces — the "chapter-boundary slicing not yet solved"
# problem this was parked on. Most of that text is either generic
# boilerplate (brand history, About Us) or a full audited
# financial-statements appendix that duplicates techcombank_vas_statements
# (Layer 1) almost entirely.
#
# Found the real chapter boundaries by hand (2026-09-03): the PDF's own
# table of contents (page 1) lists page numbers for each chapter, but the
# document is laid out as a 2-printed-page spread per PDF page — confirmed
# by cross-checking the TOC's "Glossary, page 386" against a page-by-page
# scan, which lands it exactly on PDF page 193 (386 / 2). Scoped to the
# two chapters that match this source's actual target content (leadership
# statements, technology disclosures — per the spec's own priority list):
# PDF pages 4-11 (Chapter 1 — Chairman's message, CEO Report) and 50-71
# (Chapter 4 — Data & Analytics / Digital Office / Technology(IT) /
# Talent(HR), i.e. the transformation/technology disclosures). Chapter 2
# (About Us — generic brand history), Chapter 5 (Governance/Risk/
# Culture/Sustainability — lower priority per the spec, and large), and
# Chapter 6 (audited financial statements — redundant with Layer 1) are
# deliberately excluded. Combined: ~104K real chars, ~9 chunks at
# MAX_CHUNK_CHARS — a real, deliberate reduction, not an arbitrary
# shortcut, and small enough to actually run in reasonable time.
TECHCOMBANK_ANNUAL_REPORT_URL = "https://techcombank.com/content/dam/techcombank/public-site/documents/techcombank-2025-annual-report-eng-vf.pdf"
TECHCOMBANK_ANNUAL_REPORT_PAGE_RANGES = [(4, 11), (50, 71)]  # 0-indexed, inclusive


@register_fetcher(TECHCOMBANK_ANNUAL_REPORT_URL, "parts")
async def _fetch_techcombank_annual_report_parts() -> Tuple[str, List[Tuple[str, str]]]:
    return await _fetch_annual_report_page_ranges(
        TECHCOMBANK_ANNUAL_REPORT_URL, TECHCOMBANK_ANNUAL_REPORT_PAGE_RANGES, "Techcombank"
    )
