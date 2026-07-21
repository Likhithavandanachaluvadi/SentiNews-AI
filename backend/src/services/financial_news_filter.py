"""
Financial News Filtering Engine — Sprint 1
==========================================

Standalone, zero-LLM-call service that scores, classifies, and filters
news articles by financial investment relevance.

Scoring uses a 4-pillar composite model:

  P1 — Financial Keyword Quality  (max 40 pts, weight 40%)
  P2 — Publisher / Source Quality (max 20 pts, weight 20%)
  P3 — Article Freshness          (max 20 pts, weight 20%)
  P4 — Company Name Relevance     (max 20 pts, weight 20%)
  Noise Penalty                   (−40 pts when noise-only)

  Final score = clamp(P1 + P2 + P3 + P4 − noise_penalty, 0, 100)

Each article is also assigned a `financial_category` from 14 classes.
Both fields are added as extra dict keys; all existing keys are preserved.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Category definitions (order matters — first match wins)
# ---------------------------------------------------------------------------
CATEGORY_KEYWORDS: List[Tuple[str, List[str]]] = [
    ("Earnings",          ["earnings", "eps", "earnings per share", "quarterly earnings",
                           "annual earnings", "earnings beat", "earnings miss", "earnings report"]),
    ("Financial Results", ["quarterly results", "annual results", "q1 results", "q2 results",
                           "q3 results", "q4 results", "fy results", "financial results",
                           "results announced", "net income", "pat", "ebitda", "ebit",
                           "profit after tax", "profit before tax"]),
    ("Revenue",           ["revenue", "sales growth", "topline", "top-line", "turnover",
                           "net sales", "gross revenue", "operating revenue"]),
    ("Profit",            ["profit", "net profit", "gross profit", "operating profit",
                           "profit margin", "margin expansion", "margin compression",
                           "profit growth", "profitability"]),
    ("Dividend",          ["dividend", "interim dividend", "final dividend", "special dividend",
                           "dividend declared", "dividend payout", "ex-dividend", "dividend yield"]),
    ("Guidance",          ["guidance", "outlook", "forecast", "projection", "capex plan",
                           "revenue guidance", "earnings guidance", "management commentary",
                           "full year guidance"]),
    ("Acquisition",       ["acquisition", "acquires", "acquired", "takeover", "buyout",
                           "strategic buy", "stake acquisition", "bought out"]),
    ("Merger",            ["merger", "merges", "merged", "amalgamation", "consolidation",
                           "combined entity", "deal closed", "scheme of arrangement"]),
    ("Market Movement",   ["stock price", "share price", "market cap", "52-week high",
                           "52-week low", "trading halt", "circuit breaker", "rally",
                           "sell-off", "correction", "bull run", "bear market"]),
    ("Regulation",        ["regulatory", "sebi", "rbi", "sec", "compliance", "penalty",
                           "fine", "ban", "sanction", "investigation", "probe", "notice",
                           "nse", "bse", "exchange notice"]),
    ("Governance",        ["board", "agm", "egm", "management change", "ceo", "cfo",
                           "md & ceo", "director appointment", "director resignation",
                           "shareholding", "promoter stake", "insider trading"]),
    ("Analyst Rating",    ["analyst", "upgrade", "downgrade", "target price", "price target",
                           "buy rating", "sell rating", "hold rating", "overweight",
                           "underweight", "outperform", "underperform", "broker note",
                           "research report", "initiation"]),
    ("Product Launch",    ["product launch", "new product", "launches", "unveiled",
                           "product announcement", "new offering", "commercial launch",
                           "goes live", "rollout"]),
]

# ---------------------------------------------------------------------------
# P1 — Financial Keyword tiers
# ---------------------------------------------------------------------------
TIER1_KEYWORDS: List[str] = [
    "earnings", "revenue", "profit", "eps", "ebitda", "net income",
    "quarterly results", "annual results", "q1 results", "q2 results",
    "q3 results", "q4 results", "fy results", "pat", "ebit",
    "profit after tax", "profit before tax", "net profit", "gross profit",
    "operating profit", "financial results", "results announced",
]
TIER2_KEYWORDS: List[str] = [
    "dividend", "acquisition", "merger", "guidance", "capex",
    "analyst upgrade", "analyst downgrade", "target price", "price target",
    "stake sale", "buyback", "ipo", "fpo", "rights issue",
    "open offer", "block deal", "bulk deal", "ncd", "debenture",
    "fundraise", "capital raise", "divestment", "divestiture",
    "amalgamation", "scheme of arrangement",
]
TIER3_KEYWORDS: List[str] = [
    "market share", "regulatory", "sebi", "rbi", "sec", "compliance",
    "board", "agm", "egm", "management change", "ceo", "cfo",
    "director", "shareholding", "promoter stake", "insider trading",
    "stock price", "share price", "market cap", "52-week", "rally",
    "sell-off", "correction",
]

# ---------------------------------------------------------------------------
# Noise keywords — low-investment-value signals
# ---------------------------------------------------------------------------
NOISE_KEYWORDS: List[str] = [
    "hiring", "recruitment", "job opening", "job fair", "vacancies",
    "csr", "corporate social responsibility", "philanthropy",
    "award", "awards", "felicitated", "won award", "won prize",
    "sponsorship", "sponsors", "sponsored",
    "inauguration", "inaugurates", "inaugurated", "office opening",
    "employee", "workforce event", "town hall", "team building",
    "csr initiative", "community outreach", "donation", "charity",
    "campus placement", "internship drive",
]

# ---------------------------------------------------------------------------
# P2 — Publisher quality tiers
# ---------------------------------------------------------------------------
PUBLISHER_TIER_A: List[str] = [
    "bloomberg", "reuters", "financial times", "wall street journal", "wsj",
    "cnbc", "economic times", "mint", "business standard", "moneycontrol",
    "livemint", "forbes", "barron", "ft.com", "investing.com",
    "the ken", "morning context", "entrackr",
]
PUBLISHER_TIER_B: List[str] = [
    "times of india", "the hindu", "hindustan times", "ndtv", "bbc",
    "associated press", "ap news", "pti", "ani", "yahoo finance",
    "marketwatch", "seeking alpha", "motley fool", "business today",
    "financial express", "the print", "wire", "scroll",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize(text: Optional[str]) -> str:
    """Lowercase, collapse whitespace."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.lower().strip())


