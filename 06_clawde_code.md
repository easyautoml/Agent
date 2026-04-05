# Claude Code — Architecture Overview

Source code from [sanbuphy/claude-code-source-code](https://github.com/sanbuphy/claude-code-source-code), stored in `lib/`.

---

## What is Claude Code?

Claude Code is an **AI coding agent** that runs in your terminal. You type a task in natural language; it reads your files, writes code, runs shell commands, searches the web, and iterates — all autonomously using Claude as the underlying model.

It ships as an npm package (`@anthropic-ai/claude-code`). The CLI binary is a single bundled JS file (`cli.js`) compiled from ~1,900 TypeScript source files using Bun.

---

## How the Main Function Works

Every user message goes through the same pipeline:

```
User types a message
        │
        ▼
   CLI / REPL                     main.tsx, entrypoints/cli.tsx
   Parse flags & slash commands
        │
        ▼
   Init (once at startup)         entrypoints/init.ts
   Load config, auth, telemetry
        │
        ▼
   AppState Store                 state/AppStateStore.ts
   Single immutable source of truth for the whole session
   (settings, model, permissions, message history, tasks…)
        │
        ▼
   QueryEngine                    QueryEngine.ts
   Manages context window size, auto-compaction,
   memory attachment, token budget
        │
        ▼
   Query Loop  (async generator)  query.ts
   ┌─────────────────────────────────────────────┐
   │  1. Build system prompt                     │
   │  2. Call Claude API  ──► Anthropic API      │
   │  3. Stream response back                    │
   │  4. Claude writes text  → show to user      │
   │  5. Claude calls a tool → execute it        │
   │     • check permission                      │
   │     • run tool.call(input, ctx)             │
   │     • append result to conversation         │
   │  6. Repeat until Claude says "done"         │
   └─────────────────────────────────────────────┘
        │
        ▼
   Render output                  cli/print.ts
   Display streamed text & tool results in terminal
```

The loop is an **async generator** — it `yield`s events (text chunks, tool calls, tool results) as they happen, so the UI can render in real-time while Claude is still thinking.

---

## Main Components

| Component | Files | What it does |
|-----------|-------|-------------|
| **CLI / REPL** | `main.tsx`, `entrypoints/` | Entry point, argument parsing, interactive terminal UI (built with Ink/React) |
| **QueryEngine** | `QueryEngine.ts` | Wraps the query loop; manages context budget, compaction, memory injection |
| **Query Loop** | `query.ts` | Core async generator: API call → stream → tool execution → loop |
| **Tools** | `Tool.ts`, `tools.ts`, `tools/` | Everything Claude can *do* (bash, file read/write/edit, grep, web search, spawn agents…) |
| **Commands** | `commands.ts`, `commands/` | Slash commands the user types: `/commit`, `/review`, `/pr`, `/compact`… |
| **AppState** | `state/` | Immutable observable store — shared state across all components |
| **Skills** | `skills/` | Reusable prompt templates that extend commands (see below) |
| **Memory** | `memdir/` | Persistent cross-session memory system (see below) |
| **Bridge** | `bridge/` | WebSocket connection to claude.ai for remote/web sessions |
| **Tasks** | `Task.ts`, `tasks/` | Background work (shell processes, sub-agents, remote agents) |
| **MCP** | `services/mcp/` | Plug in external tools via Model Context Protocol |
| **Plugins** | `plugins/` | Additional tool bundles loaded at startup |

---

## Skills

**Skills are reusable prompt templates** — they let Claude execute complex, multi-step behaviors without Claude having to figure out the steps from scratch each time.

### How a skill works

```
User types:  /commit

   Claude Code looks up the "commit" skill
        │
        ▼
   Loads the skill's prompt  (a .md file with instructions)
        │
        ▼
   Injects it as a system message into the query loop
        │
        ▼
   Claude follows the skill's steps:
     • read git diff
     • summarize changes
     • write commit message
     • run git commit
```

### Two kinds of skills

**Bundled skills** — compiled into the binary, always available:

| Skill | What it does |
|-------|-------------|
| `commit` | Stage and write a git commit message |
| `simplify` | Review changed code and clean it up |
| `loop` | Run a prompt on a recurring interval |
| `claudeApi` | Build apps using the Anthropic SDK |
| `remember` | Explicitly save something to memory |
| `debug` | Systematic debugging workflow |
| `keybindings` | Configure keyboard shortcuts |
| `updateConfig` | Edit `settings.json` via hooks |
| `scheduleRemoteAgents` | Create cron-triggered remote agents |

**Disk skills** — `.md` files in `~/.claude/skills/` or project `.claude/skills/`. Claude Code loads them at startup so users can add their own.

**MCP skills** — skills served by an external MCP server. Discovered at connection time.

### Skill file format

```markdown
---
name: my-skill
description: What this skill does (shown to Claude to decide when to use it)
userInvocable: true      # shows up as a slash command
allowedTools: [Bash, Read, Write]
---

Your detailed instructions here.
Claude will follow these steps when this skill is invoked.
```

---

## Memory

**Memory is a persistent, file-based knowledge store** that survives across sessions. Claude writes facts it should remember into markdown files; future sessions load them into the system prompt.

### How memory works

```
During a conversation
        │
        ├── Claude notices something worth remembering
        │   (user preference, project context, feedback)
        │
        ▼
   Write a .md file to:  ~/.claude/projects/<project>/memory/
   e.g. memory/user_role.md
        │
        ▼
   Update the index:     memory/MEMORY.md
   (one-line pointer per topic file)

Next conversation
        │
        ▼
   loadMemoryPrompt()    reads MEMORY.md (up to 200 lines)
        │
        ▼
   Injected into system prompt at session start
        │
        ▼
   Claude has context from past sessions
```

### Four memory types

| Type | What goes here | Example |
|------|---------------|---------|
| **user** | Who the user is, their role, expertise, preferences | "Senior Go engineer, new to React" |
| **feedback** | How Claude should behave — corrections and confirmations | "Don't mock the DB in tests" |
| **project** | Ongoing work, goals, deadlines, decisions | "Auth rewrite due to compliance issue" |
| **reference** | Pointers to external systems | "Bugs tracked in Linear project INGEST" |

### What is NOT saved

Memory deliberately excludes things Claude can read fresh from the codebase:
- Code patterns, architecture, file structure → just read the files
- Git history → `git log` is authoritative
- Debugging fixes → already in the code and commit messages
- Current task state → use the conversation context

### Memory file format

```markdown
---
name: user role
description: User is a senior backend engineer focused on observability
type: user
---

User is a senior backend engineer.
Currently investigating logging/telemetry gaps in the pipeline.
```

### Variants

- **Auto memory** — default mode; Claude decides what to save
- **Team memory** — shared `memory/team/` directory synced across teammates (feature-gated)
- **Assistant / KAIROS mode** — append-only daily log files; a nightly `/dream` skill distills them into `MEMORY.md`

---

## How Skills and Memory Fit Into the Query Loop

```
Session start
  loadMemoryPrompt()  ──► inject MEMORY.md into system prompt
  loadSkillsDir()     ──► register skills as slash commands / tools

User types /commit
  ──► skill prompt injected into query loop
  ──► Claude follows skill steps using tools (Bash, Read, Write…)
  ──► result shown to user

User says "remember: always use bun not npm"
  ──► Claude calls Write tool → creates memory/feedback_bun.md
  ──► Claude calls Write tool → updates memory/MEMORY.md index

Next session
  ──► MEMORY.md loaded → Claude knows to use bun without being told again
```

---

## Directory Map

```
lib/src/
├── main.tsx               Bootstrap & REPL launch
├── QueryEngine.ts         Context management & query orchestration
├── query.ts               Core async generator query loop
├── Tool.ts                Tool interface & ToolUseContext types
├── tools.ts               Assemble full tool registry
├── Task.ts / tasks.ts     Background task types & factory
├── commands.ts            Slash command registry
├── entrypoints/           CLI entry points & init
├── state/                 AppState store
├── bridge/                WebSocket bridge to claude.ai
├── cli/                   Terminal rendering & transports
├── commands/              Individual slash command modules
├── tools/                 Individual tool implementations
├── tasks/                 Task implementations (shell, agent, remote)
├── skills/                Skill loader, bundled skills, MCP skill builders
├── memdir/                Memory system (paths, prompt builder, types)
├── services/              MCP, compaction, tool orchestration
├── plugins/               Plugin loader
└── components/            Ink/React UI components
```
