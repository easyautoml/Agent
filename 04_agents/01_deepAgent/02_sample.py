"""
02_sample.py — DeepAgent Use Cases with Azure OpenAI
======================================================
Covers:
  1. Custom Tools         — give the agent Python functions as tools
  2. System Prompt        — customize agent personality / instructions
  3. Streaming            — token-by-token output via .stream()
  4. Structured Output    — enforce a Pydantic schema on the response
  5. Multi-turn Memory    — persist conversation state across calls
  6. Human-in-the-Loop    — pause before a dangerous tool and let user approve
  7. Sub-agents           — delegate specialized work to a child agent

Run any section independently by calling its function at the bottom.
"""

import json
import os

from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from pydantic import BaseModel, Field

from deepagents import create_deep_agent

load_dotenv()


def _make_model():
    """Shared helper — Azure AI Foundry exposes an OpenAI-compatible base URL.
    Use ChatOpenAI with base_url instead of AzureChatOpenAI."""
    return ChatOpenAI(
        model=os.environ["AZURE_OPENAI_DEPLOYMENT"],
        base_url=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
    )


# ──────────────────────────────────────────────────────────────────────────────
# 1. CUSTOM TOOLS
#    Pass plain Python functions as tools. DeepAgent wraps them automatically.
# ──────────────────────────────────────────────────────────────────────────────

def demo_custom_tools():
    print("\n" + "=" * 60)
    print("USE CASE 1: Custom Tools")
    print("=" * 60)

    def get_weather(city: str) -> str:
        """Return the current weather for a city (mock)."""
        mock_data = {
            "tokyo": "Sunny, 22°C, humidity 60%",
            "london": "Cloudy, 14°C, humidity 80%",
            "new york": "Rainy, 18°C, humidity 75%",
        }
        return mock_data.get(city.lower(), f"No data for {city}")

    def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
        """Convert an amount between currencies using fixed mock rates."""
        rates = {"USD": 1.0, "EUR": 0.92, "JPY": 153.0, "GBP": 0.79}
        if from_currency not in rates or to_currency not in rates:
            return "Unsupported currency"
        converted = amount / rates[from_currency] * rates[to_currency]
        return f"{amount} {from_currency} = {converted:.2f} {to_currency}"

    agent = create_deep_agent(model=_make_model(), tools=[get_weather, convert_currency])

    result = agent.invoke({
        "messages": [{
            "role": "user",
            "content": (
                "What's the weather in Tokyo? "
                "Also convert 100 USD to JPY."
            ),
        }]
    })
    print(result["messages"][-1].content)


# ──────────────────────────────────────────────────────────────────────────────
# 2. SYSTEM PROMPT
#    Shape the agent's persona and behaviour via a custom system prompt.
# ──────────────────────────────────────────────────────────────────────────────

def demo_system_prompt():
    print("\n" + "=" * 60)
    print("USE CASE 2: Custom System Prompt")
    print("=" * 60)

    SYSTEM = """\
You are a concise senior software architect.
- Answer only in bullet points.
- Always mention trade-offs.
- Keep responses under 150 words.
"""

    agent = create_deep_agent(model=_make_model(), system_prompt=SYSTEM)

    result = agent.invoke({
        "messages": [{
            "role": "user",
            "content": "Should I use REST or GraphQL for my new API?",
        }]
    })
    print(result["messages"][-1].content)


# ──────────────────────────────────────────────────────────────────────────────
# 3. STREAMING
#    Use .stream() to receive output token-by-token as it is generated.
# ──────────────────────────────────────────────────────────────────────────────

def demo_streaming():
    print("\n" + "=" * 60)
    print("USE CASE 3: Streaming")
    print("=" * 60)

    agent = create_deep_agent(model=_make_model())

    print("Streaming response:\n")
    for chunk in agent.stream(
        {"messages": [{"role": "user", "content": "Write a 3-sentence poem about AI."}]},
        stream_mode="messages",
    ):
        # chunk is a (message_chunk, metadata) tuple in stream_mode="messages"
        if isinstance(chunk, tuple):
            msg_chunk = chunk[0]
        else:
            msg_chunk = chunk
        if hasattr(msg_chunk, "content") and msg_chunk.content:
            print(msg_chunk.content, end="", flush=True)
    print()  # newline after stream ends


# ──────────────────────────────────────────────────────────────────────────────
# 4. STRUCTURED OUTPUT
#    Force the agent to respond as a validated Pydantic model.
# ──────────────────────────────────────────────────────────────────────────────

class BookRecommendation(BaseModel):
    title: str = Field(description="Book title")
    author: str = Field(description="Author name")
    genre: str = Field(description="Book genre")
    why_read: str = Field(description="One sentence explaining why to read it")
    difficulty: str = Field(description="Reading difficulty: Easy / Medium / Hard")


def demo_structured_output():
    print("\n" + "=" * 60)
    print("USE CASE 4: Structured Output")
    print("=" * 60)

    agent = create_deep_agent(
        model=_make_model(),
        response_format=BookRecommendation,
    )

    result = agent.invoke({
        "messages": [{
            "role": "user",
            "content": "Recommend one great book about systems thinking.",
        }]
    })

    # Content is a JSON string — parse it into a dict
    raw = result["messages"][-1].content
    data = json.loads(raw) if isinstance(raw, str) else raw
    print(f"Title     : {data['title']}")
    print(f"Author    : {data['author']}")
    print(f"Genre     : {data['genre']}")
    print(f"Why read  : {data['why_read']}")
    print(f"Difficulty: {data['difficulty']}")


