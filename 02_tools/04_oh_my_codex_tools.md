# oh-my-codex (OMX) Tools

> Note: This file covers the **oh-my-codex** project (`lib/oh-my-codex/`).

## What is oh-my-codex?

oh-my-codex (OMX) is a workflow layer built on top of OpenAI Codex CLI.
Codex is the execution engine. OMX adds a standard workflow on top of it.

Without OMX, Codex sessions start with no structure — no clarification step, no planning, no verification.
OMX fixes this by providing reusable **skills** that guide work through a consistent pipeline:

```
Clarify → Plan → Execute → Verify
```

All state and artifacts are saved in `.omx/` inside the project directory.

---

## What is a Skill?

A skill is a reusable workflow instruction file.
Each skill tells the agent what to do, when to do it, and how to verify it's done.

Every skill is stored in `skills/{skill-name}/SKILL.md` and registered in a central catalog (`src/catalog/manifest.json`).

A skill file contains:
- **Purpose** — what this skill does
- **Use When** — when to invoke it
- **Do Not Use When** — when to avoid it
- **Steps** — the workflow to follow
- **Tool Usage** — which tools or subagents to call

---

## How Many Skills Exist?

OMX defines **36 skills** organized into 5 categories:

### 1. Execution (4 skills)
Run work and produce results.

| Skill | Purpose |
|-------|---------|
| `$ralph` | Persistent loop — keeps working until the task is verified complete |
| `$autopilot` | Full autonomous lifecycle: clarify → plan → build → QA |
| `$ultrawork` | Parallel execution with background operations |
| `$team` | Coordinate multiple agents in parallel via tmux workers |

### 2. Planning (3 skills)
Clarify scope and build consensus before coding.

| Skill | Purpose |
|-------|---------|
| `$deep-interview` | Ask clarifying questions, score ambiguity |
| `$ralplan` | Build a plan with Planner + Architect + Critic feedback loop |
| `$plan` | General planning mode |

### 3. Shortcuts (15 skills)
Single-purpose agent shortcuts for specific tasks.

| Skill | Purpose |
|-------|---------|
| `$code-review` | Architecture review |
| `$security-review` | Security assessment |
| `$tdd` | Test-driven development |
| `$web-clone` | Extract and recreate a UI from a URL |
| `$ask-claude` / `$ask-gemini` | Query external AI models |
| `$ai-slop-cleaner` | Clean up AI-generated bloat |
| `$visual-verdict` | Vision-based evaluation |
| + 8 more | Git, build fixes, frontend, etc. |

### 4. Utility (9 skills)
Session and project management.

| Skill | Purpose |
|-------|---------|
| `$cancel` | Clean exit with state cleanup |
| `$doctor` | Verify OMX installation |
| `$help` | Browse available skills |
| `$hud --watch` | Real-time status dashboard |
| `$trace` | Debug session history |
| `$configure-notifications` | Set up Slack/Discord/Telegram alerts |

### 5. Internal (1 skill)
- `$worker` — bootstrap for tmux team workers (not called by users directly)

---

## How Skills Work Together

Skills are designed to chain together in sequence:

```
$deep-interview "add user authentication"
    ↓ produces: .omx/specs/deep-interview-{slug}.md

$ralplan "review and approve"
    ↓ consumes: spec file
    ↓ produces: .omx/plans/prd-*.md

$ralph "implement the approved plan"
    ↓ consumes: plan file
    ↓ produces: verified working code
```

Each skill knows what it needs as input and what it produces as output.
This handoff contract makes the pipeline predictable.

---

## State Storage

All artifacts are saved in `.omx/`:

| Folder | Contents |
|--------|---------|
| `specs/` | Clarification outputs |
| `plans/` | Architecture and PRD files |
| `interviews/` | Deep-interview transcripts |
| `context/` | Session snapshots |
| `state/` | Current mode (ralph, team, etc.) |
| `logs/` | Execution history |

---

## Key Components

| Component | Role |
|-----------|------|
| **Skill** | Self-contained workflow instruction |
| **Agent Role** | Specialist prompt (executor, architect, reviewer, etc.) |
| **Catalog** | Indexes all 36 skills with status and metadata |
| **State Manager** | Persists progress across interruptions |
| **Team Runtime** | tmux-based parallel worker coordination |

---

## Summary

- OMX adds workflow structure on top of Codex CLI
- Tools = skills (36 total across 5 categories)
- Three canonical stages: `$deep-interview` → `$ralplan` → `$ralph`
- Skills chain together through file-based handoffs
- All state saved in `.omx/` for resumability
