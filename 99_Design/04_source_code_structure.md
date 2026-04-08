# Source Code Structure

All application code lives under `src/`. The project root holds infrastructure files only.

---

## Project Root

```
proposal-agent/
├── src/                    # all application code (PYTHONPATH=src)
├── common/                 # shared knowledge base (read-only to agents)
│   ├── requirements/
│   ├── technical/
│   ├── member_profiles/
│   └── company_progress/
├── workspaces/             # runtime — one folder per channel (gitignored)
├── chromadb/               # runtime — vector store persistence (gitignored)
├── docs/                   # this documentation set
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## `src/` Tree

```
src/
│
├── main.py                          # entry point: init DB, start adapters + worker, run FastAPI
├── config.py                        # pydantic-settings: all env vars + derived properties
│
├── channels/                        # channel adapter layer
│   ├── base.py                      # ChannelAdapter ABC, InboundEvent, FileRef dataclasses
│   ├── registry.py                  # build_adapter(), build_all() — loads adapters by name
│   ├── dispatcher.py                # save message → provision workspace → call orchestration
│   ├── slack/
│   │   ├── adapter.py               # Bolt Socket Mode; registers all event handlers
│   │   └── normalizer.py            # Slack event dicts → InboundEvent
│   ├── teams/                       # stub — not yet supported
│   │   ├── adapter.py
│   │   └── normalizer.py
│   └── discord/                     # stub — not yet supported
│       ├── adapter.py
│       └── normalizer.py
│
├── orchestration/                   # system-level flow control (not business reasoning)
│   └── service.py                   # handle_user_event, handle_file_event, on_file_ready
│
├── processing/                      # deterministic document processing (no LLM decisions)
│   ├── parser.py                    # raw file → Markdown (markitdown → docling → fallback)
│   ├── embedder.py                  # Markdown → chunks → ChromaDB
│   ├── summarizer.py                # optional LLM summary of a clean file
│   └── pipeline.py                  # orchestrate: parse → embed → summarize → update DB
│
├── workers/                         # background asyncio workers
│   └── parse_worker.py              # queue consumer → pipeline.run() → on_ready callbacks
│
├── agents/                          # CrewAI agent runtime
│   ├── base.py                      # BaseAgent ABC + send_fn factory
│   ├── registry.py                  # lazy import registry: name → agent class
│   └── manager/
│       └── agent.py                 # ManagerAgent: builds Crew, decides clarify vs. draft
│
├── skills/                          # skill abstraction: SKILL.md prompt + tool subset
│   ├── base.py                      # BaseSkill ABC
│   ├── registry.py                  # get_skill(name, channel_id, **kwargs)
│   ├── clarification/
│   │   ├── skill.py
│   │   └── SKILL.md
│   ├── proposal/
│   │   ├── skill.py
│   │   └── SKILL.md
│   └── feedback/
│       ├── skill.py
│       └── SKILL.md
│
├── tools/                           # shared LangChain @tool functions (factory pattern)
│   ├── messaging/
│   │   └── send_message.py          # make_send_message_tool(send_fn)
│   ├── files/
│   │   ├── list_files.py            # make_list_files_tool(channel_id)
│   │   └── read_file.py             # make_read_file_tool(channel_id)
│   ├── memory/
│   │   ├── search_memory.py         # make_search_memory_tool(channel_id)
│   │   └── get_history.py           # make_get_history_tool(channel_id)
│   └── search/
│       └── web_search.py            # stub — integrate Tavily/SerpAPI here
│
├── workspace/                       # workspace lifecycle + file intake
│   ├── manager.py                   # provision(), get(), list_all()
│   ├── schema.py                    # WorkspaceSchema dataclass (root, raw, clean, output paths)
│   └── files/
│       ├── collector.py             # download file from channel → raw/ → insert DB record
│       └── versioning.py            # save_proposal(), proposal_latest_path()
│
├── storage/                         # persistence layer
│   ├── db.py                        # async engine, get_session(), init_db()
│   ├── models.py                    # SQLModel tables: Message, File, AgentSession, FeedbackInstruction
│   ├── messages_repo.py             # insert(), get_recent(), get_thread()
│   ├── files_repo.py                # insert(), update_status(), get_ready_files(), mark_ready()
│   ├── sessions_repo.py             # SessionsRepo + FeedbackRepo
│   └── vector_repo.py               # ChromaDB wrapper; always injects channel_id filter
│
├── runtime/                         # LLM + observability helpers
│   ├── llm.py                       # get_llm(), main_llm(), fast_llm() — cached ChatAnthropic
│   └── tracing.py                   # logging / observability hooks
│
└── api/                             # internal HTTP API
    └── routes.py                    # /health, /workspaces, /session status, /reset
```

---

## Key Conventions

- **`PYTHONPATH=src`** — all imports are relative to `src/`, e.g. `from config import settings`
- **Factory pattern for tools** — `make_*_tool(channel_id)` binds the workspace context at call time; agents cannot bypass the `channel_id` filter
- **Lazy imports** — `agents/registry.py` and `orchestration/service.py` use `importlib` to avoid circular imports at module load time
- **Skills are project-level, not framework-level** — `skills/` is our own abstraction on top of CrewAI, not a CrewAI feature
- **Stubs are explicit** — Teams and Discord adapters return `is_supported() = False` with a clear message
