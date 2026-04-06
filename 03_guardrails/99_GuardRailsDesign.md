# GuardRails Design — Overall Guide

## Context

This document synthesizes guardrails patterns from 7 real agent frameworks (Codex, CrewAI, Hermes, OpenClaw, LangChain, Oh-My-Codex, SuperMemory).

It answers:
- **What** types of guardrails exist
- **Why** we need them
- **How** each type works
- **How to think** when designing guardrails for your own system

---

## The Core Problem

AI agents are given **autonomy** to take actions. But autonomy without limits leads to mistakes — and some mistakes cannot be undone.

```mermaid
graph LR
    subgraph WITHOUT ["Without GuardRails"]
        A1[Agent runs freely] --> A2[Makes a mistake]
        A2 --> A3[Data deleted / Server down / Bad output]
        A3 --> A4[Cannot recover]
    end

    subgraph WITH ["With GuardRails"]
        B1[Agent runs freely] --> B2[Guardrail checks action]
        B2 -->|Safe| B3[Runs OK]
        B2 -->|Risky| B4[Blocked or ask human]
    end

    style A4 fill:#ef4444,color:#fff
    style B3 fill:#22c55e,color:#fff
    style B4 fill:#f59e0b,color:#fff
```

The goal of guardrails: **let agents be useful without letting them be dangerous**.

---

## Why Do We Need GuardRails?

Three root causes drive the need:

### 1. Agents Make Mistakes
LLMs hallucinate. They misread instructions. They take shortcuts. Without guardrails, mistakes reach the real world.

### 2. Some Actions Are Irreversible
Deleting a database, sending an email, pushing to production — once done, they cannot be undone. Guardrails create a moment to pause before irreversible actions.

### 3. Pipelines Amplify Errors
In multi-agent systems, one agent's bad output becomes the next agent's bad input. Errors compound. Guardrails are the quality gates that stop the chain reaction.

```mermaid
graph LR
    A1[Agent 1 hallucinates a fact] --> A2[Agent 2 uses that fact]
    A2 --> A3[Agent 3 publishes it]
    A3 --> A4[Wrong info goes live]

    G1[Agent 1 hallucinates a fact] --> G2[Guardrail catches it]
    G2 --> G3[Agent 1 retries with feedback]
    G3 --> G4[Correct output continues]

    style A4 fill:#ef4444,color:#fff
    style G4 fill:#22c55e,color:#fff
```

---

## The 4 Types of GuardRails

All guardrails in the 7 libraries fall into one of four types.

```mermaid
graph TD
    GR[GuardRails] --> T1[Type 1: Action GuardRails]
    GR --> T2[Type 2: Output GuardRails]
    GR --> T3[Type 3: Behavioral Constraints]
    GR --> T4[Type 4: Access Control]

    T1 --> T1A["Check BEFORE the action runs\nCodex Guardian, Hermes, OpenClaw"]
    T2 --> T2A["Check AFTER the agent produces output\nCrewAI validators, LLM Judge"]
    T3 --> T3A["Shape agent INTENT via instructions\nOMX prompt constraints"]
    T4 --> T4A["Control WHO can do WHAT\nOAuth, API keys, allowlists"]

    style T1 fill:#ef4444,color:#fff
    style T2 fill:#3b82f6,color:#fff
    style T3 fill:#8b5cf6,color:#fff
    style T4 fill:#f59e0b,color:#000
```

---

### Type 1 — Action GuardRails (Pre-Execution)

**What:** Check every action the agent wants to take, BEFORE it runs.

**When to use:** When your agent can take actions in the real world — run code, delete files, call APIs, modify databases.

**How it works:**

```mermaid
flowchart LR
    A[Agent wants to act] --> B{GuardRail check}
    B -->|Low risk| C[Run immediately]
    B -->|Medium risk| D[Ask human]
    B -->|High risk| E[Block]
    D -->|Approved| C
    D -->|Denied| E

    style C fill:#22c55e,color:#fff
    style E fill:#ef4444,color:#fff
    style D fill:#3b82f6,color:#fff
```

**Implementations seen:**

| Library | Mechanism | Risk Detection |
|---------|-----------|---------------|
| Codex | Guardian module | LLM risk scorer (0–100) |
| Hermes | Pattern detector | Regex/pattern matching |
| OpenClaw | Exec approvals | Policy + allowlist |

**The key question:** Is this action reversible?

