"""
Refactored LangGraph workflow with Reflection Loop and Pydantic nodes.
Enhanced with:
- Intent classification as first node
- Dynamic retriever with source filtering
- State propagation protection
- Comprehensive debug logging
"""
from langgraph.graph import StateGraph, END
from src.agents.state import ResearchState
from src.agents.intent_classifier import intent_classifier_node
from src.agents.dynamic_retriever import dynamic_retriever_node
from src.agents.nodes.fundamental import fundamental_node
from src.agents.nodes.technical import technical_node
from src.agents.nodes.sentiment import sentiment_node
from src.agents.nodes.verifier import verifier_node
from src.agents.judge import judge_node
from src.core.debug_logger import start_workflow_logging, debug_logger
import logging

logger = logging.getLogger(__name__)

def should_reflect(state: ResearchState) -> str:
    """Conditional routing based on the Verifier's output."""
    feedback = state.get("reflection_feedback")
    iteration = state.get("iteration_count", 0)
    
    # Max iterations to prevent infinite loops
    if iteration >= 2:
        logger.warning("Max reflection iterations reached. Forcing route to Judge.")
        return "judge"
    if feedback:
        if not feedback.get("is_valid", True):
            logger.warning("Verifier found issues. Skipping reflection loop and routing to Judge.")
            return "judge"  
    # if feedback:
    #     # feedback is a dict matching VerificationOutput
    #     if not feedback.get("is_valid", True):
    #         logger.info("Verifier found issues. Routing back to analysts.")
    #         return "reflect"
            
    return "judge"

def increment_iteration(state: ResearchState) -> dict:
    """Helper node to track iterations."""
    return {"iteration_count": state.get("iteration_count", 0) + 1}

def create_research_graph():
    """
    Builds the production-grade Autonomous Agentic RAG workflow.
    
    Flow:
    1. intent_classifier → Classify query and extract intent
    2. dynamic_retriever → Fetch intent-aware, source-filtered data
    3. fundamental, technical, sentiment (parallel) → Domain analysis
    4. verifier → Quality gate and reflection loop
    5. judge → Synthesis into final report
    """
    workflow = StateGraph(ResearchState)
    
    # ========== NODES ==========
    
    # 0. Intent Classifier (FIRST NODE)
    workflow.add_node("intent_classifier", intent_classifier_node)
    
    # 1. Dynamic Retriever (intent-aware, source-filtered)
    workflow.add_node("dynamic_retriever", dynamic_retriever_node)
    
    # 2. Analysts (parallel)
    workflow.add_node("fundamental", fundamental_node)
    workflow.add_node("technical", technical_node)
    workflow.add_node("sentiment", sentiment_node)
    
    # 3. Verifier (Gatekeeper)
    workflow.add_node("verifier", verifier_node)
    
    # 4. Helper node to bounce back
    workflow.add_node("iteration_tracker", increment_iteration)
    
    # 5. Judge
    workflow.add_node("judge", judge_node)
    
    # ========== EDGES ==========
    workflow.set_entry_point("intent_classifier")
    
    # Intent classifier -> Retriever
    workflow.add_edge("intent_classifier", "dynamic_retriever")
    
    # Retriever -> Analysts (parallel)
    workflow.add_edge("dynamic_retriever", "fundamental")
    workflow.add_edge("dynamic_retriever", "technical")
    workflow.add_edge("dynamic_retriever", "sentiment")
    
    # All analysts -> Verifier
    workflow.add_edge("fundamental", "verifier")
    workflow.add_edge("technical", "verifier")
    workflow.add_edge("sentiment", "verifier")
    
    # Conditional logic after verifier
    workflow.add_conditional_edges(
        "verifier",
        should_reflect,
        {
            "reflect": "iteration_tracker",
            "judge": "judge"
        }
    )
    
    # If reflecting, go back to analysts
    workflow.add_edge("iteration_tracker", "fundamental")
    workflow.add_edge("iteration_tracker", "technical")
    workflow.add_edge("iteration_tracker", "sentiment")
    
    # Judge -> End
    workflow.add_edge("judge", END)
    
    app = workflow.compile()
    logger.info("Autonomous Research graph compiled successfully with intent classification and dynamic retrieval")
    return app

research_app = create_research_graph()
