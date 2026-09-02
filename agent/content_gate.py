import logging
import re

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
    Returns {"usable": bool, "reason": Optional[str]}, mirroring
    agent/gate.py's checkpoint_gate return shape for the same reason: a
    uniform gate/reason pair the rest of the pipeline already knows how to
    report."""
    stripped = (text or "").strip()

    if len(stripped) < MIN_USABLE_CHARS:
        reason = f"Near-empty content ({len(stripped)} chars)."
        logger.warning("Content gate rejected: %s", reason)
        return {"usable": False, "reason": reason}

    lowered = stripped.lower()
    for marker in BLOCK_PAGE_MARKERS:
        if marker in lowered:
            reason = f"Content matches a known block-page marker: {marker!r}."
            logger.warning("Content gate rejected: %s", reason)
            return {"usable": False, "reason": reason}

    ratio = _corrupted_token_ratio(stripped)
    if ratio > MAX_CORRUPTED_TOKEN_RATIO:
        reason = (
            f"Corrupted-text ratio {ratio:.3f} exceeds {MAX_CORRUPTED_TOKEN_RATIO} "
            "(likely a scan with a broken OCR/font-encoding layer)."
        )
        logger.warning("Content gate rejected: %s", reason)
        return {"usable": False, "reason": reason}

    return {"usable": True, "reason": None}
