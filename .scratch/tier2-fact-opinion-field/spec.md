# Tier 2 `[Fact]`/`[Opinion]` schema field

Status: ready-for-agent

## Problem Statement

Two rows of `source_plan_mvp0.md`'s Layer 3/4 source plan — securities-firm research (SSI, VNDirect, VCBS, BSC) and consumer research (Cimigo, Decision Lab, Q&Me) — are Tier 2 (Citable, but analyst opinion/interpretation rather than raw official disclosure). Rule R-F07 requires every figure from a Tier 2 source to be tagged `[Opinion]` vs `[Fact]`, but `agent/schema.py`'s `MarketSignal` has no such field. `CONTEXT.md`'s own Tier 1/Tier 2 glossary entry already flags this as "a distinction not yet represented in `agent/schema.py`." Without it, neither of the two Tier 2 source rows can be added without silently violating R-F07.

## Solution

Add the fact/opinion distinction to the schema and wire a mechanism to populate it correctly, so it's ready before either Tier 2 source row is built — not something each of those two future efforts has to solve for itself. For Tier 1 sources (official disclosure — everything currently in `SOURCES`), every signal is deterministically forced to `"fact"` in code, with no reliance on the LLM's own judgment. For Tier 2 sources (once built), the field is left to the LLM's judgment, informed by that source's own prompt text, since a single research report can genuinely mix factual quotes with analyst opinion/forecast in the same document.

R-F04 (forecast figures tagged `"forecast"` with the issuing firm named) is already fully implemented via the existing `actual_proxy_forecast`/`forecast_org` fields — out of scope here, nothing to do.

## User Stories

1. As a compliance reviewer, I want every signal to carry an explicit fact-or-opinion tag, so I can filter out analyst opinion before treating a figure as settled fact.
2. As a compliance reviewer, I want every signal from an official-disclosure (Tier 1) source tagged `"fact"` with certainty, not the LLM's best guess, so this compliance-relevant field can't be silently wrong for the 34 sources that already exist and work today.
3. As a developer, I want the fact/opinion tag populated without touching any of the 34 existing source prompts, so this schema-readiness work carries zero risk to sources already in production.
4. As a developer, I want a source's tier (Tier 1 vs Tier 2) to live as source-level config metadata, the same way `role` already does, since tier is a property of the source, not of an individual signal.
5. As a developer, I want the tier-to-fact-override mechanism to live inside the shared graph machinery, not just the FastAPI service layer, so `tests/test_sources.py`'s direct-graph-invocation seam keeps reflecting real production behavior for this field, not a diverged code path.
6. As a developer building a future Tier 2 source, I want that source's own prompt text to be the natural place to add fact/opinion judgment instructions, so no new prompt-plumbing mechanism needs inventing when that work actually starts.
7. As a developer, I want the 34 existing sources to need zero explicit config changes, with `tier_1` as the implicit default, matching how `chunked`/`multi_pdf` already default to `False`/absent rather than requiring every source to state them.
8. As a developer, I want this field required (not optional) on `MarketSignal`, since every signal is unambiguously either a fact or an opinion — there's no legitimate "not applicable" case, unlike `data_basis`.
9. As a developer, I want the new field's literal values to match this schema's existing snake_case lowercase convention (`"fact"`/`"opinion"`), not the source plan's own prose bracket notation (`[Fact]`/`[Opinion]`).
10. As a developer, I want `CONTEXT.md`'s existing Tier 1/Tier 2 glossary entry updated once this lands, so it stops saying the distinction isn't represented in the schema.
11. As a developer, I want this override applied identically whether a source uses the single-piece or multi-piece (chunked/multi-PDF) structuring path, since both already funnel through one shared finalization point.
12. As a developer, I want no changes to the signal schema beyond this one field — `data_basis`, `actual_proxy_forecast`, and every other existing field are unaffected.
13. As a developer, I want this tracked as a new version entry in the project's own progress-tracking document and changelog, matching how every other source-plan-driven change this session was tracked.
14. As a developer, I want this verified via the same direct-graph-invocation seam every other piece of graph logic in this project already uses, extended with a couple of targeted unit-style assertions on the override behavior itself, rather than a new test file or a new testing seam.

## Implementation Decisions

