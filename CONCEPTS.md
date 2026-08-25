# Concepts — How Things Actually Work

Reference notes explaining mechanisms used in this project, traced down to the
actual library code (not just "trust me, it works"). Added as questions come
up; not a build tracker (see `DEVELOPMENT_PLAN.md` for that).

## `.with_structured_output(...)` — how it really works

Used in `agent/graph.py`'s `_structure_node`:
```python
model = _build_model().with_structured_output(MarketSignalBatch, include_raw=True)
```

### The problem it solves

LLMs normally reply in free text — a paragraph. Code can't reliably pull
`"4.5%"` or a date out of a paragraph without fragile text-parsing that
breaks the moment phrasing changes. We want the model to hand back
predictable fields instead — e.g. `{"signal_type": "price_change", "summary": "...", ...}`.

### It's a repurposed feature, not a new one

Tool-calling was originally built so a model can trigger *real* actions
(our actual `TavilySearch` tool in `_search_node` does this — it really
fetches web results when "called").

`MarketSignalBatch` is not a real tool. Nothing executes when the model
"calls" it — there's no function behind it. It's our schema disguised as a
fake tool, purely to exploit the one output mode models reliably produce
exact structured data in.

### Two layers force the model to comply

1. **Request-level**: the request sent to the provider sets `tool_choice`
   to force calling that exact tool — the model isn't offered a choice, it's
   told it must respond that way, not with plain text.
2. **Generation-level**: the provider's serving infrastructure uses
   **constrained decoding** — while the model generates tokens, invalid ones
   (wrong field names, a `signal_type` outside the allowed 5 values) are
   filtered out entirely, so it's structurally incapable of producing a
   mismatch.

Not "the model behaves well" — it's boxed in on both ends.

### The exact code chain (traced in this project's own `.venv`)

1. `agent/schema.py` — you define `MarketSignalBatch` (a Pydantic class).
   This is the only file that's genuinely "yours" in this whole chain.
2. `agent/graph.py` — you pass it into `.with_structured_output(MarketSignalBatch, include_raw=True)`.
3. `.venv/.../langchain_groq/chat_models.py:1141` —
   ```python
   formatted_tool = convert_to_openai_tool(schema)
   ```
   This is the line that converts your class into a JSON tool description.
4. `convert_to_openai_tool` lives in a different library file:
   `.venv/.../langchain_core/utils/function_calling.py`. Inside it (line
   157-158):
   ```python
   if hasattr(model, "model_json_schema"):
       schema = model.model_json_schema()  # Pydantic 2
   ```
   **This is the real bottom of the chain — Pydantic itself**, not
   LangChain and not AI. Every Pydantic `BaseModel` already knows how to
   describe its own fields/types/descriptions/enums as JSON — that's a
   generic Pydantic feature (the same one FastAPI uses to auto-generate API
   docs), nothing specific to LLMs.
5. LangChain then just wraps that Pydantic-generated JSON in an envelope
   that looks like a "tool":
   ```python
   {
       "type": "function",
       "function": {
           "name": model.__name__,      # "MarketSignalBatch"
           "description": model.__doc__,
           "parameters": schema,         # <- straight from step 4
       }
   }
   ```
6. `chat_models.py:1148-1150` — that JSON gets attached to the request via
   `self.bind_tools([schema], tool_choice=tool_name, ...)`, which sends it
   to Groq alongside the actual question.
7. Groq's API enforces the two layers above (forced `tool_choice` +
   constrained decoding) and returns a structured response. LangChain
   parses it back into a real `MarketSignalBatch` Python object.

**No LLM is involved in steps 3-6.** They're pure, deterministic Python
code, running entirely on your machine before any network request goes
out — same input class always produces the identical JSON output, no
randomness. The LLM only enters at step 7, when the already-built request
is sent over the network and the model reads it as input (the same way it
reads the actual question text).

### Concrete example — input class vs. output JSON

Input (`agent/schema.py`):
```python
class MarketSignal(BaseModel):
    signal_type: SignalType = Field(description="Category of the raw factual signal observed.")
    summary: str = Field(description="A single factual statement — no interpretation or recommendation.")
    source_url: Optional[str] = Field(default=None, description="URL of the source the signal was drawn from, if available.")
    observed_at: str = Field(description="Date/time the underlying event occurred or was reported, or 'unknown'.")
    confidence: Confidence = Field(description="How well-supported the signal is by the source material.")
```

