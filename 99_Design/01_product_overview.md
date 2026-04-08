# Product Overview

## Purpose

An AI agent system that manages the **proposal workflow** for client projects.
The bot lives in a channel (Slack today, Teams/Discord in future), collects uploaded files, understands requirements, asks clarifying questions, generates a proposal draft, and applies team feedback to revise it.

---

## V1 Scope

**In scope:**

- Collect and process files uploaded to the channel
- Clarify missing requirement information via channel thread
- Generate a structured proposal draft
- Apply feedback instructions to revise an existing draft
- Support multiple concurrent channels (each = one project workspace)
- Slack integration (Socket Mode, no public endpoint required)

**Out of scope for V1:**

- Teams and Discord (adapters stubbed, not active)
- Sample data analysis
- Solution design generation
- Error / log analysis
- Export to external systems (Google Docs, Confluence, etc.)
- Direct message (DM) workflows
- Multiple simultaneous proposal sessions per channel

---

## Core Principles

| Principle | Meaning |
|---|---|
| One channel = one workspace | All state, files, and agent context are scoped to the channel |
| File upload = asset registration | Uploading a file never auto-triggers a proposal |
| `@bot` mention = action request | The proposal workflow starts only when the user explicitly asks |
| `requirements.md` is the canonical truth | The agent writes and maintains one structured requirement file per workspace |
| Clarification happens in Slack thread | No Excel handoffs; questions and answers stay in the thread |
| Store history, load selectively | Channel history is captured; not all of it is sent to the LLM on every call |
| Common knowledge is read-only | Agents read `common/` but never write to it |

---

## Glossary

| Term | Definition |
|---|---|
| **Workspace** | Isolated directory + database state for one channel/project |
| **Channel ID** | Platform identifier for a channel; used as workspace isolation key |
| **Raw file** | Original file as uploaded by the team |
| **Clean document** | Parsed Markdown version of a raw file, ready for LLM use |
| **`requirements.md`** | Agent-maintained structured summary of the current requirement |
| **Proposal** | Output document drafted by the agent for the client |
| **Clarification loop** | Thread-based back-and-forth where the agent asks questions and the team replies |
| **Feedback instruction** | Free-text instruction from the team that drives a proposal revision |
| **Task session** | Active workflow state for one channel; V1 is proposal-focused |
| **Common knowledge** | Shared Markdown files (`common/`) available to all workspaces |
| **Processing pipeline** | Background worker that converts raw files to clean Markdown + embeddings |
| **Skill** | A named capability: a `SKILL.md` instruction prompt + a subset of shared tools |
| **Tool** | A callable LangChain function reused across multiple skills and agents |
| **Channel adapter** | Platform-specific connector (Slack, Teams, Discord) behind a common interface |

---

## Supported User Intents (V1)

| Intent | Example | Status |
|---|---|---|
| Propose | `@bot create a proposal based on these files` | Supported |
| Clarify | Reply in active clarification thread | Supported |
| Feedback | `@bot add a data migration section` | Supported |
| Status | `@bot status` | Supported |
| Question | `@bot what files do you have?` | Supported |
| Analyze data | `@bot analyze this sample` | Not supported — future |
| Design | `@bot create a solution design` | Not supported — future |
| Error analysis | `@bot check these logs` | Not supported — future |
