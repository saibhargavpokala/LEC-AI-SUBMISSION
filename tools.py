import io
import os
import json
import time
import contextlib
from config import tavily

# ── Document store ────────────────────────────────────────────────
documents = {}

def load_document(name: str, content: str):
    documents[name] = content
    print(f"✅ Loaded: '{name}' ({len(content)} chars)")

def load_from_file(file_path: str) -> str:
    if not os.path.exists(file_path):
        print(f"❌ Not found: {file_path}")
        return ""
    ext     = file_path.lower().split(".")[-1]
    content = ""
    if ext == "txt":
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    elif ext == "pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(file_path)
            for page in reader.pages:
                content += page.extract_text() + "\n"
        except ImportError:
            print("❌ Run: pip install pypdf")
            return ""
    elif ext == "docx":
        try:
            import docx
            doc = docx.Document(file_path)
            for para in doc.paragraphs:
                content += para.text + "\n"
        except ImportError:
            print("❌ Run: pip install python-docx")
            return ""
    else:
        print(f"❌ Unsupported: .{ext}")
        return ""
    name = file_path.replace("\\", "/").split("/")[-1]
    load_document(name, content)
    return content


# ════════════════════════════════════════════════════════════════
# KNOWLEDGE BASE
# ════════════════════════════════════════════════════════════════

KB_FILE = "knowledge_base.json"

def _load_kb() -> dict:
    if os.path.exists(KB_FILE):
        with open(KB_FILE) as f:
            data = json.load(f)
        print(f"✅ KB: {len(data)} topics loaded")
        return data
    print("✅ KB: empty — grows as you use it")
    return {}

def _save_kb():
    with open(KB_FILE, "w") as f:
        json.dump(knowledge_base, f, indent=2)

knowledge_base = _load_kb()


# ════════════════════════════════════════════════════════════════
# ADAPTIVE HELPERS
# ════════════════════════════════════════════════════════════════

def is_complex(query: str) -> bool:
    signals = [
        "build", "implement", "create", "help me",
        "how to", "step by step", "plan", "assignment",
        "project", "system", "complete", "full guide"
    ]
    return any(w in query.lower() for w in signals)


def get_output_token_limit(query: str) -> int:
    q = query.lower()
    if is_complex(query):
        return 1500
    if any(w in q for w in ["code", "implement"]):
        return 1200
    if any(w in q for w in ["what is", "define"]):
        return 600
    return 800


# ════════════════════════════════════════════════════════════════
# TOOL ROUTER
# ════════════════════════════════════════════════════════════════

def route_tools(query: str) -> tuple[list, str]:
    """
    RESOURCES — always included
    PLAN      — when deadline mentioned
    EXAMPLES  — when coding needed
    MATH      — when numbers involved
    DOCUMENT  — when file loaded
    FALLBACK  — no specialised branch → all 8 tools, Claude decides
    """
    q        = query.lower()
    selected = []
    branches_hit = 0

    selected += [
        "knowledge_base_lookup",
        "web_search",
        "save_to_knowledge_base",
    ]

    if any(w in q for w in [
        "day", "hour", "week", "tonight",
        "tomorrow", "deadline", "due", "plan",
        "schedule", "time", "finish", "by"
    ]):
        selected.append("time_planner")
        branches_hit += 1

    if any(w in q for w in [
        "code", "python", "example", "implement",
        "function", "script", "algorithm", "program",
        "javascript", "sql", "api", "debug"
    ]):
        selected.append("code_executor")
        selected.append("github_search")
        branches_hit += 1

    if any(w in q for w in [
        "calculat", "cost", "how much", "equation",
        "math", "formula", "multiply", "divide",
        "percent", "budget", "price"
    ]):
        selected.append("calculator")
        branches_hit += 1

    if documents:
        selected.append("document_qa")
        branches_hit += 1

    if branches_hit == 0:
        all_tools = [t["name"] for t in ALL_TOOL_DEFINITIONS]
        print(f"  🎯 Router: LLM fallback (all {len(all_tools)} tools)")
        return all_tools, "llm_fallback"

    print(f"  🎯 Router: deterministic — {selected}")
    return selected, "deterministic"


def get_tool_definitions(selected_tools: list) -> list:
    return [t for t in ALL_TOOL_DEFINITIONS if t["name"] in selected_tools]


# ════════════════════════════════════════════════════════════════
# RESOURCES GROUP
# ════════════════════════════════════════════════════════════════

