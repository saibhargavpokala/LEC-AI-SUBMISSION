"""
Streamlit UI wrapper for the Assignment Support Agent.

Runs alongside the CLI — does NOT modify agent.py.
Launch with:   streamlit run app.py
"""

import io
import sys
import streamlit as st
from contextlib import redirect_stdout
from agent import run_agent, run_intake, build_strategy
from tools import load_document, knowledge_base, documents
from config import TOKEN_CAP, COST_CAP


# ────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Assignment Support Agent",
    page_icon="🎓",
    layout="wide",
)

st.title("🎓 Assignment Support Agent")
st.caption("LEC AI — Production Agentic System")


# ────────────────────────────────────────────────────────────────
# MONKEY-PATCH ask_human (CLI uses input() — dead in Streamlit)
# Auto-accept answers in the UI. Documented in the report.
# ────────────────────────────────────────────────────────────────
import checkpoints
checkpoints.ask_human = lambda *a, **kw: "Yes, done!"


# ────────────────────────────────────────────────────────────────
# SIDEBAR — intake + budget
# ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Setup")

    brief = st.text_area(
        "Paste assignment brief (optional)",
        height=150,
        placeholder="Paste the assignment PDF text, or leave blank.",
    )

    time_available = st.selectbox(
        "Time available",
        ["tonight", "1 day", "2 days", "1 week"],
        index=1,
    )
    level = st.selectbox(
        "Level",
        ["beginner", "intermediate", "expert"],
        index=1,
    )
    need = st.selectbox(
        "What do you need?",
        ["all", "concepts", "plan", "code"],
        index=0,
    )

    st.divider()
    st.subheader("💰 Budget")
    st.caption(f"Cap: {TOKEN_CAP:,} tokens / ${COST_CAP:.2f}")
    st.caption(f"KB size: {len(knowledge_base)} topics")

    st.divider()
    st.subheader("🧰 8 tools")
    st.caption(
        "knowledge_base_lookup • web_search • save_to_knowledge_base • "
        "time_planner • code_executor • github_search • calculator • document_qa"
    )


# ────────────────────────────────────────────────────────────────
# MAIN AREA
# ────────────────────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []

# Show past Q&A
for item in st.session_state.history:
    with st.chat_message("user"):
        st.write(item["q"])
    with st.chat_message("assistant"):
        st.markdown(item["a"])
        with st.expander("🪵 Agent logs"):
            st.code(item["logs"], language="text")

# Input box
question = st.chat_input("Ask anything about your assignment...")

if question:
    with st.chat_message("user"):
        st.write(question)

    # Load the brief into the agent's document store
    if brief.strip():
        load_document("assignment_brief", brief)

    # Build intake + strategy from sidebar
    intake   = {"time": time_available, "level": level, "need": need}
    strategy = build_strategy(intake)

    # Capture the agent's stdout for the logs pane
    log_buffer = io.StringIO()
    with st.chat_message("assistant"):
        with st.spinner("Thinking... (tools, search, planning)"):
            try:
                with redirect_stdout(log_buffer):
                    answer = run_agent(
                        question=question,
                        intake=intake,
                        strategy=strategy,
                    )
            except Exception as e:
                answer = f"❌ Agent error: {e}"

        st.markdown(answer)
        logs = log_buffer.getvalue()
        with st.expander("🪵 Agent logs"):
            st.code(logs, language="text")

    st.session_state.history.append({
        "q":    question,
        "a":    answer,
        "logs": logs,
    })