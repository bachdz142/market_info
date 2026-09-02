import logging
import re
from io import BytesIO

from pypdf import PdfReader

logger = logging.getLogger(__name__)

# A gate distinct from agent/gate.py's checkpoint_gate: that one validates
# the *query* before any fetch happens; this one validates *fetched content*
# after crawl4ai returns "successfully" but before a real LLM call gets
# spent structuring it. Two different concepts (see CONTEXT.md) — this one
# exists because crawl4ai's own success/failure signal isn't enough: a WAF
# rejection page or a scanned PDF with a broken OCR layer both come back as
# a "successful" fetch with substantial text, just not usable text.

# Mirrors agent/crawler.py's _fetch_pdf_text near-empty threshold — content
# below this is almost certainly a stub/error page, not real content.
MIN_USABLE_CHARS = 50

# Confirmed live (2026-09-01, sbv.gov.vn): a real WAF/security-appliance
# rejection page returned with HTTP 200 and ~160 chars of real text — well
# past MIN_USABLE_CHARS, so it needs its own check. Fingerprinted verbatim
# from the actual page hit; kept as substring matches (not full-page
# equality) since the surrounding page chrome can vary.
BLOCK_PAGE_MARKERS = [
    "the requested url was rejected",
    "blocked by anti-bot protection",
]

# Corrupted-OCR/font-encoding detection: a token mixing a lowercase letter
# with a digit (e.g. "kh6ch", "di6m") almost never occurs in real prose —
# but this project's own legitimate content constantly uses short
# alphanumeric codes (Q2, H1, FY2025, 9M2025, 3M26), which are always
# upper-case-led, never lowercase+digit. Validated live (2026-09-01)
# against a real scanned/garbled PDF excerpt (sbv_legal_directives_official's
# "CT 02_2026.pdf") versus real clean fetches from several other sources
# that same day: garbled ratio 0.23, clean ratio 0.0-0.006 (a small amount
# of markdown-conversion word-gluing noise is normal and expected, e.g.
# "2026Reference" from a missing space in the source HTML) — 0.05 sits
# comfortably clear of both real measurements.
MAX_CORRUPTED_TOKEN_RATIO = 0.05

# Partial-scan detection: a PDF with real text on only its first couple of
# pages and nothing on the rest — a distinct failure shape from "scan"
# above (which needs some OCR/font-encoding layer to garble; a genuinely
# blank page produces zero corrupted tokens, not a high ratio, since
# there's no text to corrupt). check_content_usable() alone can't catch
# this: the extracted text (just the real pages) reads as perfectly clean
# prose. Needs the PDF's actual page count, which only
# check_pdf_page_density() below has access to (via a fresh download +
# pypdf, not the already-flattened text check_content_usable() works
# from) — a separate function, not folded into check_content_usable(),
# since it needs different inputs (raw PDF bytes, not just extracted
# text) and only makes sense for PDF-backed sources.
#
# Calibrated against one real, live measurement (2026-09-02,
# bidv_financial_statements' actual filing at the time: "20260818 - BID -
# CBTT BCTC HN ban nien da duoc soat xet.pdf"): 57 pages, real text
# (2414 + 1254 chars) on exactly the first 2, 0 chars on all 55 remaining
# pages — a 96.5% blank-page ratio. MAX_BLANK_PAGE_RATIO sits well below
# that (comfortable margin against a false positive on some future
# document with a handful of legitimately blank pages, e.g. a section
# separator) while still catching this shape decisively.
MIN_PAGES_FOR_DENSITY_CHECK = 5
MIN_CHARS_PER_PAGE = 20
MAX_BLANK_PAGE_RATIO = 0.6


