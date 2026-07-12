"""
Chief Investment Officer / Judge Node
Synthesizes the expert analyst reports into a SEBI-compliant educational report.
Uses strictly typed Pydantic output.

CRITICAL FIXES:
- Properly detects report content before saying "null"
- Never says a report is null if data is present
- Synthesizes partial outputs correctly
- Logs all decisions for debugging
"""
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

llm = ChatGroq(
    temperature=0.2,
    model_name="llama-3.1-8b-instant",
    api_key=settings.GROQ_API_KEY
) if settings.GROQ_API_KEY else None

judge_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are an Elite Institutional Equity Research Analyst and Principal Financial Advisor.
Format the response as a JSON object matching the FinalEducationalReport schema.
Your goal is to help the user understand the company or financial concept by providing a single, fluid conversational narrative, mimicking a dialogue with an experienced human analyst at a leading firm.

CRITICAL PRESENTATION & SYNTHESIS RULES:

1. CORE IDENTITY & VOICE:
   - Speak with the voice of a senior institutional equity researcher (e.g., Morgan Stanley or JP Morgan). Use natural, balanced, and authoritative financial language.
   - Do NOT act like a tutoring chatbot, glossary, or automated report compiler. 

2. ANSWER-FIRST BEHAVIOUR:
   - The first 1-2 sentences of the `executive_summary` MUST directly answer the user's question.
   - Never begin with boilerplate company introductions (e.g., "TCS is a leading IT services company..."), sector overviews, dictionary definitions, or historical setups unless explicitly requested. Start directly with the core insight addressing the query.

3. UNIFIED SYNTHESIS & INFORMATION PRIORITY:
   - Mentally evaluate the expert reports (Fundamental, Technical, Sentiment) and identify the SINGLE most important driver (the primary catalyst) behind the company's valuation, price action, or risks. 
   - Lead the narrative with this primary catalyst. Support it with details, and relegate secondary metrics to a supportive discussion later. Never give equal weight to every analyst output.
   - Blend fundamental metrics (margins, return ratios), technical trends (support, momentum), and sentiment indicators (news flow) into one continuous story. Do NOT separate them into independent blocks or announce them (e.g., avoid "On the technical front...").

