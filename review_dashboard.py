"""Phase 1 review dashboard (grilled 2026-09-02, see .scratch or session
notes) — regenerates a single local HTML file showing, per configured
source, the raw fetched content next to the LLM's structured extraction,
for manually eyeballing correctness. Not a product UI.

Reads only from the existing data/raw_content.csv + data/signals.jsonl
logs (joined by run_id) — no new fetch, no new LLM call, safe/free to
re-run any time. Every one of agent/sources.py's configured sources is
always listed, even with zero runs yet ("not yet run" placeholder) — per
CONTEXT.md's spot-checked vs. live-verified distinction, most sources
have only been spot-checked (a live crawl4ai fetch) so far, not
live-verified (a real fetch -> structure run); this dashboard is exactly
how you tell the two apart at a glance.

Each source with data defaults to its most recent run; a per-source
dropdown switches to any earlier run instead, if more than one exists.

Usage: python review_dashboard.py
Output: review_dashboard.html (repo root) — open directly in a browser.
"""

import csv
import html
import json
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

from agent.graph import STRUCTURE_SYSTEM_PROMPT
from agent.sources import SOURCES

# Default 131072-byte field limit is too small for a full OCR'd PDF's raw
# content (BIDV's is ~190K chars in one CSV field) — raise it rather than
# truncate real data.
csv.field_size_limit(sys.maxsize)

ROOT = Path(__file__).resolve().parent
RAW_CONTENT_CSV = ROOT / "data" / "raw_content.csv"
SIGNALS_JSONL = ROOT / "data" / "signals.jsonl"
OCR_CACHE_DIR = ROOT / "data" / "ocr_cache"
OUT_PATH = ROOT / "review_dashboard.html"

# Content-shape / Layer classification — a navigation aid here (groups
# sections so similar sources are reviewed together), matching this
# session's own source-ledger breakdown. Not the Phase 2 prompt-grouping
# axis itself (that's a separate change to agent/sources.py).
_LAYERS = [
    ("Layer 1 — Quantitative bank benchmarks", [
        "techcombank_vas_statements", "bidv_financial_statements", "acb_financial_statements",
        "mbb_financial_statements", "sbv_portal_statistics", "iav_bancassurance",
    ]),
    ("Layer 2 — CVP, offerings & segment sales", [
        "bidv_card_promotions", "bidv_personal_fee_schedule", "acb_promotions", "vpbank_news",
        "vpbank_fee_documents", "vcb_promotions", "acb_fee_schedule", "mbbank_fee_schedule",
        "mbbank_news", "vcb_fee_schedule", "techcombank_mobile_release_notes",
        "vcb_digibank_release_notes", "bidv_smartbanking_release_notes", "mbbank_app_release_notes",
        "acb_one_release_notes", "vpbank_neo_release_notes",
    ]),
    ("Layer 3 — Strategic profile per bank", [
        "banking_review_journal", "finance_review_journal", "ssi_banking_sector_report",
        "vcbs_banking_sector_report", "bsc_mbb_report", "decisionlab_bank_satisfaction_rankings",
        "qandme_online_banking_usage",
    ]),
    ("Layer 4 — Macro, government & PEST", [
        "vietnam_cpi_official", "sbv_press_releases_official", "sbv_legal_directives_official",
        "nso_data_and_statistics_official", "nso_gdp_key_indicators", "nso_vhlss_income",
        "nso_vhlss_expenditure", "chinhphu_legal_documents_official", "vnba_banking_news",
        "sbv_circular_08_2026_tt_nhnn", "sbv_official_letter_4551_nhnn_cstt",
        "sbv_circular_21_2025_tt_nhnn", "decree_94_2025_nd_cp_fintech_sandbox",
        "resolution_57_nq_tw_digital_transformation", "resolution_110_2025_ubtvqh15_pit_deduction",
        "pit_law_109_2025_qh15", "decision_21_2025_qd_ttg_green_taxonomy",
        "sbv_circular_17_2022_tt_nhnn_environmental_risk",
    ]),
]
LAYER_OF = {sid: name for name, ids in _LAYERS for sid in ids}
SIGNAL_METADATA_COLS = ["reference_period", "fact_or_opinion", "confidence"]


def _short_layer(layer_name: str) -> str:
    return layer_name.split(" — ")[0]  # "Layer 1 — Quantitative..." -> "Layer 1"


def _description(source: dict) -> str:
    """A one-line "what is this" scanning aid — deliberately NOT a
    restatement of the per-source prompt (that's its own column) — just
    Layer + kind + which site it actually comes from."""
    domain = urlparse(source.get("url") or "").netloc or "—"
    layer = _short_layer(LAYER_OF.get(source["id"], "?"))
    return f"{layer} · {source.get('kind', '')} · {domain}"