def check_pdf_page_density(pdf_bytes: bytes) -> dict:
    """A second, PDF-specific gate alongside check_content_usable() — call
    it after that one passes, when the content came from a PDF (i.e. the
    caller has the PDF's raw bytes available, not just its extracted
    text). Returns the same {"usable", "reason", "code"} shape; "code" is
    "partial_scan" or None. A malformed/unreadable PDF is treated as
    usable (returns {"usable": True, ...}) — this function's only job is
    catching the specific blank-pages shape, not general PDF validity;
    check_content_usable() already caught near-empty/corrupted text
    upstream of this."""
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        page_count = len(reader.pages)
        if page_count < MIN_PAGES_FOR_DENSITY_CHECK:
            return {"usable": True, "reason": None, "code": None}
        blank_pages = sum(
            1 for page in reader.pages if len((page.extract_text() or "").strip()) < MIN_CHARS_PER_PAGE
        )
    except Exception:
        logger.exception("check_pdf_page_density: could not parse PDF, skipping this check")
        return {"usable": True, "reason": None, "code": None}

    blank_ratio = blank_pages / page_count
    if blank_ratio > MAX_BLANK_PAGE_RATIO:
        reason = (
            f"{blank_pages}/{page_count} pages ({blank_ratio:.1%}) have under "
            f"{MIN_CHARS_PER_PAGE} chars of extractable text (likely a partial "
            "scan — real text on a few pages, scanned images for the rest)."
        )
        logger.warning("Content gate rejected: %s", reason)
        return {"usable": False, "reason": reason, "code": "partial_scan"}

    return {"usable": True, "reason": None, "code": None}


URL_RE = re.compile(r"(?:https?|data):\S+")


def _corrupted_token_ratio(text: str) -> float:
    # Strip URLs first: markdown image/link syntax embeds full URLs
    # (`![](https://.../wps/wcm/connect/e6039a2a-a43f-.../file.jpg?...)`),
    # and CDN paths are full of UUID/hash fragments that mix lowercase
    # letters and digits exactly like real OCR corruption does — but
    # they're URL noise, not prose. Confirmed live (2026-09-01,
    # bidv.com.vn/bidv/tin-tuc): a genuine, clean, dated news article
    # scored 0.054 (just over threshold, a false rejection) purely from
    # its embedded image URLs; the same text scored 0.003 with URLs
    # stripped.
    #
    # Also covers inline data: URIs (`data:image/svg+xml;utf8,<svg...>`),
    # the same noise source under a different scheme — confirmed live
    # (2026-09-02, ssi.com.vn's sector-reports page) an SVG-icon-heavy nav
    # menu inlined as base64/percent-encoded data: URIs scored 0.074 (a
    # false rejection) purely from that encoded markup, not real corrupted
    # text.
    text = URL_RE.sub(" ", text)
    tokens = re.findall(r"\b\w+\b", text)
    if not tokens:
        return 0.0
    corrupted = [t for t in tokens if re.search(r"[a-z]", t) and re.search(r"\d", t)]
    return len(corrupted) / len(tokens)


def check_content_usable(text: str) -> dict:
    """Deterministic, LLM-free check that fetched content is real and
    structurable — no model call, so this can run on every fetch for free.
    Returns {"usable": bool, "reason": Optional[str], "code": Optional[str]},
    mirroring agent/gate.py's checkpoint_gate return shape for "usable"/
    "reason". "code" is the machine-readable reason ("near_empty",
    "block_page", "scan", or None when usable) — added so agent/graph.py's
    automatic OCR fallback (see agent/ocr.py's ensure_ocr_text()) can key
    off a stable value instead of string-matching "reason"'s human prose.
    "scan" is safe to auto-OCR: it's the one rejection this function
    produces that's validated against a real scanned document
    (sbv_legal_directives_official's "CT 02_2026.pdf"); "near_empty" and
    "block_page" both fire for reasons OCR can't fix (a WAF rejection page,
    a genuine fetch failure) and would just waste a real, billed OCR job.
    (check_pdf_page_density() below produces a third OCR-eligible code,
    "partial_scan", for a different failure shape this function can't see
    — see that function's own docstring.)"""
    stripped = (text or "").strip()

    if len(stripped) < MIN_USABLE_CHARS:
        reason = f"Near-empty content ({len(stripped)} chars)."
        logger.warning("Content gate rejected: %s", reason)
        return {"usable": False, "reason": reason, "code": "near_empty"}

    lowered = stripped.lower()
    for marker in BLOCK_PAGE_MARKERS:
        if marker in lowered:
            reason = f"Content matches a known block-page marker: {marker!r}."
            logger.warning("Content gate rejected: %s", reason)
            return {"usable": False, "reason": reason, "code": "block_page"}

    ratio = _corrupted_token_ratio(stripped)
    if ratio > MAX_CORRUPTED_TOKEN_RATIO:
        reason = (
            f"Corrupted-text ratio {ratio:.3f} exceeds {MAX_CORRUPTED_TOKEN_RATIO} "
            "(likely a scan with a broken OCR/font-encoding layer)."
        )
        logger.warning("Content gate rejected: %s", reason)
        return {"usable": False, "reason": reason, "code": "scan"}

    return {"usable": True, "reason": None, "code": None}
