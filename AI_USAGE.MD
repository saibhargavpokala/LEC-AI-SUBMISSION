# AI Usage Note

The brief asked for an honest account of which parts of this submission used AI, which didn't, and how I verified what the AI produced. What follows is that account.

---

## Short version

I used Claude (via the chat interface at claude.ai) heavily throughout this build — for scaffolding, debugging, and documentation. I wrote very little code entirely from scratch. What I did do was drive the architecture decisions, make every trade-off call, test every change, and reject suggestions I disagreed with.

The submission is a product of my judgement applied through an AI collaborator, not work the AI did on my behalf.

---

## Where AI was used heavily

### Code scaffolding
The initial structure of `agent.py`, `tools.py`, `eval.py`, `budget.py`, and `config.py` was drafted by Claude based on my description of the assignment brief and the architecture I wanted. I iterated on each file multiple times, asking for specific changes rather than accepting the first output.

### Debugging
Three bugs took most of the night to resolve, all debugged in collaboration with Claude:

- **`max_tokens` silent truncation.** The agent was hitting the token ceiling mid-answer with no visible signal. Claude helped me add diagnostic prints to isolate where text was being dropped. I then decided to return the partial answer with a warning rather than retry — Claude suggested retry; I argued against it on cost-spiral grounds. Result: the `max_tokens` safety-net branch in `agent.py`.
- **Reflection loop.** The agent was looping past the 4-call threshold because `force_sent` was firing repeatedly. Claude proposed a fire-every-step fix; I rejected it after testing showed it duplicated conversation turns. Final approach: fire once, strip tools, continue.
- **File layout errors.** `config.py` and `.env` ended up inside `.venv/` at one point. Claude caught this on inspection and I moved them to root.

### Documentation
`ARCHITECTURE.md`, `REPORT.md`, `README.md`, and this file were all drafted by Claude from my notes and the eval data. I edited the drafts — cutting content, trimming length, pushing back on corporate/hype language, rewriting any section that didn't reflect what I actually built or thought.

### Evaluation design
The three-layer eval (keyword + LLM answer judge + LLM tool-use judge) was my design, following a structure Claude suggested. The specific adversarial queries (Q11–Q15) were refined by me after an initial generic set Claude proposed that didn't probe specific failure modes.

---

## Where my judgement drove the work

### Architecture decisions
Every rejected alternative in `ARCHITECTURE.md` is a call I made:

- Rejecting LangChain/LangGraph (Claude initially suggested LangChain)
- Rejecting Ollama when I proposed it as a cost-saving option
- Rejecting a late-night LangGraph Studio rewrite when I proposed it in fatigue
- Rejecting a full codebase rewrite to LangChain in the final hours

These are documented trade-offs. When Claude pushed in a direction I disagreed with, I pushed back.

### Scope discipline
Under deadline pressure I repeatedly proposed big changes (swap LLM provider, rebuild the router, start over with a different architecture). Claude consistently argued against these. I agreed each time after considering the cost. That judgement — to ship the simpler working thing — is mine, though Claude helped me articulate it.

### The budget-cap decision
`BudgetError` as hard rejection vs. soft warning was my call, defended in `ARCHITECTURE.md`. Claude's first draft used soft warnings.

### The hybrid router
Rule-based keyword routing with LLM fallback for the long tail is my design, motivated by wanting predictable cost under the $0.50 cap. Claude's first draft used LLM-based routing for every query.

### What goes in the eval set
The 15 queries are mine. I chose query 13 ("write the essay for me") specifically to probe out-of-scope compliance — and it caught a real safety failure the rest of the eval missed.

---

## How I verified AI-produced work

I did not assume any AI output was correct without checking. Specifically:

- **Every code file ran at least once before I moved on.** If it didn't, I debugged the error with Claude or independently.
- **The eval was run end-to-end three separate times during development** — once after the initial agent was working, once after the reflection bug fix, and once after key rotation. The numbers reported in `REPORT.md` are from the final run, not an earlier one.
- **The ablation was run end-to-end twice**, once after I realised the first run was blocking on human checkpoints (the auto_confirm fix).
- **Smoke-tested the app manually** at the Streamlit UI with a real multi-tool query (3-hour recursion plan) after rotating API keys. The LangSmith trace linked in the README is from that run.
- **Read the ARCHITECTURE.md and REPORT.md drafts line by line before accepting them**, cutting or rewriting anywhere they felt too promotional, too generic, or made claims I couldn't defend.
- **The "known limitations" sections in all three docs are real**, discovered by eval or observation — not scare tactics inserted for credibility.

---

## Where I'm less sure

Being honest about the gaps:

- **`app.py` (Streamlit UI)** is close to the Claude-generated version with minor edits. I verified it runs and looks reasonable, but I didn't rewrite it from scratch. If asked to write a Streamlit app without AI, I would need to look up the API.
- **The cost calculation in `budget.py`** uses token-pricing constants Claude provided. I verified the pricing against Anthropic's documentation, but I didn't independently derive the formula.
- **Tool-use JSON schemas in `tools.py`** follow the Anthropic tool-use spec, which I've only seen through AI-generated code. I understand what the fields mean but haven't written such schemas from memory.

A stronger submission would involve either building the same system without AI as a second pass, or fine-tuning specific components by hand to internalise the patterns. I didn't have time for that under this deadline.

---

## Tools used

- **Claude Opus / Sonnet** (via claude.ai web chat) — the primary AI collaborator, used throughout
- **Anthropic API** — the agent calls this at runtime (Claude 3.5 Sonnet)
- **Tavily API** — web search tool, not AI-generated
- **LangSmith** — tracing / observability, not AI-generated
- **VS Code with GitHub Copilot disabled** — I turned Copilot off deliberately to avoid two concurrent AI sources confusing the code

No AI agent acted autonomously. Claude was a collaborator in a chat interface; every file written was pasted in, reviewed, and saved by me.

---

## Closing

If the test is *"could this person have built this without AI?"* — the honest answer is: slower and with fewer features. I could write a working agent loop against the Anthropic API from scratch; I'd need longer, and the eval framework would be simpler.

If the test is *"did this person think carefully about what they built, identify real failures, and defend their trade-offs?"* — the answer is yes, and that reasoning is documented in `ARCHITECTURE.md`, `REPORT.md`, and the rejected-alternatives history in my chat log.

I treated Claude as a senior-engineer pair, not as an oracle. I argued with it, overruled it, and tested everything it suggested. The submission reflects my judgement exercised through that collaboration.