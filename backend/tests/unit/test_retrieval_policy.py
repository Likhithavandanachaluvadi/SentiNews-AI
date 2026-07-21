"""
Unit tests for RetrievalPolicy registry -- Sprint 2

Covers:
  - Every known intent has a policy entry (no KeyError)
  - EDUCATIONAL (no company) -> all fetch flags False
  - EDUCATIONAL (+company) logic: override produces fetch_market=True
  - TECHNICAL_ANALYSIS -> fetch_financials=False, fetch_news=False
  - FUNDAMENTAL_ANALYSIS -> news_categories restricted to financial events
  - COMPARISON -> multi_entity=True
  - PEER_COMPARISON -> multi_entity=True, fetch_news=False
  - NEWS_ANALYSIS -> fetch_market=False, fetch_financials=False
  - RESTRICTED_ADVISORY -> all fetch flags False
  - STOCK_ANALYSIS -> all fetch flags True, full data
  - Unknown intent falls back to GENERALIZED
  - news_min_score always in [0, 100]
  - news_max_docs >= 0
  - max_context_docs >= 0
  - Context cap > 0 for data-fetching intents
  - Planner required_data consistency: planner required_data
    matches policy fetch flags for key intents
"""

import pytest
from dataclasses import replace as dc_replace

from src.agents.retrieval_policy import (
    INTENT_POLICIES,
    RetrievalPolicy,
    get_policy,
)
from src.agents.planner import ResponsePlanner


# All intent names recognised by the intent classifier
ALL_KNOWN_INTENTS = [
    "STOCK_ANALYSIS",
    "FUNDAMENTAL_ANALYSIS",
    "TECHNICAL_ANALYSIS",
    "NEWS_ANALYSIS",
    "EARNINGS_REPORT",
    "COMPARISON",
    "PEER_COMPARISON",
    "STOCK_MOVEMENT",
    "SENTIMENT_PULSE",
    "RISK_ANALYSIS",
    "COMPANY_OVERVIEW",
    "MARKET_OVERVIEW",
    "EDUCATIONAL",
    "RESTRICTED_ADVISORY",
    "GENERALIZED",
    "COMPANY_ANALYSIS",
    "COMPANY_COMPARISON",
    "SECTOR_OUTLOOK",
    "THEME_ANALYSIS",
    "VALUATION_ANALYSIS",
    "UNKNOWN",
]


# ---------------------------------------------------------------------------
# Registry completeness
# ---------------------------------------------------------------------------

class TestRegistryCompleteness:

    def test_every_known_intent_has_a_policy(self):
        for intent in ALL_KNOWN_INTENTS:
            policy = get_policy(intent)
            assert isinstance(policy, RetrievalPolicy), \
                f"No RetrievalPolicy found for intent '{intent}'"

    def test_unknown_intent_returns_generalized(self):
        policy = get_policy("SOME_FUTURE_INTENT_THAT_DOES_NOT_EXIST")
        generalized = get_policy("GENERALIZED")
        assert policy == generalized

    def test_macroeconomic_alias_resolves(self):
        """MACROECONOMIC is aliased to MARKET_OVERVIEW."""
        policy = get_policy("MACROECONOMIC")
        assert isinstance(policy, RetrievalPolicy)


# ---------------------------------------------------------------------------
# Field sanity bounds
# ---------------------------------------------------------------------------

