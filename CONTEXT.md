# Market Insight Agent — Domain Glossary

This agent pulls external market/competitor data to support Annual Planning's
Competitor & Market Analysis section, per `source_plan_mvp0.md`. This
glossary tracks the vocabulary governing which sources may be ingested and
how — not implementation details, which live in `DEVELOPMENT_PLAN.md`/
`CHANGELOG.md`/code.

## Language

**Layer**:
One of four content areas `source_plan_mvp0.md` defines for the Competitor & Market Analysis section — Layer 1 (quant bank benchmarks), Layer 2 (CVP/offerings/segment sales models), Layer 3 (strategic profile per bank), Layer 4 (macro/government/PEST). Every source belongs to exactly one Layer.

**Role** (Citable / Aggregator / Signal-scouting / Out of scope):
The mandatory classification every source carries, per `source_plan_mvp0.md` §2 — determines how the agent is allowed to handle it, never inferred at runtime. Citable sources are ingested and figures from them are cited directly. Aggregator sources may be used as a fetch path, but the metadata records the original disclosing body, never the aggregator site. Signal-scouting sources are never ingested as data — any figure found there must be traced back to a Citable source before it can enter the store. Out-of-scope metrics have no official disclosure source and are entered manually.
_Avoid_: source type, category

**Tier 1 / Tier 2** (within Citable):
A Citable source is Tier 1 by default — official, non-opinion disclosure. Tier 2 marks a Citable source whose content is opinion/analysis rather than raw disclosure (securities-firm research, consumer surveys) — every figure from a Tier 2 source must be tagged `[Opinion]` vs `[Fact]` per rule R-F07 (R-F04, the separate forecast-tagging rule, was already covered by `actual_proxy_forecast`/`forecast_org`). Represented in code as `MarketSignal.fact_or_opinion` (`"fact"`/`"opinion"`) plus an optional `tier` key on a source config (`"tier_1"`/`"tier_2"`, defaulting to `"tier_1"`) — a `tier_1` source's signals are forced to `"fact"` regardless of what the model produces; a `tier_2` source's own prompt is responsible for guiding the model's per-signal judgment, since one document can genuinely mix both.
_Avoid_: opinion source

**Spot-checked** vs **live-verified**:
Spot-checked means only reachability and rough content volume were confirmed — a quick fetch, eyeballed once. Live-verified means the source passed a real end-to-end run through the production pipeline (fetch → structure → mandatory-metadata check), per the standing rule that only a live-`crawl()`-confirmed URL may enter `SOURCES`. A spot-check is not evidence a source will keep working — confirmed concretely when a domain spot-checked as having no anti-bot walls later returned a real block on a follow-up check.
_Avoid_: verified, tested, confirmed (without saying which kind)

**Checkpoint gate** vs **content gate**:
Two distinct, sequential validation stages a pipeline item passes through — never conflate them. The checkpoint gate validates the *query* before any fetch happens (empty, too long). The content gate validates *fetched content* after a fetch "succeeds" but before it's spent on an LLM structuring call (near-empty, a WAF block page, a scan with a broken OCR layer) — content gate rejections are reported through the same `gate_passed`/`gate_reason` fields as the checkpoint gate, distinguished only by a `"Content gate: ..."` prefix in the reason text, not a separate field.
_Avoid_: "the gate" (ambiguous which one), validation gate

**Watchlist document**:
A specific, named legal/regulatory document (identified by its own reference number, e.g. "Circular 08/2026/TT-NHNN") that Layer 4 tracks by direct lookup rather than by reading a source's general page content — distinct from an ordinary Layer 4 source, which is fetched and read as-is with no specific document identity known in advance.
_Avoid_: tracked document, monitored circular
