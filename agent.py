import json
import concurrent.futures
from langsmith import traceable
from config import claude, MODEL, TOKEN_CAP, COST_CAP
from budget import BudgetTracker, BudgetError
from tools import (
    documents, load_document,
    route_tools, get_tool_definitions,
    run_tool, is_complex, get_output_token_limit
)
from checkpoints import ask_human


# ════════════════════════════════════════════════════════════════
# SYSTEM PROMPTS
# ════════════════════════════════════════════════════════════════

SYSTEM_PROMPT_V1 = "You are a helpful assistant. Answer questions helpfully."

SYSTEM_PROMPT_V2 = """You are an expert assignment support agent.

RULES:
1. Check knowledge_base_lookup FIRST — free and instant
2. Use web_search only if KB has nothing
3. Use github_search for code examples
4. Use time_planner when deadline mentioned
5. After MAX 4 tool calls — write COMPLETE answer immediately
6. Only recommend FREE resources
7. Match depth to student level:
   beginner     → analogies, simple language
   intermediate → technical but clear
   expert       → direct, skip basics, tradeoffs
8. Gibberish → say cannot help, ask to clarify
9. NEVER cut off mid-sentence
10. Always end with free resources
"""


# ════════════════════════════════════════════════════════════════
# INTAKE — auto defaults
# ════════════════════════════════════════════════════════════════

def run_intake(brief: str = "") -> dict:
    """Auto intake — 1 day, intermediate, all."""
    print("\n✅ Auto intake: 1 day | intermediate | full support")
    return {"time": "1 day", "level": "intermediate", "need": "all"}


# ════════════════════════════════════════════════════════════════
# STRATEGY
# ════════════════════════════════════════════════════════════════

def build_strategy(intake: dict) -> dict:
    """Build response strategy from intake."""
    need  = intake["need"]
    level = intake["level"]
    time  = intake["time"]

    include = {
        "concepts":  need in ["concepts", "all"],
        "plan":      need in ["plan", "all"],
        "code":      need in ["code", "all"],
        "resources": True,
    }

    tools = ["knowledge_base_lookup"]
    if include["concepts"]:
        tools.append("web_search")
    if include["plan"]:
        tools.append("time_planner")
    if include["code"]:
        tools.append("code_executor")
        tools.append("github_search")
    if documents:
        tools.append("document_qa")

    depth_map = {
        "beginner":     "Use simple language and analogies. Explain every term.",
        "intermediate": "Be technical but clear. Assume basic knowledge.",
        "expert":       "Skip basics. Be direct. Focus on tradeoffs and architecture.",
    }

    sections = []
    if include["concepts"]:
        sections.append("## Key concepts")
    if include["plan"]:
        sections.append(f"## Realistic plan for {time}")
    if include["code"]:
        sections.append("## Working code example")
    sections.append("## Free resources")

    return {
        "tools":    tools,
        "include":  include,
        "depth":    depth_map.get(level, depth_map["intermediate"]),
        "time":     time,
        "level":    level,
        "sections": sections,
    }


# ════════════════════════════════════════════════════════════════
# PARALLEL EXECUTION
# ════════════════════════════════════════════════════════════════

def run_tools_parallel(tool_blocks: list, retries: dict) -> list:
    """Run independent tools simultaneously."""

    def execute(block):
        name = block.name
        if retries.get(name, 0) >= 2:
            return block.id, f"Retry limit for '{name}'"
        result = run_tool(name, block.input)
        if "Error" in str(result) or "failed" in str(result).lower():
            retries[name] = retries.get(name, 0) + 1
        return block.id, result

    results = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(execute, b) for b in tool_blocks]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
    return results


# ════════════════════════════════════════════════════════════════
# MAIN AGENT
# ════════════════════════════════════════════════════════════════

