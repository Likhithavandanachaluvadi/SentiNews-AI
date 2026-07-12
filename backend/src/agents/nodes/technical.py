import logging
import time
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from src.agents.state import ResearchState
from src.agents.schemas import ConfidenceMetrics, TechnicalOutput
from src.core.config import settings
from src.core.debug_logger import debug_logger, NodeStatus

logger = logging.getLogger(__name__)

llm_analyst = ChatGroq(
    temperature=0.1,
    model_name="llama-3.1-8b-instant",
    api_key=settings.GROQ_API_KEY
) if settings.GROQ_API_KEY else None

technical_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a SEBI-compliant Technical Analyst. Format as a valid JSON object matching TechnicalOutput.
RULES:
1. Use ONLY provided context metrics. Never guess or calculate yourself.
2. Never use BUY, SELL, or TARGET PRICE. Use neutral terms (e.g. "Constructive Setup").
3. Never guarantee returns or movements.
4. If data is missing, output "Data Unavailable".
5. You MUST NEVER generate, estimate, or modify any technical metrics, RSI levels, or SMA figures. Every numeric value or trend indicator in your response MUST exactly match the values provided in the Context.
6. CRITICAL RULE: In all narrative strings (such as "summary", "trend_analysis", "momentum_analysis", "support", "resistance"), you MUST NEVER include any specific numeric values, percentages, currencies, or ratios (e.g. do not write "RSI of 65", "SMA at ₹200.00"). Instead, write qualitative descriptions (e.g. "RSI is in overbought territory", "price is trading above key short-term moving averages") and refer the reader to the structured Technical Indicators and Key Statistics section for all numerical values.

Example JSON:
{{
  "summary": "Technical summary",
  "trend_analysis": "Trend details",
  "momentum_analysis": "Momentum details",
  "key_levels": {{
    "support": "Support levels",
    "resistance": "Resistance levels"
  }},
  "citations": [
    {{
      "source_name": "Source",
      "metric": "Metric",
      "value": "Value",
      "trust_tier": "Tier 1"
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

async def technical_node(state: ResearchState) -> dict:
    """
    Generates technical analysis structured output.
    CRITICAL: Never returns None/null for technical_report.=
    If analysis fails, returns a partial output with low confidence.
    """
    start_time = time.time()
    query = state.get("query", "")
    existing_report = state.get("technical_report")
    intent = state.get("intent") or {}
    primary_intent = intent.get("primary_intent", "GENERALIZED")

    planner_layout = intent.get("planner_layout", {})
    required_agents = planner_layout.get("required_agents", [])

    if "technical" not in required_agents or primary_intent in ("EDUCATIONAL", "RESTRICTED_ADVISORY", "MACROECONOMIC", "SENTIMENT_PULSE", "COMPARISON", "MARKET_OVERVIEW"):
        skipped = existing_report or {
            "status": "skipped",
            "summary": "Technical analysis skipped for this query type.",
            "trend_analysis": "Analysis skipped for this query type.",
            "momentum_analysis": "Analysis skipped for this query type.",
            "key_levels": {
                "support": "Analysis skipped for this query type.",
                "resistance": "Analysis skipped for this query type."
            },
            "citations": [],
            "confidence": {
                "confidence_score": 0,
                "uncertainty_level": "High",
                "confidence_reasoning": "Intent-aware workflow skipped technical analysis.",
                "missing_data_points": ["Technical workflow not required"],
            },
        }
        debug_logger.log_node_execution(
            node_name="technical",
            status=NodeStatus.SKIPPED,
            input_state={"query": query, "primary_intent": primary_intent},
            output_state={"status": "skipped"},
            execution_ms=0,
            missing_fields=["technical_report"],
        )
        return {"technical_report": skipped}
    
    if not llm_analyst:
        logger.warning("Groq API Key missing.")
        debug_logger.log_node_execution(
            node_name="technical",
            status=NodeStatus.FAILED,
            input_state={"query": query},
            output_state={},
            execution_ms=0,
            error_message="LLM not available",
        )
        if existing_report:
            return {"technical_report": existing_report}
        fallback = {
            "summary": "Technical analysis unavailable - LLM offline",
            "trend_analysis": "Data Unavailable",
            "momentum_analysis": "Data Unavailable",
            "key_levels": "Data Unavailable",
            "citations": [],
            "confidence": {
                "confidence_score": 0,
                "uncertainty_level": "High",
                "confidence_reasoning": "LLM service unavailable",
                "missing_data_points": ["All technical data"],
            }
        }
        return {"technical_report": fallback}

    try:
        context_str = state.get("prompt_context") or "\n".join(
            [str(c) for c in state.get("context", [])]
        )

        structured_llm = llm_analyst.with_structured_output(
            TechnicalOutput,
            method="json_mode"
        )

        chain = technical_prompt | structured_llm

        try:
            report = await chain.ainvoke({
                "query": query,
                "context": context_str,
            })

        except Exception as e:

            logger.warning(
                f"Structured output failed: {e}"
            )

            report = TechnicalOutput(
                summary="Technical analysis is temporarily unavailable.",
                trend_analysis="Data Unavailable",
                momentum_analysis="Data Unavailable",
                key_levels="Data Unavailable",
                citations=[],
                confidence=ConfidenceMetrics(
                    confidence_score=30,
                    uncertainty_level="High",
                    confidence_reasoning="Groq structured output failed.",
                    missing_data_points=[
                        "Technical Analysis"
                    ]
                )
            )

        execution_ms = int((time.time() - start_time) * 1000)

        confidence = (
            report.confidence.confidence_score
            if report.confidence
            else 50
        )

        debug_logger.log_node_execution(
            node_name="technical",
            status=NodeStatus.SUCCESS,
            input_state={
                "query": query
            },
            output_state={
                "confidence": confidence
            },
            execution_ms=execution_ms,
            confidence_score=confidence,
        )

        logger.info(
            f"Technical analysis completed. Confidence: {confidence}"
        )

        print("=" * 80)
        print("TECHNICAL REPORT")
        print(report.model_dump())
        print("=" * 80)

        return {
            "technical_report": report.model_dump()
        }

    except Exception as e:

        execution_ms = int((time.time() - start_time) * 1000)

        logger.error(
            f"Technical analysis failed: {e}"
        )

        debug_logger.log_node_execution(
            node_name="technical",
            status=NodeStatus.FAILED,
            input_state={
                "query": query
            },
            output_state={},
            execution_ms=execution_ms,
            error_message=str(e),
        )

        if existing_report:
            return {
                "technical_report": existing_report
            }

        fallback = {
            "summary": "Technical analysis error",
            "trend_analysis": "Data Unavailable",
            "momentum_analysis": "Data Unavailable",
            "key_levels": "Data Unavailable",
            "citations": [],
            "confidence": {
                "confidence_score": 10,
                "uncertainty_level": "High",
                "confidence_reasoning": f"Error: {str(e)[:80]}",
                "missing_data_points": [
                    "Error during analysis"
                ],
            }
        }

        return {
            "technical_report": fallback
        }
