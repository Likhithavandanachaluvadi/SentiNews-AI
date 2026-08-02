"""
Dynamic Retrieval System for SentiNews Query Intelligence.

Replaces the static retriever node with an intent-aware data fetching strategy.

RETRIEVAL GATING BY INTENT:
  EDUCATIONAL          → No live API calls. Static knowledge only.
  RESTRICTED_ADVISORY  → No live API calls. Educational redirect only.
  STOCK_MOVEMENT       → Price + recent news ONLY (no financials scraping).
  SENTIMENT_PULSE      → News ONLY.
  MARKET_OVERVIEW      → Index + macro data ONLY.
  MACROECONOMIC        → Macro APIs only.
  STOCK_ANALYSIS       → Full data: yfinance + screener + news.
  COMPARISON           → Full data for EACH ticker.
  GENERALIZED          → Full data (safe default).

FRESHNESS POLICIES:
  MAX_NEWS_AGE_HOURS         = 24
  MAX_MARKET_DATA_AGE_MINS   = 15

SOURCE FILTERING:
  Blocks generic tech news (BBC, Wired, Verge, Gizmodo, TechCrunch, etc.)
  Only allows finance-specific sources or known financial publications.
"""

import logging
import json
import re

from datetime import datetime, timedelta, timezone
from multiprocessing import context
from pathlib import Path
from typing import Optional


from src.agents.retriever import extract_ticker
from src.services.market_data import get_enhanced_market_context
# from src.services.news_service import fetch_news_for_ticker
from src.services.news_aggregator import NewsAggregator
from src.services.source_ranker import SourceRanker
from src.agents.retrieval_policy import get_policy, RetrievalPolicy
from src.core.debug_logger import debug_logger

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------
# Freshness Constants
# -----------------------------------------------------------------------
MAX_NEWS_AGE_HOURS = 24
MAX_MARKET_DATA_AGE_MINS = 15

# -----------------------------------------------------------------------
# SOURCE FILTERING & VALIDATION
# -----------------------------------------------------------------------

BLOCKED_SOURCES = {
    # Generic tech news (BLOCKED)
    "bbc", "bbc news", "bbc.com", "bbc.co.uk",
    "wired", "wired.com",
    "verge", "theverge", "theverge.com",
    "gizmodo", "gizmodo.com",
    "techcrunch", "techcrunch.com",
    "engadget", "engadget.com",
    "ars technica", "arstechnica.com",
    "the next web", "thenextweb.com",
    "hacker news", "news.ycombinator.com",
    "reddit", "reddit.com",
    "twitter", "x.com", "twitter.com",
    "medium", "medium.com",
    "substack", "substack.com",
    # Entertainment (BLOCKED)
    "buzzfeed", "buzzfeed.com",
    "vox", "vox.com",
    "atlantic", "theatlantic.com",
    "vice", "vice.com",
    "variety", "variety.com",
    "hollywood reporter", "hollywoodreporter.com",
}

PREFERRED_FINANCE_SOURCES = {
    # Tier 1: Primary Financial Data
    "yfinance", "yahoo finance", "finance.yahoo.com",
    "screener.in", "screener",
    "nseindia", "bseindia", "nse india", "bse india",
    "rbi", "reserve bank of india",
    
    # Tier 2: Quality Financial Publishers
    "reuters", "reuters.com",
    "bloomberg", "bloomberg.com",
    "economic times", "economictimes.indiatimes.com",
    "business standard", "business-standard.com",
    "cnbc", "cnbc.com", "cnbc-tv18", "cnbctv18.com",
    "moneycontrol", "moneycontrol.com",
    "ticker.in",
    "bsense", "bsense.com",
    "hindu business line", "thehindubusinessline.com",
    
    # Tier 2.5: Quality Indian Business News
    "financial express", "financialexpress.com",
    "mint", "mint.com", "livemint.com",
    "indianexpress", "indianexpress.com",
    "theprint", "theprint.in",
    "firstpost", "firstpost.com",
    
    # Tier 3: Brokerage & Research
    "tradingview", "tradingview.com",
    "bsense", "tickertape", "tickertape.in",
    "stockedge", "stockedge.com",
}


