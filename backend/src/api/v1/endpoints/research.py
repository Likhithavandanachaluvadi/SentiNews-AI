from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.agents.graph import research_app
from src.agents.state import ResearchState

router = APIRouter()

class ResearchRequest(BaseModel):
    query: str

class ResearchResponse(BaseModel):
    query: str
    report: str
    
@router.post("/analyze", response_model=ResearchResponse)
async def analyze_query(request: ResearchRequest):
    """
    Kicks off the Agentic RAG workflow to generate a financial research report.
    """
    try:
        # Initialize state
        initial_state = ResearchState(
            query=request.query,
            context=[],
            analyst_reports=[],
            final_report=""
        )
        
        # Run graph
        final_state = await research_app.ainvoke(initial_state)
        
        return ResearchResponse(
            query=final_state["query"],
            report=final_state.get("final_report", "Error: No report generated.")
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph execution failed: {str(e)}")
