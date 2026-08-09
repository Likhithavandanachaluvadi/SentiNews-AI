"""
Production-grade Indian financial analyst agents:
- Domain-specific expert nodes (Fundamental, Technical, Sentiment)
- Specialized LLM chains for each Indian market analysis type
- Proper error handling and fallback behaviors
"""
# pyrefly: ignore [missing-import]
from langchain_core.prompts import ChatPromptTemplate
# pyrefly: ignore [missing-import]
from langchain_groq import ChatGroq
from src.agents.state import ResearchState
from src.core.config import settings
import logging
import json

logger = logging.getLogger(__name__)

# Initialize fast 8B model for individual analyst agents
llm_analyst = ChatGroq(
    temperature=0.1,
    model_name="llama-3.1-8b-instant",
    api_key=settings.GROQ_API_KEY
) if settings.GROQ_API_KEY else None

llm_judge = ChatGroq(
    temperature=0.2,
    model_name="llama-3.3-70b-versatile",
    api_key=settings.GROQ_API_KEY,
) if settings.GROQ_API_KEY else None

# ============================================================================
# ============================================================================
# FUNDAMENTAL ANALYSIS PROMPT — INDIA FOCUSED (MASTER PROMPT STYLE)
# ============================================================================
fundamental_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a senior equity research analyst specializing in Indian equity markets (NSE/BSE).
Perform a thorough fundamental analysis of the company using ONLY the verified data provided in the context.

CRITICAL RULES:
- NEVER invent, estimate, or fabricate any number, metric, or fact.
- NEVER use BUY, SELL, HOLD, TARGET PRICE, or any advisory language.
- If a metric is unavailable in the context, state "Data unavailable" — do not guess.
- Use Indian Rupee format (₹, Crores) for all monetary values.

Your response MUST be a valid JSON object with EXACTLY these fields:

{{
    "summary": "A 2-3 paragraph institutional-grade synthesis covering: (1) the company's overall financial health, (2) valuation positioning relative to peers and history, (3) key strengths and concerns. Write this as a cohesive narrative, not bullet points. Use specific numbers from the provided data.",
    "financial_health": "Detailed analysis of revenue trends (3-year YoY growth), profit trajectory, margin dynamics (gross/operating/net), cash flow quality (OCF vs net income), and balance sheet strength (debt/equity, interest coverage). Cite specific numbers from the context. If data is partial, analyze what's available and note gaps.",
    "competitive_moat": "Assessment of competitive advantages (brand, scale, switching costs, network effects, patents), market position, industry tailwinds, and structural risks. Reference industry context where available.",
    "key_factors": [
        "List 3-5 key fundamental drivers as separate strings. Each must be a single sentence integrating Claim + Evidence + Implication.",
        "Example: 'Revenue CAGR of 18% over three years supported by strong order inflows, indicating sustained demand visibility.'",
        "Use ONLY metrics found in the provided context."
    ],
    "confidence": {{
        "confidence_score": 75,
        "uncertainty_level": "Moderate",
        "confidence_reasoning": "Explain what data was available vs missing and how it affects your confidence.",
        "missing_data_points": ["List specific data points that were unavailable but would have improved the analysis"]
    }}
}}

