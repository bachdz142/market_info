# Web Crawling / Scraping — Consolidated Notes

Context: notes for the market insight agent pipeline's `crawler.py` module.

---

## 1. Selenium vs. Playwright

| | Selenium | Playwright |
|---|---|---|
| Speed/reliability | Slower, more flaky (manual waits) | Faster, auto-waiting built in |
| API | Older, more verbose | Modern, cleaner, async-friendly |
| Multi-browser | Yes, via separate drivers | Yes, one API (Chromium/Firefox/WebKit) |
| Best for | Legacy cross-browser QA testing, existing Selenium Grid infra | New projects, scraping, modern testing |

**Origin:** Both were built primarily for **QA/cross-browser testing** — verifying a product works correctly across browsers/OS combos, gating CI/CD releases, catching regressions. Scraping is a secondary, repurposed use case for both tools.

**"Selenium Grid infrastructure"** = hub-and-node setup for running tests in parallel across many browser/OS combos (often via Docker images, cloud providers like BrowserStack/Sauce Labs, CI/CD pipelines, custom internal frameworks). This is a testing investment, not typically built for scraping — the cost of migrating off it is why some companies stick with Selenium despite Playwright being technically better for new work.

**Decision for this pipeline:** Playwright. No existing Selenium infra to justify, and Playwright's async API fits the LangGraph/FastAPI async pipeline better.

---

## 2. Scraping toolchain — tiered approach

Try the cheapest option first; only escalate when needed.

1. **Plain HTTP requests** — `requests`/`httpx` + `BeautifulSoup`/`lxml`. Fast, cheap, no browser overhead. Use when the site is static/server-rendered.
2. **Headless browser** (Playwright) — needed when content only appears after JS runs (SPAs), or you need to click/scroll/login/dismiss popups.
3. **Scraping frameworks** — e.g. Scrapy for large-scale jobs (built-in concurrency, retries, pipelines), often paired with Playwright only for JS-heavy pages.
4. **Scraping-as-a-service** — ScraperAPI, Bright Data, Apify — handle proxies/CAPTCHA/anti-bot at cost, generally overkill for internal predefined-source crawling.

**Rule of thumb:** try `requests` first; fall back to Playwright only when needed.

---

## 3. Why Playwright is "expensive at scale"

Not an LLM/token/API cost — it's **compute/infra cost**, separate from Groq/Tavily spend:

- **Memory/CPU** — each browser instance can use 100–300MB+ RAM just to launch/render.
- **Time** — 2–5+ seconds per page (browser launch, JS execution, network idle) vs. sub-second for plain HTTP.
- **Concurrency limits** — fewer parallel browser instances fit on a machine vs. parallel HTTP requests, limiting crawl throughput.
- **Compute billing** — more compute-hours on cloud infra (e.g. Databricks) = higher bill, independent of LLM API costs.

**Mitigation:** cheap heuristic first (e.g., check if key content is present in raw HTML) before deciding to spin up a browser at all.

---

## 4. Per-site config vs. generic extraction

**Per-site config (`SITE_CONFIGS`)** — needed because every site has different HTML structure, wait conditions, popups, pagination, sometimes login. Generic fetch/parse logic lives once in `crawler.py`; each new site is just a new config entry (data, not new code) — *unless* it needs something genuinely unusual (multi-step login, heavy anti-bot, unusual pagination), which does need new logic.

Example shape:
```python
SITE_CONFIGS = {
    "techcrunch.com": {
        "needs_js": False,
        "wait_selector": None,
        "content_selector": "div.article-content",
        "title_selector": "h1.article__title",
        "date_selector": "time.full-date-time",
        "pagination": None,
    },
    "bloomberg.com": {
        "needs_js": True,
        "wait_selector": "div.body-content",
        "content_selector": "div.body-content",
        "title_selector": "h1",
        "date_selector": "time",
        "pagination": None,
        "popup_dismiss_selector": "button.close-modal",
    },
    "reddit.com": {
        "needs_js": True,
        "wait_selector": "shreddit-post",
        "content_selector": "div[slot='text-body']",
        "title_selector": "h1[slot='title']",
        "date_selector": None,
        "pagination": {"type": "infinite_scroll", "max_scrolls": 5},
    },
}
```

Crawler node logic: look up domain in `SITE_CONFIGS` (fallback to `DEFAULT_CONFIG` if unlisted) → fetch via `requests` or Playwright depending on `needs_js` → parse with BeautifulSoup using the configured selectors.

**Generic extraction alternative** — libraries like **trafilatura** or **readability-lxml** guess at "main content" using heuristics (text density, tag patterns, boilerplate removal) without needing per-site selectors.

```python
import trafilatura
html = trafilatura.fetch_url(url)
content = trafilatura.extract(html)
```

| | Per-site config | Generic (trafilatura/readability) |
|---|---|---|
| Setup effort | Manual investigation per site | Little to none |
| Precision | High (hand-tuned) | Good but imperfect |
| Maintenance | Breaks on site redesigns, per-site fixes | More resilient, but not perfect |
| Scales to 100+ sites | Painful | Fine |

**Recommended approach for a predefined site list:** try trafilatura as the default/baseline across all sites first; only invest manual per-site config effort where it performs poorly or where more precision/structure (pagination, login, etc.) is required.

---

## 5. Process for onboarding a new site to crawl

1. **Inspect manually** — view page source vs. inspect element in browser DevTools. If content is missing from "view source," the site is JS-rendered → needs Playwright.
2. **Identify content structure** — find selectors for title/body/date; check 2–3 pages on the site to confirm the template is consistent.
3. **Check for obstacles** — cookie/consent banners, login walls, paywalls, CAPTCHAs, lazy-load/infinite scroll, rate limiting/bot detection.
4. **Test fetch on one URL** — `requests` + BeautifulSoup first; switch to Playwright if content is missing. Inspect raw HTML before building selectors.
5. **Build the extraction config** — define selectors, wait conditions, popup dismissal as needed (see `SITE_CONFIGS` example above).
6. **Check legality/policy** — review `robots.txt` and Terms of Service, especially since this is for internal business use.
7. **Add politeness/rate limiting** — delays between requests to the same domain, proper User-Agent, caching to avoid re-crawling unchanged content.
8. **Test at scale, then productionize** — run against several URLs from the site, add error handling (site down, selector not found, structure changed), wire the config into `crawler.py`.
9. **Monitor and maintain** — sites redesign over time; add basic alerting/logging for when a selector starts returning empty results, and spot-check content quality periodically.

**Cost note:** this investigation is a one-time, per-site *manual* cost — the per-site config approach saves coding time (generic logic in `crawler.py` handles the fetch/parse once), not investigation time. Ways to reduce the burden: use trafilatura as default and only investigate reactively for sites where it fails; batch-classify sites (static vs. JS, obvious popups) before deep-diving; maintain a shared checklist (this doc) if others on the team will add sites too.
