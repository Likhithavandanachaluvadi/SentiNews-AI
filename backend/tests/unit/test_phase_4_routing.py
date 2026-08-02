import pytest
import asyncio

from src.agents.dynamic_retriever import dynamic_retriever_node
from src.agents.planner import ResponsePlanner
from src.agents.retrieval_policy import get_policy
from src.core.middleware import validate_query_multiple_companies


def test_educational_pipeline_keeps_ticker_none():
    result = asyncio.run(dynamic_retriever_node({
        "query": "Explain ROE",
        "ticker": None,
        "intent": {
            "primary_intent": "EDUCATIONAL",
            "extracted_ticker": None,
            "planner_layout": ResponsePlanner.get_layout("EDUCATIONAL"),
        },
    }))

    assert result["ticker"] is None
    assert result["context"] == []
    assert result["ui_blocks"] == ["EducationalExplainer", "Glossary"]


def test_sector_pipeline_does_not_fetch_company_market_data(monkeypatch):
    async def fail_market_fetch(_ticker):
        raise AssertionError("sector outlook must not fetch company market data")

    async def fake_news_fetch(search_term, ticker=None):
        assert ticker is None
        assert search_term == "Indian IT sector outlook"
        return []

    monkeypatch.setattr("src.agents.dynamic_retriever.get_enhanced_market_context", fail_market_fetch)
    monkeypatch.setattr("src.agents.dynamic_retriever.NewsAggregator.fetch_all_news", fake_news_fetch)

    result = asyncio.run(dynamic_retriever_node({
        "query": "Indian IT sector outlook",
        "ticker": None,
        "intent": {
            "primary_intent": "SECTOR_OUTLOOK",
            "extracted_ticker": None,
            "planner_layout": ResponsePlanner.get_layout("SECTOR_OUTLOOK"),
        },
    }))

    assert result["ticker"] is None
    assert "SectorTrends" in result["ui_blocks"]
    assert "FundamentalCard" not in result["ui_blocks"]


def test_theme_pipeline_keeps_ai_as_theme_not_c3ai(monkeypatch):
    async def fake_news_fetch(search_term, ticker=None):
        assert ticker is None
        assert search_term == "AI is changing the software industry"
        return []

    monkeypatch.setattr("src.agents.dynamic_retriever.NewsAggregator.fetch_all_news", fake_news_fetch)

    result = asyncio.run(dynamic_retriever_node({
        "query": "AI is changing the software industry",
        "ticker": "AI",
        "intent": {
            "primary_intent": "THEME_ANALYSIS",
            "extracted_ticker": "AI",
            "planner_layout": ResponsePlanner.get_layout("THEME_ANALYSIS"),
        },
    }))

    assert result["ticker"] is None
    assert "TechnologyTrends" in result["ui_blocks"]
    assert "FundamentalCard" not in result["ui_blocks"]


def test_company_comparison_validator_allows_two_companies():
    entity_collection = {
        "entities": [
            {"ticker": "INFY", "company_name": "Infosys Limited", "confidence": 1.0, "resolution_source": "TEST"},
            {"ticker": "TCS", "company_name": "Tata Consultancy Services", "confidence": 1.0, "resolution_source": "TEST"},
        ],
        "query": "Compare Infosys and TCS",
        "resolution_mode": "MULTI",
        "total_found": 2,
    }

    validate_query_multiple_companies(
        "Compare Infosys and TCS",
        "COMPANY_COMPARISON",
        entity_collection=entity_collection,
    )


def test_validator_ignores_common_word_ticker_false_positive():
    entity_collection = {
        "entities": [
            {
                "ticker": "HDFCBANK",
                "company_name": "HDFC Bank",
                "confidence": 0.97,
                "resolution_source": "EXACT_NAME",
                "query_span": "HDFC Bank",
            },
            {
                "ticker": "CAN",
                "company_name": "Canaan Inc.",
                "confidence": 1.0,
                "resolution_source": "EXACT_TICKER",
                "query_span": "Can",
            },
        ],
        "query": "Can you explain HDFC Bank news?",
        "resolution_mode": "MULTI",
        "total_found": 2,
    }

    validate_query_multiple_companies(
        "Can you explain HDFC Bank news?",
        "NEWS_ANALYSIS",
        entity_collection=entity_collection,
    )


@pytest.mark.parametrize("intent", ["EDUCATIONAL", "SECTOR_OUTLOOK", "THEME_ANALYSIS", "MARKET_OVERVIEW"])
def test_tickerless_intents_do_not_require_ticker(intent):
    assert get_policy(intent).requires_ticker is False
    layout = ResponsePlanner.get_layout(intent)
    assert layout["required_data"]["financials"] is False
