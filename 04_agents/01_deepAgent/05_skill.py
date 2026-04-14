"""
05_skill.py — How Skills Work in DeepAgent
===========================================
A skill is a directory containing a SKILL.md file with YAML frontmatter.
DeepAgent loads skills at startup and injects their names + descriptions
into the system prompt (progressive disclosure).

The agent sees:
  - skill name + description     → always (knows when to activate)
  - full SKILL.md content        → only when it reads the file (saves tokens)

We use FilesystemBackend so skills live on disk and the agent can actually
read their full content using the built-in read_file tool.

Folder layout (pre-created in ./skills/):
  skills/
  ├── code-reviewer/
  │   └── SKILL.md    ← structured code review workflow
  ├── data-analyst/
  │   └── SKILL.md    ← data analysis workflow
  └── project/
      └── code-reviewer/
          └── SKILL.md    ← strict override for demo 4

Topics covered:
  1. SINGLE    — agent uses one skill
  2. MULTI     — agent chooses from two skills automatically
  3. OVERRIDE  — later skill source wins when names clash
"""

import os
from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

# ─────────────────────────────────────────────────────────────
# Skills live in ./skills/ next to this script
# FilesystemBackend(root_dir=SCRIPT_DIR) maps "/" → SCRIPT_DIR
# so skills=["/skills"] resolves to SCRIPT_DIR/skills/ on disk
# ─────────────────────────────────────────────────────────────
SCRIPT_DIR  = Path(__file__).parent
SKILLS_PATH = "/skills"   # POSIX path the agent sees inside FilesystemBackend


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
# 1. SINGLE — agent uses one specific skill
#
# FilesystemBackend(root_dir=SCRIPT_DIR) maps "/" to SCRIPT_DIR.
# So skills=["/skills"] looks for subdirectories in SCRIPT_DIR/skills/.
# ─────────────────────────────────────────────────────────────

def demo_single_skill():
    _header("1. SINGLE — Agent uses the code-reviewer skill")

    backend = FilesystemBackend(root_dir=str(SCRIPT_DIR))
    agent = create_deep_agent(
        model=_make_model(),
        skills=[SKILLS_PATH],
        backend=backend,
        system_prompt=(
            "You are a code reviewer. "
            "When asked to review code, use your code-reviewer skill."
        ),
    )

    code_to_review = """\
def get_user(user_id):
    query = "SELECT * FROM users WHERE id = " + user_id
    result = db.execute(query)
    return result[0]
"""

    result = agent.invoke({"messages": [{"role": "user", "content":
        f"Please review this Python function:\n\n```python\n{code_to_review}```"}]})

    print(result["messages"][-1].content)
    print("\n→ Agent loaded the code-reviewer skill and followed its checklist.")


# ─────────────────────────────────────────────────────────────
# 3. MULTI — agent sees two skills, picks the right one
#
# Both skill names + descriptions are injected into the system
# prompt. The agent decides which skill applies based on the task.
# ─────────────────────────────────────────────────────────────

def demo_multi_skill():
    _header("2. MULTI — Agent chooses from two skills automatically")

    backend = FilesystemBackend(root_dir=str(SCRIPT_DIR))
    agent = create_deep_agent(
        model=_make_model(),
        skills=[SKILLS_PATH],
        backend=backend,
    )

    data = """\
Month, Revenue, Customers
Jan, 12400, 98
Feb, 9800, 76
Mar, 15600, 124
Apr, 11200, 89
May, 18900, 153
Jun, 21300, 177
"""

    result = agent.invoke({"messages": [{"role": "user", "content":
        f"Analyse this business data and tell me what you find:\n\n{data}"}]})

    print(result["messages"][-1].content)
    print("\n→ Agent selected data-analyst skill (not code-reviewer) based on the task.")


# ─────────────────────────────────────────────────────────────
# 4. OVERRIDE — later source wins when skill names clash
#
# If two sources define a skill with the same name, the last
# source wins. This lets you layer: base → user → project.
# ─────────────────────────────────────────────────────────────

def demo_skill_override():
    _header("3. OVERRIDE — Later skill source replaces earlier one")

    backend = FilesystemBackend(root_dir=str(SCRIPT_DIR))
    agent = create_deep_agent(
        model=_make_model(),
        # base skills first, project skills second — project wins on name clash
        skills=[SKILLS_PATH, "/skills/project"],
        backend=backend,
    )

    code_to_review = """\
def process(x):
    try:
        return int(x) * 2
    except:
        pass
"""

    result = agent.invoke({"messages": [{"role": "user", "content":
        f"Review this code:\n\n```python\n{code_to_review}```"}]})

    print(result["messages"][-1].content)
    print("\n→ Project-level code-reviewer replaced the base one (last source wins).")


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    demo_single_skill()    # agent uses code-reviewer skill
    demo_multi_skill()     # agent picks data-analyst skill automatically
    demo_skill_override()  # project skill overrides base skill
