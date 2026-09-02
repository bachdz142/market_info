"""Phase 4 presentation generator — a single HTML fragment (no doctype/
html/head/body; meant to be published via the Artifact tool, which wraps
it) summarizing the Market Insight Agent pipeline: real architecture,
real source-status counts, and a few representative before/after
extraction case studies. Pulls from the same data review_dashboard.py
reads (data/raw_content.csv + data/signals.jsonl) — this is a live
snapshot as of generation time, not a fixed one-time export; regenerate
any time after a run to refresh.

Usage: python presentation.py
Output: presentation_fragment.html (repo root) — publish this file's
content via the Artifact tool, don't open it directly (it has no
doctype/head/body of its own by design).
"""

import html
import json
from pathlib import Path

from agent.sources import SOURCES
from review_dashboard import LAYER_OF, _LAYERS, _load_raw_content, _load_signals, _merge_runs

ROOT = Path(__file__).resolve().parent
OUT_PATH = ROOT / "presentation_fragment.html"


def _is_real_run(run: dict) -> bool:
    """A run counts as "real" (current-code, genuinely attempted) if it
    produced signals, spent real tokens, was legitimately gate-rejected,
    or genuinely errored. Excludes the 2026-08-31 Groq-daily-quota-outage
    fingerprint (gate_passed=True, error=None, 0 tokens, 0 signals) --
    every per-piece call silently failing before agent/llm_fallback.py
    existed, not a real completed attempt. See session notes 2026-09-02."""
    if run is None:
        return False
    if run.get("gate_passed") is False:
        return True
    if run.get("error"):
        return True
    usage = run.get("token_usage") or {}
    if (usage.get("total_tokens") or 0) > 0:
        return True
    if (run.get("result") or {}).get("signals"):
        return True
    return False


def _gather() -> dict:
    raw_by_id = _load_raw_content()
    signals_by_id = _load_signals()

    per_source = []
    for s in SOURCES:
        runs = _merge_runs(s["id"], raw_by_id, signals_by_id)
        latest = runs[0] if runs else None
        real = latest if _is_real_run(latest) else None
        per_source.append({"source": s, "run": real})

    attempted = [r for r in per_source if r["run"] is not None]
    succeeded = [r for r in attempted if r["run"]["gate_passed"] and not r["run"]["error"]]
    rejected = [r for r in attempted if r["run"]["gate_passed"] is False]
    errored = [r for r in attempted if r["run"]["error"]]
    total_signals = sum(len((r["run"].get("result") or {}).get("signals") or []) for r in attempted)
    docs_fetched = sum(1 for r in attempted if (r["run"].get("raw_content") or "").strip())

    return {
        "per_source": per_source,
        "attempted": attempted,
        "succeeded": succeeded,
        "rejected": rejected,
        "errored": errored,
        "total_signals": total_signals,
        "docs_fetched": docs_fetched,
    }