QUALITY REQUIREMENTS:
1. Every factual claim MUST be traceable to a metric in the provided context
2. Use specific numbers: "ROE of 22.4%" not "strong ROE"
3. Compare metrics against sector benchmarks or historical averages where context provides them
4. Flag any data discrepancies you notice (e.g., market cap from one source doesn't match another)
5. Write for a financially literate audience — use precise terminology""",),
    ("user", "Indian Stock Research Query: {query}\n\nVerified Market Context:\n{context}")
])


# ============================================================================
# TECHNICAL ANALYSIS PROMPT — INDIA FOCUSED (MASTER PROMPT STYLE)
# ============================================================================
technical_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a senior technical analyst specializing in Indian equities (NSE/BSE).
Perform a thorough technical analysis using ONLY the verified indicator data provided in the context.

CRITICAL RULES:
- NEVER invent, estimate, or fabricate any price level, indicator value, or chart pattern.
- NEVER provide entry prices, target prices, stop losses, or trading recommendations.
- If an indicator is unavailable, state "Data unavailable" — do not guess.
- Use Indian Rupee format (₹) for all price levels.

Your response MUST be a valid JSON object with EXACTLY these fields:

{{
    "summary": "A 2-3 paragraph technical synthesis covering: (1) current price positioning relative to key moving averages, (2) momentum state (RSI, MACD), (3) trend direction and key levels. Use specific numbers from the provided indicator data. Write as a cohesive narrative.",
    "trend_analysis": "Detailed analysis of the trend structure: price position relative to SMA 20/50/200, MACD signal line crossover status, and overall directional bias (Uptrend/Downtrend/Sideways). Reference specific indicator values from the context.",
    "momentum_analysis": "RSI interpretation (overbought >70, oversold <30, neutral 30-70), MACD histogram direction, volume confirmation or divergence. Cite exact RSI and MACD values from the data.",
    "key_levels": {{
        "support": "Key support levels based on SMA 20, SMA 50, recent swing lows, and any other technical reference points from the context.",
        "resistance": "Key resistance levels based on recent swing highs, moving averages overhead, and psychological price levels."
    }},
    "confidence": {{
        "confidence_score": 70,
        "uncertainty_level": "Moderate",
        "confidence_reasoning": "Explain what indicator data was available vs missing and how it affects your technical assessment.",
        "missing_data_points": ["List specific indicators or data points that were unavailable"]
    }}
}}

QUALITY REQUIREMENTS:
1. Every indicator reference MUST use the exact value from the provided context
2. Interpret indicators in the context of Indian market conditions
3. Note any divergences between indicators (e.g., RSI bullish but MACD bearish)
4. Use precise technical terminology appropriate for Indian equity markets""",),
    ("user", "Indian Stock Research Query: {query}\n\nVerified Technical Indicator Data:\n{context}")
])

# # ============================================================================
# # SENTIMENT ANALYSIS PROMPT — INDIA FOCUSED (MASTER PROMPT STYLE)
# # ============================================================================
# sentiment_prompt = ChatPromptTemplate.from_messages([
#     ("system", """You are a stock news & sentiment specialist for the Indian stock market (NSE/BSE).
# Analyze recent news developments for the stock from the last 30 days and provide today's comprehensive Indian market summary.

# Structure your response EXACTLY as a JSON object:
# {{
#     "market_summary": {{
#         "indices_performance": "Nifty, Sensex, Bank Nifty performance (with % change)",
#         "gainers_losers": "Top 5 gainers & losers in Nifty 50",
#         "sector_performance": "Major sector performance (Auto, IT, Banks, FMCG, Metals)",
#         "economic_updates": "Key economic data or RBI updates in last few days",
#         "global_cues": "Global market cues (US, Europe, Asia), Commodities (Gold, Crude Oil) & USD/INR"
#     }},
#     "stock_news": [
#         {{
#             "date": "DD-MM-YYYY",
#             "headline": "Headline of the news",
#             "summary": "Short 1-2 sentence summary",
#             "sentiment": "Positive" | "Negative" | "Neutral"
#         }}
#     ],
#     "recurring_themes": "Recurring themes (e.g., expansion, debt issues, litigation, management changes)",
#     "sentiment_score": 6,
#     "sentiment_reasoning": "Detailed reasoning for the sentiment score (0 to 10 scale)"
# }}

# Provide 5-10 significant news items specific to the stock in the 'stock_news' list. Ensure the output is valid, parseable JSON.""",),
#     ("user", "Indian Stock Research Query: {query}\n\nNews & Sentiment Context:\n{context}")
# ])


# ============================================================================
# SENTIMENT ANALYSIS PROMPT — INDIA FOCUSED (MASTER PROMPT STYLE)
# ============================================================================

