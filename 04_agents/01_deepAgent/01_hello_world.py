"""
Hello World with DeepAgent using Azure OpenAI
Based on: https://github.com/langchain-ai/deepagents
"""

from dotenv import load_dotenv
import os

load_dotenv()

from langchain_openai import ChatOpenAI, AzureChatOpenAI
from deepagents import create_deep_agent

# Azure AI Foundry endpoints expose an OpenAI-compatible /openai/v1 base URL.
# Use ChatOpenAI (not AzureChatOpenAI) and pass the endpoint as base_url.
model = ChatOpenAI(
    model=os.environ["AZURE_OPENAI_DEPLOYMENT"],
    base_url=os.environ["AZURE_OPENAI_ENDPOINT"],
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
)

# Create the deep agent (comes with built-in tools: filesystem, shell, planning, etc.)
agent = create_deep_agent(model=model)

# Invoke the agent with a simple task
result = agent.invoke({
    "messages": [
        {
            "role": "user",
            "content": "Say hello and briefly explain what you can do as a DeepAgent.",
        }
    ]
})

# Print the final response
print(result["messages"][-1].content)
