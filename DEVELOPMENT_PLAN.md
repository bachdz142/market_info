# Development Plan — Market Insight Agent MVP0

Progress tracker for the MVP0 build. Architecture/design rationale lives in `MVP0_PLAN.md`; this file tracks build status and is updated as work proceeds.

**In plain terms:** you ask this thing a market question (e.g. "what's happening with cloud GPU pricing lately?"), it researches the web, and hands back a clean, organized list of facts — price changes, demand shifts, competitor moves, stock availability. No opinions or recommendations, just facts, because a separate tool downstream is the one that will interpret and act on them.

## Build steps

- [x] `.env` — Groq + Tavily API keys written (gitignored, not committed)
  - *Plain terms: your two access keys/passwords are stored in a private file that never gets shared or uploaded anywhere.*
- [x] `agent/schema.py` — `MarketSignal` (signal_type, summary, source_url, observed_at, confidence) + `MarketSignalBatch` (query, signals, generated_at) Pydantic models
  - *Plain terms: a fixed, predictable format for results — every fact found gets recorded the same way every time: what kind of fact it is, a plain summary, where it came from, when it happened, and how confident the agent is in it.*
- [x] `agent/gate.py` — `checkpoint_gate()`: rejects empty or >2000-char queries before any model call
  - *Plain terms: a gatekeeper that checks your question before anything else happens. An empty or absurdly long question gets stopped right there, with a reason — no time or money wasted on a bad question.*
- [x] `agent/graph.py` — `StateGraph` wiring: `checkpoint_gate → agent (ChatGroq + Tavily) ↔ tools → structure → END`, compiled with `MemorySaver`
  - *Plain terms: the actual research brain — reads your question, searches the web, reads what it finds, writes up the findings, then converts that write-up into the clean, organized format above.*
- [x] `requirements.txt` — swapped `langchain-anthropic` → `langchain-groq`
  - *Plain terms: switched which AI provider powers the research brain, to a cheaper one.*
- [x] `.env.example` — swapped to `GROQ_API_KEY`/`GROQ_MODEL`, kept `TAVILY_API_KEY`
  - *Plain terms: updated the template that shows which access keys this needs, to match the provider switch above.*
- [x] `main.py` — CLI (`python main.py "<query>" [--thread-id ID]`), prints structured JSON or gate-rejection reason
  - *Plain terms: the way you actually run it — type one line with your question, get the results printed back.*
- [x] `market_insight_agent.md` — synced to record the Groq model-provider decision
  - *Plain terms: the project's own notes were updated to reflect the cheaper-provider decision, so the written plan matches what was actually built.*
- [x] Dependencies installed into `.venv`
  - *Plain terms: all the software pieces this needs to actually run were installed.*
  - Note: this venv's `pip` script had a broken shebang pointing at a stale path from a differently-named old project (`PythonProject/.venv/...`) — worked around with `python -m pip install` instead of `pip install`.
  - *Plain terms: hit a leftover setup problem from a previous, differently-named copy of this project (its installer tool pointed at a folder that no longer exists) — used a workaround to install anyway.*
- [x] Fixed Python 3.9 incompatibility: this venv runs 3.9, and `str | None` union syntax (PEP 604) requires 3.10+ at runtime (Pydantic evaluates annotations) — switched to `typing.Optional`/`typing.List` in `agent/schema.py` and `agent/graph.py`
  - *Plain terms: this computer's installed version of the programming language is a bit older than the code expected, so a couple of lines needed rewriting in an older-compatible style. Fixed.*

## Verification (from `MVP0_PLAN.md`)

- [ ] Import/build sanity check — `python -c "import agent.graph; agent.graph.build_graph()"`
  - *Plain terms: make sure the whole thing loads without errors.*
- [ ] Empty-query rejection path — `python main.py ""` should short-circuit at the gate, no model call, prints rejection reason
  - *Plain terms: confirm the gatekeeper actually blocks an empty question like it's supposed to.*
- [ ] Golden path — `python main.py "recent pricing changes in the cloud GPU market"` (live Groq + Tavily call) should print a structured JSON `MarketSignalBatch`
  - *Plain terms: run a real question through the whole pipeline and confirm it comes back with a proper, organized list of facts. This is the real end-to-end test, and it will spend a small amount of real API credits since it's a live run.*
- [ ] Thread-id session isolation spot check
  - *Plain terms: double check that separate conversations don't accidentally mix their results together.*

## Revision: Trigger-Based Execution (built — live end-to-end run not yet verified)

Full rationale and architecture diagram in `MVP0_PLAN.md`'s "Revision: Trigger-Based Execution" section. Short version: the CLI needed a human to type a question and watch the screen. Real usage is unattended — fired on a schedule, over a fixed list of banking-sector macro topics, with results saved somewhere instead of printed.

- [x] `agent/topics.py` — the fixed list of banking-macro questions the agent researches every run, for the **Vietnam** market (11 topics: SBV policy rate, VND interbank rate, USD/VND exchange rate, inflation, government bond yields, SBV credit-growth quota, peer-bank earnings commentary, SBV regulatory developments, credit rating actions, foreign M&A activity, real estate/corporate bond stress — edit freely)
  - *Plain terms: instead of you typing a question every time, there's a standing list of Vietnam banking topics it always checks.*