```mermaid
graph TD
    Q1{Is the action reversible?}
    Q1 -->|Yes — can undo| LOW[Low concern]
    Q1 -->|No — permanent| HIGH[High concern → GuardRail needed]
    HIGH --> Q2{How dangerous if wrong?}
    Q2 -->|Minor inconvenience| WARN[Warn and log]
    Q2 -->|Data loss / system damage| BLOCK[Block or ask human]

    style LOW fill:#22c55e,color:#fff
    style WARN fill:#f59e0b,color:#000
    style BLOCK fill:#ef4444,color:#fff
```

---

### Type 2 — Output GuardRails (Post-Execution)

**What:** Validate what the agent produced, AFTER it finishes, BEFORE passing it on.

**When to use:** When your agent generates content, answers, or data that flows into another step or to a user.

**How it works:**

```mermaid
flowchart LR
    A[Agent produces output] --> B{Output GuardRail}
    B -->|Passes checks| C[Pass to next step]
    B -->|Fails checks| D[Feedback to agent]
    D --> E[Agent retries]
    E --> B
    E -->|Max retries| F[Pipeline fails gracefully]

    style C fill:#22c55e,color:#fff
    style F fill:#ef4444,color:#fff
    style D fill:#f59e0b,color:#000
```

**Types of output checks:**

| Check | What it catches | Example |
|-------|----------------|---------|
| Format check | Wrong structure/schema | JSON malformed, missing fields |
| Content check | Harmful or off-topic content | Profanity, off-topic answers |
| Factual check | Hallucinated claims | Facts not in source material |
| Quality check | Too short, vague, or incomplete | Summary missing key points |
| LLM Judge | General quality evaluation | "Does this answer the question?" |

**Implementations seen:**

| Library | Mechanism |
|---------|-----------|
| CrewAI | Guardrail callable `(bool, result_or_error)` |
| CrewAI | LLM Guardrail — dedicated judge agent |
| CrewAI | Hallucination Guardrail — checks vs source |
| LangChain | PydanticOutputParser, custom runnables |

---

### Type 3 — Behavioral Constraints (Prompt-Level)

**What:** Rules written in plain English and given to the agent as part of its instructions.

**When to use:** As a first line of defense, or when you want to shape general agent behavior without building hard technical checks.

**How it works:**

```mermaid
flowchart LR
    A[System Prompt] --> B[Behavioral Constraints]
    B --> C[Agent reads constraints]
    C --> D{Agent decides action}
    D -->|Constraint says no| E[Agent avoids the action]
    D -->|Constraint allows| F[Agent proceeds]
    F --> G[Technical GuardRail]

    style E fill:#8b5cf6,color:#fff
    style G fill:#3b82f6,color:#fff
```

**Important limitation:**

```mermaid
graph LR
    subgraph SOFT ["Behavioral Constraints (Soft)"]
        S1[LLM interprets instructions]
        S2[Can drift with complex prompts]
        S3[No hard enforcement]
    end

    subgraph HARD ["Technical GuardRails (Hard)"]
        H1[Code enforces the rule]
        H2[Always runs, no drift]
        H3[Hard block possible]
    end

    SOFT -->|"Not enough alone"| NEED[Need both layers]
    HARD -->|"Too strict alone"| NEED

    style SOFT fill:#8b5cf6,color:#fff
    style HARD fill:#3b82f6,color:#fff
    style NEED fill:#22c55e,color:#fff
```

Behavioral constraints guide **intent**. Technical guardrails provide **enforcement**. You need both.

**Implementations seen:**

| Library | Approach |
|---------|---------|
| Oh-My-Codex | AGENTS.md with executor/planner constraints |
| Codex (system prompt) | Safety guidance embedded in base prompt |
| All LLMs | RLHF / Constitutional AI at model level |

---

### Type 4 — Access Control

**What:** Control WHO can do WHAT. Not what the agent does, but whether it is even allowed to try.

**When to use:** Multi-user systems, agents accessing external resources, or when different agents should have different capability levels.

**How it works:**

```mermaid
flowchart LR
    A[Request comes in] --> B{Authenticated?}
    B -->|No| REJECT[Reject]
    B -->|Yes| C{Authorized for this action?}
    C -->|No| REJECT
    C -->|Yes| D[Proceed to GuardRail checks]

    style REJECT fill:#ef4444,color:#fff
    style D fill:#22c55e,color:#fff
```

**Implementations seen:**

| Library | Mechanism |
|---------|-----------|
| OpenClaw | Allowlist per agent, security policy per context |
| Hermes | Session/always/once approval levels |
| SuperMemory | OAuth 2.0, API keys, per-user isolation |

---

## How the 4 Types Work Together

In a well-designed agent system, all 4 types stack as layers of defense:

