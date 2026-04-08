# Data and Storage

Three storage systems, each with a distinct role:

| # | System | Technology | What it holds |
|---|---|---|---|
| 1 | Relational DB | PostgreSQL | Messages, files, sessions, feedback |
| 2 | Vector DB | ChromaDB | Document chunks + embeddings |
| 3 | Filesystem | Disk | Raw files, clean Markdown, proposal versions |

**Workspace isolation key:** `channel_id` — present on every PostgreSQL table row and every ChromaDB chunk as a metadata field. Queries always filter by `channel_id`; no data crosses channel boundaries.

---

## Relational DB — PostgreSQL

Database: `proposal_agent`

### `messages`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `channel_id` | TEXT | workspace key |
| `channel_type` | TEXT | `slack` / `teams` / … |
| `user_id` | TEXT | |
| `role` | TEXT | `user` / `assistant` / `system` |
| `content` | TEXT | |
| `thread_id` | TEXT | Slack thread_ts or equivalent |
| `file_ids` | TEXT | JSON list of referenced file UUIDs |
| `platform_ts` | TEXT | native platform timestamp |
| `created_at` | TIMESTAMPTZ | |

INSERT-only. No UPDATE or DELETE.

### `files`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `channel_id` | TEXT | workspace key |
| `user_id` | TEXT | uploader |
| `original_name` | TEXT | filename as uploaded |
| `stored_name` | TEXT | timestamped filename on disk |
| `file_type` | TEXT | extension, e.g. `.pdf` |
| `file_size` | BIGINT | bytes |
| `raw_path` | TEXT | absolute path to raw file |
| `clean_path` | TEXT | absolute path to clean Markdown |
| `status` | TEXT | see file lifecycle below |
| `file_summary` | TEXT | LLM-generated 2–3 sentence summary |
| `is_latest` | BOOL | `false` on all previous versions of same filename |
| `is_deleted` | BOOL | soft delete |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |

**Supported file types:** `.pdf`, `.docx`, `.doc`, `.xlsx`, `.xls`, `.pptx`, `.ppt`, `.txt`, `.md`, `.png`, `.jpg`, `.jpeg`

### `agent_sessions`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `channel_id` | TEXT | workspace key |
| `channel_type` | TEXT | |
| `task_type` | TEXT | `proposal` (V1 only) |
| `status` | TEXT | session lifecycle state |
| `clarification_round` | INT | increments per clarification turn |
| `proposal_version` | INT | current proposal version number |
| `thread_id` | TEXT | active Slack thread |
| `pending_message` | TEXT | user message queued while files processing |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |

V1: one active session per channel (status not in `idle` / `failed`).

### `feedback_instructions`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `channel_id` | TEXT | workspace key |
| `text` | TEXT | free-text instruction from team |
| `active` | BOOL | `false` once superseded |
| `applied_to_version` | INT | proposal version it was applied to |
| `created_at` | TIMESTAMPTZ | |

---

## File Lifecycle

```
PENDING
  │  parse_worker picks up
  ▼
EXTRACTING
  │  parser writes clean/
  ▼
EXTRACTED
  │  embedder chunks + indexes
  ▼
EMBEDDING
  │  embedding complete
  ▼
READY  ← file is now available to agents
  │
  ├── FAILED      (on any pipeline exception)
  └── UNSUPPORTED (file type not in supported set)
```

---

## Session Lifecycle

```
IDLE → PROCESSING_INPUTS → CLARIFYING ↔ CLARIFYING
                                      ↓
                                   DRAFTING
                                      ↓
                               PROPOSAL_READY ↔ UPDATING
```

Any state → IDLE on `@bot reset`.
Any state → FAILED on unrecoverable error.

---

## Vector DB — ChromaDB

Two collections:

| Collection | Purpose |
|---|---|
| `workspace_documents` | Chunks from files uploaded by the team to each channel |
| `common_knowledge` | Chunks from files in `common/` — shared across all channels |

### Chunk metadata fields

| Field | Example | Purpose |
|---|---|---|
| `channel_id` | `C08XXXXXXX` | Always injected into queries — workspace boundary |
| `file_id` | UUID | FK → `files.id` |
| `file_name` | `requirements.pdf` | Human-readable source |
| `file_type` | `pdf` | Type filtering |
| `chunk_index` | `3` | Position in document |
| `chunk_total` | `12` | Total chunks for this file |
| `is_requirement` | `"true"` | Fast filter for requirement files |
| `created_at` | ISO 8601 | When indexed |

Every query always includes `where={"channel_id": channel_id}` — injected by `VectorRepo`, not the caller.

Chunks removed: `VectorRepo.delete_file_chunks(file_id)` called when `is_deleted = true`.

---

## Filesystem Layout

```
workspaces/
└── {channel-name}/              # one per channel
    ├── workspace.json           # channel_id, channel_name, workspace_name
    ├── raw/                     # original uploaded files (timestamped filenames)
    │   └── requirements__20260404T083000Z.pdf
    ├── clean/                   # parsed Markdown
    │   ├── requirements__20260404T083000Z.md
    │   └── requirements.md      # canonical requirement file (agent-maintained)
    └── output/                  # proposal versions
        ├── proposal_v1.md
        ├── proposal_v2.md
        └── proposal_latest.md   # always the current version

common/
├── requirements/check_list.md
├── technical/
├── member_profiles/
└── company_progress/

chromadb/
├── workspace_documents/
└── common_knowledge/
```

### File versioning

When the same filename is re-uploaded:
- a new raw file is saved with a timestamp suffix
- the previous `files` record has `is_latest` set to `false`
- the new record becomes `is_latest = true`
- the latest processed version is used for retrieval

### Context loading strategy

| Source | Load method |
|---|---|
| `clean/requirements.md` | Always direct load — never truncated |
| Active feedback instructions | Always direct load |
| Member profiles, checklists | Direct load (small, high priority) |
| Large workspace documents | Vector retrieval (top-k = 10) |
| Common knowledge | Vector retrieval (top-k = 5) |

Truncation order when over context budget:
1. Common knowledge chunks
2. Workspace document chunks
3. Summarise long clarification history
4. Never truncate `requirements.md` or active feedback

---

## LLM Model Assignments

| Task | Model |
|---|---|
| Clarification analysis | Main reasoning model (Claude Opus) |
| Proposal generation | Main reasoning model (Claude Opus) |
| Proposal update | Main reasoning model (Claude Opus) |
| File summarization | Fast model (Claude Haiku) |
| Intent classification / routing | Fast model (Claude Haiku) |
| Embeddings | `text-embedding-3-small` |