def knowledge_base_lookup(topic: str) -> str:
    """Check KB first — zero cost, instant."""
    key = topic.lower().strip()

    if key in knowledge_base:
        e = knowledge_base[key]
        return (
            f"✅ {key.upper()}\n"
            f"{e['explanation']}\n\n"
            f"Resources:\n" +
            "\n".join(f"  → {r}" for r in e["resources"])
        )

    matches = [
        (k, v) for k, v in knowledge_base.items()
        if key in k or k in key
    ]
    if matches:
        out = f"Related to '{topic}':\n\n"
        for k, v in matches[:3]:
            out += f"• {k.upper()}: {v['explanation'][:150]}\n"
            out += f"  → {v['resources'][0]}\n\n"
        return out

    return (
        f"'{topic}' not in KB yet. "
        f"KB has {len(knowledge_base)} topics.\n"
        f"→ Use web_search\n"
        f"→ Then save_to_knowledge_base"
    )


def web_search(query: str) -> str:
    """Search internet. Save results after."""
    for attempt in range(2):
        try:
            results = tavily.search(query, max_results=3)
            out     = f"🌐 '{query}':\n\n"
            for i, r in enumerate(results["results"], 1):
                out += f"[{i}] {r['title']}\n"
                out += f"    {r['url']}\n"
                out += f"    {r['content'][:300]}\n\n"
            return out
        except Exception as e:
            if attempt == 0:
                print("  ⚠️ Retrying...")
                time.sleep(1)
            else:
                return f"Search unavailable: {str(e)[:80]}"


def save_to_knowledge_base(topic: str, explanation: str, resources: str) -> str:
    """Save after EVERY web_search. Persists to disk."""
    knowledge_base[topic.lower()] = {
        "explanation": explanation,
        "resources":   [resources] if isinstance(resources, str) else resources,
    }
    _save_kb()
    print(f"💾 KB: '{topic}' saved ({len(knowledge_base)} total)")
    return f"✅ '{topic}' saved. Future queries free."


# ════════════════════════════════════════════════════════════════
# PLAN GROUP — updated keyword detection + new plan types
# ════════════════════════════════════════════════════════════════

