# Hermes Agent Tools

## What is Hermes Agent?

Hermes is a self-improving AI agent built by Nous Research.
It runs on a server and is accessible from any messaging platform:
WhatsApp, Telegram, Slack, Discord, Signal, Email, and more.

The key idea is that the agent learns from experience — it creates and improves **skills** over time.
It also remembers context across sessions using persistent memory.

---

## How a Tool is Defined

Every tool has three parts:

| Part | Purpose |
|------|---------|
| **Schema** | Describes the tool name, description, and input parameters (OpenAI function-calling format) |
| **Handler** | The Python function that runs when the tool is called |
| **Registration** | Registers schema + handler in the central registry |

Tools live in individual Python files under `tools/` and register themselves at import time.

---

## Tool Categories (20+)

Hermes organizes tools into **toolsets** — named groups that can be enabled or disabled together.

| Toolset | What It Provides |
|---------|-----------------|
| `web` | Search the web, extract page content |
| `terminal` | Run shell commands, manage processes |
| `file` | Read, write, patch, and search files |
| `browser` | Full browser automation (10 operations) |
| `vision` | Analyze images |
| `image_gen` | Generate images |
| `code_execution` | Run Python in a sandbox |
| `delegation` | Spawn isolated subagents |
| `todo` | Track tasks and plans |
| `memory` | Save and recall facts across sessions |
| `session_search` | Search conversation history |
| `moa` | Mixture of Agents — ask multiple models, synthesize the best answer |
| `skills` | Manage skill documents (procedural memory) |
| `cronjob` | Schedule repeating tasks |
| `tts` | Text-to-speech |
| `messaging` | Send messages to any connected platform |
| `honcho` | AI-native user modeling (learn preferences) |
| `homeassistant` | Control smart home devices |
| `safe` | Restricted set for untrusted contexts |
| `rl` | Reinforcement learning mode |

**Platform-specific toolsets** are also available for each messaging platform (Slack, Telegram, Discord, etc.).

---

## Main Built-in Tools

| Tool | What It Does |
|------|-------------|
| `web_search` | Search the web |
| `web_extract` | Extract content from a page |
| `terminal` | Run shell commands |
| `read_file` / `write_file` | File operations |
| `patch` | Apply fuzzy patches to files |
| `browser_navigate` / `browser_click` / `browser_type` | Automate browser |
| `execute_code` | Run Python in sandbox |
| `delegate_task` | Spawn a parallel subagent |
| `mixture_of_agents` | Query multiple models and combine answers |
| `todo` | Manage a task list |
| `memory` | Save and search long-term memory |
| `skills_list` / `skill_view` / `skill_manage` | Manage skill documents |
| `cronjob` | Schedule a recurring task |
| `send_message` | Send to Slack, Telegram, Discord, etc. |
| `text_to_speech` | Convert text to audio |
| `vision_analyze` | Analyze an image |
| `image_generate` | Generate an image |

**40+ tools total** across all categories.

---

## How Tools Work with the Agent

```
User sends message
    ↓
Agent runs conversation loop
    ↓
LLM decides which tool to call
    ↓
registry.dispatch() routes to the right handler
    ↓
Tool runs (sync or async)
    ↓
Result returned as JSON string
    ↓
LLM uses result, calls more tools if needed
    ↓
Agent replies when done
```

The registry is the central router. It maps tool names to handlers and checks availability before dispatch.

---

## Key Components

| Component | Role |
|-----------|------|
| `tools/registry.py` | Central store of all tools and their metadata |
| `model_tools.py` | Provides tool schemas to the LLM, dispatches calls |
| `toolsets.py` | Groups tools by use case |
| Individual tool files | Each tool registers itself at import time |
| `check_fn` | Optional gate — tool is only available if this returns true |
| `skills/` | Procedural memory documents (not tools, but guide behavior) |

---

## Extension Points

| Method | How |
|--------|-----|
| **Built-in** | Add a `.py` file in `tools/`, call `registry.register()` |
| **MCP** | Connect an external MCP server |
| **Plugins** | Install packages that auto-register via `discover_plugins()` |

---

## Summary

- Hermes = multi-platform agent with 40+ built-in tools
- Tools are organized into 20+ toolsets (enable/disable as groups)
- Central registry routes all tool calls
- Supports spawning subagents, scheduling tasks, controlling smart home
- Skills (separate from tools) store learned procedures as documents
