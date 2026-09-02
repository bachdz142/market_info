# OCR fallback for scan-only PDFs (Mistral OCR, Batch mode)

Status: ready-for-agent

## Problem Statement

Several already-added sources are scan-only PDFs with no real text layer — BIDV's and Vietcombank's Layer 1 financial-statement filings, and `sbv_legal_directives_official`'s documents. `agent/content_gate.py` already detects and correctly rejects these (near-empty extraction, or the corrupted-token-ratio heuristic catching broken/garbled OCR output) before any LLM spend — but nothing recovers usable text from them. These sources are effectively unusable today: the fetch succeeds, the gate correctly says "not usable," and that's where it stops.

## Solution

A Mistral OCR-based recovery path for exactly this content-gate rejection reason, built as a standalone capability first (not yet auto-wired into the live `/trigger` graph) so its real output quality can be validated on real documents before anything automatic depends on it.

Mistral's OCR product is a genuinely different API surface than the chat-completions API this project already uses (`langchain-mistralai`'s `ChatMistralAI`, part of the structuring fallback chain) — different input shape (a whole document file, not a text message), different output shape (per-page structured markdown with table structure preserved, not one reply string), different pricing model (per page, not per token), and real file-upload/storage machinery LangChain's chat-model abstraction was never built to cover. This needs Mistral's own raw SDK (`mistralai`) installed alongside the already-installed `langchain-mistralai` — same `MISTRAL_API_KEY`, same billing account, a second Python package for the platform features LangChain doesn't wrap.

Runs in Batch mode (roughly half the price of sync, per Mistral's own pricing page), which is also the practical requirement here: an OCR job can take anywhere from seconds to hours depending on queue load, and a 50+ page bank filing is not something to hold a live HTTP request open for. Submission and result-checking are therefore two separate, independent actions — not one synchronous pipeline step.

## User Stories

1. As a developer, I want to run OCR against one local PDF file directly from the command line, so I can see and judge real output quality before anything in the live pipeline depends on it.
2. As a developer, I want that CLI trigger to actually submit a real Mistral Batch OCR job (not a mock or a sync call), so what I validate is the real thing that will run in production, not a stand-in.
3. As a developer, I want the OCR job's markdown output to preserve table structure, since the target documents (bank financial statements) are dense tables where a flat text dump would lose the figures' meaning.
4. As a developer, I want OCR submission to always be a separate, deliberate action — never an automatic side effect of a normal `/trigger` run's content-gate rejection — so a routine trigger of a known-scan-only source never silently spends real OCR money without someone having decided to.
5. As a developer, once an OCR job is submitted, I want a way to check later whether it's finished and retrieve its result, without needing to keep a process alive waiting on it.
6. As a developer, I want every OCR job's lifecycle (submission, and later its outcome) logged somewhere durable, consistent with how this project already logs everything else (append-only JSONL, not a database), so job history survives process restarts and is inspectable without a special tool.
7. As a developer, I want a rough cost estimate captured for a completed job (page count × the current known per-page Batch price) where it can be calculated, clearly labeled as an estimate rather than an authoritative invoice figure, so OCR spend is visible without needing to check Mistral's own dashboard.
8. As a developer, once OCR markdown is available for a source, I want it fed into the exact same structuring step every normal crawled source already uses, so no new extraction logic has to be written or maintained for OCR-derived content specifically.
9. As a developer, I want OCR-derived signals to log under the source's own existing id (e.g. `bidv_financial_statements`), the same as a normal fetch, rather than getting a separate identity marker — so a downstream consumer doesn't have to know or care whether a given fetch happened to need OCR.
10. As a developer, I want the structuring model's own `confidence` field to be where OCR-derived uncertainty naturally shows up (an OCR read of a dense financial table is inherently less certain than a born-digital text extraction), rather than inventing a new schema field for this — the schema already has a place for "how sure are we."
11. As a developer, I want this built as an isolated, self-contained module (mirroring how `agent/llm_fallback.py` isolates the LLM structuring fallback chain from the rest of the graph), so nothing about the existing crawl/gate/structure pipeline has to change to add this capability.
12. As a developer, I want this treated explicitly as a POC — no elaborate retry/backoff logic on the OCR step itself, just clear error handling and logging when a submission or a result-fetch fails.
13. As a developer, I want automated tests to never trigger a real, billed Mistral OCR call — matching this project's standing rule against spending real money/quota during routine development or CI — while still having real test coverage of the parts of this that don't require a live API call (job-record logging, batch-result-line parsing).
14. As a developer, I want the real end-to-end OCR call path (submit → poll → fetch) validated the same way this project already validates real network-dependent work all session: a manual, deliberately-triggered run (the CLI), not something baked into the automated suite.
15. As a developer, once real output quality has been validated against at least one of the three known scan-only sources, I want a clear, separate next step for actually wiring the automatic content-gate-rejection-triggers-OCR-submission hook into the live graph — not bundled into this same pass.

## Implementation Decisions

- New module `agent/ocr.py`: a self-contained wrapper around Mistral's raw `mistralai` SDK (`mistralai.client.Mistral` — the installed 2.9.4 SDK's top-level `mistralai` package has no `__init__.py`, so this is the real import path, not `from mistralai import Mistral`), covering exactly the OCR/Files/Batch surface needed here. Mirrors `agent/llm_fallback.py`'s role as an isolated concern the rest of the graph doesn't need to know about.
- Three core functions: submit a local PDF as a one-line Batch OCR job (upload the PDF with `purpose="ocr"`, get a signed URL, wrap it in a Batch JSONL line, upload that with `purpose="batch"`, create the batch job against the `/v1/ocr` endpoint); check a job's current status; and, once a job has succeeded, download and parse its result file into the OCR markdown text. A fourth, blocking convenience function (submit + poll-until-done-or-timeout + fetch) exists specifically for the manual CLI path — never called from anything automatic.
- Model name is env-overridable (`MISTRAL_OCR_MODEL`, default `mistral-ocr-latest`), matching the existing pattern for the other LLM-fallback-chain model env vars.
- New CLI script at the repo root, mirroring `fetch_preview.py`'s shape and role: takes a local PDF path and a source id, runs the full submit-and-wait OCR flow, prints/saves the resulting markdown for manual inspection. This is the only way OCR gets triggered right now — there is no automatic hook yet.
- Job tracking: a new append-only log, `data/ocr_jobs.jsonl`, added to `agent/store.py` alongside the existing `signals.jsonl`/`signals.csv`/`raw_content.csv` logs — same file-based, no-database approach already used for everything else this project persists. One line per lifecycle event (e.g. submission, later completion/failure) rather than a row updated in place, matching the append-only nature of every other log here.
- Cost estimate: page count × Mistral's current published Batch OCR price (~$2/1,000 pages as of the pricing page checked while building this), stored alongside a completed job's record, explicitly labeled as an estimate — not treated as an authoritative figure, since the underlying price can change independently of this constant.
- No change to `MarketSignal`/`MarketSignalBatch` — OCR-derived signals use the existing schema unchanged, including the existing `confidence` field for OCR-specific uncertainty; no new "how was this obtained" field.
- No change to `agent/graph.py`, `agent/content_gate.py`, `agent/crawler.py`, or `service.py` in this pass — the automatic "content-gate rejection triggers an OCR submission" hook is explicitly a separate, later step (see Out of Scope), not built now.
- No SQLite or other database introduced — an explicit decision, since this project currently has none and the existing JSONL/CSV pattern already covers "durable, inspectable, append-only history" adequately for a POC.

