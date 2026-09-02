"""LLM provider fallback chain for the structuring step: Groq (primary) ->
Gemini -> Mistral -> OpenRouter. Centralized here as a single drop-in
replacement for a bare ChatGroq call — agent/graph.py's _structure_one()
is the only caller, and its own logic/contract (and every extraction
node above it) is unchanged; only the model-building internals move here.

Provider order: Groq is primary (fast, already the project's default) but
rate-limited on the free tier — hit repeatedly in practice this session
(see CHANGELOG's daily-quota notes). Gemini and Mistral are paid-but-cheap
general models. OpenRouter's free tier is the last resort: free models
rotate and are the least predictable of the four, so it only gets used
once the first three have all failed.
"""

import csv
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from langchain_core.messages import SystemMessage
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_mistralai import ChatMistralAI
from langchain_openai import ChatOpenAI

from agent.schema import MarketSignalBatch

logger = logging.getLogger(__name__)

VIETNAM_TZ = timezone(timedelta(hours=7))

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PROVIDER_LOG_CSV = DATA_DIR / "llm_provider_calls.csv"
PROVIDER_LOG_HEADERS = ["timestamp", "provider", "model", "success", "query_preview", "error"]

# Each provider call gets a hard timeout and no internal retries — a slow
# or hung free-tier model (confirmed live: OpenRouter's Nemotron sat with
# zero output for 4+ minutes with no timeout set) must not block the whole
# fallback chain; failing fast into the next provider is the point of this
# feature. Retries are handled by moving to the next provider, not by
# hammering the same one.
PROVIDER_TIMEOUT_SECONDS = 30

# Env-overridable so a model can be swapped without a code change; pinned
# dated versions where the provider supports them (not "latest") so a
# provider-side default change can't silently alter extraction behavior.
# gemini-2.5-flash (the originally-planned default) is confirmed dead —
# Google's API returns 404 NOT_FOUND, "no longer available to new users,"
# pointing at gemini-3.6-flash instead — confirmed live, using that.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
MISTRAL_MODEL = os.environ.get("MISTRAL_MODEL", "mistral-small-2603")
# nvidia/nemotron-3-super-120b-a12b:free — chosen live from
# openrouter.ai/models?max_price=0 (2026-08-31) after 3 free-tier
# candidates were actually tested, not just picked from a description:
#   - minimax/minimax-m2.7:free: wraps JSON in markdown code fences,
#     fails strict schema validation every time.
#   - inclusionai/ling-3.0-flash-fin:free (finance-focused, looked like
#     the best fit on paper): its backing provider (Novita) rejects
#     structured-output requests outright — "model features structured
#     outputs not support".
#   - nvidia/nemotron-3-super-120b-a12b:free: works, but ONLY with
#     method="json_mode" instead of the default (tool-calling/strict
#     schema) — and only with the schema embedded directly in the prompt;
#     confirmed live that method="json_mode" alone, without an explicit
#     schema description in the message, returns parsed=None every time.
#     See OPENROUTER_JSON_MODE / _validated() below.
# Free-tier models on OpenRouter rotate — re-check that URL and re-test
# (don't just re-read descriptions) if this one stops being offered.
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "nvidia/nemotron-3-super-120b-a12b:free")
# Only OpenRouter needs this — Groq/Gemini/Mistral all handle
# with_structured_output's default (tool-calling) method natively and were
# confirmed working with it as-is.
OPENROUTER_JSON_MODE = True


class ExtractionValidationError(Exception):
    """Raised when a provider's response doesn't validate against
    MarketSignalBatch. This is what actually triggers .with_fallbacks() to
    move to the next provider — providers differ in how strictly they honor
    JSON/tool-calling mode, so relying only on HTTP/rate-limit exceptions
    isn't enough; a "successful" call with unparseable output must count as
    a failure too."""


