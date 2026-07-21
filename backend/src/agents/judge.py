"""
Chief Investment Officer / Judge Node
Synthesizes the expert analyst reports into a SEBI-compliant educational report.
Uses strictly typed Pydantic output.

Sprint 1 Improvements:
- Expanded pruned report fields so the LLM has cross-discipline material to weave
- Rewrote judge_prompt to explicitly instruct catalyst identification and contradiction surfacing
- Replaced verbatim-copy fallback with a narrative assembler
- Fixed ver_feedback variable shadowing
- Added defensive .get() guards on verifier corrections
"""
from typing import Any
from src.services import technical_analysis_engine
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
# from backend.src.agents import state
from src.agents import state
from src.agents.state import ResearchState
from src.agents.schemas import FinalEducationalReport
from src.core.config import settings
from src.core.debug_logger import debug_logger, NodeStatus
import json
import logging
import time
from datetime import datetime
import re
logger = logging.getLogger(__name__)

TICKERLESS_JUDGE_INTENTS = {
    "EDUCATIONAL",
    "SECTOR_OUTLOOK",
    "THEME_ANALYSIS",
    "MARKET_OVERVIEW",
    "RESTRICTED_ADVISORY",
}

llm = ChatGroq(
    temperature=0.2,
    model_name="llama-3.1-8b-instant",
    api_key=settings.GROQ_API_KEY
) if settings.GROQ_API_KEY else None

judge_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are an Elite Institutional Equity Research Analyst and Principal Financial Advisor.
Format the response as a JSON object matching the FinalEducationalReport schema.
Your goal is to produce a single, fluid, institutional-grade research narrative — not a merged summary of three separate reports.

========================================================
PRE-WRITING SYNTHESIS PROTOCOL (Execute mentally before writing any field)
========================================================

Step 1 — IDENTIFY THE PRIMARY CATALYST:
  Read all three expert reports (Fundamental, Technical, Sentiment) and the grounding data.
  Identify the ONE factor that most directly drives the current situation:
  valuation, price action, or risk profile.
  This becomes the opening thesis of `executive_summary`.

Step 2 — MAP AGREEMENTS:
  Where do the fundamental, technical, and sentiment signals REINFORCE each other?
  Use these agreements to build conviction and tighten the narrative.

Step 3 — SURFACE & RESOLVE CONTRADICTIONS:
  Where do the signals CONFLICT? (e.g. RSI positive but moving averages weak, or positive sentiment against deteriorating margins.)
  Do NOT simply list both conflicting statements. Instead, explain the underlying technical/financial reason WHY they conflict (e.g. explain that a constructive RSI against weak moving averages suggests a near-term oversold relief rally within a longer-term structural downtrend).
  The explanation must read like a professional institutional equity research analyst.

Step 4 — WEIGHT BY INTENT:
  The `primary_intent` field tells you what the user actually cares about.
  - FUNDAMENTAL_ANALYSIS: lead with financial health, reference technicals as context.
  - TECHNICAL_ANALYSIS: lead with price action and momentum, reference fundamentals as background.
  - SENTIMENT_PULSE: lead with news flow and market mood, then connect to fundamentals.
  - STOCK_ANALYSIS / GENERALIZED: weigh all three proportionally; catalyst determines ordering.

Step 5 — WRITE:
  Produce `executive_summary` as one continuous, paragraph-driven institutional narrative.
  Explain:
    1. WHAT is happening (the overarching market picture, price actions, or sentiment mood).
    2. WHY it is happening (the underlying company metrics, financial developments, or trends).
    3. OPPORTUNITIES (expansion potential, moat advantages, technical support rebounds).
    4. RISKS (leverage, technical overextension, valuation stretch).
  Never copy any analyst sentence verbatim. Always reinterpret and synthesize.

========================================================
METRIC INTERPRETATION GUIDE
========================================================

Interpret financial and technical indicators provided in the VERIFIED GROUNDING CONTEXT and TOP PEERS COMPARISON using these professional guidelines (use them only when the metric is explicitly present in the data):
- Return on Equity (ROE) / Return on Capital Employed (ROCE):
  * High (e.g., >15-20%): Indicates efficient profitability and stellar capital allocation.
  * Low (e.g., <8-10%): Suggests capital allocation challenges or sub-par efficiency.
- Price-to-Earnings (P/E) Ratio:
  * Compare with the P/E ratios in the TOP PEERS COMPARISON to determine if it trades at a premium valuation or a discount. Explain the justification for any premium (e.g., strong competitive moat) or risks of overvaluation.
- RSI (14):
  * 50–70: Constructive/bullish continuation momentum.
  * <30: Technically oversold (potential short-term relief rally conditions).
  * >70: Technically overbought (potential near-term fatigue or exhaustion risks).
- Debt/Equity Ratio:
  * High (e.g., >1.5): Signals elevated leverage risk and interest service burden.
- SMA 20/50:
  * Price above SMAs suggests a constructive short/medium-term trend, while price below SMAs indicates technical weakness.

========================================================
VALIDATION AWARENESS & WARNING RULES
========================================================