def time_planner(assignment_description: str, time_available: str) -> str:
    """Realistic deadline plan for any assignment type."""
    t    = time_available.lower()
    desc = assignment_description.lower()

    # Parse time
    if any(w in t for w in ["tonight", "3 hour", "4 hour", "5 hour"]):
        hours, label = 4,  "tonight"
    elif any(w in t for w in ["1 day", "tomorrow"]):
        hours, label = 8,  "1 day"
    elif any(w in t for w in ["2 day", "weekend"]):
        hours, label = 16, "2 days"
    elif any(w in t for w in ["3 day"]):
        hours, label = 24, "3 days"
    elif any(w in t for w in ["week"]):
        hours, label = 40, "1 week"
    else:
        hours, label = 8,  "1 day"

    # Detect assignment type — ordered most specific to least.
    # Check essay/writing keywords BEFORE generic "search" terms,
    # so "binary search" doesn't trigger the retrieval branch.
    if any(w in desc for w in [
        "essay", "report", "analyse", "analyze", "discuss",
        "history", "english", "literature", "philosophy",
        "argue", "critique", "word count", "1000 word", "2000 word"
    ]):
        atype = "essay"
    elif any(w in desc for w in [
        "math", "equation", "calcul", "solve", "integral",
        "derivative", "proof", "theorem"
    ]):
        atype = "math"
    elif any(w in desc for w in [
        "implement", "python", "javascript", "algorithm",
        "function", "debug", "api", "script", "sort", "tree",
        "graph", "hash", "linked list", "binary search",
        "data structure"
    ]):
        atype = "code"
    elif any(w in desc for w in [
        "agent", "orchestrat", "retrieval", "rag",
        "vector", "embedding", "llm", "prompt"
    ]):
        atype = "llm_assignment"
    else:
        atype = "general"

    plans = {
        "essay":     {
            4:  ["H1: Research", "H2: Outline", "H3: Write", "H4: Edit"],
            8:  ["H1-2: Research", "H3: Outline", "H4-6: Write", "H7-8: Edit"],
            16: ["D1: Research + outline", "D2: Write + edit"],
            24: ["D1: Research", "D2: Outline + draft", "D3: Edit + submit"],
            40: ["D1-2: Research", "D3-4: Write", "D5: Edit"],
        },
        "math":      {
            4:  ["H1: Understand", "H2: Research", "H3: Solve", "H4: Verify"],
            8:  ["H1-2: Learn", "H3-6: Solve", "H7-8: Verify"],
            16: ["D1: Learn + practice", "D2: Solve + submit"],
            24: ["D1: Learn", "D2: Solve", "D3: Verify + submit"],
            40: ["D1-2: Learn", "D3-4: Solve", "D5: Submit"],
        },
        "code":      {
            4:  ["H1: Understand problem", "H2: Core implementation", "H3: Test + edge cases", "H4: Submit"],
            8:  ["H1-2: Concepts + setup", "H3-5: Implementation", "H6-7: Testing", "H8: Submit"],
            16: ["D1: Design + core code", "D2: Test + submit"],
            24: ["D1: Design + scaffolding", "D2: Implementation", "D3: Test + submit"],
            40: ["D1-2: Concepts + design", "D3-4: Implementation + tests", "D5: Polish + submit"],
        },
        "llm_assignment": {
            4:  ["H1: Setup + tools", "H2: Core loop", "H3: Eval", "H4: Report"],
            8:  ["H1-2: Setup", "H3-5: Core implementation", "H6-7: Eval", "H8: Report"],
            16: ["D1: Build core", "D2: Eval + report"],
            24: ["D1: Setup + tools", "D2: Core loop + eval", "D3: Report + submit"],
            40: ["D1-2: Build", "D3: Eval", "D4-5: Report"],
        },
        "general":   {
            4:  ["H1: Understand", "H2: Research", "H3: Do", "H4: Submit"],
            8:  ["H1-2: Research", "H3-6: Do", "H7-8: Review + submit"],
            16: ["D1: Research + plan", "D2: Do + submit"],
            24: ["D1: Research", "D2: Do", "D3: Review + submit"],
            40: ["D1-2: Research", "D3-4: Do", "D5: Submit"],
        },
    }

    plan  = plans.get(atype, plans["general"])
    hkey  = min(plan.keys(), key=lambda x: abs(x - hours))
    steps = plan[hkey]

    out = f"📅 {label} | {atype}\n\n"
    for s in steps:
        out += f"  ✓ {s}\n"

    if hours <= 8:
        skips = {
            "essay":         "Skip if tight: deep research, use key sources only",
            "math":          "Skip if tight: show working, just give answers",
            "code":          "Skip if tight: refactoring, docs, performance optimisation",
            "llm_assignment":"Skip if tight: prompt ablation, parallel exec, tracing",
            "general":       "Focus on must-haves first",
        }
        out += f"\n⚡ {skips.get(atype, 'Focus on must-haves')}"

    return out


# ════════════════════════════════════════════════════════════════
# EXAMPLES GROUP
# ════════════════════════════════════════════════════════════════

def code_executor(code: str) -> str:
    """Run Python safely. Tests before showing student."""
    blocked = ["import os", "import sys", "subprocess", "open(", "shutil"]
    for b in blocked:
        if b in code:
            return f"❌ Blocked: '{b}'"
    capture = io.StringIO()
    try:
        with contextlib.redirect_stdout(capture):
            exec(code, {"__builtins__": {
                "print": print, "range": range, "len": len,
                "sum": sum, "min": min, "max": max,
                "abs": abs, "round": round, "int": int,
                "float": float, "str": str, "list": list,
                "dict": dict, "set": set, "tuple": tuple,
                "enumerate": enumerate, "zip": zip,
                "sorted": sorted, "type": type,
            }})
        out = capture.getvalue()
        return f"✅ Works!\n{out}" if out else "✅ Ran successfully."
    except Exception as e:
        return f"❌ Error: {e}"


def github_search(query: str) -> str:
    """Find real code examples on GitHub."""
    import urllib.request
    import urllib.parse
    import json as _json
    try:
        encoded  = urllib.parse.quote(query)
        url      = f"https://api.github.com/search/repositories?q={encoded}&sort=stars&per_page=3"
        req      = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        response = urllib.request.urlopen(req, timeout=10)
        data     = _json.loads(response.read())
        if not data.get("items"):
            return f"No results for '{query}'"
        out = f"🐙 GitHub '{query}':\n\n"
        for repo in data["items"][:3]:
            out += f"⭐ {repo.get('stargazers_count',0):,} | {repo['full_name']}\n"
            out += f"   {(repo.get('description') or 'No description')[:100]}\n"
            out += f"   {repo['html_url']}\n\n"
        return out
    except Exception as e:
        return f"GitHub unavailable: {str(e)[:80]}"