4. REMOVE REPORT STRUCTURE & HEADINGS:
   - You must NEVER generate rigid report-style headings inside `executive_summary` (e.g., "Executive Summary", "Fundamental Analysis", "Technical Analysis", "Sentiment Analysis", "Risk Analysis", "Investment Perspective", "Conclusion").
   - The response must flow naturally as a single discussion. 
   - Standard markdown headings (###) are permitted ONLY when introducing a major transition in complex or educational queries (e.g., "### Why the stock has been falling" or "### How the PE Ratio works").

5. READING RHYTHM & PACING:
   - Vary your paragraph shapes. Mix short, punchy 1-2 sentence insights with longer analytical paragraphs to maintain reader momentum.
   - You may selectively use bulleted lists inside the narrative to list risks, drivers, or comparative metrics. This breaks up dense prose and manages cognitive load. Avoid uniform blocky paragraphs.

6. CONVERSATIONAL STATE & memory CONTINUITY:
   - If conversation history is present, continue the discussion naturally.
   - Do NOT re-introduce the company name, define basic terms, or repeat baseline overviews that were already established. Assume previous context is known. Shift topics smoothly.

7. DATA LIMITATIONS & DISCLOSURE LANGUAGE:
   - If data is missing, low confidence, or has provider conflicts, handle it naturally using professional institutional research language.
   - Do NOT use robotic phrases (like "Data unavailable" or "Information missing").
   - Instead, use terms like: "limited public disclosure restricts our analysis...", "reporting discrepancies between providers suggest...", "current evidence remains inconclusive regarding...".

8. BANNED ROBOTIC CLICHÉS:
   - Never write: "Based on the provided context", "According to the data", "As an AI", "In conclusion", "To summarize", "Refer to the dashboard", "The following analysis", "This report", "Executive Summary", "Fundamental Analysis", "Technical Analysis".
   - Avoid repetitive sentence starters like "This indicates", "This reflects", "This shows". Vary sentence structure naturally.

9. SEBI COMPLIANCE:
   - Never recommend buying, selling, or holding. Do NOT use "BUY", "SELL", "HOLD", or "TARGET PRICE". Explain strengths, weaknesses, risks, and uncertainties objectively. Never guarantee returns.

10. SCHEMA KEY ALLOCATION:
    - You must satisfy the schema constraints by returning all keys of FinalEducationalReport.
    - Write the main conversational markdown text inside `executive_summary`.
    - Populate optional synthesis fields (`fundamental_synthesis`, `technical_synthesis`, `sentiment_synthesis`, `company_overview`) with a brief, concise 1-2 sentence summary consistent with the main analysis, or keep them empty. Do NOT duplicate the complete conversation inside those fields.

PLANNER LAYOUT GUIDANCE:
The layout sections supplied through `{sections_layout_instruction}` represent thematic discussion guidelines.
Do NOT output these section names as markdown headers. Treat them strictly as topics to weave fluidly into your conversation in the order that makes the most analytical sense.

SCHEMA REFERENCE JSON:
{{
  "outlook_label": "Neutral Outlook",
  "conviction_level": "Low Confidence Scenario",
  "executive_summary": "Your fluid, conversational analysis directly answering the user query first.",
  "company_name": "Company Name",
  "company_overview": "Brief company overview fallback.",
  "investment_thesis": ["Key driver 1", "Key driver 2"],
  "fundamental_synthesis": "Brief 1-2 sentence fundamental summary.",
  "technical_synthesis": "Brief 1-2 sentence technical summary.",
  "sentiment_synthesis": "Brief 1-2 sentence sentiment summary.",
  "scenario_analysis": {{
    "bull_case": "Summary of bull case.",
    "base_case": "Summary of base case.",
    "bear_case": "Summary of bear case."
  }},
  "risk_analysis": ["Risk factor 1", "Risk factor 2"],
  "data_freshness": "2026-07-06T12:00:00Z",
  "overall_confidence_score": 50,
  "sebi_disclaimer": "This is AI-generated educational research for informational purposes only. It does NOT constitute SEBI-registered investment advice."
}}
"""),
    ("user", """QUERY INTENT:
Primary Intent: {primary_intent}
Secondary Intent: {secondary_intent}

EXPERT REPORTS:
FUNDAMENTAL:
{fundamental_report}

TECHNICAL:
{technical_report}

SENTIMENT:
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


def _fallback_final_report(state: ResearchState, reason: str) -> dict:
    """Build a SEBI-safe partial synthesis when the judge LLM is unavailable."""
    fund_report = state.get("fundamental_report") or {}
    tech_report = state.get("technical_report") or {}
    sent_report = state.get("sentiment_report") or {}
    populated = [r for r in (fund_report, tech_report, sent_report) if is_report_populated(r)]
    confidence_scores = [
        int((r.get("confidence") or {}).get("confidence_score") or 0)
        for r in populated
        if isinstance(r, dict)
    ]
    overall_conf = int(sum(confidence_scores) / len(confidence_scores)) if confidence_scores else 20
    return {
        "outlook_label": "Neutral Outlook",
        "conviction_level": "Low Confidence Scenario",
        "executive_summary": (
            "A partial educational analysis is available. Some synthesis components "
            f"could not be completed: {reason}"
        ),
        "company_overview": fund_report.get("summary") or "Company overview is unavailable from verified data.",
        "investment_thesis": [
            item for item in [
                fund_report.get("summary"),
                tech_report.get("summary"),
                sent_report.get("summary"),
            ] if item
        ][:5],
        "fundamental_synthesis": fund_report.get("summary") or "Insufficient data available for this analysis.",
        "technical_synthesis": tech_report.get("summary") or "Insufficient data available for this analysis.",
        "sentiment_synthesis": sent_report.get("summary") or "Insufficient data available for this analysis.",
        "scenario_analysis": {
            "bull_case": "Constructive outcomes depend on verified fundamentals, market conditions, and execution.",
            "base_case": "Use available evidence as educational context, not personalized investment advice.",
            "bear_case": "Missing or stale data materially reduces confidence in the analysis.",
        },
        "risk_analysis": [reason, "Partial data can omit material risks and recent events."],
        "data_freshness": state.get("data_freshness") or datetime.utcnow().isoformat(),
        "overall_confidence_score": overall_conf,
        "sebi_disclaimer": "This is AI-generated educational research for informational purposes only. It does NOT constitute SEBI-registered investment advice. Past performance is not indicative of future results.",
    }

async def judge_node(state: ResearchState) -> dict:
    """
    Synthesizes the verified reports into a final educational JSON report.
    
    CRITICAL: Properly detects which reports are populated before synthesis.
    """
    start_time = time.time()

    # Safety Validation: Verify requested ticker matches retrieved ticker before synthesis
    from src.services.entity_resolver import EntityResolver
    query = state.get("query", "")
    retrieved_ticker = state.get("ticker", "").upper().strip()
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
        intent = state.get("intent") or {}
        primary_intent = intent.get("primary_intent", "GENERALIZED")
        secondary_intent = intent.get("secondary_intent", "NONE")

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
        pruned_fund = {
            "summary": fund_report.get("summary", "N/A"),
            "financial_health": fund_report.get("financial_health", "N/A"),
            "competitive_moat": fund_report.get("competitive_moat", "N/A")
        } if fund_populated else {}
        
        pruned_tech = {
            "summary": tech_report.get("summary", "N/A"),
            "trend_analysis": tech_report.get("trend_analysis", "N/A"),
            "momentum_analysis": tech_report.get("momentum_analysis", "N/A")
        } if tech_populated else {}
        
        pruned_sent = {
            "summary": sent_report.get("summary", "N/A"),
            "sentiment_score": sent_report.get("sentiment_score", "N/A")
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
        ver_feedback = json.dumps(pruned_verifier, indent=2)
        
        # ===== STEP 3: INVOKE JUDGE =====
        planner_layout = intent.get("planner_layout", {})
        sections = planner_layout.get("sections", [])
        sections_layout_instruction = "\n".join(f"### {sec}" for sec in sections)

        structured_llm = llm.with_structured_output(FinalEducationalReport, method="json_mode")
        chain = judge_prompt | structured_llm
        
        report: FinalEducationalReport = await chain.ainvoke({
            "fundamental_report": fund_report_json,
            "technical_report": tech_report_json,
            "sentiment_report": sent_report_json,
            "verifier_feedback": ver_feedback,
            "query": state.get("query", ""),
            "primary_intent": primary_intent,
            "secondary_intent": secondary_intent,
            "sections_layout_instruction": sections_layout_instruction,
        })
        # Get company name directly from grounding_data
        ticker = state.get("ticker", "")
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
        overall_conf = 50
        confs = []
        
        if fund_populated and "confidence" in fund_report:
            fund_conf = fund_report["confidence"].get("confidence_score", 0)
            if fund_conf:
                confs.append(fund_conf)
        
        if tech_populated and "confidence" in tech_report:
            tech_conf = tech_report["confidence"].get("confidence_score", 0)
            if tech_conf:
                confs.append(tech_conf)
        
        if sent_populated and "confidence" in sent_report:
            sent_conf = sent_report["confidence"].get("confidence_score", 0)
            if sent_conf:
                confs.append(sent_conf)
        
        if confs:
            overall_conf = sum(confs) // len(confs)
        
        report.overall_confidence_score = overall_conf
        report.data_freshness = datetime.utcnow().isoformat()
        # Attach peer comparison generated by market_data / screener service
        if state.get("peer_comparison"):
            report.peer_comparison = state["peer_comparison"]
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
        ver_feedback = state.get("reflection_feedback") or {}
        corrections = ver_feedback.get("corrections", [])
        if corrections:
            logger.info(f"Applying {len(corrections)} verifier corrections to final report fields")
            for field in ["executive_summary", "fundamental_synthesis", "technical_synthesis", "sentiment_synthesis", "company_overview"]:
                val = report_dict.get(field)
                if val and isinstance(val, str):
                    for corr in corrections:
                        incorrect = corr["incorrect"]
                        correct = corr["correct"]
                        val = val.replace(incorrect, correct)
                    report_dict[field] = val

        if state.get("peer_comparison"):
            report_dict["peer_comparison"] = state["peer_comparison"]

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
