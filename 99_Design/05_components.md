# Components

---

## 1. Channel Layer

**Files:** `src/channels/`

### Responsibility
- Connect to each platform and maintain the connection
- Convert platform-specific event payloads into a single `InboundEvent`
- Send messages back via a common `send_message()` interface

### Key types

```python
@dataclass
class FileRef:
    file_id: str; name: str; url: str; size: int; mime_type: str

@dataclass
class InboundEvent:
    channel_id: str; channel_name: str; channel_type: str
    user_id: str; text: str; thread_id: str | None
    platform_ts: str; files: list[FileRef]; raw: dict

class ChannelAdapter(ABC):
    def is_supported() -> bool
    def not_supported_reason() -> str
    async def start() -> None
    async def stop() -> None
    async def send_message(channel_id, text, thread_id) -> None
```

### Slack Adapter specifics
- Uses `slack_bolt` AsyncApp + Socket Mode (no public HTTP endpoint)
- All heavy handlers use `asyncio.create_task()` to ACK Slack immediately
- Required Slack OAuth scopes: `channels:history`, `groups:history`, `app_mentions:read`, `files:read`
- Bot is added to a channel before any workflow can start

### What it must NOT do
- Contain business logic
- Decide what the agent should do
- Access the database directly (except file download in `FileCollector`)

---

## 2. Orchestration

**File:** `src/orchestration/service.py`

### Responsibility
- Manage the session lifecycle for each channel
- Route inbound events to the right next step based on session state
- Enqueue files for processing and listen for completion callbacks
- Invoke the Manager Agent when conditions are met

### Key methods

| Method | What it does |
|---|---|
| `handle_user_event(event, ws)` | Route based on current session status |
| `handle_file_event(event, ws, file_id, name)` | Enqueue file to parse_worker |
| `_on_file_ready(file_id, channel_id)` | Callback from worker; resume if a user message is waiting |
| `_start_new_session()` | Create session, check for pending files, or invoke agent |
| `_handle_feedback()` | Save feedback, set UPDATING, invoke agent |
| `_handle_clarification_answer()` | Increment round, set DRAFTING, invoke agent |
| `_invoke_manager_agent()` | Lazy-import and call `ManagerAgent.run()` as asyncio task |

### What it must NOT do
- Contain reasoning or proposal logic
- Know anything about Slack or any specific platform
- Decide whether clarification is needed (that is the Manager Agent's job)

---

## 3. Processing Pipeline

**Files:** `src/processing/`, `src/workers/`

### Responsibility
- Consume file jobs from an asyncio queue
- Convert raw files to clean Markdown
- Chunk and embed into ChromaDB with `channel_id` metadata
- Generate an optional LLM summary
- Update file status in PostgreSQL at every stage

### Pipeline stages

```
raw file
  └─► parser.py       markitdown CLI → docling → fallback text read
  └─► embedder.py     chunk (1000 chars, 150 overlap) → VectorRepo.add_chunks()
  └─► summarizer.py   fast_llm() → 2–3 sentence summary (optional)
  └─► FilesRepo       status: pending → extracting → extracted → embedding → ready
                      (→ failed on any exception)
```

### File status enum

`pending → extracting → extracted → embedding → ready → failed | unsupported`

### What it must NOT do
- Make planning or reasoning decisions
- Call the agent layer
- Skip the status update steps (orchestration depends on them)

---

## 4. Agent Layer

**Files:** `src/agents/`

The agent layer uses **CrewAI** (Agents, Tasks, Crews) with `langchain-anthropic` as the LLM provider.

### Manager Agent

The single entry point for all reasoning. Its job:

1. Read context (conversation history, workspace files, session state)
2. Decide: does the request need more information → clarify, or is there enough → draft/revise?
3. Delegate to the right child skill using its tools

The Manager Agent is the **only component that decides whether file context is needed**.
It uses `list_files`, `read_file`, and `search_memory` tools to gather context before deciding.

### Child Agents / Skills used by Manager

| Agent role | When invoked | Key action |
|---|---|---|
| Clarification | Critical info is missing | Post one message with all missing items as numbered questions |
| Proposal | Enough context available | Draft or revise `proposal_vN.md` |
| Feedback | Session is PROPOSAL_READY + feedback received | Interpret revision vs. approval; drive next step |

### Agent Registry

Agents are loaded lazily via `agents/registry.py` to avoid circular imports:

```python
get_agent("manager")  # imports agents.manager on first call
```

### What agents must NOT do
- Access the database directly (use tools)
- Know the current channel platform
- Write to `common/` (read-only)

---

## 5. Skills and Tools

### Skills

A skill is a **project-level abstraction** (not a CrewAI built-in) that wraps:
- A `SKILL.md` instruction prompt (the system prompt for that capability)
- A curated subset of shared tools, bound to the active `channel_id`

Skills are instantiated per request with `channel_id` and an optional `send_fn`:

```python
skill = get_skill("proposal", channel_id=channel_id, send_fn=send_fn, output_dir=..., version=...)
tools = skill.get_tools()
instruction = skill.get_instruction()  # reads SKILL.md
```

Current skills: `clarification`, `proposal`, `feedback`

### Tools

All tools are factory functions that close over `channel_id`:

| Tool factory | What it does |
|---|---|
| `make_send_message_tool(send_fn)` | Send a reply to the channel |
| `make_list_files_tool(channel_id)` | List `ready` files in the workspace |
| `make_read_file_tool(channel_id)` | Read clean Markdown of a file by ID |
| `make_search_memory_tool(channel_id)` | Semantic search over workspace vector store |
| `make_get_history_tool(channel_id)` | Get recent conversation messages |
| `web_search` | Stub — integrate Tavily/SerpAPI for production |

**`channel_id` is injected at tool construction time.** The agent cannot bypass the workspace filter.

### Tool Sharing Map

| Skill | send_message | list_files | read_file | search_memory | get_history |
|---|---|---|---|---|---|
| Clarification | ✓ | ✓ | | | ✓ |
| Proposal | ✓ | ✓ | ✓ | ✓ | ✓ |
| Feedback | ✓ | | | | ✓ |

---

## 6. Workspace

**Files:** `src/workspace/`

### Responsibility
- Provision a directory structure for each new channel (idempotent)
- Maintain a `workspace.json` metadata file as the lookup key
- Provide typed path properties (`raw`, `clean`, `output`)
- Handle file downloads from the channel platform

### WorkspaceSchema

```python
@dataclass
class WorkspaceSchema:
    root: Path
    channel_id: str
    channel_name: str

    @property raw    -> root / "raw"
    @property clean  -> root / "clean"
    @property output -> root / "output"
```

### Naming rule

Channel name → sanitise (lowercase, `[a-z0-9-_]` only, max 80 chars) → directory name.
On collision, append `_{channel_id[-6:]}`.

### Common Knowledge Base

`common/` lives outside all workspaces, is managed manually by the team, and is read-only to all agents.

```
common/
├── requirements/check_list.md
├── technical/          # tech standards, pricing, SLA templates
├── member_profiles/    # team member skills and availability
└── company_progress/   # active project status
```

Common files are indexed into `common_knowledge` ChromaDB collection on change.
