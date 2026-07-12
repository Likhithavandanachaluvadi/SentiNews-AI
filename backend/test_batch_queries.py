import asyncio
import os
import sys

# Ensure backend root is in the python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.agents.graph import research_app
from src.agents.state import ResearchState

queries = [
    "What were the key takeaways from NVIDIA's latest quarterly report?",
    "Analyze NVIDIA.",
    "Explain EBITDA.",
    "Compare NVIDIA and AMD.",
    "Latest Tesla news.",
    "Explain CUDA.",
    "Business model of Amazon.",
    "Why is Reliance falling?",
    "What is PE Ratio?",
    "Should I buy Infosys?"
]

async def run_queries():
    print("Starting query pipeline analysis...\n")
    for idx, q in enumerate(queries, 1):
        print(f"=== QUERY {idx}: {q} ===")
        state = ResearchState(
            query=q,
            context=[],
            analyst_reports=[],
            final_report=""
        )
        try:
            res = await research_app.ainvoke(state)
            intent_dict = res.get("intent") or {}
            primary = intent_dict.get("primary_intent", "GENERALIZED")
            ticker = res.get("ticker", "N/A")
            layout = intent_dict.get("planner_layout", {})
            sections = layout.get("sections", [])
            print(f"  Resolved Ticker : {ticker}")
            print(f"  Primary Intent  : {primary}")
            print(f"  Planner Sections: {sections}")
            print(f"  Report Excerpt  : {str(res.get('final_report', {}).get('executive_summary', ''))[:150]}...")
        except Exception as e:
            print(f"  Failed with error: {e}")
        print("-" * 50)
        # Sleep to avoid Groq rate limit issues between sequential runs
        await asyncio.sleep(5.0)

if __name__ == "__main__":
    asyncio.run(run_queries())