If a metric in the VERIFIED GROUNDING CONTEXT is annotated with a validation warning (e.g. "[Caution: could not be independently verified - reason: ...]"), you must explain in your synthesis that the metric could not be independently verified and should be interpreted with caution.
CRITICAL: Validation failures are NOT business or solvency risks. Do NOT convert validation failures into financial risks (do not suggest that unverified data indicates insolvency, credit risk, or operational failure). Explain it strictly as a caution regarding data verification.

========================================================
PRESENTATION & STYLE RULES
========================================================

1. CORE IDENTITY & VOICE:
   - Speak as a senior institutional equity researcher (Morgan Stanley or JP Morgan calibre).
   - Natural, balanced, authoritative financial language. Not a chatbot, not a report compiler.

2. ANSWER-FIRST:
   - Open `executive_summary` by directly answering the user's question.
   - Never open with boilerplate introductions ("TCS is a leading IT company...").
   - Start with the primary catalyst or core insight.

3. UNIFIED NARRATIVE — NO SILOS:
   - Blend fundamental, technical, and sentiment signals into ONE continuous story.
   - Never separate them into labelled blocks ("On the technical front...", "From a fundamental perspective...").
   - TOP PEERS COMPARISON: Naturally compare the company against its peers using the provided P/E and ROE values. Do NOT simply state 'Peer comparison suggests...'. Instead, explain whether the company's valuation or performance is stronger (trading at a premium P/E), weaker (discounted P/E), or comparable to peers, and link this directly to whether its profitability/ROE is stronger, weaker, or comparable to theirs.

