# Source Code Structure

## Contents

1. [Project Overview](#1-project-overview)
2. [Full Directory Structure](#2-full-directory-structure)
3. [The Tool → Skill → Agent Hierarchy](#3-the-tool--skill--agent-hierarchy)
4. [How Pieces Connect — ProposalAgent Example](#4-how-pieces-connect--proposalagent-example)
5. [Tool Sharing Map](#5-tool-sharing-map)
6. [Agent Registry — Manager Crew](#6-agent-registry--manager-crew)
7. [Why CrewAI](#7-why-crewai)
8. [Adding a New Agent (future)](#8-adding-a-new-agent-future)
9. [Data Storage Design](#9-data-storage-design)
   - [9.0 SQLModel — How It Works Here](#90-sqlmodel--how-it-works-here)
   - [9.1 Storage Systems Overview](#91-storage-systems-overview)
   - [9.2 Relational DB — ERD](#92-relational-db--erd)
   - [9.3 Vector DB — ChromaDB Collections and Metadata](#93-vector-db--chromadb-collections-and-metadata)
   - [9.4 Tool Definitions](#94-tool-definitions)
   - [9.5 Storage Layout Summary](#95-storage-layout-summary)

---

## 1. Project Overview

A multi-channel AI agent system where:

- **Multiple agents** handle different task types (proposal, data analysis, solution design, …)
- **Each agent** is composed of one or more **skills**
- **Each skill** selects a subset of shared **tools** + injects a `SKILL.md` instruction prompt
- **Tools** are shared — the same `search_semantic` tool is reused across every skill that needs it
- **Channels** (Slack, Teams, Discord) are abstracted behind a `ChannelAdapter` — the agent layer never knows which platform it is on

**Framework:** CrewAI for agent orchestration (Agents, Tasks, Crews).

---

## 2. Full Directory Structure

```
proposal-agent/
│
├── main.py                      # Start all channel adapters; call create_db_and_tables()
├── config.py                    # pydantic-settings, loaded once at startup
├── requirements.txt
├── .env.example
│
├── channels/                    # Channel adapter layer — one subdir per platform
│   ├── base.py                  # ChannelAdapter ABC, InboundEvent, FileRef
│   ├── registry.py              # Load adapters from CHANNEL_ADAPTERS config
│   ├── dispatcher.py            # Normalize event → save message → route to agent
│   │
│   ├── slack/                   # V1 — Slack implementation
│   │   ├── adapter.py           # SlackAdapter(ChannelAdapter)
│   │   └── normalizer.py        # Slack event dict → InboundEvent
│   │
│   ├── teams/                   # Future — Microsoft Teams
│   │   ├── adapter.py
│   │   └── normalizer.py
│   │
│   └── discord/                 # Future — Discord
│       ├── adapter.py
│       └── normalizer.py
│
├── agents/                      # Agent layer — tools, skills, and agents
│   │
│   ├── base.py                  # BaseAgent ABC: build(workspace_name) → CrewAI Agent
│   ├── registry.py              # Builds hierarchical manager Crew with all agents registered
│   │
│   ├── tools/                   # ALL shared tools (reused across skills)
│   │   ├── __init__.py
│   │   ├── base.py                    # CrewAI BaseTool helpers and shared types
│   │   ├── msg_fetch_recent.py        # Get last N messages from Postgres messages table
│   │   ├── msg_summarize.py           # Summarize channel history via fast LLM
│   │   ├── file_list.py               # List files from Postgres files table
│   │   ├── file_load.py               # Read processed .md from filesystem by file_id
│   │   ├── file_write.py              # Write files to workspace (clean/, output/)
│   │   ├── doc_parse.py               # Convert raw file → clean Markdown (docling/markitdown)
│   │   ├── doc_embed.py               # Chunk Markdown + upsert into ChromaDB
│   │   ├── doc_summarize.py           # LLM one-paragraph summary of a document
│   │   ├── search_semantic.py         # ChromaDB search — workspace docs or common knowledge
│   │   ├── search_web.py              # Future — external web search
│   │   ├── store_requirements.py      # Read/write data/clean/requirements.md
│   │   ├── store_proposal.py          # Read/write data/output/proposal_*.md
│   │   └── channel_send.py            # Send messages via channel adapter
│   │
│   ├── skills/                  # Each skill = tools subset + SKILL.md prompt
│   │   ├── base.py              # BaseSkill: get_tools(), get_instructions()
│   │   ├── data_processing/     # Used by: DataProcessingAgent
│   │   │   ├── skill.py
│   │   │   └── SKILL.md
│   │   ├── clarification/       # Used by: ClarificationAgent
│   │   │   ├── skill.py
│   │   │   └── SKILL.md
│   │   ├── proposal_draft/      # Used by: ProposalDraftAgent
│   │   │   ├── skill.py
│   │   │   └── SKILL.md
│   │   ├── feedback_update/     # Used by: FeedbackUpdateAgent
│   │   │   ├── skill.py
│   │   │   └── SKILL.md
│   │   ├── data_analysis/       # Future
│   │   │   ├── skill.py
│   │   │   └── SKILL.md
│   │   └── solution_design/     # Future
│   │       ├── skill.py
│   │       └── SKILL.md
│   │
│   ├── data_processing/         # Parses, embeds, summarises uploaded files
│   │   └── agent.py             # DataProcessingAgent — runs on every file upload
│   │
│   ├── clarification/           # Asks consolidated questions, updates requirements.md
│   │   └── agent.py             # ClarificationAgent
│   │
│   ├── proposal/                # Drafts proposal from confirmed requirements
│   │   ├── agent.py             # ProposalDraftAgent
│   │   └── runner.py            # Session state machine: IDLE→CLARIFYING→DRAFTING→READY→UPDATING
│   │
│   ├── feedback/                # Applies feedback instructions, versions the proposal
│   │   └── agent.py             # FeedbackUpdateAgent
│   │
│   ├── data_analysis/           # Future
│   │   └── agent.py
│   │
│   └── design/                  # Future
│       └── agent.py
│
├── workspace/                   # Workspace lifecycle and file intake
│   ├── __init__.py
│   ├── manager.py               # WorkspaceManager.provision(), lookup()
│   ├── registry.py              # channel_id → workspace directory path map
│   ├── schema.py                # workspace.json structure (pydantic)
│   │
│   └── files/                   # Download files from channel into raw/
│       ├── __init__.py
│       ├── collector.py         # Download file, save to raw/, trigger DataProcessingAgent
│       └── versioning.py        # Timestamped filename rules
│
├── storage/                     # Persistence layer — SQLModel + PostgreSQL + ChromaDB
│   ├── __init__.py
│   ├── db.py                    # SQLModel engine + get_session() + create_db_and_tables()
│   ├── models.py                # ALL table definitions — single source of truth
│   ├── messages_repo.py         # INSERT only (append-only)
│   ├── files_repo.py            # insert, update_status, list, soft_delete
│   ├── sessions_repo.py         # session upsert/update + feedback CRUD
│   └── vector_repo.py           # ChromaDB — search_workspace, search_common, add_chunks, delete_file_chunks
│
├── api/                         # FastAPI (health check + internal only)
│   ├── __init__.py
│   └── routes.py
│
├── chromadb/                    # ChromaDB persistent storage — git ignored
│   ├── workspace_documents/     # All workspace chunks, filtered by channel_id at query time
│   └── common_knowledge/        # Shared company knowledge, global to all workspaces
│
├── workspaces/                  # Per-workspace files — git ignored
│   └── {channel-name}/
│       └── data/
│           ├── raw/             # Original uploaded files (never modified)
│           ├── clean/           # Processed Markdown (DataProcessingAgent writes here)
│           └── output/          # Proposal versions (ProposalDraftAgent writes here)
│
└── common/                      # Shared knowledge base — read-only to all agents
    ├── requirements/
    ├── technical/
    ├── member_profiles/
    └── company_progress/
```

---

## 3. The Tool → Skill → Agent Hierarchy

```
Tools         shared callable functions
  ↑
Skills        tools subset + SKILL.md instruction prompt
  ↑
Agents        skills wired into CrewAI Agent + Crew + Tasks
  ↑
Registry      intent string → agent class
  ↑
Dispatcher    InboundEvent → intent → agent.run()
```

**Key rules:**

- A **tool** knows nothing about skills or agents — it just does one job
- A **skill** selects which tools it needs and what instructions govern their use
- An **agent** selects which skills it needs and wires them into CrewAI roles
- Adding a **new agent** requires only: new skills (if needed) + new `agents/{name}/` folder
- Adding a **new tool** requires only: one file in `agents/tools/` — no other changes



## 3. Data Storage Design


### 3.1 Storage Systems Overview

Three storage systems, each with a distinct role:

| # | Type | Technology | What it stores |
|---|---|---|---|
| 1 | **Relational (RDB)** | PostgreSQL | Structured records — messages, files, sessions, feedback |
| 2 | **Vector DB** | ChromaDB | Document chunks + embeddings for semantic search |
| 3 | **Filesystem** | Disk | Raw uploaded files, processed Markdown, proposal outputs |

**Single Postgres database** (`proposal_agent`) with `channel_id` as the workspace boundary on every table. All channels share one DB — no per-workspace files to manage, migrate, or back up.


### 3.2 Relational DB — ERD

One database (`proposal_agent`), four tables. `channel_id` on every table is the workspace isolation key.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  proposal_agent  (PostgreSQL)                                                   │
│                                                                                 │
│  ┌──────────────────────────────┐     ┌──────────────────────────────────────┐  │
│  │ messages                     │     │ files                                │  │
│  │──────────────────────────────│     │──────────────────────────────────────│  │
│  │ PK  id            UUID       │     │ PK  id            UUID               │  │
│  │     channel_id    TEXT  ──┐  │     │     channel_id    TEXT  ──┐          │  │
│  │     channel_type  TEXT   │  │     │     user_id        TEXT   │          │  │
│  │     user_id       TEXT   │  │     │     original_name  TEXT   │          │  │
│  │     role          TEXT   │  │     │     stored_name    TEXT   │          │  │
│  │     content       TEXT   │  │     │     file_type      TEXT   │          │  │
│  │     thread_id     TEXT   │  │     │     file_size      BIGINT │          │  │
│  │     file_ids      JSONB  │  │     │     raw_path       TEXT   │          │  │
│  │     platform_ts   TEXT   │  │     │     clean_path     TEXT   │          │  │
│  │     created_at    TIMESTAMPTZ     │     status        TEXT   │          │  │
│  │                          │  │     │     file_summary   TEXT   │          │  │
│  │  INSERT only             │  │     │     is_latest      BOOL   │          │  │
│  │  No UPDATE / DELETE      │  │     │     is_deleted     BOOL   │          │  │
│  └──────────────────────────┘  │     │     created_at     TIMESTAMPTZ       │  │
│                                │     │     updated_at     TIMESTAMPTZ       │  │
│                                │     │                          │          │  │
│                                │     │  status enum:            │          │  │
│                                │     │    pending               │          │  │
│                                │     │    extracting            │          │  │
│                                │     │    extracted             │          │  │
│                                │     │    embedding             │          │  │
│                                │     │    ready                 │          │  │
│                                │     │    failed                │          │  │
│                                │     │    unsupported           │          │  │
│                                │     └──────────────────────────┘          │  │
│                                │                                │          │  │
│  ┌─────────────────────────────┴──────────────────────────────────────┐    │  │
│  │                        channel_id (workspace key)                  │    │  │
│  └─────────────────────────────┬──────────────────────────────────────┘    │  │
│                                │                                            │  │
│  ┌─────────────────────────────┴────────┐  ┌────────────────────────────┐  │  │
│  │ agent_sessions                       │  │ feedback_instructions       │  │  │
│  │──────────────────────────────────────│  │────────────────────────────│  │  │
│  │ PK  id                 UUID          │  │ PK  id            UUID      │  │  │
│  │     channel_id         TEXT  ────────┼──┤     channel_id    TEXT ─────┘  │  │
│  │     channel_type       TEXT          │  │     text          TEXT         │  │
│  │     task_type          TEXT          │  │     active        BOOL         │  │
│  │     status             TEXT          │  │     applied_to_   INT          │  │
│  │     clarification_round INT          │  │       version                  │  │
│  │     proposal_version   INT           │  │     created_at    TIMESTAMPTZ  │  │
│  │     thread_id          TEXT          │  │                                │  │
│  │     pending_message    TEXT          │  │  FK  channel_id →              │  │
│  │     created_at         TIMESTAMPTZ   │  │      agent_sessions            │  │
│  │     updated_at         TIMESTAMPTZ   │  └────────────────────────────────┘  │
│  │                                      │                                      │
│  │  status enum:                        │                                      │
│  │    idle                              │                                      │
│  │    processing_inputs                 │                                      │
│  │    clarifying                        │                                      │
│  │    drafting                          │                                      │
│  │    proposal_ready                    │                                      │
│  │    updating                          │                                      │
│  │    failed                            │                                      │
│  │                                      │                                      │
│  │  UNIQUE (channel_id)                 │                                      │
│  │    WHERE status NOT IN               │                                      │
│  │    ('idle','failed')                 │                                      │
│  └──────────────────────────────────────┘                                      │
└─────────────────────────────────────────────────────────────────────────────────┘
```


### 3.3 Vector DB — ChromaDB Collections and Metadata

Shared across all workspaces. Isolation enforced by `channel_id` metadata filter — no separate collection per workspace.

**Chunk metadata fields:**

| Field | Value | Purpose |
|---|---|---|
| `channel_id` | e.g. `C08XXXXXXX` | Always included in query filter — workspace boundary |
| `file_id` | UUID | Foreign key → `files.id` in Postgres |
| `file_name` | `requirements.pdf` | Human-readable source reference |
| `file_type` | `pdf` / `docx` / … | Allows file-type filtering |
| `chunk_index` | `3` | Position within the document |
| `chunk_total` | `12` | Total chunks for this file |
| `is_requirement` | `"true"` / `"false"` | Fast filter for requirement-type files |
| `created_at` | ISO 8601 | When the chunk was indexed |

Every query always includes `where={"channel_id": channel_id}` — one workspace never sees another's documents. `channel_id` is injected at tool construction time so the agent cannot skip the filter.

Chunks added: `DataProcessingAgent` calls `vector_repo.add_chunks()` after setting `status = 'ready'` in Postgres.
Chunks removed: `vector_repo.delete_file_chunks(file_id)` called when `is_deleted = true` is set on the file.

---
