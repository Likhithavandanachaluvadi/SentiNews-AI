import asyncio
import os
import sys

# Ensure src is in the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agents.graph import research_app
from src.agents.state import ResearchState

async def test_comparison():
    queries = [
        "Compare ICICI Bank with HDFC Bank",
        "Compare NVIDIA with AMD",
        "Compare Infosys and TCS",
        "Compare Apple and Microsoft",
        "Compare Reliance Industries and Adani Enterprises"
    ]
    
    for q in queries:
        print(f"\n==================================================")
        print(f"Testing Query: '{q}'")
        print(f"==================================================")
        
        initial_state = ResearchState(
            query=q,
            context=[],
            analyst_reports=[],
            final_report=""
        )
        
        try:
            result = await research_app.ainvoke(initial_state)
            intent = result.get("intent", {})
            primary_intent = intent.get("primary_intent", "N/A")
            planner_layout = intent.get("planner_layout", {})
            sections = planner_layout.get("sections", [])
            
            print(f"Primary Intent: {primary_intent}")
            print(f"Planner Sections: {sections}")
            print("Final Report Synthesized successfully!")
            
        except Exception as e:
            print(f"Test failed with error: {e}")

if __name__ == "__main__":
    asyncio.run(test_comparison())
