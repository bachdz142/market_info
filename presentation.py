"""Phase 4 presentation generator - a single HTML fragment (no doctype/
html/head/body; published via the Artifact tool, which wraps it) in the
same plain, functional visual language as review_dashboard.py (system
fonts, flat borders, functional badges - deliberately not a "designed"
marketing page). Pulls from the same data review_dashboard.py reads
(data/raw_content.csv + data/signals.jsonl) - a live snapshot as of
generation time; regenerate any time after a run to refresh.

Usage: python presentation.py
Output: presentation_fragment.html (repo root) - publish via Artifact,
don't open directly (no doctype/head/body of its own by design).
"""

import html
from pathlib import Path

from agent.sources import SOURCES
from review_dashboard import LAYER_OF, _LAYERS, _load_raw_content, _load_signals, _merge_runs

ROOT = Path(__file__).resolve().parent
OUT_PATH = ROOT / "presentation_fragment.html"

TECH_STACK = [
    ("Fetch engine", "crawl4ai", "HTTP + Playwright-based crawling, PDF text extraction"),
    ("Browser automation", "Playwright", "JS-rendered pages, click simulation, network-capture API discovery"),
    ("Pipeline orchestration", "LangGraph", "StateGraph: checkpoint_gate -> crawl -> content_gate -> structure"),
    ("LLM chat abstraction", "LangChain", "Unified interface across 4 providers, with .with_fallbacks()"),
    ("Primary LLM", "Groq - openai/gpt-oss-120b", "Free tier, fast, rate-limited (TPM + daily TPD)"),
    ("Fallback LLM 1", "Google Gemini - gemini-3.6-flash", ""),
    ("Fallback LLM 2", "Mistral - mistral-small-2603", ""),
    ("Fallback LLM 3", "OpenRouter - nvidia/nemotron-3-super-120b-a12b:free", "Last resort, free-tier models rotate"),
    ("OCR", "Mistral OCR - mistral-ocr-latest, Batch mode", "Scanned / no-text-layer PDF recovery, ~$2/1,000 pages"),
    ("Structured output", "Pydantic", "MarketSignalBatch schema validation"),
    ("HTML parsing", "BeautifulSoup4 + lxml", "Content-selector scoping past nav/footer boilerplate"),
    ("PDF page analysis", "pypdf", "Partial-scan detection via real page counts"),
    ("HTTP client", "requests", "Raw PDF re-download for OCR / page-density checks"),
    ("API service", "FastAPI", "/trigger endpoint"),
    ("Storage", "JSONL + CSV, flat files", "signals, raw content, provider calls, OCR job log - no database yet"),
]

FURTHER_IMPROVEMENTS = [
    "Full LLM-verification pass across all 47 sources - in progress; only 9 have a real, current-code run so far.",
    "Prompt refactor grouped by content shape (financial-statement PDF / legal document / news article / app release notes) - deferred pending real evidence; the two weak-extraction candidates checked so far turned out to be stale pre-fix data, not current prompt problems.",
    "Extend automatic OCR-eligibility to the remaining single-fetch chunked sources (Techcombank, ACB, 3 fee schedules) - only BIDV and MBB have it wired so far.",
    "Reconsider blind pre-chunking of large documents (ACB's financial statement splits into 21 pieces, ~10-15 min just from pacing) - BIDV's own ~190K-char OCR'd document was handled in a single call by the fallback chain's larger-context providers; chunking may now be a pre-fallback-chain relic.",
    "A real query layer (SQLite) for joining signals <-> raw content <-> run history - currently hand-rolled Python merges in every script that needs it.",
    "Annual reports / AGM documents (Layer 3) - parked mid-discovery, deferred pending OCR effort (which now exists).",
    "Vietcombank's own Layer 1 disclosures - Akamai-blocked, routed to manual ingestion per source_plan_mvp0.md section 8, not automated.",
]

