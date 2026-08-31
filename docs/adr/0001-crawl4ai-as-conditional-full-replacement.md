# Full crawl4ai replacement, conditional on real blocking recurrence

Status: superseded by ADR-0002

`agent/crawler.py`'s hand-rolled fetch stack (`requests` + `trafilatura` + `BeautifulSoup` selectors + Playwright fallback + `pypdf`) was blocked twice by `sbv.gov.vn`'s WAF, both times during rapid manual testing rather than real `/trigger` usage — a live check four days later found no block under normal request patterns. Decided: leave the current stack as-is; if blocking ever recurs under real (non-testing) usage, replace it entirely with `crawl4ai` (purpose-built anti-bot stealth/proxy-escalation features) rather than adding `crawl4ai` as a narrow, single-site fallback path.

## Considered options

Narrow fallback — use `crawl4ai` only for whichever specific site gets blocked, keeping the existing stack for everything else. Rejected: it would mean permanently maintaining two parallel fetch stacks for one intermittent problem.

## Consequences

`crawl4ai` is async-only (`AsyncWebCrawler`). Adopting it means wrapping calls in `asyncio.run(...)` inside otherwise fully-synchronous code (LangGraph nodes, FastAPI `def` routes, `service.py`'s loop) — accepted as a small, isolated cost, confined to whichever functions call it. PDF parsing (`pypdf`) is unaffected either way; `crawl4ai` doesn't replace binary PDF text extraction.
