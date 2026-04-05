# OpenAI Codex CLI Tools

## What is Codex CLI?

Codex CLI is a coding agent from OpenAI that runs locally on your computer.
It lets an AI help you write, edit, and run code directly in your terminal.

The system is split into two parts:
- **codex-cli** — the command-line interface (TypeScript/Node.js)
- **codex-rs** — the core engine (Rust, handles tool execution)

---

## How a Tool is Defined

A tool in Codex has three parts:

| Part | Purpose |
|------|---------|
| **ToolDefinition** | Name, description, and input schema (JSON Schema format) |
| **ToolSpec** | Serialized format sent to the LLM |
| **ToolHandler** | Rust trait that implements the actual execution |

The definition describes the tool to the model.
The handler runs the real logic when the model calls it.
These two are separate — the model sees the schema, not the implementation.

---

## Tool Categories

Codex defines **33 tool handler types** organized into 8 categories:

### 1. Execution
Run commands and code.

| Tool | Purpose |
|------|---------|
| `shell` | Execute shell commands with full TTY support |
| `exec_command` | Run commands with login shell options |
| `shell_command` | Alternative shell backend |
| `code_mode` | Specialized code execution environment |

### 2. File Operations
Read and modify files.

| Tool | Purpose |
|------|---------|
| `apply_patch` | Edit files using a unified diff-like format |
| `list_dir` | List directory contents with filtering |

### 3. Code Execution
Run JavaScript interactively.

| Tool | Purpose |
|------|---------|
| `js_repl` | Run JavaScript in a REPL session |
| `js_repl_reset` | Reset the JS REPL state |

### 4. MCP Integration
Connect to external tool servers.

| Tool | Purpose |
|------|---------|
| `mcp` | Call tools from any MCP server |
| `mcp_resource` | Access MCP resources |
| `dynamic_tool` | Load tools dynamically at runtime |

### 5. Multi-Agent Orchestration
Spawn and coordinate child agents.

| Tool | Purpose |
|------|---------|
| `spawn_agent` (v1/v2) | Create a child agent |
| `wait_agent` (v1/v2) | Wait for a child agent to finish |
| `send_input` / `send_message` | Send input to a running agent |
| `close_agent` (v1/v2) | Stop a child agent |
| `list_agents` | See all running agents |
| `followup_task` | Add a followup task to an agent |
| `resume_agent` | Resume a paused agent |

### 6. Discovery and Planning
Find tools and plan work.

| Tool | Purpose |
|------|---------|
| `tool_search` | Search available tools dynamically |
| `tool_suggest` | Suggest relevant tools based on context |
| `plan` | Create a structured plan |
| `agent_jobs` | List pending agent jobs |

### 7. User Interaction
Involve the user in the workflow.

| Tool | Purpose |
|------|---------|
| `request_user_input` | Ask the user a question mid-task |
| `request_permissions` | Ask the user to approve an action |
| `view_image` | Display and analyze an image |

### 8. Utility
| Tool | Purpose |
|------|---------|
| `test_sync` | Internal testing tool |

---

## How Tools Work with the Agent

```
LLM decides to call a tool
    ↓
ToolOrchestrator receives the call
    ↓
ToolRegistry looks up the right handler
    ↓
Permission check: is this action safe / approved?
    ↓
Handler executes asynchronously
    ↓
Result returned to the LLM as ToolOutput
    ↓
LLM continues the task
```

The `ToolOrchestrator` manages sandboxing, permissions, and approval workflows.
The `ToolRegistry` maps tool names to handler implementations.

---

## Tool Execution Hooks

Every tool handler supports pre/post execution hooks:

| Hook | Purpose |
|------|---------|
| `pre_tool_use_payload()` | Runs before execution (logging, approval request) |
| `post_tool_use_payload()` | Runs after execution (logging, cleanup) |
| `is_mutating()` | Marks whether the tool changes the environment (triggers permission check) |

---

## Key Components

| Component | Role |
|-----------|------|
| `ToolDefinition` | Schema shown to the LLM |
| `ToolSpec` | Serialized tool format per provider |
| `ToolHandler` (Rust trait) | Actual execution logic |
| `ToolRegistry` | Routes tool calls to handlers |
| `ToolOrchestrator` | Manages sandboxing, approval, parallel execution |
| `ToolsConfig` | Settings for which tools are enabled |

---

## Summary

- Codex = local coding agent with 33 tool handler types
- Tools are split: model sees the schema, Rust engine runs the logic
- Eight categories: execution, file ops, JS REPL, MCP, multi-agent, discovery, user interaction, utility
- Permission system controls which tools need user approval
- Multi-agent tools allow spawning and coordinating parallel child agents
