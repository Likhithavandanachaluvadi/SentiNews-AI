"""
Production-grade Indian financial analyst agents:
- Domain-specific expert nodes (Fundamental, Technical, Sentiment)
- Specialized LLM chains for each Indian market analysis type
- Proper error handling and fallback behaviors
"""
from langchain_core.prompts import ChatPromptTemplate
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
    ("system", """You are a world-class equity analyst specializing in Indian equity markets (NSE/BSE).
Perform a complete 360° institutional-grade fundamental analysis of the company based on the provided latest available market data.

CRITICAL: Your analysis should be suitable for retail investors seeking institutional-level insights.

Structure your response EXACTLY as a valid JSON object:
{{
    "business_model": "Summarize the business model, core products, services, and competitive positioning in 2-3 paragraphs. Include key value drivers.",
    "screener_key_statistics": {{
        "market_cap_crores": "Market Cap in Crores",
        "stock_pe_ratio": "Stock P/E ratio (TTM)",
        "peg_ratio": "PEG ratio - Growth-adjusted valuation metric",
        "pb_ratio": "Price to Book ratio",
        "ps_ratio": "Price to Sales ratio (if available)",
        "book_value_per_share": "Book Value in Rupees",
        "dividend_yield_percent": "Current Dividend Yield (%)",
        "face_value": "Face Value",
        "roce_percent": "Return on Capital Employed (%)",
        "roe_percent": "Return on Equity (%)",
        "fcf_yield_percent": "Free Cash Flow Yield (%) - measure of cash generation"
    }},
    "financial_health_analysis": {{
        "revenue_analysis": "3-year revenue trend with YoY growth rates and CAGR. Include recent quarterly trends.",
        "profit_growth": "Net profit trend over 3 years. Compare with revenue growth to assess operating leverage.",
        "eps_analysis": "Earnings Per Share trend, growth rates, and forward projections based on analyst expectations.",
        "margin_analysis": "Gross Margin, Operating Margin, and Net Margin trends. Are they expanding or contracting? Why?",
        "cash_flow_analysis": "Operating Cash Flow, Free Cash Flow trends. Is the company converting profits to cash efficiently?",
        "balance_sheet_strength": "Debt-to-Equity ratio, Interest Coverage ratio, Current ratio. Liquidity position and debt sustainability."
    }},
    "valuation_analysis": {{
        "current_valuation": "P/E, P/B, EV/EBITDA multiples compared to historical 3-5 year averages and sector/industry benchmarks.",
        "peer_comparison": "Compare company's multiples (P/E, P/B, PEG) with Top 3 competitors. Is it cheap or expensive?",
        "fair_value_estimate": "Based on discounted cash flow, P/E multiple approach, and historical valuations - what's a fair price range?",
        "margin_of_safety": "At current price, is there a margin of safety for long-term investors?"
    }},
    "competitive_position": {{
        "market_share": "Company's market position and market share in key segments.",
        "competitive_moat": "What competitive advantages does the company have? (Brand, network, switching costs, scale, patents)",
        "industry_tailwinds": "What industry trends favor this company? (Consolidation, digital transformation, demographics, policy support)",
        "risk_factors": "What threats exist? (Competition, substitution, cyclicality, regulatory, geographic concentration)"
    }},
    "growth_story": {{
        "revenue_drivers": "What are the key revenue drivers for next 2-3 years?",
        "growth_projections": "Based on analyst consensus and company guidance - what's the expected revenue/earnings CAGR?",
        "expansion_opportunities": "New markets, products, segments, or geographies the company can tap into.",
        "profitability_improvement": "Scope for margin expansion through automation, scale, or operating leverage."
    }},
    "capital_allocation": {{
        "dividend_policy": "Dividend history and payout ratio. Is the company returning cash to shareholders?",
        "capex_requirements": "Capital intensity of the business. How much capex is needed to grow?",
        "buyback_activity": "Any share buyback programs? Impact on EPS and shareholder value.",
        "m_and_a_strategy": "Any major acquisitions or strategic moves planned?"
    }},
    "risk_analysis": {{
        "business_risks": "Industry cyclicality, technological disruption, competitive pressures, customer concentration.",
        "financial_risks": "Debt burden, liquidity risks, currency exposure (if applicable), interest rate sensitivity.",
        "macro_risks": "Economic slowdown impact, sector-specific regulatory risks, geopolitical factors affecting India.",
        "execution_risks": "Management capability, corporate governance, any past controversies or red flags."
    }},
    "catalysts_and_news": {{
        "recent_developments": "Major earnings beats/misses, management changes, corporate actions in last 6 months.",
        "upcoming_catalysts": "Earnings season, dividend announcements, expansion announcements, regulatory changes coming up.",
        "sentiment": "Current market sentiment - bullish, bearish, or mixed? Any insider buying/selling?"
    }},
    "investment_thesis": {{
        "bull_case": "The strongest reasons to be bullish on this stock (2-3 key points).",
        "bear_case": "The strongest reasons to be bearish on this stock (2-3 key points).",
        "base_case": "Most likely scenario over next 12-24 months - what's the consensus view?",
        "bull_target": "Upside target price and timeframe (6-12 months) if bull case plays out.",
        "bear_target": "Downside risk if bear case triggers."
    }},
    "final_verdict": {{
        "rating": "BUY / HOLD / SELL",
        "target_price": "Fair value estimate with upside/downside from current price (%)",
        "investment_horizon": "Short-term (3-6 months) / Medium-term (1-2 years) / Long-term (3+ years)",
        "risk_reward_ratio": "Assess the risk-reward profile at current valuation.",
        "investment_type": "Value / Growth / Income / Turnaround / Defensive?",
        "key_monitoring_metrics": "What metrics should investors track quarterly?"
    }},
    "analyst_recommendation_summary": "2-3 paragraph executive summary suitable for retail investors looking to understand this stock investment opportunity.",
    "score": 7.5
}}

QUALITY REQUIREMENTS:
1. All metrics MUST use Indian rupee format (₹, Crores, Lakhs) where applicable
2. All percentages should be expressed as decimals or explicit %
3. Use financial jargon but explain in terms retail investors understand
4. Focus on materiality - highlight only significant changes and drivers
5. Provide data-backed analysis - don't make vague statements
6. Include historical context (3-5 years where available)
7. Ensure output is valid, parseable JSON (test before returning)
8. Use actual data from the provided market context, not hypothetical data""",),
    ("user", "Indian Stock Research Query: {query}\n\nComprehensive Market Context (NSE/BSE Data + Screener Metrics):\n{context}")
])


