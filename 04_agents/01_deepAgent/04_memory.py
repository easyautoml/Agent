"""
04_memory.py — How MemorySaver Works with DeepAgent
=====================================================
MemorySaver is LangGraph's in-memory checkpointer.
It saves the full conversation state after every step,
keyed by thread_id — enabling multi-turn memory.

Topics covered:
  1. BASIC        — single thread, multi-turn recall
  2. MULTI-THREAD — each thread_id is an isolated conversation
  3. INSPECT      — read the saved state directly
  4. RESET        — clear a thread by overwriting its state
  5. CUSTOM       — SqliteSaver for persistence across restarts
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
# 1. BASIC — multi-turn recall within one thread
#
# MemorySaver stores state in a Python dict (in-process).
# The thread_id is the key — same thread_id = same memory.
# ─────────────────────────────────────────────────────────────

def demo_basic():
    _header("1. BASIC — Multi-turn recall")

    from langgraph.checkpoint.memory import MemorySaver

    checkpointer = MemorySaver()
    agent = create_deep_agent(model=_make_model(), checkpointer=checkpointer)
    config = {"configurable": {"thread_id": "user-alice"}}

    turns = [
        "My name is Alice and I love hiking.",
        "I am planning a trip to Nepal next year.",
        "What do you know about me so far?",   # should recall both facts
    ]
    for msg in turns:
        print(f"\nUser : {msg}")
        result = agent.invoke({"messages": [{"role": "user", "content": msg}]}, config=config)
        print(f"Agent: {result['messages'][-1].content}")


# ─────────────────────────────────────────────────────────────
# 2. MULTI-THREAD — each thread_id is fully isolated
#
# Two users, same agent, same checkpointer — but different
# thread_ids mean they never see each other's history.
# ─────────────────────────────────────────────────────────────

def demo_multi_thread():
    _header("2. MULTI-THREAD — isolated conversations")

    from langgraph.checkpoint.memory import MemorySaver

    checkpointer = MemorySaver()   # one shared checkpointer
    agent = create_deep_agent(model=_make_model(), checkpointer=checkpointer)

    cfg_alice = {"configurable": {"thread_id": "alice"}}
    cfg_bob   = {"configurable": {"thread_id": "bob"}}

    # Alice sets her context
    agent.invoke({"messages": [{"role": "user", "content": "I am Alice, I like cats."}]}, config=cfg_alice)
    # Bob sets his context
    agent.invoke({"messages": [{"role": "user", "content": "I am Bob, I like dogs."}]}, config=cfg_bob)

    # Each recalls only their own history
    r_alice = agent.invoke({"messages": [{"role": "user", "content": "What's my name and what do I like?"}]}, config=cfg_alice)
    r_bob   = agent.invoke({"messages": [{"role": "user", "content": "What's my name and what do I like?"}]}, config=cfg_bob)

    print(f"Alice's thread: {r_alice['messages'][-1].content}")
    print(f"Bob's thread  : {r_bob['messages'][-1].content}")


# ─────────────────────────────────────────────────────────────
# 3. INSPECT — read the saved state directly
#
# MemorySaver exposes get() so you can inspect what was saved
# without invoking the agent again.
# ─────────────────────────────────────────────────────────────

def demo_inspect():
    _header("3. INSPECT — read saved state directly")

    from langgraph.checkpoint.memory import MemorySaver

    checkpointer = MemorySaver()
    agent = create_deep_agent(model=_make_model(), checkpointer=checkpointer)
    config = {"configurable": {"thread_id": "inspect-demo"}}

    agent.invoke({"messages": [{"role": "user", "content": "Remember: project deadline is Friday."}]}, config=config)
    agent.invoke({"messages": [{"role": "user", "content": "Also remember: budget is $5000."}]}, config=config)

    # Read the checkpoint directly — no LLM call
    state = agent.get_state(config)
    messages = state.values.get("messages", [])

    print(f"Saved {len(messages)} messages in thread 'inspect-demo':")
    for msg in messages:
        role = getattr(msg, "type", "unknown")
        content = msg.content if isinstance(msg.content, str) else str(msg.content)[:80]
        print(f"  [{role}] {content[:100]}")


# ─────────────────────────────────────────────────────────────
# 4. RESET — clear a thread's memory
#
# To wipe a thread: update its state with an empty messages
# list. The thread_id still exists but starts fresh.
# ─────────────────────────────────────────────────────────────

def demo_reset():
    _header("4. RESET — clear a thread")

    from langgraph.checkpoint.memory import MemorySaver
    from langchain_core.messages import HumanMessage

    checkpointer = MemorySaver()
    agent = create_deep_agent(model=_make_model(), checkpointer=checkpointer)
    config = {"configurable": {"thread_id": "reset-demo"}}

    # Build some history
    agent.invoke({"messages": [{"role": "user", "content": "My secret code is ALPHA-7."}]}, config=config)
    r1 = agent.invoke({"messages": [{"role": "user", "content": "What is my secret code?"}]}, config=config)
    print(f"Before reset: {r1['messages'][-1].content}")

    # Wipe the thread by overwriting with a fresh state
    agent.update_state(config, {"messages": [HumanMessage(content="(conversation reset)")]})

    r2 = agent.invoke({"messages": [{"role": "user", "content": "What is my secret code?"}]}, config=config)
    print(f"After reset : {r2['messages'][-1].content}")
    print("→ Memory cleared — agent no longer knows the secret code.")


# ─────────────────────────────────────────────────────────────
# 5. CUSTOM — SqliteSaver for persistence across restarts
#
# MemorySaver is in-process only — it resets when your script
# ends. For real persistence use SqliteSaver (or PostgresSaver
# for production). Same API, just swap the checkpointer.
# ─────────────────────────────────────────────────────────────

def demo_sqlite_persistence():
    _header("5. CUSTOM — SqliteSaver (persists across restarts)")

    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
    except ImportError:
        print("Install: pip install langgraph-checkpoint-sqlite")
        return

    db_path = os.path.join(os.path.dirname(__file__), "memory.db")

    # SqliteSaver used as a context manager — connection is managed for you
    with SqliteSaver.from_conn_string(db_path) as checkpointer:
        agent = create_deep_agent(model=_make_model(), checkpointer=checkpointer)
        config = {"configurable": {"thread_id": "persistent-user"}}

        # First run: store a fact
        agent.invoke(
            {"messages": [{"role": "user", "content": "Remember: my favourite colour is blue."}]},
            config=config,
        )
        print(f"Saved to: {db_path}")

        # Second run (same process, but would survive a restart too)
        result = agent.invoke(
            {"messages": [{"role": "user", "content": "What is my favourite colour?"}]},
            config=config,
        )
        print(f"Agent recalled: {result['messages'][-1].content}")
        print("→ State lives in memory.db — survives script restarts.")


# ─────────────────────────────────────────────────────────────
# CHECKPOINTER COMPARISON
# ─────────────────────────────────────────────────────────────

def print_checkpointer_table():
    _header("CHECKPOINTER OPTIONS")
    rows = [
        ("Checkpointer",       "Persists?", "Use case"),
        ("─" * 20,             "─" * 9,     "─" * 35),
        ("MemorySaver",        "No",        "Dev / testing / single process"),
        ("SqliteSaver",        "Yes",       "Local apps, scripts, small projects"),
        ("PostgresSaver",      "Yes",       "Production, multi-process, multi-user"),
        ("RedisSaver",         "Yes",       "High-throughput, TTL-based expiry"),
    ]
    for name, persists, use in rows:
        print(f"  {name:<22} {persists:<10} {use}")
    print("""
Key concept — thread_id:
  Every invoke() call must pass config={"configurable": {"thread_id": "..."}}
  Same thread_id  →  same conversation history (memory continues)
  New thread_id   →  fresh conversation (no shared memory)
""")


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print_checkpointer_table()
    demo_basic()
    demo_multi_thread()
    demo_inspect()
    demo_reset()
    demo_sqlite_persistence()
