import logging
import json
import time
# pyrefly: ignore [missing-import]
from langchain_core.prompts import ChatPromptTemplate
# pyrefly: ignore [missing-import]
from langchain_groq import ChatGroq
from src.agents.state import ResearchState
from src.agents.schemas import VerificationOutput
from src.core.config import settings
from src.core.debug_logger import debug_logger, NodeStatus

logger = logging.getLogger(__name__)

llm_verifier = ChatGroq(
    temperature=0.0,  # Zero temperature for strict verification
    model_name="llama-3.1-8b-instant",
    api_key=settings.GROQ_API_KEY
) if settings.GROQ_API_KEY else None

verifier_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are the SEBI Compliance & Reliability Verifier. Format response as JSON matching VerificationOutput.
RULES FOR REJECTION (is_valid = False):
1. SEBI Violations: Any analyst uses BUY, SELL, TARGET PRICE, or guarantees returns.
2. Contradictions: Analyst reports contradict each other.
3. Hallucinations: Analyst cites a number/claim NOT in the original context.

Example JSON:
{{
  "is_valid": true,
  "contradictions_found": [],
  "hallucinations_detected": [],
  "sebi_violations": [
    {{
      "reason": "Used banned word 'BUY' in technical report"
    }}
  ],
  "feedback_for_reflection": "Clean compliance check"
}}"""),
    ("user", "Query: {query}\n\nContext:\n{context}\n\n---\n\nFundamental:\n{fundamental}\n\nTechnical:\n{technical}\n\nSentiment:\n{sentiment}")
])

async def verifier_node(state: ResearchState) -> dict:
    """
    Acts as a reliability gate, checking for hallucinations and compliance.
    
    CRITICAL: Never nulls out report sections. Downgrade confidence instead.
    If a report has issues, flag it but preserve the output with warnings.
    """
    start_time = time.time()
    intent = state.get("intent") or {}
    primary_intent = intent.get("primary_intent", "GENERALIZED")

    planner_layout = intent.get("planner_layout", {})
    required_agents = planner_layout.get("required_agents", [])

    if len(required_agents) < 2 or primary_intent not in ("STOCK_ANALYSIS", "GENERALIZED", "EARNINGS_REPORT", "FUNDAMENTAL_ANALYSIS", "COMPANY_ANALYSIS", "COMPANY_COMPARISON", "VALUATION_ANALYSIS", "RISK_ANALYSIS"):
        skipped = {
            "is_valid": True,
            "contradictions_found": [],
            "hallucinations_detected": [],
            "sebi_violations": [],
            "feedback_for_reflection": "Verification bypassed for focused query intent."
        }
        debug_logger.log_node_execution(
            node_name="verifier",
            status=NodeStatus.SKIPPED,
            input_state={"primary_intent": primary_intent},
            output_state={"reflection_feedback": skipped},
            execution_ms=0,
        )
        return {"reflection_feedback": skipped}
    
    if not llm_verifier:
        logger.warning("Groq API Key missing. Skipping verification.")
        
        debug_logger.log_node_execution(
            node_name="verifier",
            status=NodeStatus.SKIPPED,
            input_state={},
            output_state={},
            execution_ms=0,
            error_message="Verifier LLM not available",
        )
        
        # Fallback bypass - never null out reports
        return {"reflection_feedback": None}

    try:
        context_str = "\n".join([str(c) for c in state.get("context", [])])
        
        # Read the reports - NEVER null check here, use empty dicts
        fund_report = json.dumps(state.get("fundamental_report", {}))
        tech_report = json.dumps(state.get("technical_report", {}))
        sent_report = json.dumps(state.get("sentiment_report", {}))
        
        structured_llm = llm_verifier.with_structured_output(VerificationOutput, method="json_mode")
        chain = verifier_prompt | structured_llm

        verification: VerificationOutput = await chain.ainvoke({
            "query": state.get("query", ""),
            "context": context_str,
            "fundamental": fund_report,
            "technical": tech_report,
            "sentiment": sent_report
        })

        # Programmatic Grounding Checks (Phase 3)
        grounding_data = state.get("grounding_data")
        corrections = []
        if grounding_data and isinstance(grounding_data, dict):
            hallucinations = []
            
            def check_citations(report_dict, report_name):
                citations = report_dict.get("citations", [])
                if not isinstance(citations, list):
                    return
                for cit in citations:
                    metric = str(cit.get("metric", "")).lower().strip()
                    val_str = str(cit.get("value", "")).lower().strip()
                    
                    true_metric = None
                    if "price" in metric:
                        true_metric = grounding_data.get("current_price")
                    elif "pe" in metric or "p/e" in metric:
                        true_metric = grounding_data.get("pe_ratio")
                    elif "pb" in metric or "p/b" in metric:
                        true_metric = grounding_data.get("pb_ratio")
                    elif "book" in metric:
                        true_metric = grounding_data.get("book_value")
                    elif "roe" in metric:
                        true_metric = grounding_data.get("roe")
                    elif "roce" in metric:
                        true_metric = grounding_data.get("roce")
                    elif "dividend" in metric:
                        true_metric = grounding_data.get("dividend_yield")
                    elif "debt" in metric:
                        true_metric = grounding_data.get("debt_to_equity")
                    elif "rsi" in metric:
                        true_metric = grounding_data.get("rsi_14")
                    elif "sma" in metric or "ma" in metric:
                        if "20" in metric:
                            true_metric = grounding_data.get("sma_20")
                        elif "50" in metric:
                            true_metric = grounding_data.get("sma_50")
                    elif "macd" in metric:
                        if "signal" in metric:
                            true_metric = grounding_data.get("macd_signal")
                        else:
                            true_metric = grounding_data.get("macd")
                    elif "enterprise" in metric or "ev" == metric:
                        true_metric = grounding_data.get("enterprise_value")
                    elif "eps" in metric:
                        true_metric = grounding_data.get("eps")
                    elif "peg" in metric:
                        true_metric = grounding_data.get("peg_ratio")
                    elif "operating cash" in metric:
                        true_metric = grounding_data.get("operating_cash_flow")
                    elif "free cash" in metric or "fcf" in metric or "cash flow" in metric:
                        true_metric = grounding_data.get("free_cash_flow")
                    elif "revenue" in metric or "sales" in metric:
                        true_metric = grounding_data.get("annual_revenue")
                    elif "net income" in metric or "profit" in metric:
                        true_metric = grounding_data.get("net_income")
                        
                    true_val = None
                    if true_metric:
                        if isinstance(true_metric, dict):
                            true_val = true_metric.get("value")
                        else:
                            true_val = getattr(true_metric, "value", None)
                            
                    if true_val is not None:
                        try:
                            # 1. Percentage checking for roe/roce/dividend
                            if ("roe" in metric or "roce" in metric or "dividend" in metric) and "%" in val_str:
                                cit_val = float(val_str.replace("%", "").strip())
                                if abs(cit_val - (true_val * 100)) > 1.0:
                                    correct_str = f"{true_val * 100:.2f}%"
                                    hallucinations.append(f"In {report_name}: Cited {metric} as {val_str}, but ground truth is {correct_str}")
                                    corrections.append({
                                        "incorrect": val_str,
                                        "correct": correct_str
                                    })
                                continue

                            # 2. General check
                            clean_val_str = val_str.replace("₹", "").replace("$", "").replace("x", "").replace("%", "").replace(",", "").strip()
                            cit_val = float(clean_val_str)
                            
                            diff_normal = abs(cit_val - true_val)
                            diff_percent = abs(cit_val - (true_val * 100))
                            
                            is_wrong = False
                            correct_str = str(true_val)
                            
                            if "roe" in metric or "roce" in metric or "dividend" in metric or "margin" in metric:
                                if diff_normal > 1.0 and diff_percent > 1.0:
                                    is_wrong = True
                                    correct_str = f"{true_val * 100:.2f}%"
                            else:
                                if diff_normal > 1.0:
                                    is_wrong = True
                                    if "price" in metric or "book" in metric or "eps" in metric:
                                        correct_str = f"₹{true_val:,.2f}"
                                    elif "pe" in metric or "pb" in metric or "peg" in metric or "debt" in metric:
                                        correct_str = f"{true_val:.2f}x"
                                    elif "market" in metric or "enterprise" in metric or "revenue" in metric or "income" in metric or "cash" in metric:
                                        correct_str = f"₹{true_val / 1e7:.2f} Cr" if true_val >= 1e7 else f"₹{true_val:,.2f}"
                                        
                            if is_wrong:
                                hallucinations.append(f"In {report_name}: Cited {metric} as {val_str}, but ground truth is {correct_str}")
                                corrections.append({
                                    "incorrect": val_str,
                                    "correct": correct_str
                                })
                        except ValueError:
                            pass
            
            check_citations(state.get("fundamental_report", {}), "Fundamental Report")
            check_citations(state.get("technical_report", {}), "Technical Report")
            
            if hallucinations:
                verification.is_valid = False
                if verification.hallucinations_detected is None:
                    verification.hallucinations_detected = []
                for hall in hallucinations:
                    verification.hallucinations_detected.append({"reason": hall})
                verification.feedback_for_reflection = "Programmatic Grounding Verification failed: " + "; ".join(hallucinations)
        
        execution_ms = int((time.time() - start_time) * 1000)
        
        # Log verification results
        debug_logger.log_verifier_feedback(
            is_valid=verification.is_valid,
            contradictions=verification.contradictions_found or [],
            hallucinations=verification.hallucinations_detected or [],
            sebi_violations=verification.sebi_violations or [],
            feedback=verification.feedback_for_reflection or "No issues found",
        )
        
        debug_logger.log_node_execution(
            node_name="verifier",
            status=NodeStatus.SUCCESS if verification.is_valid else NodeStatus.PARTIAL,
            input_state={"query": state.get("query", "")},
            output_state={
                "is_valid": verification.is_valid,
                "issues_found": len(verification.contradictions_found or []) + len(verification.hallucinations_detected or []),
            },
            execution_ms=execution_ms,
            validation_errors=verification.hallucinations_detected or [],
        )
        
        logger.info(
            f"Verification completed. Is Valid: {verification.is_valid} | "
            f"Contradictions: {len(verification.contradictions_found or [])} | "
            f"Hallucinations: {len(verification.hallucinations_detected or [])} | "
            f"SEBI Violations: {len(verification.sebi_violations or [])}"
        )
        
        feedback_dict = verification.model_dump()
        feedback_dict["corrections"] = corrections
        
        return {
            "reflection_feedback": feedback_dict,
            "iteration_count": state.get("iteration_count", 0)
        }

    except Exception as e:
        execution_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Verification failed: {e}")
        
        debug_logger.log_node_execution(
            node_name="verifier",
            status=NodeStatus.FAILED,
            input_state={},
            output_state={},
            execution_ms=execution_ms,
            error_message=str(e),
        )
        
        # On failure, allow pass-through to prevent pipeline blockage
        # Never null out reports - they are valuable even if unverified
        return {"reflection_feedback": None}
