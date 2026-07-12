"""
Indian Stock Market Retriever Node for SentiNews AI.
Handles intelligent ticker extraction from free-form user queries,
supporting NSE/BSE tickers, company names, and casual language.
Integrates yfinance + screener.com for comprehensive market data.
"""
from src.agents.state import ResearchState
from src.services.market_data import get_enhanced_market_context
# from src.services.news_service import fetch_news_for_ticker
from src.services.news_aggregator import NewsAggregator
import logging
import re

logger = logging.getLogger(__name__)

# Action/analysis keywords to strip from user queries
INTENT_KEYWORDS = [
    "analyse", "analyze", "tell me about", "give me analysis of",
    "research", "look up", "check", "study", "report on",
    "what about", "how is", "how are", "what is", "what are",
    "should i buy", "is it a good buy", "should i invest in",
    "news about", "news on", "latest on", "update on",
    "overview of", "analysis on", "fundamentals of",
    "stock of", "shares of", "share price of", "stock price of",
    "the company", "this company", "the stock", "future of",
    "growth of", "prospects of", "outlook for",
]

def resolve_ticker_via_yf(query: str) -> str:
    """
    Query Yahoo Finance Search API to dynamically find matching Indian tickers.
    Returns the ticker symbol without suffix (e.g. ZOMATO) if found, otherwise empty.
    """
    import urllib.request
    import json
    import urllib.parse
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    url = f"https://query1.finance.yahoo.com/v1/finance/search?q={urllib.parse.quote(query)}&quotesCount=5&newsCount=0"
    
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            for q in data.get("quotes", []):
                symbol = q.get("symbol", "").upper()
                # We specifically look for Indian stock symbols ending with .NS or .BO
                if symbol.endswith(".NS") or symbol.endswith(".BO"):
                    base_ticker = symbol.split(".")[0]
                    logger.info(f"YF Search API resolved '{query}' to Indian symbol '{symbol}' -> '{base_ticker}'")
                    return base_ticker
                # If US stock symbol (no dots, e.g. NVDA, AAPL)
                if symbol.isalpha() and len(symbol) <= 5:
                    logger.info(f"YF Search API resolved '{query}' to US symbol '{symbol}'")
                    return symbol
    except Exception as e:
        logger.warning(f"Yahoo Finance search failed for '{query}': {e}")
    return ""

def extract_ticker(query: str) -> str:
    """
    Robust Indian market ticker extractor.
    1. Loads full Nifty 500 mapping from local JSON (indian_tickers.json).
    2. Uses Yahoo Finance Search API fallback for dynamic lookup of any other BSE/NSE stock.
    3. Trims intent words and converts casing.
    """
    import json
    from pathlib import Path
    
    original_query = query.strip()
    query_lower = original_query.lower()

    # Step 1: Strip intent/action words from the query
    cleaned = query_lower
    for kw in sorted(INTENT_KEYWORDS, key=len, reverse=True):
        cleaned = cleaned.replace(kw, "").strip()
    cleaned = cleaned.strip(" ?.,!")

    # Step 2: Try mapping using the downloaded Nifty 500 JSON list
    json_path = Path(__file__).resolve().parents[1] / "indian_tickers.json"
    if json_path.exists():
        try:
            with json_path.open("r", encoding="utf-8") as f:
                ticker_map = json.load(f)
            
            # Check for exact matches first
            if cleaned in ticker_map:
                logger.info(f"Nifty 500 JSON matched: '{cleaned}' -> {ticker_map[cleaned]}")
                return ticker_map[cleaned]
                
            # Check for partial matches using tokenized word intersection
            noise_words = {
                "limited", "ltd", "company", "corporation", "corp", "industries", "ind",
                "group", "and", "of", "for", "the", "services", "systems", "technologies",
                "india", "limited,", "ltd,", "recommendation", "recommend", "records", "record"
            }
            query_words = {w for w in cleaned.lower().split() if w not in noise_words}
            
            if query_words:
                for name_key, symbol in ticker_map.items():
                    name_words = {w for w in name_key.lower().split() if w not in noise_words}
                    if query_words.intersection(name_words):
                        logger.info(f"Nifty 500 JSON token match: '{name_key}' -> {symbol}")
                        return symbol
        except Exception as e:
            logger.warning(f"Failed to read indian_tickers.json: {e}")

    # Step 3: Call Yahoo Finance Search API dynamically for any BSE/NSE stock
    if cleaned:
        yf_resolved = resolve_ticker_via_yf(cleaned)
        if yf_resolved:
            return yf_resolved

    # Step 4: Try finding an all-caps ticker in the original query
    match = re.search(r'\b[A-Z][A-Z0-9&\-]{1,14}\b', original_query)
    if match:
        candidate = match.group(0)
        skip_words = {"THE", "IS", "AND", "FOR", "OF", "IN", "TO", "A", "AN", "AT", "BY"}
        if candidate not in skip_words:
            logger.info(f"Regex caps match fallback: {candidate}")
            return candidate

    # Step 5: Cleaned fallback
    if cleaned:
        return cleaned.upper().split()[0] if cleaned.split() else "NIFTY"

    return "NIFTY"



async def retriever_node(state: ResearchState) -> dict:
    """
    Retrieves comprehensive context for the given query using:
    - yfinance: Real live market data
    - screener.com: Institutional metrics
    - NewsAPI: Latest news sentiment
    
    Uses NSE ticker suffix (.NS) for yfinance Indian stock lookup.
    """
    query = state["query"]
    # Use ticker from state if already resolved (set by analysis.py), else extract
    ticker = state.get("ticker") or extract_ticker(query)
    logger.info(f"Retriever running for ticker: {ticker}")

    # Fetch Enhanced Market Context (yfinance + screener.com)
    market_context = await get_enhanced_market_context(ticker)

    # Fetch News with graceful fallback
    try:
        news_context = await NewsAggregator.fetch_all_news(ticker)

        formatted_news = []

        for article in news_context[:4]:
            formatted_news.append(
                f"[{str(article.get('publishedAt', ''))[:10]}] "
                f"{article.get('source', 'Unknown')}: "
                f"{article.get('title', 'No Title')} - "
                f"{article.get('description', '')[:100]}"
            )

        news_context = formatted_news

        context = market_context + news_context
    except Exception as e:
        logger.error(f"Failed to fetch news for {ticker}: {e}")
        news_context = [f"Note: News context for '{ticker}' could not be retrieved at this moment."]

    context = market_context + news_context
    return {"context": context, "ticker": ticker}