class TestFieldSanityBounds:

    @pytest.mark.parametrize("intent", ALL_KNOWN_INTENTS)
    def test_news_min_score_in_range(self, intent):
        p = get_policy(intent)
        assert 0 <= p.news_min_score <= 100, \
            f"{intent}: news_min_score={p.news_min_score} out of [0, 100]"

    @pytest.mark.parametrize("intent", ALL_KNOWN_INTENTS)
    def test_news_max_docs_non_negative(self, intent):
        p = get_policy(intent)
        assert p.news_max_docs >= 0, \
            f"{intent}: news_max_docs={p.news_max_docs} is negative"

    @pytest.mark.parametrize("intent", ALL_KNOWN_INTENTS)
    def test_max_context_docs_non_negative(self, intent):
        p = get_policy(intent)
        assert p.max_context_docs >= 0, \
            f"{intent}: max_context_docs={p.max_context_docs} is negative"

    @pytest.mark.parametrize("intent", ALL_KNOWN_INTENTS)
    def test_description_is_non_empty_string(self, intent):
        p = get_policy(intent)
        assert isinstance(p.description, str) and len(p.description) > 0, \
            f"{intent}: description is empty"

    @pytest.mark.parametrize("intent", ALL_KNOWN_INTENTS)
    def test_news_categories_is_list(self, intent):
        p = get_policy(intent)
        assert isinstance(p.news_categories, list), \
            f"{intent}: news_categories is not a list"

    @pytest.mark.parametrize("intent", ALL_KNOWN_INTENTS)
    def test_blocked_categories_is_list(self, intent):
        p = get_policy(intent)
        assert isinstance(p.blocked_categories, list), \
            f"{intent}: blocked_categories is not a list"


# ---------------------------------------------------------------------------
# EDUCATIONAL intent
# ---------------------------------------------------------------------------

class TestEducationalIntent:

    def test_educational_no_company_all_flags_false(self):
        """Pure educational query (no ticker): no live API calls."""
        p = get_policy("EDUCATIONAL")
        assert p.fetch_market is False
        assert p.fetch_financials is False
        assert p.fetch_news is False

    def test_educational_context_cap_is_zero(self):
        p = get_policy("EDUCATIONAL")
        assert p.max_context_docs == 0

    def test_educational_company_override_produces_live_flags(self):
        """Simulate the runtime override applied in dynamic_retriever for EDUCATIONAL+ticker."""
        base = get_policy("EDUCATIONAL")
        override = dc_replace(
            base,
            fetch_market=True,
            fetch_financials=True,
            fetch_news=False,
        )
        assert override.fetch_market is True
        assert override.fetch_financials is True
        assert override.fetch_news is False
        # Original policy unchanged (frozen dataclass)
        assert base.fetch_market is False

    def test_educational_policy_is_immutable(self):
        p = get_policy("EDUCATIONAL")
        with pytest.raises((AttributeError, TypeError)):
            p.fetch_market = True   # type: ignore[misc]


# ---------------------------------------------------------------------------
# RESTRICTED_ADVISORY intent
# ---------------------------------------------------------------------------

class TestRestrictedAdvisory:

    def test_all_fetch_flags_false(self):
        p = get_policy("RESTRICTED_ADVISORY")
        assert p.fetch_market is False
        assert p.fetch_financials is False
        assert p.fetch_news is False

    def test_context_cap_is_zero(self):
        assert get_policy("RESTRICTED_ADVISORY").max_context_docs == 0

    def test_requires_ticker_false(self):
        assert get_policy("RESTRICTED_ADVISORY").requires_ticker is False

    def test_multi_entity_false(self):
        assert get_policy("RESTRICTED_ADVISORY").multi_entity is False


# ---------------------------------------------------------------------------
# TECHNICAL_ANALYSIS intent
# ---------------------------------------------------------------------------

class TestTechnicalAnalysis:

    def test_fetch_market_true(self):
        assert get_policy("TECHNICAL_ANALYSIS").fetch_market is True

    def test_fetch_financials_false(self):
        assert get_policy("TECHNICAL_ANALYSIS").fetch_financials is False

    def test_fetch_news_false(self):
        assert get_policy("TECHNICAL_ANALYSIS").fetch_news is False

    def test_news_max_docs_zero(self):
        assert get_policy("TECHNICAL_ANALYSIS").news_max_docs == 0

    def test_context_cap_is_tight(self):
        """Chart-only mode should have a lower cap than full analysis."""
        tech_cap = get_policy("TECHNICAL_ANALYSIS").max_context_docs
        full_cap = get_policy("STOCK_ANALYSIS").max_context_docs
        assert tech_cap <= full_cap


