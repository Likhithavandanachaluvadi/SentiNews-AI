"""
Unit tests for FinancialNewsFilter — Sprint 1

Covers all four scoring pillars individually, composite scoring,
noise penalty, category classification, and filter_and_rank behaviour.
"""

import pytest
from datetime import datetime, timezone, timedelta

from src.services.financial_news_filter import (
    FinancialNewsFilter,
    _score_p1_keywords,
    _score_p2_publisher,
    _score_p3_freshness,
    _score_p4_company_relevance,
    _detect_noise,
    _classify_category,
    _normalize,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso(delta: timedelta = timedelta(0)) -> str:
    return (datetime.now(tz=timezone.utc) - delta).isoformat()


def _make_article(
    title: str = "",
    description: str = "",
    source: str = "Unknown",
    published_at: str = "",
) -> dict:
    return {
        "title": title,
        "description": description,
        "source": source,
        "publishedAt": published_at,
        "url": "https://example.com",
        "provider": "test",
        "relevance_score": 0,  # original key — must survive unchanged
    }


# ---------------------------------------------------------------------------
# P1 — Financial Keyword Quality
# ---------------------------------------------------------------------------

class TestP1Keywords:

    def test_tier1_keyword_scores_high(self):
        score, has_fin = _score_p1_keywords("quarterly results beat expectations significantly")
        assert score >= 15
        assert has_fin is True

    def test_multiple_tier1_capped_at_40(self):
        # 3 distinct tier-1 hits × 15 pts = 45 → capped to 30 for T1.
        # No tier-2 or tier-3 hits → total = 30, still ≤ 40 cap.
        # Use a text with exactly 3 tier-1 keywords to verify raw > cap is trimmed.
        text = "quarterly earnings results showed strong ebitda and net income growth"
        score, _ = _score_p1_keywords(text)
        # T1 matches: earnings, quarterly results, ebitda, net income → 4 × 15 = 60 → T1 capped at 30
        # Final = min(30, 40) = 30
        assert score == 30

    def test_tier2_keyword_scores_correctly(self):
        text = "company announces dividend payout to shareholders"
        score, has_fin = _score_p1_keywords(text)
        assert score >= 8
        assert has_fin is True

    def test_tier3_keyword_scores_correctly(self):
        text = "sebi issues compliance notice to the board of directors"
        score, has_fin = _score_p1_keywords(text)
        assert score >= 5
        assert has_fin is True

    def test_zero_for_unrelated_text(self):
        score, has_fin = _score_p1_keywords("company wins best employer award")
        assert score == 0
        assert has_fin is False

    def test_mixed_tiers_combined(self):
        # T1 + T2 + T3 should accumulate, capped at 40
        text = "earnings guidance analyst upgrade dividend sebi board"
        score, has_fin = _score_p1_keywords(text)
        assert 0 < score <= 40
        assert has_fin is True


# ---------------------------------------------------------------------------
# P2 — Publisher Quality
# ---------------------------------------------------------------------------

class TestP2Publisher:

    def test_tier_a_bloomberg(self):
        assert _score_p2_publisher("Bloomberg") == 20

    def test_tier_a_economic_times(self):
        assert _score_p2_publisher("The Economic Times") == 20

    def test_tier_a_moneycontrol(self):
        assert _score_p2_publisher("Moneycontrol") == 20

    def test_tier_b_times_of_india(self):
        assert _score_p2_publisher("Times of India") == 12

    def test_tier_b_ndtv(self):
        assert _score_p2_publisher("NDTV") == 12

    def test_tier_c_unknown(self):
        assert _score_p2_publisher("Some Random Blog") == 6

    def test_tier_c_none(self):
        assert _score_p2_publisher(None) == 6

    def test_case_insensitive(self):
        assert _score_p2_publisher("BLOOMBERG") == 20
        assert _score_p2_publisher("economic times") == 20


# ---------------------------------------------------------------------------
# P3 — Freshness
# ---------------------------------------------------------------------------

class TestP3Freshness:

    def test_within_24h_scores_20(self):
        ts = _now_iso(timedelta(hours=6))
        assert _score_p3_freshness(ts) == 20

    def test_within_3_days_scores_16(self):
        ts = _now_iso(timedelta(days=2))
        assert _score_p3_freshness(ts) == 16

    def test_within_7_days_scores_12(self):
        ts = _now_iso(timedelta(days=5))
        assert _score_p3_freshness(ts) == 12

    def test_within_14_days_scores_8(self):
        ts = _now_iso(timedelta(days=10))
        assert _score_p3_freshness(ts) == 8

    def test_within_30_days_scores_4(self):
        ts = _now_iso(timedelta(days=25))
        assert _score_p3_freshness(ts) == 4

    def test_older_than_30_days_scores_0(self):
        ts = _now_iso(timedelta(days=45))
        assert _score_p3_freshness(ts) == 0

    def test_empty_string_scores_0(self):
        assert _score_p3_freshness("") == 0

    def test_none_scores_0(self):
        assert _score_p3_freshness(None) == 0

    def test_malformed_date_scores_0(self):
        assert _score_p3_freshness("not-a-date") == 0


# ---------------------------------------------------------------------------
# P4 — Company Name Relevance
# ---------------------------------------------------------------------------

class TestP4CompanyRelevance:

    def test_company_name_in_title_scores_20(self):
        score = _score_p4_company_relevance(
            "Infosys reports strong quarterly results",
            "The company beat estimates",
            "Infosys",
            None,
        )
        assert score == 20

    def test_company_name_in_description_scores_10(self):
        score = _score_p4_company_relevance(
            "IT sector continues strong growth",
            "Infosys announced its results today",
            "Infosys",
            None,
        )
        assert score == 10

    def test_ticker_in_title_scores_15(self):
        score = _score_p4_company_relevance(
            "INFY stock rallies on strong earnings",
            "Details below",
            None,
            "INFY",
        )
        assert score == 15

    def test_ticker_in_description_scores_8(self):
        score = _score_p4_company_relevance(
            "Indian IT sector gains",
            "INFY shares rose sharply today",
            None,
            "INFY",
        )
        assert score == 8

    def test_no_match_scores_0(self):
        score = _score_p4_company_relevance(
            "Markets fall on global cues",
            "Investors remain cautious",
            "Infosys",
            "INFY",
        )
        assert score == 0

    def test_company_name_and_ticker_takes_max(self):
        # Company name in title (20) > ticker in description (8) → should be 20
        score = _score_p4_company_relevance(
            "Tata Consultancy Services beats estimates",
            "TCS reported strong INFY-like results",
            "Tata Consultancy Services",
            "TCS",
        )
        assert score == 20


# ---------------------------------------------------------------------------
# Noise Detection
# ---------------------------------------------------------------------------

class TestNoiseDetection:

    def test_hiring_is_noise(self):
        assert _detect_noise("company opens new hiring drive for engineers") is True

    def test_csr_is_noise(self):
        assert _detect_noise("annual csr initiative launches in rural areas") is True

    def test_award_is_noise(self):
        assert _detect_noise("company wins best employer award at ceremony") is True

    def test_sponsorship_is_noise(self):
        assert _detect_noise("company sponsors ipl team for new season") is True

    def test_inauguration_is_noise(self):
        assert _detect_noise("ceo inaugurates new office in hyderabad") is True

    def test_financial_article_not_noise(self):
        assert _detect_noise("quarterly earnings beat analyst estimates") is False

    def test_empty_not_noise(self):
        assert _detect_noise("") is False


# ---------------------------------------------------------------------------
# Category Classification
# ---------------------------------------------------------------------------

class TestCategoryClassification:

    @pytest.mark.parametrize("text,expected_category", [
        ("earnings beat analyst expectations on quarterly basis", "Earnings"),
        ("company reports record financial results in q3", "Financial Results"),
        ("net sales accelerate in second quarter period", "Revenue"),
        ("net profit surges despite market headwinds", "Profit"),
        ("board declares final dividend for fy2026", "Dividend"),
        ("management issues revised capex guidance for year", "Guidance"),
        ("company acquires rival firm in all-cash deal", "Acquisition"),
        ("two firms agree on merger terms after months", "Merger"),
        ("stock price hits 52-week high amid rally", "Market Movement"),
        ("sebi issues notice over regulatory compliance", "Regulation"),
        ("ceo resigns from board after agm controversy", "Governance"),
        ("analyst upgrades stock with new target price", "Analyst Rating"),
        ("company launches new product line this quarter", "Product Launch"),
        ("company wins award for best workplace culture", "Other"),
    ])
    def test_category(self, text, expected_category):
        assert _classify_category(text) == expected_category


# ---------------------------------------------------------------------------
# score_and_classify (end-to-end enrichment)
# ---------------------------------------------------------------------------

class TestScoreAndClassify:

    def test_enriches_article_with_score_and_category(self):
        article = _make_article(
            title="Infosys quarterly results beat estimates",
            description="Net profit rose significantly above expectations",
            source="Economic Times",
            published_at=_now_iso(timedelta(hours=2)),
        )
        result = FinancialNewsFilter.score_and_classify(
            [article], company_name="Infosys", ticker="INFY"
        )
        a = result[0]
        assert "financial_relevance_score" in a
        assert "financial_category" in a
        assert a["relevance_score"] == 0  # original key preserved
        assert a["financial_relevance_score"] >= 60  # should score high
        assert a["financial_category"] in (
            "Earnings", "Financial Results", "Profit", "Revenue"
        )

    def test_high_signal_article_scores_above_60(self):
        article = _make_article(
            title="TCS Q3 earnings beat: PAT up, revenue grows, dividend declared",
            description="Tata Consultancy Services reports strong quarterly results with EBITDA expansion",
            source="Bloomberg",
            published_at=_now_iso(timedelta(hours=1)),
        )
        FinancialNewsFilter.score_and_classify(
            [article], company_name="Tata Consultancy Services", ticker="TCS"
        )
        assert article["financial_relevance_score"] >= 60

    def test_noise_only_article_scores_low(self):
        article = _make_article(
            title="Company wins best CSR award at national ceremony",
            description="Employees celebrate at annual town hall event",
            source="Some Blog",
            published_at=_now_iso(timedelta(days=20)),
        )
        FinancialNewsFilter.score_and_classify([article])
        assert article["financial_relevance_score"] < 20

    def test_noise_plus_financial_keyword_survives(self):
        article = _make_article(
            title="Infosys hiring drive announces record EPS growth",
            description="Company expands workforce following earnings beat",
            source="Economic Times",
            published_at=_now_iso(timedelta(days=1)),
        )
        FinancialNewsFilter.score_and_classify(
            [article], company_name="Infosys", ticker="INFY"
        )
        # Financial keyword present → no noise penalty
        assert article["financial_relevance_score"] >= 20

    def test_empty_list_returns_empty(self):
        assert FinancialNewsFilter.score_and_classify([]) == []


# ---------------------------------------------------------------------------
# filter_and_rank
# ---------------------------------------------------------------------------

class TestFilterAndRank:

    def _sample_articles(self):
        return [
            _make_article(
                title="TCS Q3 earnings beat consensus estimates",
                description="PAT and revenue both grew strongly",
                source="Bloomberg",
                published_at=_now_iso(timedelta(hours=3)),
            ),
            _make_article(
                title="Company wins CSR award for community work",
                description="Annual employee volunteering event celebrated",
                source="Local Blog",
                published_at=_now_iso(timedelta(days=22)),
            ),
            _make_article(
                title="Infosys dividend declared ahead of AGM",
                description="Board approves record interim dividend for shareholders",
                source="Moneycontrol",
                published_at=_now_iso(timedelta(days=2)),
            ),
            _make_article(
                title="IT sector hiring surge continues",
                description="Recruitment drive targets 10000 fresh graduates",
                source="Times of India",
                published_at=_now_iso(timedelta(days=5)),
            ),
        ]

    def test_filters_below_min_score(self):
        articles = self._sample_articles()
        result = FinancialNewsFilter.filter_and_rank(
            articles, company_name="TCS", ticker="TCS", min_score=20
        )
        scores = [a["financial_relevance_score"] for a in result]
        assert all(s >= 20 for s in scores)

    def test_sorted_descending_by_score(self):
        articles = self._sample_articles()
        result = FinancialNewsFilter.filter_and_rank(
            articles, company_name="TCS", ticker="TCS", min_score=0
        )
        scores = [a["financial_relevance_score"] for a in result]
        assert scores == sorted(scores, reverse=True)

    def test_top_n_respected(self):
        articles = self._sample_articles() * 5  # 20 articles
        result = FinancialNewsFilter.filter_and_rank(
            articles, company_name="TCS", ticker="TCS",
            top_n=3, min_score=0
        )
        assert len(result) <= 3

    def test_empty_input_returns_empty(self):
        assert FinancialNewsFilter.filter_and_rank([]) == []

    def test_original_keys_preserved(self):
        articles = self._sample_articles()
        result = FinancialNewsFilter.filter_and_rank(
            articles, company_name="TCS", ticker="TCS", min_score=0
        )
        for a in result:
            assert "relevance_score" in a   # original field
            assert "url" in a
            assert "provider" in a
            assert "financial_relevance_score" in a  # new field
            assert "financial_category" in a          # new field

    def test_financial_articles_rank_above_noise(self):
        articles = self._sample_articles()
        result = FinancialNewsFilter.filter_and_rank(
            articles, company_name="TCS", ticker="TCS", min_score=0
        )
        top_title = result[0]["title"]
        # The earnings article should rank first
        assert "earnings" in top_title.lower() or "dividend" in top_title.lower()