- [x] `agent/store.py` — saves each run's results as one line in a results file (`data/signals.jsonl`) that accumulates over time
  - *Plain terms: since nobody's watching a screen when this runs on a timer, results get saved to a file instead of just printed, so nothing is lost.*
- [x] `service.py` — a small always-on web service exposing one address you (or a scheduler) can call to fire a run (`POST /trigger`, `GET /health`)
  - *Plain terms: this is the "trigger" — hitting one web address kicks off a full research run across every topic and hands back the results.*
- [x] `requirements.txt` / `.gitignore` updates to support the above (adds the web-service software, keeps the results file out of version control)
- [x] `agent/graph.py` — reworked so the AI no longer decides whether to search; it always searches each topic directly, then reads the results once to write up the findings
  - *Plain terms: token budget is tight, so this cuts out the AI "thinking about whether to search" step entirely — since the topic list already says exactly what to look up, there's nothing to decide. The AI still reads the search results and writes them up, but that's now one step instead of a back-and-forth loop, which uses a lot fewer tokens per topic.*
- [x] Import/build sanity check — graph builds with 3 nodes (`checkpoint_gate → search → structure`), topics load, service routes register. No live calls made.
- [x] Empty-query gate rejection re-verified against the new graph shape — still short-circuits before any search/model call.
- [ ] **Live end-to-end trigger run** — `curl -X POST http://127.0.0.1:8000/trigger`, all 11 topics. **Not run yet — spends real Groq + Tavily credits across 11 topics, holding off until you say go.**

**Design decision made along the way:** discussed whether an AI needs to *decide* to search at all for known numbers like interest rates, versus a plain fixed lookup. Conclusion: for a fixed topic list, the AI never needs to decide *what* to search — that's only useful for open-ended questions with no predefined list, which isn't the case here. So the "AI decides to search" step is being removed entirely (not just for the numeric topics — for all topics, since every topic already has a fixed question). What's *not* being built yet is a way to skip the AI-written-summary step too for pure numbers (e.g. pulling an interest rate straight from an official source instead of writing it up) — that's a separate future upgrade needing a new data source.

## Logging + token tracking

No new framework added (evaluated and skipped MLflow/Langtrace/LangSmith as overkill for MVP0) — built on Python's built-in `logging` module and LangChain's built-in per-call token counts, since both were already available for free.

- [x] `agent/logging_config.py` — `setup_logging()`: turns on logging to both the terminal and a file (`data/app.log`), so a run's history survives after the terminal closes
  - *Plain terms: before this, progress only showed up as scattered `print()` lines that vanished once the terminal closed. Now everything is timestamped and also saved to a file you can reopen later.*
- [x] `agent/gate.py` — logs every gate pass/reject with the reason
  - *Plain terms: you can now see in the log exactly which questions got waved through and which got blocked, and why.*
- [x] `agent/graph.py` — logs how long each web search and each AI write-up call took, and captures the exact token count (input/output/total) used by each AI call
  - *Plain terms: this is the token-usage tracking — every AI call now reports back exactly how much it cost in tokens, instead of that being invisible.*
- [x] `main.py` / `service.py` — both turn logging on at startup; `service.py` also logs a one-line progress update after each topic finishes (`[3/11] sbv_policy_rate done in 4.2s`), so a long 11-topic run shows visible progress instead of going silent until the very end
  - *Plain terms: during a real run you can now watch it move through the topic list one by one in the log, instead of staring at a blank screen for a couple of minutes wondering if it's stuck.*
- [x] `agent/store.py` — the CSV output now has extra columns: how long each topic took, and the input/output/total tokens that topic's AI call used
  - *Plain terms: the spreadsheet-friendly results file now also tells you the cost (in tokens) and time spent per topic, not just the facts found.*
- [x] Import/build sanity check — all touched modules import cleanly and the graph still compiles with the expected 3 nodes. No live calls made.

## Maintenance fixes

- [x] Swapped the AI model this uses: Groq shut down `llama-3.3-70b-versatile` (and the cheaper `llama-3.1-8b-instant`) on 2026-08-16. Now defaults to `openai/gpt-oss-120b`, Groq's own recommended replacement (still overridable via `GROQ_MODEL`).
  - *Plain terms: the specific AI model this was built on got discontinued by its provider right after we set this up. Swapped it for the provider's official suggested replacement — same setup, different underlying model.*

## Open follow-ups (not in MVP0 scope)

- Persistence backend: `MemorySaver` only for now (in-RAM, resets each run). SQLite/Postgres deferred until signals need to survive across restarts — drop-in swap in `agent/graph.py`'s `build_graph()` when needed.
  - *Plain terms: right now, results only exist while the program is running — nothing is saved permanently yet. Adding permanent storage is a small future step, not needed yet.*
- MCP-based tool integration (noted as a future goal in `market_insight_agent.md`, not part of MVP0).
  - *Plain terms: a more standardized way of plugging in tools (like search) is planned for later, not needed for this first working version.*
- Deterministic (non-AI) direct lookups for known figures like interest rates and yields — needs picking a real financial data source and a new access key. Not built yet, just planned for.
  - *Plain terms: a faster, cheaper, more reliable way to get well-known numbers without asking the AI to search for them — a future upgrade, not part of this pass.*
