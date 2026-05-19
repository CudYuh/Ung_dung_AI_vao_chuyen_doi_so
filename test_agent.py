import asyncio
import os
from langchain_openai import ChatOpenAI
from langchain.tools import tool
from langchain.agents import create_agent

os.environ["OPENAI_API_KEY"] = "sk-placeholder"

@tool
def dummy_tool(query: str) -> str:
    """Dummy tool"""
    return "Dummy"

async def main():
    llm = ChatOpenAI(model="gpt-4o-mini")
    agent = create_agent(llm, tools=[dummy_tool], system_prompt="You are a helpful assistant.")
    
    # We don't have a real API key so we shouldn't ainvoke it, just print it
    print("Agent created successfully.", agent)

asyncio.run(main())