BLOCKERS_FACED = [
    "Anti-bot walls: Akamai (MBBank's, Vietcombank's own sites), intermittent WAF rejections (sbv.gov.vn) - routed around via aggregator mirrors or accepted as flaky, never evasion techniques.",
    "AJAX-gapped listings (VPBank, ACB) where the real content loads via client-side API calls invisible to a plain fetch - solved via real Playwright network capture of an actual click, not scraping guesses.",
    "Scanned / no-text-layer PDFs (BIDV, SBV legal directives, MBBank's Vietstock mirror) - needed a real OCR pipeline (Mistral Batch OCR) built from scratch this session.",
    "A full Groq daily token-quota exhaustion (2026-08-31) - silently produced \"completed\" runs with zero real signals, before the current Groq -> Gemini -> Mistral -> OpenRouter fallback chain existed to catch it.",
    "robots.txt blocks naming ClaudeBot specifically (thuvienphapluat.vn, VNDirect) - routed to an equivalent aggregator instead of working around the block.",
    "A corrupted-text auto-detection threshold with a real near-miss: MBBank's re-OCR'd mirror measured 0.0477 against a 0.05 cutoff - needed a manual per-source override, not a global threshold change.",
    "Content that fetches successfully but is 100% navigation boilerplate (SBV statistics) - invisible to a basic reachability check; only caught by directly reading the fetched text.",
]

BLOCKERS_AHEAD = [
    "No formal spend cap on LLM/OCR usage yet - real financial exposure if the pipeline runs unattended at full scale.",
    "More sources likely have SBV-statistics-style bugs (fetches fine, content is boilerplate) - only found by manual review so far, not systematically.",
    "Provider API / model deprecations - already happened once mid-project (Groq retired llama-3.3-70b-versatile); the fallback chain helps but doesn't eliminate this.",
    "Vietcombank's Layer 1 data has no automated path at all - needs a real manual-ingestion workflow that doesn't exist yet.",
    "Chunked-source processing time scales badly - a single heavily-split document can take 10+ minutes from per-piece pacing alone.",
]


def _is_real_run(run: dict) -> bool:
    """See session notes 2026-09-02: excludes the 2026-08-31 Groq-daily-
    quota-outage fingerprint (gate_passed=True, error=None, 0 tokens,
    0 signals) - every per-piece call silently failing before
    agent/llm_fallback.py existed, not a real completed attempt."""
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
        "per_source": per_source, "attempted": attempted, "succeeded": succeeded,
        "rejected": rejected, "errored": errored,
        "total_signals": total_signals, "docs_fetched": docs_fetched,
    }


