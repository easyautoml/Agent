# CrewAI Tools

## What is a Tool?

A tool is a capability an agent can use to complete a task.
It can read files, call APIs, search memory, or delegate work to another agent.
Each tool has a name, a description, and a set of input parameters.

---

## How a Tool is Defined

Every tool has three parts:

| Part | Purpose |
|------|---------|
| **name** | Unique identifier the agent calls |
| **description** | Tells the agent when and how to use it |
| **args_schema** | Defines the required inputs (Pydantic model) |

The simplest way to define a tool is the `@tool` decorator.
For more control, inherit from `BaseTool` and implement the `_run()` method.

---

## Tool Categories

CrewAI has five main categories:

### 1. BaseTool
The abstract base class every tool extends.
All tools must implement `_run()` (sync) or `_arun()` (async).

### 2. Tool (decorator)
Wraps a plain Python function into a tool.
Schema is inferred from the function signature automatically.
Easiest way to create a custom tool.

### 3. Agent Tools
Tools for agent-to-agent interaction:

| Tool | Purpose |
|------|---------|
| `DelegateWorkTool` | Assign a subtask to another agent |
| `AskQuestionTool` | Ask another agent a question |
| `AddImageTool` | Attach images to a response |
| `ReadFileTool` | Read files from crew inputs |

### 4. Memory Tools
Tools for storing and recalling knowledge:

| Tool | Purpose |
|------|---------|
| `RecallMemoryTool` | Search what the agent has learned |
| `RememberTool` | Save a fact or decision to memory |

### 5. Integration Tools
Tools that connect to external systems:

| Tool | Purpose |
|------|---------|
| `MCPNativeTool` | Tools from any MCP server |
| `MCPToolWrapper` | Wrapped MCP tools for compatibility |
| `CacheTools` | Reuse previous tool results |

---

## How Tools Work with Agents and Tasks

```
Crew assigns task to agent
    ↓
Agent reads task description + tool descriptions
    ↓
Agent calls the right tool with arguments
    ↓
Arguments are validated against the schema
    ↓
Tool executes and returns result
    ↓
Result stored in cache (if cache_function set)
    ↓
Agent continues until task is complete
```

Agents are initialized with a list of tools.
The LLM decides which tool to call based on descriptions.

---

## Built-in Tools Summary

| Tool | Purpose |
|------|---------|
| Delegate work to coworker | Split task to another agent |
| Ask question to coworker | Query another agent |
| Search memory | Find remembered facts |
| Save to memory | Store important information |
| read_file | Read input files |
| Add image | Attach image to response |
| Hit Cache | Get a cached tool result |

---

## Key Components

| Component | Role |
|-----------|------|
| `BaseTool` | Base class for all tools |
| `@tool` decorator | Quick tool creation from function |
| `ToolsHandler` | Executes tools and fires callbacks |
| `cache_handler` | Stores/retrieves tool results |
| `args_schema` | Validates inputs (Pydantic model) |
| `result_as_answer` | If true, tool output = final agent answer |

---

## Summary

- Tool = name + description + input schema + function
- Five categories: base, decorator, agent tools, memory, integrations
- Agent picks tools by reading descriptions
- Results can be cached to avoid repeated calls
- Use `@tool` for quick tools, `BaseTool` for full control
