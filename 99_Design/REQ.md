# REQ — Slack-Based Project Agent System
## Requirements Specification

**Version:** 1.2  
**Status:** Draft

---

## Contents

1. [System Overview](#1-system-overview)
2. [Glossary](#2-glossary)
3. [System Architecture](#3-system-architecture)
4. [Component Specifications](#4-component-specifications)
   - [4.1 Slack Event Handler](#41-slack-event-handler)
   - [4.2 Workspace Manager](#42-workspace-manager)
   - [4.3 File Collector](#43-file-collector)
   - [4.4 Document Processing Pipeline](#44-document-processing-pipeline)
   - [4.5 Proposal Agent](#45-proposal-agent)
   - [4.6 Clarification Loop](#46-clarification-loop)
   - [4.7 Feedback Instruction Handler](#47-feedback-instruction-handler)
   - [4.8 Common Knowledge Base](#48-common-knowledge-base)
5. [Data Model](#5-data-model)
6. [File System Layout](#6-file-system-layout)
7. [Agent Workflow — State Machine](#7-agent-workflow--state-machine)
8. [Slack Command Interface](#8-slack-command-interface)
9. [LLM & Embedding Integration](#9-llm--embedding-integration)
10. [Error Handling](#10-error-handling)
11. [Configuration Reference](#11-configuration-reference)
12. [Non-Functional Requirements](#12-non-functional-requirements)
13. [Open Questions](#13-open-questions)

---

## 1. System Overview

### Purpose

A Slack-integrated AI agent system that manages the proposal workflow for a client project — from file intake and requirement clarification through proposal generation and proposal update — using a per-channel workspace model.

### Core Principle

**One Slack channel = one project workspace.**

The system manages **multiple concurrent workspaces**, one per channel. Each workspace is named after the Slack channel name (for example `proj-acme-crm`) and lives as its own directory under `workspaces/`. Each workspace has its own isolated data directory, document store, vector index, and agent state. No data crosses workspace boundaries.

A **shared common knowledge base** (`common/`) lives outside any workspace and is available to all proposal workflows.

### V1 Scope

V1 focuses on **proposal support only**:
- collect and process uploaded files
- understand requirement context
- ask clarification questions in Slack when important information is missing
- generate a proposal draft
- update the proposal when the team gives feedback

Other future task types such as design generation, sample data analysis, and error analysis are out of scope for V1, but the architecture should not block them.

### High-Level Flow

```text
Bot added to channel
        │
        ▼
Workspace provisioned (directories + DBs)
        │
        ▼
Team uploads files → data/raw/
        │
        ▼
Processing Pipeline converts files → data/clean/ → indexed if needed
        │
        ▼
User asks bot to create proposal
(message may include text, attached files, or both)
        │
        ▼
Agent loads requirement + processed documents + common checklist
        │
        ▼
Agent asks ONE consolidated clarification message if important information is missing
        │
        ▼
Team replies in Slack thread
        │
        ▼
Agent updates clean/requirements.md
        │
        ▼
If enough information exists → Draft proposal → post to Slack
        │
        ▼
Team sends feedback instructions
        │
        ▼
Agent updates proposal + saves new version
```

### Design Principles for V1

- **File upload = asset registration**
- **`@bot` mention = action request**
- **Clarification happens in Slack thread, not by generated Excel**
- **`clean/requirements.md` is the canonical structured requirement file**
- **Store all channel history, but do not load all history blindly into every LLM call**

---

## 2. Glossary

| Term | Definition |
|------|-----------|
| **Workspace** | The isolated directory + state for one Slack channel / project |
| **Raw file** | Original file as uploaded by the team to Slack |
| **Clean document** | Processed Markdown version of a raw file, ready for LLM consumption |
| **`clean/requirements.md`** | Agent-written structured summary of the current confirmed requirement for this workspace |
| **Proposal** | The output document drafted by the agent for the client |
| **Clarification loop** | Slack-based back-and-forth where the agent posts questions and the team replies until enough information is gathered to write the proposal |
| **Feedback instruction** | A free-text instruction from the team that changes how the proposal should be updated |
| **Channel ID** | Slack's unique identifier for a channel, used as workspace key |
| **Processing pipeline** | The background worker that converts raw files to clean Markdown |
| **Vector index** | Per-workspace vector store of clean document chunks for semantic search |
| **Common knowledge** | Shared Markdown files outside any workspace — checklist, technical standards, member profiles, company progress |
| **Task session** | The current active workflow for one channel. In V1 this is proposal-focused. |

---

## 3. System Architecture

```text
┌──────────────────────────────────────────────────────────────────────┐
│                          Slack Platform                              │
│  Events API ──────────────────────────────────────────────────────►  │
│  (file_shared, app_mention, message.channels, message.groups)       │
└────────────────────────┬─────────────────────────────────────────────┘
                         │  WebSocket (Socket Mode — persistent, TLS)
                         ▼
┌──────────────────────────────────────────────────────────────────────┐
│              Event Handler (slack_bolt SocketModeHandler)           │
│  - Persistent WebSocket connection to Slack                         │
│  - No public HTTP endpoint required                                 │
│  - Dispatch to:                                                     │
│      WorkspaceManager   ← bot added to channel                      │
│      FileCollector      ← file_shared                               │
│      AgentDispatcher    ← app_mention, thread replies               │
│      HistoryCapture     ← channel messages                          │
└──────┬──────────────────────────┬────────────────────────────────────┘
       │                          │
       ▼                          ▼
┌──────────────────┐   ┌─────────────────────────────────────────────┐
│ Workspace        │   │ Processing Pipeline (asyncio background)    │
│ Manager          │   │ - reads jobs from internal queue            │
│                  │   │ - extracts / converts / saves to clean/     │
│ workspaces/      │   │ - chunks + embeds when needed               │
│ {channel_name}/  │   └─────────────────────────────────────────────┘
│ └── data/        │
│     ├── raw/     │   ┌─────────────────────────────────────────────┐
│     ├── clean/   │   │ Proposal Agent (LLM-powered)                │
│     ├── output/  │   │ - reads requirement + processed docs        │
│     └── state/   │   │ - reads shared common knowledge             │
│                  │   │ - asks clarification questions in Slack     │
│ common/          │   │ - drafts / updates proposal                 │
│ ├── requirements/│   │ - applies feedback instructions             │
│ ├── technical/   │   └─────────────────────────────────────────────┘
│ ├── member_profiles/
│ └── company_progress/
└──────────────────┘
```

### Technology Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Slack integration | `slack_bolt` (Python) + `slack_sdk` Socket Mode | WebSocket Socket Mode only |
| Web server | FastAPI | Health check + internal API only |
| Background worker | `asyncio` task queue | V1 keeps worker simple; no Celery |
| LLM | Claude or equivalent | Main proposal reasoning and drafting |
| Fast LLM | Smaller model | Classification, routing, light summarization |
| Embeddings | `text-embedding-3-small` or equivalent | Per-workspace vector index |
| Vector store | ChromaDB or Qdrant | Per-channel collection |
| File parsing | `docling`, `markitdown`, or external helper tools | Chosen per file type / quality needs |
| External helper tools | Claude Code, Codex | Optional bounded helpers for extraction or summarization |
| State DB | SQLite (per workspace) | Agent state, job tracking, message history |
| Config | `pydantic-settings` + `.env` | Environment-based config |

### Architecture Note

The system workflow, state management, storage, retrieval policy, and proposal versioning are controlled by this application. External tools such as Claude Code or Codex may be used only as bounded helper functions for sub-tasks such as PDF-to-Markdown conversion, summarization, or draft generation.

---

## 4. Component Specifications

---

### 4.1 Slack Event Handler

#### Transport: WebSocket via Socket Mode

The system uses **Slack Socket Mode** exclusively. This establishes a persistent outbound WebSocket connection from the bot to Slack's WebSocket gateway. No inbound public HTTP endpoint is required.

#### Events to Handle

| Event | Trigger | Handler |
|-------|---------|---------|
| `bot_joined_channel` | Bot added to existing channel | `WorkspaceManager.provision()` |
| `file_shared` | File uploaded to channel | `FileCollector.collect()` |
| `app_mention` | `@bot` message | `AgentDispatcher.dispatch()` |
| `message.channels` | Any public channel message | `HistoryCapture.save()` |
| `message.groups` | Any private channel message | `HistoryCapture.save()` |

#### V1 Scope Rule

Proposal workflow is triggered **only inside a Slack channel where the bot has already been added**.

Direct messages are **not used for proposal workflow in V1**.

#### Async Dispatch Pattern

All heavy work is dispatched to an internal background queue so the WebSocket handler returns immediately.

```text
Slack pushes event over WebSocket
    │
    ▼
Handler receives event
    │
    ├── Enqueue task to internal worker queue
    ├── Acknowledge event to Slack immediately
    └── Return
                    │
             background task processes work
```

#### Conversation History

The bot captures channel message history **reactively** — every relevant message received via WebSocket event is immediately saved to SQLite. No backfill of pre-bot history is performed.

**Coverage:**

| Scope | Event | Stored |
|-------|-------|--------|
| Public channels | `message.channels` | Yes |
| Private channels | `message.groups` | Yes |

Each message is stored in `state/messages.db` inside the channel's workspace with `channel_id`, `user_id`, `ts`, `thread_ts`, and `text`.

The system does **not** load full channel history into every LLM call. Instead, it uses a selective policy:
- always include messages from the active proposal thread
- include explicitly referenced recent messages when relevant
- optionally retrieve additional relevant chat snippets from `messages.db` when proposal context appears incomplete

**Required Slack OAuth Scopes:**

```text
# Public channels
channels:history
message.channels

# Private channels
groups:history
message.groups

# Bot mentions
app_mentions:read
```

---

### 4.2 Workspace Manager

#### Responsibilities
- Create and initialize a workspace directory structure for each new channel
- Register the workspace in the global registry
- Detect if a workspace already exists (idempotent provisioning)

#### Provisioning Trigger

Workspace is created **only** when the bot is added to a channel (`bot_joined_channel`). This is the single guaranteed trigger.

`file_shared` and `app_mention` handlers assume the workspace already exists. If it does not, they log a warning and skip.

#### Workspace Naming

Workspaces are named after the **Slack channel name**, not the channel ID, so the directory is human-readable.

```text
Slack channel: #proj-acme-crm  →  workspaces/proj-acme-crm/
Slack channel: #proj-beta-mvp  →  workspaces/proj-beta-mvp/
Slack channel: #proj-xyz-2026  →  workspaces/proj-xyz-2026/
```

**Name sanitization rules:**
- lowercase
- replace spaces with `-`
- remove characters not in `[a-z0-9-_]`
- truncate to 80 characters
- on collision, append `_{channel_id_suffix}`

The `channel_id` is always stored in `workspace.json` as the authoritative lookup key.

#### Provisioning Actions

```text
WorkspaceManager.provision(channel_id, channel_name)
    │
    ├── sanitize channel_name → workspace_name
    ├── if workspace exists → return existing workspace
    ├── create directory tree under workspaces/{workspace_name}/
    ├── initialize SQLite databases
    ├── initialize empty vector collection
    └── post welcome message to Slack channel
```

#### Multiple Workspace Layout

```text
workspaces/
├── proj-acme-crm/
│   └── data/ ...
├── proj-beta-mvp/
│   └── data/ ...
└── proj-xyz-2026/
    └── data/ ...

common/
├── requirements/
├── technical/
├── member_profiles/
└── company_progress/
```

#### Workspace Metadata (`state/workspace.json`)

```json
{
  "workspace_name": "proj-acme-crm",
  "channel_id": "C08XXXXXXX",
  "channel_name": "proj-acme-crm",
  "created_at": "2026-04-01T10:00:00Z",
  "status": "active",
  "file_count": 0,
  "last_activity": "2026-04-01T10:00:00Z"
}
```

---

### 4.3 File Collector

#### Responsibilities
- Download every file shared in the Slack channel
- Save to `workspaces/{workspace_name}/data/raw/`
- Create a processing job record in `jobs.sqlite`
- Enqueue a parsing job for each supported file
- Preserve file version history when the same logical filename is uploaded again

#### Supported File Types

| Type | Extensions |
|------|-----------|
| PDF | `.pdf` |
| Word | `.docx`, `.doc` |
| Excel | `.xlsx`, `.xls` |
| PowerPoint | `.pptx`, `.ppt` |
| Plain text | `.txt`, `.md` |
| Images | `.png`, `.jpg`, `.jpeg` |

Unsupported files are still saved to `raw/` but marked `status: unsupported`.

#### Collection Flow

```text
file_shared event received
    │
    ├── 1. Download file from Slack
    ├── 2. Save to data/raw/{timestamped_filename}
    ├── 3. Insert job record in jobs.sqlite
    └── 4. Enqueue processing job if supported
```

#### File Versioning Rule

If the same filename is uploaded again, save the new raw file as a **new version with timestamp suffix**.

Example:

```text
requirements.pdf
requirements__20260404T083000Z.pdf
requirements__20260405T091500Z.pdf
```

The latest processed version becomes the canonical current version for retrieval and proposal generation. Older versions are retained for traceability.

#### File Processing Log (`jobs.sqlite`)

Every file that arrives gets a record in `jobs.sqlite`.

| Column | What it stores |
|---|---|
| `id` | Unique job ID |
| `channel_id` | Which workspace this file belongs to |
| `filename` | Original filename from Slack |
| `stored_filename` | Timestamped saved filename |
| `raw_path` | Path to the saved original file |
| `clean_path` | Path to the parsed Markdown output |
| `file_type` | File extension |
| `status` | `pending` → `processing` → `done` / `failed` / `unsupported` |
| `error_message` | What went wrong, if failed |
| `created_at` | When the file arrived |
| `updated_at` | When the status last changed |
| `is_latest` | Whether this is the latest version for that logical filename |

---

### 4.4 Document Processing Pipeline

#### Responsibilities
- Watch the internal queue for `pending` jobs
- Extract raw text from each file type
- Convert to clean, structured Markdown
- Save clean output to `workspaces/{workspace_name}/data/clean/`
- Chunk and index documents when needed
- Update job status on completion or failure

#### Processing Strategy

The system may use either:
- deterministic parsing libraries such as **Docling** or **MarkItDown**, or
- external AI helper tools such as **Claude Code** or **Codex**

These are used only as bounded sub-task helpers for document extraction, summarization, or draft preparation.

#### Processing Worker Design

The worker is implemented using an internal `asyncio` task queue.

```text
Async worker loop
    │
    └── Wait for new processing jobs in internal queue
               │
               ├── Mark job status = 'processing'
               ├── Run FileProcessor(raw_path, file_type)
               │       │
               │       ├── Extract text using parser or external helper
               │       ├── Clean noise
               │       ├── Convert to structured Markdown
               │       └── Return markdown_content
               │
               ├── Save clean Markdown
               ├── Chunk and index if needed
               ├── Mark job status = 'done'
               └── On error: mark status = 'failed' and store error_message
```

#### Chunking and Indexing Rule

- `clean/requirements.md` is always loaded directly and does not depend on vector search
- Small, short clean files may also be loaded directly
- Large or numerous workspace documents are chunked and indexed for semantic retrieval

---

### 4.5 Proposal Agent

#### Responsibilities
- Accept proposal requests from Slack channel messages with optional attached files
- Read requirement text, processed project documents, and common knowledge
- Identify missing information needed to draft the proposal
- Ask one consolidated clarification message per round in Slack
- Update `data/clean/requirements.md` as the canonical structured requirement summary
- Retrieve relevant project and common context when needed
- Draft the proposal once enough information is available
- Apply feedback instructions to update an existing proposal

#### Trigger Model

The system separates file intake from action execution.

1. `file_shared`
   - Download and process the file
   - Store it in the workspace
   - Do **not** automatically start proposal generation

2. `@bot` message without file
   - Classify user intent
   - If intent is `propose`, start or continue the proposal workflow using already available workspace files

3. `@bot` message with attached file
   - Register and process the file
   - Create an action request linked to the current message
   - Start the proposal workflow after required files are ready

4. Reply in active clarification thread
   - Treat as clarification answer for the current active session

#### Intent Table

| Intent | Example | Behavior in V1 | Future Extension |
|--------|---------|----------------|------------------|
| `propose` | "Help me create a proposal" | Supported | Core workflow |
| `clarify` | Reply to clarification thread | Supported | Core workflow |
| `feedback` | "Add a section on data migration" | Supported | Core workflow |
| `status` | "What is the status?" | Supported | Core workflow |
| `question` | "What documents do you have?" | Supported | Info query |
| `analyze_data` | "Analyze this sample data" | Not supported yet | Future |
| `design` | "Create solution design" | Not supported yet | Future |
| `error_analysis` | "Analyze these logs" | Not supported yet | Future |

#### Requirement Input — Channel Only (V1)

In V1, the proposal workflow is triggered only inside a Slack channel where the bot has already been added.

Supported input forms:
- `@bot` message with requirement text
- `@bot` message with attached file
- `@bot` message with both text and attached file

The channel is the workspace boundary. Direct messages are not used for proposal workflow in V1.

#### Proposal Preparation State Machine

```text
Request received in channel
        │
        ▼
Check whether required uploaded files are already processed
        │
        ├── if not ready → wait for processing completion
        │
        ▼
Load requirement text + clean docs + checklist + relevant common knowledge
        │
        ▼
Check whether important information is missing for proposal drafting
        │
        ├── if missing → enter clarification loop
        │
        └── if enough → draft proposal
```

#### `clean/requirements.md` — Canonical Requirement File

This file is the agent's structured summary of the client requirement for this workspace. It is the single source of truth used for proposal generation.

- Created when the agent has enough information to structure the requirement clearly
- Updated whenever the user provides new information or changes the requirement
- Stored in `data/clean/`
- Format: structured Markdown with clear sections such as objective, scope, constraints, timeline, assumptions, stakeholders, and open points

If `clean/requirements.md` already exists when a new requirement arrives, the agent updates it rather than creating a new file.

#### Agent Inputs

| Input | Source | How loaded |
|-------|--------|-----------|
| Requirement text | User's Slack message or uploaded file | Parsed directly or loaded from `data/clean/` |
| `clean/requirements.md` | Workspace `data/clean/` | Always loaded directly as primary context |
| Requirement checklist | `common/requirements/check_list.md` | Loaded in full |
| Project documents | Workspace clean docs / vector index | Direct load if small, semantic search if large |
| Technical standards | `common/technical/` | Direct load for small files, vector retrieval if large |
| Member profiles | `common/member_profiles/` | Loaded in full |
| Company progress | `common/company_progress/` | Loaded in full |
| Active feedback | `state/feedback.jsonl` | All active instructions loaded |
| Clarification history | `agent_messages` + active thread | Selective thread-based loading |
| Proposal draft | `data/output/proposal_latest.md` | Loaded only in update mode |

#### Clarification Analysis Requirements

The clarification analysis prompt must:
- check requirement completeness against the checklist
- identify only critical missing items
- produce one consolidated clarification message
- indicate whether the agent can proceed with assumptions

Detailed prompt text is maintained outside this requirement document.

#### Proposal Generation Requirements

The proposal generation prompt must:
- use `clean/requirements.md` as primary requirement context
- use project documents and common knowledge as supporting context
- generate a structured Markdown proposal
- flag missing information explicitly instead of inventing facts
- apply active feedback instructions

Detailed prompt text is maintained outside this requirement document.

---

### 4.6 Clarification Loop

#### Purpose

When the agent needs more information to draft the proposal, it posts a clarifying message directly in the Slack thread. The team replies in Slack. No Excel exchange is used in V1.

#### Clarification Loop State Machine

```text
Agent determines important information is missing
        │
        ▼
Post ONE clarifying message to Slack thread
  - List all missing critical items as numbered questions
  - Keep it concise
  - One message per round, not one question at a time
        │
        ▼
State: CLARIFYING
        │
        ▼
Team replies in the same thread
        │
        ▼
Store answers in agent state
        │
        ▼
Re-evaluate requirement completeness
        │
        ├── still missing → ask next clarification round
        │
        └── enough information → update clean/requirements.md and continue to proposal drafting
```

#### Exit Conditions

The agent stops asking when:
- all critical checklist items are sufficiently covered, or
- user explicitly says `proceed`, `skip`, or `make assumptions`, or
- maximum clarification rounds is reached

#### Clarification Message Rules

Each clarification message should:
- contain only critical missing items
- avoid repeating already answered questions
- use simple, direct wording
- be posted under the active request thread

---

### 4.7 Feedback Instruction Handler

#### Purpose

Allow the team to send free-text instructions that modify how the proposal should be updated, without starting from scratch.

#### Trigger Conditions

A message is treated as feedback when:
- it is addressed to the bot in the active proposal thread, and
- the dispatcher classifies it as intent `feedback`, and
- there is an existing proposal draft in `output/`

#### Examples of Feedback Instructions

```text
"No need to worry about privacy regulations."
"Assume the client already has a DevOps team."
"Add a section on data migration from their legacy system."
"Use agile methodology for the timeline section."
"The budget ceiling is $50,000."
```

#### Feedback Storage (`state/feedback.jsonl`)

Each instruction is appended as a JSON line:

```json
{"id": "uuid", "text": "No need to worry about privacy", "created_at": "2026-04-01T11:00:00Z", "active": true, "source_user": "U08XXXXXXX"}
```

#### Feedback Processing Flow

```text
Feedback instruction received
        │
        ├── Save to feedback.jsonl
        ├── Acknowledge in Slack
        ├── Load existing proposal
        ├── Load all active feedback instructions
        ├── Re-run proposal update in UPDATE mode
        ├── Save updated proposal (versioned)
        └── Post updated proposal + short change summary
```

#### Proposal Versioning

```text
output/
├── proposal_v1.md
├── proposal_v2.md
├── proposal_v3.md
└── proposal_latest.md
```

Each version includes a version header:

```markdown
---
version: 3
created_at: 2026-04-01T12:00:00Z
based_on: v2
change_reason: "Applied instruction: No need to worry about privacy"
---
```

---

### 4.8 Common Knowledge Base

#### Purpose

The Common Knowledge Base is a shared, workspace-independent repository of Markdown files that every proposal workflow can read when generating technical solutions.

This separates:
- **workspace-specific truth** for one client/project
- **shared organizational knowledge** used across many projects

#### Location

```text
common/
├── requirements/
│   └── check_list.md
├── technical/
│   └── *.md
├── member_profiles/
│   └── *.md
└── company_progress/
    └── *.md
```

This directory lives outside all workspaces and is read-only to all agents.

#### Example Files

| File | Content |
|------|---------|
| `requirements/check_list.md` | Checklist of what a requirement must cover before proposal drafting |
| `technical/tech_standards.md` | Approved languages, frameworks, cloud platforms |
| `technical/architecture_patterns.md` | Reusable architecture patterns |
| `technical/pricing_guide.md` | Day rates, pricing models |
| `technical/sla_templates.md` | Standard SLA tiers and response times |
| `member_profiles/john_doe.md` | Skills, role, availability |
| `company_progress/aws_setup.md` | Client-related setup progress |

#### Indexing

Common knowledge files are indexed into a shared vector collection when needed. The index is separate from all workspace vector indexes.

**Re-indexing trigger:** any change under `common/`.

Conceptually:

```python
for md_file in Path("common").rglob("*.md"):
    ...
```

#### How the Agent Uses Common Knowledge

During proposal generation, the agent queries both:
- workspace-specific context
- common shared knowledge

It keeps the sources separate so the model can distinguish client-specific facts from general company standards.

#### Retrieval Policy

The system uses two retrieval modes:

1. **Direct load**
   - Used for small, high-priority files such as `clean/requirements.md`, checklist, member profiles, and short common files

2. **Vector retrieval**
   - Used when workspace documents are large or numerous
   - Used to find the most relevant chunks from project documents and common technical knowledge

**Default rule:**
- always load `clean/requirements.md` directly
- load small structured files directly
- use vector retrieval only for larger document sets

#### Maintenance

- The team manages `common/` files directly
- Adding, editing, or deleting a file triggers re-indexing
- Agent never writes to `common/`

---

## 5. Data Model

### Agent State (`agent.sqlite`)

```sql
CREATE TABLE agent_sessions (
    id                TEXT PRIMARY KEY,
    channel_id        TEXT NOT NULL,
    task_type         TEXT NOT NULL DEFAULT 'proposal',
    status            TEXT NOT NULL,
    requirement       TEXT,
    requirement_file  TEXT,
    clarification_round INTEGER DEFAULT 0,
    proposal_version  INTEGER DEFAULT 0,
    thread_ts         TEXT,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);

-- V1 task_type:
-- proposal

-- V1 status enum:
-- idle
-- processing_inputs
-- clarifying
-- drafting
-- proposal_ready
-- updating
-- failed

CREATE TABLE agent_messages (
    id          TEXT PRIMARY KEY,
    channel_id  TEXT NOT NULL,
    thread_ts   TEXT,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    slack_ts    TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE feedback_instructions (
    id                  TEXT PRIMARY KEY,
    channel_id          TEXT NOT NULL,
    text                TEXT NOT NULL,
    active              INTEGER DEFAULT 1,
    created_at          TEXT NOT NULL,
    applied_to_version  INTEGER
);
```

### V1 Session Policy

Only **one active proposal session per channel** is supported in V1.

If a new proposal request arrives while another proposal session is still active, the bot must:
- reject the new request, or
- ask the user to reset the current session first

---

## 6. File System Layout

```text
workspaces/
│
├── proj-acme-crm/
│   └── data/
│       ├── raw/
│       │   ├── requirements__20260404T083000Z.pdf
│       │   ├── meeting_notes__20260404T093000Z.docx
│       │   └── sample_data__20260404T103000Z.xlsx
│       │
│       ├── clean/
│       │   ├── requirements__20260404T083000Z.md
│       │   ├── meeting_notes__20260404T093000Z.md
│       │   ├── sample_data__20260404T103000Z.md
│       │   └── requirements.md
│       │
│       ├── output/
│       │   ├── proposal_v1.md
│       │   ├── proposal_v2.md
│       │   └── proposal_latest.md
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
├── proj-beta-mvp/
│   └── data/ ...
│
└── proj-xyz-2026/
    └── data/ ...

common/
├── requirements/
│   └── check_list.md
├── technical/
│   ├── tech_standards.md
│   ├── pricing_guide.md
│   └── sla_templates.md
├── member_profiles/
│   └── *.md
└── company_progress/
    └── *.md
```

---

## 7. Agent Workflow — State Machine

```text
                    ┌──────────────────────────────────────────────┐
                    │                    IDLE                      │
                    │  No active proposal session                  │
                    └────────────────────┬─────────────────────────┘
                                         │ @bot proposal request
                                         ▼
                    ┌──────────────────────────────────────────────┐
                    │             PROCESSING_INPUTS                │
                    │  Wait until required files are processed     │
                    └────────────────────┬─────────────────────────┘
                                         │ inputs ready
                                         ▼
                    ┌──────────────────────────────────────────────┐
                    │                CLARIFYING                    │
                    │  Ask questions only if critical info         │
                    │  needed for proposal is missing              │
                    └──────┬───────────────────────────┬───────────┘
                           │ still missing              │ enough info
                           ▼                            ▼
             stay in CLARIFYING             ┌────────────────────────────┐
             and ask next round             │          DRAFTING          │
                                            │  Generate proposal draft   │
                                            └──────────────┬─────────────┘
                                                           │ proposal posted
                                                           ▼
                                            ┌────────────────────────────┐
                                            │       PROPOSAL_READY       │
                                            │ Waiting for feedback       │
                                            └──────────────┬─────────────┘
                                                           │ feedback received
                                                           ▼
                                            ┌────────────────────────────┐
                                            │         UPDATING           │
                                            │ Apply feedback instruction │
                                            └──────────────┬─────────────┘
                                                           │ update posted
                                                           ▼
                                                   back to PROPOSAL_READY
```

### State Transition Rules

| From | Event | To | Action |
|------|-------|----|--------|
| IDLE | `@bot` proposal request | PROCESSING_INPUTS | Start or resume proposal workflow |
| PROCESSING_INPUTS | Required files ready | CLARIFYING | Run clarification analysis |
| CLARIFYING | Missing info remains | CLARIFYING | Post one clarification message |
| CLARIFYING | Enough info available | DRAFTING | Update `clean/requirements.md` and generate proposal |
| DRAFTING | Proposal generated | PROPOSAL_READY | Post proposal to Slack |
| PROPOSAL_READY | Feedback instruction | UPDATING | Apply feedback and save new version |
| UPDATING | Update complete | PROPOSAL_READY | Post updated proposal |
| any | `@bot reset` | IDLE | Clear current session |

### Future Expansion Note

The current state machine is proposal-focused for V1.

In future versions, the system may generalize session handling to support additional task types such as design generation, sample data analysis, and error analysis.

---

## 8. Slack Command Interface

### Commands (via `@bot` mention)

| Command | Example | Description |
|---------|---------|-------------|
| **Trigger proposal** | `@bot Here is the requirement: [text or attached file]` | Starts the proposal workflow |
| **Check status** | `@bot status` | Returns current agent state + pending jobs |
| **List documents** | `@bot what documents do you have?` | Lists processed clean documents |
| **Force re-process** | `@bot reprocess [filename]` | Re-runs processing pipeline on a file |
| **Apply feedback** | `@bot [feedback instruction]` | Updates proposal per instruction |
| **Reset session** | `@bot reset` | Clears current proposal session (keeps files) |
| **Show proposal** | `@bot show proposal` | Re-posts latest proposal draft |

### Bot Response Format

All bot responses should be threaded under the user's triggering message when possible.

#### Processing acknowledgment

```text
I received your request. I'll continue in this thread after the related files are ready.
```

#### Clarifying questions

```text
I need a few more details before I can write the proposal:

1. Timeline — What is the expected delivery date?
2. Budget — Is there a budget ceiling?
3. Users — How many concurrent users are expected?

Please reply in this thread and I will continue.
```

#### Proposal posting

```text
Here is the proposal draft (v1):

[attachment: proposal_v1.md]

Key assumptions made:
- Estimated 50 concurrent users
- 3-month timeline assumed

Let me know what you want to change.
```

#### Update acknowledgment

```text
Got it. I am updating the proposal based on your instruction and will reply in this thread.
```

---

## 9. LLM & Embedding Integration

### Model Assignments

| Task | Model | Reason |
|------|-------|--------|
| Clarification analysis | Main reasoning model | Requires strong reasoning |
| Proposal generation | Main reasoning model | High quality output needed |
| Proposal update | Main reasoning model | Complex instruction following |
| Intent classification | Fast model | Cheap, fast classification |
| Markdown conversion / document extraction helper | Fast model or external helper | High volume, bounded sub-task |
| Embedding | Embedding model | Cost-efficient semantic retrieval |

### Context Window Strategy

For proposal generation, construct the prompt in this priority order:

```text
1. System prompt                                     ~500 tokens
2. Active feedback instructions                      ~500 tokens
3. clean/requirements.md                             ~2000 tokens
4. Clarification history from active thread          ~1000 tokens
5. Project document chunks (workspace, top-k=10)     ~3000 tokens
6. Common knowledge chunks (common/, top-k=5)        ~1500 tokens
7. Existing proposal draft (UPDATE mode only)        ~2000 tokens
──────────────────────────────────────────────────────────────
Total target: ≤ 10000 tokens
```

**Truncation priority when over budget:**
1. Common knowledge chunks
2. Project document chunks
3. Summarize long clarification history
4. Never truncate `clean/requirements.md` or active feedback instructions

### Retrieval Strategy

The system uses hybrid retrieval:
- direct load for small, critical files
- vector retrieval for larger document sets

Conceptually:

```python
def retrieve_context(workspace_name: str, query: str) -> dict:
    return {
        "requirement": load("clean/requirements.md"),
        "project": retrieve_project_context(workspace_name, query),
        "common": retrieve_common_context(query),
        "thread": retrieve_active_thread_context(workspace_name),
    }
```

### Prompt Management

Detailed prompt text is maintained outside this requirement document.

Recommended structure:

```text
prompts/
├── clarification_analysis.md
├── proposal_generation.md
└── proposal_update.md
```

---

## 10. Error Handling

### Processing Pipeline Errors

| Error | Behavior |
|-------|---------|
| File download fails | Retry 3× with exponential backoff; notify Slack on final failure |
| Unsupported file type | Mark `status: unsupported`; post a simple notice if user tries to use it |
| Parser exception | Mark `status: failed`; log error; post failure message |
| AI-based conversion fails | Fallback to deterministic parser if available, or save best-effort text |
| Embedding fails | Retry 3×; file may still be saved to `clean/` even if unindexed |

### Agent Errors

| Error | Behavior |
|-------|---------|
| LLM API timeout / error | Retry 2×; post a short retry/failure message |
| No usable project docs | Proceed with requirement text only and note limited context |
| Clarification loop exceeds max rounds | Draft with explicit assumptions and warn the user |
| Update instruction conflicts with prior instruction | Ask for clarification before updating |

### Retry Policy

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
)
async def call_llm(prompt: str) -> str:
    ...
```

---

## 11. Configuration Reference

```env
# Slack
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...

# LLM
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Vector Store
VECTOR_STORE=chroma
CHROMA_PERSIST_DIR=./data
QDRANT_URL=http://localhost:6333

# Paths
WORKSPACES_DIR=./workspaces
COMMON_DIR=./common
DEBOUNCE_SECONDS=5
MAX_CHUNK_TOKENS=512
CHUNK_OVERLAP_TOKENS=50
TOP_K_RETRIEVAL=10
COMMON_KNOWLEDGE_TOP_K=5
WORKSPACE_DOCS_TOP_K=10

# Agent
MAX_CLARIFICATION_ROUNDS=3
LLM_MAIN_MODEL=claude-sonnet-4-6
LLM_FAST_MODEL=claude-haiku-4-5-20251001
EMBEDDING_MODEL=text-embedding-3-small
MAX_CONTEXT_TOKENS=10000

# Processing helpers
PARSER_BACKEND=docling          # docling | markitdown | helper_agent
HELPER_AGENT=claude_code        # claude_code | codex | none
ENABLE_OCR=true
```

---

## 12. Non-Functional Requirements

| Category | Requirement |
|----------|-------------|
| **Response time** | Slack acknowledgment ≤ 3 seconds |
| **Processing latency** | Single PDF (≤ 20 pages): target within 60 seconds |
| **Proposal generation** | Initial draft target within 120 seconds of trigger |
| **Concurrency** | Support ≥ 10 simultaneous active project channels |
| **Data isolation** | Strict per-channel isolation. No query, file, or state crosses channel boundaries |
| **Durability** | All raw files and proposals persisted to disk immediately |
| **Versioning** | Re-uploading a file with the same name creates a new file version. The latest version is used for retrieval and proposal generation |
| **Observability** | Structured logs per component. Job status queryable via `@bot status` |
| **Security** | Socket Mode only. No public Slack endpoint exposed. Tokens stored only in environment variables |
| **Common knowledge** | `common/` is read-only to all agents |
| **Portability** | All workspace data in `./workspaces/`, shared knowledge in `./common/` |

---

## 13. Open Questions

| # | Question | Impact | Owner |
|---|----------|--------|-------|
| 1 | Which vector store should be used in V1: ChromaDB or Qdrant? | Infrastructure setup | — |
| 2 | Who has permission to send feedback instructions: any channel member or specific roles only? | Security + Slack permissions | — |
| 3 | Should proposals be posted as Slack messages, file attachments, or both? | UX | — |
| 4 | Should the bot later support multiple active sessions per channel? | State machine complexity | — |
| 5 | How should future task types such as design generation or sample data analysis be introduced into the dispatcher and session model? | Expansion design | — |
| 6 | Is there a need to export final proposals to Google Docs, Confluence, or another system? | Integration scope | — |
