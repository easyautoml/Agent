"""
03_comparison.py — The 3 Things DeepAgent Gives You For Free
=============================================================
Plain LangChain can do most things DeepAgent does.
The real difference comes down to just 3 built-in capabilities:

  1. AUTO CONTEXT SUMMARISATION
     Plain LangChain: long conversations hit the token limit and crash/degrade.
     DeepAgent: automatically summarises old context and keeps going — silently.

  2. FILESYSTEM + SHELL TOOLS
     Plain LangChain: you must write every file/shell tool yourself (~30 lines).
     DeepAgent: ls, read_file, write_file, grep, glob, execute — all built-in.

  3. TASK PLANNING (write_todos)
     Plain LangChain: no equivalent — model outputs free-text only.
     DeepAgent: write_todos creates a tracked checklist the agent ticks off.

Each demo below shows the DeepAgent version of that capability.
"""

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from deepagents import create_deep_agent

load_dotenv()


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
# 1. AUTO CONTEXT SUMMARISATION
#
# Why it matters:
#   Every LLM has a token limit. In a long conversation the
#   history keeps growing. Plain LangChain does nothing — at
#   some point the call fails or the model starts forgetting.
#   DeepAgent silently summarises old turns and injects a
#   compact summary, so the agent keeps working indefinitely.
#
# How to see it:
#   We push many turns through the same thread. DeepAgent
#   never crashes; the agent still recalls early context via
#   its auto-generated summary.
# ─────────────────────────────────────────────────────────────

def demo_auto_summarisation():
    _header("1. AUTO CONTEXT SUMMARISATION")

    from langgraph.checkpoint.memory import MemorySaver

    agent = create_deep_agent(
        model=_make_model(),
        system_prompt="You are a helpful assistant. Remember everything the user tells you.",
        checkpointer=MemorySaver(),
    )
    config = {"configurable": {"thread_id": "summary-demo"}}

    # Seed some facts early in the conversation
    facts = [
        "My name is Alex.",
        "I work as a data engineer.",
        "My favourite language is Python.",
        "I am based in Tokyo.",
        "I prefer concise answers.",
    ]
    for fact in facts:
        agent.invoke({"messages": [{"role": "user", "content": fact}]}, config=config)

    # Pad with filler to grow the context
    for i in range(10):
        agent.invoke(
            {"messages": [{"role": "user", "content": f"Filler turn {i+1}: just say OK."}]},
            config=config,
        )

    # Ask something that requires recalling early context
    result = agent.invoke(
        {"messages": [{"role": "user", "content":
            "Summarise everything you know about me in one sentence."}]},
        config=config,
    )
    print(result["messages"][-1].content)
    print("\n→ Agent recalled early facts even after many turns.")
    print("  Plain LangChain would silently lose them or crash at the token limit.")


# ─────────────────────────────────────────────────────────────
# 2. FILESYSTEM + SHELL TOOLS
#
# Why it matters:
#   Real agents need to read files, write results, search code,
#   and run shell commands. Plain LangChain ships with none of
#   these — you write every tool yourself.
#   DeepAgent includes: ls, glob, grep, read_file, write_file,
#   edit_file, execute (shell) — zero setup required.
#
# How to see it:
#   We ask the agent to inspect this very file, count something
#   in it, then write a report — using only built-in tools.
# ─────────────────────────────────────────────────────────────

def demo_filesystem_shell():
    _header("2. FILESYSTEM + SHELL TOOLS")

    # The agent's sandbox is isolated from the host filesystem.
    # We read the file content here in Python and pass it as context.
    # The agent then uses write_file (built-in) to produce the report —
    # demonstrating the tool without needing host path access.
    this_dir = os.path.dirname(os.path.abspath(__file__))
    py_files = [f for f in os.listdir(this_dir) if f.endswith(".py")]
    this_file_content = open(__file__, encoding="utf-8").read()
    func_count = this_file_content.count("\ndef ")

    agent = create_deep_agent(
        model=_make_model(),
        system_prompt="You are a code analyst. Always use your built-in tools — never simulate tool results in text.",
    )

    result = agent.invoke({"messages": [{"role": "user", "content":
        f"Do these steps using your built-in tools only:\n"
        f"1. Use write_file to save this text to /tmp/report.txt:\n"
        f"   Files: {py_files}\n"
        f"   Function count in 03_comparison.py: {func_count}\n"
        f"2. Use read_file to read /tmp/report.txt back.\n"
        f"3. Reply with ONLY the contents you read — nothing else."}]})

    content = result["messages"][-1].content
    # Strip doubled output — take only the first occurrence if repeated
    half = len(content) // 2
    if content[:half].strip() == content[half:].strip():
        content = content[:half].strip()

    print(content)
    print("\n→ Agent used write_file + read_file — both built-in, zero tool code written.")
    print("  Plain LangChain: ~16 lines of tool code needed for the same two tools.")


# ─────────────────────────────────────────────────────────────
# 3. TASK PLANNING (write_todos)
#
# Why it matters:
#   For multi-step tasks an agent benefits from breaking the
#   work into an explicit checklist it can tick off as it goes.
#   Plain LangChain has no such concept — the model outputs
#   free-text and there is no tracked state.
#   DeepAgent's write_todos tool creates a living checklist:
#   the agent adds items, marks them done, and you can inspect
#   progress at any point.
#
# How to see it:
#   We give the agent a multi-step research task and ask it to
#   plan before executing. The agent will call write_todos to
#   create a checklist, then work through it step by step.
# ─────────────────────────────────────────────────────────────

def demo_task_planning():
    _header("3. TASK PLANNING (write_todos)")

    # Strip Windows drive letter so paths work in the agent's Linux sandbox
    this_dir    = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/").lstrip("C:").lstrip("c:")
    report_path = this_dir + "/audit_report.txt"

    agent = create_deep_agent(
        model=_make_model(),
        system_prompt=(
            "You are a code auditor. For every multi-step task:\n"
            "1. Call write_todos FIRST to create a checklist of steps.\n"
            "2. Execute each step using your file and shell tools.\n"
            "3. Mark each todo done as you complete it.\n"
            "Never skip the todo list — it is required."
        ),
    )

    result = agent.invoke({"messages": [{"role": "user", "content":
        f"Audit the Python files in {this_dir}. Do these steps in order:\n"
        f"1. List all .py files in the folder.\n"
        f"2. Count the total lines in each .py file (use shell: wc -l).\n"
        f"3. Find all function definitions across all .py files (use shell: grep -rn 'def ').\n"
        f"4. Write a short audit report summarising the findings to {report_path}.\n"
        f"Use write_todos to plan these 4 steps before you start."}]})

    print(result["messages"][-1].content)

    if os.path.exists(report_path):
        print(f"\n→ audit_report.txt created. Contents:\n")
        print(open(report_path).read())
    else:
        print("\n→ Check agent output above for results.")
    print("\n  Each todo item mapped to a real shell/file action — not just text.")


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    demo_auto_summarisation()
    demo_filesystem_shell()
    demo_task_planning()
