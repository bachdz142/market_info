# Content-Usability Gate

Status: ready-for-agent

## Problem Statement

Fetched content can come back "successfully" from `crawl4ai` — a real HTTP 200, a substantial byte count, no exception raised — and still be completely unusable. Two concrete cases hit live during this project's own development: a WAF/security-appliance block page served as if it were real content, and a scanned PDF with a broken OCR/font-encoding layer that produces text which is present but nonsense. Nothing in the pipeline caught either case before it reached the LLM structuring step — every fetch that cleared `crawl4ai`'s own near-empty/error checks got spent on a real Groq/LLM call regardless of whether the content actually meant anything. This wastes real, budget-constrained LLM quota on garbage input, and risks producing structured "signals" that look plausible but were fabricated from noise.

## Solution

A new, deterministic, LLM-free content-usability gate (`agent/content_gate.py`) runs after every fetch and before any structuring call, in both the single-fetch and multi-document graph paths. It rejects near-empty content, content matching known WAF/block-page fingerprints, and content with a suspiciously high ratio of corrupted-looking tokens — a signature of scanned documents with broken OCR/font-encoding layers — all without spending a single LLM call. For multi-document sources, each document is checked individually so one bad PDF doesn't block the good ones alongside it. Rejections are reported through the same `gate_passed`/`gate_reason` mechanism the rest of the pipeline already understands, so no downstream reporting/CSV changes were needed.

## User Stories

1. As a developer, I want fetched content that's actually a WAF/security-appliance block page rejected before it reaches the LLM, so a real Groq call is never spent structuring a rejection notice as if it were real data.
2. As a developer, I want a scanned document with a broken OCR/font-encoding layer detected and rejected, so garbled nonsense text never gets sent to the LLM to be "structured" into fabricated-looking signals.
3. As a developer, I want this detection to require zero LLM/model calls, so it can run on every single fetch for free, unconditionally, without touching the daily Groq quota.
4. As a developer, I want the corrupted-text heuristic to never misclassify this project's own legitimate short alphanumeric codes (Q2, H1, FY2025, 9M2025, 3M26 and similar reference-period codes), so real financial data is never silently dropped as if it were garbage.
5. As a developer, I want the corrupted-text heuristic tuned against real captured samples from this project rather than invented text, so the threshold is grounded in what this project's sources actually produce, both when things go wrong and when they work.
6. As a developer, when a multi-document source has some usable and some unusable documents, I want only the unusable ones dropped, so the good documents still make it to structuring rather than the whole source failing.
7. As a developer, when every document (and the fallback listing/page text) from a multi-document source turns out to be unusable, I want the whole item marked as gate-rejected with no signals produced, rather than silently structuring nothing or crashing.
8. As a developer, I want a rejection from this new gate reported through the exact same `gate_passed`/`gate_reason` fields the existing checkpoint gate already uses, so `service.py`'s reporting, the CSV output schema, and existing tests need no changes to surface a content-gate rejection.
9. As a developer, I want the reason text to distinguish a content-gate rejection from a checkpoint-gate rejection (a `"Content gate: ..."` prefix), so an operator reading `gate_reason` can tell which kind of rejection happened even though both share the same field.
10. As a developer, I want this gate's core check function to be a pure function with no network or LLM dependency, so it can be tested completely offline, fast, and for free — unlike the rest of this project's tests, which deliberately hit real network/LLM calls.
11. As a developer, I want the gate's tests to use real captured text from this project's own live development (a real scanned-PDF excerpt, a real WAF block page, real clean fetched content) rather than invented synthetic examples, so the tests describe genuine, previously-observed failure modes.
12. As a developer, I want a regression test specifically asserting this project's own legitimate financial period codes are never flagged as corrupted, so a future threshold change can't silently reintroduce that false-positive risk.
13. As an Annual Planning analyst (indirect beneficiary), I want structured signals to never originate from a block page or an unreadable scan, so the data reaching reports is trustworthy by construction, not just by luck.
14. As a developer, I want this gate wired into both the single-fetch graph and the multi-document graph, so every current and future source gets this protection regardless of its fetch shape.
15. As a developer, I want the gate validated against a real previously-fetched problem case (a source already known to contain a scanned, OCR-broken PDF) rather than only synthetic examples, so there's direct evidence it catches a real failure this project actually hit — not just a hypothetical one.
16. As a developer, when the gate rejects a piece, I want the reason logged, so a source's real failure mode is diagnosable from logs alone without re-fetching.
17. As a developer, I want the gate to require no per-source configuration (no language flag, no source-specific threshold), so adding a new source never requires also configuring this gate for it.

## Implementation Decisions

