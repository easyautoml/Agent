# AI Agent Memory — Complete Architecture Guide
## Covering LangChain & CrewAI

---

## Contents

1. [What is Memory and Why It Matters](#1-what-is-memory-and-why-it-matters)
2. [The Universal Memory Taxonomy](#2-the-universal-memory-taxonomy)
3. [Memory Types — Decision Guide](#3-memory-types--decision-guide)
4. [LangChain Memory Architecture](#4-langchain-memory-architecture)
5. [CrewAI Memory Architecture](#5-crewai-memory-architecture)
6. [Supermemory Architecture](#6-supermemory-architecture)
7. [LangChain vs CrewAI vs Supermemory — Side by Side](#7-langchain-vs-crewai-vs-supermemory--side-by-side)
8. [How Memory Works Technically](#8-how-memory-works-technically)
9. [Real-World Patterns](#9-real-world-patterns)
10. [Pros and Cons of Each Approach](#10-pros-and-cons-of-each-approach)
11. [Quick Reference](#11-quick-reference)

---

## 1. What is Memory and Why It Matters

Without memory, every LLM call starts from zero. The agent has no idea what happened before, who it talked to, or what it learned. It's like hiring a brilliant expert who develops amnesia between every meeting.

![Without Memory vs With Memory](./img/03_lr1_without_with_memory.png)

**Memory solves three problems:**

| Problem | Without Memory | With Memory |
|---------|---------------|-------------|
| Context | Agent forgets everything between turns | Agent builds on each interaction |
| Personalization | Every user gets identical generic responses | Agent adapts to each user's history |
| Multi-agent coordination | Agents duplicate work, contradict each other | Agents share findings, build together |

---

## 2. The Universal Memory Taxonomy

Cognitive science has studied human memory for decades. AI agent memory mirrors the same patterns.

![Memory Taxonomy](./img/20_memory_taxonomy_mindmap.png)

### The 4 Memory Types — Core Concepts

![Four Memory Types Core Concepts](./img/21_four_memory_types.png)

### How This Maps to All Three Frameworks

| Cognitive Type | LangChain Implementation | CrewAI Implementation | Supermemory Implementation |
|---------------|--------------------------|----------------------|---------------------------|
| **Working Memory** | ConversationBufferMemory | In-task context (LLM context window) | LRU cache (per-turn, 100 entries) |
| **Short-term Buffer** | BufferWindowMemory, TokenBufferMemory | — | Dynamic Memory (recent activity) |
| **Episodic (Long-term)** | VectorStoreRetrieverMemory | Long-term Memory (LanceDB/Qdrant) | Conversation Memory (/v4/conversations) |
| **Semantic (Facts)** | ConversationEntityMemory, SummaryMemory | Short-term Memory + Entity Memory | Static Memory (core identity facts) |
| **Compressed History** | ConversationSummaryMemory | Analyze Engine → summary records | Profile API — automatic extraction |
| **Cross-agent Shared** | ReadOnlySharedMemory, CombinedMemory | MemorySlice across scopes | Container tags (shared project tag) |
| **Managed / External** | — | — | Document Memory (/v3/documents) |

---

## 3. Memory Types — Decision Guide

### Decision Tree — Which Memory to Use?

![Decision Tree — Which Memory to Use](./img/22_decision_tree.png)

### Decision by Data Type

![Decision by Data Type](./img/03_lr2_decision_by_data_type.png)

### Quick Use-Case Table

| Situation | Best Choice | Why |
|-----------|-------------|-----|
| Quick prototype / demo | `ConversationBufferMemory` | Zero setup, works immediately |
| Customer support chat | `ConversationSummaryBufferMemory` | Long sessions, need detail + context |
| Coding assistant | `ConversationBufferWindowMemory` | Recent code is what matters |
| Personal assistant | `ConversationEntityMemory` + `VectorStoreRetrieverMemory` | Tracks people and finds past conversations |
| Research agent | `VectorStoreRetrieverMemory` | Search huge knowledge base by meaning |
| Multi-agent pipeline | CrewAI Memory with scopes | Agents share and isolate memories |
| Production chatbot | `ConversationSummaryBufferMemory` + Redis backend | Persistent, bounded, scalable |
| Inject system rules | `SimpleMemory` | Static context, never changes |
| Share memory across chains | `ReadOnlySharedMemory` | One source of truth, write-protected |

---

## 4. LangChain Memory Architecture

### The Big Picture

![LangChain Memory Architecture](./img/23_langchain_architecture.png)

### The Universal 3-Step Lifecycle

Every LangChain memory type follows the same lifecycle on every turn:

![LangChain 3-Step Memory Lifecycle](./img/03_seq1_langchain_lifecycle.png)

**The key insight:** Memory is just *context injection*. It decides what text to prepend to the current message. Each type uses a different strategy to pick that text.

### The 7 Memory Strategies — Visual Comparison

![Seven Memory Strategies Visual Comparison](./img/24_seven_strategies.png)

### Token Budget — How Each Type Uses Tokens

![Token Budget Growth Over Conversation](./img/25_token_budget_chart.png)

> **Lines (top to bottom):** Buffer (grows forever) → Window (stable) → Summary (very small) → Summary Buffer (capped) → Vector (only top-k results)

---

## 5. CrewAI Memory Architecture

### The Big Picture

CrewAI memory is designed for **multi-agent coordination**, not single-agent conversations. Every memory is stored in a **hierarchical scope tree**, like a file system. Agents can only see their own scope — but a MemorySlice can search across multiple scopes.

![CrewAI Memory Architecture](./img/26_crewai_architecture.png)

### Hierarchical Scope Tree

![CrewAI Hierarchical Scope Tree](./img/27_scope_tree.png)

**Rule:** An agent with scope `/crew/sales-team/agent/hunter` can only read/write within its subtree. It is invisible to the support team and vice versa — unless a MemorySlice bridges the two.

### MemoryRecord — One Piece of Memory

![MemoryRecord Fields](./img/03_lr3_memory_record_fields.png)

### The 5-Step EncodingFlow (Save Pipeline)

![CrewAI 5-Step EncodingFlow](./img/28_encoding_flow.png)

### The RecallFlow (Search Pipeline)

![CrewAI RecallFlow Search Pipeline](./img/29_recall_flow.png)

### Composite Scoring — How Results Are Ranked

Every search result gets a score combining 3 factors:

![Memory Relevance Composite Score](./img/30_composite_scoring_pie.png)

![Composite Scoring Formula](./img/03_lr4_composite_scoring.png)

**Example:**

| Record | Semantic | Recency | Importance | Score |
|--------|----------|---------|------------|-------|
| "Client wants email" — saved yesterday, importance 0.9 | 0.88 | 1.0 | 0.9 | **0.44 + 0.30 + 0.18 = 0.92** |
| "Client wants email" — saved 2 months ago, importance 0.9 | 0.88 | 0.25 | 0.9 | **0.44 + 0.08 + 0.18 = 0.70** |

The recent record wins even though content is identical.

---

## 6. Supermemory Architecture

### The Big Picture

Supermemory is a **managed memory service** — instead of building memory infrastructure yourself, you call an API. It handles extraction, conflict resolution, deduplication, and semantic search automatically.

![Supermemory 3 Memory Types](./img/sm_d01_three_memory_types.png)

### The 3 Memory Types

| Type | What it stores | Changes how often | Retrieved by |
|------|---------------|------------------|--------------|
| **Static** | Core identity facts — name, job, long-term preferences | Rarely; only on explicit update | `profile` or `full` mode |
| **Dynamic** | Recent activity — current projects, this week's focus | Often; fades naturally as new activity takes over | `profile` or `full` mode |
| **Search Results** | Semantically relevant past memories for the current question | Every query — computed fresh each time | `query` or `full` mode |

### The 3 Retrieval Modes

![Supermemory 3 Retrieval Modes](./img/sm_d04_three_modes.png)

| Mode | Returns | Best for |
|------|---------|---------|
| `profile` | Static + Dynamic | Always need user context; personalization |
| `query` | Semantic search only | Document Q&A; RAG patterns |
| `full` | Static + Dynamic + Search | Personal assistants; support bots (recommended default) |

### How Memory Gets Saved

![Supermemory Save Flow](./img/sm_d02_save_flow.png)

Enable with `addMemory: "always"` — every conversation is saved and processed automatically. The backend extracts facts, detects conflicts (new info replaces old), expires time-sensitive facts, and builds the profile.

### How Memory Gets Recalled

![Supermemory Recall Flow](./img/sm_d03_recall_flow.png)

On every user message: query text is embedded → LRU cache checked (100 entries) → `/v4/profile` fetched on miss → results deduplicated (Static > Dynamic > Search) → formatted as markdown → injected into system prompt. Total: ~50ms.

### Conflict Resolution

When a user shares contradicting information, Supermemory resolves it automatically:

![Memory Conflict Resolution](./img/sm_d06_memory_conflict.png)

**Rule:** New > Old. "I moved to San Francisco" automatically replaces "Lives in New York."

### Memory Lifecycle

![Memory Lifecycle](./img/sm_d11_memory_lifecycle.png)

Facts are born, updated on conflict, expired automatically when time-sensitive ("meeting tomorrow"), or forgotten on explicit request.

### Container Tags — User Isolation

![Container Tags](./img/sm_d09_container_tags.png)

Each user gets a `containerTag` (e.g. `"user-alice"`). Memories never mix across tags. Use a shared project tag (`"sm_project_x"`) for team-wide knowledge.

### Document Memory vs Conversation Memory

![Document vs Conversation Memory](./img/sm_d07_document_vs_conversation.png)

Both feed the same Profile API — documents store files/pages; conversations store chat history extracted as facts.

---

## 7. LangChain vs CrewAI vs Supermemory — Side by Side

### Design Philosophy

![LangChain vs CrewAI Design Philosophy](./img/03_lr5_langchain_vs_crewai.png)

![Supermemory vs LangChain Comparison](./img/sm_d12_compare_with_langchain.png)

### Feature Comparison

| Feature | LangChain | CrewAI | Supermemory |
|---------|-----------|--------|-------------|
| **Primary use** | Single-agent conversation | Multi-agent crew coordination | Any agent — managed memory service |
| **Memory model** | Strategy-based (choose 1 of 7) | Unified with scoped storage | Static / Dynamic / Search Results |
| **Storage options** | 21 backends (you manage) | LanceDB or Qdrant (you manage) | Cloudflare-backed (fully managed) |
| **Context injection** | `{history}` placeholder in prompt | RecallMemoryTool + RememberTool | `withSupermemory()` wraps your model |
| **Deduplication** | Manual | Automatic (similarity threshold) | Automatic (Static > Dynamic > Search) |
| **User isolation** | Not built-in (use session_id manually) | Built-in via scope paths | Built-in via containerTag |
| **Cross-agent sharing** | CombinedMemory | MemorySlice | Shared containerTag |
| **LLM-powered compression** | SummaryMemory, EntityMemory | Analyze Engine (automatic) | Profile API (automatic extraction) |
| **Semantic search** | VectorStoreRetrieverMemory only | All memories indexed as vectors | All memories + documents searchable |
| **Conflict resolution** | Manual | Automatic (consolidation engine) | Automatic (new > old rule) |
| **Temporal expiry** | Manual | Via importance decay | Automatic (time-sensitive facts) |
| **Background saves** | No (synchronous) | Yes (non-blocking) | Yes (async, ~50ms recall) |
| **Importance scoring** | No | Yes (0.0–1.0, weighted) | Profile rank (Static > Dynamic) |
| **Setup complexity** | Low | Medium | Minimal — 2 lines of code |
| **Infrastructure required** | Redis/FAISS/Pinecone (you manage) | LanceDB/Qdrant (you manage) | None — external API |
| **Data control** | Full — stays on your servers | Full — stays on your servers | Partial — data on Supermemory servers |

### When to Choose Which

![When to Choose LangChain vs CrewAI](./img/31_when_to_choose.png)

| Choose | When |
|--------|------|
| **LangChain** | Full offline control, data sovereignty, custom memory logic, existing LangChain stack |
| **CrewAI** | Multi-agent system, need scoped isolation between agents, automatic deduplication |
| **Supermemory** | Speed to market, no memory infrastructure, smart conflict resolution, user-facing products |

---

## 8. How Memory Works Technically

### Vector Embeddings — The Foundation

Both frameworks rely on **vector embeddings** for semantic search. This is how meaning is compared mathematically.

![Vector Embeddings — Semantic Similarity](./img/03_lr6_vector_embeddings.png)

**Key insight:** Words don't need to match — *meaning* matches. "Client prefers email" and "Customer wants email updates" have different words but similar vectors.

### LangChain — Context Injection Mechanics

![LangChain Context Injection Mechanics](./img/03_seq2_langchain_injection.png)

### CrewAI — Background Save Mechanics

![CrewAI Background Save Mechanics](./img/03_seq3_crewai_background_save.png)

### Memory Consolidation — Keeping Memory Clean

CrewAI automatically merges similar records to avoid duplicates:

![Memory Consolidation — Keeping Memory Clean](./img/32_memory_consolidation.png)

### Session vs Persistent Memory

![Session vs Persistent vs Semantic Memory](./img/03_lr7_session_vs_persistent.png)

---

## 9. Real-World Patterns

### Pattern 1 — Simple Chatbot (LangChain)

Use `ConversationSummaryBufferMemory` with a Redis backend for a production chatbot.

![Pattern 1 — Simple Chatbot with Redis](./img/33_pattern1_simple_chatbot.png)

**Good for:** Customer support, personal assistants, FAQ bots.

### Pattern 2 — Research Crew (CrewAI)

Three agents share knowledge through scoped memory.

![CrewAI Research Crew Memory Flow](./img/03_seq4_crewai_research_crew.png)

### Pattern 3 — Multi-User Production (LangChain + Redis)

![Pattern 3 — Multi-User Production](./img/34_pattern3_multiuser.png)

Each user's history is completely isolated by `session_id`. Sessions persist across server restarts.

### Pattern 4 — Parallel Crew Workers (CrewAI + Qdrant Edge)

![CrewAI Parallel Workers with Qdrant Edge](./img/03_seq5_crewai_parallel_workers.png)

**Good for:** Processing many customers, documents, or cases in parallel.

---

## 10. Pros and Cons of Each Approach

### LangChain Memory

| Memory Type | Pros | Cons |
|-------------|------|------|
| **BufferMemory** | Dead simple, no LLM calls, zero latency | Token usage grows unbounded; breaks for long conversations |
| **BufferWindowMemory** | Stable token usage, simple to reason about | Old info permanently lost; window size is a guess |
| **TokenBufferMemory** | Precise token control, predictable cost | Still loses old info; requires LLM for counting |
| **SummaryMemory** | Very small token usage, scales to any length | Loses nuance; extra LLM call per turn adds latency + cost |
| **SummaryBufferMemory** | Best balance — detail for recent, compressed for old | More complex; still needs LLM; slight latency |
| **EntityMemory** | Tracks facts about specific people/places over time | Only as good as LLM extraction; can miss entities |
| **VectorStoreRetrieverMemory** | Searches all history by meaning, no size limit | Needs vector store setup; misses sequential context |
| **CombinedMemory** | Maximum flexibility | Complex setup; key conflicts possible; debugging harder |
| **SimpleMemory** | Zero overhead, perfect for static rules | Not real memory — just a constant injected every turn |

### CrewAI Memory

| Aspect | Pros | Cons |
|--------|------|------|
| **Unified system** | One API for all memory needs | Less granular control per memory type |
| **Auto-deduplication** | Memory stays clean without manual effort | LLM call overhead for consolidation |
| **Hierarchical scopes** | Natural agent isolation, no accidental leakage | Scope design requires upfront planning |
| **MemorySlice** | Flexible cross-agent knowledge sharing | Slightly more complex query patterns |
| **Importance scoring** | Frequently accessed / high-importance info surfaces first | LLM assigns importance — not always accurate |
| **Background saves** | Non-blocking, agent keeps working | Race conditions possible if recall happens too fast |
| **Semantic search always on** | All records searchable by meaning, out of the box | LanceDB not distributed; Qdrant Edge more complex |
| **Analyze Engine** | Auto-categorizes, auto-scopes, no manual tagging | LLM call on every save without fast path |

### Supermemory

| Aspect | Pros | Cons |
|--------|------|------|
| **Zero-infra setup** | Works in 2 lines, no Redis/FAISS/Pinecone to manage | External API dependency; outage = no memory |
| **Auto conflict resolution** | New facts automatically replace old ones | Resolution logic not customizable |
| **Auto temporal expiry** | Time-sensitive facts expire without manual cleanup | Expiry timing not configurable per fact |
| **Static/Dynamic split** | Clean separation of "who you are" vs "what you're doing" | Less granular than LangChain's 7 strategies |
| **Retrieval modes** | profile / query / full covers most use cases | No custom scoring (vs CrewAI's 3-factor formula) |
| **Container tag isolation** | User isolation built in, zero extra code | All data lives on Supermemory servers |
| **LRU cache** | Same-turn queries skip API calls | Cache is per-turn; no cross-session hot cache |
| **Framework integrations** | Works with OpenAI, Vercel AI, Mastra, LangChain, n8n | Python support is partial vs full TS support |

### Overall Comparison

![LangChain vs CrewAI Tradeoffs Quadrant](./img/35_tradeoffs_quadrant.png)

---

## 11. Quick Reference

### LangChain — Choose by Situation

| Situation | Memory Type | Storage Backend |
|-----------|-------------|-----------------|
| Prototype / demo | `ConversationBufferMemory` | In-memory |
| Chatbot, short sessions | `ConversationBufferWindowMemory` | Redis |
| Strict token budget | `ConversationTokenBufferMemory` | Redis |
| Long sessions, compressed | `ConversationSummaryMemory` | Redis / PostgreSQL |
| Long sessions, best quality | `ConversationSummaryBufferMemory` | Redis / PostgreSQL |
| Track people and places | `ConversationEntityMemory` | Redis / SQLite |
| Search all history by meaning | `VectorStoreRetrieverMemory` | FAISS / Pinecone / Chroma |
| Need multiple strategies | `CombinedMemory` | Mix |
| Share memory read-only | `ReadOnlySharedMemory` | Wrap any backend |
| Static system instructions | `SimpleMemory` | None needed |

### Supermemory — Key Operations

| Operation | Method | When to Use |
|-----------|--------|-------------|
| Add memory to your model | `withSupermemory(model, userId)` | Wrap any model in 2 lines |
| Set retrieval mode | `mode: "profile" / "query" / "full"` | Profile=always facts; Query=semantic search; Full=both |
| Auto-save conversations | `addMemory: "always"` | Save every turn automatically |
| Save a specific fact | `client.add({ content, containerTag })` | Save explicit information |
| Get user profile | `client.profile({ containerTag })` | Fetch static + dynamic summary |
| Search memories | `client.search.memories({ q, containerTag })` | Semantic search over all memory |
| Forget a memory | `client.memoryForget({ content })` | Remove a specific fact |
| Add a document | `client.add({ content, metadata })` | Add PDF, web page, or knowledge base entry |

### CrewAI — Key Operations

| Operation | Method | When to Use |
|-----------|--------|-------------|
| Save a fact | `memory.remember(content)` | After agent discovers something important |
| Save many facts | `memory.remember_many(contents)` | Batch save after a research phase |
| Search memory | `memory.recall(query)` | Before starting a task to check prior knowledge |
| Delete memories | `memory.forget(scope)` | Clean up stale or wrong information |
| Break text into facts | `memory.extract_memories(text)` | When saving long reports or documents |
| Isolate an agent | `memory.scope(path)` | Give an agent its own private memory region |
| Search across agents | `memory.slice(paths)` | Manager agent needs everyone's findings |
| See scope structure | `memory.tree(path)` | Debug what agents have remembered |

### All Memory Types at a Glance

![All Memory Types at a Glance](./img/36_all_memory_types.png)

### The Golden Rules

![The Golden Rules of Memory](./img/03_lr8_golden_rules.png)

---

## Summary — The Big Picture

![Summary — The Big Picture](./img/37_summary_big_picture.png)

**The core truth about memory in both frameworks:**

> Memory is not magic. It is **context engineering** — deciding what information to prepend to a prompt so the LLM can answer as if it remembers. Every strategy, every component, every storage backend exists to answer one question: *"What context does the LLM need right now, and how do we get it there efficiently?"*

| Framework | Best Summary |
|-----------|-------------|
| **LangChain** | Give you 7 strategies and 21 backends. You choose what to keep and where to put it. Maximum flexibility, minimum magic. |
| **CrewAI** | One unified system that automatically embeds, deduplicates, categorizes, and scopes everything. Less control, more automation. |
