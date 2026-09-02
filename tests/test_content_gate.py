"""Offline, LLM-free tests for agent/content_gate.py — the first mocked/
offline test seam in the crawl layer (everything else in this project is
live-network-only by deliberate testing decision). That's appropriate here,
not a deviation from convention: check_content_usable() has zero network or
LLM dependency by design, so there's nothing to prove "for real" the way a
live crawl4ai/Groq call would need to be.

Fixtures below are real text captured during this project's own live
development (2026-09-01), not invented samples — see agent/content_gate.py's
own comments for where each came from.
"""

import agent.content_gate
import agent.graph
import agent.ocr
from agent.content_gate import check_content_usable, check_pdf_page_density
from agent.graph import _content_gate_multi_node, _content_gate_node

# Real excerpt from sbv_legal_directives_official's "CT 02_2026.pdf" — a
# scanned document with a broken OCR/font-encoding layer, confirmed live by
# manually opening the PDF.
GARBLED_SCAN_EXCERPT = (
    "ctrAm di6m tin dung tu dQng voi kho d[ li€u kh6ch hang, dt liQu md, dri "
    "liQu b€n thri ba vi m6 hinh ch6m tti6m 6 chri d$ng phet hien sdm vd img "
    "ph6, xir lf kip thoi, hiQu qui c6c cuQc t6n c6ng m4ng c6 th6 xiy ra."
)

# Real block page returned live from sbv.gov.vn (2026-09-01) — a genuine
# WAF/security-appliance rejection, HTTP 200, well past MIN_USABLE_CHARS.
BLOCK_PAGE_TEXT = (
    "The requested URL was rejected. Please consult with your administrator.  \n"
    "  \nYour support ID is: 4409962095025656360  \n  \n[[Go Back]](javascript:history.back();)"
)

# Real excerpt fetched live from vnba_banking_news (2026-09-01) — genuine
# Vietnamese prose, no corruption.
CLEAN_VIETNAMESE_TEXT = (
    "CQTT Hiệp hội Ngân hàng Việt Nam phát động thi đua giai đoạn 2026 - 2030: "
    "Quyết tâm đồng hành cùng mục tiêu tăng trưởng bền vững. Ngày 24/8/2026, Cơ "
    "quan Thường trực (CQTT) Hiệp hội Ngân hàng Việt Nam ban hành Công văn số "
    "481/CV-CQTT do Tổng Thư ký Đào Minh Tú ký nhằm phát động Phong trào thi đua "
    "giai đoạn 2026 - 2030 trong toàn thể cán bộ, người lao động."
)

# This project's own legitimate short alphanumeric codes — must never be
# treated as corrupted text, even though they mix letters and digits.
LEGIT_FINANCIAL_CODES_TEXT = (
    "Techcombank 3M26 Financial Statements published on 21/04/2026. CASA ratio "
    "for Q2 2026 rose versus H1 2025. FY2025 credit growth reached 9M2025 levels."
)


def test_rejects_near_empty_content():
    result = check_content_usable("too short")
    assert result["usable"] is False
    assert "near-empty" in result["reason"].lower()


def test_rejects_empty_or_none_content():
    for text in ["", "   ", None]:
        result = check_content_usable(text)
        assert result["usable"] is False


def test_rejects_known_block_page():
    result = check_content_usable(BLOCK_PAGE_TEXT)
    assert result["usable"] is False
    assert "block-page marker" in result["reason"].lower()


def test_rejects_corrupted_ocr_scan_text():
    # Real content, well past MIN_USABLE_CHARS, no block-page marker — only
    # the corrupted-token ratio should catch this.
    padded = GARBLED_SCAN_EXCERPT * 2  # ensure comfortably past the length floor
    result = check_content_usable(padded)
    assert result["usable"] is False
    assert "corrupted-text ratio" in result["reason"].lower()


def test_accepts_clean_vietnamese_content():
    result = check_content_usable(CLEAN_VIETNAMESE_TEXT)
    assert result["usable"] is True
    assert result["reason"] is None