- New module with a single pure function, `check_content_usable(text) -> {"usable": bool, "reason": Optional[str]}`, mirroring the existing checkpoint-gate's return shape.
- Three checks, in order: (1) near-empty content, mirroring the near-empty threshold already used elsewhere in the crawl layer for PDF fetches; (2) a small set of known block-page fingerprint substrings, matched case-insensitively, sourced from a real block page observed live during this project's own development; (3) a corrupted-token-ratio heuristic — the fraction of whitespace-delimited tokens that mix a lowercase letter and a digit — flagged above a threshold set empirically against real samples, chosen to comfortably separate real garbled OCR output, real clean fetched content's small amount of normal markdown-conversion noise, and this project's own legitimate short alphanumeric reference-period codes.
- No dictionary, language model, or per-language configuration — the corrupted-token check is deliberately language-agnostic. It never checks for the presence of Vietnamese diacritics specifically, since several of this project's sources are English-language and that would have caused false positives on them.
- Wired into the LangGraph pipeline as two new nodes: one between the existing single-fetch crawl node and the structuring node, and one between the existing multi-document crawl node and the multi-document structuring node — checking each document individually in the latter case, dropping only the unusable ones, and only rejecting the whole item if nothing usable remains, including the fallback listing/page text the multi-document structuring step would otherwise use.
- Rejections are reported by reusing the existing `gate_passed`/`gate_reason` state fields rather than introducing a parallel field pair — the reason string itself is prefixed to distinguish a content-gate rejection from the pre-existing checkpoint-gate (query validation) rejection. Deliberate choice to avoid a CSV/schema migration and downstream reporting changes for a second, conceptually distinct gate, at the cost of overloading one field pair's original meaning slightly — recorded as a real trade-off, not an oversight.

## Testing Decisions

- The core check function and the two new graph-node functions are pure, state-in/state-out functions with no network or LLM dependency — tested with genuine offline, fully mock-free unit tests, a deliberate first departure from this project's otherwise universal "hit real network and LLM calls" testing convention, justified because there is nothing external to fake here.
- Fixtures are real captured text from this project's own live development, not invented examples: a real scanned-PDF excerpt with broken OCR, a real WAF block page, and real clean fetched content.
- Coverage includes: near-empty rejection, empty/None input handling, known block-page rejection, corrupted-OCR rejection, acceptance of clean real content, a specific regression guard for legitimate financial period codes never being misclassified, and both graph-node functions' state-update behavior (pass-through on good content, per-document filtering, and the "reject the whole item" path when nothing usable survives).
- Prior art: two existing offline/mocked test files are this project's only other non-live tests; the existing live-network/LLM integration test suite for whole-source verification was not changed by this work.
- Validated post-hoc against a real previously-captured problem case — a real fetched file from a source already known to contain a scanned, OCR-broken PDF — confirming the gate independently reproduces a failure a human had already found by manually opening the PDF, without spending any LLM call to do so.

## Out of Scope

- Any change to the signal schema, the CSV schema, or the trigger service's reporting — the gate's rejections reuse existing fields.
- A nav-boilerplate/selector-mismatch heuristic (detecting when a CSS selector fails to match and a fetch silently falls back to a huge raw page dump) — considered and explicitly deferred to a later iteration, since it's harder to tune without more real false-positive data first.
- A language-aware or dictionary-based corrupted-text check — the current heuristic is deliberately simple and language-agnostic.
- Any LLM-based self-critique or reflection step (e.g. an agent reflecting on whether its own structured output matches the source content) — considered and explicitly rejected as the wrong tool for this specific problem, since it would reintroduce the exact LLM-cost problem this gate exists to avoid.
- Re-introducing a dynamic reasoning/tool-calling loop for deciding what to fetch next — this project deliberately removed that pattern early on for cost reasons; this gate is a deterministic check, not a reasoning step.
- Retrying with an alternate fetch strategy when content is rejected (e.g. escalating to a different selector or a different document) — the gate only decides usable/not-usable; it does not attempt to fetch something better.
- Any change to the underlying scanned-document/OCR problem itself — that remains the user's own separately in-progress OCR work, and this gate only detects the symptom, not fixes the cause.

## Further Notes

- This closes out phase 2 of the three-phase Layer 2-4 development plan established earlier in this same working session (fetch/save raw content → a content-usability gate → reasoning/structuring prompt quality). Phase 3 remains a separate, not-yet-started effort.
- An LLM-based approach (asking the model itself "is this text garbage") was explicitly considered and rejected during design, specifically because it would have reintroduced the real-quota-spend problem that motivated this whole piece of work in the first place.
- The corrupted-token-ratio threshold is a tuned empirical constant, not a theoretically derived one — it should be revisited if a future real sample turns out to sit close to the boundary, the same way this threshold itself was set only after checking real garbled vs. real clean vs. legitimate-code samples rather than picking a number a priori.
- This project's domain glossary (`CONTEXT.md`) does not yet have an entry distinguishing this new gate from the existing checkpoint gate by name — worth adding once the two-gates-sharing-one-field-pair design is confirmed as the long-term shape, not just this pass's shortcut.
