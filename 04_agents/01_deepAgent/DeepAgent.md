# DeepAgent — Architecture & Internals

Based on `deepagents/graph.py` — the single file that assembles the entire framework.

---

## Overview

`create_deep_agent()` is a thin factory function. It does one thing: assemble a **LangGraph `CompiledStateGraph`** by stacking middleware layers on top of LangChain's `create_agent()`.

```
create_deep_agent(model, tools, ...)
  │
  ├─ resolve model + provider profile
  ├─ build middleware stack (14 ordered layers)
  ├─ wire subagents into SubAgentMiddleware
  ├─ assemble final system prompt
  │
  └─ create_agent(model, system_prompt, tools, middleware=stack)
       └─ returns CompiledStateGraph  ← what you invoke/stream
```

The graph itself is LangGraph's standard agent loop. DeepAgent's value is entirely in the middleware it injects before the LLM call.

---

## Entry Point

```python
def create_deep_agent(
    model: str | BaseChatModel | None = None,   # default: claude-sonnet-4-6
    tools: Sequence[BaseTool | Callable | dict] | None = None,
    *,
    system_prompt: str | SystemMessage | None = None,
    middleware: Sequence[AgentMiddleware] = (),
    subagents: Sequence[SubAgent | CompiledSubAgent | AsyncSubAgent] | None = None,
    skills: list[str] | None = None,
    memory: list[str] | None = None,
    permissions: list[FilesystemPermission] | None = None,
    response_format: ...,
    context_schema: type | None = None,
    checkpointer: Checkpointer | None = None,
    store: BaseStore | None = None,
    backend: BackendProtocol | BackendFactory | None = None,
    interrupt_on: dict[str, bool | InterruptOnConfig] | None = None,
    debug: bool = False,
    name: str | None = None,
    cache: BaseCache | None = None,
) -> CompiledStateGraph
```

**Model resolution order:**
1. `model=None` → `ChatAnthropic(model_name="claude-sonnet-4-6")`
2. `model="provider:name"` → `init_chat_model(model, model_provider=provider)`
3. `model=BaseChatModel` → used as-is

---

## Middleware Stack (Execution Order)

Middleware wraps the LLM call. Each layer can inject tools, modify the system prompt, or intercept tool calls. The order is fixed and intentional.

### Main Agent Stack

```
1.  TodoListMiddleware              — injects write_todos tool; maintains checklist state
2.  SkillsMiddleware                — (if skills=) loads skill definitions into context
3.  FilesystemMiddleware            — injects ls, read_file, write_file, edit_file, glob, grep, execute
4.  SubAgentMiddleware              — injects task tool; routes calls to inline subagents
5.  SummarizationMiddleware         — compresses old turns when context grows too large
6.  PatchToolCallsMiddleware        — fixes malformed tool call arguments from the LLM
7.  AsyncSubAgentMiddleware         — (if async subagents) injects background task tools
8.  [user middleware]               — your custom middleware, inserted here
9.  profile.extra_middleware        — provider-specific layers (e.g., OpenAI Responses API shims)
10. _ToolExclusionMiddleware        — removes tools the provider doesn't support
11. AnthropicPromptCachingMiddleware— adds cache_control breakpoints; no-ops on non-Anthropic
12. MemoryMiddleware                — (if memory=) loads AGENTS.md files into system prompt
13. HumanInTheLoopMiddleware        — (if interrupt_on=) pauses before specified tool calls
14. _PermissionMiddleware           — (if permissions=) enforces filesystem access rules; ALWAYS LAST
```

**Why this order matters:**
- Summarization sits after filesystem tools so the summary can reference file-op results.
- `_PermissionMiddleware` is last so it sees every tool injected by every middleware above it.
- `AnthropicPromptCachingMiddleware` sits before `MemoryMiddleware` because memory changes the system prompt — putting caching after memory would invalidate the cache prefix on every turn.

---

## System Prompt Assembly