ARCHITECTURE_SVG = """
<svg viewBox="0 0 920 560" role="img" aria-label="Pipeline architecture diagram" class="archsvg">
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="var(--arch-line)"></path>
    </marker>
  </defs>
  <style>
    .archsvg text { font-family: 'JetBrains Mono', monospace; }
    .box { fill: var(--arch-box); stroke: var(--arch-line); stroke-width: 1.3; }
    .box.gate { fill: var(--arch-gate); }
    .box.ocr { fill: var(--arch-ocr); stroke: var(--arch-ocr-line); }
    .box.dormant { fill: var(--arch-dormant); stroke-dasharray: 4 3; }
    .lbl { font-size: 13px; fill: var(--arch-text); }
    .lbl.small { font-size: 10.5px; fill: var(--arch-text-dim); }
    .edge { stroke: var(--arch-line); stroke-width: 1.4; fill: none; marker-end: url(#arrow); }
    .edge.ocr { stroke: var(--arch-ocr-line); stroke-dasharray: 3 3; }
    .edge.dormant { stroke: var(--arch-text-dim); stroke-dasharray: 3 3; }
  </style>

  <!-- START -->
  <circle cx="180" cy="30" r="14" class="box gate"></circle>
  <text x="180" y="34" text-anchor="middle" class="lbl">START</text>

  <!-- checkpoint_gate -->
  <rect x="100" y="70" width="160" height="44" rx="6" class="box gate"></rect>
  <text x="180" y="93" text-anchor="middle" class="lbl">checkpoint_gate</text>
  <text x="180" y="106" text-anchor="middle" class="lbl small">validates the query</text>
  <path d="M180,44 L180,70" class="edge"></path>

  <!-- fork label -->
  <text x="180" y="140" text-anchor="middle" class="lbl small">routes by source shape</text>
  <path d="M180,114 L180,132" class="edge"></path>

  <!-- crawl (single) -->
  <rect x="20" y="155" width="160" height="44" rx="6" class="box"></rect>
  <text x="100" y="178" text-anchor="middle" class="lbl">crawl</text>
  <text x="100" y="191" text-anchor="middle" class="lbl small">single-fetch source</text>
  <path d="M155,132 L100,155" class="edge"></path>

  <!-- crawl_multi -->
  <rect x="200" y="155" width="180" height="44" rx="6" class="box"></rect>
  <text x="290" y="178" text-anchor="middle" class="lbl">crawl_multi</text>
  <text x="290" y="191" text-anchor="middle" class="lbl small">multi-piece: chunked / multi_pdf</text>
  <path d="M205,132 L290,155" class="edge"></path>

  <!-- content_gate -->
  <rect x="20" y="230" width="160" height="44" rx="6" class="box gate"></rect>
  <text x="100" y="253" text-anchor="middle" class="lbl">content_gate</text>
  <text x="100" y="266" text-anchor="middle" class="lbl small">near-empty / block-page / scan</text>
  <path d="M100,199 L100,230" class="edge"></path>

  <!-- content_gate_multi -->
  <rect x="200" y="230" width="180" height="44" rx="6" class="box gate"></rect>
  <text x="290" y="253" text-anchor="middle" class="lbl">content_gate_multi</text>
  <text x="290" y="266" text-anchor="middle" class="lbl small">per-piece, same checks</text>
  <path d="M290,199 L290,230" class="edge"></path>

  <!-- OCR fallback box -->
  <rect x="440" y="222" width="230" height="60" rx="6" class="box ocr"></rect>
  <text x="555" y="246" text-anchor="middle" class="lbl">ensure_ocr_text()</text>
  <text x="555" y="260" text-anchor="middle" class="lbl small">real, billed Mistral OCR</text>
  <text x="555" y="273" text-anchor="middle" class="lbl small">cached per document</text>
  <path d="M180,246 L440,246" class="edge ocr"></path>
  <text x="310" y="238" class="lbl small" fill="var(--arch-ocr-line)">"scan" / "partial_scan" detected</text>
  <path d="M440,262 C 400,300 240,300 180,262" class="edge ocr"></path>
  <text x="310" y="308" text-anchor="middle" class="lbl small" fill="var(--arch-ocr-line)">recovered text, re-checked</text>

  <!-- structure -->
  <rect x="20" y="335" width="160" height="44" rx="6" class="box"></rect>
  <text x="100" y="358" text-anchor="middle" class="lbl">structure</text>
  <text x="100" y="371" text-anchor="middle" class="lbl small">one LLM call</text>
  <path d="M100,274 L100,335" class="edge"></path>

  <!-- structure_multi -->
  <rect x="200" y="335" width="180" height="44" rx="6" class="box"></rect>
  <text x="290" y="358" text-anchor="middle" class="lbl">structure_multi</text>
  <text x="290" y="371" text-anchor="middle" class="lbl small">one call per piece, merged</text>
  <path d="M290,274 L290,335" class="edge"></path>

  <!-- fallback chain note -->
  <rect x="440" y="335" width="230" height="60" rx="6" class="box">
  </rect>
  <text x="555" y="356" text-anchor="middle" class="lbl">Groq → Gemini → Mistral</text>
  <text x="555" y="370" text-anchor="middle" class="lbl">→ OpenRouter</text>
  <text x="555" y="384" text-anchor="middle" class="lbl small">first success wins</text>
  <path d="M180,357 L440,363" class="edge"></path>
  <path d="M290,357 L440,367" class="edge"></path>

  <!-- END -->
  <circle cx="180" cy="450" r="14" class="box gate"></circle>
  <text x="180" y="454" text-anchor="middle" class="lbl">END</text>
  <path d="M100,379 L160,443" class="edge"></path>
  <path d="M290,379 L200,443" class="edge"></path>

  <!-- dormant search path -->
  <rect x="680" y="70" width="200" height="60" rx="6" class="box dormant"></rect>
  <text x="780" y="93" text-anchor="middle" class="lbl small">search (Tavily)</text>
  <text x="780" y="107" text-anchor="middle" class="lbl small">build_graph()</text>
  <text x="780" y="121" text-anchor="middle" class="lbl small">built, disabled: TOPICS=[]</text>
  <path d="M260,92 L680,100" class="edge dormant"></path>
</svg>
"""