def is_finance_relevant_source(source_name: str) -> bool:
    """
    Check if a source is finance-relevant and should be included.
    Blocks generic tech/entertainment news.
    Returns True if source is acceptable, False if blocked.
    """
    if not source_name:
        return False
    
    source_lower = source_name.lower().strip()
    
    # Hard block: Generic tech/entertainment
    for blocked in BLOCKED_SOURCES:
        if blocked in source_lower:
            logger.debug(f"BLOCKED source: {source_name}")
            return False
    
    # Prefer known finance sources
    for preferred in PREFERRED_FINANCE_SOURCES:
        if preferred in source_lower:
            logger.debug(f"PREFERRED source: {source_name}")
            return True
    
    # Allow if explicitly mentions finance keywords
    finance_keywords = [
        "stock", "market", "finance", "trading", "invest",
        "equity", "share", "nse", "bse", "ticker",
        "earnings", "quarterly", "revenue", "profit",
        "analyst", "rating", "recommendation",
    ]
    
    for keyword in finance_keywords:
        if keyword in source_lower:
            logger.debug(f"FINANCE KEYWORD match: {source_name}")
            return True
    
    # Default: reject unknown sources (safe default)
    logger.debug(f"REJECTED unknown source: {source_name}")
    return False


def is_blocked_source(source_name: str) -> bool:
    if not source_name:
        return False
    source_lower = source_name.lower().strip()
    return any(blocked in source_lower for blocked in BLOCKED_SOURCES)


def company_aliases_for_ticker(ticker: str) -> list[str]:
    aliases = [ticker.lower()] if ticker else []
    try:
        json_path = Path(__file__).resolve().parents[1] / "indian_tickers.json"
        if json_path.exists():
            with json_path.open("r", encoding="utf-8") as f:
                ticker_map = json.load(f)
            aliases.extend([name for name, symbol in ticker_map.items() if symbol == ticker.upper()])
    except Exception as exc:
        logger.debug(f"Could not load ticker aliases for {ticker}: {exc}")
    return [alias.lower() for alias in aliases if alias]

# ============================================================================
# Financial News Filtering
# ============================================================================

FINANCIAL_KEYWORDS = {
    "quarter",
    "quarterly",
    "earnings",
    "results",
    "revenue",
    "profit",
    "net profit",
    "ebitda",
    "margin",
    "dividend",
    "bonus",
    "buyback",
    "stock split",
    "rights issue",
    "acquisition",
    "merger",
    "contract",
    "order",
    "client",
    "deal",
    "guidance",
    "capex",
    "debt",
    "credit rating",
    "promoter",
    "shareholding",
    "fii",
    "dii",
    "insider",
    "rbi",
    "sebi",
    "ipo",
    "investment",
    "valuation",
    "target price",
    "upgrade",
    "downgrade"
}

BLOCKED_NEWS_KEYWORDS = {
    "traffic",
    "bengaluru traffic",
    "viral",
    "weather",
    "festival",
    "crime",
    "sports",
    "movie",
    "celebrity",
    "campus",
    "recruitment",
    "hiring",
    "social media",
    "marathon",
    "lifestyle",
    "opinion"
}

def filter_news_results(news_items: list[str], ticker: str) -> tuple[list[str], list[str]]:
    """
    Filter news results to:
    1. Remove generic tech news
    2. Ensure ticker relevance
    
    Returns: (filtered_news, blocked_sources_list)
    """
    filtered = []
    blocked = []
    aliases = company_aliases_for_ticker(ticker)
    
    for item in news_items:
        item_str = str(item).lower()
        
        source = extract_news_source(item)
        
        if is_blocked_source(source):
            blocked.append(source)
            logger.warning(f"Filtering out blocked source: {source}")
            continue
        
        # Stock analysis requires ticker, company-name, or trusted finance-source relevance.
        has_entity_match = any(alias in item_str for alias in aliases)
        has_finance_source = source and is_finance_relevant_source(source)
        if ticker and not has_entity_match and not has_finance_source:
            blocked.append(source or "entity_mismatch")
            logger.warning(f"Filtering out non-company-specific news item: {str(item)[:100]}")
            continue

        # -------------------------------------------------------
        # Financial relevance filtering
        # -------------------------------------------------------

        text = item_str

        if ticker and any(keyword in text for keyword in BLOCKED_NEWS_KEYWORDS):
            blocked.append(source or "non_financial")
            logger.info(f"Blocked non-financial news: {str(item)[:100]}")
            continue

        if ticker and not any(keyword in text for keyword in FINANCIAL_KEYWORDS):
            blocked.append(source or "low_financial_relevance")
            logger.info(f"Blocked low financial relevance news: {str(item)[:100]}")
            continue

        filtered.append(item)
    
    return filtered, blocked


