# Operations

---

## Bot Command Interface

All commands are sent as `@bot` mentions in the channel.
Bot replies are threaded under the triggering message.

| Command | Example | Behaviour |
|---|---|---|
| Trigger proposal | `@bot Here is the requirement: [text or file]` | Starts proposal workflow |
| Check status | `@bot status` | Returns session state + pending file jobs |
| List documents | `@bot what documents do you have?` | Lists processed files in workspace |
| Apply feedback | `@bot add a data migration section` | Updates proposal per instruction |
| Reset session | `@bot reset` | Clears current session; keeps files |
| Show proposal | `@bot show proposal` | Re-posts `proposal_latest.md` |
| Force reprocess | `@bot reprocess [filename]` | Re-runs pipeline on a specific file |

### Bot Response Formats

**Processing acknowledgment** (file received, not yet ready):
```
I received your request. I'll continue in this thread after the related files are ready.
```

**Clarifying questions:**
```
I need a few more details before I can write the proposal:

1. Timeline — What is the expected delivery date?
2. Budget — Is there a budget ceiling?

Please reply in this thread and I will continue.
```

**Proposal posted:**
```
Here is the proposal draft (v1):
[attachment: proposal_v1.md]

Key assumptions made:
- Estimated 50 concurrent users
- 3-month timeline assumed

Let me know what you want to change.
```

**Update acknowledgment:**
```
Got it. I am updating the proposal based on your instruction and will reply in this thread.
```

---

## Configuration

All config is set via environment variables. Copy `.env.example` to `.env`.

```env
# ── Channels ──────────────────────────────────────────────
ENABLED_CHANNELS=slack              # comma-separated: slack,teams,discord

# ── Slack ─────────────────────────────────────────────────
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
SLACK_SIGNING_SECRET=...

# ── LLM ───────────────────────────────────────────────────
ANTHROPIC_API_KEY=sk-ant-...
MAIN_MODEL=claude-opus-4-6
FAST_MODEL=claude-haiku-4-5-20251001

# ── Embeddings ────────────────────────────────────────────
OPENAI_API_KEY=sk-...
EMBEDDING_MODEL=text-embedding-3-small

# ── PostgreSQL ────────────────────────────────────────────
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=proposal_agent
POSTGRES_USER=agent
POSTGRES_PASSWORD=secret

# ── ChromaDB ──────────────────────────────────────────────
CHROMA_PERSIST_DIR=./chromadb

# ── Paths ─────────────────────────────────────────────────
WORKSPACES_DIR=./workspaces
COMMON_DIR=./common

# ── Agent tuning ──────────────────────────────────────────
MAX_FILE_SIZE_MB=50
MAX_CLARIFICATION_ROUNDS=5
MAX_CONTEXT_TOKENS=10000
TOP_K_WORKSPACE=10
TOP_K_COMMON=5

# ── API ───────────────────────────────────────────────────
API_HOST=0.0.0.0
API_PORT=8000
```

### Key config notes

- `ENABLED_CHANNELS` controls which adapters are built at startup. Unknown or unsupported channels are skipped with a warning log.
- Slack credentials must all be non-empty for `SlackAdapter.is_supported()` to return `True`.
- The PostgreSQL database is created automatically by `init_db()` at startup — no manual migration needed for V1.

---

## Running Locally

```bash
# 1. start postgres
docker-compose up -d postgres

# 2. install dependencies
pip install -r requirements.txt

# 3. run the app
PYTHONPATH=src python src/main.py
```

### Docker

```bash
docker-compose up --build
```

The `agent` service waits for postgres health before starting.

---

## Internal API

FastAPI app, accessible at `http://localhost:8000`.

| Endpoint | Method | Description |
|---|---|---|
| `/api/health` | GET | Liveness check |
| `/api/workspaces` | GET | List all provisioned workspaces |
| `/api/workspaces/{id}/files` | GET | List ready files for a channel |
| `/api/workspaces/{id}/session` | GET | Current session state |
| `/api/workspaces/{id}/reset` | POST | Reset active session |

---

## Error Handling

### Processing Pipeline

| Error | Behaviour |
|---|---|
| File download fails | Retry 3× exponential backoff; notify channel on final failure |
| Unsupported file type | Saved to `raw/`, marked `status: unsupported`; simple Slack notice if used |
| Parser exception | Mark `status: failed`; log error; post failure message |
| AI summarisation fails | Skip summary; file still marked `ready` |
| Embedding fails | Retry 3×; file saved to `clean/` even if unindexed |

### Agent Errors

| Error | Behaviour |
|---|---|
| LLM API timeout / error | Retry 2×; post short failure message |
| No usable workspace docs | Proceed with requirement text only; note limited context |
| Clarification max rounds reached | Draft with explicit assumptions; warn the user |
| Conflicting feedback instructions | Ask for clarification before updating |

### Retry policy (LLM calls)

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
)
async def call_llm(prompt): ...
```

---

## Non-Functional Requirements

| Category | Requirement |
|---|---|
| **Response time** | Slack ACK ≤ 3 seconds |
| **Processing latency** | Single PDF (≤ 20 pages) → ready within 60 seconds |
| **Proposal generation** | Initial draft within 120 seconds of trigger |
| **Concurrency** | ≥ 10 simultaneous active channels |
| **Data isolation** | Strict per-channel isolation via `channel_id`; no data crosses boundaries |
| **Durability** | Raw files and proposals persisted to disk immediately |
| **Versioning** | Same filename re-uploaded → new version; latest used for retrieval |
| **Observability** | Structured logs per component; job status via `@bot status` |
| **Security** | Socket Mode only; no public Slack endpoint; credentials in env vars only |
| **Common knowledge** | `common/` is read-only to all agents |
| **Portability** | All workspace data in `./workspaces/`; shared knowledge in `./common/` |
