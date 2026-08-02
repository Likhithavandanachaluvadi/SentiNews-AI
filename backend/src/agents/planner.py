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
            "ui_blocks": ["EducationalExplainer", "Glossary"]
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

    # Per-intent layouts with correct required_data.
    # Sections and UI blocks inherit from the closest logical archetype;
    # required_data is specialised per intent so the retriever fetches
    # only what each intent actually needs.

    LAYOUTS["FUNDAMENTAL_ANALYSIS"] = {
        "required_agents": ["fundamental", "sentiment"],
        "required_data": {"market": True, "financials": True, "news": True},
        "sections": [
            "Executive Summary", "Fundamental Analysis",
            "Financial Health", "Valuation", "Risk Analysis", "Conclusion",
        ],
        "ui_blocks": ["ExecutiveSummary", "ConfidenceGauge", "FundamentalCard",
                      "SentimentCard", "RiskFactors", "Citations"],
    }

    LAYOUTS["TECHNICAL_ANALYSIS"] = {
        "required_agents": ["technical"],
        "required_data": {"market": True, "financials": False, "news": False},
        "sections": [
            "Executive Summary", "Price Action",
            "Technical Indicators", "Support & Resistance",
            "Momentum", "Conclusion",
        ],
        "ui_blocks": ["ExecutiveSummary", "TechnicalCard", "Citations"],
    }

    LAYOUTS["STOCK_MOVEMENT"] = {
        "required_agents": ["technical", "sentiment"],
        "required_data": {"market": True, "financials": False, "news": True},
        "sections": [
            "Executive Summary", "Movement Drivers",
            "News Catalysts", "Technical Picture", "Conclusion",
        ],
        "ui_blocks": ["ExecutiveSummary", "TechnicalCard", "SentimentCard",
                      "NewsTimeline", "Citations"],
    }

    LAYOUTS["COMPANY_OVERVIEW"] = {
        "required_agents": ["fundamental", "sentiment"],
        "required_data": {"market": True, "financials": True, "news": True},
        "sections": [
            "Executive Summary", "Business Model",
            "Financial Overview", "News Highlights", "Conclusion",
        ],
        "ui_blocks": ["ExecutiveSummary", "FundamentalCard", "SentimentCard",
                      "Citations"],
    }

    LAYOUTS["COMPANY_ANALYSIS"] = {
        "required_agents": ["fundamental", "technical", "sentiment"],
        "required_data": {"market": True, "financials": True, "news": True},
        "sections": [
            "Executive Summary", "Fundamental Analysis",
            "Technical Analysis", "News Summary", "Risk Analysis",
            "Investment Perspective", "Conclusion"
        ],
        "ui_blocks": ["ExecutiveSummary", "ConfidenceGauge", "FundamentalCard",
                      "TechnicalCard", "SentimentCard", "ScenarioCards",
                      "RiskFactors", "Citations"],
    }

    LAYOUTS["COMPANY_COMPARISON"] = {
        "required_agents": ["fundamental", "sentiment"],
        "required_data": {"market": True, "financials": True, "news": True},
        "sections": [
            "Executive Summary", "Company Comparison",
            "Financial Comparison", "Strengths", "Weaknesses",
            "Final Assessment", "Sources"
        ],
        "ui_blocks": ["ExecutiveSummary", "ComparisonTable", "Citations"],
    }

    LAYOUTS["SECTOR_OUTLOOK"] = {
        "required_agents": ["sentiment"],
        "required_data": {"market": False, "financials": False, "news": True},
        "sections": [
            "Executive Summary", "Sector Overview",
            "Industry Trends", "Market Drivers", "Key Risks",
            "Conclusion"
        ],
        "ui_blocks": ["SectorTrends", "MacroDrivers", "IndustryNews", "Citations"],
    }

    LAYOUTS["THEME_ANALYSIS"] = {
        "required_agents": ["sentiment"],
        "required_data": {"market": False, "financials": False, "news": True},
        "sections": [
            "Executive Summary", "Theme Overview",
            "Technology Trends", "Industry Adoption", "Research Context",
            "Market Drivers", "Key Risks"
        ],
        "ui_blocks": ["TechnologyTrends", "Adoption", "Research", "Citations"],
    }

    LAYOUTS["MARKET_OVERVIEW"] = {
        "required_agents": ["sentiment"],
        "required_data": {"market": False, "financials": False, "news": True},
        "sections": [
            "Executive Summary", "Market Overview",
            "Macro Drivers", "Sector Trends", "Conclusion",
        ],
        "ui_blocks": ["MarketTrends", "NewsHighlights", "Citations"],
    }

    LAYOUTS["VALUATION_ANALYSIS"] = {
        "required_agents": ["fundamental"],
        "required_data": {"market": True, "financials": True, "news": True},
        "sections": [
            "Executive Summary", "Valuation Multiples",
            "PE & PEG Analysis", "Relative Valuation", "Conclusion"
        ],
        "ui_blocks": ["ExecutiveSummary", "FundamentalCard", "Citations"],
    }

    LAYOUTS["RISK_ANALYSIS"] = {
        "required_agents": ["fundamental", "sentiment"],
        "required_data": {"market": True, "financials": True, "news": True},
        "sections": [
            "Executive Summary", "Financial Risk",
            "Regulatory Risk", "Market Risk", "Operational Risk", "Conclusion",
        ],
        "ui_blocks": ["ExecutiveSummary", "RiskFactors", "FundamentalCard",
                      "SentimentCard", "Citations"],
    }

    LAYOUTS["PEER_COMPARISON"] = {
        "required_agents": ["fundamental"],
        "required_data": {"market": True, "financials": True, "news": False},
        "sections": [
            "Executive Summary", "Valuation Comparison",
            "Financial Metrics", "Competitive Position", "Conclusion",
        ],
        "ui_blocks": ["ExecutiveSummary", "ComparisonTable", "FundamentalCard",
                      "Citations"],
    }

    LAYOUTS["SENTIMENT_PULSE"] = {
        "required_agents": ["sentiment"],
        "required_data": {"market": False, "financials": False, "news": True},
        "sections": [
            "Executive Summary", "Sentiment Overview",
            "Key Headlines", "Market Mood", "Conclusion",
        ],
        "ui_blocks": ["ExecutiveSummary", "SentimentPulse", "NewsTimeline",
                      "Citations"],
    }

    LAYOUTS["UNKNOWN"] = LAYOUTS["GENERALIZED"]
    LAYOUTS["STOCK_ANALYSIS"] = LAYOUTS["COMPANY_ANALYSIS"]
    LAYOUTS["COMPARISON"] = LAYOUTS["COMPANY_COMPARISON"]

    @classmethod
    def get_layout(cls, primary_intent: str) -> Dict[str, Any]:
        """Get layout configuration for target intent, falling back to GENERALIZED."""
        return cls.LAYOUTS.get(primary_intent, cls.LAYOUTS["GENERALIZED"])
