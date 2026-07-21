"""
Source Intelligence & Evidence Ranking -- Sprint 3
===================================================

Standalone SourceRanker that assigns a composite Evidence Score (0-100) to
every retrieved article before it reaches the LLM analysts.

Four scoring pillars:

  S1 -- Source Trust          (max 40 pts, weight 40%)
  S2 -- Financial Relevance   (max 30 pts, weight 30%)  <- reuses Sprint 1 score
  S3 -- Freshness             (max 20 pts, weight 20%)
  S4 -- Source Type Bonus     (max 10 pts, weight 10%)

  evidence_score = clamp(S1 + S2 + S3 + S4, 0, 100)

After scoring, articles are:
  1. Sorted by evidence_score descending
  2. Deduplicated (same event -> keep highest-scored copy only)

All original article keys are preserved. Four new keys are added:
  - evidence_score          (int)
  - trust_score             (int)   S1 contribution
  - source_type             (str)
  - source_tier_label       (str)

Publisher trust config lives exclusively in source_trust_config.py.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from src.services.source_trust_config import (
    SOURCE_TYPE_REGISTRY,
    SourceTypeConfig,
    DEFAULT_TRUST_SCORE,
    resolve_publisher_tier,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalize(text: Optional[str]) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.lower().strip())


def _parse_published_at(published_at: Optional[str]) -> Optional[datetime]:
    if not published_at:
        return None
    try:
        ts = published_at.replace("Z", "+00:00")
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def _normalize_title_for_dedup(title: str) -> frozenset:
    """
    Tokenise a title for near-duplicate detection.
    Returns a frozenset of significant words (length >= 4, non-stopword).
    """
    STOPWORDS = {
        "the", "and", "for", "with", "from", "that", "this", "have", "will",
        "been", "were", "they", "their", "what", "when", "where", "which",
        "into", "more", "also", "amid", "over", "after", "says", "said",
        "its", "amid", "after", "about", "just", "than", "then", "some",
    }
    words = re.findall(r"[a-z]{4,}", title.lower())
    return frozenset(w for w in words if w not in STOPWORDS)


# ---------------------------------------------------------------------------
# Pillar scoring
# ---------------------------------------------------------------------------

def _score_s1_trust(source: Optional[str]) -> Tuple[int, str, str]:
    """
    S1 -- Source Trust (max 40 pts).
    Returns (score, tier_label, matched_token).
    """
    tier = resolve_publisher_tier(source)
    if tier:
        return tier.score, tier.label, ""
    return DEFAULT_TRUST_SCORE, "Unknown/Blog", ""


def _score_s2_financial_relevance(article: Dict[str, Any]) -> int:
    """
    S2 -- Financial Relevance (max 30 pts).
    Reuses financial_relevance_score from Sprint 1 (0-100) scaled to 30.
    If Sprint 1 filter has not run, defaults to 15 (neutral).
    """
    raw = article.get("financial_relevance_score")
    if raw is None:
        return 15
    return round((raw / 100) * 30)


def _score_s3_freshness(published_at: Optional[str]) -> int:
    """S3 -- Freshness (max 20 pts)."""
    dt = _parse_published_at(published_at)
    if dt is None:
        return 0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    age = datetime.now(tz=timezone.utc) - dt
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


def _detect_source_type(article: Dict[str, Any]) -> SourceTypeConfig:
    """
    Detect source type from URL + title + description.
    Iterates SOURCE_TYPE_REGISTRY in priority order (highest bonus first).
    Falls back to 'News Article' if nothing matches.
    """
    url = _normalize(article.get("url", ""))
    title = _normalize(article.get("title", ""))
    desc = _normalize(article.get("description", ""))
    combined_text = f"{title} {desc}"

    sorted_registry = sorted(SOURCE_TYPE_REGISTRY, key=lambda c: c.bonus, reverse=True)

    for config in sorted_registry:
        if config.type_name == "News Article":
            continue
        if any(tok in url for tok in config.url_tokens):
            return config
        if any(tok in combined_text for tok in config.title_tokens):
            return config

    for config in SOURCE_TYPE_REGISTRY:
        if config.type_name == "News Article":
            return config

    return SourceTypeConfig(type_name="Unknown", bonus=1)


def _score_s4_source_type(article: Dict[str, Any]) -> Tuple[int, str]:
    """S4 -- Source Type Bonus (max 10 pts). Returns (bonus, type_name)."""
    cfg = _detect_source_type(article)
    return cfg.bonus, cfg.type_name


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _deduplicate(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove near-duplicate articles (same event, multiple sources).

    Strategy: Jaccard similarity on stopword-filtered title tokens.
    Threshold >= 0.65 -> duplicate; keep highest evidence_score.
    Genuinely different articles (Jaccard < 0.65) both survive.
    """
    SIMILARITY_THRESHOLD = 0.65

    kept: List[Dict[str, Any]] = []
    kept_fingerprints: List[frozenset] = []

    for article in articles:
        fp = _normalize_title_for_dedup(article.get("title", ""))

        if not fp:
            kept.append(article)
            kept_fingerprints.append(fp)
            continue

        is_duplicate = False
        for i, existing_fp in enumerate(kept_fingerprints):
            if not existing_fp:
                continue
            intersection = len(fp & existing_fp)
            union = len(fp | existing_fp)
            if union == 0:
                continue
            jaccard = intersection / union
            if jaccard >= SIMILARITY_THRESHOLD:
                existing_score = kept[i].get("evidence_score", 0)
                current_score = article.get("evidence_score", 0)
                if current_score > existing_score:
                    kept[i] = article
                    kept_fingerprints[i] = fp
                is_duplicate = True
                break

        if not is_duplicate:
            kept.append(article)
            kept_fingerprints.append(fp)

    return kept


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class SourceRanker:
    """
    Evaluates every retrieved article on source trust, financial relevance,
    freshness, and source type -- then ranks and deduplicates.

    All public methods are static. No instantiation needed.
    """

    @staticmethod
    def score(article: Dict[str, Any]) -> Dict[str, Any]:
        """
        Score a single article and enrich it with evidence metadata.

        Adds keys (preserves all originals):
          evidence_score      int   0-100
          trust_score         int   S1 contribution (0-40)
          source_type         str
          source_tier_label   str
          _s2_relevance       int   (internal, for debug)
          _s3_freshness       int   (internal, for debug)
        """
        source = article.get("source", "")
        published_at = article.get("publishedAt", "")

        s1, tier_label, _ = _score_s1_trust(source)
        s2 = _score_s2_financial_relevance(article)
        s3 = _score_s3_freshness(published_at)
        s4, source_type = _score_s4_source_type(article)

        raw = s1 + s2 + s3 + s4
        evidence_score = max(0, min(100, raw))

        article["evidence_score"] = evidence_score
        article["trust_score"] = s1
        article["source_type"] = source_type
        article["source_tier_label"] = tier_label
        article["_s2_relevance"] = s2
        article["_s3_freshness"] = s3

        logger.debug(
            "SourceRanker | score=%d | s1=%d(%s) s2=%d s3=%d s4=%d(%s) | title=%.80s",
            evidence_score, s1, tier_label, s2, s3, s4, source_type,
            article.get("title", ""),
        )

        return article

    @staticmethod
    def rank(
        articles: List[Dict[str, Any]],
        deduplicate: bool = True,
        top_n: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Score all articles, optionally deduplicate, sort by evidence_score desc,
        and return the top-N.
        """
        if not articles:
            return []

        for article in articles:
            SourceRanker.score(article)

        ranked = sorted(
            articles,
            key=lambda a: a.get("evidence_score", 0),
            reverse=True,
        )

        if deduplicate:
            ranked = _deduplicate(ranked)
            logger.info(
                "SourceRanker dedup | before=%d after=%d",
                len(articles), len(ranked),
            )

        result = ranked[:top_n] if top_n is not None else ranked

        logger.info(
            "SourceRanker | scored=%d | after_dedup=%d | returned=%d | "
            "top_score=%d | bottom_score=%d",
            len(articles),
            len(ranked),
            len(result),
            result[0].get("evidence_score", 0) if result else 0,
            result[-1].get("evidence_score", 0) if result else 0,
        )

        return result

    @staticmethod
    def format_ranked_context(
        articles: List[Dict[str, Any]],
        max_description_chars: int = 200,
    ) -> List[str]:
        """
        Convert already-scored+ranked articles into LLM context strings.

        Format:
          [YYYY-MM-DD] Source (Type | Trust=NN | Evidence=NN) -- Title
          Description snippet...
        """
        lines = []
        for article in articles:
            date = str(article.get("publishedAt", ""))[:10]
            source = article.get("source", "Unknown")
            title = article.get("title", "No Title")
            desc = article.get("description", "")[:max_description_chars]
            src_type = article.get("source_type", "News Article")
            evidence = article.get("evidence_score", 0)
            trust = article.get("trust_score", 0)

            lines.append(
                f"[{date}] {source} ({src_type} | Trust={trust} | Evidence={evidence}) -- {title}\n"
                f"{desc}"
            )
        return lines
