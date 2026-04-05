# SuperMemory Tools

## What is SuperMemory?

SuperMemory is a persistent memory engine for AI assistants.
Without it, AI forgets everything between conversations.
SuperMemory stores facts, preferences, and context — so the AI remembers across sessions.

It ranks #1 on major AI memory benchmarks (LongMemEval, LoCoMo, ConvoMem).

---

## How Tools are Defined

SuperMemory exposes tools through the **MCP (Model Context Protocol)** standard.
Any AI assistant that supports MCP can use these tools.
The tools are hosted as a Cloudflare Workers server and called over HTTP.

---

## The Three Core Tools

| Tool | What It Does |
|------|-------------|
| **`memory`** | Save or forget something. Called automatically when the user shares important info. |
| **`recall`** | Search memories by query. Returns relevant facts + a user profile summary. |
| **`whoAmI`** | Get the current user's identity (userId, email, name). |

These three tools are the AI-facing interface.
Everything else in the system supports them.

---

## How Tools Work Together

```
User shares something in conversation
    ↓
AI calls `memory` tool → saves the fact
    ↓
Next conversation starts
    ↓
AI calls `recall` tool with context query
    ↓
SuperMemory returns relevant memories + profile
    ↓
AI uses that context to give a personalized response
```

Memory is never loaded in full — only relevant pieces are retrieved based on the query.

---

## Memory Types

SuperMemory stores four types of memory:

| Type | Example |
|------|---------|
| **Static** | "Senior engineer at Acme Corp" |
| **Dynamic** | "Currently working on auth migration" |
| **Temporal** | "Has exam tomorrow" (auto-expires) |
| **Relationships** | Updates, corrections, or extensions of older memories |

---

## Main Components

SuperMemory is a monorepo with **19 components** across three groups:

### Apps (7) — user-facing
| App | Purpose |
|-----|---------|
| `web` | Consumer web app |
| `mcp` | MCP server (hosts the 3 tools) |
| `browser-extension` | Browser plugin |
| `raycast-extension` | Raycast integration |
| `memory-graph-playground` | Visualize memory relationships |
| `docs` | Documentation site |

### Packages (11) — developer libraries
| Package | Purpose |
|---------|---------|
| `tools` | AI SDK, OpenAI SDK, and Mastra integrations |
| `ai-sdk` | Vercel AI SDK middleware |
| `lib` | Core shared utilities |
| `ui` | React UI components |
| Python packages | OpenAI, Pipecat, Microsoft Agent Framework |

### Skills (1)
`supermemory` skill — Claude plugin with usage guides.

---

## Framework Integrations

SuperMemory connects to most major AI frameworks:

| Framework | Integration |
|-----------|------------|
| Vercel AI SDK | `withSupermemory()` middleware |
| OpenAI SDK | `withSupermemory()` + function calling |
| LangChain / LangGraph | Custom memory tools |
| Mastra | Input/output processors |
| OpenAI Agents SDK | Memory tools |
| Claude Desktop | MCP plugin |
| Cursor / Windsurf | MCP plugin |

---

## Summary

- SuperMemory = persistent memory for AI across sessions
- Three tools: `memory`, `recall`, `whoAmI`
- Works via MCP — compatible with any MCP-supporting AI
- 19 components: MCP server, SDKs, browser extension, web app
- Memory is retrieved selectively by relevance, not loaded in full
