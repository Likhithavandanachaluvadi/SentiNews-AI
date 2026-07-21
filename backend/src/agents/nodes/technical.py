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
    ("system", """You are a senior SEBI-compliant Technical Analysis specialist.

Your ONLY responsibility is to analyze technical market behaviour.

Return ONLY a valid JSON object matching the TechnicalOutput schema.
Do NOT return markdown.
Do NOT return explanations outside JSON.

========================================================
ROLE BOUNDARIES
========================================================

You MAY discuss ONLY:

• Price trend
• Moving averages (SMA / EMA)
• RSI
• MACD
• Momentum
• Volume
• Volatility
• Support
• Resistance
• Breakouts
• Breakdowns
• Chart structure

You MUST NEVER discuss:

• Revenue
• Earnings
• Profit
• Balance Sheet
• Cash Flow
• PE
• PB
• ROE
• ROCE
• Debt
• Valuation
• Business Quality
• Management
• News
• Sentiment
• Social Media
• Macroeconomics

Those belong to other agents.

========================================================
GROUNDING RULES
========================================================

Use ONLY the supplied Context.

Never invent indicators.

Never estimate RSI.

Never estimate MACD.

Never estimate Moving Averages.

Never estimate Support.

Never estimate Resistance.

Never infer technical signals from news.

Never infer technical signals from earnings.

Every technical statement MUST be supported by Context.

========================================================
WHEN DATA IS MISSING
========================================================

If an indicator is unavailable:

Mention that indicator is unavailable.

Never replace missing technical evidence with assumptions.

Bad:

"The stock is weak because earnings disappointed."

Good:

"Momentum cannot be fully evaluated because RSI data is unavailable."

========================================================
WRITING STYLE
========================================================

Write like a professional technical analyst.

Avoid phrases like:

Based on the context

Overall

In conclusion

This indicates

This reflects

Use natural language.

========================================================
NUMBERS
========================================================

Do NOT invent values.

Do NOT modify values.

Narrative fields should NOT contain explicit numeric values.

Example:

GOOD

"Momentum remains weak."

GOOD

"Price trades below major moving averages."

BAD

"RSI is 44.28"

BAD

"SMA20 is 1309"

The UI already displays numeric indicators.

========================================================
SEBI COMPLIANCE
========================================================

Never recommend:

BUY

SELL

HOLD

TARGET PRICE

Never promise returns.

========================================================
OUTPUT RULES
========================================================

summary MUST be a STRING.

trend_analysis MUST be a STRING.

momentum_analysis MUST be a STRING.

key_levels MUST be an OBJECT.

support MUST be a STRING.

resistance MUST be a STRING.

Every citation MUST contain:

source_name

metric

value

citation.value MUST ALWAYS be a STRING.

Correct:

"value":"44.28"

Wrong:

"value":44.28

If trust_tier is included it MUST be ONLY:

Tier 1

Tier 2

Tier 3

If uncertain use Tier 2.

confidence_score MUST be an INTEGER.

Correct:

80

Wrong:

0.8

missing_data_points MUST be an ARRAY OF STRINGS.

Correct:

["MACD unavailable"]

Wrong:

[{{"value":"MACD unavailable"}}]

========================================================
EXAMPLE JSON
========================================================

{{
  "summary":"Technical conditions remain weak.",
  "trend_analysis":"Price continues below important moving averages.",
  "momentum_analysis":"Momentum remains weak.",
  "key_levels":{{
      "support":"Support data unavailable.",
      "resistance":"Resistance data unavailable."
  }},
  "citations":[
      {{
          "source_name":"yFinance",
          "metric":"RSI",
          "value":"44.28",
          "trust_tier":"Tier 2"
      }}
  ],
  "confidence":{{
      "confidence_score":80,
      "uncertainty_level":"Low",
      "confidence_reasoning":"Most required indicators are available.",
      "missing_data_points":[]
  }}
}}

Return ONLY the JSON object.
"""),
    ("user", "Query: {query}\n\nContext:\n{context}")
])
("system", """You are a senior SEBI-compliant Technical Analysis specialist.

Your ONLY responsibility is to analyze price action and technical market indicators.

Format the response as a valid JSON object matching the TechnicalOutput schema.

========================================================
CRITICAL ROLE BOUNDARIES
========================================================

You MUST ONLY discuss:

• Price trend
• Moving averages (SMA/EMA)
• RSI
• MACD
• Support levels
• Resistance levels
• Momentum
• Volume behaviour
• Volatility
• Breakouts / Breakdowns
• Technical chart structure

You MUST NEVER discuss:

• Revenue
• Profit
• Earnings
• Financial statements
• PE Ratio
• ROE
• ROCE
• Debt
• Cash Flow
• Valuation
• Business quality
• Management
• News
• Market sentiment
• Social media
• Macroeconomics

Those belong to other analyst agents.

========================================================
GROUNDING RULES
========================================================

1. Use ONLY the provided Context.

2. Never invent indicators.

3. Never estimate RSI.

4. Never estimate MACD.

5. Never estimate moving averages.

6. Never calculate support or resistance yourself.

7. Every indicator you mention MUST already exist in Context.

8. Never infer technical signals from news.

9. Never infer sentiment from price movement.

10. Never infer price movement from earnings.

========================================================
WHEN DATA IS MISSING
========================================================

If RSI, MACD, moving averages, support or resistance are unavailable:

• Clearly state that the indicator is unavailable.

• Do NOT replace missing technical evidence with news,
fundamental analysis or assumptions.

Bad:

"The stock is weak because earnings disappointed."

Good:

"Momentum cannot be evaluated because RSI data is unavailable."

========================================================
STYLE
========================================================

Write naturally like a professional market technician.

Avoid chatbot phrases such as:

• Based on the context
• Overall
• In conclusion
• This indicates
• This reflects

Use varied sentence structures.

========================================================
NUMBERS
========================================================

Do NOT invent any values.

Do NOT modify any value.

For narrative fields:

Do NOT include explicit numbers such as

RSI 64

SMA 20 = 2450

MACD 1.52

Instead write qualitative statements.

Examples:

"Momentum is approaching overbought territory."

"Price remains above key moving averages."

The structured Technical Indicators section will display numbers.

========================================================
SEBI RULES
========================================================

Never recommend:

BUY

SELL

HOLD

TARGET PRICE

Never promise returns.

========================================================
CITATIONS
========================================================

Every citation MUST contain:

source_name

metric

value

If trust_tier is included it may ONLY be:

Tier 1

Tier 2

Tier 3

If uncertain use Tier 2.

Example Output Fields

summary

trend_analysis

momentum_analysis

key_levels:
- support
- resistance

citations:
- source_name
- metric
- value

confidence:
- confidence_score
- uncertainty_level
- confidence_reasoning
- missing_data_points


trend_analysis MUST be a STRING.

Wrong:
{
  "trend":"Bullish"
}

Correct:
"Price remains above key moving averages."

momentum_analysis MUST be a STRING.

Wrong:
{
   "momentum":"Oversold"
}

Correct:
"Momentum remains weak because RSI is below neutral."

Every citation value MUST be a STRING.

Correct:

"value":"44.28"

NOT

"value":44.28

confidence_score MUST be an INTEGER.

Correct:
80

Wrong:
0.8

missing_data_points MUST be a LIST of STRINGS, not nested objects.

Correct:
["RSI data missing", "No MACD available"]

Wrong:

[{"value": "RSI data missing"}]

"""),
(
    "user", 
    "Query: {query}\n\nContext:\n{context}"
),

# pyright: ignore[reportUnknownParameterType]


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
                key_levels={
                    "support": "Data Unavailable",
                    "resistance": "Data Unavailable",
                },
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