4. NO REPORT HEADINGS:
   - NEVER use rigid headings like "Fundamental Analysis", "Technical Analysis", "Sentiment Analysis",
     "Risk Analysis", "Investment Perspective", "Conclusion", or "Executive Summary" inside the summary.
   - Markdown headings (###) are allowed ONLY for major topic transitions in complex educational queries.

5. READING RHYTHM:
   - Mix short punchy sentences (1-2 lines) with longer analytical paragraphs.
   - Use selective bullet lists only for multi-item risks or drivers — not as a substitute for prose.

6. DATA GAPS — PROFESSIONAL LANGUAGE:
   - If data is missing or low-confidence, use institutional phrasing:
     "limited public disclosure restricts...", "provider discrepancies suggest...",
     "current evidence remains inconclusive regarding..."
   - Never write "Data unavailable" or "Information missing".

7. BANNED PHRASES:
   - Never write: "Based on the provided context", "According to the data", "As an AI",
     "In conclusion", "To summarize", "Refer to the dashboard", "The following analysis",
     "This report", "Executive Summary", "Fundamental Analysis", "Technical Analysis".
   - Never start consecutive sentences with "This indicates", "This reflects", "This shows".

8. SEBI COMPLIANCE & EDUCATIONAL WORDING:
   - Never use "BUY", "SELL", "HOLD", or "TARGET PRICE".
   - Avoid target-directed advice such as "Investors should...", "We recommend...", "You should...". Replace them entirely with objective, descriptive, educational language (e.g. "One may monitor...", "It is helpful to analyze...", "The data suggests...", "This suggests that...").
   - Discuss strengths, weaknesses, risks, and uncertainties. Never guarantee returns.

9. SYNTHESIS FIELD RULES:
   - `executive_summary`: the full synthesis narrative described above.
   - `fundamental_synthesis`: 1-2 sentence distillation of the fundamental signal and its
     tension with or support for the other signals. NOT a copy of fundamental summary.
   - `technical_synthesis`: 1-2 sentence distillation of the key technical signal and whether
     it confirms or contradicts the fundamental picture.
   - `sentiment_synthesis`: 1-2 sentence distillation of market mood and how it amplifies
     or cuts against the fundamental/technical direction.
   - `company_overview`: brief factual company description only. Do NOT repeat analysis here.
   - `investment_thesis`: 3-5 key educational drivers. Each item in the list MUST be a single natural conversational string (sentence) integrating Claim -> Evidence -> Implication. Do NOT output JSON objects, key-value mappings, or nested dictionaries.
     Phrasing style: "[Claim] supported by [Evidence], implying [Implication]."
     Example: "Durable profitability supported by an ROE of 22%, indicating highly efficient conversion of equity capital into earnings growth."
     Do not copy or list raw key_factors verbatim.
   - `risk_analysis`: A list of major risks that could cause the thesis to fail. Each item MUST be a single natural conversational string (sentence). Do NOT output JSON objects or nested dictionaries.
     Example: "Rising competitive pressures in core segments could compress operating margins, threatening the projected free cash flow trajectory."
   - `scenario_analysis`:
     * `bull_case`: Must paint a positive scenario grounded in verified evidence, major opportunities, and potential breakout triggers (e.g. momentum continuation, moat expansion).
     * `base_case`: The most likely path reflecting the intent-weighted consensus signals.
     * `bear_case`: A pessimistic scenario highlighting key risks (leverage, trend breakdowns, sentiment deterioration) backed by grounded evidence.
     * Do not use generic or placeholder scenarios.

10. PLANNER SECTIONS:
    Sections in `{sections_layout_instruction}` are thematic topics — weave them into the
    narrative flow. Do NOT output them as markdown headers.

========================================================
STRICT ENUM RULES
========================================================

"outlook_label" MUST be EXACTLY one of:
  Positive Long-Term Outlook | Neutral Outlook | Elevated Risk Outlook
  Constructive Momentum | Weak Momentum | Uncertain Outlook

Never generate: Bearish Outlook, Bullish Outlook, Positive, Negative, Neutral,
Strong Buy, Strong Sell, or any other wording.

"conviction_level" MUST be EXACTLY one of:
  High Conviction | Moderate Conviction | Medium Conviction
  Low Confidence Scenario | Medium Confidence Scenario

"overall_confidence_score" MUST be an INTEGER between 0 and 100.

"data_freshness" MUST be an ISO-8601 datetime string.

If trust_tier is present it MUST be one of: Tier 1 | Tier 2 | Tier 3
If uncertain, use Tier 2.

========================================================
EXAMPLE JSON STRUCTURE (Do NOT wrap in any root key)
========================================================

{{
  "outlook_label": "Neutral Outlook",
  "conviction_level": "Low Confidence Scenario",
  "executive_summary": "Your synthesized narrative here.",
  "company_name": "TICKER",
  "company_overview": "Brief overview.",
  "investment_thesis": [
    "Key driver 1",
    "Key driver 2"
  ],
  "fundamental_synthesis": "Fundamental synthesis.",
  "technical_synthesis": "Technical synthesis.",
  "sentiment_synthesis": "Sentiment synthesis.",
  "scenario_analysis": {{
    "bull_case": "Optimistic case details.",
    "base_case": "Most likely details.",
    "bear_case": "Pessimistic details."
  }},
  "risk_analysis": [
    "Major risk 1",
    "Major risk 2"
  ],
  "data_freshness": "2026-07-17T12:00:00Z",
  "overall_confidence_score": 50,
  "sebi_disclaimer": "This is AI-generated educational research for informational purposes only. It does NOT constitute SEBI-registered investment advice."
}}

========================================================
OUTPUT RULES
========================================================

Return ONLY a valid JSON object matching the FinalEducationalReport schema.
The JSON keys must be at the root of the object.
CRITICAL: Do NOT wrap the JSON inside a "final_educational_report" key or any other wrapper key.
Do not return markdown. Do not return explanations.
Populate every required field. Enums must exactly match the schema.
"""),
    ("user", """QUERY INTENT:
Primary Intent: {primary_intent}
Secondary Intent: {secondary_intent}

========================================================
SYNTHESIS TASK
========================================================
Before writing any output field, execute the Pre-Writing Synthesis Protocol above:
1. Identify the primary catalyst from the three reports below.
2. Map agreements between fundamental, technical, and sentiment signals.
3. Surface any contradictions — explain them explicitly in the narrative.
4. Weight the signals according to the primary intent '{primary_intent}'.
5. Write executive_summary as a unified, contradiction-aware narrative explaining what is happening, why, opportunities, and risks.

Never copy any analyst sentence verbatim. Always reinterpret, connect, and synthesize.

========================================================
VERIFIED GROUNDING CONTEXT
========================================================
{grounding_context}

========================================================
TOP PEERS COMPARISON
========================================================
{peer_summary}

========================================================
EXPERT REPORTS
========================================================

FUNDAMENTAL ANALYST REPORT:
{fundamental_report}

TECHNICAL ANALYST REPORT:
{technical_report}

SENTIMENT ANALYST REPORT:
{sentiment_report}

VERIFIER FEEDBACK:
{verifier_feedback}

User Query: {query}""")
])

def is_report_populated(report: dict) -> bool:
    """Check if a report has actual content (not just empty dict)."""
    if not report:
        return False
    if report.get("content"):
        return True
    
    # Check for key fields that indicate actual content
    # key_fields = ["summary", "confidence", "key_themes", "trend_analysis"]
    key_fields = [
    "summary",
    "content",
    "confidence",
    "key_themes",
    "trend_analysis"
]
    for field in key_fields:
        if field in report and report[field]:
            # Special check: confidence object should have a score
            if field == "confidence":
                if isinstance(report[field], dict) and report[field].get("confidence_score", 0) > 0:
                    return True
            else:
                return True
    
    return False

def _calculate_overall_confidence(
    fund_report: dict,
    tech_report: dict,
    sent_report: dict,
    fund_populated: bool,
    tech_populated: bool,
    sent_populated: bool
) -> int:
    confs = []
    
    if fund_populated and isinstance(fund_report, dict):
        conf_obj = fund_report.get("confidence") or {}
        score = conf_obj.get("confidence_score") if isinstance(conf_obj, dict) else getattr(conf_obj, "confidence_score", 0)
        if score:
            confs.append(int(score))
            
    if tech_populated and isinstance(tech_report, dict):
        conf_obj = tech_report.get("confidence") or {}
        score = conf_obj.get("confidence_score") if isinstance(conf_obj, dict) else getattr(conf_obj, "confidence_score", 0)
        if score:
            confs.append(int(score))
            
    if sent_populated and isinstance(sent_report, dict):
        conf_obj = sent_report.get("confidence") or {}
        score = conf_obj.get("confidence_score") if isinstance(conf_obj, dict) else getattr(conf_obj, "confidence_score", 0)
        if score:
            confs.append(int(score))
            
    if confs:
        return sum(confs) // len(confs)
    return 20

def _fallback_final_report(state: ResearchState, reason: str) -> dict:
    """
    Build a SEBI-safe partial synthesis when the judge LLM is unavailable.

    Sprint 1 fix: assemble a concise narrative from available analyst reports
    instead of copying summary fields verbatim into synthesis fields.
    Each available perspective is described with its signal direction so the
    output still reads as a coherent (if limited) research view.
    """
    fund_report = state.get("fundamental_report") or {}
    tech_report = state.get("technical_report") or {}
    sent_report = state.get("sentiment_report") or {}

    fund_populated = is_report_populated(fund_report)
    tech_populated = is_report_populated(tech_report)
    sent_populated = is_report_populated(sent_report)

    overall_conf = _calculate_overall_confidence(
        fund_report, tech_report, sent_report, fund_populated, tech_populated, sent_populated
    )

    # ── Assemble executive summary from available perspectives ──────────────
    # Each block describes the signal rather than copying the summary string.
    narrative_parts: list[str] = []

    if fund_populated:
        fund_summary = fund_report.get("summary", "")
        fund_health = fund_report.get("financial_health", "")
        fund_moat = fund_report.get("competitive_moat", "")
        fund_factors = fund_report.get("key_factors") or []
        fund_factors_str = (
            "; ".join(str(f) for f in fund_factors[:3]) if fund_factors else ""
        )
        # Build a descriptive sentence rather than copying the raw summary
        fund_part = fund_summary if fund_summary else "Fundamental data was partially retrieved."
        if fund_factors_str:
            fund_part += f" Key drivers include: {fund_factors_str}."
        if fund_health and fund_health not in ("N/A", "Data Unavailable"):
            fund_part += f" Financial health assessment: {fund_health}"
        narrative_parts.append(fund_part)

    if tech_populated:
        tech_summary = tech_report.get("summary", "")
        tech_trend = tech_report.get("trend_analysis", "")
        tech_momentum = tech_report.get("momentum_analysis", "")
        tech_part = tech_summary if tech_summary else "Technical data was partially retrieved."
        if tech_trend and tech_trend not in ("N/A", "Data Unavailable", "Analysis skipped for this query type."):
            tech_part += f" Trend picture: {tech_trend}"
        if tech_momentum and tech_momentum not in ("N/A", "Data Unavailable", "Analysis skipped for this query type."):
            tech_part += f" Momentum: {tech_momentum}"
        narrative_parts.append(tech_part)

    if sent_populated:
        sent_summary = sent_report.get("summary", "")
        sent_themes = sent_report.get("key_themes") or []
        sent_themes_str = "; ".join(str(t) for t in sent_themes[:3]) if sent_themes else ""
        sent_part = sent_summary if sent_summary else "Sentiment data was partially retrieved."
        if sent_themes_str:
            sent_part += f" Recurring market themes: {sent_themes_str}."
        narrative_parts.append(sent_part)

    if narrative_parts:
        exec_summary = (
            "The following educational overview is based on partially available data. "
            "Full synthesis was unavailable due to: " + reason + ". "
            "Available signals: " + " | ".join(narrative_parts)
        )
    else:
        exec_summary = (
            "Insufficient data was available to construct an educational overview. "
            f"Synthesis unavailable: {reason}"
        )

    # ── Synthesis fields: 1-2 sentence signal distillation, not a copy ──────
    fund_synthesis = (
        f"Fundamental signals suggest: {fund_report.get('summary', 'data unavailable')}. "
        + (f"Financial health: {fund_report.get('financial_health', '')}" if fund_populated else "")
    ).strip() if fund_populated else "Fundamental data was not retrieved for this query."

    tech_synthesis = (
        f"Technical picture: {tech_report.get('summary', 'data unavailable')}. "
        + (f"Trend: {tech_report.get('trend_analysis', '')}" if tech_populated else "")
    ).strip() if tech_populated else "Technical data was not retrieved for this query."

    sent_synthesis = (
        f"Market sentiment: {sent_report.get('summary', 'data unavailable')}."
    ).strip() if sent_populated else "Sentiment data was not retrieved for this query."

    # ── Investment thesis: key factors if available, otherwise minimal items ─
    thesis_items: list[str] = []
    fund_factors = fund_report.get("key_factors") or []
    for factor in fund_factors[:3]:
        thesis_items.append(str(factor))
    sent_themes = sent_report.get("key_themes") or []
    for theme in sent_themes[:2]:
        if str(theme) not in thesis_items:
            thesis_items.append(str(theme))
    if not thesis_items:
        thesis_items = ["Partial data available — full investment thesis requires complete analyst reports."]

    return {
        "outlook_label": "Neutral Outlook",
        "conviction_level": "Low Confidence Scenario",
        "executive_summary": exec_summary,
        "company_overview": (
            fund_report.get("competitive_moat", "")
            or fund_report.get("summary", "")
            or "Company overview is unavailable from verified data."
        ),
        "investment_thesis": thesis_items[:5],
        "fundamental_synthesis": fund_synthesis,
        "technical_synthesis": tech_synthesis,
        "sentiment_synthesis": sent_synthesis,
        "scenario_analysis": {
            "bull_case": "Constructive outcomes depend on verified fundamentals, market conditions, and execution.",
            "base_case": "Use available evidence as educational context, not personalized investment advice.",
            "bear_case": "Missing or stale data materially reduces confidence in the analysis.",
        },
        "risk_analysis": [reason, "Partial data can omit material risks and recent events."],
        "data_freshness": state.get("data_freshness") or datetime.utcnow().isoformat(),
        "overall_confidence_score": overall_conf,
        "sebi_disclaimer": (
            "This is AI-generated educational research for informational purposes only. "
            "It does NOT constitute SEBI-registered investment advice. "
            "Past performance is not indicative of future results."
        ),
    }


def _tickerless_final_report(state: ResearchState, primary_intent: str) -> dict:
    query = state.get("query", "")
    sentiment_report = state.get("sentiment_report") or {}
    context = [str(item) for item in (state.get("context") or []) if item]

    sentiment_summary = ""
    if isinstance(sentiment_report, dict) and sentiment_report.get("status") != "skipped":
        sentiment_summary = str(sentiment_report.get("summary") or "").strip()

    if sentiment_summary:
        executive_summary = sentiment_summary
    elif context:
        executive_summary = "Here is the relevant context I found: " + " ".join(context[:3])
    elif primary_intent == "EDUCATIONAL":
        executive_summary = f"{query} is best treated as an educational finance concept. No company ticker is required for this explanation."
    elif primary_intent == "SECTOR_OUTLOOK":
        executive_summary = f"{query} is a sector-level question, so the response should focus on industry trends, macro drivers, policy context, and competitive landscape rather than company financial statements."
    elif primary_intent == "THEME_ANALYSIS":
        executive_summary = f"{query} is a theme-level question, so the response should focus on technology trends, adoption, research context, and market drivers rather than company metrics."
    elif primary_intent == "MARKET_OVERVIEW":
        executive_summary = f"{query} is a market-level question, so the response should focus on broad market context and macro drivers rather than a single ticker."
    else:
        executive_summary = "This query does not require a company ticker, so company-specific judge synthesis was skipped."

    return {
        "outlook_label": "Neutral Outlook",
        "conviction_level": "Low Confidence Scenario",
        "executive_summary": executive_summary,
        "company_name": None,
        "company_overview": "",
        "investment_thesis": [],
        "fundamental_synthesis": "Company financial statement analysis was not required for this query.",
        "technical_synthesis": "Technical price analysis was not required for this query.",
        "sentiment_synthesis": sentiment_summary or "Sentiment synthesis was not required or not available for this query.",
        "scenario_analysis": {
            "bull_case": "Constructive outcomes depend on the broader drivers relevant to the query.",
            "base_case": "The most useful interpretation is educational and context-driven rather than ticker-specific.",
            "bear_case": "The main limitation is that tickerless context can miss company-specific evidence.",
        },
        "risk_analysis": ["Tickerless query: company-specific risks were intentionally not analyzed."],
        "data_freshness": state.get("data_freshness") or datetime.utcnow().isoformat(),
        "overall_confidence_score": 50 if sentiment_summary or context else 25,
        "sebi_disclaimer": (
            "This is AI-generated educational research for informational purposes only. "
            "It does NOT constitute SEBI-registered investment advice. "
            "Past performance is not indicative of future results."
        ),
    }

def _extract_metric_info(metric: Any) -> tuple[Any, str, str]:
    if metric is None:
        return None, "PASS", ""
    if isinstance(metric, (int, float, str, bool)):
        return metric, "PASS", ""
    if isinstance(metric, dict):
        return (
            metric.get("value"),
            metric.get("validation_status", "PASS"),
            metric.get("validation_reason", "")
        )
    return (
        getattr(metric, "value", metric),
        getattr(metric, "validation_status", "PASS"),
        getattr(metric, "validation_reason", "")
    )

def _extract_metric_val(metric: Any) -> Any:
    val, _, _ = _extract_metric_info(metric)
    return val

def _build_grounding_context(state: ResearchState, primary_intent: str) -> str:
    gd = state.get("grounding_data")
    if not gd:
        return "No verified grounding metrics available."
    
    from typing import Any
    def get_field(field_name: str) -> Any:
        if isinstance(gd, dict):
            return gd.get(field_name)
        return getattr(gd, field_name, None)
    
    lines = []
    lines.append("VERIFIED GROUNDING METRICS:")
    
    is_fundamental = primary_intent in ("FUNDAMENTAL_ANALYSIS", "STOCK_ANALYSIS", "GENERALIZED", "COMPARISON", "EARNINGS_REPORT")
    is_technical = primary_intent in ("TECHNICAL_ANALYSIS", "STOCK_ANALYSIS", "GENERALIZED", "COMPARISON", "STOCK_MOVEMENT")
    is_sentiment = primary_intent in ("SENTIMENT_PULSE", "STOCK_ANALYSIS", "GENERALIZED", "COMPARISON", "STOCK_MOVEMENT")
    
    def add_metric_line(label: str, field_name: str):
        val, status, reason = _extract_metric_info(get_field(field_name))
        if val is not None:
            if status in ("FAIL", "WARNING"):
                lines.append(f"- {label}: {val} [Caution: could not be independently verified - reason: {reason}]")
            else:
                lines.append(f"- {label}: {val}")
                
    if is_fundamental:
        add_metric_line("P/E Ratio", "pe_ratio")
        add_metric_line("Return on Equity (ROE)", "roe")
        add_metric_line("Return on Capital Employed (ROCE)", "roce")
        add_metric_line("Earnings Per Share (EPS)", "eps")
        add_metric_line("Debt/Equity Ratio", "debt_to_equity")
        add_metric_line("Free Cash Flow", "free_cash_flow")
        add_metric_line("Annual Revenue", "annual_revenue")
        
    if is_technical:
        add_metric_line("RSI (14)", "rsi_14")
        add_metric_line("SMA 20", "sma_20")
        add_metric_line("SMA 50", "sma_50")
        add_metric_line("MACD", "macd")
        add_metric_line("Technical Trend", "technical_trend")
        
    if is_sentiment:
        pass

    if len(lines) == 1:
        return "No verified grounding metrics available for this intent."
    
    return "\n".join(lines)

def _build_peer_summary(state: ResearchState) -> str:
    gd = state.get("grounding_data")
    if not gd:
        return "No peer comparison data available."
    
    if isinstance(gd, dict):
        peers = gd.get("peers") or []
    else:
        peers = getattr(gd, "peers", []) or []
        
    if not peers:
        return "No peer comparison data available."
    
    lines = ["TOP PEERS COMPARISON (Top 3):"]
    for peer in peers[:3]:
        if isinstance(peer, dict):
            ticker = peer.get("ticker", "N/A")
            name = peer.get("name", "N/A")
            pe = peer.get("stock_pe", "N/A")
            roe = peer.get("roe", "N/A")
        else:
            ticker = getattr(peer, "ticker", "N/A")
            name = getattr(peer, "name", "N/A")
            pe = getattr(peer, "stock_pe", "N/A")
            roe = getattr(peer, "roe", "N/A")
        lines.append(f"- {name} ({ticker}): P/E = {pe}, ROE = {roe}")
        
    return "\n".join(lines)

async def judge_node(state: ResearchState) -> dict:
    """
    Synthesizes the verified reports into a final educational JSON report.
    
    CRITICAL: Properly detects which reports are populated before synthesis.
    """
    start_time = time.time()

    intent = state.get("intent") or {}
    primary_intent = intent.get("primary_intent", "GENERALIZED")
    secondary_intent = intent.get("secondary_intent", "NONE")
    raw_ticker = state.get("ticker")
    retrieved_ticker = (raw_ticker or "").upper().strip()

    if primary_intent in TICKERLESS_JUDGE_INTENTS and not retrieved_ticker:
        execution_ms = int((time.time() - start_time) * 1000)
        debug_logger.log_node_execution(
            node_name="judge",
            status=NodeStatus.SKIPPED,
            input_state={"query": state.get("query", "")[:50], "primary_intent": primary_intent, "ticker": None},
            output_state={"tickerless_final_report": True},
            execution_ms=execution_ms,
        )
        return {"final_report": _tickerless_final_report(state, primary_intent)}

    # Safety Validation: Verify requested ticker matches retrieved ticker before synthesis
    from src.services.entity_resolver import EntityResolver
    query = state.get("query", "")
    requested_ticker, _ = EntityResolver.resolve_sync(query)
    
    if requested_ticker and retrieved_ticker and requested_ticker.upper() != retrieved_ticker:
        logger.warning(f"Judge: Mismatch between requested '{requested_ticker}' and retrieved '{retrieved_ticker}'")
        mismatch_msg = "Unable to verify requested company due to ticker resolution mismatch."
        return {
            "final_report": {
                "outlook_label": "Neutral Outlook",
                "conviction_level": "Low Confidence Scenario",
                "executive_summary": mismatch_msg,
                "company_name": retrieved_ticker,
                "company_overview": mismatch_msg,
                "investment_thesis": [mismatch_msg],
                "fundamental_synthesis": mismatch_msg,
                "technical_synthesis": mismatch_msg,
                "sentiment_synthesis": mismatch_msg,
                "scenario_analysis": {
                    "bull_case": mismatch_msg,
                    "base_case": mismatch_msg,
                    "bear_case": mismatch_msg
                },
                "risk_analysis": [mismatch_msg],
                "data_freshness": datetime.utcnow().isoformat(),
                "overall_confidence_score": 0,
                "sebi_disclaimer": "This is AI-generated educational research for informational purposes only. It does NOT constitute SEBI-registered investment advice."
            }
        }
    
    if not llm:
        logger.warning("Groq API Key missing.")
        
        debug_logger.log_node_execution(
            node_name="judge",
            status=NodeStatus.FAILED,
            input_state={},
            output_state={},
            execution_ms=0,
            error_message="LLM not available",
        )
        
        return {"final_report": _fallback_final_report(state, "Judge LLM service unavailable")}
    
    try:
        # ===== STEP 1: DETECT POPULATED REPORTS =====
        fund_report = state.get("fundamental_report", {})
        tech_report = state.get("technical_report", {})
        sent_report = state.get("sentiment_report", {})
        
        fund_populated = is_report_populated(fund_report)
        tech_populated = is_report_populated(tech_report)
        sent_populated = is_report_populated(sent_report)
        
        logger.info(
            f"Judge report detection: Fund={fund_populated}, Tech={tech_populated}, Sent={sent_populated}"
        )
        
        # ===== STEP 2: PREPARE REPORTS FOR SYNTHESIS =====
        # Sprint 1: expanded field set so the LLM has cross-discipline material
        # to weave (key_factors, key_levels, key_themes, data_gaps) rather than
        # only rephrasing three standalone summary strings.
        pruned_fund = {
            "summary": fund_report.get("summary", "N/A"),
            "financial_health": fund_report.get("financial_health", "N/A"),
            "competitive_moat": fund_report.get("competitive_moat", "N/A"),
            # Cross-discipline material: factors the LLM can connect to technicals/sentiment
            "key_factors": fund_report.get("key_factors") or [],
            "confidence_score": (fund_report.get("confidence") or {}).get("confidence_score", 0),
            "data_gaps": (fund_report.get("confidence") or {}).get("missing_data_points") or [],
        } if fund_populated else {}

        pruned_tech = {
            "summary": tech_report.get("summary", "N/A"),
            "trend_analysis": tech_report.get("trend_analysis", "N/A"),
            "momentum_analysis": tech_report.get("momentum_analysis", "N/A"),
            # Key levels let the LLM anchor price-action context against fundamentals
            "key_levels": tech_report.get("key_levels") or {},
            "confidence_score": (tech_report.get("confidence") or {}).get("confidence_score", 0),
            "data_gaps": (tech_report.get("confidence") or {}).get("missing_data_points") or [],
        } if tech_populated else {}

        pruned_sent = {
            "summary": sent_report.get("summary", "N/A"),
            "sentiment_score": sent_report.get("sentiment_score", "N/A"),
            # Themes give the LLM recurring news signals to weave into the narrative
            "key_themes": sent_report.get("key_themes") or [],
            "confidence_score": (sent_report.get("confidence") or {}).get("confidence_score", 0),
            "data_gaps": (sent_report.get("confidence") or {}).get("missing_data_points") or [],
        } if sent_populated else {}

        ver_feedback_raw = state.get("reflection_feedback", {}) or {}
        pruned_verifier = {
            "confidence": "Valid" if ver_feedback_raw.get("is_valid") else "Requires Review",
            "warnings": [
                *ver_feedback_raw.get("contradictions_found", []),
                *ver_feedback_raw.get("hallucinations_detected", []),
                *[v.get("reason") if isinstance(v, dict) else str(v) for v in ver_feedback_raw.get("sebi_violations", [])]
            ]
        } if ver_feedback_raw else {}

        fund_report_json = json.dumps(pruned_fund, indent=2)
        tech_report_json = json.dumps(pruned_tech, indent=2)
        sent_report_json = json.dumps(pruned_sent, indent=2)
        ver_feedback_json = json.dumps(pruned_verifier, indent=2)
        
        # Sprint 2: Build grounding context and peer summary
        grounding_context = _build_grounding_context(state, primary_intent)
        peer_summary = _build_peer_summary(state)
        
        # ===== STEP 3: INVOKE JUDGE =====
        planner_layout = intent.get("planner_layout", {})
        sections = planner_layout.get("sections", [])
        sections_layout_instruction = "\n".join(f"### {sec}" for sec in sections)

        structured_llm = llm.with_structured_output(FinalEducationalReport, method="json_mode")
        chain = judge_prompt | structured_llm
        logger.info("=" * 80)
        logger.info("JUDGE INPUT")
        logger.info("=" * 80)

        logger.info(f"QUERY:\n{state.get('query','')}\n")

        logger.info(f"FUNDAMENTAL:\n{fund_report_json}\n")

        logger.info(f"TECHNICAL:\n{tech_report_json}\n")

        logger.info(f"SENTIMENT:\n{sent_report_json}\n")

        logger.info(f"VERIFIER:\n{ver_feedback_json}\n")
        
        logger.info(f"GROUNDING CONTEXT:\n{grounding_context}\n")
        
        logger.info(f"PEER SUMMARY:\n{peer_summary}\n")

        logger.info("=" * 80)
        report: FinalEducationalReport = await chain.ainvoke({
            "fundamental_report": fund_report_json,
            "technical_report": tech_report_json,
            "sentiment_report": sent_report_json,
            "verifier_feedback": ver_feedback_json,
            "grounding_context": grounding_context,
            "peer_summary": peer_summary,
            "query": state.get("query", ""),
            "primary_intent": primary_intent,
            "secondary_intent": secondary_intent,
            "sections_layout_instruction": sections_layout_instruction,
        })
        logger.info("=" * 80)
        logger.info("JUDGE OUTPUT")
        logger.info("=" * 80)
        logger.info(report.model_dump_json(indent=2))
        logger.info("=" * 80)
        # Get company name directly from grounding_data
        ticker = state.get("ticker") or ""
        grounding_data = state.get("grounding_data")
        if grounding_data and grounding_data.get("company_name"):
            comp_name_metric = grounding_data.get("company_name")
            if isinstance(comp_name_metric, dict):
                report.company_name = comp_name_metric.get("value", ticker)
            else:
                report.company_name = getattr(comp_name_metric, "value", ticker)
        else:
            report.company_name = ticker


        # ===== STEP 4: CALCULATE OVERALL CONFIDENCE =====
        overall_conf = _calculate_overall_confidence(
            fund_report, tech_report, sent_report, fund_populated, tech_populated, sent_populated
        )
        
        report.overall_confidence_score = overall_conf
        report.data_freshness = datetime.utcnow().isoformat()
        # NOTE: peer_comparison is built by response_builder from grounding_data.peers.
        # ResearchState does not carry a peer_comparison key, so no attachment is needed here.
        # ===== STEP 5: DEBUG LOGGING =====
        execution_ms = int((time.time() - start_time) * 1000)
        
        sections_populated = []
        if fund_populated:
            sections_populated.append("fundamentals")
        if tech_populated:
            sections_populated.append("technicals")
        if sent_populated:
            sections_populated.append("sentiment")
        
        sections_missing = []
        if not fund_populated:
            sections_missing.append("fundamentals")
        if not tech_populated:
            sections_missing.append("technicals")
        if not sent_populated:
            sections_missing.append("sentiment")
        
        debug_logger.log_synthesis_result(
            outlook_label=report.outlook_label,
            conviction_level=report.conviction_level,
            overall_confidence=overall_conf,
            sections_populated=sections_populated,
            sections_missing=sections_missing,
            synthesis_quality="high" if len(sections_populated) >= 2 else "partial",
        )
        
        debug_logger.log_node_execution(
            node_name="judge",
            status=NodeStatus.SUCCESS,
            input_state={
                "query": state.get("query", "")[:50],
                "reports_available": {
                    "fundamental": fund_populated,
                    "technical": tech_populated,
                    "sentiment": sent_populated,
                }
            },
            output_state={
                "outlook": report.outlook_label,
                "confidence": overall_conf,
                "sections": sections_populated,
            },
            execution_ms=execution_ms,
            confidence_score=overall_conf,
        )
        
        logger.info(
            f"Judge synthesis completed. Outlook: {report.outlook_label} | "
            f"Conviction: {report.conviction_level} | Confidence: {overall_conf}% | "
            f"Sections: {len(sections_populated)} populated"
        )
        
        report_dict = report.model_dump()

        # Apply programmatic verifier corrections to all textual fields (Requirement 4)
        # Sprint 1 fix 1: use a distinct variable name to avoid shadowing ver_feedback_json
        # Sprint 1 fix 2: use .get() with guards so a malformed correction dict never raises KeyError
        reflection_raw = state.get("reflection_feedback") or {}
        corrections = reflection_raw.get("corrections") or []
        if corrections:
            logger.info(f"Applying {len(corrections)} verifier corrections to final report fields")
            for field in ["executive_summary", "fundamental_synthesis", "technical_synthesis", "sentiment_synthesis", "company_overview"]:
                val = report_dict.get(field)
                if val and isinstance(val, str):
                    for corr in corrections:
                        if not isinstance(corr, dict):
                            continue
                        incorrect = corr.get("incorrect", "")
                        correct = corr.get("correct", "")
                        if not incorrect:
                            # Skip malformed or empty correction entries
                            continue
                        val = val.replace(incorrect, correct)
                    report_dict[field] = val

        # NOTE: peer_comparison is assembled in response_builder from grounding_data.peers
        # and injected into the final_report dict there. No action required here.

        return {
            "final_report": report_dict
        }
        
    except Exception as e:
        execution_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Judge synthesis failed: {e}")
        
        debug_logger.log_node_execution(
            node_name="judge",
            status=NodeStatus.FAILED,
            input_state={},
            output_state={},
            execution_ms=execution_ms,
            error_message=str(e),
        )
        
        return {"final_report": _fallback_final_report(state, f"Judge synthesis failed: {str(e)[:120]}")}