def _stat_tile(n: int, label: str, cls: str = "") -> str:
    return f"<div class='stile {cls}'><div class='n'>{n}</div><div class='l'>{html.escape(label)}</div></div>"


def _status_badge(row: dict) -> str:
    run = row["run"]
    if run is None:
        return "<span class='badge notrun'>not yet run</span>"
    if run["gate_passed"] is False:
        return "<span class='badge rejected'>gate-rejected</span>"
    if run["error"]:
        return "<span class='badge errored'>errored</span>"
    return "<span class='badge ok'>succeeded</span>"


def _source_rows_html(data: dict) -> str:
    by_layer = {}
    for row in data["per_source"]:
        layer = LAYER_OF.get(row["source"]["id"], "Unclassified")
        by_layer.setdefault(layer, []).append(row)

    sections = []
    for layer_name, _ids in _LAYERS:
        rows = by_layer.get(layer_name, [])
        body = "".join(
            f"<tr><td class='sid'>{r['source']['id']}</td><td>{_status_badge(r)}</td>"
            f"<td>{len((r['run'].get('result') or {}).get('signals') or []) if r['run'] else '—'}</td></tr>"
            for r in rows
        )
        sections.append(
            f"<h3>{html.escape(layer_name)}</h3>"
            f"<table class='srctable'><thead><tr><th>Source</th><th>Status</th><th>Signals</th></tr></thead>"
            f"<tbody>{body}</tbody></table>"
        )
    return "".join(sections)


def _case_study(title: str, note: str, raw_excerpt: str, signals: list) -> str:
    sig_html = "".join(
        f"<li><b>{html.escape(s.get('signal_type',''))}</b> — {html.escape(s.get('summary',''))}</li>"
        for s in signals
    )
    return f"""
    <div class="case">
      <h3>{html.escape(title)}</h3>
      <p class="casenote">{html.escape(note)}</p>
      <div class="casecols">
        <div>
          <h4>Raw (excerpt)</h4>
          <pre class="caseraw">{html.escape(raw_excerpt)}</pre>
        </div>
        <div>
          <h4>Extracted</h4>
          <ul class="caseul">{sig_html}</ul>
        </div>
      </div>
    </div>
    """


def _build_case_studies(data: dict) -> str:
    by_id = {r["source"]["id"]: r for r in data["per_source"]}
    cases = []

    bidv = by_id.get("bidv_financial_statements")
    if bidv and bidv["run"]:
        run = bidv["run"]
        raw = run.get("raw_content") or ""
        idx = raw.find("LNST")
        excerpt = raw[max(0, idx - 200):idx + 400] if idx > 0 else raw[:600]
        sigs = (run.get("result") or {}).get("signals") or []
        cases.append(_case_study(
            "BIDV — a scanned financial statement, recovered via OCR",
            "content_gate detected 55/57 blank pages (a partial scan). Mistral OCR ran automatically, "
            "and the recovered text is what produced these real signals — the page was previously invisible to the pipeline entirely.",
            excerpt, sigs[:3],
        ))

    sbv = by_id.get("sbv_portal_statistics")
    if sbv and sbv["run"]:
        run = sbv["run"]
        raw = (run.get("raw_content") or "")[:600]
        sigs = (run.get("result") or {}).get("signals") or []
        cases.append(_case_study(
            "SBV system-wide statistics — from 100% nav boilerplate to a real data table",
            "The original URL always fetched pure navigation menu, zero real content. Swapped to the real "
            "statistics page (found via a live hover on the site's own dropdown) — now a real, current table.",
            raw, sigs[:3],
        ))

    iav = by_id.get("iav_bancassurance")
    if iav and iav["run"]:
        run = iav["run"]
        raw = (run.get("raw_content") or "")[:500]
        sigs = (run.get("result") or {}).get("signals") or []
        cases.append(_case_study(
            "IAV bancassurance — from headlines only to real premium figures",
            "The listing page was being read as-is (titles + dates only). Now follows into the actual "
            "market-overview articles for the real premium revenue and growth figures inside them.",
            raw, sigs[:3],
        ))

    return "".join(cases) if cases else "<p class='empty'>No case studies available yet — run the pipeline first.</p>"


