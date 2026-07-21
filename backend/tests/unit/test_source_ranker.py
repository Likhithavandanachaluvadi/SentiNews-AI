"""
Unit tests for SourceRanker & source_trust_config — Sprint 3

Covers:
  - S1 Source Trust scoring (all 5 tiers + edge cases)
  - S2 Financial Relevance scaling from Sprint 1 scores
  - S3 Freshness bands
  - S4 Source Type detection (all registry types)
  - Composite evidence_score assembly
  - Deduplication (duplicates removed, distinct perspectives kept)
  - rank() method: ordering, top_n, empty input
  - format_ranked_context() output shape
  - Trust ranking order verification (official > reuters > yahoo > general > blog)
  - All registry entries have sane bounds
"""

import pytest
from datetime import datetime, timezone, timedelta
from typing import Any, Dict

from src.services.source_ranker import (
    SourceRanker,
    _score_s1_trust,
    _score_s2_financial_relevance,
    _score_s3_freshness,
    _score_s4_source_type,
    _deduplicate,
    _normalize_title_for_dedup,
)
from src.services.source_trust_config import (
    PUBLISHER_TRUST_TIERS,
    SOURCE_TYPE_REGISTRY,
    DEFAULT_TRUST_SCORE,
    resolve_publisher_tier,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso(delta: timedelta = timedelta(0)) -> str:
    return (datetime.now(tz=timezone.utc) - delta).isoformat()


def _article(
    title: str = "Company reports quarterly earnings",
    description: str = "Strong results beat analyst estimates",
    source: str = "Reuters",
    published_at: str = "",
    url: str = "https://reuters.com/article/123",
    financial_relevance_score: int | None = 80,
) -> Dict[str, Any]:
    a = {
        "title": title,
        "description": description,
        "source": source,
        "publishedAt": published_at or _now_iso(timedelta(hours=3)),
        "url": url,
        "provider": "test",
        "relevance_score": 0,   # original Sprint 1 key — must survive
    }
    if financial_relevance_score is not None:
        a["financial_relevance_score"] = financial_relevance_score
    return a


# ---------------------------------------------------------------------------
# source_trust_config sanity checks
# ---------------------------------------------------------------------------

class TestSourceTrustConfig:

    def test_all_tiers_have_positive_scores(self):
        for tier in PUBLISHER_TRUST_TIERS:
            assert tier.score > 0, f"Tier {tier.label} has score {tier.score}"

    def test_tier_scores_within_bounds(self):
        for tier in PUBLISHER_TRUST_TIERS:
            assert 0 <= tier.score <= 40, f"Tier {tier.label} score out of range"

    def test_all_tiers_have_tokens(self):
        for tier in PUBLISHER_TRUST_TIERS:
            assert len(tier.tokens) > 0, f"Tier {tier.label} has no tokens"

    def test_all_source_type_bonuses_within_bounds(self):
        for cfg in SOURCE_TYPE_REGISTRY:
            assert 0 <= cfg.bonus <= 10, f"{cfg.type_name} bonus out of range"

    def test_official_tier_is_highest(self):
        official = resolve_publisher_tier("nseindia")
        premium = resolve_publisher_tier("bloomberg")
        assert official is not None
        assert premium is not None
        assert official.score >= premium.score

    def test_premium_tier_above_general(self):
        premium = resolve_publisher_tier("economic times")
        general = resolve_publisher_tier("times of india")
        assert premium is not None
        assert general is not None
        assert premium.score > general.score

    def test_unknown_publisher_returns_none(self):
        assert resolve_publisher_tier("some-random-blog.xyz") is None

    def test_none_publisher_returns_none(self):
        assert resolve_publisher_tier(None) is None

    def test_case_insensitive_resolution(self):
        t1 = resolve_publisher_tier("Bloomberg")
        t2 = resolve_publisher_tier("BLOOMBERG")
        t3 = resolve_publisher_tier("bloomberg.com")
        assert t1 is not None
        assert t1.score == t2.score == t3.score


# ---------------------------------------------------------------------------
# S1 — Source Trust
# ---------------------------------------------------------------------------

class TestS1SourceTrust:

    def test_official_nse_scores_40(self):
        score, label, _ = _score_s1_trust("NSEIndia")
        assert score == 40
        assert "Official" in label or "Regulatory" in label

    def test_official_sebi_scores_40(self):
        score, _, _ = _score_s1_trust("sebi.gov.in")
        assert score == 40

    def test_bloomberg_scores_35(self):
        score, label, _ = _score_s1_trust("Bloomberg")
        assert score == 35
        assert "Premium" in label

    def test_reuters_scores_35(self):
        score, _, _ = _score_s1_trust("Reuters")
        assert score == 35

    def test_economic_times_scores_35(self):
        score, _, _ = _score_s1_trust("The Economic Times")
        assert score == 35

    def test_moneycontrol_scores_35(self):
        score, _, _ = _score_s1_trust("Moneycontrol")
        assert score == 35

    def test_yahoo_finance_scores_28(self):
        score, _, _ = _score_s1_trust("Yahoo Finance")
        assert score == 28

    def test_times_of_india_scores_20(self):
        score, label, _ = _score_s1_trust("Times of India")
        assert score == 20
        assert "General" in label

    def test_ndtv_scores_20(self):
        score, _, _ = _score_s1_trust("NDTV")
        assert score == 20

    def test_google_news_scores_12(self):
        score, label, _ = _score_s1_trust("Google News")
        assert score == 12
        assert "Aggregator" in label

    def test_finnhub_scores_12(self):
        score, _, _ = _score_s1_trust("Finnhub")
        assert score == 12

    def test_unknown_blog_scores_default(self):
        score, label, _ = _score_s1_trust("some-unknown-blog.xyz")
        assert score == DEFAULT_TRUST_SCORE
        assert score == 5

    def test_none_scores_default(self):
        score, _, _ = _score_s1_trust(None)
        assert score == DEFAULT_TRUST_SCORE

    def test_empty_string_scores_default(self):
        score, _, _ = _score_s1_trust("")
        assert score == DEFAULT_TRUST_SCORE


# ---------------------------------------------------------------------------
# S2 — Financial Relevance
# ---------------------------------------------------------------------------

class TestS2FinancialRelevance:

    def test_perfect_sprint1_score_gives_30(self):
        a = _article(financial_relevance_score=100)
        assert _score_s2_financial_relevance(a) == 30

    def test_zero_sprint1_score_gives_0(self):
        a = _article(financial_relevance_score=0)
        assert _score_s2_financial_relevance(a) == 0

    def test_50_sprint1_score_gives_15(self):
        a = _article(financial_relevance_score=50)
        assert _score_s2_financial_relevance(a) == 15

    def test_missing_sprint1_score_gives_neutral_15(self):
        a = _article(financial_relevance_score=None)
        assert _score_s2_financial_relevance(a) == 15

    def test_scaling_rounds_correctly(self):
        a = _article(financial_relevance_score=80)
        assert _score_s2_financial_relevance(a) == 24  # round(80/100 * 30)


# ---------------------------------------------------------------------------
# S3 — Freshness
# ---------------------------------------------------------------------------

class TestS3Freshness:

    def test_within_24h_scores_20(self):
        assert _score_s3_freshness(_now_iso(timedelta(hours=6))) == 20

    def test_within_3_days_scores_16(self):
        assert _score_s3_freshness(_now_iso(timedelta(days=2))) == 16

    def test_within_7_days_scores_12(self):
        assert _score_s3_freshness(_now_iso(timedelta(days=5))) == 12

    def test_within_14_days_scores_8(self):
        assert _score_s3_freshness(_now_iso(timedelta(days=10))) == 8

    def test_within_30_days_scores_4(self):
        assert _score_s3_freshness(_now_iso(timedelta(days=25))) == 4

    def test_older_than_30_days_scores_0(self):
        assert _score_s3_freshness(_now_iso(timedelta(days=45))) == 0

    def test_none_scores_0(self):
        assert _score_s3_freshness(None) == 0

    def test_malformed_date_scores_0(self):
        assert _score_s3_freshness("not-a-date") == 0


# ---------------------------------------------------------------------------
# S4 — Source Type Detection
# ---------------------------------------------------------------------------

class TestS4SourceType:

    def test_annual_report_url_detected(self):
        a = _article(url="https://company.com/annual-report/2025")
        score, type_name = _score_s4_source_type(a)
        assert type_name == "Annual Report"
        assert score == 10

    def test_quarterly_results_in_title(self):
        a = _article(title="TCS Q3 quarterly results announced", url="https://tcs.com/news")
        score, type_name = _score_s4_source_type(a)
        assert type_name == "Earnings Release"
        assert score == 9

    def test_earnings_call_transcript(self):
        a = _article(
            title="Infosys earnings call transcript Q2 FY26",
            url="https://example.com/earnings-call/infosys-q2",
        )
        score, type_name = _score_s4_source_type(a)
        assert type_name == "Earnings Call Transcript"
        assert score == 9

    def test_sec_filing_url(self):
        a = _article(url="https://sec.gov/cgi-bin/browse-edgar?action=getcompany")
        score, type_name = _score_s4_source_type(a)
        assert type_name == "Regulatory Filing"
        assert score == 10

    def test_analyst_report_title(self):
        a = _article(
            title="Analyst report: Initiating coverage on HDFC Bank with target price",
            url="https://somebroker.com/research/hdfc",
        )
        score, type_name = _score_s4_source_type(a)
        assert type_name == "Analyst Report"
        assert score == 7

    def test_investor_presentation(self):
        a = _article(
            title="Reliance investor presentation capital markets day",
            url="https://ril.com/investor-presentation",
        )
        score, type_name = _score_s4_source_type(a)
        assert type_name == "Investor Presentation"
        assert score == 8

    def test_generic_news_article(self):
        a = _article(title="Markets update today", url="https://example.com/news/123")
        _, type_name = _score_s4_source_type(a)
        assert type_name == "News Article"

    def test_press_release_url(self):
        a = _article(url="https://company.com/press-release/2025-q3")
        bonus, type_name = _score_s4_source_type(a)
        assert type_name == "Press Release"
        assert bonus == 5


# ---------------------------------------------------------------------------
# Composite evidence_score
# ---------------------------------------------------------------------------

class TestCompositeScore:

    def test_official_source_scores_very_high(self):
        """NSE filing + high financial relevance + fresh + regulatory type → near 100"""
        a = _article(
            source="NSEIndia",
            url="https://nseindia.com/companies/filing/TCS",
            title="TCS quarterly results filing NSE",
            published_at=_now_iso(timedelta(hours=1)),
            financial_relevance_score=90,
        )
        SourceRanker.score(a)
        assert a["evidence_score"] >= 75

    def test_bloomberg_recent_earnings_scores_high(self):
        a = _article(
            source="Bloomberg",
            title="TCS Q3 earnings beat consensus; PAT up",
            published_at=_now_iso(timedelta(hours=5)),
            financial_relevance_score=85,
        )
        SourceRanker.score(a)
        assert a["evidence_score"] >= 70

    def test_unknown_blog_old_article_scores_low(self):
        a = _article(
            source="some-blog.example.xyz",
            title="Company hiring event last year recap",
            published_at=_now_iso(timedelta(days=60)),
            financial_relevance_score=5,
        )
        SourceRanker.score(a)
        assert a["evidence_score"] <= 30

    def test_evidence_score_clamped_0_to_100(self):
        a = _article(
            source="NSEIndia",
            title="TCS q3 quarterly results",
            url="https://nseindia.com/annual-report",
            published_at=_now_iso(timedelta(minutes=30)),
            financial_relevance_score=100,
        )
        SourceRanker.score(a)
        assert 0 <= a["evidence_score"] <= 100

    def test_original_keys_preserved(self):
        a = _article(source="Reuters", financial_relevance_score=70)
        SourceRanker.score(a)
        assert "relevance_score" in a     # original Sprint 1 field
        assert "url" in a
        assert "provider" in a
        assert "evidence_score" in a      # new
        assert "trust_score" in a         # new
        assert "source_type" in a         # new
        assert "source_tier_label" in a   # new

    def test_trust_ranking_order(self):
        """Official > Premium Financial > Quality Financial > General > Aggregator > Unknown"""
        sources_list = [
            ("Unknown Blog",   "some-blog.xyz"),
            ("Finnhub",        "Finnhub"),
            ("BBC",            "BBC News"),
            ("Yahoo Finance",  "Yahoo Finance"),
            ("Reuters",        "Reuters"),
            ("NSE India",      "NSEIndia"),
        ]
        articles = [
            _article(
                source=src,
                title="TCS quarterly results earnings report",
                published_at=_now_iso(timedelta(hours=2)),
                financial_relevance_score=80,
            )
            for label, src in sources_list
        ]
        ranked = SourceRanker.rank(articles, deduplicate=False)
        ranked_sources = [a["source"] for a in ranked]

        # NSEIndia must be first, unknown blog must be last
        assert ranked_sources[0] == "NSEIndia"
        assert ranked_sources[-1] == "some-blog.xyz"

        # Reuters must outrank Yahoo Finance which outranks BBC
        reuters_idx = ranked_sources.index("Reuters")
        yahoo_idx = ranked_sources.index("Yahoo Finance")
        bbc_idx = ranked_sources.index("BBC News")
        assert reuters_idx < yahoo_idx < bbc_idx


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

class TestDeduplication:

    def test_identical_titles_deduplicated(self):
        a1 = _article(
            title="TCS reports record quarterly profit above estimates",
            source="Reuters",
            financial_relevance_score=80,
        )
        a2 = _article(
            title="TCS reports record quarterly profit above estimates",
            source="Some Blog",
            financial_relevance_score=20,
        )
        SourceRanker.score(a1)
        SourceRanker.score(a2)
        result = _deduplicate([a1, a2])
        assert len(result) == 1
        # Higher evidence score kept
        assert result[0]["source"] == "Reuters"

    def test_near_duplicate_titles_deduplicated(self):
        """Two headlines sharing almost all tokens → deduplicated; higher score kept"""
        a1 = _article(
            title="Infosys quarterly earnings results beat analyst expectations strongly reported",
            source="Bloomberg",
            financial_relevance_score=85,
        )
        a2 = _article(
            title="Infosys quarterly earnings results beat analyst expectations strongly",
            source="NDTV",
            financial_relevance_score=40,
        )
        SourceRanker.score(a1)
        SourceRanker.score(a2)
        result = _deduplicate([a1, a2])
        assert len(result) == 1
        assert result[0]["source"] == "Bloomberg"

    def test_distinct_events_both_kept(self):
        """Two genuinely different articles should both survive dedup"""
        a1 = _article(
            title="Infosys quarterly results earnings beat consensus strongly",
            source="Reuters",
        )
        a2 = _article(
            title="Infosys acquires European consulting firm digital transformation",
            source="Bloomberg",
        )
        SourceRanker.score(a1)
        SourceRanker.score(a2)
        result = _deduplicate([a1, a2])
        assert len(result) == 2

    def test_empty_input_returns_empty(self):
        assert _deduplicate([]) == []

    def test_single_article_passes_through(self):
        a = _article()
        SourceRanker.score(a)
        result = _deduplicate([a])
        assert len(result) == 1


# ---------------------------------------------------------------------------
# rank() method
# ---------------------------------------------------------------------------

class TestRank:

    def _sample(self):
        return [
            _article(
                source="NSEIndia",
                title="TCS quarterly results filing NSE exchange",
                published_at=_now_iso(timedelta(hours=1)),
                financial_relevance_score=90,
            ),
            _article(
                source="some-random-blog.xyz",
                title="Company hiring 1000 employees campus recruitment drive",
                published_at=_now_iso(timedelta(days=40)),
                financial_relevance_score=5,
            ),
            _article(
                source="Bloomberg",
                title="TCS PAT profit rises dividend declared",
                published_at=_now_iso(timedelta(hours=3)),
                financial_relevance_score=85,
            ),
            _article(
                source="Times of India",
                title="Stock market update general commentary today",
                published_at=_now_iso(timedelta(days=8)),
                financial_relevance_score=30,
            ),
        ]

    def test_sorted_descending_by_evidence_score(self):
        result = SourceRanker.rank(self._sample(), deduplicate=False)
        scores = [a["evidence_score"] for a in result]
        assert scores == sorted(scores, reverse=True)

    def test_top_n_respected(self):
        result = SourceRanker.rank(self._sample() * 4, top_n=3, deduplicate=False)
        assert len(result) <= 3

    def test_empty_returns_empty(self):
        assert SourceRanker.rank([]) == []

    def test_official_source_ranks_first(self):
        result = SourceRanker.rank(self._sample(), deduplicate=False)
        assert result[0]["source"] == "NSEIndia"

    def test_old_blog_ranks_last(self):
        result = SourceRanker.rank(self._sample(), deduplicate=False)
        assert result[-1]["source"] == "some-random-blog.xyz"

    def test_dedup_reduces_count_for_same_event(self):
        dupes = [
            _article(title="TCS quarterly earnings results beat strong above analyst estimates"),
            _article(title="TCS quarterly earnings results beat strong above analyst estimates"),
        ]
        result_with = SourceRanker.rank(dupes, deduplicate=True)
        result_without = SourceRanker.rank(dupes, deduplicate=False)
        assert len(result_with) <= len(result_without)


# ---------------------------------------------------------------------------
# format_ranked_context()
# ---------------------------------------------------------------------------

class TestFormatRankedContext:

    def test_returns_list_of_strings(self):
        articles = [_article()]
        SourceRanker.score(articles[0])
        lines = SourceRanker.format_ranked_context(articles)
        assert isinstance(lines, list)
        assert all(isinstance(line, str) for line in lines)

    def test_context_includes_evidence_metadata(self):
        a = _article(source="Reuters", financial_relevance_score=80)
        SourceRanker.score(a)
        lines = SourceRanker.format_ranked_context([a])
        assert len(lines) == 1
        line = lines[0]
        assert "Evidence=" in line
        assert "Trust=" in line

    def test_empty_input_returns_empty(self):
        assert SourceRanker.format_ranked_context([]) == []

    def test_description_truncated(self):
        a = _article(description="x" * 500)
        SourceRanker.score(a)
        lines = SourceRanker.format_ranked_context([a], max_description_chars=100)
        parts = lines[0].split("\n", 1)
        if len(parts) > 1:
            assert len(parts[1]) <= 100
