# LangChain Tools

## What is a Tool?

A tool is a capability an agent can call to interact with the outside world.
It wraps a function with a name, a description, and an input schema.
The agent reads the description to decide when and how to use the tool.

---

## How a Tool is Defined

Every tool has three parts:

| Part | Purpose |
|------|---------|
| **name** | Unique identifier (e.g. `web_search`) |
| **description** | Tells the agent when to use it |
| **args_schema** | Defines the input fields and their types |

The simplest way to create a tool is with the `@tool` decorator.
LangChain infers the schema from the function signature automatically.

---

## Tool Types

LangChain has three built-in tool types:

| Type | When to Use |
|------|-------------|
| **Tool** | Single string input, lightweight tasks |
| **StructuredTool** | Multiple typed inputs, complex tasks |
| **@tool decorator** | Quickest way — wraps any Python function |

All three inherit from `BaseTool`.

---

## Built-in Tool Categories

LangChain ships 60+ ready-made tools:

| Category | Examples |
|----------|---------|
| Search & Web | Google Search, DuckDuckGo, Tavily |
| File Management | Read, Write, Copy, Delete files |
| Database | SQL query, Spark SQL |
| Communication | Gmail, Slack, Office365 |
| Knowledge | Wikipedia, ArXiv, PubMed |
| Development | GitHub, Jira, OpenAPI |
| HTTP | Requests GET/POST, GraphQL |
| Finance | Yahoo Finance, Google Trends |

**Toolkits** are groups of related tools bundled together (e.g. File Toolkit = read + write + delete + list).

---

## How Tools Work Together with Agents

```
Agent gets a task
    ↓
Agent reads all tool descriptions
    ↓
Agent picks the right tool
    ↓
Agent calls the tool with inputs
    ↓
Tool runs and returns result
    ↓
Agent uses result to continue
    ↓
Repeat until task is done
```

The agent does not call tools directly — the LLM decides which tool to use based on the descriptions.
The `AgentExecutor` handles routing and execution.

---

## Key Components

| Component | Role |
|-----------|------|
| `BaseTool` | Base class all tools inherit from |
| `@tool` decorator | Converts a plain function into a tool |
| `StructuredTool` | Multi-input tool with full schema |
| `AgentExecutor` | Runs the agent loop and dispatches tool calls |
| `render_text_description()` | Formats tools for the LLM prompt |
| `ToolkitBase` | Groups related tools into a named set |

---

## Simple Flow Example

> Task: "What is the weather in Tokyo?"

1. Agent sees `WeatherTool` with description "Get current weather for a city"
2. Agent calls `WeatherTool(city="Tokyo")`
3. Tool returns `"Sunny, 22°C"`
4. Agent replies to the user with the result

---

## Summary

- A tool = name + description + function
- Agent picks tools based on descriptions
- LangChain provides 60+ built-in tools
- Use `@tool` decorator for custom tools
- `AgentExecutor` manages the loop
