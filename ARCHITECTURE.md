# Architecture Decisions

LEC AI Assignment 2 — Production Agentic System.
This document explains **what was built**, **what was rejected**, and **the trade-offs behind each call**.

---

## 1. System overview

An assignment support agent that reads a student's assignment brief and returns four things: explanations of key concepts, a realistic deadline-based plan, working code examples, and free study resources.

┌───────────────┐
│  Student      │
│  query/brief  │
└──────┬────────┘
↓
┌──────────────────────────────────┐
│   Entry point (CLI or Streamlit) │
└──────┬───────────────────────────┘
↓
┌──────────────────────────────────┐
│   Intake + strategy              │
└──────┬───────────────────────────┘
↓
┌──────────────────────────────────┐
│   route_tools()                  │
│   (deterministic | llm_fallback) │
└──────┬───────────────────────────┘
↓
┌──────────────────────────────────────────┐
│   Agent loop (max 8 steps)               │
│                                          │
│   tools  ←─ parallel ThreadPoolExecutor  │
│     ↓                                    │
│   observations                           │
│     ↓                                    │
│   reflection (fires at ≥4 tool calls)    │
│     ↓                                    │
│   final answer                           │
└──────┬───────────────────────────────────┘
↓
end_turn  |  max_tokens safety net  |  loop_prevention
↓
┌──────────────────────────────────┐
│  Final answer + cost + trace     │
└──────────────────────────────────┘


**Tool loop:** query → plan → tools (parallel) → observations → reflect → final answer.

**Eight tools:** `knowledge_base_lookup`, `web_search`, `save_to_knowledge_base`, `time_planner`, `code_executor`, `github_search`, `calculator`, `document_qa`.

---

## 2. Stack

| Piece | Chose | Why |
|---|---|---|
| Agent framework | Anthropic API direct | Full control, no framework lock-in |
| LLM | Claude 3.5 Sonnet | Native tool use, reliable JSON |
| Web search | Tavily | Built for agents |
| KB | JSON file on disk | Zero infra, grows on every search |
| Parallel tools | `ThreadPoolExecutor` | Stdlib, good enough for I/O |
| Tracing | LangSmith `@traceable` | One decorator, full observability |
| UI | Streamlit (~80 lines) | Wraps agent without touching it |
| Routing | Keyword rules + LLM fallback | Cheap common path, flexible long tail |
| Eval | Keyword + LLM answer judge + LLM tool judge | 3 orthogonal signals |

---

## 3. Rejected

| Rejected | Why not |
|---|---|
| LangChain / LangGraph | Framework overhead; harder to debug under deadline pressure |
| Ollama / local LLM | Weaker tool use; loses tracing |
| Pure LLM routing | 2–4× token cost, less predictable |
| FAISS vector KB | Premature for <20 entries |
| Redis KB | Single-user demo; v2 need |
| `asyncio` | Threads are enough for 8 I/O tools |
| GPT-4 as second judge | Budget; documented as limitation |
| FastAPI + React frontend | Scope creep; Streamlit is enough |

---

## 4. Trade-offs

- **Routing:** rules for 80% of queries at zero LLM cost; LLM fallback for the rest.
- **Budget cap:** hard rejection over soft warning — predictable cost beats forgiving UX.
- **Truncation:** return partial answer with warning, don't retry — avoids cost spiral.
- **Reflection:** fires once after 4 tool calls — simple and deterministic, occasionally one step late.
- **Eval:** 3 cheap signals beat 1 expensive one. Regression tracking, percentiles, human ground truth all deferred to v2.
- **KB as JSON:** single-writer, fine for demo, will corrupt under concurrency. Redis planned.

---

## 5. What breaks at 100 users

1. **API rate limits** (Tavily, Anthropic) — fix: paid tiers + exponential backoff.
2. **KB file write contention** — fix: Redis with optimistic locking.
3. **In-process state** — fix: Redis session store + Celery queue.

Scoped engineering tasks, not a rewrite.

---

## 6. Known limitations

- **Query 13 safety failure.** Agent complied with "write the essay for me" instead of refusing. Prompt-level fix planned.
- **Truncation.** 5/10 standard eval queries cut mid-sentence. Fix: stream output in sections.
- **Time planner keyword-matched.** Occasionally miscategorises; Claude's synthesis layer overrides in the final answer.
- **Single-model judge.** Claude judging Claude has bias. V2: add GPT-4 as second judge.
- **15 queries** is not statistically meaningful. Needs 50+ per query for latency percentiles.

---

Hidden failures aren't fixed failures. The above are documented on purpose.