- `MarketSignal` gains one new required field, `fact_or_opinion`, a two-value literal (`"fact"` / `"opinion"`) — no third "not applicable" value, since every signal is one or the other.
- Source configs gain one new optional key, `tier` (`"tier_1"` / `"tier_2"`), documented alongside the existing `role` key's top-of-file convention note. Left unset (implicitly `"tier_1"`) on every one of the 34 existing sources — only ever set explicitly to `"tier_2"` on a source that needs it, matching the existing `chunked` key's own set-only-when-true convention.
- The graph's per-request state gains one new field, `tier` (optional, defaults to `"tier_1"`), threaded through the same way the existing `chunked` field already is: read from the source config in both the FastAPI service path and the direct-test-invocation path, passed into the compiled graph's initial state.
- The graph's shared finalization step (the single point both the single-piece and multi-piece structuring paths already funnel through before returning a result) forces every signal's `fact_or_opinion` to `"fact"` whenever the request's `tier` is `"tier_1"` — overriding whatever the LLM itself produced, the same "trust known metadata over the model's guess" principle already applied there to `source_url`. When `tier` is `"tier_2"`, the LLM's own output is left as-is.
- The shared structuring system prompt gains one added line describing the new field in general terms (a disclosed/reported figure is `"fact"`; an analyst's forecast, interpretation, or subjective assessment is `"opinion"`) — needed because the field is now required on every call regardless of tier, so the model must always attempt a value. For Tier 1 sources this guess is discarded by the override; for a future Tier 2 source, its own prompt text is expected to add more specific per-source guidance on top of this baseline, not a new shared mechanism.
- Zero changes to any of the 34 existing sources' own prompt text.
- `CONTEXT.md`'s Tier 1/Tier 2 entry updated to remove the "not yet represented in `agent/schema.py`" caveat now that it is.

## Testing Decisions

- Same seam as every other piece of source/graph logic in this project: direct graph invocation (`tests/test_sources.py`'s existing parametrization over `SOURCES`) — real network + real LLM, already covers every existing source, and will automatically cover a future Tier 2 source's own test case once one exists. No new test file, no new seam.
- Add a small number of targeted assertions to that existing seam (or an adjacent focused test) specifically checking the override behavior: a `tier_1` (or default/unset-tier) source's signals always come back `fact_or_opinion == "fact"` regardless of what the model attempted; the schema itself rejects a `MarketSignal` missing the field. This is standard-library/pytest-only, following this project's existing prior art of testing observable output rather than internal call sequencing.
- No mocking introduced — matches this project's standing testing decision (only `tests/test_content_gate.py` is offline/mocked, and that's for an unrelated deterministic gate, not this).
- Per the project's fetch-dev-no-llm-by-default direction, the LLM-inclusive parts of this aren't required to be re-run for every one of the 34 existing sources as part of landing this change — the override is deterministic and source-agnostic once the plumbing is verified against a couple of representative sources.

## Out of Scope

- Adding either Tier 2 source row (securities-firm research, consumer research) — this spec only makes the schema and mechanism ready for them; building the actual sources is separate, future work.
- R-F04 (forecast tagging) — already fully implemented via `actual_proxy_forecast`/`forecast_org`, nothing to change.
- Any change to `data_basis`, `actual_proxy_forecast`, or any other existing `MarketSignal` field.
- Any change to the 34 existing sources' own prompt text or config beyond what's needed for the `tier` key to default correctly.
- A per-signal (rather than per-source) tier override mechanism — tier is source-level metadata, matching `role`, not something an individual signal carries.
- Any change to the content-usability gate, the checkpoint gate, or the fetch/crawl layer — this is purely a structuring-schema and graph-finalization change.

## Further Notes

- This directly unblocks the two Tier 2 rows named in `source_plan_mvp0.md` §5 and §6.3 — whoever picks up either of those next builds directly on this, writing that source's own prompt with fact/opinion judgment guidance rather than inventing schema plumbing.
- Annual reports/AGM documents (Layer 3, 5 banks) remains separately parked mid-discovery — unrelated to this spec, tracked in `.scratch/layer3-annual-reports/spec.md`.
- Also still open, unrelated to this spec: GSO stats, app-store release notes (6 apps), Phase 3 structuring-prompt-quality work.
