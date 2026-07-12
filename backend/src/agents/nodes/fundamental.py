from itertools import chain
import logging
import time
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from src.agents.state import ResearchState
from src.agents.schemas import FundamentalOutput
from src.core.config import settings
from src.core.debug_logger import debug_logger, NodeStatus

logger = logging.getLogger(__name__)

llm_analyst = ChatGroq(
    temperature=0.1,
    model_name="llama-3.1-8b-instant",
    api_key=settings.GROQ_API_KEY
)if settings.GROQ_API_KEY else None

fundamental_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a senior, SEBI-compliant Equity Research Analyst. Your goal is to help users understand companies and financial concepts, speaking naturally without technical jargon. Provide insightful, conversational, and highly objective fundamental analysis based ONLY on the provided verified Context.

Format the response as a JSON object matching the FundamentalOutput schema.

CRITICAL RULES:
1. SEBI Compliance & Balanced Advice:
   - Never recommend buying or selling (do not use "BUY", "SELL", "HOLD", or "TARGET PRICE").
   - Instead, explain the strengths, weaknesses, risks, and uncertainties of the company.
   - Never guarantee returns or use speculative words like "sure gain" or "guaranteed profit".
   - Avoid generic investment advice. Maintain a balanced, objective, and neutral tone.

2. Strict Numeric Grounding & Evidence Reasoning:
   - Always reason from verified evidence. Never generate unsupported conclusions.
   - You MAY and SHOULD include specific financial numbers, percentages, and metrics in your narratives (e.g., "ROE of 22%", "Debt-to-Equity of 0.15") to support your points.
   - However, every numerical value, margin, ratio, or percentage you write MUST match a value in the provided Context exactly.
   - You MUST NEVER estimate, extrapolate, calculate, or invent any financial numbers.
   - If a metric supports your conclusion, explicitly explain why and what it means (answer: "Why does this matter?").
   - Connect related metrics together (e.g., link margin trends to return ratios, or leverage structures to valuation multiples) to provide synthesized reasoning.
   - Encourage macroeconomic or industry context (e.g., interest rate cycles, inflation pressures, sector headwinds) when relevant and supported by the context.

3. Conversational Tone & Banned Phrasing:
   - Write naturally, like a human senior research analyst explaining details in a briefing.
   - You must NOT use chatbot transition clichés or robotic phrasing. Banned phrases include:
     * "Based on the context" or "Based on the provided information"
     * "Analyzing the data" or "Analyzing the fundamentals"
     * "This indicates", "This reflects", "This signifies", "This demonstrates" (vary sentence structures; never start consecutive sentences with these)
     * "In conclusion", "To summarize", "Overall"
     * "Please refer to the structured statistics dashboard" or any dashboard references
   - Integrate metrics, business meanings, and risks fluidly. Do not use structural markers, forced headings, or template separations within the JSON fields. Write clear, continuous paragraphs.
   - If a JSON field (e.g., competitive_moat or financial_health) is irrelevant to the user's specific query, write a minimal, one-sentence transition or mark it as not applicable. Prioritize concise relevance over verbose filler content.

4. Conversational Continuity & Memory:
   - If the query is part of an ongoing conversation, adapt your response to build upon earlier turns.
   - Do NOT repeat baseline company overviews, stock descriptions, or dictionary definitions that were established in earlier turns.
   - Never introduce the target company name or sector repeatedly. Assume previous statements are common knowledge. Shift focus naturally.

5. Data Gaps & Professional Uncertainty Phrasing:
   - If a metric is missing, low confidence, or has provider conflicts, handle it naturally using professional research language.
   - Do NOT use robotic system-centric phrases (like "Data unavailable", "Confidence is low because metrics are missing").
   - Instead, use institutional research terms (e.g., "limited public disclosure on capital metrics restricts...", "discrepancies in provider reported valuations suggest...", "historical volatility in reporting limits...", "provider reported figures are conflicting...").

6. User Understanding First:
   - The primary objective is to help the user understand the company or financial concept.
   - If a concept might confuse a beginner (e.g., ROCE, Debt-to-Equity, FCF Yield), explain it briefly in simple language before continuing.

---
INTERNAL REASONING PIPELINE (Process Mentally Before Generating JSON Fields)
---------------------------------------------------------------------------
Before writing the value for any JSON field, mentally execute these steps:
1. Understand the user's question, intent, and previous conversation context.
2. Identify the verified facts and metrics in prompt_context relevant to this query.
3. Filter out and ignore unrelated metrics.
4. Interpret what the relevant facts mean for the company's fundamentals.
5. Separate facts from interpretation, ensuring no extrapolation.
6. Identify weak evidence, warnings, or missing metrics, and prepare to explain the uncertainty.
7. Write the conversational, adaptive responses into the JSON schema fields.

Note: The reasoning pipeline is internal. Do NOT output the reasoning steps or headings in the JSON fields.