```mermaid
graph TD
    USER[User or System Request]
    USER --> L4[Layer 4: Access Control\nIs this agent allowed to act here?]
    L4 -->|Denied| R1[Reject]
    L4 -->|Allowed| L3

    L3[Layer 3: Behavioral Constraints\nDoes the agent's intent align with rules?]
    L3 -->|Intent blocked| R2[Agent self-corrects]
    L3 -->|Intent OK| L1

    L1[Layer 1: Action GuardRail\nIs this specific action safe to execute?]
    L1 -->|Risky| HUMAN[Ask human / Block]
    L1 -->|Safe| ACT[Execute Action]

    ACT --> L2[Layer 2: Output GuardRail\nIs the result good enough to pass on?]
    L2 -->|Bad output| RETRY[Retry with feedback]
    L2 -->|Good output| DONE[Pass to next step / User]

    style R1 fill:#ef4444,color:#fff
    style R2 fill:#8b5cf6,color:#fff
    style HUMAN fill:#f59e0b,color:#000
    style DONE fill:#22c55e,color:#fff
```

Each layer catches different things. If one layer misses something, the next layer may still catch it. This is called **defense in depth**.

---

## Patterns Observed Across All Libraries

### Pattern 1 — Fail Closed (Default Deny)

When in doubt, **block**. Never default to allow when the action is ambiguous.

```
OpenClaw default: security = "deny"
Hermes timeout: deny after 60 seconds with no response
Codex: risk score ≥ 80 → block (not ask)
```

### Pattern 2 — Separate the Judge from the Agent

The component that checks safety should be **independent** from the agent being checked.

```
Codex: dedicated guardian LLM session, does not share context with main agent
CrewAI: dedicated "Guardrail Agent" separate from the crew
```

Why: if the same agent judges itself, it will rationalize its own decisions.

### Pattern 3 — Fail Fast with Clear Feedback

When a guardrail fails, give clear, actionable error messages so the agent can retry intelligently.

```
CrewAI: (False, "Output too short, needs at least 100 words")
            ↓ agent retries knowing exactly what to fix
```

Vague errors → random retries → wasted tokens and time.

### Pattern 4 — Escalating Approval

Start automated. Escalate to human only when needed. Give humans clear options.

```mermaid
graph LR
    A[Low risk] -->|Auto| B[Allow]
    C[Medium risk] -->|Ask| D[Human: once / session / always / deny]
    E[High risk] -->|Block| F[Always require explicit approval]
```

### Pattern 5 — Irreversibility = Risk

The more irreversible an action, the more protection it needs.

```mermaid
graph LR
    subgraph LOW_RISK ["Low Risk — Easy to Undo"]
        L1[Read a file]
        L2[Create a draft]
        L3[Run a query]
    end

    subgraph HIGH_RISK ["High Risk — Cannot Undo"]
        H1[Delete a database]
        H2[Send an email]
        H3[Push to production]
        H4[rm -rf]
    end

    LOW_RISK -->|No guardrail needed| AUTO[Auto allow]
    HIGH_RISK -->|Guardrail required| PROTECT[Block or ask human]

    style AUTO fill:#22c55e,color:#fff
    style PROTECT fill:#ef4444,color:#fff
```

---

## How to Think When Designing GuardRails

Use these questions as your design checklist.

### Step 1 — What can your agent DO?

```mermaid
graph TD
    Q[What can your agent do?]
    Q --> A1[Read-only: query, search, summarize]
    Q --> A2[Write: create files, generate content]
    Q --> A3[Act: run commands, call APIs, modify data]
    Q --> A4[Communicate: send messages, post, email]

    A1 --> R1[Low risk — minimal guardrails]
    A2 --> R2[Medium risk — output guardrails]
    A3 --> R3[High risk — action guardrails required]
    A4 --> R4[High risk — irreversible, requires approval]

    style R1 fill:#22c55e,color:#fff
    style R2 fill:#f59e0b,color:#000
    style R3 fill:#ef4444,color:#fff
    style R4 fill:#ef4444,color:#fff
```

### Step 2 — What can go WRONG?

For each agent capability, ask: "What is the worst thing that could happen?"

| Capability | Worst case | Guardrail type needed |
|------------|-----------|----------------------|
| Search the web | Returns bad data | Output guardrail (fact check) |
| Write a file | Overwrites wrong file | Action guardrail (confirm path) |
| Delete data | Permanent data loss | Action guardrail (approval required) |
| Generate a report | Contains hallucinations | Output guardrail (LLM judge) |
| Call external API | Sends private data externally | Action guardrail (destination check) |
| Run shell command | Destroys system | Action guardrail (pattern + risk score) |