def _ocr_flag(source_id: str, latest_run: dict) -> tuple:
    """(css_class, label) — derived only from real, checkable evidence,
    never a hardcoded per-source guess:
    - "used": data/ocr_cache/ has a cached recovery keyed to this exact
      source_id (agent/ocr.py's ensure_ocr_text() cache — proof OCR
      actually ran and produced something for this source before).
    - "flagged": the latest run's own gate_reason mentions a scan/partial
      scan (content_gate.py's "scan"/"partial_scan" codes) but no cache
      entry exists yet — flagged, not yet recovered.
    - "": no evidence either way."""
    if OCR_CACHE_DIR.is_dir() and any(OCR_CACHE_DIR.glob(f"{source_id}_*.md")):
        return "ocr-used", "OCR: used"
    reason = (latest_run or {}).get("gate_reason") or ""
    if "scan" in reason.lower():
        return "ocr-flagged", "OCR: flagged"
    return "", ""


def _load_raw_content() -> dict:
    by_id = defaultdict(list)
    if RAW_CONTENT_CSV.is_file():
        with RAW_CONTENT_CSV.open(newline="") as f:
            for row in csv.DictReader(f):
                by_id[row["id"]].append(row)
    return by_id


def _load_signals() -> dict:
    by_id = defaultdict(list)
    if SIGNALS_JSONL.is_file():
        with SIGNALS_JSONL.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                by_id[rec.get("id")].append(rec)
    return by_id


def _merge_runs(source_id: str, raw_by_id: dict, signals_by_id: dict) -> list:
    """One entry per run_id for this source, newest first — raw_content
    and the structured result are logged by two separate append calls
    (service.py's _run_item), so either can exist without the other;
    merge rather than assume both are always present together."""
    runs: dict = {}
    for row in raw_by_id.get(source_id, []):
        runs.setdefault(row["run_id"], {})["triggered_at"] = row["triggered_at"]
        runs[row["run_id"]]["raw_content"] = row["raw_content"]
    for rec in signals_by_id.get(source_id, []):
        run_id = rec.get("run_id")
        if not run_id:
            # A handful of very early log lines predate run_id/triggered_at
            # being added to the record shape — skip rather than crash;
            # that data has no run to join against anyway.
            continue
        runs.setdefault(run_id, {})["triggered_at"] = rec.get("triggered_at", "")
        runs[run_id].update({
            "gate_passed": rec.get("gate_passed"),
            "gate_reason": rec.get("gate_reason"),
            "error": rec.get("error"),
            "result": rec.get("result"),
        })
    ordered = sorted(runs.items(), key=lambda kv: kv[1].get("triggered_at") or "", reverse=True)
    return [{"run_id": rid, **data} for rid, data in ordered]


def _signals_table_html(result: dict) -> str:
    signals = (result or {}).get("signals") or []
    if not signals:
        return '<p class="empty">No signals extracted.</p>'
    head = "<tr><th>Type</th><th>Summary</th>" + "".join(f"<th>{c}</th>" for c in SIGNAL_METADATA_COLS) + "</tr>"
    rows = []
    for s in signals:
        cells = "".join(f"<td>{html.escape(str(s.get(c, '') or ''))}</td>" for c in SIGNAL_METADATA_COLS)
        rows.append(
            f"<tr><td class='sigtype'>{html.escape(s.get('signal_type', ''))}</td>"
            f"<td>{html.escape(s.get('summary', ''))}</td>{cells}</tr>"
        )
    return f"<table class='sigtable'><thead>{head}</thead><tbody>{''.join(rows)}</tbody></table>"


