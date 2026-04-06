# Oh-My-Codex (OMX) — GuardRails

## Context

**Oh-My-Codex (OMX)** is a workflow layer that sits on top of the Codex CLI. It adds better prompts, structured workflows, and role-based agent guidance — while keeping Codex as the actual execution engine.

Think of OMX as a **set of instructions and rules** given to the Codex agent to shape how it behaves.

---

## What Are GuardRails in OMX?

OMX does **not have runtime guardrails**.

Instead, it uses **prompt-based constraints** — safety rules written in plain text that the agent reads and is supposed to follow.

```
Agent receives prompt with constraints
        ↓
Agent reads: "Do not do X. Always check Y first."
        ↓
Agent follows rules (based on LLM understanding, not code enforcement)
```

This is **behavioral guidance**, not technical enforcement.

---

## Why Does This Matter?

| Technical GuardRail | Prompt-Based Constraint (OMX approach) |
|--------------------|-----------------------------------------|
| Code checks the action | LLM interprets the instruction |
| Always enforced | Depends on model following instructions |
| Hard stop / block | Soft guidance / suggestion |
| No bypass possible | Can drift with complex prompts |

OMX keeps things simple and flexible. The actual safety enforcement is **delegated to Codex's Guardian** (see `01_codex_guardrails.md`).

---

## Main Components (3 Parts)

```mermaid
graph TD
    A[AGENTS.md Template] --> B[Role Prompts]
    B --> C[Executor Constraints]
    B --> D[Planner Constraints]
    B --> E[Safety Constraints]
    C --> F[Codex Agent]
    D --> F
    E --> F
    F --> G[Codex Guardian]
    G --> H[Actual Execution]

    style G fill:#3b82f6,color:#fff
    style H fill:#22c55e,color:#fff
```

### 1. AGENTS.md Template
A markdown file given to the agent as its operating guide. Defines:
- What the agent is allowed to do
- What it should verify before acting
- Behavioral constraints for each role

### 2. Role-Specific Constraints
Different agent roles get different constraint levels:

| Role | Key Constraint |
|------|---------------|
| **Executor** | Treat newer user instructions as local overrides to earlier plans |
| **Planner** | Preserve non-conflicting constraints from previous steps |
| **Reviewer** | Validate output before signing off |

### 3. Guidance Schema (`docs/guidance-schema.md`)
Defines the structure of how guidance/constraints are written and passed to agents. Includes a "safety constraints" section per agent.

---

## How Constraints Flow

```mermaid
sequenceDiagram
    participant User
    participant OMX
    participant Codex as "Codex Agent"
    participant Guardian

    User->>OMX: Start task
    OMX->>Codex: Task + AGENTS.md (with constraints)
    Codex->>Codex: Read constraints: "don't delete outside /tmp"
    Codex->>Guardian: Attempt: rm /etc/config
    Guardian->>Guardian: Risk score = 95
    Guardian-->>Codex: BLOCKED
    Codex-->>User: Cannot do this — blocked by safety policy
```

Note: OMX's prompt constraints guide the agent's **intent**. The Codex Guardian handles **enforcement**.

---

## What OMX Constraints Look Like

Example from executor constraints:

```markdown
## Safety Constraints
- Never overwrite files outside the project directory without explicit user confirmation
- Always show a diff before applying changes to existing files
- If a command could affect system state, pause and confirm with the user
- Treat user instructions in later messages as overrides to earlier plans
```

These are **plain English rules** embedded in the agent's system prompt.

---

## OMX + Codex: Two Layers

```mermaid
graph LR
    subgraph OMX_LAYER ["OMX Layer (Behavioral)"]
        P1[Prompt Constraints]
        P2[Role Guidance]
        P3[Workflow Structure]
    end

    subgraph CODEX_LAYER ["Codex Layer (Technical)"]
        G1[Guardian Risk Scorer]
        G2[Evidence Collector]
        G3[Approval System]
    end

    OMX_LAYER --> CODEX_LAYER
    CODEX_LAYER --> EXEC[Execution]

    style OMX_LAYER fill:#8b5cf6,color:#fff
    style CODEX_LAYER fill:#3b82f6,color:#fff
    style EXEC fill:#22c55e,color:#fff
```

---

## Summary

- **What:** Prompt-based behavioral constraints, not runtime guardrails
- **Why it matters:** OMX shapes agent *intent*; Codex Guardian handles *enforcement*
- **Components:** AGENTS.md Template → Role Prompts (Executor/Planner) → Guidance Schema
- **Actual safety:** Delegated to Codex's Guardian module
- **Built in:** Markdown files and prompt templates (`oh-my-codex/docs/`, `oh-my-codex/prompts/`)
