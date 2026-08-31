# crawl4ai adopted unconditionally, replacing the hand-rolled fetch stack

Status: accepted

Supersedes ADR-0001. ADR-0001 framed the `crawl4ai` switch as conditional on the `sbv.gov.vn` WAF block recurring under real usage — that framing was misleading: the intent to move to `crawl4ai` was a standing preference independent of that incident, and the incident wasn't the actual trigger for adopting it. Decided: `agent/crawler.py`'s hand-rolled stack (`requests` + `trafilatura` + `BeautifulSoup` + direct Playwright + `pypdf`) is replaced entirely by `crawl4ai`, unconditionally — `crawl4ai` becomes the sole fetch mechanism for both HTML pages and PDFs, via `AsyncHTTPCrawlerStrategy`/the default Playwright-based strategy and `PDFCrawlerStrategy`/`PDFContentScrapingStrategy` respectively. `beautifulsoup4`/`lxml` are kept for CSS-selector parsing of `crawl4ai`'s output, per `crawl4ai`'s own recommendation.

## Consequences

`crawl4ai` requires Python 3.10+ in practice (its own code uses `X | None` union syntax), despite its packaging metadata claiming `>=3.9` — this forced a project-wide upgrade to Python 3.11, which in turn required `playwright==1.60.0` (newer releases dropped macOS 13 support on the development machine). `crawl4ai` is async-only (`AsyncWebCrawler`), so calls are wrapped in `asyncio.run(...)` inside the otherwise-synchronous LangGraph nodes, FastAPI routes, and `service.py`'s loop — an isolated cost confined to the functions that call it. `pypdf` and `requests`/`trafilatura` are removed from `requirements.txt`, since `crawl4ai` now covers both HTML and PDF fetching.
