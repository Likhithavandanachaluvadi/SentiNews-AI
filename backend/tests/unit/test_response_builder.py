from src.services.response_builder import build_response


def _intent(primary_intent: str = "NEWS_ANALYSIS") -> dict:
    return {
        "primary_intent": primary_intent,
        "secondary_intent": "NONE",
        "intent_confidence": 0.9,
        "query_risk_level": "LOW",
        "query_risk_score": 0.0,
        "complexity_level": "LIGHT",
        "classification_reasoning": "test",
    }


def test_build_response_never_returns_blank_summary_without_final_report():
    envelope = build_response(
        intent_data=_intent("NEWS_ANALYSIS"),
        final_report={},
        ticker="HDFCBANK",
        query="What happened with HDFC Bank?",
        context=[],
    )

    assert envelope.summary.strip()
    assert envelope.data["executive_summary"].strip()
    assert "could not complete" in envelope.summary.lower()
    assert envelope.warnings


def test_build_response_empty_final_report_mentions_retrieved_context_when_available():
    envelope = build_response(
        intent_data=_intent("NEWS_ANALYSIS"),
        final_report={},
        ticker="HDFCBANK",
        query="Latest HDFC Bank news",
        context=["[2026-08-01] Google News - HDFC Bank update: Example item"],
    )

    assert envelope.summary.strip()
    assert "source data was retrieved" in envelope.summary
    assert envelope.data["news_summary"] == envelope.summary


def test_build_response_preserves_successful_summary():
    envelope = build_response(
        intent_data=_intent("NEWS_ANALYSIS"),
        final_report={
            "executive_summary": "# Executive Summary\nHDFC Bank was in focus after recent news.",
            "data_freshness": "2026-08-01T00:00:00",
            "overall_confidence_score": 70,
        },
        ticker="HDFCBANK",
        query="Latest HDFC Bank news",
        context=[],
    )

    assert "HDFC Bank was in focus" in envelope.summary
    assert "could not complete" not in envelope.summary.lower()