def extract_news_source(item: str) -> str:
    """
    Extract the publisher from news_service chunks.

    Expected format:
      [YYYY-MM-DD] Moneycontrol - Headline: Description

    The text inside [] is the publication date, not the source.
    """
    item_str = str(item).strip()
    dated_match = re.match(r"^\[[^\]]+\]\s+(.+?)\s+-\s+", item_str)
    if dated_match:
        return dated_match.group(1).strip()

    undated_match = re.match(r"^(.+?)\s+-\s+", item_str)
    if undated_match:
        return undated_match.group(1).strip()

    return ""


# -----------------------------------------------------------------------
# Intent → Data fetch strategy map
# -----------------------------------------------------------------------
TICKERLESS_INTENTS = {"EDUCATIONAL", "SECTOR_OUTLOOK", "THEME_ANALYSIS", "MARKET_OVERVIEW"}

FETCH_STRATEGY = {
    # intent_key         : (fetch_market, fetch_financials, fetch_news)
    "STOCK_ANALYSIS":     (True,  True,  True),
    "STOCK_MOVEMENT":     (True,  False, True),
    "MARKET_OVERVIEW":    (True,  False, False),
    "MACROECONOMIC":      (False, False, False),   # uses macro_context node
    "SENTIMENT_PULSE":    (False, False, True),
    "EDUCATIONAL":        (False, False, False),   # zero live calls
    "COMPARISON":         (True,  True,  True),
    "RESTRICTED_ADVISORY":(False, False, False),   # immediate refusal
    "GENERALIZED":        (True,  True,  True),    # safe default: full data
}

# UI blocks per intent (drives frontend rendering)
UI_BLOCKS_MAP = {
    "STOCK_ANALYSIS":      ["ExecutiveSummary", "ConfidenceGauge", "FundamentalCard", "TechnicalCard", "SentimentCard", "ScenarioCards", "RiskFactors", "Citations"],
    "STOCK_MOVEMENT":      ["MovementDrivers", "NewsTimeline", "SentimentPulse"],
    "MARKET_OVERVIEW":     ["MarketTrends", "NewsHighlights"],
    "MACROECONOMIC":       ["MacroSummary", "PolicyImpact"],
    "SENTIMENT_PULSE":     ["SentimentPulse", "NewsTimeline"],
    "EDUCATIONAL":         ["EducationalExplainer", "Glossary"],
    "COMPARISON":          ["ComparisonTable", "FundamentalCard", "TechnicalCard"],
    "COMPANY_COMPARISON":  ["ComparisonTable", "FundamentalCard", "SentimentPulse"],
    "SECTOR_OUTLOOK":      ["SectorTrends", "MacroDrivers", "IndustryNews"],
    "THEME_ANALYSIS":      ["TechnologyTrends", "Adoption", "Research"],
    "RESTRICTED_ADVISORY": ["SafeRefusal", "EducationalRedirect"],
    "GENERALIZED":         ["ExecutiveSummary", "ConfidenceGauge", "FundamentalCard", "TechnicalCard", "SentimentCard", "Citations"],
}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _freshness_tag() -> str:
    return _now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")


def _news_search_term(query: str, primary_intent: str, ticker: Optional[str]) -> str:
    if ticker and primary_intent not in TICKERLESS_INTENTS:
        return ticker
    return query.strip()


def _debug_query_understanding(
    *,
    query: str,
    primary_intent: str,
    entity_type: str,
    ticker: Optional[str],
    policy: RetrievalPolicy,
) -> None:
    print(
        f"\n================================================\n"
        f"QUERY UNDERSTANDING\n"
        f"================================================\n"
        f"Query\n{query}\n"
        f"Intent\n{primary_intent}\n"
        f"Entity\n{entity_type}\n"
        f"Ticker\n{ticker or 'None'}\n"
        f"Routing\n{policy.pipeline}\n"
        f"Retrieval Policy\n{policy.description}\n"
        f"Modules Activated\n{', '.join(policy.modules) or 'None'}\n"
        f"Modules Skipped\n{', '.join(policy.skipped_modules) or 'None'}\n"
        f"================================================\n"
    )


