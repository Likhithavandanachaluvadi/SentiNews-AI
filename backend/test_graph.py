import asyncio
import os
import sys

# Ensure src is in the python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.agents.graph import research_app
from src.agents.state import ResearchState

async def test():
    print("Testing LangGraph execution for 'Analyze NVIDIA'...")
    initial_state = ResearchState(
        query="Analyze NVIDIA",
        context=[],
        analyst_reports=[],
        final_report=""
    )
    
    try:
        result = await research_app.ainvoke(initial_state)
        print("\n--- FINAL REPORT ---")
        print(result.get("final_report"))
        print("\nTest passed successfully!")
    except Exception as e:
        print(f"\nTest failed with error: {e}")

if __name__ == "__main__":
    asyncio.run(test())
