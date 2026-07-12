from typing import Dict, Any, List

class ResponsePlanner:
    """
    Intelligent Response Planner for SentiNews AI.
    Maps query intents directly to response layouts, required agents, required data sources, and UI blocks.
    """
    
    LAYOUTS: Dict[str, Dict[str, Any]] = {
        "EARNINGS_REPORT": {
            "required_agents": ["fundamental", "sentiment"],
            "required_data": {"market": True, "financials": True, "news": True},
            "sections": [
                "Executive Summary",
                "Key Takeaways",
                "Financial Highlights",
                "Revenue Performance",
                "Profitability",
                "Business Segment Performance",
                "Management Outlook",
                "Risks",
                "Conclusion"
            ],
            "ui_blocks": ["ExecutiveSummary", "Citations"]
        },
        "STOCK_ANALYSIS": {
            "required_agents": ["fundamental", "technical", "sentiment"],
            "required_data": {"market": True, "financials": True, "news": True},
            "sections": [
                "Executive Summary",
                "Fundamental Analysis",
                "Technical Analysis",
                "News Summary",
                "Risk Analysis",
                "Investment Perspective",
                "Conclusion"
            ],
            "ui_blocks": ["ExecutiveSummary", "ConfidenceGauge", "FundamentalCard", "TechnicalCard", "SentimentCard", "ScenarioCards", "RiskFactors", "Citations"]
        },
        "COMPARISON": {
            "required_agents": ["fundamental", "sentiment"],
            "required_data": {"market": True, "financials": True, "news": True},
            "sections": [
                "Executive Summary",
                "Company Comparison",
                "Financial Comparison",
                "Strengths",
                "Weaknesses",
                "Final Assessment",
                "Sources"
            ],
            "ui_blocks": ["ExecutiveSummary", "ComparisonTable", "Citations"]
        },
        "NEWS_ANALYSIS": {
            "required_agents": ["sentiment"],
            "required_data": {"market": False, "financials": False, "news": True},
            "sections": [
                "Executive Summary",
                "Major News",
                "Market Impact",
                "Sentiment",
                "Risks",
                "Conclusion"
            ],
            "ui_blocks": ["ExecutiveSummary", "NewsTimeline", "SentimentPulse", "Citations"]
        },
        "EDUCATIONAL": {
            "required_agents": [],
            "required_data": {"market": False, "financials": False, "news": False},
            "sections": [
                "Definition",
                "Explanation",
                "Example",
                "Importance",
                "Conclusion"
            ],
            "ui_blocks": ["ExecutiveSummary"]
        },
        "RESTRICTED_ADVISORY": {
            "required_agents": [],
            "required_data": {"market": False, "financials": False, "news": False},
            "sections": [
                "Disclaimer Warning",
                "Refusal of Advisory Services",
                "Educational Alternative Guidance"
            ],
            "ui_blocks": ["ExecutiveSummary"]
        },
        "GENERALIZED": {
            "required_agents": ["fundamental", "technical", "sentiment"],
            "required_data": {"market": True, "financials": True, "news": True},
            "sections": [
                "Executive Summary",
                "Fundamental Overview",
                "Technical Trend",
                "Sentiment Catalyst",
                "Conclusion"
            ],
            "ui_blocks": ["ExecutiveSummary", "ConfidenceGauge", "FundamentalCard", "TechnicalCard", "SentimentCard", "Citations"]
        }
    }

    # Add fallback mappings for standard analyst intent variants
    LAYOUTS["FUNDAMENTAL_ANALYSIS"] = LAYOUTS["STOCK_ANALYSIS"]
    LAYOUTS["TECHNICAL_ANALYSIS"] = LAYOUTS["STOCK_ANALYSIS"]
    LAYOUTS["STOCK_MOVEMENT"] = LAYOUTS["STOCK_ANALYSIS"]
    LAYOUTS["COMPANY_OVERVIEW"] = LAYOUTS["STOCK_ANALYSIS"]
    LAYOUTS["RISK_ANALYSIS"] = LAYOUTS["STOCK_ANALYSIS"]
    LAYOUTS["PEER_COMPARISON"] = LAYOUTS["STOCK_ANALYSIS"]
    LAYOUTS["SENTIMENT_PULSE"] = LAYOUTS["NEWS_ANALYSIS"]

    @classmethod
    def get_layout(cls, primary_intent: str) -> Dict[str, Any]:
        """Get layout configuration for target intent, falling back to GENERALIZED."""
        return cls.LAYOUTS.get(primary_intent, cls.LAYOUTS["GENERALIZED"])
