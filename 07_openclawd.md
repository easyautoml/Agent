# Agent Architecture — Technical Deep Dive

## Contents

1. [Overview](#1-overview)
2. [Architecture Diagram](#2-architecture-diagram)
3. [Component 1 — Agent Scope](#3-component-1--agent-scope)
4. [Component 2 — Bootstrap Pipeline](#4-component-2--bootstrap-pipeline)
5. [Component 3 — Memory Search](#5-component-3--memory-search)
6. [Component 4 — Agent Runner](#6-component-4--agent-runner)
7. [Component 5 — Embedded Runner](#7-component-5--embedded-runner)
8. [Component 6 — CLI Runner](#8-component-6--cli-runner)
9. [Component 7 — Model Fallback + Auth Profiles](#9-component-7--model-fallback--auth-profiles)
10. [Component 8 — Tools Layer](#10-component-8--tools-layer)
11. [How a Message Flows Through All Components](#11-how-a-message-flows-through-all-components)

---

## 1. Overview

The `src/agents/` directory contains the core execution engine for OpenClaw agents. It is responsible for everything that happens between receiving a message and sending a reply: loading identity files, assembling the LLM prompt, picking a model, running the AI, executing tools, and writing memory.

The directory contains ~200 source files grouped into eight functional components. Understanding these eight components is enough to understand the full agent lifecycle and know where to look when customizing behavior.

| Component | Key files | What it does |
|---|---|---|
| Agent Scope | `agent-scope.ts` | Resolves IDs → workspace dirs, model config, auth |
| Bootstrap Pipeline | `workspace.ts`, `bootstrap-files.ts`, `bootstrap-budget.ts`, `bootstrap-hooks.ts` | Loads workspace .md files into LLM context |
| Memory Search | `memory-search.ts` | Vector/hybrid semantic retrieval from MEMORY.md and sessions |
| Agent Runner | `auto-reply/reply/agent-runner*.ts` | Central orchestrator — assembles prompt, dispatches, streams |
| Embedded Runner | `pi-embedded-runner/` | Direct API calls via SDK (Anthropic, OpenAI, Gemini, etc.) |
| CLI Runner | `cli-runner.ts` | Spawns external CLI binary as a subprocess |
| Model Fallback + Auth | `model-fallback.ts`, `auth-profiles.ts` | Rotates API keys, failover between providers |
| Tools Layer | `bash-tools.ts`, `channel-tools.ts` | `exec`, messaging, memory read/write |

---

## 2. Architecture Diagram

![Agent Architecture](../img/agent-arch.svg)

The diagram shows how data flows top-to-bottom on every agent turn:

1. **Agent Scope** resolves which workspace, model, and auth profile belong to this request
2. **Bootstrap Pipeline** and **Memory Search** run in parallel, each contributing context into the prompt
3. **Agent Runner** assembles the final system prompt and dispatches to a runner
4. **Embedded Runner** or **CLI Runner** executes the LLM call
5. **Model Fallback + Auth Profiles** wraps all execution — retrying with other providers on failure
6. **Tools Layer** is called by the LLM mid-run; results are returned back into the LLM context

---

## 3. Component 1 — Agent Scope

**Files:** [src/agents/agent-scope.ts](../../src/agents/agent-scope.ts), [src/agents/agent-paths.ts](../../src/agents/agent-paths.ts)

Agent Scope is the resolver layer. Every time a message arrives, the system needs to answer three questions: Which agent handles this? Where is its workspace? Which model should it use? Agent Scope answers all three.

### Key functions

**`resolveAgentWorkspaceDir(cfg, agentId)`**

Returns the workspace folder path for a given agent. Priority order:
1. `agents.list[id].workspace` from config (explicit override)
2. `agents.defaults.workspace` if this is the default agent
3. `~/.openclaw/workspace` for the default agent
4. `~/.openclaw/state/workspace-<id>` for non-default agents

**`resolveAgentWorkspaceDir` fallback chain (simplified):**

```typescript
// agent-scope.ts
export function resolveAgentWorkspaceDir(cfg, agentId) {
  const configured = resolveAgentConfig(cfg, id)?.workspace?.trim();
  if (configured) return resolveUserPath(configured);         // explicit
  if (id === defaultAgentId) {
    const fallback = cfg.agents?.defaults?.workspace?.trim();
    if (fallback) return resolveUserPath(fallback);           // defaults
    return resolveDefaultAgentWorkspaceDir();                 // ~/.openclaw/workspace
  }
  return path.join(stateDir, `workspace-${id}`);             // per-agent fallback
}
```

**`resolveAgentIdByWorkspacePath(cfg, path)`**

Reverse lookup — given a file path, finds which agent owns it. Used when a tool writes a file and the system needs to know which agent's workspace it belongs to.

**`resolveAgentDir(cfg, agentId)`**

Different from workspace. The `agentDir` is OpenClaw's internal state folder for this agent (`~/.openclaw/state/agents/<id>/agent/`), not the user-facing workspace. This is where session files and internal agent state are stored.

---

## 4. Component 2 — Bootstrap Pipeline

**Files:** [src/agents/workspace.ts](../../src/agents/workspace.ts), [src/agents/bootstrap-files.ts](../../src/agents/bootstrap-files.ts), [src/agents/bootstrap-budget.ts](../../src/agents/bootstrap-budget.ts), [src/agents/bootstrap-hooks.ts](../../src/agents/bootstrap-hooks.ts)

The bootstrap pipeline reads the workspace folder and turns it into a list of context files that get injected into the LLM's system prompt before every run. This is how the agent "remembers" its identity and instructions across sessions.

### Step 1 — `workspace.ts` reads the files

Loads each recognized bootstrap file from the workspace directory:

```
AGENTS.md · SOUL.md · TOOLS.md · IDENTITY.md · USER.md · HEARTBEAT.md · BOOTSTRAP.md · MEMORY.md
```

Each file is read with boundary guards (files must stay within the workspace root — no path traversal). Results are cached by inode/mtime to avoid re-reading unchanged files. If a file is missing, it is included as `{ missing: true }` so downstream code can decide what to do.

**Filtered for sub-agents:** When the session is a cron run or sub-agent spawn, only the minimal set is loaded (`AGENTS.md`, `SOUL.md`, `TOOLS.md`, `IDENTITY.md`, `USER.md`) — the full MEMORY.md and session context are excluded to save tokens.

### What each file contains

![Workspace Files](../img/workspace-files.svg)

| File | Purpose | Content summary | Loaded when |
|---|---|---|---|
| **BOOTSTRAP.md** | First-run ritual | Guides the agent through a conversation to discover its name, vibe, identity. Deleted once complete. | First conversation only |
| **SOUL.md** | Core personality | Values, behavioural rules, desired vibe, privacy principles, continuity philosophy. Agent can edit over time. | Every session |
| **IDENTITY.md** | Self-description | Name, nature/creature type, emoji signature, avatar path. Also drives the avatar shown in channel UIs. | Every session |
| **USER.md** | Human profile | User's name, pronouns, timezone, projects, preferences. Built up over time by the agent as it learns. | Every session |
| **AGENTS.md** | Workspace rules | Session startup ritual, memory write rules (daily notes vs MEMORY.md), red lines, group chat etiquette, heartbeat behaviour. | Every session |
| **TOOLS.md** | Local setup notes | SSH hosts, camera names, TTS voice preferences, device nicknames — anything environment-specific. Separate from shared skills. | Every session |
| **HEARTBEAT.md** | Periodic checklist | Short task list for heartbeat polls (email, calendar, weather checks). Empty = skip the API call entirely. Agent edits freely. | Heartbeat runs only |
| **MEMORY.md** | Long-term memory | Curated decisions, lessons, user facts distilled from daily `memory/YYYY-MM-DD.md` logs. **Not loaded in group chats or sub-agents** (security). | Main session (1-on-1) only |

**Key design principle:** Files are your agent's only persistent state between turns. Nothing lives in RAM across sessions — if it isn't written to a file, the agent forgets it when the session ends.

### Step 2 — `bootstrap-files.ts` assembles the payload

Calls `loadWorkspaceBootstrapFiles()`, then runs `applyBootstrapHookOverrides()` so plugins can add/replace files at runtime (for example, injecting extra context for a specific session).

Returns a list of `WorkspaceBootstrapFile` objects, each with a name, path, content, and missing flag.

### Step 3 — `bootstrap-budget.ts` enforces limits

Each workspace file has a per-file character limit (configurable). If the total would exceed the total bootstrap budget, files are truncated or omitted starting from the least critical. A warning is injected into the system prompt if truncation occurred, so the LLM knows its context was cut.

### Step 4 — `bootstrap-hooks.ts` calls plugin hooks

Fires the `agent.bootstrap` internal hook, giving plugins a chance to modify the file list before it is compiled into the prompt. A plugin could add a custom file, replace SOUL.md content, or inject dynamic context.

---

## 5. Component 3 — Memory Search

**File:** [src/agents/memory-search.ts](../../src/agents/memory-search.ts)

Memory Search provides the agent with semantically relevant memories — past decisions, facts about the user, project context — retrieved from MEMORY.md files and (optionally) session transcripts.

It is separate from the bootstrap pipeline: bootstrap loads fixed workspace files; memory search does a query-time vector lookup against indexed content.

### How it works

1. At the start of a session (or on search), the memory store is synchronized — new content in MEMORY.md and recent sessions is chunked and embedded
2. When a prompt is assembled, a semantic query retrieves the most relevant chunks
3. Retrieved chunks are injected into the system prompt alongside the bootstrap context

### Configuration

Memory search is highly configurable per-agent in `openclaw.json`:

```json
{
  "agents": {
    "defaults": {
      "memorySearch": {
        "provider": "openai",
        "model": "text-embedding-3-small",
        "query": {
          "maxResults": 6,
          "hybrid": { "enabled": true, "vectorWeight": 0.7, "textWeight": 0.3 }
        },
        "sync": { "onSessionStart": true, "watch": true }
      }
    }
  }
}
```

**Embedding providers:** `openai` · `gemini` · `voyage` · `mistral` · `ollama` · `local` · `auto`

**Store:** SQLite with `sqlite-vss` vector extension. Default path: `~/.openclaw/state/memory/<agentId>.sqlite`

**Hybrid query:** Combines cosine similarity (vector) with BM25 full-text search. Default weights: 70% vector, 30% text. Supports MMR (Maximal Marginal Relevance) for diversity and temporal decay to deprioritize old memories.

---

## 6. Component 4 — Agent Runner

**Files:** [src/auto-reply/reply/agent-runner.ts](../../src/auto-reply/reply/agent-runner.ts), [src/auto-reply/reply/agent-runner-execution.ts](../../src/auto-reply/reply/agent-runner-execution.ts), [src/auto-reply/reply/agent-runner-payloads.ts](../../src/auto-reply/reply/agent-runner-payloads.ts)

The Agent Runner is the central orchestrator. It receives a message body and coordinates all other components to produce a reply. It lives in `src/auto-reply/` rather than `src/agents/` because it operates at the reply level, not just the model level.

### Responsibilities

- Assembles the final system prompt from bootstrap context + memory search results + skills
- Determines which runner to use (embedded vs CLI) based on the provider
- Calls the runner and streams reply blocks back to the channel
- Routes tool calls: when the LLM calls a tool, the runner executes it and feeds the result back
- Handles model fallback: if execution fails, delegates to the Model Fallback layer
- Triggers memory flush after the turn completes (persists new memories to the vector store)
- Manages reply queueing: subsequent messages while a run is active are queued or dropped per policy

### Entry point: `runReplyAgent()`

The main function in `agent-runner.ts`. Called once per inbound message. It:

1. Checks the queue policy (skip/queue/replace if another run is active)
2. Signals typing to the channel
3. Calls `runAgentTurnWithFallback()` (in `agent-runner-execution.ts`)
4. Streams reply payloads via the block reply pipeline
5. Runs `runMemoryFlushIfNeeded()` after the turn
6. Queues followup runs if needed

### Two execution paths

`runAgentTurnWithFallback()` decides which runner to use:

```typescript
if (isCliProvider(provider)) {
  // spawn CLI subprocess
  return runCliAgent(...)
} else {
  // direct API call via SDK
  return runEmbeddedPiAgent(...)
}
```

The distinction is set by the provider name in config. Providers starting with `claude-cli`, `codex`, or any custom CLI backend use the CLI Runner. Everything else (Anthropic API, OpenAI, Gemini, Ollama, etc.) uses the Embedded Runner.

---

## 7. Component 5 — Embedded Runner

**Files:** [src/agents/pi-embedded-runner/](../../src/agents/pi-embedded-runner/) (directory)

The Embedded Runner makes direct API calls to LLM providers using their native SDK. It is the default path for all API-based providers.

### Key capabilities

**Native streaming:** The response streams token-by-token back to the caller. The Agent Runner receives each block as it arrives and forwards it to the channel — the user sees the reply being typed in real time.

**Native tool call loop:** When the LLM emits a tool call in the response, the runner:
1. Receives the tool call
2. Executes the tool (bash, web search, memory read, etc.)
3. Appends the tool result to the conversation
4. Continues the LLM response from where it left off

This loop repeats until the LLM produces a final text response with no further tool calls.

**Session compaction:** When the conversation history grows large enough to approach the context window, the runner compacts the session — summarizing earlier turns to free up space. The new session starts from the compacted state.

**Session lanes:** Multiple concurrent sessions to the same LLM provider run in separate lanes to avoid interference. A lane is a stable routing key derived from the session key.

**History limiting:** For group chats and DM sessions, the number of history turns sent to the LLM is capped to avoid token bloat.

### Supported providers

Any provider accessible via the `@mariozechner/pi-ai` SDK layer:
- Anthropic (Claude models via API key)
- OpenAI (GPT models)
- Google Gemini
- Ollama (local models, no API key)
- Mistral, Groq, Together AI, Fireworks, and others via LiteLLM

---

## 8. Component 6 — CLI Runner

**File:** [src/agents/cli-runner.ts](../../src/agents/cli-runner.ts)

The CLI Runner spawns an external AI CLI tool as a child process and communicates with it via stdin/stdout/arguments. This enables providers that expose a CLI (like Claude Code or OpenAI Codex) to be used as agent backends.

### How it works

1. Loads the bootstrap context (same workspace files as the embedded path)
2. Builds a system prompt string
3. Constructs the CLI arguments: `--model`, `--system-prompt`, `--session-id`, `--print`, etc.
4. Spawns the CLI as a child process via the **process supervisor**
5. Waits for the process to complete, collects stdout
6. Parses output: `text`, `json`, or `jsonl` format depending on the backend config

### Process supervisor

The process supervisor (`src/process/supervisor/`) manages all spawned child processes. For the CLI runner it provides:

- **Watchdog timeout:** Kills the process if it produces no output for N seconds (configurable). This catches the CLI stalling at an interactive prompt or approval dialog.
- **Session scoping:** If the CLI supports session resumption (`--resume`), the supervisor keeps track of the CLI's session ID so subsequent runs can continue the same conversation.
- **Serialization:** Some CLI backends can only handle one request at a time. The supervisor queues calls behind a per-backend key.

### Session expiry recovery

If the CLI returns a session-expired error (e.g., the CLI's session was evicted), the runner automatically retries without a session ID — creating a fresh CLI session.

### Backend configuration

CLI backends are registered in config. Each backend defines:

```json
{
  "command": "claude",
  "args": ["--print", "--model", "{model}"],
  "systemPromptArg": "--system-prompt",
  "output": "text"
}
```

Multiple CLI backends can be registered and selected by provider name.

---

## 9. Component 7 — Model Fallback + Auth Profiles

**Files:** [src/agents/model-fallback.ts](../../src/agents/model-fallback.ts), [src/agents/auth-profiles.ts](../../src/agents/auth-profiles.ts), [src/agents/api-key-rotation.ts](../../src/agents/api-key-rotation.ts), [src/agents/model-selection.ts](../../src/agents/model-selection.ts)

This component wraps all LLM execution and provides two reliability mechanisms: model fallback and API key rotation.

### Model Fallback (`model-fallback.ts`)

When an LLM call fails, the system tries the next configured provider/model rather than returning an error to the user. You configure the fallback chain in `openclaw.json`:

```json
{
  "models": {
    "fallbacks": {
      "claude-opus-4-6": ["gpt-4o", "claude-haiku-4-5"]
    }
  }
}
```

Failure reasons that trigger fallback:

| Reason | Example |
|---|---|
| `auth_error` | Invalid or expired API key |
| `rate_limit` | Provider rate limit hit |
| `timeout` | Request exceeded timeout (or CLI watchdog) |
| `context_overflow` | Message too large for this model's context window |
| `model_not_found` | Model ID deprecated or unavailable |
| `server_error` | Provider 5xx |

Reasons that do NOT trigger fallback (abort immediately):
- `user_abort` — the user cancelled
- Billing/payment errors — won't be fixed by switching model

### Auth Profiles (`auth-profiles.ts`)

An auth profile is one set of credentials for one provider. You can configure multiple profiles per provider (multiple API keys). When one key hits a rate limit or error:

1. That profile is put into **cooldown** for a configured duration
2. The next profile in rotation order is tried
3. When cooldown expires, the profile is eligible again

This is useful for working around per-key rate limits by spreading requests across multiple API keys.

**Profile resolution order:** By default, profiles are ordered by last-used time (least recently used first, to spread load). You can set an explicit order in config.

---

## 10. Component 8 — Tools Layer

**Files:** [src/agents/bash-tools.ts](../../src/agents/bash-tools.ts) and related, [src/agents/channel-tools.ts](../../src/agents/channel-tools.ts)

The Tools Layer implements the callable functions that give the agent real-world capabilities. Tools are registered with the Embedded Runner; the LLM calls them by name in its response. Results are returned back into the conversation for the LLM to continue.

> **Note:** When using the CLI Runner, tools are handled entirely inside the CLI process itself. The CLI Runner does not use this tools layer directly.

### `exec` — Shell command execution (`bash-tools.ts`)

The most powerful tool. Lets the LLM run arbitrary shell commands in the workspace directory.

**Execution modes:**

| Mode | When used |
|---|---|
| PTY (pseudo-terminal) | Default for interactive commands |
| Plain subprocess | Fallback when PTY is unavailable |
| Docker | When sandbox mode is enabled |

**Approval gating:** Before running a new command pattern, the system checks `~/.openclaw/exec-approvals.json`. If the pattern is not approved, the agent pauses and asks the user for permission. Approved patterns are remembered. Pre-populate the approvals file to allow commands in automated setups.

**Background processes:** The agent can launch long-running processes (e.g., `npm run dev`) and later send input to them or check their output. `bash-process-registry.ts` tracks active background processes.

**Docker sandbox:** When `sandbox.mode = "docker"` is set for an agent, all shell commands run inside a Docker container instead of the host OS. Configurable mounts, user, and network policy.

### `channel-tools` — Send messages to channels

Lets the agent proactively send messages to a Telegram chat, Slack channel, Discord channel, etc. — independently of the current conversation. Used for notifications, proactive updates, and cross-channel replies.

### Memory tools

The Embedded Runner registers `mem_read` and `mem_write` tools that let the LLM explicitly read from or write to the vector memory store mid-conversation, beyond what is auto-injected at session start.

---

## 11. How a Message Flows Through All Components

![Agent Message Flow](../img/agent-message-flow.svg)

Tracing a single inbound message end-to-end:

**Step 1 — Gateway + Channel Plugin**

The user's message hits the Gateway as an HTTP webhook. The Gateway dispatches it to the matching Channel Plugin (e.g. `msteams`, `slack`). The plugin normalises the raw payload into a standard envelope and calls the **Routing Engine** to resolve which `agentId` should handle this conversation (based on `bindings` config: peer ID, team, account, or default).

**Step 2 — Agent Runner orchestrates the context**

The Agent Runner is the main coordinator. It runs four sub-steps before sending anything to the LLM:

| Sub-step | What happens |
|---|---|
| **2a Agent Scope** | Translates `agentId` → `workspaceDir`, model config, auth profile |
| **2b Bootstrap** | Loads all workspace files (`AGENTS.md`, `SOUL.md`, `IDENTITY.md`, `USER.md`, `TOOLS.md`, `HEARTBEAT.md`) — enforces token budget — runs bootstrap hooks |
| **2c Memory Search** | Runs a semantic query against the vector store — returns the top-N most relevant memory chunks |
| **2d Assemble Prompt** | Combines: bootstrap context + memory chunks + skills + heartbeat + tool definitions → the full system prompt |

Model Fallback and Auth Profiles wrap the entire runner — if the primary API key or provider fails, the runner automatically retries with the next in the rotation.

**Step 3 — Dispatch to CLI Runner or Embedded Runner**

| Backend | When used |
|---|---|
| **CLI Runner** | Provider is a CLI-based backend (e.g. `claude` CLI, `codex`) — spawns a subprocess, streams output via ACP protocol |
| **Embedded Runner** | Provider is a direct API (Anthropic, OpenAI, Gemini, etc.) — calls API directly, streams tokens |

**Step 4 — LLM executes**

The LLM reads the assembled system prompt and generates a response. If it emits `tool_use` blocks, the **Tools Layer** executes them (`exec`, `web_search`, `read`, `write`, `mem_read`, etc.) and returns results back to the LLM. This loop repeats until the LLM produces a final text response.

**Step 5 — Post-run (parallel)**

Three things happen simultaneously after the LLM finishes:

- **Memory flush** — new session content is indexed into the vector store
- **Channel delivery** — the Channel Plugin receives the reply and sends it back to the user on Teams / Slack / etc.
- **Session accounting** — token usage is persisted to disk

The entire flow runs for every message, every time. No persistent in-memory state is carried between turns — all continuity comes from the workspace files, the vector memory store, and the session transcript stored on disk.