Example JSON output structure (ensure keys exactly match these):
{{
  "summary": "Your conversational executive summary.",
  "financial_health": "Your conversational analysis of financial health.",
  "competitive_moat": "Your conversational analysis of the moat.",
  "key_factors": ["Factor 1", "Factor 2"],
  "citations": [
    {{
      "source_name": "Source Name",
      "metric": "Metric Name",
      "value": "Value String",
      "trust_tier": "Tier 1"
    }}
  ],
  "confidence": {{
    "confidence_score": 85,
    "uncertainty_level": "Low",
    "confidence_reasoning": "Reasoning for the confidence score.",
    "missing_data_points": []
  }}
}}"""),
    ("user", "Query: {query}\n\nContext:\n{context}")
])

async def fundamental_node(state: ResearchState) -> dict:
    """
    Generates fundamental analysis structured output.
    
    CRITICAL: Never returns None/null for fundamental_report.
    If analysis fails, returns a partial output with low confidence.
    """
    start_time = time.time()
    query = state.get("query", "")
    existing_report = state.get("fundamental_report")
    intent = state.get("intent") or {}
    primary_intent = intent.get("primary_intent", "GENERALIZED")
    secondary_intent = intent.get("secondary_intent", "NONE")
    ticker = state.get("ticker") or intent.get("extracted_ticker")
    has_stock_ticker = bool(ticker and str(ticker).strip())

    planner_layout = intent.get("planner_layout", {})
    required_agents = planner_layout.get("required_agents", [])

    if "fundamental" not in required_agents or primary_intent in ("EDUCATIONAL", "RESTRICTED_ADVISORY", "MACROECONOMIC", "SENTIMENT_PULSE", "MARKET_OVERVIEW", "STOCK_MOVEMENT"):
        skipped = existing_report or {
            "status": "skipped",
            "summary": "Fundamental analysis skipped for this query type.",
            "financial_health": "Analysis skipped for this query type.",
            "competitive_moat": "Analysis skipped for this query type.",
            "key_factors": [],
            "citations": [],
            "confidence": {
                "confidence_score": 0,
                "uncertainty_level": "High",
                "confidence_reasoning": "Intent-aware workflow skipped deep fundamentals.",
                "missing_data_points": ["Fundamental workflow not required"],
            },
        }
        debug_logger.log_node_execution(
            node_name="fundamental",
            status=NodeStatus.SKIPPED,
            input_state={"query": query, "primary_intent": primary_intent},
            output_state={"status": "skipped"},
            execution_ms=0,
            missing_fields=["fundamental_report"],
        )
        return {"fundamental_report": skipped}
    
    if not llm_analyst:
        logger.warning("Groq API Key missing.")
        
        debug_logger.log_node_execution(
            node_name="fundamental",
            status=NodeStatus.FAILED,
            input_state={"query": query, "context_items": len(state.get("context", []))},
            output_state={"fundamental_report": None},
            execution_ms=0,
            error_message="LLM not available",
        )
        
        # Return existing report if available, never return None
        if existing_report:
            return {"fundamental_report": existing_report}
        
        # Fallback: minimal report with low confidence
        fallback = {
            "summary": "Fundamental analysis unavailable - LLM service offline",
            "financial_health": "Data Unavailable",
            "competitive_moat": "Data Unavailable",
            "key_factors": [],
            "citations": [],
            "confidence": {
                "confidence_score": 0,
                "uncertainty_level": "High",
                "confidence_reasoning": "LLM service unavailable",
                "missing_data_points": ["All fundamental data"],
            }
        }
        return {"fundamental_report": fallback}

    try:
        context_str = state.get("prompt_context") or "\n".join(state.get("context", []))

        # Use structured output to enforce the FundamentalOutput schema
        structured_llm = llm_analyst.with_structured_output(FundamentalOutput, method="json_mode")
        chain = fundamental_prompt | structured_llm

        report: FundamentalOutput = await chain.ainvoke({
            "query": query,
            "context": context_str,
        })
    #     structured_llm = llm_analyst
    #     chain = fundamental_prompt | structured_llm

    #     report = await chain.ainvoke({
    # "query": query,
    # "context": context_str,
    #     })
    #     execution_ms = int((time.time() - start_time) * 1000)
    #     confidence = 50  # Placeholder confidence score
        
        execution_ms = int((time.time() - start_time) * 1000)
        # derive confidence if available on the response
        try:
            confidence = int(report.confidence.confidence_score)  # type: ignore
        except Exception:
            confidence = 50

        debug_logger.log_node_execution(
            node_name="fundamental",
            status=NodeStatus.SUCCESS,
            input_state={"query": query, "context_items": len(state.get("context", []))},
            output_state={"confidence": confidence, "citations": len(getattr(report, 'citations', []) or [])},
            execution_ms=execution_ms,
            citations_count=len(getattr(report, 'citations', []) or []),
            confidence_score=confidence,
        )
        
        logger.info(f"Fundamental analysis completed. Confidence: {confidence}")

        # Store as dict in state
        try:
            report_dict = report.model_dump()
        except Exception:
            # fallback if report is already a dict-like or string
            try:
                report_dict = dict(report)
            except Exception:
                report_dict = {"summary": str(report)}

        return {"fundamental_report": report_dict}
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        execution_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Fundamental analysis failed: {e}")
        
        debug_logger.log_node_execution(
            node_name="fundamental",
            status=NodeStatus.FAILED,
            input_state={"query": query, "context_items": len(state.get("context", []))},
            output_state={"error": str(e)},
            execution_ms=execution_ms,
            error_message=str(e),
        )
        
        # CRITICAL: Never return None. Return partial output with low confidence.
        if existing_report:
            return {"fundamental_report": existing_report}
        
        fallback = {
            "summary": "Fundamental analysis encountered an error",
            "financial_health": "Data Unavailable",
            "competitive_moat": "Data Unavailable",
            "key_factors": [],
            "citations": [],
            "confidence": {
                "confidence_score": 10,
                "uncertainty_level": "High",
                "confidence_reasoning": f"Analysis failed: {str(e)[:100]}",
                "missing_data_points": ["Error during analysis"],
            }
        }
        return {"fundamental_report": fallback}