def test_accepts_content_with_many_cdn_image_urls():
    """Regression guard for a real false positive (2026-09-01,
    bidv.com.vn/bidv/tin-tuc): markdown image URLs with UUID/hash CDN
    paths mix lowercase letters and digits just like real OCR corruption
    does, but they're URL noise, not prose — must not count toward the
    corrupted-token ratio."""
    text = (
        "![](https://bidv.com.vn/wps/wcm/connect/e6039a2a-a43f-4860-bbdb-cefbb2c3a3a7/"
        "Phat%2Bmai%2Btai%2Bsan.jpg?MOD=AJPERES&CACHEID=ROOTWORKSPACE-e6039a2a-a43f-4860-bbdb-cefbb2c3a3a7-mtpiRLd)\n\n"
        "BIDV Thủ Thiêm thông báo thu giữ tài sản bảo đảm của Ông NGÔ KHẢI MINH- Bà TRẦN NGỌC THÚY\n"
        "Đăng tải ngày 30/07/2026\n"
        "Ngân hàng TMCP Đầu tư và Phát triển Việt Nam – Chi nhánh Thủ Thiêm thông báo thu giữ tài "
        "sản để xử lý thu hồi nợ theo quy định."
    )
    result = check_content_usable(text)
    assert result["usable"] is True


def test_accepts_content_with_inline_data_uri_icons():
    """Regression guard for a real false positive (2026-09-02,
    ssi.com.vn/khach-hang-ca-nhan/bao-cao-nganh): nav-menu icons inlined as
    base64/percent-encoded `data:image/svg+xml;utf8,<svg...>` URIs mix
    lowercase letters and digits just like real OCR corruption does, but
    they're markup noise, not prose — same failure mode as the CDN-URL
    case above, different URL scheme."""
    text = (
        "[Đăng nhập](data:image/svg+xml;utf8,<svg%20xmlns='http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg'"
        "%20viewBox='0%200%20153.37%20166'><path%20d='M111.63%2082.16a3.9%203.9%200%200%200-1.19-2.8'/>"
        "<%2Fsvg>)\n\n"
        "Ngân hàng TMCP Kỹ Thương Việt Nam (TCB) công bố báo cáo tài chính Quý 2/2026, "
        "lợi nhuận trước thuế tăng 15,9% so với cùng kỳ năm trước."
    )
    result = check_content_usable(text)
    assert result["usable"] is True


def test_accepts_legit_financial_period_codes():
    """Regression guard: Q2/H1/FY2025/9M2025/3M26 mix letters and digits but
    must never be flagged as corrupted — this is exactly the false-positive
    risk the corrupted-token heuristic was designed around."""
    result = check_content_usable(LEGIT_FINANCIAL_CODES_TEXT)
    assert result["usable"] is True


def test_content_gate_node_passes_good_content():
    state = {"search_results": CLEAN_VIETNAMESE_TEXT, "url": "https://example.com"}
    update = _content_gate_node(state)
    assert update == {}


def test_content_gate_node_rejects_bad_content():
    state = {"search_results": BLOCK_PAGE_TEXT, "url": "https://example.com"}
    update = _content_gate_node(state)
    assert update["gate_passed"] is False
    assert update["gate_reason"].startswith("Content gate:")


class _FakePage:
    def __init__(self, text):
        self._text = text

    def extract_text(self):
        return self._text


class _FakePdfReader:
    def __init__(self, pages):
        self.pages = pages


def _fake_reader_factory(page_texts):
    return lambda _bytes_io: _FakePdfReader([_FakePage(t) for t in page_texts])


def test_check_pdf_page_density_flags_a_real_partial_scan_shape(monkeypatch):
    """Real numbers from the live calibration document (2026-09-02,
    bidv_financial_statements' actual filing): 57 pages, real text
    (2414 + 1254 chars) on the first 2, 0 chars on the other 55."""
    pages = [2414 * "x", 1254 * "x"] + [""] * 55
    monkeypatch.setattr(agent.content_gate, "PdfReader", _fake_reader_factory(pages))
    result = check_pdf_page_density(b"irrelevant, PdfReader is mocked")
    assert result["usable"] is False
    assert result["code"] == "partial_scan"
    assert "55/57" in result["reason"]