@traceable(name="AssignmentAgent")
def run_agent(
    question:       str,
    brief:          str  = "",
    intake:         dict = None,
    strategy:       dict = None,
    prompt_version: str  = "v2",
    auto_confirm:   bool = False,
) -> str:
    """
    Main agent loop.
    Query → Plan → Tools → Observations → Reflect → Answer

    auto_confirm=True skips the human checkpoint.
    Used by ablation runs and other automated evaluations.
    """
    if brief:
        load_document("assignment_brief", brief)

    budget        = BudgetTracker(token_cap=TOKEN_CAP, cost_cap=COST_CAP)
    system_prompt = SYSTEM_PROMPT_V2 if prompt_version == "v2" else SYSTEM_PROMPT_V1

    if strategy:
        selected_tools = strategy["tools"]
        depth          = strategy["depth"]
        sections       = strategy["sections"]
        time_available = strategy["time"]
        routing_mode   = "strategy_override"
    else:
        selected_tools, routing_mode = route_tools(question)
        depth          = "Be clear and helpful."
        sections       = ["## Answer", "## Free resources"]
        time_available = ""

    tool_definitions = get_tool_definitions(selected_tools)
    max_tokens       = get_output_token_limit(question)

    print(f"\n{'='*50}")
    print(f"QUERY: {question[:80]}")
    print(f"{'='*50}")
    print(f"🎯 Mode:   {routing_mode}")
    print(f"🎯 Tools:  {selected_tools}")
    print(f"🎯 Tokens: {max_tokens}")
    print(f"💰 {budget.status()}")

    # Brief injection — keep start and end on long briefs
    assignment_content = ""
    if "assignment_brief" in documents:
        brief_text = documents["assignment_brief"]
        if len(brief_text) > 4000:
            brief_text = (
                brief_text[:2500]
                + "\n[...middle truncated...]\n"
                + brief_text[-1500:]
            )
        assignment_content = f"\nAssignment:\n{brief_text}\n"

    intake_context = ""
    if intake:
        intake_context = (
            f"\nStudent: {intake['time']} available | "
            f"{intake['level']} level | needs {intake['need']}\n"
        )

    conversation = [{
        "role": "user",
        "content": (
            f"{assignment_content}"
            f"{intake_context}"
            f"Question: {question}\n\n"
            f"Depth: {depth}\n\n"
            f"Required sections:\n"
            + "\n".join(f"  {s}" for s in sections) +
            f"\n\nRules:\n"
            f"1. knowledge_base_lookup FIRST\n"
            f"2. web_search only if KB has nothing\n"
            f"3. MAX 4 tool calls then write answer\n"
            f"4. Free resources only\n"
            f"5. Complete answer — never cut off\n"
        )
    }]

    observations    = []
    retries         = {}
    tool_calls_made = 0
    force_sent      = False

    for step in range(8):
        print(f"\n--- Step {step+1}/8 | {budget.status()} ---")

        # Reflect — force answer after 4 tool calls — ONCE
        if tool_calls_made >= 4 and not force_sent:
            force_sent = True
            print("🔍 REFLECTION: Forcing final answer")
            conversation.append({
                "role": "assistant",
                "content": "I have gathered sufficient information. Let me write the complete answer now."
            })
            conversation.append({
                "role": "user",
                "content": (
                    "Yes — write your COMPLETE final answer now. "
                    "Use these sections:\n"
                    + "\n".join(f"  {s}" for s in sections) +
                    "\nDo not call any more tools. Write the full answer now."
                )
            })

        try:
            # Remove tools after reflection — forces answer
            # Also bump tokens on the final step to reduce truncation
            active_tools  = None if force_sent else tool_definitions
            active_tokens = min(max_tokens * 2, 3000) if force_sent else max_tokens

            response = claude.messages.create(
                model=MODEL,
                max_tokens=active_tokens,
                system=system_prompt,
                **({"tools": active_tools} if active_tools else {}),
                messages=conversation,
            )
            budget.record(
                response.usage.input_tokens,
                response.usage.output_tokens
            )

        except BudgetError as e:
            print(f"\n❌ Budget exceeded: {e}")
            return json.dumps({
                "status":       "rejected_budget_exceeded",
                "reason":       str(e),
                "observations": observations,
                "routing_mode": routing_mode,
                "suggestion":   "Try a simpler question"
            })
        except Exception as e:
            print(f"\n❌ API error: {e}")
            break

        # Claude finished with a normal end_turn
        if response.stop_reason == "end_turn":
            text_blocks = [
                b.text for b in response.content
                if hasattr(b, "text") and b.text
            ]
            final_text = "\n".join(text_blocks) if text_blocks else "(Agent returned no text)"

            if observations:
                print(f"\n📋 OBSERVATIONS ({len(observations)} total):")
                for obs in observations:
                    icon = "✅" if obs["status"] == "success" else "❌"
                    print(f"  {icon} Step {obs['step']}: {obs['tool']} → {obs['result_summary'][:80]}")

            cost_line    = f"\n\n---\n💰 Tokens: {budget.total_tokens:,} | Cost: ${budget.total_cost:.4f} | Mode: {routing_mode}"
            final_answer = final_text + cost_line

            print(f"\n{'='*50}")
            print("✅ FINAL ANSWER:")
            print(f"{'='*50}")
            print(final_answer)

            # Skip human checkpoint in automated runs (ablation, eval)
            if auto_confirm:
                return final_answer

            sign_off = ask_human(
                "Happy with this answer?",
                options=["Yes, done!", "No, improve it"]
            )

            if sign_off == "No, improve it":
                feedback = ask_human("What needs improving?")
                print("\n⚡ Improving...")
                try:
                    text_only = [b for b in response.content if hasattr(b, "text")]
                    improvement = claude.messages.create(
                        model=MODEL,
                        max_tokens=min(max_tokens + 300, 2000),
                        system=system_prompt,
                        messages=conversation + [
                            {"role": "assistant", "content": text_only},
                            {"role": "user", "content": f"Improve: {feedback}. Write complete response. No tool calls."}
                        ],
                    )
                    budget.record(
                        improvement.usage.input_tokens,
                        improvement.usage.output_tokens
                    )
                    improved     = next(
                        (b.text for b in improvement.content if hasattr(b, "text")),
                        final_text
                    )
                    cost_line    = f"\n\n---\n💰 Tokens: {budget.total_tokens:,} | Cost: ${budget.total_cost:.4f} | Mode: {routing_mode}"
                    final_answer = improved + cost_line
                    print(f"\n{'='*50}")
                    print("✅ IMPROVED ANSWER:")
                    print(f"{'='*50}")
                    print(final_answer)
                except Exception as e:
                    print(f"❌ Improvement failed: {e}")

            return final_answer

        # Claude was cut off at max_tokens — extract and print partial answer
        if response.stop_reason == "max_tokens":
            text_blocks = [
                b.text for b in response.content
                if hasattr(b, "text") and b.text
            ]
            final_text = "\n".join(text_blocks) if text_blocks else "(Answer truncated — no text recovered)"
            print(f"⚠️ TRUNCATED at step {step+1} — returning partial answer ({len(final_text)} chars)")

            cost_line    = (
                f"\n\n---\n"
                f"⚠️ Answer was truncated at the token limit.\n"
                f"💰 Tokens: {budget.total_tokens:,} | Cost: ${budget.total_cost:.4f} | Mode: {routing_mode}"
            )
            final_answer = final_text + cost_line

            print(f"\n{'='*50}")
            print("✅ FINAL ANSWER (truncated):")
            print(f"{'='*50}")
            print(final_answer)

            return final_answer

        # Claude wants tools
        if response.stop_reason == "tool_use":
            conversation.append({
                "role": "assistant",
                "content": response.content
            })

            tool_blocks = [b for b in response.content if b.type == "tool_use"]
            print(f"  🔧 Tools: {[b.name for b in tool_blocks]}")

            parallel_results = run_tools_parallel(tool_blocks, retries)
            tool_calls_made += len(tool_blocks)

            tool_results = []
            for block in tool_blocks:
                result = next(
                    (r for tid, r in parallel_results if tid == block.id),
                    "Not found"
                )
                print(f"  📤 {block.name}: {str(result)[:100]}")

                observation = {
                    "step":           step + 1,
                    "tool":           block.name,
                    "input":          str(block.input)[:100],
                    "status":         "success" if "Error" not in str(result) else "failure",
                    "result_summary": str(result)[:150],
                    "next_action":    "continue" if tool_calls_made < 4 else "answer",
                }
                observations.append(observation)
                print(f"  📋 Obs: step={observation['step']} tool={observation['tool']} status={observation['status']}")

                tool_results.append({
                    "type":        "tool_result",
                    "tool_use_id": block.id,
                    "content":     str(result),
                })

            conversation.append({
                "role": "user",
                "content": tool_results
            })

    # Loop prevention
    print(f"\n⚠️ Max steps reached.")
    return json.dumps({
        "status":       "terminated_loop_prevention",
        "tools_used":   list(set(o["tool"] for o in observations)),
        "observations": observations,
        "routing_mode": routing_mode,
        "suggestion":   "Try a more specific question",
    })