def build() -> str:
    data = _gather()
    total = len(SOURCES)

    stats_html = "".join([
        _stat_tile(total, "Sources configured"),
        _stat_tile(len(data["attempted"]), "Attempted (real run)"),
        _stat_tile(len(data["succeeded"]), "Succeeded", "ok"),
        _stat_tile(len(data["rejected"]), "Gate-rejected", "warn"),
        _stat_tile(len(data["errored"]), "Errored", "fail"),
        _stat_tile(data["total_signals"], "Signals extracted"),
        _stat_tile(data["docs_fetched"], "Documents fetched"),
    ])

    return f"""<title>Market Insight Pipeline</title>
<style>
:root {{
  --paper: #f5f6f8; --surface: #ffffff; --ink: #161b22; --ink-dim: #5b6472;
  --line: #d8dce3; --accent: #2d4f8f; --accent-soft: #e8edf7;
  --ok: #1f8a5f; --ok-bg: #e2f4ec; --warn: #b8791f; --warn-bg: #faf0dc;
  --fail: #b8433a; --fail-bg: #fbe4e2; --muted: #6b7280; --muted-bg: #eceef1;
  --arch-box: #ffffff; --arch-gate: #eef1f8; --arch-ocr: #fbe4e2; --arch-ocr-line: #b8433a;
  --arch-dormant: #eceef1; --arch-line: #a9b3c2; --arch-text: #161b22; --arch-text-dim: #7b8494;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --paper: #12151b; --surface: #1a1e26; --ink: #e7eaf0; --ink-dim: #9aa3b2;
    --line: #2c313c; --accent: #7fa0e0; --accent-soft: #1f2a3d;
    --ok: #5cc999; --ok-bg: #163227; --warn: #e0ac5c; --warn-bg: #362a15;
    --fail: #e08a83; --fail-bg: #3a201f; --muted: #9aa3b2; --muted-bg: #232833;
    --arch-box: #1f2430; --arch-gate: #232a3d; --arch-ocr: #3a201f; --arch-ocr-line: #e08a83;
    --arch-dormant: #202531; --arch-line: #4a5568; --arch-text: #e7eaf0; --arch-text-dim: #8b93a3;
  }}
}}
:root[data-theme="dark"] {{
  --paper: #12151b; --surface: #1a1e26; --ink: #e7eaf0; --ink-dim: #9aa3b2;
  --line: #2c313c; --accent: #7fa0e0; --accent-soft: #1f2a3d;
  --ok: #5cc999; --ok-bg: #163227; --warn: #e0ac5c; --warn-bg: #362a15;
  --fail: #e08a83; --fail-bg: #3a201f; --muted: #9aa3b2; --muted-bg: #232833;
  --arch-box: #1f2430; --arch-gate: #232a3d; --arch-ocr: #3a201f; --arch-ocr-line: #e08a83;
  --arch-dormant: #202531; --arch-line: #4a5568; --arch-text: #e7eaf0; --arch-text-dim: #8b93a3;
}}
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@600;700&family=Source+Sans+3:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');
* {{ box-sizing: border-box; }}
body {{ background: var(--paper); color: var(--ink); font-family: 'Source Sans 3', sans-serif; margin: 0; padding: 0; }}
.wrap {{ max-width: 68rem; margin: 0 auto; padding: 3rem 2rem 5rem; }}
h1, h2, h3, h4 {{ font-family: 'Sora', sans-serif; text-wrap: balance; }}
.eyebrow {{ font-family: 'JetBrains Mono', monospace; font-size: .78rem; letter-spacing: .08em; text-transform: uppercase; color: var(--accent); margin: 0 0 .6rem; }}
h1 {{ font-size: 2.1rem; margin: 0 0 .6rem; }}
.dek {{ color: var(--ink-dim); font-size: 1.02rem; max-width: 42rem; line-height: 1.6; margin: 0 0 .5rem; }}
.snapshot {{ font-family: 'JetBrains Mono', monospace; font-size: .78rem; color: var(--ink-dim); background: var(--accent-soft); display: inline-block; padding: .3rem .7rem; border-radius: 5px; margin-top: .8rem; }}
h2 {{ font-size: 1.4rem; margin: 3.2rem 0 .3rem; border-bottom: 2px solid var(--line); padding-bottom: .5rem; }}
.sectiondek {{ color: var(--ink-dim); font-size: .92rem; margin: 0 0 1.4rem; max-width: 44rem; line-height: 1.55; }}
.archwrap {{ background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 1rem; overflow-x: auto; }}
.archsvg {{ width: 100%; min-width: 760px; height: auto; display: block; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(8.5rem, 1fr)); gap: 1px; background: var(--line); border: 1px solid var(--line); border-radius: 10px; overflow: hidden; }}
.stile {{ background: var(--surface); padding: 1rem 1.1rem; }}
.stile .n {{ font-family: 'Sora', sans-serif; font-weight: 700; font-size: 1.9rem; font-variant-numeric: tabular-nums; }}
.stile .l {{ font-size: .74rem; color: var(--ink-dim); text-transform: uppercase; letter-spacing: .04em; margin-top: .3rem; }}
.stile.ok .n {{ color: var(--ok); }} .stile.warn .n {{ color: var(--warn); }} .stile.fail .n {{ color: var(--fail); }}
h3 {{ font-size: 1rem; margin: 1.6rem 0 .5rem; }}
.srctable {{ width: 100%; border-collapse: collapse; font-size: .86rem; margin-bottom: .6rem; }}
.srctable th {{ text-align: left; font-size: .7rem; text-transform: uppercase; letter-spacing: .04em; color: var(--ink-dim); padding: .35rem .6rem; border-bottom: 1px solid var(--line); }}
.srctable td {{ padding: .4rem .6rem; border-bottom: 1px solid var(--line); }}
.sid {{ font-family: 'JetBrains Mono', monospace; font-size: .8rem; }}
.badge {{ font-family: 'JetBrains Mono', monospace; font-size: .7rem; padding: .18rem .55rem; border-radius: 999px; }}
.badge.ok {{ background: var(--ok-bg); color: var(--ok); }}
.badge.rejected {{ background: var(--warn-bg); color: var(--warn); }}
.badge.errored {{ background: var(--fail-bg); color: var(--fail); }}
.badge.notrun {{ background: var(--muted-bg); color: var(--muted); }}
.case {{ background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 1.2rem 1.4rem; margin-bottom: 1.2rem; }}
.casenote {{ color: var(--ink-dim); font-size: .88rem; line-height: 1.55; margin: .2rem 0 1rem; }}
.casecols {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.2rem; }}
.casecols h4 {{ font-size: .74rem; text-transform: uppercase; letter-spacing: .05em; color: var(--ink-dim); margin: 0 0 .4rem; }}
.caseraw {{ background: var(--paper); border: 1px solid var(--line); border-radius: 6px; padding: .7rem; font-size: .76rem; max-height: 220px; overflow: auto; white-space: pre-wrap; word-break: break-word; font-family: 'JetBrains Mono', monospace; }}
.caseul {{ margin: 0; padding-left: 1.1rem; font-size: .86rem; line-height: 1.6; }}
.empty {{ color: var(--ink-dim); font-style: italic; }}
footer {{ margin-top: 3rem; padding-top: 1.2rem; border-top: 2px solid var(--ink); font-size: .8rem; color: var(--ink-dim); }}
@media (max-width: 640px) {{ .casecols {{ grid-template-columns: 1fr; }} h1 {{ font-size: 1.6rem; }} }}
</style>

<div class="wrap">
  <p class="eyebrow">Vietnam Banking Market Intelligence</p>
  <h1>Market Insight Agent — Pipeline</h1>
  <p class="dek">A crawl → gate → extract pipeline over 47 real sources — bank IR pages, SBV statistics, legal circulars, industry research — feeding structured, cited market signals.</p>
  <div class="snapshot">Live snapshot — regenerated from data/signals.jsonl + raw_content.csv, not a fixed export</div>

  <h2>Architecture</h2>
  <p class="sectiondek">The real graph shape, not a simplified version — including the automatic OCR-recovery branch and the disabled search path still present in code.</p>
  <div class="archwrap">{ARCHITECTURE_SVG}</div>

  <h2>Run summary</h2>
  <p class="sectiondek">Counts reflect only genuinely completed structuring passes — a handful of stale entries from a 2026-08-31 provider-quota outage (before the current Groq→Gemini→Mistral→OpenRouter fallback chain existed) are excluded, not counted as real attempts.</p>
  <div class="stats">{stats_html}</div>

  <h2>Sources, by Layer</h2>
  <p class="sectiondek">source_plan_mvp0.md's 4 content layers — quant bank benchmarks, CVP/offerings, strategic profile, and macro/government.</p>
  {_source_rows_html(data)}

  <h2>What changed: before → after</h2>
  <p class="sectiondek">A few representative sources where the raw fetch and the structured output tell the real story of what this pipeline actually does.</p>
  {_build_case_studies(data)}

  <footer>Generated by presentation.py from live pipeline data. Re-run any time to refresh.</footer>
</div>
"""


def main() -> None:
    OUT_PATH.write_text(build())
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
