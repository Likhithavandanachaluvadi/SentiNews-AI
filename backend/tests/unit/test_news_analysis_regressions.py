import asyncio

from src.agents.dynamic_retriever import dynamic_retriever_node
from src.agents.judge import (
    _enforce_news_market_reaction_guard,
    is_report_populated,
)
from src.agents.planner import ResponsePlanner
from src.services.response_builder import build_response, build_sections


def test_news_analysis_skips_market_and_grounding_fetches(monkeypatch):
    async def fail_market_fetch(_ticker):
        raise AssertionError("NEWS_ANALYSIS must not fetch market context")

    async def fail_grounding_fetch(_ticker):
        raise AssertionError("NEWS_ANALYSIS must not fetch Screener/yFinance grounding data")

    async def fake_news_fetch(_search_term, ticker=None):
        assert ticker == "HDFCBANK"
        return [{
            "title": "HDFC Bank update",
            "description": "A verified news development.",
            "source": "Reuters",
            "publishedAt": "2026-08-09T09:30:00Z",
        }]

    monkeypatch.setattr(
        "src.agents.dynamic_retriever.get_enhanced_market_context", fail_market_fetch
    )
    monkeypatch.setattr("src.services.market_data.get_grounding_data", fail_grounding_fetch)
    monkeypatch.setattr(
        "src.agents.dynamic_retriever.NewsAggregator.fetch_all_news", fake_news_fetch
    )
    monkeypatch.setattr(
        "src.agents.dynamic_retriever.filter_news_results",
        lambda articles, _ticker: (articles, []),
    )
    monkeypatch.setattr(
        "src.agents.dynamic_retriever.SourceRanker.rank",
        lambda articles, **_kwargs: articles,
    )
    monkeypatch.setattr(
        "src.agents.dynamic_retriever.SourceRanker.format_ranked_context",
        lambda articles, **_kwargs: [f"[{article['publishedAt']}] Reuters -- {article['title']}" for article in articles],
    )
    monkeypatch.setattr(
        "src.services.entity_resolver.EntityResolver.resolve_sync",
        lambda _query: ("HDFCBANK", "HDFC Bank"),
    )

    result = asyncio.run(dynamic_retriever_node({
        "query": "Why is HDFC Bank in the news?",
        "ticker": "HDFCBANK",
        "intent": {
            "primary_intent": "NEWS_ANALYSIS",
            "extracted_ticker": "HDFCBANK",
            "planner_layout": ResponsePlanner.get_layout("NEWS_ANALYSIS"),
        },
    }))

    assert result["grounding_data"] == {}
    assert result["data_freshness"] == "2026-08-09T09:30:00Z"
    assert len(result["news_articles"]) == 1


def test_news_freshness_is_newest_retrieved_evidence(monkeypatch):
    from src.agents.dynamic_retriever import _freshness_from_evidence

    assert _freshness_from_evidence([
        {"publishedAt": "2026-08-08T22:00:00Z"},
        {"published_at": "2026-08-09T09:30:00Z"},
        {"date": "not-a-date"},
    ]) == "2026-08-09T09:30:00Z"
    assert _freshness_from_evidence([{}]) == "unknown"


def test_news_market_reaction_guard_removes_unsupported_claims():
    summary = (
        "# Executive Summary\nRecent stock price changes and increased trading volume were driven by the news.\n\n"
        "# Market Impact\nThe news caused a share price increase.\n\n"
        "# Overall Sentiment\nNeutral."
    )

    guarded = _enforce_news_market_reaction_guard(summary, verified=False)

    assert "stock price changes" not in guarded.lower()
    assert "trading volume" not in guarded.lower()
    assert "No verified short-term market reaction was identified" in guarded
    assert "business impact is unclear" in guarded


def test_skipped_reports_do_not_count_as_populated_sections():
    skipped_fundamental = {
        "status": "skipped",
        "summary": "Fundamental analysis skipped for this query type.",
        "confidence": {"confidence_score": 0},
    }
    skipped_technical = {
        "status": "skipped",
        "summary": "Technical analysis skipped for this query type.",
        "confidence": {"confidence_score": 0},
    }
    sentiment = {
        "summary": "Recent source evidence is neutral.",
        "confidence": {"confidence_score": 72},
    }

    sections = build_sections(
        intent="NEWS_ANALYSIS",
        final_report={},
        fundamental_report=skipped_fundamental,
        technical_report=skipped_technical,
        sentiment_report=sentiment,
        data_freshness="2026-08-09T09:30:00Z",
        allowed_sections={"sentiment"},
    )

    assert not is_report_populated(skipped_fundamental)
    assert not is_report_populated(skipped_technical)
    assert sections["fundamentals"]["status"] == "skipped"
    assert sections["technicals"]["status"] == "skipped"
    assert sections["sentiment"]["status"] == "available"


def test_news_response_preserves_renderable_structure():
    envelope = build_response(
        intent_data={
            "primary_intent": "NEWS_ANALYSIS",
            "secondary_intent": "NONE",
            "intent_confidence": 0.9,
            "query_risk_level": "LOW",
            "query_risk_score": 0.0,
            "complexity_level": "LIGHT",
            "classification_reasoning": "test",
        },
        final_report={
            "executive_summary": "# Executive Summary\nA verified article reported a board change.",
            "data_freshness": "2026-08-09T09:30:00Z",
            "overall_confidence_score": 72,
        },
        ticker="HDFCBANK",
        query="Why is HDFC Bank in the news?",
        news_articles=[{"title": "HDFC Bank update", "publishedAt": "2026-08-09T09:30:00Z"}],
        data_freshness="2026-08-09T09:30:00Z",
        fundamental_report={"status": "skipped"},
        technical_report={"status": "skipped"},
        sentiment_report={"summary": "Neutral", "confidence": {"confidence_score": 72}},
    )

    assert envelope.summary
    assert envelope.meta.data_freshness == "2026-08-09T09:30:00Z"
    assert envelope.sections["fundamentals"]["status"] == "skipped"
    assert envelope.sections["technicals"]["status"] == "skipped"
    assert envelope.sections["sentiment"]["status"] == "available"
