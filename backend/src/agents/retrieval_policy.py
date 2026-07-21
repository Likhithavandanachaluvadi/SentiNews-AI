"""
Intent-Aware Retrieval Policy Registry -- Sprint 2
===================================================

Single source of truth that maps every primary intent to a RetrievalPolicy.

To add a new intent:
  1. Add its name to IntentClassification.primary_intent in intent_classifier.py
  2. Add a matching entry to INTENT_POLICIES below.
  3. No other files need changing.

Policy fields
-------------
fetch_market      bool   Fetch yfinance / screener market data
fetch_financials  bool   Fetch annual/quarterly reports, ratios
fetch_news        bool   Fetch news aggregator articles
news_min_score    int    Minimum financial_relevance_score to include (Sprint 1)
news_max_docs     int    Maximum news articles to pass into context
news_categories   list   Whitelist of Sprint-1 financial_category values ([] = all)
blocked_categories list  Categories to suppress even if score is high
requires_ticker   bool   If True and no ticker found, skip all live calls
multi_entity      bool   If True, fetch independently for every resolved entity
max_context_docs  int    Hard ceiling on total context items sent to LLM
description       str    Human-readable note for logging / debugging
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class RetrievalPolicy:
    fetch_market: bool
    fetch_financials: bool
    fetch_news: bool
    news_min_score: int = 20
    news_max_docs: int = 8
    news_categories: List[str] = field(default_factory=list)     # [] = all allowed
    blocked_categories: List[str] = field(default_factory=list)  # [] = none blocked
    requires_ticker: bool = True
    multi_entity: bool = False
    max_context_docs: int = 20
    pipeline: str = "Company Pipeline"
    modules: List[str] = field(default_factory=list)
    skipped_modules: List[str] = field(default_factory=list)
    description: str = ""


# ---------------------------------------------------------------------------
# Pre-defined category whitelists (reuse across similar intents)
# ---------------------------------------------------------------------------

_EARNINGS_CATEGORIES = [
    "Earnings", "Financial Results", "Revenue", "Profit", "Guidance",
]

_FINANCIAL_CATEGORIES = [
    "Earnings", "Financial Results", "Revenue", "Profit", "Dividend",
    "Guidance", "Acquisition", "Merger", "Analyst Rating", "Regulation",
]

_MARKET_MOVEMENT_CATEGORIES = [
    "Market Movement", "Earnings", "Financial Results", "Revenue", "Profit",
]

_RISK_CATEGORIES = [
    "Regulation", "Governance", "Analyst Rating", "Earnings",
    "Financial Results", "Acquisition", "Merger",
]

# ---------------------------------------------------------------------------
# Intent -> Policy Registry
# ---------------------------------------------------------------------------

INTENT_POLICIES: Dict[str, RetrievalPolicy] = {

    # ------------------------------------------------------------------
    # STOCK_ANALYSIS  -- full data, all signals
    # ------------------------------------------------------------------
    "STOCK_ANALYSIS": RetrievalPolicy(
        fetch_market=True,
        fetch_financials=True,
        fetch_news=True,
        news_min_score=30,
        news_max_docs=8,
        news_categories=[],          # all financial categories
        blocked_categories=[],
        requires_ticker=True,
        multi_entity=False,
        max_context_docs=20,
        description="Full data: market + financials + news (all categories)",
    ),

    # ------------------------------------------------------------------
    # FUNDAMENTAL_ANALYSIS  -- financials-first, no technical chart data,
    #                          news restricted to financial-event categories
    # ------------------------------------------------------------------
    "FUNDAMENTAL_ANALYSIS": RetrievalPolicy(
        fetch_market=True,           # need price for valuation ratios
        fetch_financials=True,
        fetch_news=True,
        news_min_score=35,           # stricter than STOCK_ANALYSIS
        news_max_docs=5,
        news_categories=_FINANCIAL_CATEGORIES,
        blocked_categories=["Product Launch", "Other"],
        requires_ticker=True,
        multi_entity=False,
        max_context_docs=18,
        description="Financials focus: market + reports + earnings/results news only",
    ),

    # ------------------------------------------------------------------
    # TECHNICAL_ANALYSIS  -- price action only; no reports, no news
    # ------------------------------------------------------------------
    "TECHNICAL_ANALYSIS": RetrievalPolicy(
        fetch_market=True,
        fetch_financials=False,
        fetch_news=False,
        news_min_score=0,
        news_max_docs=0,
        news_categories=[],
        blocked_categories=[],
        requires_ticker=True,
        multi_entity=False,
        max_context_docs=10,
        pipeline="Technical Pipeline",
        modules=["Price History", "Indicators", "Momentum"],
        skipped_modules=["Fundamentals", "Peers"],
        description="Price + indicators only: no financials, no news",
    ),

    # ------------------------------------------------------------------
    # NEWS_ANALYSIS  -- news only, no price/financial data
    # ------------------------------------------------------------------
    "NEWS_ANALYSIS": RetrievalPolicy(
        fetch_market=False,
        fetch_financials=False,
        fetch_news=True,
        news_min_score=20,
        news_max_docs=10,
        news_categories=[],          # all financial news types
        blocked_categories=[],
        requires_ticker=False,       # can work without a ticker (sector news)
        multi_entity=False,
        max_context_docs=12,
        pipeline="News Pipeline",
        modules=["News", "Sentiment"],
        skipped_modules=["Yahoo", "Screener", "Peer Comparison"],
        description="News-only: no market data, no financial reports",
    ),

    # ------------------------------------------------------------------
    # EARNINGS_REPORT  -- strict category whitelist for earnings content
    # ------------------------------------------------------------------
    "EARNINGS_REPORT": RetrievalPolicy(
        fetch_market=True,
        fetch_financials=True,
        fetch_news=True,
        news_min_score=40,           # high bar: must be a real earnings article
        news_max_docs=6,
        news_categories=_EARNINGS_CATEGORIES,
        blocked_categories=["Other", "Product Launch", "Governance"],
        requires_ticker=True,
        multi_entity=False,
        max_context_docs=16,
        description="Earnings focus: high relevance bar, earnings/results categories only",
    ),

    # ------------------------------------------------------------------
    # COMPARISON  -- full data, independently for each entity
    # ------------------------------------------------------------------
    "COMPARISON": RetrievalPolicy(
        fetch_market=True,
        fetch_financials=True,
        fetch_news=True,
        news_min_score=25,
        news_max_docs=5,             # per entity
        news_categories=_FINANCIAL_CATEGORIES,
        blocked_categories=[],
        requires_ticker=True,
        multi_entity=True,           # KEY: loop over all resolved entities
        max_context_docs=30,         # higher cap to fit multiple companies
        description="Multi-entity: fetch market + financials + news for each company independently",
    ),

    # ------------------------------------------------------------------
    # PEER_COMPARISON  -- financial metrics, no news needed
    # ------------------------------------------------------------------
    "PEER_COMPARISON": RetrievalPolicy(
        fetch_market=True,
        fetch_financials=True,
        fetch_news=False,
        news_min_score=0,
        news_max_docs=0,
        news_categories=[],
        blocked_categories=[],
        requires_ticker=True,
        multi_entity=True,           # compare peers too
        max_context_docs=20,
        description="Peer metrics: market + financials for each entity, no news",
    ),

    # ------------------------------------------------------------------
    # STOCK_MOVEMENT  -- recent news + price action
    # ------------------------------------------------------------------
    "STOCK_MOVEMENT": RetrievalPolicy(
        fetch_market=True,
        fetch_financials=False,
        fetch_news=True,
        news_min_score=20,
        news_max_docs=6,
        news_categories=_MARKET_MOVEMENT_CATEGORIES,
        blocked_categories=["Governance", "Product Launch", "Other"],
        requires_ticker=True,
        multi_entity=False,
        max_context_docs=12,
        description="Price + movement news: why did the stock move?",
    ),

    # ------------------------------------------------------------------
    # SENTIMENT_PULSE  -- news sentiment only
    # ------------------------------------------------------------------
    "SENTIMENT_PULSE": RetrievalPolicy(
        fetch_market=False,
        fetch_financials=False,
        fetch_news=True,
        news_min_score=20,
        news_max_docs=10,
        news_categories=[],
        blocked_categories=[],
        requires_ticker=False,
        multi_entity=False,
        max_context_docs=12,
        description="Sentiment: news only, no market data",
    ),

    # ------------------------------------------------------------------
    # RISK_ANALYSIS  -- regulatory, governance, analyst downgrades
    # ------------------------------------------------------------------
    "RISK_ANALYSIS": RetrievalPolicy(
        fetch_market=True,
        fetch_financials=True,
        fetch_news=True,
        news_min_score=25,
        news_max_docs=5,
        news_categories=_RISK_CATEGORIES,
        blocked_categories=["Product Launch", "Other"],
        requires_ticker=True,
        multi_entity=False,
        max_context_docs=16,
        description="Risk focus: regulatory, governance, analyst ratings news",
    ),

    # ------------------------------------------------------------------
    # COMPANY_OVERVIEW  -- broad view, all data, lower news bar
    # ------------------------------------------------------------------
    "COMPANY_OVERVIEW": RetrievalPolicy(
        fetch_market=True,
        fetch_financials=True,
        fetch_news=True,
        news_min_score=25,
        news_max_docs=5,
        news_categories=[],
        blocked_categories=[],
        requires_ticker=True,
        multi_entity=False,
        max_context_docs=18,
        description="Company overview: broad data across all signals",
    ),

    # ------------------------------------------------------------------
    # COMPANY_ANALYSIS  -- fundamentals + technicals + sentiment + peers
    # ------------------------------------------------------------------
    "COMPANY_ANALYSIS": RetrievalPolicy(
        fetch_market=True,
        fetch_financials=True,
        fetch_news=True,
        news_min_score=25,
        news_max_docs=8,
        news_categories=[],
        blocked_categories=[],
        requires_ticker=True,
        multi_entity=False,
        max_context_docs=20,
        pipeline="Company Pipeline",
        modules=["Fundamentals", "Technicals", "Sentiment", "Peers"],
        skipped_modules=[],
        description="Company analysis: fundamentals, technicals, sentiment, and peers",
    ),

    # ------------------------------------------------------------------
    # COMPANY_COMPARISON  -- comparison between two or more companies
    # ------------------------------------------------------------------
    "COMPANY_COMPARISON": RetrievalPolicy(
        fetch_market=True,
        fetch_financials=True,
        fetch_news=True,
        news_min_score=25,
        news_max_docs=5,
        news_categories=[],
        blocked_categories=[],
        requires_ticker=True,
        multi_entity=True,
        max_context_docs=30,
        pipeline="Comparison Pipeline",
        modules=["Comparison Retrieval", "Fundamentals", "News", "Relative Metrics"],
        skipped_modules=[],
        description="Company comparison: multi-entity financials, news, and relative metrics",
    ),

    # ------------------------------------------------------------------
    # SECTOR_OUTLOOK  -- sector/industry trends and macro outlook
    # ------------------------------------------------------------------
    "SECTOR_OUTLOOK": RetrievalPolicy(
        fetch_market=False,
        fetch_financials=False,
        fetch_news=True,
        news_min_score=15,
        news_max_docs=8,
        news_categories=[],
        blocked_categories=[],
        requires_ticker=False,
        multi_entity=False,
        max_context_docs=16,
        pipeline="Sector Pipeline",
        modules=["Sector News", "Macro", "Industry Trends"],
        skipped_modules=["Yahoo", "Screener", "Peer Comparison", "Company Financials"],
        description="Sector outlook: sector news, macro, industry reports, and trends (no company financials)",
    ),

    # ------------------------------------------------------------------
    # THEME_ANALYSIS  -- tech trends and industry adoption
    # ------------------------------------------------------------------
    "THEME_ANALYSIS": RetrievalPolicy(
        fetch_market=False,
        fetch_financials=False,
        fetch_news=True,
        news_min_score=15,
        news_max_docs=8,
        news_categories=[],
        blocked_categories=[],
        requires_ticker=False,
        multi_entity=False,
        max_context_docs=16,
        pipeline="Theme Pipeline",
        modules=["Technology Trends", "Research", "Industry Adoption"],
        skipped_modules=["Yahoo", "Screener", "Peer Comparison", "Market Data"],
        description="Theme analysis: technology trends, industry adoption, and theme news",
    ),

    # ------------------------------------------------------------------
    # MARKET_OVERVIEW  -- index + macro + sector news, no company financials
    # ------------------------------------------------------------------
    "MARKET_OVERVIEW": RetrievalPolicy(
        fetch_market=False,
        fetch_financials=False,
        fetch_news=True,
        news_min_score=15,
        news_max_docs=5,
        news_categories=[],
        blocked_categories=[],
        requires_ticker=False,
        multi_entity=False,
        max_context_docs=12,
        pipeline="Market Pipeline",
        modules=["Market News", "Macro", "Index Context"],
        skipped_modules=["Screener", "Peer Comparison", "Company Financials"],
        description="Market overview: macro and market news, no company reports",
    ),

    # ------------------------------------------------------------------
    # VALUATION_ANALYSIS  -- valuation multiples, PE/PEG/DCF focus
    # ------------------------------------------------------------------
    "VALUATION_ANALYSIS": RetrievalPolicy(
        fetch_market=True,
        fetch_financials=True,
        fetch_news=True,
        news_min_score=30,
        news_max_docs=6,
        news_categories=_FINANCIAL_CATEGORIES,
        blocked_categories=["Product Launch", "Other"],
        requires_ticker=True,
        multi_entity=False,
        max_context_docs=18,
        description="Valuation analysis: ratios, multiples, and relative valuation metrics",
    ),

    # ------------------------------------------------------------------
    # EDUCATIONAL (no company)  -- static knowledge, zero live calls
    # EDUCATIONAL (+ company)   -- handled at runtime in dynamic_retriever
    # ------------------------------------------------------------------
    "EDUCATIONAL": RetrievalPolicy(
        fetch_market=False,
        fetch_financials=False,
        fetch_news=False,
        news_min_score=0,
        news_max_docs=0,
        news_categories=[],
        blocked_categories=[],
        requires_ticker=False,
        multi_entity=False,
        max_context_docs=0,
        pipeline="Knowledge Pipeline",
        modules=["Knowledge", "Definitions", "Glossary"],
        skipped_modules=["Yahoo", "Screener", "Peer Comparison", "Market Data"],
        description="Static knowledge only: no live API calls",
    ),

    # ------------------------------------------------------------------
    # RESTRICTED_ADVISORY  -- hard block, zero live calls
    # ------------------------------------------------------------------
    "RESTRICTED_ADVISORY": RetrievalPolicy(
        fetch_market=False,
        fetch_financials=False,
        fetch_news=False,
        news_min_score=0,
        news_max_docs=0,
        news_categories=[],
        blocked_categories=[],
        requires_ticker=False,
        multi_entity=False,
        max_context_docs=0,
        description="Hard block: immediate refusal, no live data",
    ),

    # ------------------------------------------------------------------
    # GENERALIZED  -- safe full-data default (mirrors original behaviour)
    # ------------------------------------------------------------------
    "GENERALIZED": RetrievalPolicy(
        fetch_market=True,
        fetch_financials=True,
        fetch_news=True,
        news_min_score=20,
        news_max_docs=8,
        news_categories=[],
        blocked_categories=[],
        requires_ticker=True,
        multi_entity=False,
        max_context_docs=20,
        description="Safe default: full data across all signals",
    ),
}

# Aliases kept for backward compatibility with callers that use these intent names
INTENT_POLICIES["MACROECONOMIC"] = INTENT_POLICIES["MARKET_OVERVIEW"]
INTENT_POLICIES["STOCK_ANALYSIS"] = INTENT_POLICIES["COMPANY_ANALYSIS"]
INTENT_POLICIES["COMPARISON"] = INTENT_POLICIES["COMPANY_COMPARISON"]
INTENT_POLICIES["UNKNOWN"] = INTENT_POLICIES["GENERALIZED"]


def get_policy(primary_intent: str) -> RetrievalPolicy:
    """
    Look up the RetrievalPolicy for a given primary_intent.
    Falls back to GENERALIZED if the intent is unknown.
    """
    return INTENT_POLICIES.get(primary_intent, INTENT_POLICIES["GENERALIZED"])
