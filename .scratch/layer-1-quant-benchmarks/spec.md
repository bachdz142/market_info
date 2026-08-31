# Layer 1 — Quant Bank Benchmarks

Status: ready-for-agent

## Problem Statement

Annual Planning's Competitor & Market Analysis section needs quantitative benchmark data — CASA growth, CASA ratio, term deposit growth, credit growth — for a peer set of banks, plus system-wide indicators (SBV policy data, bancassurance data). Today this is gathered manually: it's slow, coverage is inconsistent across banks, and it risks compliance violations — an analyst can cite a non-citable or banned source, omit required audit metadata (which source, what period the data covers, whether it's actual/proxy/forecast, who forecasted it), or lose track of when data was pulled. There's no automated, compliant way to keep this benchmark data current.

## Solution

Extend the existing Market Insight Agent (LangGraph/FastAPI) to automatically fetch Layer 1 quantitative benchmark data from a fixed, pre-vetted list of official/compliant sources — 5 peer banks' investor-relations pages, Vietstock's document aggregator per ticker, the SBV portal, and IAV — using `crawl4ai` as the sole fetch mechanism (no ad hoc search). Every extracted data point carries the full mandatory metadata set (source code, reference period, data basis, actual/proxy/forecast + forecasting org), so records are audit-ready and citation-compliant by construction rather than by manual review.

## User Stories

1. As an Annual Planning analyst, I want each bank's latest disclosed CASA growth, CASA ratio, term deposit growth, and credit growth pulled automatically from that bank's own investor-relations page, so that I don't have to manually visit five separate bank websites.
2. As an Annual Planning analyst, I want each data point tagged with the bank's source code (TCB/VCB/BID/MBB/ACB), so I can filter and compare benchmark data by bank without re-reading the source document.
3. As a compliance reviewer, I want every pulled data point to record whether it came from a citable primary source or an aggregator, so I can verify citation rules were followed before the data reaches a report.
4. As a compliance reviewer, I want Vietstock-sourced documents tagged with an aggregator role rather than attributed as the bank's own disclosure, so citations point back to the true origin.
5. As an Annual Planning analyst, I want each data point tagged with the reference period it covers (e.g. "Q2 2026"), distinct from the date it was pulled, so I don't confuse when data was fetched with when it was measured.
6. As an Annual Planning analyst, I want each data point tagged as standalone, consolidated, or not_applicable for data basis, so I don't compare standalone figures against consolidated ones by mistake.
7. As an Annual Planning analyst, I want each data point labeled actual, proxy, or forecast, so I know whether I'm looking at a bank's disclosed number or an estimate.
8. As an Annual Planning analyst, when a data point is a forecast, I want the forecasting organization recorded, so I can judge the credibility of the estimate.
9. As a compliance reviewer, I want the pipeline to never fetch from a domain outside the pre-approved Layer 1 source list, so banned or non-compliant sources can never enter the dataset.
10. As an Annual Planning analyst, I want SBV system-wide interest-rate and credit-institution data pulled from the SBV portal automatically, so I have consistent system benchmarks alongside peer-bank data.
11. As an Annual Planning analyst, I want bancassurance data pulled from IAV automatically, so I don't have to track that source manually.
12. As a developer, I want dttktt.sbv.gov.vn explicitly excluded and documented as manual-only (it's bot-blocked), so nobody wastes time trying to automate it or wonders why it's missing.
13. As a developer, I want the crawler to handle both static HTML pages and JS-rendered pages transparently, so I don't need per-source custom fetch code beyond configuration.
14. As a developer, I want PDF documents linked from bank IR pages fetched and parsed, so data locked in PDF disclosures is captured, not just HTML page text.
15. As a developer, when one PDF among several fails to fetch, I want the pipeline to keep processing the remaining PDFs, so a single bad link doesn't blank out an entire bank's results.
16. As a developer, I want each merged signal to carry the correct source URL of the specific document it came from (not the listing page URL), so provenance is traceable to the exact document.
17. As a developer, I want the raw content of every fetched document (not just the top-level listing page) saved to the raw-content store, so extraction can be audited or re-run without re-fetching.
18. As a developer, I want concurrent pipeline runs to not corrupt the CSV output files' headers, so data integrity holds under concurrent `/trigger` calls.
19. As a developer, I want each Layer 1 source individually testable via a direct function call, so I can verify a source produces real, correctly-tagged data before it's trusted in production.
20. As an Annual Planning analyst, I want the existing SBV policy-rate, USD/VND rate, and CPI sources to keep working unchanged, so this migration doesn't regress currently-working functionality.
21. As a developer, I want `crawl4ai` to fully replace the previous requests/trafilatura/playwright/pypdf stack, so the codebase has one fetch mechanism instead of several.

## Implementation Decisions

- Fetch mechanism: `crawl4ai` fully replaces the ad hoc requests/trafilatura/playwright/pypdf stack for all crawling, keeping the existing crawl module's interface (fetch a page's text; fetch a listing page plus its linked PDFs' text) so downstream graph/source code doesn't change shape.
- The existing LangGraph/FastAPI architecture is kept and extended, not rebuilt; the per-item flow remains checkpoint gate → fetch → structure → merge.
- No search-based discovery (Tavily) for Layer 1 — every source is a fixed, pre-configured URL. Retiring the existing Tavily-based topic-search path is deferred to when Layer 2 (which needs bank news-page discovery) is built.
- Banned-domain compliance is enforced by construction — the source list is hand-curated and never includes banned domains — rather than by runtime filtering code. No compliance-checking module is needed for Layer 1.
- The signal schema is extended with: `source_code` (one of the bank/SBV/IAV codes), `reference_period` (the period the data covers, distinct from the pull timestamp), `data_basis` (standalone / consolidated / not_applicable), `actual_proxy_forecast` (actual / proxy / forecast), and `forecast_org` (optional, required when `actual_proxy_forecast` is forecast).
  ```python
  data_basis: Literal["standalone", "consolidated", "not_applicable"]
  actual_proxy_forecast: Literal["actual", "proxy", "forecast"]
  forecast_org: Optional[str] = None  # required (non-None) when actual_proxy_forecast == "forecast"
  ```
- The "date pulled" requirement is satisfied by the existing generation timestamp field — no new field, since the pipeline's per-item architecture means one pull instant covers one document.
- Each source config gains a `role` field (citable vs. aggregator), orthogonal to the existing `kind` field (quant vs. qualitative). All Layer 1 sources are `citable` except Vietstock's per-ticker document pages, which are `aggregator` — attribution and extraction prompts must record the underlying bank document, not Vietstock, for aggregator sources.
- Layer 1 source list: investor-relations pages for 5 peer banks (Techcombank, Vietcombank, BIDV, MBBank, ACB), Vietstock's per-ticker document-aggregator page for each of the same 5 banks, the SBV portal (credit-institution-system + interest-rate sections), and IAV (bancassurance). `dttktt.sbv.gov.vn` is explicitly excluded and documented as manual-only (bot-blocked).
- The existing already-verified sources (SBV policy rate, USD/VND rate, Vietnam CPI) are kept unchanged and coexist with the new Layer 1 sources.
- Four known bugs are fixed as part of this same body of work, since they sit in the code being touched:
  1. Merged multi-document signals must carry the originating document's own URL, not the listing page's URL.
  2. A single failed PDF fetch must not discard the rest of that source's results.
  3. Raw content for every fetched document (not only the top-level listing page) must be persisted.
  4. The CSV writer's header-preparation logic must be safe under concurrent writers.
- Layers 2, 3, and 4 of the source plan, the manual-ingestion path, and the Tavily-retirement decision are explicitly out of scope for this spec.

## Testing Decisions

- This codebase currently has no automated test suite — all verification to date has been manual, ad hoc invocation of the crawl/graph functions with eyeballed output.
- This spec introduces a real automated test suite (`pytest`) rather than continuing manual-only verification.
- The test seam is direct graph invocation: build the crawl graph for a given source configuration, invoke it, and assert on the structured result. This is the highest available seam — it exercises fetch → structure → merge end-to-end without mocking `crawl4ai` internals or standing up the FastAPI service, and it asserts on external behavior (the structured signal output) rather than internal implementation details.
- Coverage: one test per Layer 1 source (or parametrized across the source list) asserting real content was retrieved (not an empty or blocked page) and that all mandatory metadata fields are populated correctly, with `forecast_org` populated only when `actual_proxy_forecast` is forecast. Additional targeted tests cover each of the four bug fixes above.
- These tests hit real network and LLM calls, consistent with how sources have been verified throughout this project so far; no mocking layer is introduced. Making these tests hermetic/mockable is a separate future decision, not part of this spec.

## Out of Scope

- Layers 2, 3, and 4 of `source_plan_mvp0.md` (qualitative/news sources, signal-scouting sources, and whatever else those layers define).
- Retiring or modifying the existing Tavily-based topic search path — deferred to when Layer 2 is built.
- A runtime banned-domain compliance-checking module — not needed while every Layer 1 source is a hand-curated fixed URL.
- The manual-ingestion path for sources that can't be automated (e.g. `dttktt.sbv.gov.vn`) — stubbed for later, not built now.
- Mocking `crawl4ai`/LLM calls in tests, or CI wiring for the new test suite.

## Further Notes

- This spec depends on completing the in-progress `crawl4ai` migration (Python 3.11 upgrade and `crawl4ai` install already done; the crawler rewrite itself is part of this spec's implementation work).
- ADR-0001 (crawl4ai as conditional replacement) should be marked superseded by a new ADR-0002 recording the corrected motivation (crawl4ai was always the standing preference, not an incident response) and the discovered Python 3.10+ requirement.
- A file-by-file implementation breakdown and the full source URL table live in the working plan for this feature; this spec is the durable synthesis of the decisions behind it, meant to survive independently of that plan.

## Comments