```python
# base_prompt = BASE_AGENT_PROMPT (or profile override)
# optional suffix appended from provider profile

if system_prompt is None:
    final = base_prompt
elif isinstance(system_prompt, SystemMessage):
    final = SystemMessage([*system_prompt.content_blocks, base_prompt])
else:  # string
    final = system_prompt + "\n\n" + base_prompt
```

Your `system_prompt` is always **prepended**. The `BASE_AGENT_PROMPT` is always **appended**. You cannot remove the base prompt — you can only add to it.

**BASE_AGENT_PROMPT** instructs the agent to:
- Be concise, skip preamble ("Sure!", "I'll now...")
- Understand → Act → Verify (iterate, don't stop partway)
- Analyze failures before retrying
- Give brief progress updates on long tasks

---

## Built-in Tools

Injected by `FilesystemMiddleware` and `TodoListMiddleware` — zero setup required:

| Tool | Purpose |
|---|---|
| `write_todos` | Create/update a tracked checklist |
| `ls` | List directory contents |
| `read_file` | Read a file |
| `write_file` | Write a file |
| `edit_file` | Edit a file (targeted replacement) |
| `glob` | Find files by pattern |
| `grep` | Search file contents |
| `execute` | Run a shell command (requires sandbox backend) |
| `task` | Call a subagent by name |

`execute` only works when the backend implements `SandboxBackendProtocol`. With the default `StateBackend`, `execute` returns an error.

---

## Backends

Control where files and state live.

| Backend | Class | Files | Shell (`execute`) |
|---|---|---|---|
| Default | `StateBackend` | In-memory (passed via `invoke(files={...})`) | No |
| Disk | `FilesystemBackend` | Local disk at `root_dir` | Yes (in process) |
| Sandbox | Custom `SandboxBackendProtocol` | Isolated container | Yes |

```python
from deepagents.backends import StateBackend
agent = create_deep_agent(model=model, backend=StateBackend())  # default
```

---

## Subagents

Three types, each handled differently:

### 1. `SubAgent` (declarative)
A dict specifying name, description, system prompt, and optional tools/model/middleware.
Invoked by the main agent via the `task` tool. Gets its own copy of the full middleware
stack (TodoList + Filesystem + Summarization + ...).

```python
subagents=[{
    "name": "math-agent",
    "description": "Handles math calculations.",
    "system_prompt": "You are a precise math assistant.",
    "tools": [calculate],
}]
```

### 2. `CompiledSubAgent`
A pre-built LangGraph runnable. No middleware is added — you own the full configuration.

```python
subagents=[{
    "name": "my-agent",
    "description": "...",
    "runnable": my_compiled_graph,
}]
```

### 3. `AsyncSubAgent`
A remote agent deployed on LangSmith (identified by `graph_id`). Runs as a background
task — the main agent can launch, poll, and cancel it.

```python
subagents=[{
    "name": "remote-agent",
    "description": "...",
    "graph_id": "abc123",
}]
```

**General-purpose subagent:** If no subagent named `"general-purpose"` exists in your list,
DeepAgent auto-inserts one at position 0. This is the default delegate for open-ended subtasks.
Override it by providing your own entry with `name="general-purpose"`.

**Inheritance:** `SubAgent` entries inherit the parent's `interrupt_on` and `permissions`
unless they define their own (which replaces, not merges). `CompiledSubAgent` and
`AsyncSubAgent` do not inherit either.

---

## Provider Profiles (`_HarnessProfile`)

DeepAgent looks up a profile for the resolved model (by provider or model ID). Profiles
let the framework adapt to provider-specific quirks without if/else in your code.

A profile can set:
- `extra_middleware` — additional layers inserted after user middleware
- `excluded_tools` — tools to strip (e.g., provider doesn't support certain schemas)
- `tool_description_overrides` — rewrite tool descriptions per-provider
- `base_system_prompt` — replace the default `BASE_AGENT_PROMPT` entirely
- `system_prompt_suffix` — append text to the base prompt

For most models (including Azure OpenAI via `ChatOpenAI`) the profile is empty and all
defaults apply. Anthropic models get `AnthropicPromptCachingMiddleware` active; for others
it silently no-ops.

---

## Human-in-the-Loop

```python
agent = create_deep_agent(
    model=model,
    tools=[delete_record],
    interrupt_on={"delete_record": True},
    checkpointer=MemorySaver(),
)
config = {"configurable": {"thread_id": "..."}}

# First invoke: pauses before delete_record
result = agent.invoke({"messages": [...]}, config=config, version="v2")

# Resume after user approves
result = agent.invoke(
    Command(resume={"decisions": [{"type": "approve"}]}),
    config=config,
    version="v2",
)
```

`interrupt_on` values can be `True` (pause always) or an `InterruptOnConfig` (conditional).
Requires a `checkpointer` to save state between the pause and the resume.

---

## Permissions

`FilesystemPermission` rules restrict what the agent can read/write. Rules are evaluated
in declaration order; first match wins. If no rule matches, the call is allowed.

```python
from deepagents.middleware.permissions import FilesystemPermission

agent = create_deep_agent(
    model=model,
    permissions=[
        FilesystemPermission(path="/safe/", allow=True),
        FilesystemPermission(path="/", allow=False),    # deny everything else
    ],
)
```

`_PermissionMiddleware` is always the last middleware so it can gate every tool —
including those injected by other middleware layers.

---

## Summarization (Token Overflow Prevention)

`SummarizationMiddleware` (`create_summarization_middleware`) sits in the stack and runs
before the LLM call on every turn:

```
invoke()
  ├─ load history from checkpointer
  ├─ SummarizationMiddleware
  │     too long? → LLM call to compress old turns → [<summary> + recent turns]
  │     ok?      → pass through unchanged
  ├─ run agent step with (possibly compressed) messages
  └─ save compressed state to checkpointer
```

This is separate from `MemorySaver`. The checkpointer stores whatever state the
summarization middleware produces — after compression, not the raw full history.
Plain LangGraph's `MemorySaver` alone does not summarize; it just stores everything as-is.

---

## Memory (AGENTS.md files)

`memory=` loads persistent instruction files into the system prompt at startup:

```python
agent = create_deep_agent(
    model=model,
    memory=["/memory/AGENTS.md"],
    backend=FilesystemBackend(root_dir="/workspace"),
)
```

`MemoryMiddleware` reads these files from the backend and injects them into the system
prompt before each invocation. Placed after `AnthropicPromptCachingMiddleware` in the
stack so memory changes don't invalidate the cache prefix.

---

## Skills

`skills=` loads reusable skill definitions (structured prompt fragments) from the backend:

```python
agent = create_deep_agent(
    model=model,
    skills=["/skills/project/"],
    backend=FilesystemBackend(root_dir="/workspace"),
)
```

`SkillsMiddleware` reads skill files from the given source paths. With `StateBackend`,
supply skill file contents via `invoke(files={"/skills/project/my_skill.md": b"..."})`.
Later sources override earlier ones for skills with the same name.

---

## Recursion Limit

DeepAgent sets `recursion_limit=9_999` on the compiled graph. This effectively removes
the step cap that LangGraph imposes by default (25), allowing long-running autonomous tasks
to run without hitting the recursion limit.

---

## Quick Reference

```python
from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver

model = ChatOpenAI(
    model="gpt-4o",
    base_url="https://<resource>.openai.azure.com/openai/v1",
    api_key="...",
)

agent = create_deep_agent(
    model=model,                          # any BaseChatModel or "provider:model" string
    tools=[my_tool],                      # merged with built-ins
    system_prompt="You are ...",          # prepended before BASE_AGENT_PROMPT
    subagents=[{"name": "...", ...}],     # delegate work to child agents
    checkpointer=MemorySaver(),           # enable multi-turn memory
    interrupt_on={"edit_file": True},     # pause for human approval
    permissions=[...],                    # restrict filesystem access
    response_format=MyPydanticModel,      # enforce structured output
)

result = agent.invoke(
    {"messages": [{"role": "user", "content": "..."}]},
    config={"configurable": {"thread_id": "user-123"}},
)
print(result["messages"][-1].content)
```