# ════════════════════════════════════════════════════════════════
# MATH GROUP
# ════════════════════════════════════════════════════════════════

def calculator(expression: str) -> str:
    """Safe math. Arithmetic, costs, budgets."""
    try:
        allowed = set("0123456789+-*/.() ")
        if not all(c in allowed for c in expression):
            return "Error: only basic arithmetic allowed"
        return f"Result: {eval(expression)}"
    except Exception as e:
        return f"Error: {e}"


# ════════════════════════════════════════════════════════════════
# DOCUMENT GROUP
# ════════════════════════════════════════════════════════════════

def document_qa(question: str, document_name: str = "") -> str:
    """Read loaded assignment documents."""
    if not documents:
        return "No documents loaded."
    docs  = (
        {document_name: documents[document_name]}
        if document_name and document_name in documents
        else documents
    )
    words = [w for w in question.lower().split() if len(w) > 3]
    fallback = None
    for name, content in docs.items():
        lines = [
            l.strip() for l in content.split("\n")
            if l.strip() and any(w in l.lower() for w in words)
        ]
        if lines:
            return f"From '{name}':\n" + "\n".join(lines[:10])
        if fallback is None:
            fallback = f"Document '{name}':\n{content[:1500]}"
    return fallback or "Nothing found."


# ════════════════════════════════════════════════════════════════
# TOOL DEFINITIONS + DISPATCHER
# ════════════════════════════════════════════════════════════════

ALL_TOOL_DEFINITIONS = [
    {
        "name": "knowledge_base_lookup",
        "description": "ALWAYS check first — free and instant. Grows smarter every session.",
        "input_schema": {"type": "object",
                         "properties": {"topic": {"type": "string"}},
                         "required": ["topic"]}
    },
    {
        "name": "web_search",
        "description": "Search internet when KB has nothing. Always save after.",
        "input_schema": {"type": "object",
                         "properties": {"query": {"type": "string"}},
                         "required": ["query"]}
    },
    {
        "name": "save_to_knowledge_base",
        "description": "Save after EVERY web_search. Makes future queries free.",
        "input_schema": {"type": "object",
                         "properties": {
                             "topic":       {"type": "string"},
                             "explanation": {"type": "string"},
                             "resources":   {"type": "string"},
                         },
                         "required": ["topic", "explanation", "resources"]}
    },
    {
        "name": "time_planner",
        "description": "Realistic deadline plan. Detects assignment type automatically.",
        "input_schema": {"type": "object",
                         "properties": {
                             "assignment_description": {"type": "string"},
                             "time_available":         {"type": "string"},
                         },
                         "required": ["assignment_description", "time_available"]}
    },
    {
        "name": "code_executor",
        "description": "Run Python safely. Only for coding tasks.",
        "input_schema": {"type": "object",
                         "properties": {"code": {"type": "string"}},
                         "required": ["code"]}
    },
    {
        "name": "github_search",
        "description": "Find real code examples on GitHub. Only for coding.",
        "input_schema": {"type": "object",
                         "properties": {"query": {"type": "string"}},
                         "required": ["query"]}
    },
    {
        "name": "calculator",
        "description": "Safe math. Arithmetic, costs, budgets.",
        "input_schema": {"type": "object",
                         "properties": {"expression": {"type": "string"}},
                         "required": ["expression"]}
    },
    {
        "name": "document_qa",
        "description": "Read loaded assignment documents.",
        "input_schema": {"type": "object",
                         "properties": {
                             "question":      {"type": "string"},
                             "document_name": {"type": "string"},
                         },
                         "required": ["question"]}
    },
]

TOOL_MAP = {
    "knowledge_base_lookup":  knowledge_base_lookup,
    "web_search":             web_search,
    "save_to_knowledge_base": save_to_knowledge_base,
    "time_planner":           time_planner,
    "code_executor":          code_executor,
    "github_search":          github_search,
    "calculator":             calculator,
    "document_qa":            document_qa,
}

def run_tool(name: str, inputs: dict) -> str:
    if name in TOOL_MAP:
        return TOOL_MAP[name](**inputs)
    return f"Unknown tool: '{name}'"