def test_check_pdf_page_density_accepts_a_dense_document(monkeypatch):
    pages = [800 * "x" for _ in range(12)]
    monkeypatch.setattr(agent.content_gate, "PdfReader", _fake_reader_factory(pages))
    result = check_pdf_page_density(b"irrelevant, PdfReader is mocked")
    assert result["usable"] is True
    assert result["code"] is None


def test_check_pdf_page_density_skips_short_documents(monkeypatch):
    """Below MIN_PAGES_FOR_DENSITY_CHECK, even an all-blank document is
    left alone — real risk of flagging a genuinely short, legitimate
    document (e.g. a 2-page notice) that just happens to render with no
    extractable text on one page."""
    pages = ["", "", ""]
    monkeypatch.setattr(agent.content_gate, "PdfReader", _fake_reader_factory(pages))
    result = check_pdf_page_density(b"irrelevant, PdfReader is mocked")
    assert result["usable"] is True


def test_check_pdf_page_density_treats_unparseable_bytes_as_usable():
    """A malformed/undownloadable PDF isn't this function's problem to
    catch — check_content_usable() already caught near-empty/corrupted
    text upstream; this just must not raise and crash content_gate."""
    result = check_pdf_page_density(b"not a real pdf file")
    assert result["usable"] is True


def test_content_gate_node_recovers_a_scan_via_ocr_fallback(monkeypatch):
    """Single-fetch-path mirror of the multi-node OCR-recovery test: a
    "scan"-coded flattened result with exactly one PDF piece gets one
    shot at OCR recovery before being rejected."""
    monkeypatch.setattr(agent.ocr, "ensure_ocr_text", lambda source_id, url: CLEAN_VIETNAMESE_TEXT)
    garbled = GARBLED_SCAN_EXCERPT * 2
    state = {
        "search_results": f"listing text\n\n--- Full content of https://example.com/scan.pdf ---\n{garbled}",
        "pdf_texts": [("https://example.com/scan.pdf", garbled)],
        "url": "https://example.com",
        "source_id": "bidv_financial_statements",
    }
    update = _content_gate_node(state)
    assert "gate_passed" not in update
    assert CLEAN_VIETNAMESE_TEXT in update["search_results"]
    assert garbled not in update["search_results"]


def test_content_gate_node_recovers_a_partial_scan_via_ocr_fallback(monkeypatch):
    """Content that reads as clean, real prose (so check_content_usable()
    passes it) but whose PDF is mostly blank pages (check_pdf_page_density())
    also gets one shot at OCR recovery — BIDV's actual live failure shape."""
    cover_letter = CLEAN_VIETNAMESE_TEXT
    monkeypatch.setattr(agent.ocr, "download_pdf_bytes", lambda url: b"fake pdf bytes")
    monkeypatch.setattr(
        agent.graph, "check_pdf_page_density",
        lambda pdf_bytes: {"usable": False, "reason": "55/57 pages blank", "code": "partial_scan"},
    )
    monkeypatch.setattr(agent.ocr, "ensure_ocr_text", lambda source_id, url: LEGIT_FINANCIAL_CODES_TEXT)
    state = {
        "search_results": f"listing text\n\n--- Full content of https://example.com/report.pdf ---\n{cover_letter}",
        "pdf_texts": [("https://example.com/report.pdf", cover_letter)],
        "url": "https://example.com",
        "source_id": "bidv_financial_statements",
    }
    update = _content_gate_node(state)
    assert "gate_passed" not in update
    assert LEGIT_FINANCIAL_CODES_TEXT in update["search_results"]
    assert cover_letter not in update["search_results"]


def test_content_gate_node_rejects_partial_scan_when_ocr_does_not_help(monkeypatch):
    cover_letter = CLEAN_VIETNAMESE_TEXT
    monkeypatch.setattr(agent.ocr, "download_pdf_bytes", lambda url: b"fake pdf bytes")
    monkeypatch.setattr(
        agent.graph, "check_pdf_page_density",
        lambda pdf_bytes: {"usable": False, "reason": "55/57 pages blank", "code": "partial_scan"},
    )
    monkeypatch.setattr(agent.ocr, "ensure_ocr_text", lambda source_id, url: None)
    state = {
        "search_results": f"listing text\n\n--- Full content of https://example.com/report.pdf ---\n{cover_letter}",
        "pdf_texts": [("https://example.com/report.pdf", cover_letter)],
        "url": "https://example.com",
        "source_id": "bidv_financial_statements",
    }
    update = _content_gate_node(state)
    assert update["gate_passed"] is False
    assert "55/57 pages blank" in update["gate_reason"]


