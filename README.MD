# Assignment Support Agent

A production-grade AI agent that reads a student's assignment brief and returns:

- Key concepts explained
- A realistic deadline-based plan
- Working code examples
- Free study resources

Built for **LEC AI Assignment 2 — Production Agentic System** (April 2026).

---

## What it does

A student pastes their assignment. The agent:

1. Routes the query through a hybrid rule-based + LLM fallback router
2. Calls the appropriate tools (up to 4 in parallel)
3. Tracks cost and enforces a hard $0.50 budget cap
4. Reflects on progress, forces an answer at 4 tool calls
5. Returns a structured response with concepts, plan, code, and resources

Eight tools are available: `knowledge_base_lookup`, `web_search`, `save_to_knowledge_base`, `time_planner`, `code_executor`, `github_search`, `calculator`, `document_qa`.

---

## Quick start

### 1. Clone and install --

```bash
git clone <repo-url>
cd LEC_AI
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
```

### 2. Add API keys

Create a `.env` file in the project root:

```env
ANTHROPIC_API_KEY=sk-ant-...
TAVILY_API_KEY=tvly-...
LANGCHAIN_API_KEY=lsv2_pt_...
```

Get keys from [Anthropic](https://console.anthropic.com/), [Tavily](https://tavily.com/), [LangSmith](https://smith.langchain.com/).

### 3. Run

```bash
python main.py
```

You'll see a menu:
- `1` — Help with an assignment (paste brief, chat interactively)
- `2` — Run evaluation (15 queries, reports success rate + cost)
- `3` — Run prompt ablation (V1 vs V2 comparison)

### 4. Optional: web UI

```bash
python -m streamlit run app.py
```

Opens at `http://localhost:8501`.

---

## Results

On 15 evaluation queries:

| Metric | Value |
|---|---|
| Keyword pass rate (standard, n=10) | 9/10 (90%) |
| Answer judge (LLM, 1–5) | 3.6 |
| Tool-use judge (LLM, 1–5) | 4.1 |
| Graceful refusal (adversarial, by judge) | 4/5 |
| Cost per successful query | $0.027 |
| Median latency | 14s |

Prompt ablation (V2 focused vs V1 generic): **V2 wins by +0.6 on judge scale.**

Full analysis in [`REPORT.md`](REPORT.md).
Architecture and rejected alternatives in [`ARCHITECTURE.md`](ARCHITECTURE.md).

---
## Live trace

A shared LangSmith trace of a real run: [View trace](https://smith.langchain.com/public/979a9f36-198a-4db8-91a4-3e24cbc9dbe5/r)

Shows the full tool loop — routing, parallel tool execution, observation handling, reflection, final answer, token usage, and latency across 35 seconds.

## File layout
```
LEC_AI/
├── agent.py              # Main agent loop, intake, strategy, ablation
├── tools.py              # 8 tools + router + knowledge base
├── eval.py               # 15-query eval + LLM judges + ablation runner
├── budget.py             # BudgetTracker + BudgetError
├── checkpoints.py        # ask_human helper for CLI
├── config.py             # API clients, model config, token cap
├── main.py               # Entry point (CLI menu)
├── app.py                # Streamlit web UI
├── knowledge_base.json   # Persistent KB (grows from web searches)
├── ARCHITECTURE.md       # Chosen stack, rejected alternatives, trade-offs
├── REPORT.md             # Written report for LEC AI
└── README.md             # This file
```
---

## Known limitations

Documented honestly rather than hidden. See `REPORT.md` for full analysis.

- Long multi-section answers can truncate at the token ceiling (partial answer returned with warning)
- One adversarial safety failure (Q13): agent complied with "write my essay for me" instead of refusing — prompt-level fix planned
- `time_planner` uses keyword-based assignment-type detection; Claude's synthesis layer usually overrides miscategorisations in the final answer
- Evaluation uses a single model (Claude) as judge — known bias; V2 plan: add GPT-4 as second judge

---

## Tech

- Python 3.14 (3.11+ supported)
- Anthropic API (Claude 3.5 Sonnet)
- Tavily (web search)
- LangSmith (tracing)
- Streamlit (UI)
- `concurrent.futures` for parallel tool execution

---

## License

Built for an interview assignment. Not licensed for production use.