# Horizontal flow, two lanes (single-fetch on top, multi-piece on bottom),
# sharing checkpoint_gate on the left and END on the right - same real
# node names as agent/graph.py, not a simplified version. The OCR
# fallback sits above both content_gate boxes (elbow arrows up and back
# down); the LLM fallback chain sits below both structure boxes; the
# disabled search path is a separate dashed box under checkpoint_gate.
ARCHITECTURE_SVG = """
<svg viewBox="0 0 1220 420" role="img" aria-label="Pipeline architecture, horizontal, two parallel lanes" class="archsvg">
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="#888"></path>
    </marker>
    <marker id="arrowocr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="#a33"></path>
    </marker>
  </defs>
  <style>
    .archsvg text { font-family: ui-monospace, monospace; }
    .box { fill: #fff; stroke: #ccc; stroke-width: 1.2; }
    .box.gate { fill: #eef1f4; }
    .box.ocr { fill: #fbdada; stroke: #c98; }
    .box.dormant { fill: #f2f2f2; stroke-dasharray: 4 3; }
    .lbl { font-size: 12.5px; fill: #1a1f24; }
    .lbl.small { font-size: 10px; fill: #777; }
    .lbl.ocrnote { font-size: 8px; fill: #a33; }
    .edge { stroke: #999; stroke-width: 1.3; fill: none; marker-end: url(#arrow); }
    .edge.ocr-trig { stroke: #a33; marker-end: url(#arrowocr); }
    .edge.ocr-ret { stroke: #a33; stroke-dasharray: 3 3; marker-end: url(#arrowocr); }
    .edge.dormant { stroke: #999; stroke-dasharray: 3 3; }
  </style>

  <circle cx="30" cy="170" r="13" class="box gate"></circle>
  <text x="30" y="174" text-anchor="middle" class="lbl">START</text>

  <rect x="70" y="148" width="140" height="44" rx="5" class="box gate"></rect>
  <text x="140" y="168" text-anchor="middle" class="lbl">checkpoint_gate</text>
  <text x="140" y="181" text-anchor="middle" class="lbl small">validates the query</text>
  <path d="M43,170 L70,170" class="edge"></path>

  <!-- top lane: single-fetch - y49-91 throughout, dedicated to this lane only -->
  <rect x="280" y="49" width="130" height="42" rx="5" class="box"></rect>
  <text x="345" y="68" text-anchor="middle" class="lbl">crawl</text>
  <text x="345" y="80" text-anchor="middle" class="lbl small">single-fetch source</text>
  <path d="M210,158 L280,70" class="edge"></path>

  <rect x="460" y="49" width="150" height="42" rx="5" class="box gate"></rect>
  <text x="535" y="68" text-anchor="middle" class="lbl">content_gate</text>
  <text x="535" y="80" text-anchor="middle" class="lbl small">near-empty / block / scan</text>
  <path d="M410,70 L460,70" class="edge"></path>

  <!-- structure is pushed right of structure_multi's column so its straight
       vertical drop to the fallback lane below has a clear channel past the
       bottom lane's row (nothing else sits above x=790 down there) -->
  <rect x="900" y="49" width="130" height="42" rx="5" class="box"></rect>
  <text x="965" y="68" text-anchor="middle" class="lbl">structure</text>
  <text x="965" y="80" text-anchor="middle" class="lbl small">one LLM call</text>
  <path d="M610,70 L900,70" class="edge"></path>

  <!-- bottom lane: multi-piece - y249-291 throughout, dedicated to this lane only -->
  <rect x="280" y="249" width="130" height="42" rx="5" class="box"></rect>
  <text x="345" y="268" text-anchor="middle" class="lbl">crawl_multi</text>
  <text x="345" y="280" text-anchor="middle" class="lbl small">chunked / multi_pdf</text>
  <path d="M210,182 L280,270" class="edge"></path>

  <rect x="460" y="249" width="150" height="42" rx="5" class="box gate"></rect>
  <text x="535" y="268" text-anchor="middle" class="lbl">content_gate_multi</text>
  <text x="535" y="280" text-anchor="middle" class="lbl small">per-piece, same checks</text>
  <path d="M410,270 L460,270" class="edge"></path>

  <rect x="660" y="249" width="130" height="42" rx="5" class="box"></rect>
  <text x="725" y="268" text-anchor="middle" class="lbl">structure_multi</text>
  <text x="725" y="280" text-anchor="middle" class="lbl small">per piece, merged</text>
  <path d="M610,270 L660,270" class="edge"></path>

  <!-- ensure_ocr_text(): its own vertical lane, sandwiched directly between
       content_gate (above) and content_gate_multi (below) - both arrows in,
       both arrows out, are short, symmetric straight verticals -->
  <rect x="460" y="150" width="150" height="40" rx="5" class="box ocr"></rect>
  <text x="535" y="166" text-anchor="middle" class="lbl">ensure_ocr_text()</text>
  <text x="535" y="178" text-anchor="middle" class="lbl small">billed Mistral OCR, cached/doc</text>

  <path d="M520,91 L520,150" class="edge ocr-trig"></path>
  <path d="M550,150 L550,91" class="edge ocr-ret"></path>
  <text x="558" y="122" class="lbl ocrnote">recovered, re-checked</text>

  <path d="M520,249 L520,190" class="edge ocr-trig"></path>
  <path d="M550,190 L550,249" class="edge ocr-ret"></path>
  <text x="558" y="224" class="lbl ocrnote">recovered, re-checked</text>

  <!-- LLM fallback chain: own lane below both structure nodes. Straight
       vertical drops from each (structure's is the long one, routed through
       the clear channel right of structure_multi's box), one straight line
       back up to END - no diagonal crossing through this zone. -->
  <rect x="650" y="340" width="360" height="52" rx="5" class="box"></rect>
  <text x="830" y="358" text-anchor="middle" class="lbl">Groq -> Gemini -> Mistral</text>
  <text x="830" y="371" text-anchor="middle" class="lbl">-&gt; OpenRouter</text>
  <text x="830" y="384" text-anchor="middle" class="lbl small">first success wins</text>
  <path d="M965,91 L965,340" class="edge"></path>
  <path d="M725,291 L725,340" class="edge"></path>
  <path d="M1010,366 L1060,180" class="edge"></path>

  <rect x="1060" y="155" width="140" height="50" rx="5" class="box"></rect>
  <text x="1130" y="185" text-anchor="middle" class="lbl">END</text>

  <!-- dormant search path -->
  <rect x="70" y="300" width="150" height="56" rx="5" class="box dormant"></rect>
  <text x="145" y="320" text-anchor="middle" class="lbl small">search (Tavily)</text>
  <text x="145" y="333" text-anchor="middle" class="lbl small">build_graph()</text>
  <text x="145" y="346" text-anchor="middle" class="lbl small">disabled: TOPICS=[]</text>
  <path d="M140,192 L145,300" class="edge dormant"></path>
</svg>
"""


