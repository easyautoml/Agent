# 04_DeepAgent

Learning DeepAgent ([langchain-ai/deepagents](https://github.com/langchain-ai/deepagents)) with Azure OpenAI.

## Files

| File | What it covers |
|---|---|
| `01_hello_world.py` | Minimal DeepAgent setup |
| `02_sample.py` | 7 use cases: tools, system prompt, streaming, structured output, memory, HITL, sub-agents |
| `03_comparison.py` | DeepAgent vs plain LangChain — the 3 real differences |
| `04_memory.py` | MemorySaver deep dive: multi-turn, multi-thread, inspect, reset, SQLite |

## Setup

```bash
pip install deepagents python-dotenv langchain langchain-openai langgraph pydantic
```

`.env` file:
```
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com/openai/v1
AZURE_OPENAI_DEPLOYMENT=gpt-4.1-mini
AZURE_OPENAI_API_VERSION=2025-04-14
```

---

## Memory

### How MemorySaver works

`MemorySaver` is just a Python dictionary that saves conversation snapshots.

```
storage = {
    "thread-1": {
        "checkpoint-001": (messages, metadata, parent_id),
        "checkpoint-002": (messages, metadata, parent_id),
    },
    "thread-2": { ... }
}
```

Every time the agent finishes a step it calls `put()` — saves a snapshot into the dict.
Every time it starts a step it calls `get_tuple()` — loads the latest snapshot back out.

```
invoke()
  ├─ get_tuple(thread_id)  ← load previous snapshot
  ├─ run agent step
  └─ put(thread_id)        ← save new snapshot
```

**Why it resets on restart:** it lives in RAM only. No file, no database.
When the process ends, everything is gone. For persistence, swap it with
`SqliteSaver` or `PostgresSaver` — same interface, different backend.

### `thread_id` is the key

```python
config = {"configurable": {"thread_id": "user-alice"}}
agent.invoke({"messages": [...]}, config=config)
```

| `thread_id` | Effect |
|---|---|
| Same as previous call | Conversation continues — agent remembers history |
| Different from previous | Fresh conversation — no shared memory |

One `MemorySaver` instance can hold many independent threads at once.

### MemorySaver does NOT prevent token overflow

`MemorySaver` stores everything as-is — it never trims or summarises.
The thing that prevents token overflow is **DeepAgent's summarisation middleware**,
which sits in front of the LLM call:

```
invoke()
  ├─ load full history from MemorySaver
  │
  ├─ summarisation middleware
  │     too long? → call LLM to compress old turns into a summary
  │                 replace old messages with [<summary> + recent turns]
  │     ok?      → pass through unchanged
  │
  ├─ run agent with (possibly compressed) messages
  └─ save compressed state back to MemorySaver
```

Plain LangGraph's `MemorySaver` alone hits the token limit because there is no
summarisation middleware. DeepAgent wraps the same checkpointer with that layer on top.
After compression, the saved snapshot is smaller — not the raw full history.

### Checkpointer options

| Checkpointer | Persists? | Use case |
|---|---|---|
| `MemorySaver` | No | Dev / testing / single process |
| `SqliteSaver` | Yes | Local apps, scripts, small projects |
| `PostgresSaver` | Yes | Production, multi-process, multi-user |

```bash
# SQLite
pip install langgraph-checkpoint-sqlite

# Postgres
pip install langgraph-checkpoint-postgres
```

Swap the checkpointer without changing any other code:

```python
# Dev
from langgraph.checkpoint.memory import MemorySaver
checkpointer = MemorySaver()

# Production
from langgraph.checkpoint.postgres import PostgresSaver
checkpointer = PostgresSaver.from_conn_string("postgresql://...")

agent = create_deep_agent(model=model, checkpointer=checkpointer)
```