def _count_keyword_hits(text: str, keywords: List[str]) -> int:
    """Count how many distinct keywords appear in text."""
    return sum(1 for kw in keywords if kw in text)


def _parse_published_at(published_at: Optional[str]) -> Optional[datetime]:
    """Best-effort ISO 8601 parse; returns None on failure."""
    if not published_at:
        return None
    try:
        # Handle Z suffix
        ts = published_at.replace("Z", "+00:00")
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Pillar scoring functions
# ---------------------------------------------------------------------------

def _score_p1_keywords(combined_text: str) -> Tuple[int, bool]:
    """
    P1 — Financial Keyword Quality (max 40 pts).

    Returns (score, has_any_financial_keyword).
    """
    t1 = _count_keyword_hits(combined_text, TIER1_KEYWORDS)
    t2 = _count_keyword_hits(combined_text, TIER2_KEYWORDS)
    t3 = _count_keyword_hits(combined_text, TIER3_KEYWORDS)

    t1_pts = min(t1 * 15, 30)
    t2_pts = min(t2 * 8, 24)
    t3_pts = min(t3 * 5, 15)

    raw = t1_pts + t2_pts + t3_pts
    score = min(raw, 40)
    has_financial = (t1 + t2 + t3) > 0
    return score, has_financial


def _score_p2_publisher(source: Optional[str]) -> int:
    """P2 — Publisher / Source Quality (max 20 pts)."""
    if not source:
        return 6  # Unknown → Tier C

    src_lower = source.lower()

    for pub in PUBLISHER_TIER_A:
        if pub in src_lower:
            return 20

    for pub in PUBLISHER_TIER_B:
        if pub in src_lower:
            return 12

    return 6  # Tier C — aggregator / unknown


def _score_p3_freshness(published_at: Optional[str]) -> int:
    """P3 — Article Freshness (max 20 pts)."""
    dt = _parse_published_at(published_at)
    if dt is None:
        return 0

    # Ensure timezone-aware comparison
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    now = datetime.now(tz=timezone.utc)
    age: timedelta = now - dt

    if age <= timedelta(hours=24):
        return 20
    if age <= timedelta(days=3):
        return 16
    if age <= timedelta(days=7):
        return 12
    if age <= timedelta(days=14):
        return 8
    if age <= timedelta(days=30):
        return 4
    return 0