async def _discover_theme_companies_async(query: str) -> list:
    """
    Dynamically discovers top companies matching a theme/sector query from company_master.
    Returns a list of dicts with company metadata (ticker, company_name, sector, industry, market_cap).
    """
    from src.database.session import async_session_factory
    from src.models.company_master import CompanyMaster
    from sqlalchemy import select, or_

    query_clean = query.lower().strip()
    stop_words = {
        "top", "best", "companies", "company", "stocks", "stock", "shares", "share",
        "in", "india", "indian", "sector", "industry", "theme", "analysis", "overview",
        "of", "the", "for", "and", "or", "to", "a", "an", "list", "leading", "major"
    }
    words = [w for w in re.findall(r'\b[a-z0-9]+\b', query_clean) if w not in stop_words and len(w) >= 2]
    if not words:
        return []

    try:
        async with async_session_factory() as session:
            filters = []
            for term in words:
                if term == "ai":
                    filters.append(CompanyMaster.industry.ilike("%software%"))
                    filters.append(CompanyMaster.industry.ilike("%technology%"))
                    filters.append(CompanyMaster.industry.ilike("%artificial%"))
                    filters.append(CompanyMaster.company_name.ilike("%ai %"))
                elif term == "ev":
                    filters.append(CompanyMaster.industry.ilike("%electric%"))
                    filters.append(CompanyMaster.industry.ilike("%auto%"))
                    filters.append(CompanyMaster.company_name.ilike("%ev %"))
                else:
                    filters.append(CompanyMaster.company_name.ilike(f"%{term}%"))
                    filters.append(CompanyMaster.industry.ilike(f"%{term}%"))
                    filters.append(CompanyMaster.sector.ilike(f"%{term}%"))

            stmt = (
                select(CompanyMaster)
                .where(or_(*filters))
                .order_by(CompanyMaster.market_cap.desc().nulls_last())
                .limit(5)
            )
            res = await session.execute(stmt)
            companies = res.scalars().all()

            results = []
            for c in companies:
                results.append({
                    "ticker": c.symbol,
                    "name": c.company_name,
                    "company_name": c.company_name,
                    "sector": c.sector or "Technology",
                    "industry": c.industry or "General",
                    "market_cap": f"₹{c.market_cap / 10000000:,.2f} Cr" if c.market_cap else "N/A",
                    "stock_pe": "N/A",
                    "roe": "N/A"
                })
            return results
    except Exception as e:
        logger.warning(f"Dynamic theme company discovery failed: {e}")
        return []