# ──────────────────────────────────────────────────────────────────────────────
# 5. MULTI-TURN MEMORY (persistent conversation)
#    Use a checkpointer + thread_id to maintain state across multiple .invoke()
#    calls, enabling a real back-and-forth conversation.
# ──────────────────────────────────────────────────────────────────────────────

def demo_multi_turn():
    print("\n" + "=" * 60)
    print("USE CASE 5: Multi-turn Memory")
    print("=" * 60)

    checkpointer = MemorySaver()
    agent = create_deep_agent(model=_make_model(), checkpointer=checkpointer)
    config = {"configurable": {"thread_id": "demo-thread-42"}}

    turns = [
        "My name is Alex and I love Python.",
        "What's my name and favourite language?",
        "Suggest one Python project idea for me.",
    ]

    for user_msg in turns:
        print(f"\nUser : {user_msg}")
        result = agent.invoke(
            {"messages": [{"role": "user", "content": user_msg}]},
            config=config,
        )
        print(f"Agent: {result['messages'][-1].content}")


# ──────────────────────────────────────────────────────────────────────────────
# 6. HUMAN-IN-THE-LOOP (interrupt_on)
#    Pause execution before a "dangerous" tool and let the user approve/reject.
# ──────────────────────────────────────────────────────────────────────────────

@tool
def delete_record(record_id: str) -> str:
    """Permanently delete a database record by ID."""
    return f"Record {record_id} deleted."


def demo_human_in_the_loop():
    print("\n" + "=" * 60)
    print("USE CASE 6: Human-in-the-Loop (interrupt_on)")
    print("=" * 60)

    checkpointer = MemorySaver()
    agent = create_deep_agent(
        model=_make_model(),
        tools=[delete_record],
        interrupt_on={"delete_record": True},   # pause BEFORE this tool runs
        checkpointer=checkpointer,
    )
    config = {"configurable": {"thread_id": "hitl-thread-1"}}

    # First call — agent will pause when it tries to call delete_record
    result = agent.invoke(
        {"messages": [{"role": "user", "content": "Delete record ID-9999."}]},
        config=config,
        version="v2",
    )

    if hasattr(result, "interrupts") and result.interrupts:
        interrupt = result.interrupts[0].value
        print(f"[INTERRUPT] Agent wants to call: {interrupt}")
        answer = input("Approve? (yes/no): ").strip().lower()
        decision = [{"type": "approve" if answer == "yes" else "reject"}]
        result = agent.invoke(
            Command(resume={"decisions": decision}),
            config=config,
            version="v2",
        )
        print(result["messages"][-1].content)
    else:
        # No interrupt raised — print the result directly
        print(result["messages"][-1].content)


# ──────────────────────────────────────────────────────────────────────────────
# 7. SUB-AGENTS
#    Delegate specialised tasks to child agents with their own tools & prompts.
# ──────────────────────────────────────────────────────────────────────────────

def calculate(expression: str) -> str:
    """Safely evaluate a mathematical expression and return the result."""
    try:
        allowed = set("0123456789+-*/(). ")
        if not all(c in allowed for c in expression):
            return "Invalid expression"
        return str(eval(expression))  # noqa: S307 — safe subset enforced above
    except Exception as e:
        return f"Error: {e}"


def lookup_fact(topic: str) -> str:
    """Return a short mock fact about a topic."""
    facts = {
        "python": "Python was created by Guido van Rossum and released in 1991.",
        "ai": "The term 'Artificial Intelligence' was coined by John McCarthy in 1956.",
        "langchain": "LangChain was founded in 2022 by Harrison Chase.",
    }
    return facts.get(topic.lower(), f"No fact found for '{topic}'.")


def demo_subagents():
    print("\n" + "=" * 60)
    print("USE CASE 7: Sub-agents")
    print("=" * 60)

    math_subagent = {
        "name": "math-agent",
        "description": "Handles all arithmetic and mathematical calculations.",
        "system_prompt": "You are a precise math assistant. Always show your work.",
        "tools": [calculate],
    }

    facts_subagent = {
        "name": "facts-agent",
        "description": "Looks up factual information on a topic.",
        "system_prompt": "You are a knowledgeable facts assistant. Be concise.",
        "tools": [lookup_fact],
    }

    agent = create_deep_agent(
        model=_make_model(),
        system_prompt=(
            "You are an orchestrator. Delegate maths to math-agent "
            "and fact lookups to facts-agent. Summarise the combined result."
        ),
        subagents=[math_subagent, facts_subagent],
    )

    result = agent.invoke({
        "messages": [{
            "role": "user",
            "content": (
                "What is (123 * 456) + 789? "
                "Also tell me a fact about Python."
            ),
        }]
    })
    print(result["messages"][-1].content)


# ──────────────────────────────────────────────────────────────────────────────
# MAIN — run all demos in order
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Comment out any section you don't want to run
    demo_custom_tools()
    demo_system_prompt()
    demo_streaming()
    demo_structured_output()
    demo_multi_turn()
    demo_human_in_the_loop()   # interactive — uncomment to try
    demo_subagents()
