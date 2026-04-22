import os
from pathlib import Path
from anthropic import Anthropic
from tavily import TavilyClient
from dotenv import load_dotenv

# Load .env from the project root
load_dotenv(Path(__file__).resolve().parent / ".env")


# ─── Secrets (loaded from .env, never hardcoded) ────────────────
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
TAVILY_API_KEY    = os.environ["TAVILY_API_KEY"]
LANGCHAIN_API_KEY = os.environ["LANGCHAIN_API_KEY"]


# ─── LangSmith tracing config ───────────────────────────────────
os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
os.environ.setdefault("LANGSMITH_TRACING",    "true")
os.environ.setdefault("LANGSMITH_API_KEY",    LANGCHAIN_API_KEY)
os.environ.setdefault("LANGCHAIN_PROJECT",    "lec-ai-agent")
os.environ.setdefault("LANGSMITH_ENDPOINT",   "https://api.smith.langchain.com")


# ─── Model + budget settings ────────────────────────────────────
MODEL     = "claude-sonnet-4-5"
TOKEN_CAP = 50_000
COST_CAP  = 0.50


# ─── API clients ────────────────────────────────────────────────
claude = Anthropic(api_key=ANTHROPIC_API_KEY)
tavily = TavilyClient(api_key=TAVILY_API_KEY)