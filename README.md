# Market Insight Agent — MVP0

Raw, factual market-signal collection for Vietnam's banking sector — the
entry point of a larger multi-agent pipeline. This agent surfaces facts
(rate changes, product launches, regulatory moves, competitor activity); it
deliberately does **not** interpret, score, or recommend — that's a
downstream agent's job.

## What it does

Given a fixed list of banking-sector topics (`agent/topics.py`) and, where
applicable, known official-source URLs (`agent/sources.py`), it:

1. Validates the query (`agent/gate.py` — rejects empty/oversized input)
2. Gathers raw information — either a deterministic web search
   (`TavilySearch`, for open-ended topics) or a direct URL fetch
   (`TavilyExtract`, for official pages where the fact reliably lives at
   one stable URL)
3. Makes exactly one LLM call (Groq) to structure the raw results into a
   fixed schema (`agent/schema.py` — `MarketSignal`/`MarketSignalBatch`)
4. Saves the result incrementally to `data/signals.jsonl` and
   `data/signals.csv`, so nothing is lost if a later item fails

Built with [LangGraph](https://langchain-ai.github.io/langgraph/) for the
pipeline/state machine and [LangChain](https://python.langchain.com/) for
the individual model/tool calls. See `CONCEPTS.md` for a from-scratch
explanation of how the structured-output mechanism actually works.

## Setup

```bash
python3 -m venv .venv
.venv/bin/python3 -m pip install -r requirements.txt
cp .env.example .env   # then fill in GROQ_API_KEY and TAVILY_API_KEY
```

## Running

**One-off query** (CLI, for manual/ad hoc testing):
```bash
.venv/bin/python3 main.py "recent pricing changes in the cloud GPU market"
```

**Full trigger run** (all predefined topics + sources, via HTTP):
```bash
.venv/bin/python3 service.py
# then, in another terminal:
curl -X POST http://127.0.0.1:8000/trigger
# or open http://127.0.0.1:8000/docs for the Swagger UI
```
`GET /health` is a free liveness check; `POST /trigger` runs the full
topic/source list and spends real Groq + Tavily credits.

## Output

- `data/signals.jsonl` — one JSON line per topic/source, full fidelity
- `data/signals.csv` — one row per signal found, spreadsheet-friendly
- `data/app.log` — full run log (console output is mirrored here)

## Docs

- `MVP0_PLAN.md` — architecture and design decisions, updated as the
  project evolves
- `DEVELOPMENT_PLAN.md` — build progress checklist, plain-English
- `CONCEPTS.md` — deep-dive explanations of mechanisms used (structured
  output, rate limiting, virtual environments, etc.)
- `market_insight_agent.md` — original project brief