sentiment_prompt = ChatPromptTemplate.from_messages([
    ("system", """
You are a Senior Financial News Analyst specializing in NSE/BSE listed companies.
Analyze the retrieved news articles and provide a sentiment assessment using ONLY the evidence provided.

CRITICAL RULES:
- NEVER fabricate news events, dates, sources, or sentiment assessments.
- If fewer than 3 relevant articles are available, explicitly state the limited evidence base.
- Every factual claim MUST reference a specific article from the context.
- Never include generic placeholders like "recent developments" or "market activity".

Your response MUST be a valid JSON object with EXACTLY these fields:

{{
    "summary": "A 2-3 paragraph synthesis of the company's current news environment. Cover: (1) the primary news catalyst driving attention, (2) overall sentiment direction with evidence from specific articles, (3) key risks or opportunities highlighted by recent coverage. Use specific headlines and dates from the provided articles. If no relevant news is available, state that clearly.",
    "sentiment_score": 65,
    "sentiment_reasoning": "Evidence-based explanation for the score. Reference specific articles, their sentiment classification, and market impact assessment. Explain what's driving the overall mood.",
    "key_themes": [
        "List 2-4 recurring themes from the news coverage as separate strings.",
        "Each theme must be a specific observation, not a generic category.",
        "Example: 'Q3 revenue miss of 8% driven by weakness in the IT services segment' not 'Financial performance'."
    ],
    "confidence": {{
        "confidence_score": 70,
        "uncertainty_level": "Moderate",
        "confidence_reasoning": "Assess the quality and recency of available news sources. Note if sources are primarily from one provider or if coverage is sparse.",
        "missing_data_points": ["List specific types of information that were missing from the news coverage"]
    }}
}}

QUALITY REQUIREMENTS:
1. Score interpretation: 0-25 = Highly Negative, 26-45 = Negative, 46-55 = Neutral, 56-75 = Positive, 76-100 = Highly Positive
2. Prioritize recent articles (last 30 days) over older ones
3. Distinguish between material news (earnings, M&A, regulatory) and noise (social media, gossip)
4. Note source quality — official filings rank higher than blog posts""",),

    ("user",
     "Indian Stock Research Query: {query}\n\n"
     "Retrieved News Articles:\n{context}")
])



# ============================================================================
# FUNDAMENTAL ANALYST NODE
# ============================================================================
async def fundamental_node(state: ResearchState) -> dict:
    """Generates fundamental analysis report for an Indian stock."""
    if not llm_analyst:
        logger.warning("Groq API Key missing - using fallback fundamental analysis")
        return {"fundamental_report": {"analysis": "API key not configured.", "score": 5.0}}

    try:
        context_str = "\n".join(state.get("context", []))
        chain = fundamental_prompt | llm_analyst

        response = await chain.ainvoke({
            "query": state["query"],
            "context": context_str,
        })

        try:
            report = json.loads(response.content)
        except json.JSONDecodeError:
            report = {"analysis": response.content, "score": 5.0}

        logger.info(f"Fundamental analysis completed - Score: {report.get('score', 'N/A')}")
        return {"fundamental_report": report}

    except Exception as e:
        logger.error(f"Fundamental analysis failed: {e}")
        return {
            "fundamental_report": {
                "analysis": f"Analysis failed: {str(e)}",
                "score": 0.0,
            }
        }



# ============================================================================
# TECHNICAL ANALYST NODE
# ============================================================================
async def technical_node(state: ResearchState) -> dict:
    """Generates technical analysis report for an Indian stock."""
    if not llm_analyst:
        logger.warning("Groq API Key missing - using fallback technical analysis")
        return {"technical_report": {"analysis": "API key not configured.", "score": 5.0}}

    try:
        context_str = "\n".join(state.get("context", []))
        chain = technical_prompt | llm_analyst

        response = await chain.ainvoke({
            "query": state["query"],
            "context": context_str,
        })

        try:
            report = json.loads(response.content)
        except json.JSONDecodeError:
            report = {"analysis": response.content, "score": 5.0}

        logger.info(f"Technical analysis completed - Score: {report.get('score', 'N/A')}")
        return {"technical_report": report}

    except Exception as e:
        logger.error(f"Technical analysis failed: {e}")
        return {
            "technical_report": {
                "analysis": f"Analysis failed: {str(e)}",
                "score": 0.0,
            }
        }

# ============================================================================
# SENTIMENT ANALYST NODE
# ============================================================================
async def sentiment_node(state: ResearchState) -> dict:
    """Generates sentiment analysis report based on Indian news & market perception."""
    if not llm_analyst:
        logger.warning("Groq API Key missing - using fallback sentiment analysis")
        return {"sentiment_report": {"analysis": "API key not configured.", "sentiment_score": 0}}

    try:
        context_str = "\n".join(state.get("context", []))
        chain = sentiment_prompt | llm_analyst

        response = await chain.ainvoke({
            "query": state["query"],
            "context": context_str,
        })

        try:
            report = json.loads(response.content)
        except json.JSONDecodeError:
            report = {"analysis": response.content, "sentiment_score": 0}

        logger.info(f"Sentiment analysis completed - Score: {report.get('sentiment_score', 0)}")
        return {"sentiment_report": report}

    except Exception as e:
        logger.error(f"Sentiment analysis failed: {e}")
        return {
            "sentiment_report": {
                "analysis": f"Analysis failed: {str(e)}",
                "sentiment_score": 0,
            }
        }
