import logging
import time
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from src.agents.state import ResearchState
from src.agents.schemas import SentimentOutput
from src.core.config import settings
from src.core.debug_logger import debug_logger, NodeStatus

logger = logging.getLogger(__name__)

llm_analyst = ChatGroq(
    temperature=0.1,
    model_name="llama-3.1-8b-instant",
    api_key=settings.GROQ_API_KEY
) if settings.GROQ_API_KEY else None

sentiment_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a SEBI-compliant Sentiment Analyst. Format response as JSON matching SentimentOutput.
RULES:
1. Never use BUY, SELL, or TARGET PRICE.
2. Rate sentiment strictly on provided news language.
3. If data is missing, output "Data Unavailable".
4. CRITICAL RULE: In all narrative strings (such as "summary", "key_themes"), you MUST NEVER include any specific numeric values, percentages, currencies, or ratios. Instead, write qualitative descriptions (e.g. "highly positive investor sentiment", "recent earnings beat") and refer the reader to the structured dashboard for all numerical values.

Example JSON:
{{
  "summary": "Sentiment summary",
  "sentiment_score": 75,
  "key_themes": ["Theme A"],
  "citations": [
    {{
      "source_name": "Source",
      "metric": "Metric",
      "value": "Value",
    }}
  ],
  "confidence": {{
    "confidence_score": 80,
    "uncertainty_level": "Low",
    "confidence_reasoning": "Reasoning",
    "missing_data_points": []
  }}
}}"""),
    ("user", "Query: {query}\n\nContext:\n{context}")
])

async def sentiment_node(state: ResearchState) -> dict:
    """
    Generates sentiment analysis structured output.
    CRITICAL: Never returns None/null for sentiment_report.
    If analysis fails, returns a partial output with low confidence.
    """
    start_time = time.time()
    query = state.get("query", "")
    existing_report = state.get("sentiment_report")
    intent = state.get("intent") or {}
    primary_intent = intent.get("primary_intent", "GENERALIZED")

    planner_layout = intent.get("planner_layout", {})
    required_agents = planner_layout.get("required_agents", [])

    if "sentiment" not in required_agents or primary_intent in ("EDUCATIONAL", "RESTRICTED_ADVISORY", "MACROECONOMIC", "MARKET_OVERVIEW", "STOCK_MOVEMENT", "COMPARISON"):
        skipped = existing_report or {
            "status": "skipped",
            "summary": "Sentiment analysis skipped for this query type.",
            "sentiment_score": 50,
            "key_themes": [],
            "citations": [],
            "confidence": {
                "confidence_score": 0,
                "uncertainty_level": "High",
                "confidence_reasoning": "Intent-aware workflow skipped sentiment retrieval.",
                "missing_data_points": ["Sentiment workflow not required"],
            },
        }
        debug_logger.log_node_execution(
            node_name="sentiment",
            status=NodeStatus.SKIPPED,
            input_state={"query": query, "primary_intent": primary_intent},
            output_state={"status": "skipped"},
            execution_ms=0,
            missing_fields=["sentiment_report"],
        )
        return {"sentiment_report": skipped}
    
    if not llm_analyst:
        logger.warning("Groq API Key missing.")
        debug_logger.log_node_execution(
            node_name="sentiment",
            status=NodeStatus.FAILED,
            input_state={"query": query},
            output_state={},
            execution_ms=0,
            error_message="LLM not available",
        )
        if existing_report:
            return {"sentiment_report": existing_report}
        fallback = {
            "summary": "Sentiment analysis unavailable - LLM offline",
            "sentiment_score": 50,
            "key_themes": [],
            "citations": [],
            "confidence": {
                "confidence_score": 0,
                "uncertainty_level": "High",
                "confidence_reasoning": "LLM service unavailable",
                "missing_data_points": ["All news data"],
            }
        }
        return {"sentiment_report": fallback}

    try:
        context_str = state.get("prompt_context") or "\n".join([str(c) for c in state.get("context", []) if "News" in str(c) or "[" in str(c)])
        if not context_str.strip():
            context_str = "No recent news available."
            
        structured_llm = llm_analyst.with_structured_output(SentimentOutput, method="json_mode")
        chain = sentiment_prompt | structured_llm

        report: SentimentOutput = await chain.ainvoke({
            "query": query,
            "context": context_str,
        })
        
        execution_ms = int((time.time() - start_time) * 1000)
        confidence = report.confidence.confidence_score if report.confidence else 0
        
        debug_logger.log_node_execution(
            node_name="sentiment",
            status=NodeStatus.SUCCESS,
            input_state={"query": query},
            output_state={"confidence": confidence},
            execution_ms=execution_ms,
            confidence_score=confidence,
        )
        
        logger.info(f"Sentiment analysis completed. Confidence: {confidence}")
        return {"sentiment_report": report.model_dump()}

    except Exception as e:
        execution_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Sentiment analysis failed: {e}")
        
        debug_logger.log_node_execution(
            node_name="sentiment",
            status=NodeStatus.FAILED,
            input_state={"query": query},
            output_state={},
            execution_ms=execution_ms,
            error_message=str(e),
        )
        
        if existing_report:
            return {"sentiment_report": existing_report}
        
        fallback = {
            "summary": "Sentiment analysis error",
            "sentiment_score": 50,
            "key_themes": [],
            "citations": [],
            "confidence": {
                "confidence_score": 10,
                "uncertainty_level": "High",
                "confidence_reasoning": f"Error: {str(e)[:80]}",
                "missing_data_points": ["Error during analysis"],
            }
        }
        return {"sentiment_report": fallback}