async def dynamic_retriever_node(state: dict) -> dict:
    """
    Intent-aware LangGraph node for data retrieval.
    
    CRITICAL FEATURE: Source filtering prevents generic tech news contamination.
    
    Reads `state['intent']` to decide WHAT data to fetch, then 
    populates `state['context']` and `state['data_freshness']`.
    
    Source filtering ensures:
    - BBC, Wired, Verge, Gizmodo, TechCrunch are BLOCKED
    - Only finance-specific sources are allowed
    - Ticker relevance is checked
    """
    intent = state.get("intent", {})
    primary_intent = intent.get("primary_intent", "GENERALIZED")
    extracted_ticker = intent.get("extracted_ticker")
    query = state.get("query", "")
    planner_layout = intent.get("planner_layout", {})
    required_ui_blocks = planner_layout.get("ui_blocks", [])

    # -----------------------------------------------------------------------
    # Sprint 2: Look up centralized RetrievalPolicy for this intent
    # -----------------------------------------------------------------------
    policy: RetrievalPolicy = get_policy(primary_intent)

    if primary_intent in TICKERLESS_INTENTS:
        extracted_ticker = None

    # -----------------------------------------------------------------------
    # Fast path: No live data needed (RESTRICTED_ADVISORY or pure EDUCATIONAL)
    # -----------------------------------------------------------------------
    if not policy.fetch_market and not policy.fetch_financials and not policy.fetch_news:
        logger.info(
            f"Intent={primary_intent} | policy='{policy.description}' | "
            "skipping all live API calls."
        )

        debug_logger.log_retrieval_operation(
            ticker="None",
            intent=primary_intent,
            sources_retrieved=0,
            data_types=[],
            execution_ms=0,
        )

        _debug_query_understanding(
            query=query,
            primary_intent=primary_intent,
            entity_type=primary_intent.replace("_", " ").title(),
            ticker=None,
            policy=policy,
        )

        return {
            "context": [],
            "ticker": None,
            "data_freshness": _freshness_tag(),
            "ui_blocks": required_ui_blocks or UI_BLOCKS_MAP.get(primary_intent, ["EducationalExplainer"]),
            "grounding_data": None,
        }

    # -----------------------------------------------------------------------
    # Resolve ticker
    # -----------------------------------------------------------------------
    ticker = None if primary_intent in TICKERLESS_INTENTS else (state.get("ticker") or extracted_ticker)
    if not ticker and policy.requires_ticker:
        ticker = extract_ticker(query)
    ticker = ticker.upper().strip() if ticker else None

    if policy.requires_ticker and not ticker:
        logger.info("Intent=%s requires a ticker, but none was resolved.", primary_intent)
        return {
            "context": [],
            "ticker": None,
            "news_articles": [],
            "data_freshness": _freshness_tag(),
            "ui_blocks": required_ui_blocks or UI_BLOCKS_MAP.get(primary_intent, UI_BLOCKS_MAP["GENERALIZED"]),
            "grounding_data": {},
            "prompt_context": "",
        }

    # Pre-retrieval Validation Layer
    from src.services.entity_resolver import EntityResolver, EntityResolutionError, log_entity_validation
    resolved_entities_dict = state.get("resolved_entities")
    req_ticker = None
    req_company = None
    if resolved_entities_dict:
        from src.services.entity_models import EntityCollection
        collection = EntityCollection.from_dict(resolved_entities_dict)
        if not collection.is_empty and collection.primary:
            req_ticker = collection.primary_ticker
            req_company = collection.primary.company_name
    elif ticker:
        req_ticker, req_company = EntityResolver.resolve_sync(query)
    if req_ticker and ticker != req_ticker:
        log_entity_validation(
            query=query,
            req_company=req_company or "Unknown",
            req_ticker=req_ticker,
            res_company=EntityResolver._ticker_to_company.get(ticker) or "Unknown",
            res_ticker=ticker,
            ret_company="N/A",
            ret_ticker="N/A",
            status="FAILED",
            reason="Ticker mismatch detected"
        )
        raise EntityResolutionError(
            f"EntityResolutionError: Requested ticker: {req_ticker}, but resolved ticker was: {ticker}."
        )
    elif req_ticker:
        log_entity_validation(
            query=query,
            req_company=req_company or "Unknown",
            req_ticker=req_ticker,
            res_company=EntityResolver._ticker_to_company.get(ticker) or "Unknown",
            res_ticker=ticker,
            ret_company="N/A",
            ret_ticker="N/A",
            status="PASS"
        )

    logger.info(
        f"Dynamic retriever | intent={primary_intent} | ticker={ticker} | "
        f"policy='{policy.description}'"
    )
    _debug_query_understanding(
        query=query,
        primary_intent=primary_intent,
        entity_type="Company" if ticker else primary_intent.replace("_", " ").title(),
        ticker=ticker,
        policy=policy,
    )

    # Resolve entity list for multi-entity intents (COMPARISON, PEER_COMPARISON)
    entity_collection_dict = intent.get("entity_collection")
    all_tickers: list[str] = [ticker] if ticker else []
    if policy.multi_entity and entity_collection_dict:
        from src.services.entity_models import EntityCollection
        ec = EntityCollection.from_dict(entity_collection_dict)
        if ec.is_multi:
            all_tickers = ec.all_tickers
            logger.info(
                f"Multi-entity mode | intents={primary_intent} | entities={all_tickers}"
            )

    # Fetch flags come from the policy (Sprint 2), not the planner required_data
    fetch_market = policy.fetch_market
    fetch_financials = policy.fetch_financials
    fetch_news = policy.fetch_news

    context: list[str] = []
    data_types_fetched = []
    total_sources = 0
    blocked_sources_list = []

    news_ctx = []
    ranked_news = []

    # -----------------------------------------------------------------------
    # Fetch market/financial data
    # -----------------------------------------------------------------------
    if fetch_market and ticker:
        try:
            market_ctx = await get_enhanced_market_context(ticker)
            context.extend(market_ctx)
            data_types_fetched.append("market_data")
            total_sources += len(market_ctx)
            logger.debug(f"Market context fetched: {len(market_ctx)} items")
        except Exception as e:
            logger.warning(f"Market data fetch failed for {ticker}: {e}")
            context.append(
                f"[DATA UNAVAILABLE] Live market data for {ticker} could not be retrieved. "
                "Confidence should be lowered accordingly."
            )

    # -----------------------------------------------------------------------
    # Fetch news with SOURCE FILTERING
    # -----------------------------------------------------------------------
    if fetch_news:
        try:
            news_query = _news_search_term(query, primary_intent, ticker)
            news_ctx = await NewsAggregator.fetch_all_news(news_query, ticker=ticker)

            # ===== STEP 1: SOURCE FILTERING =====
            filtered_news, blocked = filter_news_results(news_ctx, ticker or "")
            blocked_sources_list.extend(blocked)

            if blocked:
                logger.warning(
                    f"Blocked {len(blocked)} non-finance sources: {set(blocked)}"
                )

            # ===== STEP 2: FRESHNESS FILTER =====
            cutoff = _now_utc() - timedelta(hours=MAX_NEWS_AGE_HOURS)

            fresh_news = []
            stale_count = 0

            for article in filtered_news:

                published = str(article.get("publishedAt", ""))[:10]

                try:
                    if published:
                        item_day = datetime.strptime(
                            published,
                            "%Y-%m-%d"
                        ).date()

                        if item_day >= _now_utc().date():
                            fresh_news.append(article)

                        elif datetime.combine(
                            item_day,
                            datetime.min.time(),
                            tzinfo=timezone.utc
                        ) >= cutoff:
                            fresh_news.append(article)

                        else:
                            stale_count += 1
                    else:
                        fresh_news.append(article)

                except Exception:
                    fresh_news.append(article)

            if stale_count > 0:
                logger.info(
                    f"Filtered {stale_count} stale news items (older than {MAX_NEWS_AGE_HOURS}h)"
                )

            if not fresh_news and filtered_news:
                logger.warning(
                    f"All news for {ticker or news_query} is older than {MAX_NEWS_AGE_HOURS}h. Using most recent 3."
                )
                fresh_news = filtered_news[:3]

            # ===== STEP 3: SOURCE INTELLIGENCE RANKING (Sprint 3) =====
            # Score each article: Source Trust (40%) + Financial Relevance (30%)
            # + Freshness (20%) + Source Type Bonus (10%), then deduplicate.
            ranked_news = SourceRanker.rank(
                fresh_news,
                deduplicate=True,
                top_n=None,
            )

            # ===== STEP 4: Format ranked articles into LLM context strings =====
            # Evidence metadata (trust tier, source type, score) is embedded
            # in each context line so analysts can weight sources accordingly.
            formatted_news = SourceRanker.format_ranked_context(
                ranked_news,
                max_description_chars=200,
            )

            context.extend(formatted_news)

            data_types_fetched.append("news")
            total_sources += len(formatted_news)

            if ranked_news:
                scores = [a.get("evidence_score", 0) for a in ranked_news]
                avg_evidence = round(sum(scores) / len(scores))
                top_evidence = scores[0]
            else:
                avg_evidence = top_evidence = 0

            logger.info(
                f"News retrieval: "
                f"fetched={len(news_ctx)}, "
                f"finance_relevant={len(filtered_news)}, "
                f"fresh={len(fresh_news)}, "
                f"after_dedup={len(ranked_news)}, "
                f"top_evidence={top_evidence}, "
                f"avg_evidence={avg_evidence}, "
                f"blocked_sources={len(blocked)}"
            )

        except Exception as e:
            logger.error(f"News fetch failed for {ticker or query}: {e}")
            context.append(
                f"[DATA UNAVAILABLE] News context for {ticker or query} could not be retrieved at this moment."
            )

    # -----------------------------------------------------------------------
    # Sprint 2: Multi-entity news fetch (COMPARISON / PEER_COMPARISON)
    # -----------------------------------------------------------------------
    # For non-primary tickers, fetch news and merge into the shared context.
    if policy.multi_entity and len(all_tickers) > 1 and fetch_news:
        for extra_ticker in all_tickers[1:]:
            try:
                extra_news_raw = await NewsAggregator.fetch_all_news(extra_ticker)
                extra_filtered, _ = filter_news_results(extra_news_raw, extra_ticker)
                extra_ranked = SourceRanker.rank(
                    extra_filtered,
                    deduplicate=True,
                    top_n=policy.news_max_docs,
                )
                extra_formatted = SourceRanker.format_ranked_context(
                    extra_ranked, max_description_chars=200
                )
                context.extend(extra_formatted)
                total_sources += len(extra_formatted)
                ranked_news.extend(extra_ranked)
                logger.info(
                    f"Multi-entity news | ticker={extra_ticker} | "
                    f"fetched={len(extra_news_raw)} | ranked={len(extra_ranked)}"
                )
            except Exception as e:
                logger.warning(f"Multi-entity news fetch failed for {extra_ticker}: {e}")

    # -----------------------------------------------------------------------
    # Sprint 2: Context cap -- trim to policy.max_context_docs
    # -----------------------------------------------------------------------
    if policy.max_context_docs > 0 and len(context) > policy.max_context_docs:
        logger.info(
            f"Context cap applied | intent={primary_intent} | "
            f"before={len(context)} | cap={policy.max_context_docs}"
        )
        context = context[: policy.max_context_docs]

    # ===== DEBUG LOGGING =====
    debug_logger.log_retrieval_operation(
        ticker=ticker or "None",
        intent=primary_intent,
        sources_retrieved=total_sources,
        data_types=data_types_fetched,
        execution_ms=0,
        filtered_sources=[c[:50] for c in context[:3]],
        blocked_sources=blocked_sources_list[:5] if blocked_sources_list else None,
    )

    # Fetch structured grounding data (Phase 2)
    grounding_data = {}
    if ticker and ticker != "N/A":
        try:
            from src.services.market_data import get_grounding_data
            grounding_data = await get_grounding_data(ticker)
        except Exception as e:
            logger.error(f"Failed to fetch grounding data for {ticker}: {e}")
    elif primary_intent == "THEME_ANALYSIS":
        discovered_peers = await _discover_theme_companies_async(query)
        if discovered_peers:
            from src.agents.schemas import GroundingPeerItem
            peer_items = [
                GroundingPeerItem(
                    ticker=p["ticker"],
                    name=p["name"],
                    market_cap=p["market_cap"],
                    stock_pe=p.get("stock_pe", "N/A"),
                    roe=p.get("roe", "N/A")
                ) for p in discovered_peers
            ]
            grounding_data = {
                "ticker": None,
                "company_name": f"Theme: {query}",
                "peers": peer_items,
                "discovered_companies": [p["ticker"] for p in discovered_peers],
                "sector": query,
            }
            peer_context = ["TOP DISCOVERED THEME BENEFICIARIES:"]
            for p in discovered_peers:
                peer_context.append(f"- {p['name']} ({p['ticker']}): Industry={p['industry']}, Sector={p['sector']}, Market Cap={p['market_cap']}")
            context = peer_context + context

    # Generate unified prompt context using PromptContextBuilder
    from src.services.prompt_context_builder import PromptContextBuilder
    prompt_context = PromptContextBuilder.build(
        query=query,
        grounding_data=grounding_data,
        news_articles=news_ctx,
        retrieval_context=context
    )

    return {
        "context": context,
        "ticker": ticker,
        "news_articles": ranked_news,
        "data_freshness": _freshness_tag(),
        "ui_blocks": required_ui_blocks or UI_BLOCKS_MAP.get(
            primary_intent,
            UI_BLOCKS_MAP["GENERALIZED"]
        ),
        "grounding_data": grounding_data,
        "prompt_context": prompt_context,
    }
