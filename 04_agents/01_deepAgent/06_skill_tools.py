"""
06_skill_tools.py — Tools Inside Skill Directories
====================================================
Tools (Python scripts) live inside the skill folder alongside SKILL.md.
The SKILL.md tells the agent what scripts exist and how to call them.
The agent runs them with its built-in `execute` tool — no Python tool
registration needed.

Skill layout:
  skills/
  ├── sql-helper/
  │   ├── SKILL.md          ← references run_query.py and explain_query.py
  │   ├── run_query.py      ← runs SQL against orders.db
  │   ├── explain_query.py  ← shows query plan
  │   └── setup_db.py       ← one-time DB seed (run manually)
  └── text-summarizer/
      ├── SKILL.md          ← references analyze_text.py
      └── analyze_text.py   ← counts words + extracts keywords

Why LocalShellBackend:
  FilesystemBackend alone cannot run shell commands.
  LocalShellBackend extends it with SandboxBackendProtocol,
  which enables the built-in `execute` tool.

Setup (run once before the demos):
  cd skills/sql-helper && python setup_db.py
"""

import os
from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends.local_shell import LocalShellBackend
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

SCRIPT_DIR  = Path(__file__).parent
SKILLS_PATH = "/skills"


def _make_model():
    return ChatOpenAI(
        model=os.environ["AZURE_OPENAI_DEPLOYMENT"],
        base_url=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
    )


def _header(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


# ─────────────────────────────────────────────────────────────
# LocalShellBackend:
#   root_dir = SCRIPT_DIR  →  "/" maps to this folder on disk
#   Enables the `execute` tool so the agent can run shell cmds
# ─────────────────────────────────────────────────────────────

def _make_backend() -> LocalShellBackend:
    return LocalShellBackend(root_dir=str(SCRIPT_DIR))


# ─────────────────────────────────────────────────────────────
# 1. SQL — agent reads SKILL.md then runs run_query.py
# ─────────────────────────────────────────────────────────────

def demo_sql():
    _header("1. SQL — script inside skill directory")

    agent = create_deep_agent(
        model=_make_model(),
        skills=[SKILLS_PATH],
        backend=_make_backend(),
    )

    result = agent.invoke({"messages": [{"role": "user", "content":
        "Show me total revenue per customer from the orders table, sorted highest first."}]})

    print(result["messages"][-1].content)
    print("\n→ Agent read SKILL.md, called: python /skills/sql-helper/run_query.py '...'")
    print("  No Python @tool functions registered — script runs via execute.")


# ─────────────────────────────────────────────────────────────
# 2. TEXT — agent reads SKILL.md then runs analyze_text.py
# ─────────────────────────────────────────────────────────────

def demo_text():
    _header("2. TEXT — script inside skill directory")

    agent = create_deep_agent(
        model=_make_model(),
        skills=[SKILLS_PATH],
        backend=_make_backend(),
    )

    result = agent.invoke({"messages": [{"role": "user", "content":
        "Summarise this: "
        "Machine learning is a branch of artificial intelligence that enables systems "
        "to learn and improve from experience without being explicitly programmed. "
        "It focuses on developing computer programs that can access data and use it "
        "to learn for themselves. The process begins with observations or data such "
        "as examples or direct experience to look for patterns in data and make better "
        "decisions in the future. The primary aim is to allow computers to learn "
        "automatically without human intervention or assistance."}]})

    print(result["messages"][-1].content)
    print("\n→ Agent ran analyze_text.py via execute, used output to write the summary.")


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    demo_sql()
    demo_text()
