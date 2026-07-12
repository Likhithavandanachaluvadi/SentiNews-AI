"""
Unified Response Envelope Builder
Ensures all API responses conform to the standard response schema.
Transforms LangGraph outputs into frontend-friendly UnifiedResponseEnvelope.
"""

import uuid
from datetime import datetime
from typing import Optional, Dict, List, Any
from src.agents.schemas import (
    UnifiedResponseEnvelope,
    IntentMeta,
    ResponseMeta,
    ConfidenceMetrics,
    EvidenceCitation,
    SourceItem,
)
from src.core.debug_logger import logger

# UI BLOCK MAPPING: Intent -> List of components to render
UI_BLOCKS_BY_INTENT = {
    "STOCK_ANALYSIS": [
        "ExecutiveSummary",
        "ConfidenceGauge",
        "FundamentalCard",
        "TechnicalCard",
        "SentimentCard",
        "ScenarioCards",
        "RiskFactors",
        "Citations",
    ],
    "FUNDAMENTAL_ANALYSIS": [
        "ExecutiveSummary",
        "FundamentalCard",
        "ScenarioCards",
        "Citations",
    ],
    "TECHNICAL_ANALYSIS": [
        "TechnicalCard",
        "TechnicalMomentum",
        "Citations",
    ],
    "NEWS_ANALYSIS": [
        "NewsTimeline",
        "SentimentPulse",
        "Citations",
    ],
    "STOCK_MOVEMENT": [
        "MovementDrivers",
        "NewsTimeline",
        "SentimentPulse",
        "TechnicalMomentum",
        "Citations",
    ],
    "MARKET_OVERVIEW": [
        "MarketTrends",
        "SectorPerformance",
        "NewsHighlights",
        "RiskMetrics",
    ],
    "SENTIMENT_PULSE": [
        "SentimentMeter",
        "NewsTimeline",
        "KeyThemes",
        "Warnings",
    ],
    "EDUCATIONAL": [
        "EducationalExplainer",
        "Glossary",
        "ConceptCards",
        "References",
    ],
    "COMPARISON": [
        "ComparisonTable",
        "ChartComparison",
        "Strengths",
        "Weaknesses",
    ],
    "RESTRICTED_ADVISORY": [
        "SafeRefusal",
        "EducationalRedirect",
        "DisclaimerWarning",
    ],
    "GENERALIZED": [
        "ExecutiveSummary",
        "BasicExplainer",
        "RelatedContent",
    ],
    "MACROECONOMIC": [
        "MacroIndicators",
        "CentralBankActions",
        "RegionalImpact",
        "Citations",
    ],
}

INTENT_ALLOWED_SECTIONS = {
    "STOCK_ANALYSIS": {"fundamentals", "technicals", "sentiment", "valuation"},
    "FUNDAMENTAL_ANALYSIS": {"fundamentals", "valuation"},
    "TECHNICAL_ANALYSIS": {"technicals"},
    "STOCK_MOVEMENT": {"technicals", "sentiment"},
    "COMPANY_OVERVIEW": {"fundamentals", "sentiment"},
    "RISK_ANALYSIS": {"sentiment", "valuation"},
    "PEER_COMPARISON": {"fundamentals", "valuation"},
    "COMPARISON": set(),
    "NEWS_ANALYSIS": {"sentiment"},
    "SENTIMENT_PULSE": {"sentiment"},
    "MARKET_OVERVIEW": set(),
    "RESTRICTED_ADVISORY": set(),
    "MACROECONOMIC": set(),
    "EARNINGS_REPORT": {"fundamentals", "sentiment"},
    "GENERALIZED": {"fundamentals", "technicals", "sentiment", "valuation"},
}

INTENT_RESPONSE_BLOCKS = {
    "STOCK_ANALYSIS": {
        "executive_summary", "key_statistics", "fundamentals", "technicals",
        "sentiment", "valuation", "peer_comparison",
    },
    "FUNDAMENTAL_ANALYSIS": {
        "executive_summary", "key_statistics", "fundamentals", "valuation",
    },
    "TECHNICAL_ANALYSIS": {
        "technical_analysis", "indicators", "support_resistance", "momentum",
    },
    "STOCK_MOVEMENT": {
        "movement_summary", "technical_analysis", "recent_catalysts", "sentiment",
    },
    "NEWS_ANALYSIS": {
        "news_summary", "headlines", "sentiment",
    },
    "SENTIMENT_PULSE": {
        "sentiment", "news_highlights",
    },
    "EDUCATIONAL": {
        "educational_explanation",
    },
    "COMPARISON": {
        "comparison_summary", "comparison_table", "strengths", "weaknesses",
    },
    "MARKET_OVERVIEW": {
        "market_overview", "trends", "sectors",
    },
    "RESTRICTED_ADVISORY": {
        "executive_summary",
    },
    "GENERALIZED": {
        "executive_summary", "key_statistics", "fundamentals", "technicals",
        "sentiment", "valuation",
    },
}