def _stat_row(label: str, value) -> str:
    return f"<tr><td>{html.escape(label)}</td><td class='num'>{value}</td></tr>"


def _status_badge(row: dict) -> str:
    run = row["run"]
    if run is None:
        return "<span class='badge notrun-badge'>not yet run</span>"
    if run["gate_passed"] is False:
        return "<span class='badge rejected'>gate-rejected</span>"
    if run["error"]:
        return "<span class='badge errored'>errored</span>"
    return "<span class='badge ok'>succeeded</span>"


def _tech_table_html() -> str:
    rows = "".join(
        f"<tr><td>{html.escape(role)}</td><td class='sid'>{html.escape(name)}</td><td class='technote'>{html.escape(note)}</td></tr>"
        for role, name, note in TECH_STACK
    )
    return f"<table class='srctable'><thead><tr><th>Role</th><th>Technology</th><th>Note</th></tr></thead><tbody>{rows}</tbody></table>"


def _source_sections_html(data: dict) -> str:
    by_layer = {}
    for row in data["per_source"]:
        layer = LAYER_OF.get(row["source"]["id"], "Unclassified")
        by_layer.setdefault(layer, []).append(row)

    sections = []
    for layer_name, _ids in _LAYERS:
        rows = by_layer.get(layer_name, [])
        body = "".join(
            f"<tr><td class='sid'>{r['source']['id']}</td><td>{r['source'].get('kind','')}</td>"
            f"<td>{_status_badge(r)}</td>"
            f"<td class='num'>{len((r['run'].get('result') or {}).get('signals') or []) if r['run'] else '-'}</td></tr>"
            for r in rows
        )
        sections.append(
            f"<h3>{html.escape(layer_name.replace(' — ', ' - '))} <span class='countnote'>({len(rows)} sources)</span></h3>"
            f"<table class='srctable'><thead><tr><th>Source</th><th>Kind</th><th>Status</th><th>Signals</th></tr></thead>"
            f"<tbody>{body}</tbody></table>"
        )
    return "".join(sections)


def _list_html(items: list) -> str:
    return "<ul class='plainlist'>" + "".join(f"<li>{html.escape(i)}</li>" for i in items) + "</ul>"