### Step 3 — How Often Should a Human Be Involved?

```mermaid
graph LR
    subgraph NEVER ["Never involve human"]
        N1[Agent reads files]
        N2[Agent searches database]
    end

    subgraph SOMETIMES ["Involve human on miss"]
        S1[Unknown command → ask]
        S2[High-risk action → ask]
    end

    subgraph ALWAYS ["Always involve human"]
        A1[Send email to customers]
        A2[Push to production]
        A3[Delete production data]
    end

    style NEVER fill:#22c55e,color:#fff
    style SOMETIMES fill:#f59e0b,color:#000
    style ALWAYS fill:#ef4444,color:#fff
```

**Rule:** The more irreversible + the wider the impact = the more human oversight is needed.

### Step 4 — What Should Happen on Failure?

For each guardrail, define all 3 outcomes:

```mermaid
graph TD
    GR[GuardRail Check]
    GR --> P[PASS → continue]
    GR --> F[FAIL → retry with feedback]
    GR --> B[BLOCK → hard stop + explain why]

    P --> P1[What does the next step receive?]
    F --> F1[What feedback helps the agent retry?]
    B --> B1[What message does the user see?]
```

Never fail silently. Always explain why the guardrail triggered.

### Step 5 — What Is the Cost of Being Wrong?

Two types of errors:

| Error Type | Definition | Example | Cost |
|-----------|------------|---------|------|
| **False Positive** | Blocked a safe action | GuardRail stops `ls -la` as dangerous | Agent is useless |
| **False Negative** | Allowed a dangerous action | GuardRail misses `rm -rf /var` | System destroyed |

```mermaid
graph LR
    subgraph FP ["Too many False Positives"]
        FP1[GuardRail too strict]
        FP1 --> FP2[Agent blocked constantly]
        FP2 --> FP3[User loses trust in agent]
    end

    subgraph FN ["Too many False Negatives"]
        FN1[GuardRail too loose]
        FN1 --> FN2[Dangerous actions get through]
        FN2 --> FN3[Real damage happens]
    end
```

Balance by:
- Tuning the risk threshold (Codex: score of 80, not 50 or 100)
- Using allowlists to trust known-safe patterns (OpenClaw, Hermes)
- Escalating to human for the gray area in the middle

---

## Design Decision Map

Use this to quickly find which guardrail type you need:

```mermaid
flowchart TD
    START[My agent needs guardrails]

    START --> Q1{Does it execute actions\nor commands?}
    Q1 -->|Yes| AG[Add Action GuardRails\nType 1]
    Q1 -->|No| Q2

    START --> Q2{Does it produce output\nthat flows downstream?}
    Q2 -->|Yes| OG[Add Output GuardRails\nType 2]
    Q2 -->|No| Q3

    START --> Q3{Do you want to\nshape its behavior broadly?}
    Q3 -->|Yes| BC[Add Behavioral Constraints\nType 3]

    START --> Q4{Does it access resources\nor serve multiple users?}
    Q4 -->|Yes| AC[Add Access Control\nType 4]

    AG --> BOTH[Combine with Behavioral Constraints\nfor defense in depth]
    OG --> BOTH
    BC --> BOTH
    AC --> BOTH

    style AG fill:#ef4444,color:#fff
    style OG fill:#3b82f6,color:#fff
    style BC fill:#8b5cf6,color:#fff
    style AC fill:#f59e0b,color:#000
    style BOTH fill:#22c55e,color:#fff
```

---

## Summary Table — GuardRail Types at a Glance

| Type | Name | When | What it checks | Libraries |
|------|------|------|---------------|-----------|
| 1 | Action GuardRails | Before action runs | Is this action safe? | Codex, Hermes, OpenClaw |
| 2 | Output GuardRails | After output produced | Is this output good? | CrewAI, LangChain |
| 3 | Behavioral Constraints | Always (in prompt) | Does the agent intend the right thing? | OMX, all LLMs |
| 4 | Access Control | Before anything runs | Is this agent/user allowed? | OpenClaw, SuperMemory |

---

## Key Principles (Remember These)

1. **Fail closed** — default deny when uncertain
2. **Separate the judge** — don't let the agent evaluate itself
3. **Fail fast with feedback** — clear errors enable smart retries
4. **Irreversibility = risk level** — the harder to undo, the more protection needed
5. **Defense in depth** — layer all 4 types; each catches what others miss
6. **Balance** — too strict makes agents useless; calibrate thresholds carefully
7. **Escalate don't block** — prefer "ask human" over hard block for edge cases