def log_provider_call(provider: str, model: str, success: bool, query: str, error: str = "") -> None:
    """Appends one row per structuring call to data/llm_provider_calls.csv
    — which provider actually served it (or attempted to, on failure), so
    extraction-quality shifts between providers on the same kind of input
    can be traced back later."""
    from agent.store import _prepare_csv  # reuse the existing thread-safe schema-migration helper

    _prepare_csv(PROVIDER_LOG_CSV, PROVIDER_LOG_HEADERS)
    with PROVIDER_LOG_CSV.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(
            [
                datetime.now(VIETNAM_TZ).isoformat(),
                provider,
                model,
                success,
                (query or "")[:80],
                error,
            ]
        )


def _validated(chat_model, provider: str, model_name: str, json_mode: bool = False) -> Runnable:
    """Bind chat_model to MarketSignalBatch's structured-output schema,
    then wrap it so a validation failure raises ExtractionValidationError
    instead of silently returning parsed=None — the raise is what
    .with_fallbacks() needs to detect the failure and try the next
    provider. On success, tags the response with which provider/model
    actually served it, since .with_fallbacks() doesn't expose that on its
    own.

    json_mode=True (OpenRouter only, see OPENROUTER_JSON_MODE): uses
    with_structured_output's looser "json_mode" instead of the default
    (tool-calling/strict schema), which OpenRouter's free-tier models don't
    reliably support — and, confirmed live, json_mode alone still returns
    parsed=None unless the schema is spelled out in the prompt itself, so
    this also injects a schema-description SystemMessage before invoking."""
    if json_mode:
        structured = chat_model.with_structured_output(
            MarketSignalBatch, include_raw=True, method="json_mode"
        )
        schema_note = SystemMessage(
            content=(
                "Respond with a single JSON object matching exactly this schema "
                f"(no markdown code fences, no commentary): {MarketSignalBatch.model_json_schema()}"
            )
        )
        pipeline = RunnableLambda(lambda messages: list(messages) + [schema_note]) | structured
    else:
        pipeline = chat_model.with_structured_output(MarketSignalBatch, include_raw=True)

    def _check(response: dict) -> dict:
        if response.get("parsed") is None:
            logger.warning(
                "[%s/%s] failed schema validation, trying next provider | error: %s",
                provider, model_name, response.get("parsing_error"),
            )
            raise ExtractionValidationError(
                f"[{provider}/{model_name}] failed schema validation: {response.get('parsing_error')}"
            )
        return {**response, "_provider": provider, "_model": model_name}

    return pipeline | RunnableLambda(_check)


def build_structuring_model() -> Runnable:
    """Groq -> Gemini -> Mistral -> OpenRouter. Drop-in replacement for a
    bare `_build_model().with_structured_output(MarketSignalBatch,
    include_raw=True)` call: .invoke(messages) still returns a dict with
    "raw"/"parsed"/"parsing_error" (plus "_provider"/"_model", new) —
    every existing caller's response.get(...) calls keep working
    unchanged."""
    groq = ChatGroq(
        model=os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b"),
        temperature=0,
        timeout=PROVIDER_TIMEOUT_SECONDS,
        max_retries=0,
    )
    gemini = ChatGoogleGenerativeAI(
        model=GEMINI_MODEL, temperature=0, timeout=PROVIDER_TIMEOUT_SECONDS, max_retries=0
    )
    mistral = ChatMistralAI(
        model=MISTRAL_MODEL, temperature=0, timeout=PROVIDER_TIMEOUT_SECONDS, max_retries=0
    )
    openrouter = ChatOpenAI(
        model=OPENROUTER_MODEL,
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"],
        temperature=0,
        timeout=PROVIDER_TIMEOUT_SECONDS,
        max_retries=0,
    )

    primary = _validated(groq, "groq", os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b"))
    fallbacks = [
        _validated(gemini, "gemini", GEMINI_MODEL),
        _validated(mistral, "mistral", MISTRAL_MODEL),
        _validated(openrouter, "openrouter", OPENROUTER_MODEL, json_mode=OPENROUTER_JSON_MODE),
    ]
    return primary.with_fallbacks(fallbacks)