def _score_p4_company_relevance(
    title: str,
    description: str,
    company_name: Optional[str],
    ticker: Optional[str],
) -> int:
    """P4 — Company Name Relevance (max 20 pts)."""
    title_lower = title.lower()
    desc_lower = description.lower()

    scores: List[int] = []

    if company_name:
        # Use longest token of name for partial match (e.g., "tata consultancy")
        name_lower = company_name.lower().strip()
        # Try full name first, then first significant word (≥ 4 chars)
        tokens = [t for t in name_lower.split() if len(t) >= 4]
        match_str = name_lower if len(name_lower) > 3 else (tokens[0] if tokens else name_lower)

        if match_str in title_lower:
            scores.append(20)
        elif match_str in desc_lower:
            scores.append(10)

    if ticker:
        ticker_lower = ticker.lower()
        if ticker_lower in title_lower:
            scores.append(15)
        elif ticker_lower in desc_lower:
            scores.append(8)

    return max(scores) if scores else 0


def _detect_noise(combined_text: str) -> bool:
    """Returns True if any noise keyword is found in combined text."""
    return any(kw in combined_text for kw in NOISE_KEYWORDS)


def _classify_category(combined_text: str) -> str:
    """Return the first matching financial category, else 'Other'."""
    for category, keywords in CATEGORY_KEYWORDS:
        if any(kw in combined_text for kw in keywords):
            return category
    return "Other"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class FinancialNewsFilter:
    """
    Scores, classifies, and filters news articles for financial relevance.

    All public methods are static — instantiation is never required.
    """

    @staticmethod
    def score_and_classify(
        articles: List[Dict[str, Any]],
        company_name: Optional[str] = None,
        ticker: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Enrich each article dict with:
          - `financial_relevance_score` (int 0–100)
          - `financial_category`        (str)

        Original article keys are preserved unchanged.
        Returns the same list with articles mutated in-place.
        """
        for article in articles:
            title = _normalize(article.get("title"))
            description = _normalize(article.get("description"))
            source = article.get("source", "")
            published_at = article.get("publishedAt", "")
            combined = f"{title} {description}"

            p1, has_financial = _score_p1_keywords(combined)
            p2 = _score_p2_publisher(source)
            p3 = _score_p3_freshness(published_at)
            p4 = _score_p4_company_relevance(title, description, company_name, ticker)

            is_noisy = _detect_noise(combined)
            noise_penalty = 40 if (is_noisy and not has_financial) else 0

            raw_score = p1 + p2 + p3 + p4 - noise_penalty
            final_score = max(0, min(100, raw_score))

            category = _classify_category(combined)

            article["financial_relevance_score"] = final_score
            article["financial_category"] = category

            logger.debug(
                "Article scored | score=%d | p1=%d p2=%d p3=%d p4=%d "
                "noise=%d | category=%s | title=%.80s",
                final_score, p1, p2, p3, p4, noise_penalty, category,
                article.get("title", ""),
            )

        return articles

    @staticmethod
    def filter_and_rank(
        articles: List[Dict[str, Any]],
        company_name: Optional[str] = None,
        ticker: Optional[str] = None,
        top_n: int = 10,
        min_score: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Score, classify, filter (score ≥ min_score), and return the top-N
        articles sorted by `financial_relevance_score` descending.

        Args:
            articles:     Raw list of article dicts from any news provider.
            company_name: Optional company name for P4 relevance scoring.
            ticker:       Optional ticker symbol for P4 relevance scoring.
            top_n:        Maximum number of articles to return.
            min_score:    Minimum score threshold; articles below are dropped.

        Returns:
            Filtered, ranked list of article dicts (≤ top_n).
        """
        if not articles:
            return []

        FinancialNewsFilter.score_and_classify(articles, company_name, ticker)

        ranked = sorted(
            articles,
            key=lambda a: a.get("financial_relevance_score", 0),
            reverse=True,
        )

        filtered = [a for a in ranked if a.get("financial_relevance_score", 0) >= min_score]
        result = filtered[:top_n]

        logger.info(
            "FinancialNewsFilter | input=%d | passed_threshold=%d | returned=%d "
            "| min_score=%d | top_n=%d",
            len(articles), len(filtered), len(result), min_score, top_n,
        )

        return result