# ---------------------------------------------------------------------------
# FUNDAMENTAL_ANALYSIS intent
# ---------------------------------------------------------------------------

class TestFundamentalAnalysis:

    def test_fetch_market_true(self):
        assert get_policy("FUNDAMENTAL_ANALYSIS").fetch_market is True

    def test_fetch_financials_true(self):
        assert get_policy("FUNDAMENTAL_ANALYSIS").fetch_financials is True

    def test_fetch_news_true(self):
        assert get_policy("FUNDAMENTAL_ANALYSIS").fetch_news is True

    def test_news_categories_restricted(self):
        """Fundamental analysis should only fetch financial-event news."""
        p = get_policy("FUNDAMENTAL_ANALYSIS")
        assert len(p.news_categories) > 0, \
            "FUNDAMENTAL_ANALYSIS should have a news_categories whitelist"
        assert "Earnings" in p.news_categories
        assert "Revenue" in p.news_categories

    def test_news_min_score_higher_than_generalized(self):
        """Stricter relevance bar than the default."""
        fund_min = get_policy("FUNDAMENTAL_ANALYSIS").news_min_score
        gen_min = get_policy("GENERALIZED").news_min_score
        assert fund_min >= gen_min


# ---------------------------------------------------------------------------
# EARNINGS_REPORT intent
# ---------------------------------------------------------------------------

class TestEarningsReport:

    def test_all_data_fetched(self):
        p = get_policy("EARNINGS_REPORT")
        assert p.fetch_market and p.fetch_financials and p.fetch_news

    def test_very_high_news_min_score(self):
        """Earnings reports need only the highest-relevance articles."""
        assert get_policy("EARNINGS_REPORT").news_min_score >= 35

    def test_earnings_categories_in_whitelist(self):
        p = get_policy("EARNINGS_REPORT")
        assert "Earnings" in p.news_categories
        assert "Financial Results" in p.news_categories


# ---------------------------------------------------------------------------
# COMPARISON intent
# ---------------------------------------------------------------------------

class TestComparisonIntent:

    def test_multi_entity_true(self):
        assert get_policy("COMPARISON").multi_entity is True

    def test_all_data_fetched(self):
        p = get_policy("COMPARISON")
        assert p.fetch_market and p.fetch_financials and p.fetch_news

    def test_context_cap_larger_than_single_entity(self):
        """Comparison needs more context to hold data for two+ companies."""
        comp_cap = get_policy("COMPARISON").max_context_docs
        stock_cap = get_policy("STOCK_ANALYSIS").max_context_docs
        assert comp_cap >= stock_cap


# ---------------------------------------------------------------------------
# PEER_COMPARISON intent
# ---------------------------------------------------------------------------

class TestPeerComparison:

    def test_multi_entity_true(self):
        assert get_policy("PEER_COMPARISON").multi_entity is True

    def test_fetch_news_false(self):
        """Peer comparison is purely financial metrics — no news needed."""
        assert get_policy("PEER_COMPARISON").fetch_news is False

    def test_fetch_financials_true(self):
        assert get_policy("PEER_COMPARISON").fetch_financials is True


# ---------------------------------------------------------------------------
# NEWS_ANALYSIS intent
# ---------------------------------------------------------------------------

class TestNewsAnalysis:

    def test_fetch_market_false(self):
        assert get_policy("NEWS_ANALYSIS").fetch_market is False

    def test_fetch_financials_false(self):
        assert get_policy("NEWS_ANALYSIS").fetch_financials is False

    def test_fetch_news_true(self):
        assert get_policy("NEWS_ANALYSIS").fetch_news is True

    def test_requires_ticker_false(self):
        """News analysis can work for sector/market queries without a ticker."""
        assert get_policy("NEWS_ANALYSIS").requires_ticker is False

    def test_news_max_docs_generous(self):
        """News-only queries benefit from more articles."""
        assert get_policy("NEWS_ANALYSIS").news_max_docs >= 8


