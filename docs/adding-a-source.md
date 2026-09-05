# Adding a source

See `CONTEXT.md` for the **custom fetcher** / **config-driven source**
distinction this guide is built around, and
`.scratch/source-fetcher-refactor/spec.md` for why the fetch code is laid
out this way.

## First question: does this need custom code?

Try the config-driven path first. If the page's real content sits in one
DOM region a CSS selector can reach (optionally after a JS wait, optionally
following a PDF link), you don't need any Python.

You need a custom fetcher only when the site does something a CSS
selector can't express: an API call, a click-through interaction, a
JS-predicate wait (not just "wait for one CSS selector to appear"), PDF
page-range slicing, or similar. See `agent/fetchers/mbbank.py` for a real
example of each of these:

- `_fetch_mbbank_fee_text` — a JS-predicate wait plus following one PDF
  link found inside a scoped content section.
- `_fetch_mbbank_news_parts` — a listing page followed into 3 separate
  article pages (a "parts" source: several distinct documents, one
  structuring call per piece).
- `_fetch_mbbank_annual_report_parts` — PDF page-range slicing via the
  shared `agent.crawler._fetch_annual_report_page_ranges` helper.
- `_fetch_mbbank_financial_statements` — delegates to a shared
  cross-bank helper (`agent.crawler._fetch_vietstock_statement_text`)
  for a bank whose own site is unreachable.

## Path A: config-driven source (no custom code)

1. Add an entry to `SITE_CONFIGS` in `agent/crawler.py`, keyed by the
   URL (if another source already uses that domain with a different
   selector) or the bare domain (the common case). See
   `_resolve_site_config`'s own docstring for which key to use.
2. Add the source's dict to the right file in `agent/sources/` — pick
   `layer1.py`/`layer2.py`/`layer3.py`/`layer4.py` by the source's content
   Layer (`CONTEXT.md`'s **Layer** entry).
3. Confirm it fetches real content with a crawl-only check (no LLM
   spend) — see `fetch_preview.py` — before writing its prompt.

## Path B: custom fetcher

1. Pick the file under `agent/fetchers/` for the source's site. If one
   already exists (another source on the same site), add to it — site
   files share constants/helpers (request URLs, wait conditions,
   selectors). Otherwise create a new file, one per site.
2. Write an `async def` fetcher with no required arguments, returning
   `(text, documents)` — a `str` and a `List[Tuple[pdf_or_article_url,
   text]]` (empty list if there's nothing to break out separately).
   Register it with `@register_fetcher(URL, shape)` right above its
   definition, where `shape` is `"single"` (the source is plain or
   `chunked` — see `CONTEXT.md`) or `"parts"` (the source is `multi_pdf`
   — several distinct documents, each structured separately). Registering
   the same URL twice raises immediately, rather than silently
   overwriting a fetcher's entry.
3. If your fetcher needs `agent/crawler.py`'s shared helpers
   (`_fetch_html`, `_fetch_pdf_text`, `_throttle`, `_domain`,
   `_fetch_annual_report_page_ranges`, `_fetch_vietstock_statement_text`,
   `_chunk_text`/`MAX_CHUNK_CHARS`), import them with
   `from agent.crawler import ...` — don't reimplement them.
4. Add the source's dict to the matching `agent/sources/layerN.py` file,
   with `"multi_pdf": True` if (and only if) your fetcher is registered
   `"parts"` — `tests/test_fetcher_registry.py` checks this
   automatically and fails loudly on a mismatch.
5. New site file? Add it to the import list in
   `agent/fetchers/__init__.py` — that's what actually runs its
   `@register_fetcher(...)` decorators.

## Verifying before writing a prompt

Run `tests/test_fetcher_registry.py` (fast, offline) after adding a
source — it checks the source count/id uniqueness and the shape/
`multi_pdf` match. Then do a crawl-only check with `fetch_preview.py` or
`agent.crawler.crawl`/`crawl_parts` directly — confirm the source is
fetchable with real content before spending any LLM budget writing and
testing its prompt.