Output (`convert_to_openai_tool(MarketSignalBatch)`, what actually gets sent
to Groq):
```json
{
  "type": "function",
  "function": {
    "name": "MarketSignalBatch",
    "parameters": {
      "properties": {
        "signal_type": {
          "type": "string",
          "enum": ["price_change", "demand_shift", "competitor_activity", "availability", "other"],
          "description": "Category of the raw factual signal observed."
        },
        "summary": { "type": "string", "description": "A single factual statement — no interpretation or recommendation." }
      },
      "required": ["signal_type", "summary", "observed_at", "confidence"]
    }
  }
}
```

Every piece of the output JSON traces back to something typed in the class:
class name → tool name, field name → JSON property, Python type →
JSON `"type"`, `Literal[...]` → `"enum"` list, `Field(description=...)` →
`"description"` text, fields without `default=` → `"required"`.

### Is this Groq-specific?

No. `convert_to_openai_tool` lives in `langchain_core` (provider-agnostic)
and is reused as-is by multiple integrations — confirmed by searching this
project's `.venv`: `langchain_groq`, and generic LangChain agent/chain code
that has nothing to do with Groq. It's named "openai" because OpenAI's
function-calling JSON shape became a de facto industry standard that most
providers (including Groq, whose API is explicitly OpenAI-compatible)
adopted — not because the conversion code itself belongs to any one
provider.

### Can you write this yourself instead?

Yes — it's not privileged framework magic. The manual version:
1. Write your own instruction into the system prompt describing the exact
   JSON shape you want (field names, allowed `signal_type` values, etc.).
2. Call `model.invoke(messages)` directly — plain text response, no
   `.with_structured_output(...)`.
3. Parse the response text yourself: `json.loads(response.content)`, then
   `MarketSignalBatch.model_validate(parsed_dict)`, wrapped in try/except
   for malformed JSON.

Worth knowing as a fallback for the planned Databricks move: if a served
model doesn't support tool-calling well, this manual version is what you'd
fall back to.

## Groq rate limits (tokens-per-minute) and how the crash happened

Groq's free/on-demand tier caps **tokens per minute (TPM)**, not just
requests. Confirmed from a real error hit during testing:
```
Rate limit reached for model `openai/gpt-oss-120b` ... on tokens per minute (TPM): Limit 8000, Used 3163, Requested 4981.
```

Each topic's structure call alone uses ~1,900-5,700 tokens (search itself
is free/untokened — only the LLM call counts). Firing 21 topics back-to-back
with no delay blew through the 8,000 TPM cap after ~2 topics, triggering
repeated `429 Too Many Requests`.

The Groq client auto-retries failed requests up to `DEFAULT_MAX_RETRIES = 2`
times (confirmed in `.venv/.../groq/_constants.py`) before giving up and
raising `groq.RateLimitError`. In the original code, nothing caught that
exception, so it crashed the entire `/trigger` request — and since results
were only saved once at the very end of the loop, every topic computed
before the crash (and paid for in real tokens) was lost.

**Fix** (in `service.py`): a 30s pacing delay between topics
(`TOPIC_DELAY_SECONDS`) to stay under the TPM cap in the first place, plus a
try/except around each topic's call so one failure is logged and recorded
with an `error` field instead of crashing the whole run — combined with
per-topic incremental saving (`append_topic_jsonl`/`append_topic_csv` in
`agent/store.py`) so nothing already computed gets lost even if a topic
does fail.

## `.venv/bin/python3` vs. plain `python3`

Your machine has more than one Python installed. `.venv/` is a virtual
environment — a self-contained copy of Python with only this project's
packages (FastAPI, LangGraph, `tqdm`, etc.) installed into it, separate from
your system Python. Running `.venv/bin/python3` explicitly guarantees using
the interpreter that actually has these packages; plain `python3` would use
whatever your shell finds first, which likely has none of them installed.

`uv` (a faster alternative to `pip`/`venv`) and `conda` (heavier, used for
non-Python/data-science dependencies) both still produce this same kind of
`.venv`-style folder — switching tools wouldn't remove the concept, just
change which tool creates/manages it. Not needed for this project currently.