# ════════════════════════════════════════════════════════════════
# MULTI-TURN CONVERSATION
# ════════════════════════════════════════════════════════════════

def run_conversation(brief: str = "") -> None:
    """Intake → initial answer → follow-up questions."""
    if brief:
        load_document("assignment_brief", brief)

    intake   = run_intake(brief)
    strategy = build_strategy(intake)

    run_agent(
        question="Help me understand and plan this assignment",
        brief=brief,
        intake=intake,
        strategy=strategy,
    )

    print("\n" + "="*50)
    print("💬 Ask follow-up questions (type 'exit' to quit)")
    print("="*50)

    while True:
        follow_up = input("\n❓ Your question: ").strip()
        if follow_up.lower() in ["exit", "quit", "done", "bye", "q"]:
            print("\n✅ Good luck with your assignment!")
            break
        if not follow_up:
            continue
        run_agent(question=follow_up, intake=intake)


# ════════════════════════════════════════════════════════════════
# PROMPT ABLATION
# ════════════════════════════════════════════════════════════════

def run_ablation(query: str, brief: str = "") -> dict:
    """Compare V1 vs V2 prompts. auto_confirm=True to skip human checkpoints."""
    print("\n🔬 PROMPT ABLATION")
    print("="*50)

    print("\n--- V1 (generic) ---")
    a1 = run_agent(query, brief=brief, prompt_version="v1", auto_confirm=True)

    print("\n--- V2 (focused) ---")
    a2 = run_agent(query, brief=brief, prompt_version="v2", auto_confirm=True)

    print(f"\n📊 Results:")
    print(f"  V1: {len(a1)} chars")
    print(f"  V2: {len(a2)} chars")
    print(f"  Delta: {len(a2)-len(a1):+d}")

    return {"v1": a1, "v2": a2}