SCHEMA_VERSION = "DQI-1.0"
SECTION_NAMES = ("fundamentals", "technicals", "sentiment", "valuation")
KEY_STAT_LABELS = {
    "Market Cap",
    "Current Price",
    "High / Low",
    "Stock P/E",
    "P/E Ratio (TTM)",
    "PEG Ratio",
    "Price to Book",
    "Price/Book",
    "Book Value",
    "Dividend Yield",
    "ROCE",
    "ROE",
    "Face Value",
    "EPS (TTM)",
    "Annual Revenue",
    "Net Profit Margin",
    "Debt/Equity Ratio",
}


def _confidence_score(report: Optional[Dict[str, Any]]) -> int:
    if not isinstance(report, dict):
        return 0
    confidence = report.get("confidence") or {}
    if isinstance(confidence, dict):
        return int(confidence.get("confidence_score") or 0)
    return 0


def _is_populated(report: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(report, dict) or not report:
        return False
    if report.get("status") == "skipped":
        return False
    if _confidence_score(report) > 0:
        return True
    return any(bool(report.get(key)) for key in ("summary", "financial_health", "trend_analysis", "momentum_analysis", "key_themes"))


def _section(
    *,
    name: str,
    report: Optional[Dict[str, Any]],
    synthesis: str = "",
    freshness: Optional[str],
    skipped_reason: Optional[str] = None,
) -> Dict[str, Any]:
    populated = _is_populated(report) or bool(synthesis)
    report_status = report.get("status") if isinstance(report, dict) else None
    status = "available" if populated else "skipped" if skipped_reason or report_status == "skipped" else "unavailable"
    warning = skipped_reason or (report.get("summary") if isinstance(report, dict) and report_status == "skipped" else None) or (None if populated else "Insufficient verified data was returned for this section.")
    return {
        "status": status,
        "data": report if isinstance(report, dict) else {},
        "synthesis": synthesis or "",
        "confidence": _confidence_score(report),
        "warnings": [warning] if warning else [],
        "data_freshness": freshness,
        "source_quality": "Tier 1" if name in ("fundamentals", "technicals") and populated else "Tier 2" if populated else "Unavailable",
        "retrieval_status": "verified" if populated else "missing",
    }


from src.services.market_data import _format_inr

def wrap_metric(metric: Any, formatted_value: str) -> Dict[str, Any]:
    """
    Wraps a metric from grounding_data into a structured dict with all Sprint 5.1.2 audit fields.
    """
    if not metric:
        return {
            "value": None,
            "source": "N/A",
            "timestamp": "N/A",
            "confidence": 0.0,
            "source_url": None,
            "raw_value": None,
            "normalized_value": None,
            "display_value": formatted_value,
            "validation_status": "PASS",
            "other_provider_values": None,
            "selected_provider": "N/A",
            "validation_reason": "No metric returned"
        }
    
    # If metric is already a dict
    if isinstance(metric, dict):
        val = metric.get("value")
        display_val = metric.get("display_value") or formatted_value
        return {
            "value": val,
            "source": metric.get("source", "N/A"),
            "timestamp": metric.get("timestamp", "N/A"),
            "confidence": metric.get("confidence", 0.0),
            "source_url": metric.get("source_url", None),
            "raw_value": metric.get("raw_value"),
            "normalized_value": metric.get("normalized_value"),
            "display_value": display_val,
            "validation_status": metric.get("validation_status", "PASS"),
            "other_provider_values": metric.get("other_provider_values"),
            "selected_provider": metric.get("selected_provider", "N/A"),
            "validation_reason": metric.get("validation_reason")
        }
        
    # If metric is a Pydantic object
    val = getattr(metric, "value", None)
    display_val = getattr(metric, "display_value", None) or formatted_value
    return {
        "value": val,
        "source": getattr(metric, "source", "N/A"),
        "timestamp": getattr(metric, "timestamp", "N/A"),
        "confidence": getattr(metric, "confidence", 0.0),
        "source_url": getattr(metric, "source_url", None),
        "raw_value": getattr(metric, "raw_value", None),
        "normalized_value": getattr(metric, "normalized_value", None),
        "display_value": display_val,
        "validation_status": getattr(metric, "validation_status", "PASS"),
        "other_provider_values": getattr(metric, "other_provider_values", None),
        "selected_provider": getattr(metric, "selected_provider", "N/A"),
        "validation_reason": getattr(metric, "validation_reason", None)
    }


def key_statistics_markdown(stats: Dict[str, str]) -> str:
    if not stats:
        return ""
    lines = ["### Screener Key Statistics", "| Metric | Value |", "| :--- | :--- |"]
    for label, value in stats.items():
        lines.append(f"| {label} | {value} |")
    return "\n".join(lines)


def extract_key_statistics_from_context(context: Optional[List[Any]]) -> Dict[str, str]:
    stats: Dict[str, str] = {}
    for ctx in context or []:
        for line in str(ctx).splitlines():
            if ":" not in line:
                continue
            label, value = [part.strip(" -*") for part in line.split(":", 1)]
            if label in KEY_STAT_LABELS and value:
                stats[label] = value
    return stats


def extract_peer_comparison_from_context(context: Optional[List[Any]]) -> str:
    lines: List[str] = []
    capture = False
    for ctx in context or []:
        for line in str(ctx).splitlines():
            normalized = line.strip()
            if "peer comparison" in normalized.lower():
                capture = True
            if capture and normalized.startswith("|"):
                lines.append(normalized)
    return "\n".join(lines)


def _allowed_blocks_for_intent(intent: str, has_company: bool) -> set:
    allowed = set(INTENT_RESPONSE_BLOCKS.get(intent, INTENT_RESPONSE_BLOCKS["GENERALIZED"]))
    if intent == "EDUCATIONAL" and has_company:
        allowed.add("key_statistics")
    return allowed


def _first_text(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, list):
            text = "\n".join(str(item) for item in value if item)
            if text.strip():
                return text
    return ""


def build_sections(
    *,
    intent: str,
    final_report: Optional[Dict[str, Any]],
    fundamental_report: Optional[Dict[str, Any]],
    technical_report: Optional[Dict[str, Any]],
    sentiment_report: Optional[Dict[str, Any]],
    data_freshness: Optional[str],
    context: Optional[List[Any]] = None,
    key_statistics: Optional[Dict[str, str]] = None,
    peer_comparison: Optional[str] = None,
    allowed_sections: Optional[set] = None,
) -> Dict[str, Any]:
    final_report = final_report or {}
    if key_statistics is None:
        key_statistics = extract_key_statistics_from_context(context)
    if peer_comparison is None:
        peer_comparison = final_report.get("peer_comparison") or extract_peer_comparison_from_context(context)
    enriched_fundamental_report = dict(fundamental_report or {})
    if key_statistics:
        enriched_fundamental_report["key_statistics"] = key_statistics
    if peer_comparison:
        enriched_fundamental_report["peer_comparison"] = peer_comparison
    from src.agents.planner import ResponsePlanner
    planner_layout = ResponsePlanner.get_layout(intent)
    required_agents = planner_layout.get("required_agents", [])

    skip_fundamentals = None if "fundamental" in required_agents else "Analysis skipped for this query type."
    skip_technicals = None if "technical" in required_agents else "Analysis skipped for this query type."
    skip_sentiment = None if "sentiment" in required_agents else "Analysis skipped for this query type."
    skip_valuation = None if ("fundamental" in required_agents or "comparison" in intent.lower()) else "Analysis skipped for this query type."

    if allowed_sections is not None:
        if "fundamentals" not in allowed_sections:
            skip_fundamentals = "Analysis skipped for this query type."
            enriched_fundamental_report = {}
            key_statistics = {}
        if "technicals" not in allowed_sections:
            skip_technicals = "Analysis skipped for this query type."
            technical_report = {}
        if "sentiment" not in allowed_sections:
            skip_sentiment = "Analysis skipped for this query type."
            sentiment_report = {}
        if "valuation" not in allowed_sections:
            skip_valuation = "Analysis skipped for this query type."

    def section_allowed(section_name: str) -> bool:
        return allowed_sections is None or section_name in allowed_sections

    return {
        "fundamentals": _section(
            name="fundamentals",
            report=enriched_fundamental_report,
            synthesis="\n\n".join(
                part for part in [
                    final_report.get("fundamental_synthesis", ""),
                    key_statistics_markdown(key_statistics),
                ] if part
            ) if section_allowed("fundamentals") else "",
            freshness=data_freshness,
            skipped_reason=skip_fundamentals,
        ),
        "technicals": _section(
            name="technicals",
            report=technical_report,
            synthesis=final_report.get("technical_synthesis", "") if section_allowed("technicals") else "",
            freshness=data_freshness,
            skipped_reason=skip_technicals,
        ),
        "sentiment": _section(
            name="sentiment",
            report=sentiment_report,
            synthesis=final_report.get("sentiment_synthesis", "") if section_allowed("sentiment") else "",
            freshness=data_freshness,
            skipped_reason=skip_sentiment,
        ),
        "valuation": _section(
            name="valuation",
            report={
                "scenario_analysis": final_report.get("scenario_analysis", {}) if section_allowed("valuation") else {},
                "investment_thesis": final_report.get("investment_thesis", []) if section_allowed("valuation") else [],
                "risks": final_report.get("risk_analysis", []) if section_allowed("valuation") else [],
                "peer_comparison": peer_comparison if section_allowed("valuation") else "",
            },
            synthesis="\n\n".join(
                part for part in [
                    peer_comparison if section_allowed("valuation") else "",
                    "\n".join(final_report.get("investment_thesis", []) or []) if section_allowed("valuation") else "",
                ] if part
            ),
            freshness=data_freshness,
            skipped_reason=skip_valuation,
        ),
    }


def extract_citations_from_context(context: Optional[List[Any]]) -> List[Dict[str, str]]:
    citations: List[Dict[str, str]] = []
    for ctx in context or []:
        ctx_str = str(ctx).strip()
        if ctx_str.startswith("[") and " - " in ctx_str:
            try:
                date_part, rest = ctx_str.split("] ", 1)
                source_part, title_desc = rest.split(" - ", 1)
                title = title_desc.split(": ", 1)[0]
                citations.append({
                    "source_name": source_part.strip(),
                    "metric": title.strip()[:120],
                    "value": date_part[1:].strip(),
                    "trust_tier": "Tier 2",
                })
            except Exception:
                continue
        elif "financial snapshot" in ctx_str.lower() or "screener" in ctx_str.lower():
            citations.append({
                "source_name": "yFinance/Screener",
                "metric": ctx_str.splitlines()[0][:120],
                "value": "live market context",
                "trust_tier": "Tier 1",
            })
    return citations[:20]


def _source_value(item: Any, key: str, default: str = "") -> str:
    if isinstance(item, dict):
        value = item.get(key, default)
    else:
        value = getattr(item, key, default)
    return str(value or "").strip()


def _add_source(
    sources: List[SourceItem],
    seen_urls: set[str],
    *,
    title: str,
    url: str,
    source_type: str,
) -> None:
    clean_url = str(url or "").strip()
    if not clean_url:
        return

    normalized_url = clean_url.rstrip("/").lower()
    if normalized_url in seen_urls:
        return

    seen_urls.add(normalized_url)
    sources.append(SourceItem(
        title=str(title or source_type or "Source").strip(),
        url=clean_url,
        source_type=str(source_type or "Source").strip(),
    ))


def _iter_grounding_url_items(
    value: Any,
    *,
    parent_key: str = "",
) -> List[Dict[str, str]]:
    if isinstance(value, dict):
        url = (
            _source_value(value, "url")
            or _source_value(value, "source_url")
            or _source_value(value, "document_url")
            or _source_value(value, "pdf_url")
            or _source_value(value, "link")
        )
        items: List[Dict[str, str]] = []
        if url:
            source = _source_value(value, "source") or _source_value(value, "provider")
            title = (
                _source_value(value, "title")
                or _source_value(value, "name")
                or _source_value(value, "metric")
                or _source_value(value, "date")
                or parent_key.replace("_", " ").title()
                or source
            )
            items.append({
                "title": title or "Source",
                "url": url,
                "source_type": source or parent_key.replace("_", " ").title() or "Source",
            })

        for key, nested_value in value.items():
            items.extend(
                _iter_grounding_url_items(
                    nested_value,
                    parent_key=str(key),
                )
            )
        return items

    if isinstance(value, list):
        items: List[Dict[str, str]] = []
        for nested_value in value:
            items.extend(
                _iter_grounding_url_items(
                    nested_value,
                    parent_key=parent_key,
                )
            )
        return items

    return []


def _build_source_links(
    *,
    ticker: Optional[str],
    query: str,
    company_name: str,
    news_articles: Optional[List[Dict[str, Any]]],
    grounding_data: Optional[Dict[str, Any]],
) -> List[SourceItem]:
    sources_list: List[SourceItem] = []
    seen_urls: set[str] = set()

    # Direct article/document URLs already retrieved from providers.
    for article in news_articles or []:
        article_url = _source_value(article, "url")
        if not article_url:
            continue

        publisher = (
            _source_value(article, "source")
            or _source_value(article, "provider")
            or "News Source"
        )
        title = _source_value(article, "title") or f"{publisher} article"
        provider = _source_value(article, "provider")
        source_type = publisher or provider or "News Article"

        _add_source(
            sources_list,
            seen_urls,
            title=title,
            url=article_url,
            source_type=source_type,
        )

    # Structured grounding data may carry real provider/document URLs now or in
    # future retrievers. Only expose URLs that are present in that payload.
    for item in _iter_grounding_url_items(grounding_data or {}):
        _add_source(
            sources_list,
            seen_urls,
            title=item["title"],
            url=item["url"],
            source_type=item["source_type"],
        )

    return sources_list


def build_response(
    * ,
    intent_data: Dict[str, Any],
    final_report: Optional[Dict[str, Any]],
    ticker: Optional[str] = None,
    query: str = "",
    execution_logs: Optional[List[Dict[str, Any]]] = None,
    ui_blocks_override: Optional[List[str]] = None,
    data_freshness: Optional[str] = None,
    generation_time_ms: int = 0,
    fundamental_report: Optional[Dict[str, Any]] = None,
    technical_report: Optional[Dict[str, Any]] = None,
    sentiment_report: Optional[Dict[str, Any]] = None,
    context: Optional[List[Any]] = None,
    warnings: Optional[List[str]] = None,
    news_articles: Optional[List[Dict[str, Any]]] = None,
    conversation_id: Optional[str] = None,
    grounding_data: Optional[Dict[str, Any]] = None,
) -> UnifiedResponseEnvelope:
    """
    Transforms LangGraph output into UnifiedResponseEnvelope.
    """
    final_report = final_report or {}
    
    # Extract intent details
    primary_intent = intent_data.get("primary_intent", "GENERALIZED")
    secondary_intent = intent_data.get("secondary_intent", "NONE")
    intent_confidence = intent_data.get("intent_confidence", 0.5)
    query_risk_level = intent_data.get("query_risk_level", "LOW")
    query_risk_score = intent_data.get("query_risk_score", 0.0)
    complexity_level = intent_data.get("complexity_level", "LIGHT")
    classification_reasoning = intent_data.get("classification_reasoning", "")
    
    # Determine UI blocks from the final intent policy. Upstream planner blocks can be
    # broader than the response payload, so the response builder is authoritative here.
    ui_blocks = UI_BLOCKS_BY_INTENT.get(primary_intent, UI_BLOCKS_BY_INTENT["GENERALIZED"])
    
    # Build intent metadata
    intent_meta = IntentMeta(
        primary_intent=primary_intent,
        secondary_intent=secondary_intent if secondary_intent != "NONE" else None,
        intent_confidence=intent_confidence,
        query_risk_level=query_risk_level,
        query_risk_score=query_risk_score,
        complexity_level=complexity_level,
        classification_reasoning=classification_reasoning,
    )
    
    # Build response metadata
    if data_freshness is None:
        data_freshness = datetime.utcnow().isoformat()
    
    response_meta = ResponseMeta(
        report_id=str(uuid.uuid4()),
        ticker=ticker,
        data_freshness=data_freshness,
        generation_time_ms=generation_time_ms,
        created_at=datetime.utcnow().isoformat(),
        conversation_id=conversation_id,
    )
    
    # Extract summary and data from final report
    summary = ""
    data_payload: Dict[str, Any] = {}
    confidence_metrics: Optional[ConfidenceMetrics] = None
    citations = extract_citations_from_context(context)
    response_warnings = list(warnings or [])
    
    # Map key statistics and peers directly from grounding data (Phase 5)
    key_statistics = {}
    peer_comparison = ""
    peers_list = []
    tech_indicators = {}
    
    # Determine allowed sections based on intent and company context
    has_company = bool(ticker and ticker.upper() not in ("N/A", "NIFTY"))
    allowed_blocks = _allowed_blocks_for_intent(primary_intent, has_company)
    if primary_intent == "EDUCATIONAL":
        allowed_sections = set()
    else:
        allowed_sections = INTENT_ALLOWED_SECTIONS.get(primary_intent, INTENT_ALLOWED_SECTIONS["GENERALIZED"])

    # Normalize and wrap metrics from grounding_data
    if not grounding_data:
        grounding_data = {}
        
    def val_of(m_key):
        m = grounding_data.get(m_key)
        if not m:
            return None
        if isinstance(m, dict):
            return m.get("value")
        return getattr(m, "value", None)

    if "key_statistics" in allowed_blocks:
        m_cap = val_of("market_cap")
        c_price = val_of("current_price")
        high = val_of("fifty_two_week_high")
        low = val_of("fifty_two_week_low")
        pe = val_of("pe_ratio")
        peg = val_of("peg_ratio")
        pb = val_of("pb_ratio")
        bv = val_of("book_value")
        div_y = val_of("dividend_yield")
        roce = val_of("roce")
        roe = val_of("roe")
        de = val_of("debt_to_equity")
        eps = val_of("eps")
        ev = val_of("enterprise_value")
        rev = val_of("annual_revenue")
        ni = val_of("net_income")
        ocf = val_of("operating_cash_flow")
        fcf = val_of("free_cash_flow")

        key_statistics = {
            "Market Cap": wrap_metric(
                grounding_data.get("market_cap"),
                f"₹{m_cap / 10000000:,.2f} Cr" if m_cap else "N/A"
            ),
            "Current Price": wrap_metric(
                grounding_data.get("current_price"),
                f"₹{c_price:,.2f}" if c_price else "N/A"
            ),
            "High / Low": wrap_metric(
                grounding_data.get("fifty_two_week_high") or grounding_data.get("fifty_two_week_low"),
                f"₹{high:,.2f} / ₹{low:,.2f}" if (high and low) else "N/A"
            ),
            "P/E Ratio (TTM)": wrap_metric(
                grounding_data.get("pe_ratio"),
                f"{pe:.2f}x" if pe else "N/A"
            ),
            "PEG Ratio": wrap_metric(
                grounding_data.get("peg_ratio"),
                f"{peg:.2f}x" if peg else "N/A"
            ),
            "Price to Book": wrap_metric(
                grounding_data.get("pb_ratio"),
                f"{pb:.2f}x" if pb else "N/A"
            ),
            "Book Value": wrap_metric(
                grounding_data.get("book_value"),
                f"₹{bv:,.2f}" if bv else "N/A"
            ),
            "Dividend Yield": wrap_metric(
                grounding_data.get("dividend_yield"),
                f"{div_y * 100:.2f}%" if div_y else "N/A"
            ),
            "ROCE": wrap_metric(
                grounding_data.get("roce"),
                f"{roce * 100:.2f}%" if roce else "N/A"
            ),
            "ROE": wrap_metric(
                grounding_data.get("roe"),
                f"{roe * 100:.2f}%" if roe else "N/A"
            ),
            "Debt/Equity Ratio": wrap_metric(
                grounding_data.get("debt_to_equity"),
                f"{de:.2f}x" if de else "N/A"
            ),
            "Face Value": wrap_metric(None, "N/A"),
            "EPS (TTM)": wrap_metric(
                grounding_data.get("eps"),
                f"₹{eps:.2f}" if eps else "N/A"
            ),
            "Enterprise Value": wrap_metric(
                grounding_data.get("enterprise_value"),
                f"₹{ev / 10000000:,.2f} Cr" if ev else "N/A"
            ),
            "Annual Revenue": wrap_metric(
                grounding_data.get("annual_revenue"),
                _format_inr(rev) if rev else "N/A"
            ),
            "Net Income": wrap_metric(
                grounding_data.get("net_income"),
                _format_inr(ni) if ni else "N/A"
            ),
            "Operating Cash Flow": wrap_metric(
                grounding_data.get("operating_cash_flow"),
                _format_inr(ocf) if ocf else "N/A"
            ),
            "Free Cash Flow": wrap_metric(
                grounding_data.get("free_cash_flow"),
                _format_inr(fcf) if fcf else "N/A"
            ),
        }
    if "peer_comparison" in allowed_blocks or "comparison_table" in allowed_blocks:
        peers_list = grounding_data.get("peers") or []

    if "technicals" in allowed_sections:
        tech_indicators = {
            "rsi_14": wrap_metric(grounding_data.get("rsi_14"), val_of("rsi_14")),
            "sma_20": wrap_metric(grounding_data.get("sma_20"), val_of("sma_20")),
            "sma_50": wrap_metric(grounding_data.get("sma_50"), val_of("sma_50")),
            "macd": wrap_metric(grounding_data.get("macd"), val_of("macd")),
            "macd_signal": wrap_metric(grounding_data.get("macd_signal"), val_of("macd_signal")),
            "technical_trend": wrap_metric(grounding_data.get("technical_trend"), val_of("technical_trend")),
            "technical_momentum": wrap_metric(grounding_data.get("technical_momentum"), val_of("technical_momentum")),
        }
    
    # Build peer comparison markdown table for fallback usage
    if ("peer_comparison" in allowed_blocks or "comparison_table" in allowed_blocks) and peers_list:
        m_cap = val_of("market_cap")
        pe = val_of("pe_ratio")
        roe = val_of("roe")
        lines = ["| Metric | Co. | " + " | ".join([p.get("ticker") if isinstance(p, dict) else getattr(p, "ticker", "") for p in peers_list]) + " |",
                 "| :--- | :--- | " + " | ".join([":---" for _ in peers_list]) + " |"]
        
        # Row 1: Market Cap
        lines.append("| Market Cap | " + (f"{m_cap / 10000000:,.2f} Cr" if m_cap else "N/A") + " | " + " | ".join([p.get("market_cap") if isinstance(p, dict) else getattr(p, "market_cap", "") for p in peers_list]) + " |")
        # Row 2: P/E Ratio
        lines.append("| P/E Ratio | " + (f"{pe:.2f}" if pe else "N/A") + " | " + " | ".join([p.get("stock_pe") if isinstance(p, dict) else getattr(p, "stock_pe", "") for p in peers_list]) + " |")
        # Row 3: ROE
        lines.append("| ROE | " + (f"{roe * 100:.2f}%" if roe else "N/A") + " | " + " | ".join([p.get("roe") if isinstance(p, dict) else getattr(p, "roe", "") for p in peers_list]) + " |")
        peer_comparison = "\n".join(lines)
        
    if final_report:
        final_report = dict(final_report)
        if peer_comparison:
            final_report["peer_comparison"] = peer_comparison
    
    if final_report:
        narrative = final_report.get("executive_summary", "")
        summary = narrative if "executive_summary" in allowed_blocks else ""
        educational_explanation = narrative if "educational_explanation" in allowed_blocks else ""
        news_summary = _first_text(final_report.get("sentiment_synthesis"), narrative) if "news_summary" in allowed_blocks else ""
        movement_summary = narrative if "movement_summary" in allowed_blocks else ""
        comparison_summary = narrative if "comparison_summary" in allowed_blocks else ""
        market_overview = narrative if "market_overview" in allowed_blocks else ""
        technical_analysis = final_report.get("technical_synthesis", "") if "technical_analysis" in allowed_blocks else ""
        sentiment_text = final_report.get("sentiment_synthesis", "") if "sentiment" in allowed_blocks else ""
        recent_catalysts = news_articles or []
        headlines = news_articles if "headlines" in allowed_blocks else []
        news_highlights = news_articles if "news_highlights" in allowed_blocks else []
        comparison_table = final_report.get("peer_comparison", "") if "comparison_table" in allowed_blocks else ""
        
        # Build data payload with all report sections
        data_payload = {
            "schema_version": SCHEMA_VERSION,
            "executive_summary": summary,
            "educational_explanation": educational_explanation,
            "movement_summary": movement_summary,
            "news_summary": news_summary,
            "comparison_summary": comparison_summary,
            "comparison_table": comparison_table,
            "market_overview": market_overview,
            "trends": final_report.get("technical_synthesis", "") if "trends" in allowed_blocks else "",
            "sectors": [],
            "outlook": final_report.get("outlook_label", "Neutral Outlook"),
            "conviction": final_report.get("conviction_level", "Low Confidence Scenario"),
            "fundamentals": final_report.get("fundamental_synthesis", "") if "fundamentals" in allowed_sections else "",
            "technicals": technical_analysis if "technicals" in allowed_sections else "",
            "technical_analysis": technical_analysis,
            "sentiment": sentiment_text,
            "company_name": final_report.get("company_name", ""),
            "company_overview": final_report.get("company_overview", "") if "fundamentals" in allowed_sections else "",
            "investment_thesis": final_report.get("investment_thesis", []) if "valuation" in allowed_sections else [],
            "scenario_analysis": final_report.get("scenario_analysis", {}) if "valuation" in allowed_sections else {},
            "risks": final_report.get("risk_analysis", []) if "valuation" in allowed_sections else [],
            "peer_comparison": final_report.get("peer_comparison", "") if "peer_comparison" in allowed_blocks else "",
            "strengths": final_report.get("investment_thesis", []) if "strengths" in allowed_blocks else [],
            "weaknesses": final_report.get("risk_analysis", []) if "weaknesses" in allowed_blocks else [],
            "recent_catalysts": recent_catalysts if "recent_catalysts" in allowed_blocks else [],
            "headlines": headlines,
            "news_highlights": news_highlights,
            "news_articles": (news_articles or []) if ("headlines" in allowed_blocks or "recent_catalysts" in allowed_blocks or "news_highlights" in allowed_blocks) else [],
            
            # Grounding structures (Phase 5)
            "key_statistics": key_statistics,
            "peers": peers_list if "peer_comparison" in allowed_blocks or "comparison_table" in allowed_blocks else [],
            "technical_indicators": tech_indicators if "indicators" in allowed_blocks or "technical_analysis" in allowed_blocks else {},
            "support_resistance": technical_report.get("key_levels", {}) if "support_resistance" in allowed_blocks and isinstance(technical_report, dict) else {},
            "momentum": technical_report.get("momentum_analysis", "") if "momentum" in allowed_blocks and isinstance(technical_report, dict) else "",
            "quarterly_reports": (grounding_data.get("quarterly_reports", []) if grounding_data else []) if "fundamentals" in allowed_sections else [],
            "annual_reports": (grounding_data.get("annual_reports", []) if grounding_data else []) if "fundamentals" in allowed_sections else [],
        }
        
        # Try to extract confidence metrics
        if isinstance(final_report.get("overall_confidence_score"), int):
            confidence_metrics = ConfidenceMetrics(
                confidence_score=final_report["overall_confidence_score"],
                uncertainty_level="Low" if final_report["overall_confidence_score"] > 70 else "Moderate" if final_report["overall_confidence_score"] > 40 else "High",
                confidence_reasoning=f"Synthesis confidence based on input quality and cross-analyst agreement.",
                missing_data_points=[],
            )
    else:
        response_warnings.append("Judge synthesis was unavailable; rendering partial analyst outputs.")
        data_payload = {
            "schema_version": SCHEMA_VERSION,
            "executive_summary": "",
            "educational_explanation": "",
            "movement_summary": "",
            "news_summary": "",
            "comparison_summary": "",
            "comparison_table": "",
            "market_overview": "",
            "key_statistics": key_statistics,
            "peers": peers_list if "peer_comparison" in allowed_blocks or "comparison_table" in allowed_blocks else [],
            "technical_indicators": tech_indicators if "indicators" in allowed_blocks or "technical_analysis" in allowed_blocks else {},
            "quarterly_reports": (grounding_data.get("quarterly_reports", []) if grounding_data else []) if "fundamentals" in allowed_sections else [],
            "annual_reports": (grounding_data.get("annual_reports", []) if grounding_data else []) if "fundamentals" in allowed_sections else [],
        }

    if primary_intent == "RESTRICTED_ADVISORY":
        summary = (
            "I cannot provide personalized investment advice or specific trade recommendations. "
            "However, this response can still provide educational context, risk factors, valuation considerations, "
            "and market evidence without making a buy or sell call."
        )
        response_warnings.append("Query contains advisory-risk language; response restricted to educational context.")

    sections = build_sections(
        intent=primary_intent,
        final_report=final_report,
        fundamental_report=fundamental_report,
        technical_report=technical_report,
        sentiment_report=sentiment_report,
        data_freshness=data_freshness,
        context=context,
        key_statistics=key_statistics,
        peer_comparison=peer_comparison,
        allowed_sections=allowed_sections,
    )

    for section_name, section in sections.items():
        if section["status"] != "available":
            response_warnings.extend(section.get("warnings", []))
    
    # Log response building
    logger.info(
        f"Built UnifiedResponseEnvelope: intent={primary_intent}, "
        f"ui_blocks={len(ui_blocks)}, confidence={confidence_metrics.confidence_score if confidence_metrics else 'N/A'}"
    )
    
    # Construct dynamic source links while preserving retrieved provenance.
    ticker_val = ticker or "NIFTY"
    company_name = final_report.get("company_name") or ticker_val
    sources_list = _build_source_links(
        ticker=ticker_val,
        query=query,
        company_name=company_name,
        news_articles=news_articles,
        grounding_data=grounding_data,
    )

    # Construct the unified envelope
    envelope = UnifiedResponseEnvelope(
        intent=intent_meta,
        meta=response_meta,
        summary=summary,
        data=data_payload,
        sections=sections,
        confidence=confidence_metrics,
        warnings=list(dict.fromkeys(response_warnings)),
        citations=citations,
        sources=sources_list,
        ui_blocks=ui_blocks,
        debug={
            "schema_version": SCHEMA_VERSION,
            "execution_logs": execution_logs or [],
            "retrieval_sources": [str(c)[:200] for c in (context or [])],
            "section_status": {name: section["status"] for name, section in sections.items()},
        },
    )
    
    return envelope