def test_content_gate_multi_node_drops_only_the_bad_piece(monkeypatch):
    # ensure_ocr_text() hits a real network call + real, billed Mistral
    # spend when it actually recovers something — stubbed to None (OCR
    # attempted, nothing recovered) so this test stays what its name says:
    # the drop-the-bad-piece behavior, isolated from the OCR fallback
    # itself (covered separately below).
    monkeypatch.setattr(agent.ocr, "ensure_ocr_text", lambda source_id, url: None)
    state = {
        "pdf_texts": [
            ("https://example.com/good.pdf", CLEAN_VIETNAMESE_TEXT),
            ("https://example.com/scan.pdf", GARBLED_SCAN_EXCERPT * 2),
        ],
        "search_results": "",
        "url": "https://example.com",
    }
    update = _content_gate_multi_node(state)
    assert update["pdf_texts"] == [("https://example.com/good.pdf", CLEAN_VIETNAMESE_TEXT)]
    assert "gate_passed" not in update  # untouched — the item overall still succeeds


def test_content_gate_multi_node_falls_back_to_usable_list_text(monkeypatch):
    monkeypatch.setattr(agent.ocr, "ensure_ocr_text", lambda source_id, url: None)
    state = {
        "pdf_texts": [("https://example.com/scan.pdf", GARBLED_SCAN_EXCERPT * 2)],
        "search_results": CLEAN_VIETNAMESE_TEXT,
        "url": "https://example.com",
    }
    update = _content_gate_multi_node(state)
    assert update["pdf_texts"] == []
    assert "gate_passed" not in update  # list text is usable, so the item still proceeds


def test_content_gate_multi_node_rejects_when_nothing_survives(monkeypatch):
    monkeypatch.setattr(agent.ocr, "ensure_ocr_text", lambda source_id, url: None)
    state = {
        "pdf_texts": [("https://example.com/scan.pdf", GARBLED_SCAN_EXCERPT * 2)],
        "search_results": BLOCK_PAGE_TEXT,
        "url": "https://example.com",
    }
    update = _content_gate_multi_node(state)
    assert update["gate_passed"] is False
    assert update["pdf_texts"] == []


def test_content_gate_multi_node_recovers_a_scan_via_ocr_fallback(monkeypatch):
    """The new automatic-OCR path: a "scan"-coded piece isn't dropped
    outright — ensure_ocr_text() gets one shot at recovering it first, and
    a genuinely usable result is kept (with the OCR text replacing the
    original garbled extraction), same as any other good piece."""
    monkeypatch.setattr(agent.ocr, "ensure_ocr_text", lambda source_id, url: CLEAN_VIETNAMESE_TEXT)
    state = {
        "pdf_texts": [("https://example.com/scan.pdf", GARBLED_SCAN_EXCERPT * 2)],
        "search_results": "",
        "url": "https://example.com",
        "source_id": "sbv_legal_directives_official",
    }
    update = _content_gate_multi_node(state)
    assert update["pdf_texts"] == [("https://example.com/scan.pdf", CLEAN_VIETNAMESE_TEXT)]
    assert "gate_passed" not in update


def test_content_gate_multi_node_drops_piece_when_ocr_recovery_is_still_unusable(monkeypatch):
    """A piece must not be trusted just because OCR ran — if the OCR
    result itself still fails content_gate (e.g. came back empty), it's
    dropped exactly like an OCR call that failed outright."""
    monkeypatch.setattr(agent.ocr, "ensure_ocr_text", lambda source_id, url: "")
    state = {
        "pdf_texts": [("https://example.com/scan.pdf", GARBLED_SCAN_EXCERPT * 2)],
        "search_results": BLOCK_PAGE_TEXT,
        "url": "https://example.com",
        "source_id": "sbv_legal_directives_official",
    }
    update = _content_gate_multi_node(state)
    assert update["gate_passed"] is False
    assert update["pdf_texts"] == []
