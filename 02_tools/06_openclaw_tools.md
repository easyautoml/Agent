# OpenClaw Tools

## What is OpenClaw?

OpenClaw is a personal AI assistant you host on your own infrastructure.
It connects to 13+ messaging channels (WhatsApp, Telegram, Slack, Discord, Signal, iMessage, Matrix, and more).
The agent can run commands, browse the web, manage files, and spawn subagents — all from a single system.

The architecture has two main parts:
- **Gateway** — manages sessions, channels, and incoming events
- **Agent** — the AI executor that uses tools to act

---

## How a Tool is Defined

Tools are TypeScript objects with:

| Part | Purpose |
|------|---------|
| **name** | Unique identifier |
| **description** | Tells the LLM what the tool does |
| **parameters** | Input schema using TypeBox (like JSON Schema) |
| **execute()** | Async function that runs the tool and returns a result |

OpenClaw uses `@sinclair/typebox` for parameter validation.
Helper functions (`readStringParam`, `readNumberParam`, etc.) extract values safely inside `execute()`.

---

## Tool Categories (8 groups)

### 1. Coding Tools
File and command operations — the core developer toolkit.

| Tool | Purpose |
|------|---------|
| `read` | Read a file from disk |
| `write` | Create or append to a file |
| `edit` | Modify specific lines in a file |
| `exec` | Run a bash command (with approval gates) |
| `apply_patch` | Apply a unified diff patch |

### 2. Browser Tools
Automate a real web browser.

| Tool | Purpose |
|------|---------|
| `browser_act` | Click, type, scroll, screenshot |
| `browser_navigate` | Open a URL |
| `browser_screenshot` | Capture current page state |

### 3. Web Tools
Retrieve information from the internet.

| Tool | Purpose |
|------|---------|
| `web_search` | Search via Brave, Perplexity, Kimi, or Grok |
| `web_fetch` | Fetch and parse a web page |

### 4. Session Tools
Coordinate multiple agents.

| Tool | Purpose |
|------|---------|
| `sessions_list` | List all active sessions |
| `sessions_send` | Send a message to another session |
| `sessions_spawn` | Launch an isolated subagent task |
| `sessions_yield` | Pause and return an intermediate result |
| `sessions_history` | Retrieve a session's message history |

### 5. Message Tools
Communicate across channels.

| Tool | Purpose |
|------|---------|
| `message_send` | Send a message to any connected channel |

### 6. Media Tools
Work with images, PDFs, audio, and visual canvases.

| Tool | Purpose |
|------|---------|
| `image_tool` | Process or generate images |
| `pdf_tool` | Extract text from PDFs |
| `tts_tool` | Convert text to speech |
| `canvas_tool` | Render an interactive visual workspace |

### 7. Infrastructure Tools
Manage the system itself.

| Tool | Purpose |
|------|---------|
| `cron_tool` | Schedule a recurring task |
| `gateway_tool` | Query gateway state and config |
| `nodes_tool` | Run structured workflows with branching |

### 8. Agent Management Tools
Discover and control agents.

| Tool | Purpose |
|------|---------|
| `agents_list` | List running agents |
| `subagents_tool` | Manage subagents |

**Total: ~21 built-in tools**

---

## How Tools Work Together

```
User sends message
    ↓
Gateway routes to agent
    ↓
Tool policies filter the available tool list
    ↓
LLM receives filtered tool schemas
    ↓
LLM calls a tool by name with parameters
    ↓
Tool executes and returns structured result
    ↓
LLM continues until task is done
    ↓
Agent sends reply to the originating channel
```

---

## Tool Policies

Not all tools are available in every situation.
OpenClaw applies a policy pipeline to filter the tool list based on:

| Policy | Example |
|--------|---------|
| **Agent profile** | `restricted` profile = no terminal access |
| **Channel type** | `voice` channel = no `tts` tool |
| **Sandbox mode** | Sandboxed session = reduced permissions |
| **Owner authorization** | Some tools require the message to be from the owner |
| **Explicit allow/deny lists** | `tools.allow`, `tools.deny` in config |

This keeps powerful tools like `exec` away from untrusted contexts automatically.

---

## Plugin Tools

Tools can also be added by plugins:

- Plugins register tools via `api.registerTool()`
- Optional plugins require explicit allowlisting in config
- Conflict-checked against core tool names
- Can add any new capability the user needs

---

## Key Components

| Component | Role |
|-----------|------|
| `openclaw-tools.ts` | Assembles the main tool list |
| `pi-tools.ts` | Assembles the coding tool list |
| Tool policy pipeline | Filters tool list per context |
| TypeBox schemas | Validate all tool inputs |
| Plugin SDK | Lets plugins register custom tools |
| `exec` approval gate | Asks user before running shell commands |

---

## Summary

- OpenClaw = self-hosted AI assistant with 21+ built-in tools
- Eight tool categories: coding, browser, web, sessions, messages, media, infrastructure, agents
- Tool policies control what the LLM can access per context
- Plugins extend the tool set without modifying core code
- Session tools enable multi-agent coordination across channels