def build() -> str:
    data = _gather()
    total = len(SOURCES)

    stats_table = "".join([
        _stat_row("Sources configured", total),
        _stat_row("Attempted (real run)", len(data["attempted"])),
        _stat_row("Succeeded", len(data["succeeded"])),
        _stat_row("Gate-rejected", len(data["rejected"])),
        _stat_row("Errored", len(data["errored"])),
        _stat_row("Signals extracted", data["total_signals"]),
        _stat_row("Documents fetched", data["docs_fetched"]),
    ])

    return f"""<title>Market Insight Pipeline</title>
<style>
body {{ font-family: -apple-system, "Segoe UI", sans-serif; background:#f4f5f6; color:#1a1f24; margin:0; padding:1.5rem 2rem 4rem; }}
h1 {{ font-size:1.5rem; margin-bottom:.2rem; }}
.dek {{ color:#555; font-size:.92rem; max-width:42rem; line-height:1.55; margin:.3rem 0 .6rem; }}
.stats-note {{ color:#555; font-size:.85rem; margin-bottom:1.5rem; }}
h2 {{ font-size:1.1rem; border-bottom:2px solid #ccc; padding-bottom:.3rem; margin-top:2.4rem; }}
h3 {{ font-size:.95rem; margin:1.4rem 0 .4rem; }}
.countnote {{ font-weight:400; color:#888; font-size:.8rem; }}
.archwrap {{ background:#fff; border:1px solid #ddd; border-radius:6px; padding:.8rem; overflow-x:auto; }}
.archsvg {{ width:100%; min-width:820px; height:auto; display:block; }}
.srctable {{ width:100%; border-collapse:collapse; font-size:.85rem; margin-bottom:.6rem; background:#fff; border:1px solid #ddd; border-radius:6px; overflow:hidden; }}
.srctable th {{ text-align:left; font-size:.7rem; text-transform:uppercase; letter-spacing:.04em; color:#666; padding:.4rem .7rem; border-bottom:1px solid #ddd; background:#f7f7f8; }}
.srctable td {{ padding:.42rem .7rem; border-bottom:1px solid #eee; }}
.srctable tr:last-child td {{ border-bottom:none; }}
.num {{ font-variant-numeric:tabular-nums; }}
.sid {{ font-family:ui-monospace, monospace; font-size:.82rem; }}
.techup {{ font-family:ui-monospace, monospace; }}
.technote {{ color:#666; font-size:.82rem; }}
.badge {{ font-size:.7rem; padding:.15rem .5rem; border-radius:999px; background:#e8eaed; color:#444; }}
.badge.ok {{ background:#dcf3e6; color:#186a3c; }}
.badge.rejected {{ background:#fff3cd; color:#7a5200; }}
.badge.errored {{ background:#fbdada; color:#8a1c1c; }}
.badge.notrun-badge {{ background:#eee; color:#777; }}
.plainlist {{ margin:0 0 1rem; padding-left:1.2rem; font-size:.9rem; line-height:1.6; }}
.plainlist li {{ margin-bottom:.4rem; }}
footer {{ margin-top:2.5rem; padding-top:1rem; border-top:2px solid #ccc; font-size:.8rem; color:#777; }}
</style>

<h1>Market Insight Pipeline</h1>
<p class="dek">Vietnam banking market intelligence - a crawl -> gate -> extract pipeline over 47 real sources: bank IR pages, SBV statistics, legal circulars, industry research.</p>
<p class="stats-note">Live snapshot, regenerated from data/signals.jsonl + raw_content.csv - not a fixed export. Run <code>python presentation.py</code> again any time to refresh.</p>

<h2>Tech stack</h2>
{_tech_table_html()}

<h2>Architecture</h2>
<p class="stats-note">The real graph shape - including the automatic OCR-recovery branch and the disabled search path still present in code, not a simplified version.</p>
<div class="archwrap">{ARCHITECTURE_SVG}</div>

<h2>Run summary</h2>
<p class="stats-note">Counts reflect only genuinely completed structuring passes - stale entries from a 2026-08-31 provider-quota outage (before the current fallback chain existed) are excluded, not counted as real attempts.</p>
<table class="srctable">{stats_table}</table>

<h2>Sources, by Layer</h2>
<p class="stats-note">source_plan_mvp0.md's 4 content layers - every one of the 47 configured sources, not just a count.</p>
{_source_sections_html(data)}

<h2>Further improvements</h2>
{_list_html(FURTHER_IMPROVEMENTS)}

<h2>Blockers we faced</h2>
{_list_html(BLOCKERS_FACED)}

<h2>Blockers we might still face</h2>
{_list_html(BLOCKERS_AHEAD)}

<footer>Generated by presentation.py from live pipeline data.</footer>
"""


def main() -> None:
    OUT_PATH.write_text(build(), encoding="utf-8")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
