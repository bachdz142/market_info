import asyncio
from typing import List, Tuple

from agent.crawler import _domain, _throttle
from agent.fetcher_registry import register_fetcher

from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig

# NSO's GDP data (source_plan_mvp0.md §6.3) lives behind a genuine PxWeb
# statistical-database UI (classic ASP.NET WebForms, not the general
# WordPress feed nso_data_and_statistics_official reuses) — a different
# integration than anything else in this file. Its "Continue" button
# looked like a plain link but isn't: a raw JS-level .click() reset the
# selection to 0 cells instead of submitting (confirmed live) — ASP.NET's
# postback needs the listbox's actual selection state set via a real
# browser selection API (Playwright's select_option, which fires a proper
# change event), not just a DOM click. The resulting table URL's `rxid`
# is a server-side session id, not a stable/shareable link — confirmed
# live that re-fetching it in a fresh browser session just redirects back
# to the selection form — so the real table text has to be read from the
# very page that just submitted the form, in the same session, not
# fetched again afterward. This is why this function uses crawl4ai's
# on_page_context_created hook to get a real Playwright `page` handle,
# unlike every other custom fetch function in this file (which only need
# js_code) — genuinely necessary here, not a stylistic choice.
NSO_GDP_KEY_INDICATORS_URL = (
    "https://pxweb.nso.gov.vn/pxweb/en/National%20Accounts%20and%20State%20budget/"
    "National%20Accounts%20and%20State%20budget/E03.01.px/"
)
# Same PxWeb instance, VHLSS (household income/expenditure) tables —
# confirmed live that _fetch_nso_pxweb_table_text works unchanged for these
# too, no new logic needed: PxWeb's selection-form shape (2 listboxes +
# a "Continue" button with this exact element id) is generic across every
# table on this server, not something specific to the GDP one.
NSO_VHLSS_INCOME_URL = (
    "https://pxweb.nso.gov.vn/pxweb/en/Health%2C%20Culture%2C%20Sport%20and%20Living%20standard/"
    "Health%2C%20Culture%2C%20Sport%20and%20Living%20standard/E14.26.px/"
)
NSO_VHLSS_EXPENDITURE_URL = (
    "https://pxweb.nso.gov.vn/pxweb/en/Health%2C%20Culture%2C%20Sport%20and%20Living%20standard/"
    "Health%2C%20Culture%2C%20Sport%20and%20Living%20standard/E14.40.px/"
)


async def _fetch_nso_pxweb_table_text(url: str) -> str:
    _throttle(_domain(url))
    captured_page: dict = {}

    async def _on_page_ready(page, **kwargs):
        captured_page["page"] = page

    async with AsyncWebCrawler() as crawler:
        crawler.crawler_strategy.set_hook("on_page_context_created", _on_page_ready)
        await crawler.arun(url=url, config=CrawlerRunConfig(cache_mode=CacheMode.BYPASS))
        page = captured_page.get("page")
        if not page:
            raise RuntimeError(f"Failed to capture a page handle for {url}")

        selects = await page.query_selector_all("select[id*='ValuesListBox']")
        if len(selects) < 2:
            raise RuntimeError(f"Expected 2 PxWeb selection listboxes on {url}, found {len(selects)}")
        item_select, year_select = selects[0], selects[1]

        item_values = [await o.get_attribute("value") for o in await item_select.query_selector_all("option")]
        await item_select.select_option(value=item_values)

        # Latest 3 years only — keeps the selection well under PxWeb's
        # 100,000-cell limit and matches this project's "pull the latest
        # figures, not a historical archive" convention used elsewhere.
        year_values = [await o.get_attribute("value") for o in await year_select.query_selector_all("option")]
        await year_select.select_option(value=year_values[-3:])

        await page.click(
            "#ctl00_ContentPlaceHolderMain_VariableSelector1_VariableSelector1_ButtonViewTable"
        )
        await asyncio.sleep(3)
        text = await page.inner_text("body")

    if len(text.strip()) < 50:
        raise RuntimeError(f"Near-empty content submitting PxWeb selection at {url}")
    return text


@register_fetcher(NSO_GDP_KEY_INDICATORS_URL, "single")
async def _fetch_nso_gdp_key_indicators() -> Tuple[str, List[Tuple[str, str]]]:
    return await _fetch_nso_pxweb_table_text(NSO_GDP_KEY_INDICATORS_URL), []


@register_fetcher(NSO_VHLSS_INCOME_URL, "single")
async def _fetch_nso_vhlss_income() -> Tuple[str, List[Tuple[str, str]]]:
    return await _fetch_nso_pxweb_table_text(NSO_VHLSS_INCOME_URL), []


@register_fetcher(NSO_VHLSS_EXPENDITURE_URL, "single")
async def _fetch_nso_vhlss_expenditure() -> Tuple[str, List[Tuple[str, str]]]:
    return await _fetch_nso_pxweb_table_text(NSO_VHLSS_EXPENDITURE_URL), []