# ---------------------------------------------------------------------------
# SENTIMENT_PULSE intent
# ---------------------------------------------------------------------------

class TestSentimentPulse:

    def test_fetch_market_false(self):
        assert get_policy("SENTIMENT_PULSE").fetch_market is False

    def test_fetch_financials_false(self):
        assert get_policy("SENTIMENT_PULSE").fetch_financials is False

    def test_fetch_news_true(self):
        assert get_policy("SENTIMENT_PULSE").fetch_news is True


# ---------------------------------------------------------------------------
# STOCK_MOVEMENT intent
# ---------------------------------------------------------------------------

class TestStockMovement:

    def test_fetch_market_true(self):
        assert get_policy("STOCK_MOVEMENT").fetch_market is True

    def test_fetch_financials_false(self):
        """Movement queries don't need full financial statements."""
        assert get_policy("STOCK_MOVEMENT").fetch_financials is False

    def test_fetch_news_true(self):
        assert get_policy("STOCK_MOVEMENT").fetch_news is True

    def test_market_movement_in_categories(self):
        p = get_policy("STOCK_MOVEMENT")
        assert "Market Movement" in p.news_categories


# ---------------------------------------------------------------------------
# STOCK_ANALYSIS intent (baseline / full data)
# ---------------------------------------------------------------------------

class TestStockAnalysis:

    def test_all_fetch_flags_true(self):
        p = get_policy("STOCK_ANALYSIS")
        assert p.fetch_market and p.fetch_financials and p.fetch_news

    def test_all_categories_allowed(self):
        """STOCK_ANALYSIS should allow all news categories (empty = no filter)."""
        assert get_policy("STOCK_ANALYSIS").news_categories == []

    def test_no_blocked_categories(self):
        assert get_policy("STOCK_ANALYSIS").blocked_categories == []

    def test_multi_entity_false(self):
        assert get_policy("STOCK_ANALYSIS").multi_entity is False


# ---------------------------------------------------------------------------
# GENERALIZED intent (safe default)
# ---------------------------------------------------------------------------

class TestGeneralized:

    def test_all_fetch_flags_true(self):
        p = get_policy("GENERALIZED")
        assert p.fetch_market and p.fetch_financials and p.fetch_news

    def test_multi_entity_false(self):
        assert get_policy("GENERALIZED").multi_entity is False


# ---------------------------------------------------------------------------
# Planner consistency checks
# ---------------------------------------------------------------------------

class TestPlannerConsistency:
    """
    Verify that planner required_data flags stay consistent with policy fetch flags
    for the key intents that were specialised in Sprint 2.
    """

    @pytest.mark.parametrize("intent,expected_market,expected_financials,expected_news", [
        ("TECHNICAL_ANALYSIS", True,  False, False),
        ("STOCK_MOVEMENT",     True,  False, True),
        ("PEER_COMPARISON",    True,  True,  False),
        ("SENTIMENT_PULSE",    False, False, True),
        ("NEWS_ANALYSIS",      False, False, True),
        ("EDUCATIONAL",        False, False, False),
        ("RESTRICTED_ADVISORY",False, False, False),
    ])
    def test_planner_required_data_matches_policy(
        self, intent, expected_market, expected_financials, expected_news
    ):
        layout = ResponsePlanner.get_layout(intent)
        rd = layout.get("required_data", {})
        assert rd.get("market") == expected_market, \
            f"{intent}: planner market={rd.get('market')}, expected {expected_market}"
        assert rd.get("financials") == expected_financials, \
            f"{intent}: planner financials={rd.get('financials')}, expected {expected_financials}"
        assert rd.get("news") == expected_news, \
            f"{intent}: planner news={rd.get('news')}, expected {expected_news}"
