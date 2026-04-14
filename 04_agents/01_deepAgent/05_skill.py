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

Folder layout created by this script:
  skills/
  ├── code-reviewer/
  │   └── SKILL.md    ← structured code review workflow
  └── data-analyst/
      └── SKILL.md    ← data analysis workflow

Topics covered:
  1. CREATE    — write skill files to disk
  2. SINGLE    — agent uses one skill
  3. MULTI     — agent chooses from two skills automatically
  4. OVERRIDE  — later skill source wins when names clash
"""

import os
import textwrap
from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

# ─────────────────────────────────────────────────────────────
# Skill directory — created next to this script
# ─────────────────────────────────────────────────────────────
SCRIPT_DIR  = Path(__file__).parent
SKILLS_DIR  = SCRIPT_DIR / "skills"
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
# 1. CREATE — write skill files to disk
#
# A skill is just a directory named after the skill, containing
# a SKILL.md file with this required YAML frontmatter:
#   name:        (must match the directory name)
#   description: (shown to the agent — determines when it activates)
# ─────────────────────────────────────────────────────────────

def create_skills():
    """Write two example skill directories to disk."""
    _header("1. CREATE — Write skill files to disk")

    # Skill 1: code-reviewer
    code_reviewer_dir = SKILLS_DIR / "code-reviewer"
    code_reviewer_dir.mkdir(parents=True, exist_ok=True)
    (code_reviewer_dir / "SKILL.md").write_text(textwrap.dedent("""\
        ---
        name: code-reviewer
        description: Structured code review. Use when the user asks to review, audit, or critique code quality, bugs, or style.
        license: MIT
        ---

        # Code Review Skill

        ## When to Use
        - User says "review my code", "audit this", "check for bugs", "critique"
        - Any request to evaluate code quality, correctness, or style

        ## Review Checklist

        Work through these sections in order. For each item, state: ✅ Pass, ⚠️ Warning, or ❌ Fail.

        ### 1. Correctness
        - Are there any logic errors or off-by-one mistakes?
        - Does the code handle edge cases (empty input, None, zero)?
        - Are exceptions caught where appropriate?

        ### 2. Security
        - Any SQL injection, XSS, or command injection risks?
        - Are secrets hardcoded?
        - Is user input validated?

        ### 3. Performance
        - Any obvious O(n²) loops that could be O(n)?
        - Unnecessary database calls inside loops?

        ### 4. Readability
        - Are variable and function names clear?
        - Is complex logic commented?

        ## Output Format
        Produce a short report:
        ```
        ## Code Review Report

        ### Summary
        <one sentence verdict>

        ### Findings
        | Severity | Finding |
        |----------|---------|
        | ❌ High  | ... |
        | ⚠️ Medium | ... |
        | ✅ Pass  | ... |

        ### Recommendation
        <what to fix first>
        ```
    """), encoding="utf-8")

    # Skill 2: data-analyst
    data_analyst_dir = SKILLS_DIR / "data-analyst"
    data_analyst_dir.mkdir(parents=True, exist_ok=True)
    (data_analyst_dir / "SKILL.md").write_text(textwrap.dedent("""\
        ---
        name: data-analyst
        description: Structured data analysis. Use when the user provides numbers, tables, or datasets and asks for insights, trends, or summaries.
        license: MIT
        ---

        # Data Analysis Skill

        ## When to Use
        - User says "analyse this data", "what do these numbers mean?", "find trends"
        - Any request involving tables, lists of values, or metrics

        ## Analysis Steps

        1. **Understand the data** — identify columns/fields, data types, size
        2. **Descriptive stats** — min, max, mean, median for numeric fields
        3. **Spot anomalies** — outliers, missing values, duplicates
        4. **Find patterns** — trends over time, correlations, top/bottom N
        5. **Summarise** — write 3–5 bullet insights a non-technical reader can act on

        ## Output Format
        ```
        ## Data Analysis Report

        ### Dataset Overview
        <rows, columns, types>

        ### Key Statistics
        <min/max/mean for each numeric field>

        ### Notable Patterns
        - ...
        - ...

        ### Actionable Insights
        1. ...
        2. ...
        ```
    """), encoding="utf-8")

    print(f"Created: {code_reviewer_dir / 'SKILL.md'}")
    print(f"Created: {data_analyst_dir / 'SKILL.md'}")
    print("\n→ Each skill is a directory + SKILL.md with YAML frontmatter.")
    print("  name must match the directory name exactly.")


# ─────────────────────────────────────────────────────────────
# 2. SINGLE — agent uses one specific skill
#
# FilesystemBackend(root_dir=SCRIPT_DIR) maps "/" to SCRIPT_DIR.
# So skills=["/skills"] looks for subdirectories in SCRIPT_DIR/skills/.
# ─────────────────────────────────────────────────────────────

def demo_single_skill():
    _header("2. SINGLE — Agent uses the code-reviewer skill")

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
    _header("3. MULTI — Agent chooses from two skills automatically")

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
    _header("4. OVERRIDE — Later skill source replaces earlier one")

    # Create a "project" version of code-reviewer with stricter rules
    project_dir = SKILLS_DIR / "project" / "code-reviewer"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "SKILL.md").write_text(textwrap.dedent("""\
        ---
        name: code-reviewer
        description: Strict code review for production code. Enforces team standards.
        license: MIT
        ---

        # Project Code Review Skill (STRICT MODE)

        This is the PROJECT-LEVEL override. It adds extra rules on top of the base review.

        ## Extra Rules (Team Standards)
        - All functions MUST have docstrings
        - No bare `except:` clauses — always catch specific exceptions
        - All database queries MUST use parameterised statements (no string concatenation)
        - Functions longer than 20 lines must be refactored

        ## Output
        State clearly at the top: "PROJECT SKILL (strict mode) applied."
        Then follow the standard review format.
    """), encoding="utf-8")

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
    create_skills()          # write skill files to disk first
    demo_single_skill()      # agent uses code-reviewer skill
    demo_multi_skill()       # agent picks data-analyst skill automatically
    demo_skill_override()    # project skill overrides base skill
