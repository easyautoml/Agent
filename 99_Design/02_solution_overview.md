# Solution Overview

## Architecture Summary

The system is built in distinct layers. Each layer has one clear responsibility and communicates with its neighbours through defined interfaces.

```
┌──────────────────────────────────────────────────────────┐
│  Channels  (Slack · Teams stub · Discord stub)           │
│  ChannelAdapter → normalise event → InboundEvent         │
└────────────────────────┬─────────────────────────────────┘
                         │ InboundEvent
                         ▼
┌──────────────────────────────────────────────────────────┐
│  Dispatcher  (channels/dispatcher.py)                    │
│  save message · provision workspace · call orchestration │
└────────────────────────┬─────────────────────────────────┘
                         │
           ┌─────────────┴──────────────┐
           │                            │
           ▼                            ▼
┌──────────────────────┐   ┌────────────────────────────────┐
│  Orchestration       │   │  Processing  +  Workers        │
│  system-level flow   │   │  parse → embed → notify        │
│  session state       │   │  (deterministic, not an agent) │
└──────────┬───────────┘   └────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────┐
│  Agents  (CrewAI)                                        │
│  Manager Agent → delegates to child agents               │
│  Clarification · Proposal · Feedback                     │
└────────────────────────┬─────────────────────────────────┘
                         │
           ┌─────────────┴──────────────┐
           │                            │
           ▼                            ▼
┌──────────────────┐       ┌────────────────────────────────┐
│  Skills          │       │  Tools                         │
│  SKILL.md prompt │       │  Shared callable functions     │
│  + tool subset   │       │  (messaging · files · memory   │
└──────────────────┘       │   · search)                    │
                           └────────────────────────────────┘
                                        │
           ┌─────────────────────────────────────────────┐
           │  Storage                                    │
           │  PostgreSQL · ChromaDB · Filesystem         │
           └─────────────────────────────────────────────┘
```

---

## Layer Responsibilities

### Channel Layer
- Connect to each platform (Slack Socket Mode, Teams/Discord stubs)
- Normalise platform events into a single `InboundEvent` dataclass
- Send messages back via `send_message()`
- Does **not** contain business logic

### Dispatcher
- Receive `InboundEvent` from any channel
- Save the inbound message to the database
- Provision the workspace if it does not exist
- Hand off to `OrchestrationService`
- Does **not** decide what the agent should do

### Orchestration
- Manage session lifecycle (states: idle → processing_inputs → clarifying → drafting → proposal_ready → updating)
- Decide which step to run next based on session state
- Notify the agent layer when files are ready
- Does **not** contain reasoning or business logic — that belongs to agents

### Processing + Workers
- Background asyncio queue
- Parse raw files to clean Markdown (`markitdown` → `docling` → fallback)
- Chunk and embed into ChromaDB
- Generate an optional file summary
- Update file status in PostgreSQL
- Entirely deterministic — no LLM decisions in this layer

### Agent Layer (CrewAI)
- **Manager Agent** — reads context, decides whether to clarify or draft, delegates to the right child agent
- **Clarification Agent** — asks focused questions in the channel thread
- **Proposal Agent** — drafts or revises the proposal using workspace context
- **Feedback Agent** — interprets feedback and decides revision vs. approval
- Future: Data Analysis, Solution Design

### Skills
- A project-level abstraction that wraps a `SKILL.md` instruction prompt + a curated subset of tools
- Each skill is owned by one agent but may share tools with others
- Skill instruction prompts live in `skills/<name>/SKILL.md`

### Tools
- Shared LangChain `@tool` functions
- Bound to a workspace at creation time (`channel_id` injected)
- Categories: messaging (send reply), files (list, read), memory (search vector store, get history), search (web stub)

### Workspace
- Provisions directories (`raw/`, `clean/`, `output/`) per channel
- Stores workspace metadata in `workspace.json`
- Is the bridge between channels and the filesystem

### Storage
Three systems, each with a distinct role:

| System | Technology | What it holds |
|---|---|---|
| Relational DB | PostgreSQL | Messages, files, sessions, feedback instructions |
| Vector DB | ChromaDB | Document chunks + embeddings (workspace isolation via `channel_id` metadata filter) |
| Filesystem | Disk | Raw files, clean Markdown, proposal versions |

---

## Technology Stack

| Layer | Technology |
|---|---|
| Channel — Slack | `slack_bolt` (Socket Mode) |
| Web server | FastAPI + uvicorn |
| Agent orchestration | CrewAI |
| LLM | Claude (main model: Opus; fast model: Haiku) |
| LLM client | `langchain-anthropic` → `ChatAnthropic` |
| Tools | LangChain `@tool` functions |
| Embeddings | `text-embedding-3-small` (OpenAI) |
| Vector store | ChromaDB (persistent) |
| Relational DB | PostgreSQL + SQLModel + asyncpg |
| File parsing | `markitdown` CLI, `docling` Python API, raw-text fallback |
| Config | `pydantic-settings` + `.env` |
| Background workers | `asyncio` task queue |