## Testing Decisions

- The real network-calling functions in `agent/ocr.py` (submit/poll/fetch, and the blocking convenience wrapper) are **not** covered by the automated test suite — matching this project's standing rule against spending real money/API calls during routine development, and matching the precedent already set for `fetch_preview.py`'s own role (manual, deliberately-triggered, real-network validation, not part of `pytest`). The new CLI script is that seam for this feature — the same role `fetch_preview.py` already plays for crawl4ai work.
- Pure, non-network logic gets real offline tests, following `tests/test_tier_fact_opinion.py`'s prior art (testing `_finalize_payload` as a pure function) and `tests/test_bug_fixes.py`'s prior art (pure data-shaping code tested with no network involved): `agent/store.py`'s new `append_ocr_job()` (write a record, read the file back, assert its shape — same style as the existing store.py tests' pattern), and the batch-result-line parsing logic in `fetch_ocr_batch_result()` (feed it a synthetic result-file response shape, assert the markdown comes back correctly joined) — this specific piece is worth isolating for a direct unit test since the batch result line's exact wrapping shape was ambiguous across different documentation sources during research, making it a real risk of drifting silently if the actual API response shape doesn't match what the code assumes.
- No mocking of the Mistral SDK itself introduced — consistent with this project's existing "no mocking" testing decision for real-network code; the untested network path is deliberately left untested rather than tested against a fake.

## Out of Scope

- Wiring an automatic hook so a content-gate rejection (for the "likely a scan" reason) automatically submits an OCR job during a normal `/trigger` run — a deliberate, separate next step, only after real output quality has been validated on at least one real document via the CLI.
- A new FastAPI endpoint (e.g. `POST /ocr/check`) or any other always-on service for checking job completion — the CLI is the only interface for now.
- Any specific commitment about which of the three known scan-only sources (BIDV, Vietcombank's Vietstock mirror, `sbv_legal_directives_official`) gets tried first, or re-adding/upgrading any of them in `agent/sources.py` — that's downstream of validating quality, not part of this spec.
- Retry/backoff logic on OCR submission or polling beyond straightforward error handling and logging — explicitly a POC.
- SQLite or any other database for job tracking.
- A distinct identity marker (new id suffix, new schema field) for OCR-derived signals — they reuse the source's existing id and the existing `confidence` field.
- Any change to pricing/cost-estimate accuracy guarantees — the estimate is a rough, explicitly-labeled approximation, not a billing-accurate figure.

## Further Notes

- The three known candidate documents for real validation, per this project's own history: BIDV's Layer 1 financial statements (`bidv_financial_statements` — confirmed live that one filing has real text only on its first 2 pages of 56, another has zero extractable text across 36 pages), Vietcombank's financial-statement fetch via its Vietstock static-CDN mirror (same practical category), and `sbv_legal_directives_official` (confirmed live: at least one of its PDFs comes back with visibly garbled/broken OCR text, e.g. "ctrAm di6m").
- `DEVELOPMENT_PLAN.md` already carries a note from 2026-09-01 that OCR was going to be "the user's own separate, in-progress work" — this spec supersedes that note; the work is happening in this codebase now.
