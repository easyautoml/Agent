# Design Document — Slack-Based Project Agent System

**Version:** 1.0
**Status:** Draft
**Based on:** REQ.md v1.2, ARC.md v1.0

---

## Contents

1. [System Overview](#1-system-overview)
2. [Architecture](#2-architecture)
3. [Components](#3-components)
4. [How Components Work Together](#4-how-components-work-together)
5. [Data Design](#5-data-design)
6. [File System Layout](#6-file-system-layout)
7. [Memory Layers](#7-memory-layers)
8. [State Machine](#8-state-machine)

---

## 1. System Overview

### What It Does

A Slack bot that automates the proposal workflow for client projects. The team uploads client documents and sends requirements via Slack. The bot processes the documents, checks whether the requirement is complete, asks clarification questions if needed, and drafts a professional proposal — all within the Slack channel.

### Core Principle

**One Slack channel = one isolated project workspace.**

Each channel has its own directory, its own documents, its own vector index, and its own agent state. No data ever crosses channel boundaries.

### V1 Scope

Proposal support only:
- Collect and process uploaded files
- Understand and clarify client requirements
- Draft and update project proposals
- Apply team feedback instructions

---

## 2. Architecture

### Three Independent Runtime Layers

The system is split into three layers that run independently and communicate through the **file system and SQLite** — never through direct function calls. This keeps each layer independently testable and replaceable.

```
┌─────────────────────────────────────────────────────────────────┐
│                     LAYER 1 — EVENT HANDLER                      │
│  Persistent WebSocket connection to Slack (Socket Mode)          │
│  Receives all events. Acknowledges immediately. Dispatches work. │
└───────────────┬──────────────────────────────────────────────────┘
                │ dispatches via asyncio queue
                ▼
┌─────────────────────────────────────────────────────────────────┐
│                  LAYER 2 — BACKGROUND WORKERS                    │
│  WorkspaceManager  FileCollector  ProcessingPipeline             │
│  Read/write files. Update SQLite job status. Index to VectorDB.  │
└───────────────┬──────────────────────────────────────────────────┘
                │ agent reads files + SQLite state
                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   LAYER 3 — PROPOSAL AGENT                       │
│  LangGraph ReAct agent. Reads context. Calls LLM. Posts to Slack.│
│  State checkpointed to SQLite — can pause and resume.            │
└─────────────────────────────────────────────────────────────────┘
```

### High-Level Component Map

```
Slack Platform
    │ WebSocket (Socket Mode)
    ▼
┌──────────────────────────────────────────────────────────────────┐
│  Event Handler (slack_bolt)                                       │
│  Routes: bot_joined → WorkspaceManager                           │
│          file_shared → FileCollector                              │
│          app_mention → AgentDispatcher                           │
│          message.*   → HistoryCapture                            │
└──────┬───────────────────────┬───────────────────────────────────┘
       │                       │
       ▼                       ▼
┌─────────────┐     ┌──────────────────────────────────────────┐
│  Workspace  │     │  Processing Pipeline (background)         │
│  Manager   │     │  FileCollector → DataParser               │
│            │     │  → Chunker → VectorDB                     │
│  workspaces│     └──────────────────────────────────────────┘
│  /channel/ │
│  └─ data/  │     ┌──────────────────────────────────────────┐
│     raw/   │     │  Proposal Agent (LangGraph ReAct)         │
│     clean/ │     │  - Loads requirement checklist            │
│     output/│     │  - Retrieves context from VectorDB        │
│     state/ │     │  - Identifies gaps, asks in Slack         │
│            │     │  - Drafts and updates proposals            │
│  common/   │     │  - Applies feedback instructions          │
│  └─ knowl. │     └──────────────────────────────────────────┘
└────────────┘
```

### Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Slack transport | `slack_bolt` + Socket Mode | Persistent outbound WebSocket, no public HTTP |
| Async queue | `asyncio` | Decouple Slack acks from processing |
| Agent orchestration | LangGraph (ReAct) | State machine with pause/resume via checkpoints |
| LLM — reasoning | Claude Sonnet 4.6 | Proposal drafting, gap analysis, clarification |
| LLM — processing | Claude Haiku 4.5 | Document Markdown conversion (cheap, high volume) |
| Embeddings | `text-embedding-3-small` | Semantic retrieval |
| Vector store | ChromaDB (local, file-based) | Per-workspace + shared common knowledge indexes |
| File parsing | Docling / MarkItDown | PDF, Word, Excel, PowerPoint, images → Markdown |
| State persistence | SQLite | Sessions, messages, jobs, feedback |
| Web framework | FastAPI | Health checks and internal API only |
| Config | `pydantic-settings` + `.env` | Type-safe environment config |

---

## 3. Components

### 3.1 Slack Event Handler

**What it does:** Maintains the persistent WebSocket connection to Slack. Receives every event, acknowledges it immediately (≤ 3 seconds), and dispatches the actual work to background handlers.

**Events handled:**

| Event | Dispatched to |
|-------|--------------|
| `bot_joined_channel` | WorkspaceManager |
| `file_shared` | FileCollector |
| `app_mention` | AgentDispatcher → Proposal Agent |
| `message.channels` | HistoryCapture + FeedbackHandler |
| `message.groups` | HistoryCapture |
| `message.im` | HistoryCapture |
| `message.mpim` | HistoryCapture |

**Key rule:** The handler never does heavy work. It enqueues and returns. All processing happens in background workers.

---

### 3.2 Workspace Manager

**What it does:** Creates and initializes the isolated directory structure for a channel when the bot first joins it.

**Triggered by:** `bot_joined_channel` only. No other event creates a workspace.

**What it creates:**

```
workspaces/{channel_name}/
└── data/
    ├── raw/              ← all uploaded files land here
    ├── clean/            ← processed Markdown output
    ├── output/           ← generated proposals
    ├── vector_index/     ← per-workspace ChromaDB
    └── state/
        ├── workspace.json
        ├── jobs.sqlite
        ├── agent.sqlite
        ├── messages.db
        └── feedback.jsonl
```

**Idempotent:** If the workspace already exists, provisioning is a no-op.

---

### 3.3 File Collector

**What it does:** Downloads every file shared in the Slack channel and saves it to `data/raw/` using the original filename. If the same filename was uploaded before, all three locations are replaced: `raw/`, `clean/`, and VectorDB chunks for that file.

**Flow:**

```
file_shared event
  → Download file from Slack
  → Save to data/raw/{original_filename}  (overwrite if exists)
  → Insert or replace record in jobs.sqlite (status: pending)
  → Enqueue to DataParser worker
```

**Supported file types:** PDF, Word, Excel, PowerPoint, plain text, images.
Unsupported extensions are saved to `raw/` and marked `status: unsupported` — no parsing attempted.

---

### 3.4 Processing Pipeline (DataParser)

**What it does:** Background worker that picks up `pending` jobs from `jobs.sqlite`, parses each file into clean Markdown, chunks it, embeds it, and upserts the chunks into the workspace VectorDB.

**Flow:**

```
Poll jobs.sqlite for status='pending'
  → Mark job status = 'processing'
  → Run DataParser(raw_path, file_type)
      → Extract text (Docling or MarkItDown — configured at runtime)
      → Clean noise (headers, footers, page numbers)
      → LLM conversion to structured Markdown (claude-haiku — cheap + fast)
  → Save to data/clean/{filename}.md  (overwrite if exists)
  → Chunk by semantic section (heading-aware)
      → Fallback: sliding window 512 tokens, 50 token overlap
  → Delete existing VectorDB chunks for this filename
  → Embed chunks + upsert to workspace VectorDB
  → Mark job status = 'done', update clean_path
  → On error: mark status = 'failed', log error_message
```

**One parser for all types.** No QAParser or separate routes — every supported file goes through the same DataParser and produces a `.md` output in `clean/`.

---

### 3.5 Proposal Agent

**What it does:** The main reasoning engine. A LangGraph ReAct agent that checks requirements, asks clarifying questions, drafts proposals, and applies feedback. State is checkpointed to SQLite so the agent can pause between Slack messages and resume exactly where it left off.

**Triggered by:** Any `app_mention` classified as intent `propose` or `clarify`.

**Intent classification:**

| Intent | Example | Action |
|--------|---------|--------|
| `propose` | "Here is the requirement, create a proposal" | Start proposal workflow |
| `clarify` | Reply to agent's clarifying questions | Continue requirement intake |
| `feedback` | "Don't include DevOps cost" | Route to Feedback Handler |
| `status` | "What's the status?" | Status Reporter |
| `question` | "What documents do you have?" | Info Agent |

**Agent tools (LLM-callable):**

| Tool | What it does |
|------|-------------|
| `search_workspace_docs` | Semantic search over client documents (top-k=10) |
| `search_common_knowledge` | Semantic search over shared standards (top-k=5) |
| `read_clean_doc` | Read a specific clean Markdown file in full |
| `check_pending_jobs` | Check if any files are still being processed |
| `analyze_gaps` | LLM gap analysis against checklist |
| `write_requirements` | Write/update `data/clean/requirements.md` |
| `write_proposal` | Write the proposal to `data/output/proposal_v{N}.md` |
| `post_message_to_slack` | Post a message (clarification questions, status updates) |
| `post_file_to_slack` | Post a file (proposal) to Slack |

---

### 3.6 Clarification Loop

**What it does:** When the agent finds critical information missing, it posts a single consolidated message in Slack with all missing questions. The team replies in the same thread. The agent collects the answers, merges them into its understanding, and re-evaluates. This loops until the requirement is complete or the max iteration limit is hit.

**Key rule:** One message per round — all missing items in one message. Not one question at a time.

**Exit conditions:**
- All critical checklist items are covered, OR
- User says "proceed" / "skip" / "make assumptions", OR
- `MAX_CLARIFY_ITERATIONS` reached → agent proceeds with stated assumptions

**What gets stored:** Every user reply is saved to `agent_messages` table with `role: 'user'`. The agent loads this history as clarification context on each run.

---

### 3.7 Feedback Handler

**What it does:** Accepts free-text instructions from the team after a proposal exists. Saves the instruction, re-generates the affected sections, and saves a new versioned proposal.

**Triggered by:** `app_mention` classified as intent `feedback` when `output/proposal_latest.md` exists.

**Storage:** Each instruction is appended to `state/feedback.jsonl` as a JSON line with `active: true`. All active instructions are loaded on every proposal update.

**Proposal versioning:** Each update creates `proposal_v{N}.md` with a YAML header recording the version, timestamp, and what changed. `proposal_latest.md` always points to the most recent version.

---

### 3.8 Common Knowledge Base

**What it does:** A shared directory of Markdown files that every agent reads when generating proposals. Contains organizational standards, templates, team profiles, and company status — things that are true for all projects, not just one client.

**Location:** `common/` — outside all workspaces. Read-only to all agents.

**Structure:**

| Folder | Contents | How agent uses it |
|--------|---------|-------------------|
| `requirements/check_list.md` | Checklist of what a complete requirement must cover | Loaded directly on every intake |
| `technical/*.md` | Approved tech stacks, architecture patterns, pricing, SLAs | Vector search, top-k=5 |
| `member_profiles/*.md` | Team member skills, role, availability | Loaded directly (small files) |
| `company_progress/*.md` | AWS setup, service provisioning status per client | Loaded directly (small files) |

**Re-indexing:** Any change to `common/` triggers automatic re-chunking and re-embedding of that folder's vector index.

---

### 3.9 Message History Capture

**What it does:** Saves every Slack message across all channel types to `state/messages.db`. Provides the agent with conversation context without relying on Slack's API for history retrieval.

**Strategy:** Reactive only. Messages are captured as they arrive via WebSocket events. No backfill of history before the bot was added.

**Coverage:** Public channels, private channels, DMs, and group DMs.

**Required Slack scopes:** `channels:history`, `groups:history`, `im:history`, `mpim:history`.

---

## 4. How Components Work Together

### Phase 1 — Workspace Setup

```
Team creates Slack channel and adds bot
    │
    ▼
Event Handler receives bot_joined_channel
    │
    ▼
WorkspaceManager.provision(channel_id, channel_name)
    → Sanitize channel name → workspace_name
    → Create directory tree
    → Initialize jobs.sqlite and agent.sqlite
    → Initialize empty ChromaDB collection
    → Post welcome message to Slack
```

---

### Phase 2 — File Ingestion and Processing

```
Team uploads a file to Slack
    │
    ▼
Event Handler receives file_shared
    │
    ▼
FileCollector.collect()
    → Download file from Slack API
    → Save to data/raw/{filename}  (overwrite if same name)
    → Insert job record in jobs.sqlite (status: pending)
    → Enqueue to ProcessingPipeline
    │
    ▼
ProcessingPipeline (background worker)
    → Poll jobs.sqlite for pending jobs
    → DataParser extracts text → clean Markdown
    → Save to data/clean/{filename}.md
    → Delete old VectorDB chunks for this filename
    → Embed chunks → upsert to workspace ChromaDB
    → Mark job status = 'done'
```

At this point the file is ready for the agent to retrieve.

---

### Phase 3 — Requirement Intake

```
User: "@bot Here is the client requirement: [text or attached file]"
    │
    ▼
Event Handler receives app_mention
    │
    ▼
AgentDispatcher classifies intent → 'propose'
    │
    ▼
Proposal Agent starts (LangGraph)
    → Check jobs.sqlite: any pending jobs?
         YES → post "Still processing files, please wait" → pause (PROCESSING_INPUTS)
         NO  → continue
    │
    ▼
Load common/requirements/check_list.md
    │
    ▼
Check requirement against checklist
    │
    ├── Critical items missing?
    │       │
    │       ▼
    │   Post ONE consolidated message to Slack:
    │   "I need a few details before writing the proposal:
    │    1. Timeline — What is the expected delivery date?
    │    2. Budget — Is there a budget ceiling?"
    │       │
    │       ▼
    │   Save state to SQLite → pause (AWAITING_CLARIFY)
    │       │
    │       ▼
    │   User replies in Slack
    │       │
    │       ▼
    │   Event Handler receives message → classifies intent → 'clarify'
    │       │
    │       ▼
    │   Agent resumes from checkpoint
    │   → Save answer to agent_messages
    │   → Merge into requirement understanding
    │   → Re-check checklist → loop if still missing
    │
    └── All critical items covered?
            │
            ▼
    Agent writes data/clean/requirements.md
    (structured, well-formatted requirement summary)
```

---

### Phase 4 — Proposal Generation

```
Requirement confirmed and written to clean/requirements.md
    │
    ▼
Agent retrieves context
    → search_workspace_docs(requirement_text, k=10)   ← client documents
    → search_common_knowledge(requirement_text, k=5)  ← standards + templates
    → load member_profiles/*.md                        ← team resources
    → load company_progress/*.md                       ← infrastructure status
    │
    ▼
Run gap analysis (claude-sonnet)
    → Compare requirement against common knowledge checklist
    → Is there enough info to write each proposal section?
    │
    ├── Gaps found → post clarifying questions → AWAITING_CLARIFY
    │
    └── Enough info → draft proposal (DRAFTING)
            │
            ▼
    write_proposal(content) → data/output/proposal_v1.md
            │
            ▼
    post_file_to_slack(proposal_v1.md)
            │
            ▼
    State: PROPOSAL_READY
```

---

### Phase 5 — Feedback and Updates

```
User: "@bot Assume the client has an existing DevOps team — don't include that cost."
    │
    ▼
Event Handler → classify intent → 'feedback'
    │
    ▼
FeedbackHandler
    → Save instruction to state/feedback.jsonl (active: true)
    → Acknowledge in Slack: "Got it, updating the proposal..."
    │
    ▼
Proposal Agent → UPDATE mode
    → Load proposal_latest.md
    → Load ALL active feedback instructions
    → Re-generate affected sections only
    → Save as proposal_v{N+1}.md
    → Post updated proposal to Slack
    │
    ▼
State: PROPOSAL_READY (again, waiting for next feedback)
```

---

### Component Interaction Summary

```
                    ┌──────────────┐
                    │  Slack API   │
                    └──────┬───────┘
                           │ WebSocket events
                           ▼
              ┌────────────────────────┐
              │    Event Handler       │
              └──┬──────┬──────┬───┬──┘
                 │      │      │   │
          joined │  file│ men- │msg│
                 │      │ tion │   │
                 ▼      ▼      │   ▼
         ┌────────┐ ┌───────┐  │ ┌──────────────┐
         │Workspace│ │File   │  │ │Message       │
         │Manager │ │Collect│  │ │History       │
         └────────┘ └───┬───┘  │ └──────┬───────┘
                        │      │        │
                        ▼      │        ▼
                  ┌──────────┐ │   messages.db
                  │Processing│ │
                  │Pipeline  │ │
                  └────┬─────┘ │
                       │       ▼
         data/raw/     │  ┌─────────────────┐
         data/clean/   │  │  Proposal Agent │◄── common/
         jobs.sqlite ──┘  │  (LangGraph)    │    requirements/
         VectorDB ────────►  agent.sqlite   │    technical/
                           │  agent_messages │    member_profiles/
                           └────────┬────────┘    company_progress/
                                    │
                                    ▼
                              Slack channel
                          (questions, proposals,
                           status updates)
```

---

## 5. Data Design

### `jobs.sqlite` — File Processing Log

Tracks every file received and its processing status. Internal only — no Slack notifications sent.

```sql
CREATE TABLE processing_jobs (
    id            TEXT PRIMARY KEY,
    channel_id    TEXT NOT NULL,
    filename      TEXT NOT NULL,
    raw_path      TEXT NOT NULL,
    clean_path    TEXT,
    file_type     TEXT,
    status        TEXT NOT NULL,    -- pending | processing | done | failed | unsupported
    error_message TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
```

---

### `agent.sqlite` — Agent State

Stores active sessions, conversation history, and feedback instructions.

```sql
CREATE TABLE agent_sessions (
    id                TEXT PRIMARY KEY,
    channel_id        TEXT NOT NULL,
    status            TEXT NOT NULL,
    requirement       TEXT,
    requirement_file  TEXT,
    clarify_iteration INTEGER DEFAULT 0,
    proposal_version  INTEGER DEFAULT 0,
    thread_ts         TEXT,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);

-- Status values:
-- idle | intake | awaiting_clarify | processing_docs
-- gap_analysis | drafting | proposal_ready | updating

CREATE TABLE agent_messages (
    id          TEXT PRIMARY KEY,
    channel_id  TEXT NOT NULL,
    thread_ts   TEXT,
    role        TEXT NOT NULL,   -- user | assistant
    content     TEXT NOT NULL,
    slack_ts    TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE feedback_instructions (
    id                 TEXT PRIMARY KEY,
    channel_id         TEXT NOT NULL,
    text               TEXT NOT NULL,
    active             INTEGER DEFAULT 1,
    created_at         TEXT NOT NULL,
    applied_to_version INTEGER
);
```

---

### `messages.db` — Message History

Full channel message log for conversation context.

```sql
CREATE TABLE messages (
    id         TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL,
    user_id    TEXT NOT NULL,
    ts         TEXT NOT NULL,    -- Slack timestamp (unique per channel)
    text       TEXT NOT NULL,
    created_at TEXT NOT NULL
);
```

---

### `state/feedback.jsonl` — Feedback Log

Append-only file. One JSON line per instruction.

```json
{"id": "uuid", "text": "No privacy concerns", "created_at": "2026-04-04T10:00:00Z", "active": true}
{"id": "uuid", "text": "Client has own DevOps team", "created_at": "2026-04-04T11:00:00Z", "active": true}
```

---

## 6. File System Layout

```
workspaces/
├── proj-acme-crm/
│   └── data/
│       ├── raw/
│       │   ├── requirements.pdf
│       │   ├── tech_overview.docx
│       │   └── budget.xlsx
│       │
│       ├── clean/
│       │   ├── requirements.md          ← agent-written canonical requirement
│       │   ├── requirements.pdf.md      ← parsed from raw/requirements.pdf
│       │   ├── tech_overview.docx.md
│       │   └── budget.xlsx.md
│       │
│       ├── output/
│       │   ├── proposal_v1.md
│       │   ├── proposal_v2.md
│       │   └── proposal_latest.md       ← always the most recent version
│       │
│       ├── vector_index/
│       │   └── chroma.sqlite3
│       │
│       └── state/
│           ├── workspace.json
│           ├── jobs.sqlite
│           ├── agent.sqlite
│           ├── messages.db
│           └── feedback.jsonl
│
└── proj-beta-mvp/
    └── data/ ...

common/
├── requirements/
│   └── check_list.md
├── technical/
│   ├── tech_standards.md
│   ├── architecture_patterns.md
│   ├── pricing_guide.md
│   └── sla_templates.md
├── member_profiles/
│   └── *.md
└── company_progress/
    └── *.md
```

**Key file — `clean/requirements.md`:**
- Written by the agent after requirement intake is complete
- Updated on every clarification round or requirement change
- Loaded directly into every proposal generation prompt (not via vector search)
- Indexed into VectorDB as part of the workspace so it is also retrievable semantically

---

## 7. Memory Layers

The agent has three distinct memory layers that serve different purposes.

```
┌─────────────────────────────────────────────────────────┐
│  Layer 1 — Short-term (LangGraph State)                  │
│  Lives in memory during a single agent run               │
│  Retrieved chunks, gap analysis, tool call results       │
│  Checkpointed to SQLite if agent pauses between turns    │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│  Layer 2 — Long-term (SQLite: agent.sqlite)              │
│  Persists across all sessions for a workspace            │
│  Conversation history, clarification answers, feedback   │
│  Loaded at the start of every agent run                  │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│  Layer 3 — Retrieval (ChromaDB VectorDB)                 │
│  Semantic search over all clean documents                │
│  Two indexes: workspace-specific + common knowledge      │
│  Agent searches at run start — never writes during run   │
└─────────────────────────────────────────────────────────┘
```

### Context Window Budget (Proposal Generation)

```
1. System prompt                            ~500 tokens  (fixed)
2. Active feedback instructions             ~500 tokens  (all active)
3. Client requirement (clean/requirements.md) ~2000 tokens
4. Clarification history                   ~1000 tokens  (Slack Q&A thread)
5. Project document chunks (top-k=10)      ~3000 tokens  (most relevant)
6. Common knowledge chunks (top-k=5)       ~1500 tokens  (standards + templates)
7. Existing proposal draft (UPDATE mode)   ~2000 tokens
─────────────────────────────────────────────────────────
Total target: ≤ 10,000 tokens

Truncation order (if over budget):
  1. Common knowledge chunks (truncate first)
  2. Project document chunks (drop least relevant)
  3. Summarize clarification history if very long
  4. Never truncate requirement or feedback instructions
```

---

## 8. State Machine

### Agent States

```
                        ┌───────────┐
                        │   IDLE    │ No active session
                        └─────┬─────┘
                              │ @bot [requirement]
                              ▼
                    ┌──────────────────┐
                    │ PROCESSING_DOCS  │ Waiting for pending file jobs
                    └────────┬─────────┘
                             │ all jobs done
                             ▼
                    ┌──────────────────┐
                    │     INTAKE       │ Checking requirement vs checklist
                    └────────┬─────────┘
                             │ critical items missing
                             ▼
                    ┌──────────────────┐
                    │ AWAITING_CLARIFY │◄──────────────┐
                    │ Posted questions  │               │
                    └────────┬─────────┘          still missing
                             │ user replies
                             ▼
                    ┌──────────────────┐
                    │   GAP_ANALYSIS   │ Enough info for proposal?
                    └────┬─────────────┘
           not enough    │        enough
                         ▼           ▼
              AWAITING_CLARIFY   ┌──────────┐
                                 │ DRAFTING │
                                 └────┬─────┘
                                      │ proposal posted
                                      ▼
                             ┌─────────────────┐
                             │  PROPOSAL_READY  │◄──┐
                             └────────┬─────────┘   │
                                      │ feedback     │
                                      ▼             │
                             ┌─────────────────┐   │
                             │    UPDATING      │───┘
                             └─────────────────┘
```

### State Transition Table

| From | Event | To | Action |
|------|-------|----|--------|
| IDLE | `@bot [requirement]` | PROCESSING_DOCS | Check pending file jobs |
| PROCESSING_DOCS | All jobs complete | INTAKE | Start checklist check |
| INTAKE | Critical items missing | AWAITING_CLARIFY | Post questions in Slack |
| AWAITING_CLARIFY | User replies | GAP_ANALYSIS | Merge answers, re-evaluate |
| GAP_ANALYSIS | Not enough info | AWAITING_CLARIFY | Post new questions |
| GAP_ANALYSIS | Enough info | DRAFTING | Write `requirements.md`, generate proposal |
| DRAFTING | Proposal written | PROPOSAL_READY | Post proposal to Slack |
| PROPOSAL_READY | Feedback instruction | UPDATING | Apply instruction, save new version |
| UPDATING | Update complete | PROPOSAL_READY | Post updated proposal |
| any | `@bot reset` | IDLE | Clear session, keep files |

### Pause and Resume

The agent can pause mid-workflow (e.g., waiting for user to reply to clarifying questions) and resume later without losing state. LangGraph checkpoints the full agent state to `agent.sqlite` at every step. When the next Slack event arrives, the agent loads from the checkpoint and continues exactly where it stopped.