# ============================================================================
# TECHNICAL ANALYSIS PROMPT — INDIA FOCUSED (MASTER PROMPT STYLE)
# ============================================================================
technical_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a senior technical analyst specializing in Indian equities (NSE/BSE).
Perform a complete technical analysis of the stock based on recent market data.

Structure your response EXACTLY as a JSON object:
{{
    "current_price_change": "Current Price and % change (Daily & Weekly)",
    "fifty_two_week_and_ath_atl": "52-Week High & Low, All-Time High & Low in ₹",
    "support_resistance": "Key support and resistance levels (short-term, medium-term, long-term)",
    "moving_averages": "20, 50, 100, 200-day MAs, and whether price is above or below each",
    "momentum_indicators": "RSI, MACD, Stochastic readings & interpretation",
    "trend_analysis": "Trend direction (Uptrend / Downtrend / Sideways)",
    "chart_patterns": "Triangles, Head & Shoulders, Cup & Handle, or other visible patterns",
    "volume_trends": "Volume analysis - whether volume supports or contradicts price action",
    "trading_plan": {{
        "entry": "Recommended entry price level",
        "target": "Technical targets",
        "stop_loss": "Recommended Stop Loss level"
    }},
    "risk_factors_traders": "Key risk factors for short-term traders",
    "trader_outlook_summary": "Concise 2-3 sentence trader's outlook summary (Bullish, Bearish, or Neutral)",
    "score": 6.5
}}

IMPORTANT: Use Indian Rupees (₹) for all price levels. Ensure the output is valid, parseable JSON.""",),
    ("user", "Indian Stock Research Query: {query}\n\nMarket Context:\n{context}")
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
You are a Senior Financial News Analyst and Indian Equity Market Intelligence Specialist specializing in NSE/BSE listed companies.

Analyze ONLY stock market relevant news for the requested company.

===========================================================================
IMPORTANT RULES
===========================================================================

Only include news that has a DIRECT impact on the company's:

- Stock price
- Financial performance
- Quarterly results
- Annual results
- Revenue
- Profitability
- Business operations
- Investor sentiment
- Valuation
- Future growth

STRICTLY IGNORE the following:

- Traffic news
- Weather
- Crime
- Politics (unless directly affecting the company)
- Sports
- Entertainment
- Celebrity news
- Social media discussions
- Viral posts
- Recruitment notifications
- Campus hiring
- Employee events
- CSR activities without financial impact
- Lifestyle articles
- Technology news unrelated to the company
- General city news
- Festival news
- Historical articles
- Duplicate articles
- Opinion blogs
- Articles where the company is only mentioned in passing

If an article does NOT materially affect investors,
DO NOT include it.

===========================================================================
ONLY INCLUDE NEWS ABOUT
===========================================================================

- Quarterly Results
- Annual Results
- Earnings
- Revenue
- Net Profit
- EBITDA
- Margin Expansion
- Dividend
- Bonus Issue
- Stock Split
- Buyback
- Rights Issue
- Acquisitions
- Mergers
- Joint Ventures
- Major Client Wins
- Government Contracts
- SEBI announcements
- RBI announcements
- Credit Rating changes
- Promoter Shareholding
- FII/DII activity
- Insider Trading disclosures
- Block Deals
- Bulk Deals
- CEO/CFO appointments
- Management changes
- Business Expansion
- Capex
- Debt Reduction
- Regulatory approvals
- Litigation with financial impact
- Product launches affecting revenue
- Industry developments affecting the company
- Analyst upgrades/downgrades

===========================================================================
QUALITY RULES
===========================================================================

- Return only HIGH QUALITY finance news.
- Ignore duplicate articles.
- Ignore clickbait headlines.
- Ignore rumours.
- Ignore unverified information.
- Prefer trusted financial sources.
- Prioritize the latest news.
- If fewer than 5 relevant articles exist, return only those.
- Never hallucinate information.
- Never create fake news.

===========================================================================
Return your response EXACTLY as valid JSON.

{{
    "market_summary": {{
        "indices_performance": "Nifty, Sensex, Bank Nifty performance",
        "sector_performance": "Sector wise movement",
        "economic_updates": "Recent RBI/Economic updates",
        "global_cues": "Global market impact"
    }},

    "stock_news": [
        {{
            "date": "DD-MM-YYYY",

            "headline": "",

            "summary": "",

            "source": "",

            "sentiment": "Positive | Neutral | Negative",

            "market_impact": "High | Medium | Low",

            "financial_relevance": "High | Medium | Low",

            "confidence": 95
        }}
    ],

    "recurring_themes": "",

    "sentiment_score": 8,

    "sentiment_reasoning": ""
}}

Return ONLY valid JSON.
Do not include markdown.
Do not include explanations.
Do not include extra text.
"""),

    ("user",
     "Indian Stock Research Query: {query}\n\n"
     "News & Sentiment Context:\n{context}")
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
