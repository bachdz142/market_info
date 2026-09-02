# Layer 3 — Annual Reports & AGM Documents (5 Banks)

Status: ready-for-agent

## Problem Statement

Annual Planning's Competitor & Market Analysis section needs Layer 3's "strategic profile per bank" data — annual reports and AGM (shareholder meeting) documents from Vietnam's 5 peer banks (Techcombank, Vietcombank, BIDV, MBBank, ACB). Nothing in the pipeline currently fetches this: Layer 1's existing bank sources are scoped narrowly to quarterly quantitative figures, not the qualitative strategic content — retail customer counts, fee revenue composition, technology disclosures, leadership statements — that only shows up in annual/AGM filings.

## Solution

Add one Layer 3 source per bank (5 total) that fetches each bank's latest annual report and/or AGM document, reusing the existing `crawl4ai` pipeline and `MarketSignal` schema unchanged. Each bank's own investor-relations page is tried first, reusing or extending whatever fetch infrastructure Layer 1/Layer 2 already proved for that domain (including, where relevant, the "www." subdomain discovery this session already made for two of these banks' other content). Vietstock's document aggregator is the fallback for a bank whose own site can't be reached, per the source plan's own aggregator role definition — attribution still points to the bank's own document, not Vietstock, matching the convention already established for MBBank's Layer 1 source.

## User Stories

1. As an Annual Planning analyst, I want each bank's latest annual report pulled automatically, so I have strategic direction, retail customer counts, fee revenue composition, technology disclosures, and leadership statements without manually visiting five separate investor-relations pages.
2. As an Annual Planning analyst, I want each bank's latest AGM document pulled alongside the annual report where a separate one exists, so out-of-cycle strategic announcements aren't missed.
3. As a compliance reviewer, I want every annual-report/AGM signal tagged with its source bank's ticker, so I can filter and compare strategic disclosures by bank.
4. As a compliance reviewer, I want a document fetched via Vietstock's aggregator to still record the originating bank's own document as the source in metadata, not Vietstock, matching the convention already used for MBBank's Layer 1 financial-statement source.
5. As an Annual Planning analyst, I want only the most recent annual report/AGM document pulled per bank, not a historical archive, matching how every other source in this pipeline already works.
6. As a developer, I want each bank's IR page tried first via its own domain infrastructure (reusing or extending whatever fetch mechanism Layer 1/Layer 2 already proved for that domain), so this doesn't duplicate already-solved problems.
7. As a developer, when a bank's own IR page can't be reached (an Akamai wall, a JS-rendering gap, etc.), I want a legitimately-reachable alternate subdomain checked before falling back to Vietstock, since this session already found that technique works for two of these banks on other content.
8. As a developer, I want each candidate source live-verified via a real `crawl4ai` fetch before being added to the source list, consistent with the project's standing rule that only a live-confirmed URL may enter it.
9. As a developer, I want each source's content checked against the content-usability gate (near-empty, block-page, corrupted-OCR detection) before it's trusted, so a scan-only or blocked annual report doesn't silently enter the pipeline as if it were real content.
10. As a developer, when a bank's only available annual-report document turns out to be a scan with no extractable text, I want that documented as a known limitation (the same category as existing scan-only Layer 1 filings) rather than silently dropped or force-added.
11. As a developer, I want each source's extraction prompt grounded in the actual real content found on that bank's specific page, not written speculatively before the page is inspected.
12. As a developer, I want long annual-report documents (typically 50+ pages) split into pieces for structuring, matching the existing chunked/multi-document handling already used for other long documents in this pipeline.
13. As a developer, I want no changes to the signal schema for this work, since the existing metadata fields already cover annual-report content adequately.
14. As a developer, I want this work tracked as a new version entry in the project's own progress-tracking document and changelog, not a separate implementation-plan document, matching how this session's other source-addition work was tracked once already spec'd.
15. As a developer, I want each source verified fetch-only (no LLM/Groq call) during development, per this project's standing direction not to spend real LLM quota verifying new sources by default.
16. As a developer, if a bank's annual-report page requires the same real click-simulation/network-capture technique already proven this session, I want that technique applied directly rather than a shortcut (asking for a manually-provided URL or guessing filenames).
17. As an Annual Planning analyst, I want technology disclosures (core banking, open API, super app, BaaS, wallet partnerships) specifically called out in each extraction prompt where present, since these are explicitly named as target content for this layer.
18. As a developer, I want every one of these 5 sources treated as Tier 1, Citable (no new Tier-2 handling needed), since annual reports/AGM documents are official bank disclosures, not journalism or analyst opinion.
19. As a developer, I want each source individually testable via the same direct-graph-invocation seam every other source in this project already uses, so a source's correctness can be verified before it's trusted in production.

## Implementation Decisions

- 5 new sources added to the source list, one per bank (Techcombank, Vietcombank, BIDV, MBBank, ACB), all role Citable, kind qualitative (strategic/technology/leadership content, not quantitative figures).
- Each source targets that bank's own investor-relations site first, reusing or extending whatever fetch mechanism (a site-specific selector configuration, a custom fetch function, or a newly-discovered subdomain) was already proved for that domain in earlier Layer 1/Layer 2 work; Vietstock's document aggregator is the fallback when a bank's own site can't be reached, with metadata still attributing the bank's own document as the source.
- Only the latest annual report (and latest AGM document, if separately available) is pulled per bank — no historical archive.
- No schema changes: existing metadata fields cover this content; the data-basis field is "not applicable" for non-financial-statement strategic disclosures.
- Long documents are split via the existing multi-document/chunking mechanism already used elsewhere in this pipeline, rather than a new one.
- Each source is verified fetch-only (a real fetch plus the content-usability gate) before being added — no LLM spend during discovery.
- Where a bank's own site needs the same real click-simulation/network-capture technique already used earlier this session, that technique is applied directly rather than substituted with a manual workaround.
- Tracked as a new version entry in the project's progress-tracking document and changelog; no separate implementation-plan document beyond this spec.

## Testing Decisions

- Same seam as every other source in this project: direct graph invocation, already parametrized over the full source list — no test-file changes needed, each new source gets a test case automatically.
- That test suite is real-network/real-LLM by the project's existing testing decision; per the fetch-first development direction already established this session, it is not run by default during development — fetch-only verification (real fetch + content-usability gate) is treated as sufficient before a source is added, with the full LLM-inclusive test reserved for whenever a full-pipeline check is explicitly wanted.
- Prior art: every Layer 1/Layer 2 source added this session followed this exact fetch-only-first, live-network-verified pattern.

## Out of Scope

- Historical annual reports/AGM documents beyond the latest one per bank.
- Securities-firm research reports and consumer-research sites (the remaining Layer 3/4 items) — both are Tier 2 and need a new `[Opinion]`/`[Fact]` schema field first, a distinct, not-yet-started piece of engineering.
- Thư viện Pháp luật/LuatVietnam document-by-reference lookups for the 9 named Layer 4 watchlist documents — a separate, not-yet-started discovery task.
- App-store release notes (6 apps) — a different site type entirely, not started.
- Phase 3 (structuring/reasoning prompt quality improvements) — a distinct, not-yet-started effort unrelated to source discovery.
- Any change to the signal schema, the content-usability gate, or the underlying fetch mechanism beyond what's needed to reuse it for these 5 new sources.
- OCR for any bank's annual report/AGM document that turns out to be scan-only — that remains the user's own separate, in-progress work; a scan-only document is documented as a known limitation, not solved here.

## Further Notes

- This closes out the "annual reports and AGM documents" row of the Layer 3 source plan — the layer's other rows (securities-firm research; the two banking/finance journals, already solved in an earlier pass; trade financial press, which is signal-scouting and not ingested) are either already done or explicitly out of scope above.
- Given this session's experience with two of these banks (both blocked on their own investor-relations domain for Layer 1, but reachable via an alternate subdomain for other content types), the same subdomain-discovery technique is a reasonable first thing to try for those two banks' annual-report pages specifically, rather than immediately falling back to Vietstock.
- If any bank's annual-report content turns out to require the same real click-simulation/network-capture technique already validated this session, that technique should be applied directly rather than substituted with a shortcut.
