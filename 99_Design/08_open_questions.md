# Open Questions

---

## Product / Workflow

| # | Question | Impact |
|---|---|---|
| 1 | Who can send feedback instructions — any channel member or specific roles only? | Security, Slack permission scopes |
| 2 | Should proposals be posted as Slack messages, file attachments, or both? | UX, Slack API limits |
| 3 | Should the bot support multiple simultaneous active sessions per channel in a future version? | Session model complexity |
| 4 | What is the UX for `@bot reset` — should it ask for confirmation before clearing the session? | UX |
| 5 | Should the bot notify the channel proactively when a file finishes processing, or only when there is a pending user request? | UX, noise level |

---

## Architecture / Storage

| # | Question | Impact |
|---|---|---|
| 6 | Is ChromaDB sufficient for production load, or should Qdrant be evaluated? | Infrastructure, migration effort |
| 7 | Should `common/` be indexed automatically on file change, or on a scheduled job, or manually triggered? | Operational complexity |
| 8 | Should Alembic be added for schema migrations now, or is `init_db()` auto-create acceptable past V1? | DB operations |
| 9 | What is the retention policy for old proposal versions and raw files? | Disk usage |

---

## Integrations

| # | Question | Impact |
|---|---|---|
| 10 | Is there a need to export final proposals to Google Docs, Confluence, or another system? | Integration scope |
| 11 | Should the web search tool (`tools/search/web_search.py`) be wired to Tavily or SerpAPI in V1, or remain a stub? | Research capability |
| 12 | Teams and Discord adapters are stubs. What is the priority and timeline for activating them? | Channel roadmap |

---

## Future Scope

| # | Question | Impact |
|---|---|---|
| 13 | How should future task types (data analysis, solution design, error analysis) be introduced into the session model and dispatcher? | Architecture, session state machine extension |
| 14 | Should the skills layer evolve to use a YAML/JSON registry rather than Python registry files? | Developer experience |
| 15 | Should there be a way for the team to browse or download past proposals from a web UI, not just via Slack? | Product scope |