def _run_panel_html(run: dict, source: dict) -> str:
    raw = run.get("raw_content") or ""
    result = run.get("result")
    gate_passed = run.get("gate_passed")
    gate_reason = run.get("gate_reason")
    error = run.get("error")

    raw_html = (
        f"<details open><summary>{len(raw):,} chars</summary>"
        f"<pre class='rawbox'>{html.escape(raw) if raw else '(empty)'}</pre></details>"
        if raw else "<p class='empty'>No raw content logged for this run.</p>"
    )

    prompt_text = source.get("prompt") or ""
    prompt_html = (
        f"<details open><summary>{len(prompt_text):,} chars</summary>"
        f"<pre class='promptbox'>{html.escape(prompt_text)}</pre></details>"
        if prompt_text else "<p class='empty'>No per-source prompt (search-based topic?).</p>"
    )

    status_bits = []
    if gate_passed is False:
        status_bits.append(f"<div class='status warn'>Gate rejected: {html.escape(gate_reason or '')}</div>")
    if error:
        status_bits.append(f"<div class='status err'>Error: {html.escape(error)}</div>")
    status_html = "".join(status_bits)

    if result is not None:
        extracted_html = (
            _signals_table_html(result)
            + f"<details class='fulljson'><summary>Full JSON</summary>"
              f"<pre>{html.escape(json.dumps(result, indent=2, ensure_ascii=False))}</pre></details>"
        )
    elif gate_passed is False:
        extracted_html = "<p class='empty'>Gate-rejected before structuring — no extraction attempted.</p>"
    elif error:
        extracted_html = "<p class='empty'>Structuring raised an error — no result.</p>"
    else:
        extracted_html = "<p class='empty'>No extraction result for this run.</p>"

    return (
        f"<div class='panel'>{status_html}"
        f"<div class='cols'>"
        f"<div class='col'><h4>Raw (pre-LLM)</h4>{raw_html}</div>"
        f"<div class='col'><h4>Prompt (per-source)</h4>{prompt_html}</div>"
        f"<div class='col'><h4>Extracted</h4>{extracted_html}</div>"
        f"</div></div>"
    )


def _head_badges(source: dict, ocr_class: str, ocr_label: str) -> str:
    sid = source["id"]
    url = source.get("url") or ""
    link_badge = f"<a class='badge link' href='{html.escape(url)}' target='_blank' rel='noopener'>↗ link</a>" if url else ""
    ocr_badge = f"<span class='badge {ocr_class}'>{ocr_label}</span>" if ocr_label else ""
    return (
        f"<code class='sid'>{sid}</code>"
        f"{link_badge}"
        f"<span class='badge desc'>{html.escape(_description(source))}</span>"
        f"<span class='badge kind'>{source.get('kind', '')}</span>"
        f"{ocr_badge}"
    )


def _source_section_html(source: dict, raw_by_id: dict, signals_by_id: dict) -> str:
    sid = source["id"]
    runs = _merge_runs(sid, raw_by_id, signals_by_id)

    if not runs:
        ocr_class, ocr_label = _ocr_flag(sid, None)
        prompt_text = source.get("prompt") or ""
        prompt_html = (
            f"<details><summary>{len(prompt_text):,} chars</summary>"
            f"<pre class='promptbox'>{html.escape(prompt_text)}</pre></details>"
            if prompt_text else ""
        )
        return (
            f"<section class='source notrun' id='{sid}'>"
            f"<div class='src-head'>{_head_badges(source, ocr_class, ocr_label)}"
            f"<span class='badge notrun-badge'>not yet run</span></div>"
            f"<p class='empty'>Spot-checked only (fetch confirmed) — never run through structuring. "
            f"No raw content or extraction logged for this source.</p>{prompt_html}</section>"
        )

    ocr_class, ocr_label = _ocr_flag(sid, runs[0])
    options = "".join(
        f"<option value='{i}'{' selected' if i == 0 else ''}>{html.escape(r['triggered_at'])}"
        f"{' (latest)' if i == 0 else ''}</option>"
        for i, r in enumerate(runs)
    )
    panels = "".join(
        f"<div class='runpanel' data-idx='{i}'{'' if i == 0 else ' hidden'}>{_run_panel_html(r, source)}</div>"
        for i, r in enumerate(runs)
    )
    picker = (
        f"<select class='runpicker' onchange=\"selectRun('{sid}', this.value)\">{options}</select>"
        if len(runs) > 1 else f"<span class='onerun'>{html.escape(runs[0]['triggered_at'])}</span>"
    )

    return (
        f"<section class='source' id='{sid}'>"
        f"<div class='src-head'>{_head_badges(source, ocr_class, ocr_label)}"
        f"<span class='badge runs'>{len(runs)} run{'s' if len(runs) != 1 else ''}</span>"
        f"{picker}</div>{panels}</section>"
    )


def build() -> str:
    raw_by_id = _load_raw_content()
    signals_by_id = _load_signals()

    have_data = sum(1 for s in SOURCES if _merge_runs(s["id"], raw_by_id, signals_by_id))
    total = len(SOURCES)

    layer_sections = []
    for layer_name, ids in _LAYERS:
        sources_in_layer = [s for s in SOURCES if s["id"] in ids]
        body = "".join(_source_section_html(s, raw_by_id, signals_by_id) for s in sources_in_layer)
        layer_sections.append(f"<h2>{layer_name}</h2>{body}")

    body_html = "".join(layer_sections)

    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<title>Review Dashboard</title>
