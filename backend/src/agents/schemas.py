from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Literal, Dict, Any
from datetime import datetime

# ==========================================
# Core Confidence & Evidence Structures
# ==========================================

class EvidenceCitation(BaseModel):
    """Represents a validated citation for a factual claim."""
    source_name: str = Field(description="Name of the source (e.g., 'yFinance', 'Screener.in', 'Reuters')")
    metric: str = Field(description="The exact metric or fact cited")
    value: str = Field(description="The value of the metric")
    trust_tier: Literal["Tier 1", "Tier 2", "Tier 3"] = Field(
        description="Tier 1: Primary data (NSE, RBI, SEC). Tier 2: Reputable media (Reuters). Tier 3: Opinion/Blogs"
    )

class ConfidenceMetrics(BaseModel):
    """Standardized confidence scoring for all agents."""
    confidence_score: int = Field(ge=0, le=100, description="Confidence score from 0 to 100")
    uncertainty_level: Literal["Low", "Moderate", "Medium", "High"] = Field(description="Level of uncertainty due to missing or conflicting data")
    confidence_reasoning: str = Field(description="Explanation of why this confidence level was chosen")
    missing_data_points: List[str] = Field(default_factory=list, description="List of important data points that were missing from context")

    @field_validator("missing_data_points", mode="before")
    @classmethod
    def ensure_list(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            if v.strip() in ("", "N/A", "None", "[]"):
                return []
            return [v.strip()]
        if isinstance(v, list):
            return [str(x) for x in v]
        return []

# ==========================================
# Specific Analyst Output Schemas
# ==========================================

class FundamentalOutput(BaseModel):
    summary: str = Field(description="Executive summary of fundamental health")
    financial_health: str = Field(description="Analysis of revenue, profit, margins, and debt")
    competitive_moat: str = Field(description="Analysis of competitive advantages")
    key_factors: List[str] = Field(description="Key fundamental drivers")
    citations: List[EvidenceCitation] = Field(description="Evidence supporting fundamental claims")
    confidence: ConfidenceMetrics

class KeyLevels(BaseModel):
    support: str
    resistance: str

class TechnicalOutput(BaseModel):
    summary: str = Field(description="Summary of programmatic technical indicators")
    trend_analysis: str = Field(description="Analysis of SMAs, MACD, and price action")
    momentum_analysis: str = Field(description="Analysis of RSI and volume trends")
    key_levels: KeyLevels = Field(description="Support and resistance levels")
    citations: List[EvidenceCitation] = Field(description="Evidence based on programmatic technical data")
    confidence: ConfidenceMetrics

class SentimentOutput(BaseModel):
    summary: str = Field(description="Summary of recent news and social sentiment")
    sentiment_score: int = Field(ge=0, le=100, description="0 (Extremely Negative) to 100 (Extremely Positive)")
    key_themes: List[str] = Field(description="Recurring themes in recent news")
    citations: List[EvidenceCitation] = Field(description="Citations of specific news articles")
    confidence: ConfidenceMetrics

# ==========================================
# Verifier & Reflection Output Schemas
# ==========================================

class SebiViolation(BaseModel):
    reason: str = Field(description="Explanation of why this violates SEBI guidelines")

class VerificationOutput(BaseModel):
    """Output of the Verifier Agent acting as a reliability gate."""
    is_valid: bool = Field(description="True if all claims are supported and no SEBI violations exist")
    contradictions_found: List[str] = Field(default_factory=list, description="Contradictions between different analyst reports")
    hallucinations_detected: List[str] = Field(default_factory=list, description="Claims made without supporting evidence in context")
    sebi_violations: List[SebiViolation] = Field(default_factory=list, description="Uses of banned words like BUY, SELL, GUARANTEED")
    feedback_for_reflection: str = Field(description="Instructions for analysts if re-run is needed")

# ==========================================
# Final Judge / Synthesis Schema
# ==========================================

class ScenarioAnalysis(BaseModel):
    bull_case: Optional[str] = Field(default="", description="Optimistic educational scenario")
    base_case: Optional[str] = Field(default="", description="Most likely educational scenario")
    bear_case: Optional[str] = Field(default="", description="Pessimistic educational scenario")

class FinalEducationalReport(BaseModel):
    """The final SEBI-compliant educational intelligence report."""
    outlook_label: Literal[
        "Positive Long-Term Outlook", 
        "Neutral Outlook", 
        "Elevated Risk Outlook", 
        "Constructive Momentum", 
        "Weak Momentum",
        "Uncertain Outlook"
    ] = Field(default="Neutral Outlook", description="SEBI-safe educational outlook label")
    
    conviction_level: Literal["High Conviction", "Moderate Conviction", "Medium Conviction", "Low Confidence Scenario", "Medium Confidence Scenario"] = Field(default="Low Confidence Scenario")
    
    executive_summary: str = Field(description="Crisp, high-impact summary of the educational analysis")
    company_name: Optional[str] = None
    company_overview: Optional[str] = ""
    investment_thesis: List[str] = Field(default_factory=list, description="Key educational drivers (3-5 bullet points)")
    
    fundamental_synthesis: Optional[str] = ""
    technical_synthesis: Optional[str] = ""
    sentiment_synthesis: Optional[str] = ""
    
    scenario_analysis: Optional[ScenarioAnalysis] = Field(default_factory=lambda: ScenarioAnalysis())
    
    risk_analysis: List[str] = Field(default_factory=list, description="Major risks that could cause the thesis to fail")
    
    data_freshness: str = Field(description="Timestamp of when the latest data was retrieved")
    overall_confidence_score: int = Field(default=50, ge=0, le=100)
    
    sebi_disclaimer: str = Field(
        default="This is AI-generated educational research for informational purposes only. It does NOT constitute SEBI-registered investment advice. Past performance is not indicative of future results."
    )

    @field_validator("investment_thesis", "risk_analysis", mode="before")
    @classmethod
    def ensure_list(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            if v.strip() in ("", "N/A", "None", "[]"):
                return []
            return [v.strip()]
        if isinstance(v, list):
            return [str(x) for x in v]
        return []


# ==========================================
# Unified Response Envelope
# ==========================================

class IntentMeta(BaseModel):
    """Intent and risk metadata for the response."""
    primary_intent: str
    secondary_intent: Optional[str] = "NONE"
    intent_confidence: float
    query_risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    query_risk_score: float = 0.0
    complexity_level: Literal["LIGHT", "DEEP"]
    classification_reasoning: str

class ResponseMeta(BaseModel):
    """Operational metadata for the response."""
    report_id: str
    ticker: Optional[str] = None
    data_freshness: str
    generation_time_ms: int
    created_at: str
    conversation_id: Optional[str] = None

class SourceItem(BaseModel):
    title: str
    url: str
    source_type: str

class UnifiedResponseEnvelope(BaseModel):
    """
    The SINGLE predictable JSON structure returned by ALL API responses.
    
    The frontend only needs to handle this one shape.
    The `ui_blocks` list tells the frontend EXACTLY which components to render.
    
    Example ui_blocks by intent:
      STOCK_ANALYSIS:  ["ExecutiveSummary", "ConfidenceGauge", "FundamentalCard", "TechnicalCard", "SentimentCard", "ScenarioCards", "RiskFactors", "Citations"]
      STOCK_MOVEMENT:  ["MovementDrivers", "NewsTimeline", "SentimentPulse"]
      EDUCATIONAL:     ["EducationalExplainer", "Glossary"]
      RESTRICTED_ADVISORY: ["SafeRefusal", "EducationalRedirect"]
    """
    intent: IntentMeta
    meta: ResponseMeta
    summary: str = Field(description="Plain-language summary of the response")
    data: Dict[str, Any] = Field(default_factory=dict, description="Dynamic payload — content varies by intent")
    sections: Dict[str, Any] = Field(default_factory=dict, description="Stable report sections; every expected section is always present")
    confidence: Optional[ConfidenceMetrics] = None
    warnings: List[str] = Field(default_factory=list)
    citations: List[EvidenceCitation] = Field(default_factory=list)
    sources: List[SourceItem] = Field(default_factory=list, description="List of dynamic search source links for the sidebar")
    ui_blocks: List[str] = Field(
        description="Ordered list of UI component names the frontend should render"
    )
    debug: Optional[Dict[str, Any]] = Field(default=None, description="Internal debugging dashboard payload")
    sebi_disclaimer: str = Field(
        default="This is AI-generated educational research for informational purposes only. "
                "It does NOT constitute SEBI-registered investment advice. "
                "Past performance is not indicative of future results."
    )

# ==========================================
# Grounding Layer Data Schema
# ==========================================

class GroundedMetric(BaseModel):
    value: Any = None
    source: str = "N/A"
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    confidence: float = 0.0
    source_url: Optional[str] = None
    
    # Audit fields (Sprint 5.1.2)
    raw_value: Optional[Any] = None
    normalized_value: Optional[float] = None
    display_value: Optional[str] = None
    validation_status: str = "PASS"  # PASS, WARNING, FAIL
    other_provider_values: Optional[Dict[str, Any]] = None
    selected_provider: Optional[str] = None
    validation_reason: Optional[str] = None

class GroundingPeerItem(BaseModel):
    ticker: str
    name: str
    market_cap: str
    stock_pe: str
    roe: str

class GroundingHistoricalReport(BaseModel):
    date: str
    revenue: str
    net_income: str
    gross_margin: str
    operating_margin: str
    net_margin: str

class StockGroundingData(BaseModel):
    ticker: str
    company_name: str
    exchange: Optional[str] = "NSE"
    current_price: Optional[GroundedMetric] = None
    change_percent: Optional[GroundedMetric] = None
    fifty_two_week_high: Optional[GroundedMetric] = None
    fifty_two_week_low: Optional[GroundedMetric] = None
    market_cap: Optional[GroundedMetric] = None
    pe_ratio: Optional[GroundedMetric] = None
    peg_ratio: Optional[GroundedMetric] = None
    pb_ratio: Optional[GroundedMetric] = None
    book_value: Optional[GroundedMetric] = None
    eps: Optional[GroundedMetric] = None
    dividend_yield: Optional[GroundedMetric] = None
    roe: Optional[GroundedMetric] = None
    roce: Optional[GroundedMetric] = None
    debt_to_equity: Optional[GroundedMetric] = None
    profit_margin: Optional[GroundedMetric] = None
    operating_margin: Optional[GroundedMetric] = None
    free_cash_flow: Optional[GroundedMetric] = None
    fcf_yield: Optional[GroundedMetric] = None
    
    rsi_14: Optional[GroundedMetric] = None
    sma_20: Optional[GroundedMetric] = None
    sma_50: Optional[GroundedMetric] = None
    macd: Optional[GroundedMetric] = None
    macd_signal: Optional[GroundedMetric] = None
    technical_trend: Optional[GroundedMetric] = None
    technical_momentum: Optional[GroundedMetric] = None
    
    enterprise_value: Optional[GroundedMetric] = None
    operating_cash_flow: Optional[GroundedMetric] = None
    annual_revenue: Optional[GroundedMetric] = None
    net_income: Optional[GroundedMetric] = None
    
    peers: List[GroundingPeerItem] = Field(default_factory=list)
    quarterly_reports: List[GroundingHistoricalReport] = Field(default_factory=list)
    annual_reports: List[GroundingHistoricalReport] = Field(default_factory=list)
