"""
Source Trust Configuration -- Sprint 3
=======================================

Centralized, declarative registry of publisher trust tiers and source-type bonuses.
No ranking logic lives here -- only data.

Adding a new publisher: append to the relevant tier in PUBLISHER_TRUST_TIERS.
Adding a new source type: append to SOURCE_TYPE_REGISTRY.

Trust tiers feed into SourceRanker.score_source_trust() (max 40 pts).
Source type bonuses feed into SourceRanker.score_source_type() (max 10 pts).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Publisher Trust Tiers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PublisherTier:
    label: str
    score: int          # contribution to Source Trust pillar (0-40)
    tokens: List[str]   # lowercase substrings to match against source name


PUBLISHER_TRUST_TIERS: List[PublisherTier] = [

    # Tier 0 - Official / Regulatory / Primary Filings  (40 pts)
    PublisherTier(
        label="Official/Regulatory",
        score=40,
        tokens=[
            "nseindia", "nse india", "bseindia", "bse india",
            "sebi", "sebi.gov.in", "rbi", "rbi.org.in",
            "mca.gov.in", "mca21",
            "sec.gov", "edgar",
            "investor.relations", "annual-report", "annualreport",
            "corporate.filings", "cdsl", "nsdl",
        ],
    ),

    # Tier 1 - Premium Financial Publishers  (35 pts)
    PublisherTier(
        label="Premium Financial",
        score=35,
        tokens=[
            "bloomberg", "reuters", "financial times", "ft.com",
            "wall street journal", "wsj", "wsj.com",
            "cnbc", "cnbctv18", "cnbc-tv18",
            "economic times", "economictimes",
            "business standard", "business-standard",
            "moneycontrol", "livemint", "mint",
            "forbes", "barron", "barrons",
        ],
    ),

    # Tier 2 - Quality Financial Publishers  (28 pts)
    PublisherTier(
        label="Quality Financial",
        score=28,
        tokens=[
            "yahoo finance", "finance.yahoo", "marketwatch",
            "seeking alpha", "investopedia",
            "financial express", "financialexpress",
            "hindu business line", "thehindubusinessline",
            "firstpost", "theprint", "the ken", "entrackr",
            "morning context", "motley fool", "fool.com",
            "zacks", "benzinga", "tradingview",
        ],
    ),

    # Tier 3 - General Quality News  (20 pts)
    PublisherTier(
        label="General Quality News",
        score=20,
        tokens=[
            "times of india", "timesofindia",
            "the hindu", "thehindu",
            "hindustan times", "hindustantimes",
            "ndtv", "ndtv profit",
            "bbc", "bbc news",
            "associated press", "ap news", "apnews",
            "pti", "ani",
            "the wire", "wire.in",
            "scroll", "scroll.in",
            "outlook", "outlookbusiness",
            "business today", "businesstoday",
            "the quint",
        ],
    ),

    # Tier 4 - Aggregators / Neutral Providers  (12 pts)
    PublisherTier(
        label="Aggregator",
        score=12,
        tokens=[
            "google news", "news.google",
            "finnhub", "newsapi",
            "stockedge", "tickertape",
        ],
    ),

    # Tier 5 - Unknown / Blog / Generic -> DEFAULT_TRUST_SCORE (5 pts) catch-all
]

# Convenience lookup built at import time
_TIER_LOOKUP: Dict[str, PublisherTier] = {}
for _tier in PUBLISHER_TRUST_TIERS:
    for _token in _tier.tokens:
        _TIER_LOOKUP[_token] = _tier

DEFAULT_TRUST_SCORE: int = 5   # Tier 5 fallback for unknown publishers


def resolve_publisher_tier(source_name: str) -> Optional[PublisherTier]:
    """
    Return the highest-scoring matching PublisherTier for source_name,
    or None if no tier matches (caller uses DEFAULT_TRUST_SCORE).
    """
    if not source_name:
        return None
    src_lower = source_name.lower().strip()
    best: Optional[PublisherTier] = None
    for token, tier in _TIER_LOOKUP.items():
        if token in src_lower:
            if best is None or tier.score > best.score:
                best = tier
    return best


# ---------------------------------------------------------------------------
# Source Type Bonuses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SourceTypeConfig:
    type_name: str
    bonus: int          # 0-10
    url_tokens: List[str] = field(default_factory=list)
    title_tokens: List[str] = field(default_factory=list)


SOURCE_TYPE_REGISTRY: List[SourceTypeConfig] = [

    SourceTypeConfig(
        type_name="Annual Report",
        bonus=10,
        url_tokens=["/annual-report", "/annualreport", "/annual_report", "/ar20", "/ar-20"],
        title_tokens=["annual report", "annual report 202", "financial year report"],
    ),
    SourceTypeConfig(
        type_name="Regulatory Filing",
        bonus=10,
        url_tokens=[
            "sec.gov", "edgar", "nseindia.com/companies",
            "bseindia.com/stock-market-data", "sebi.gov.in", "mca.gov.in",
        ],
        title_tokens=[
            "sec filing", "10-k", "20-f", "6-k", "8-k", "annual filing",
            "nse filing", "bse filing", "stock exchange filing", "corporate filing",
        ],
    ),
    SourceTypeConfig(
        type_name="Earnings Release",
        bonus=9,
        url_tokens=["earnings-release", "earnings_release", "press-release/earnings"],
        title_tokens=[
            "earnings release", "q1 results", "q2 results", "q3 results", "q4 results",
            "quarterly results", "annual results", "financial results", "fy results",
            "earnings announced", "profit after tax", "pat",
        ],
    ),
    SourceTypeConfig(
        type_name="Earnings Call Transcript",
        bonus=9,
        url_tokens=["earnings-call", "earnings_call", "conference-call", "transcript"],
        title_tokens=[
            "earnings call", "conference call transcript", "analyst call",
            "management call",
        ],
    ),
    SourceTypeConfig(
        type_name="Investor Presentation",
        bonus=8,
        url_tokens=[
            "investor-presentation", "investor_presentation", "ir-presentation",
            "investor-day", "capital-markets-day",
        ],
        title_tokens=[
            "investor presentation", "investor day", "capital markets day",
            "roadshow presentation", "analyst day",
        ],
    ),
    SourceTypeConfig(
        type_name="Analyst Report",
        bonus=7,
        url_tokens=["research-report", "analyst-report", "broker-report", "research/"],
        title_tokens=[
            "analyst report", "research report", "broker note", "initiating coverage",
            "initiation", "analyst upgrade", "analyst downgrade",
            "target price raised", "target price cut", "rating upgrade", "rating downgrade",
        ],
    ),
    SourceTypeConfig(
        type_name="Press Release",
        bonus=5,
        url_tokens=["press-release", "pressrelease", "press_release", "media-release", "news-release"],
        title_tokens=["press release", "official statement", "media release"],
    ),
    SourceTypeConfig(
        type_name="News Article",
        bonus=3,
        url_tokens=[],
        title_tokens=[],
    ),
]