<style>
body {{ font-family: -apple-system, "Segoe UI", sans-serif; background:#f4f5f6; color:#1a1f24; margin:0; padding:1.5rem 2rem 4rem; }}
h1 {{ font-size:1.4rem; margin-bottom:.2rem; }}
.stats {{ color:#555; font-size:.9rem; margin-bottom:1.5rem; }}
h2 {{ font-size:1.05rem; border-bottom:2px solid #ccc; padding-bottom:.3rem; margin-top:2.2rem; }}
section.source {{ background:#fff; border:1px solid #ddd; border-radius:6px; margin:.8rem 0; padding:.8rem 1rem; }}
section.notrun {{ background:#fafafa; opacity:.7; }}
.src-head {{ display:flex; align-items:center; gap:.6rem; flex-wrap:wrap; }}
.sid {{ font-family: ui-monospace, monospace; font-weight:600; font-size:.92rem; }}
.badge {{ font-size:.7rem; padding:.15rem .5rem; border-radius:999px; background:#e8eaed; color:#444; }}
.badge.notrun-badge {{ background:#f0d9a8; color:#7a5200; }}
.runpicker {{ margin-left:auto; font-size:.8rem; }}
.onerun {{ margin-left:auto; font-size:.78rem; color:#777; }}
.cols {{ display:grid; grid-template-columns:1fr 1fr 1fr; gap:1rem; margin-top:.6rem; }}
.col h4 {{ margin:.2rem 0 .3rem; font-size:.8rem; text-transform:uppercase; letter-spacing:.04em; color:#666; }}
.rawbox, .promptbox {{ max-height:320px; overflow:auto; background:#f7f7f8; border:1px solid #e5e5e5; border-radius:4px; padding:.6rem; font-size:.78rem; white-space:pre-wrap; word-break:break-word; }}
.promptbox {{ background:#f5f8fc; border-color:#dbe6f3; }}
.sigtable {{ width:100%; border-collapse:collapse; font-size:.78rem; }}
.sigtable th, .sigtable td {{ text-align:left; padding:.3rem .4rem; border-bottom:1px solid #eee; vertical-align:top; }}
.sigtype {{ font-family: ui-monospace, monospace; white-space:nowrap; }}
.fulljson pre {{ max-height:280px; overflow:auto; font-size:.72rem; background:#f7f7f8; border:1px solid #e5e5e5; border-radius:4px; padding:.6rem; }}
.empty {{ color:#999; font-size:.82rem; font-style:italic; }}
.status {{ font-size:.78rem; padding:.35rem .6rem; border-radius:4px; margin-bottom:.4rem; }}
.status.warn {{ background:#fff3cd; color:#7a5200; }}
.status.err {{ background:#fbdada; color:#8a1c1c; }}
.badge.link {{ background:#dbe9fb; color:#1a4d8f; text-decoration:none; }}
.badge.link:hover {{ text-decoration:underline; }}
.badge.desc {{ background:#eef1f4; color:#555; }}
.badge.ocr-used {{ background:#d9f0d9; color:#1e6b1e; }}
.badge.ocr-flagged {{ background:#f8dede; color:#8a1c1c; }}
.syspromptblock {{ background:#fff; border:1px solid #ddd; border-radius:6px; padding:.8rem 1rem; margin-bottom:1.2rem; }}
.syspromptblock summary {{ cursor:pointer; font-size:.85rem; font-weight:600; }}
.syspromptblock .filepath {{ font-family: ui-monospace, monospace; font-weight:400; color:#666; font-size:.78rem; }}
.syspromptblock pre {{ margin-top:.6rem; background:#f7f7f8; border:1px solid #e5e5e5; border-radius:4px; padding:.6rem; font-size:.78rem; white-space:pre-wrap; }}
[hidden] {{ display:none !important; }}
</style></head>
<body>
<h1>Review Dashboard</h1>
<p class="stats">{have_data} of {total} sources have at least one run logged &middot; {total - have_data} not yet run (spot-checked only, no structuring pass yet)</p>
<details class="syspromptblock">
<summary>Shared system prompt <span class="filepath">(agent/graph.py — STRUCTURE_SYSTEM_PROMPT)</span></summary>
<p class="empty">Identical for every source below — defines the output contract (signal_type taxonomy + metadata schema), not extraction guidance. Each source's own instructions (shown per-row in the "Prompt" column) are combined with this as the human message; this is the system message.</p>
<pre>{html.escape(STRUCTURE_SYSTEM_PROMPT)}</pre>
</details>
{body_html}
<script>
function selectRun(sid, idx) {{
  const section = document.getElementById(sid);
  section.querySelectorAll('.runpanel').forEach(p => {{
    p.hidden = p.dataset.idx !== String(idx);
  }});
}}
</script>
</body></html>"""


def main() -> None:
    OUT_PATH.write_text(build())
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
