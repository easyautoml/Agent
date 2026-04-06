# Hermes Agent — GuardRails

## Context

**Hermes Agent** (by Nous Research) is a self-improving AI agent that learns new skills from experience. It runs on servers, VPS, and cloud platforms, and can be accessed via Telegram, Discord, Slack, and other chat platforms.

Because Hermes executes real shell commands on real servers, it needs a way to stop **dangerous operations** before they cause irreversible damage.

---

## What Are GuardRails?

GuardRails in Hermes = a **dangerous command detection + approval system**.

Before any command runs, Hermes checks it against a list of known-dangerous patterns. If it matches, it stops and asks for permission.

```
Command about to run
        ↓
Pattern check (does it look dangerous?)
        ↓
YES → Ask human to approve  →  Approve / Deny
NO  → Run it
```

---

## Why Do We Need GuardRails?

| Scenario | Without GuardRails | With GuardRails |
|----------|-------------------|-----------------|
| Agent runs `rm -rf /` | Server destroyed | Blocked, user alerted |
| Agent drops a database table | Data permanently lost | Approval required |
| Agent runs `curl \| sh` from internet | Malware executed | Flagged and blocked |
| Agent kills all processes | System crash | Human must approve |

Hermes is a **persistent agent on live servers**. Mistakes aren't just bugs — they can delete production data or crash systems.

---

## Main Components (4 Parts)

```mermaid
graph TD
    CMD[Command to Execute] --> DET[Pattern Detector]
    DET -->|Safe| RUN[Run Immediately]
    DET -->|Dangerous| APR[Approval System]
    APR --> MOD{Approval Mode}
    MOD -->|manual| HUM[Ask Human]
    MOD -->|smart| LLM[Ask LLM to assess]
    MOD -->|off/yolo| RUN
    HUM -->|approve| RUN
    HUM -->|deny| BLK[Block Command]
    LLM -->|low risk| RUN
    LLM -->|high risk| HUM

    style RUN fill:#22c55e,color:#fff
    style BLK fill:#ef4444,color:#fff
    style HUM fill:#3b82f6,color:#fff
```

### 1. Pattern Detector
Checks the command against known-dangerous patterns before execution.

### 2. Approval System
Routes the command to the right approval flow based on mode.

### 3. Allowlist (`~/.hermes/config.yaml`)
Stores commands you've already approved as "always allow". Hermes won't ask again.

### 4. YOLO Mode
A way to disable all guardrails for the session (use with caution).

---

## Dangerous Patterns Detected

```mermaid
graph LR
    subgraph DESTROY ["💣 Destroy Data"]
        D1["rm -r ..."]
        D2["mkfs"]
        D3["dd if="]
        D4["DROP TABLE"]
        D5["DELETE FROM (no WHERE)"]
        D6["TRUNCATE TABLE"]
    end

    subgraph SYSTEM ["⚙️ System Changes"]
        S1["chmod 777/666"]
        S2["chown -R root"]
        S3["systemctl stop/disable"]
        S4["> /etc/ (overwrite configs)"]
    end

    subgraph REMOTE ["🌐 Remote Execution"]
        R1["curl | sh"]
        R2["bash <(wget ...)"]
        R3["kill -9 -1"]
    end
```

---

## How They Work Together

```mermaid
sequenceDiagram
    participant Agent
    participant Detector
    participant User as "Human (via chat)"
    participant Allowlist

    Agent->>Detector: Run: "DROP TABLE users"
    Detector->>Allowlist: Is this pre-approved?
    Allowlist-->>Detector: No
    Detector->>User: ⚠️ Dangerous: DROP TABLE users. Allow?
    Note over User: Options: once / session / always / deny
    User-->>Detector: "session" (allow for rest of session)
    Detector-->>Agent: Approved
    Agent->>Agent: Executes command
```

---

## Approval Options

| Option | What it does |
|--------|-------------|
| **once** | Allow this one time only |
| **session** | Allow for the rest of this session |
| **always** | Save to allowlist, never ask again |
| **deny** | Block it (default if no response in 60s) |

---

## Approval Modes

```mermaid
graph LR
    subgraph MODES ["Approval Modes"]
        M1["manual — always ask human"]
        M2["smart — ask LLM first, human if unsure"]
        M3["off (YOLO) — never ask, just run"]
    end
```

YOLO mode can be toggled:
- CLI: `hermes --yolo`
- Chat command: `/yolo`
- Env variable: `HERMES_YOLO_MODE=1`

---

## Container Bypass

When Hermes detects it's running inside a container (Docker, Singularity, Modal), it skips the dangerous command checks. The container itself is the safety boundary.

```mermaid
flowchart LR
    A[Command] --> B{In container?}
    B -->|Yes| C[Run without checks]
    B -->|No| D[Pattern check → Approval]

    style C fill:#f59e0b,color:#fff
    style D fill:#3b82f6,color:#fff
```

---

## Summary

- **What:** Pattern-based dangerous command detection with human-in-the-loop approval
- **Why:** Prevent irreversible damage on live servers from agent mistakes
- **Components:** Pattern Detector → Approval System → Allowlist → YOLO Mode
- **Default behavior:** Prompt user, deny if no response within 60 seconds
- **Built in:** Python (`hermes-agent/`) with chat-based approval flow
