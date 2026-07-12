import httpx
import logging
from tenacity import retry, stop_after_attempt, wait_exponential
from typing import List, Dict, Any
from src.core.config import settings
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Basic rate limit and retry settings
# Retries up to 3 times, waiting exponentially between retries.
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def fetch_news_for_ticker(ticker: str) -> List[str]:
    """
    Fetches the latest news for a given ticker over the last 30 days.
    Returns a list of formatted strings for the LLM context.
    """
    if not settings.NEWS_API_KEY:
        logger.warning("NEWS_API_KEY is not set. Skipping real news fetch.")
        return [f"News context for {ticker}: API Key missing. Simulating news..."]

    # Calculate date 30 days ago for news search
    thirty_days_ago = (datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    # Attempt to do a reverse lookup on indian_tickers.json to find company name for better search precision
    company_name = ""
    import json
    from pathlib import Path
    json_path = Path(__file__).resolve().parents[1] / "indian_tickers.json"
    if json_path.exists():
        try:
            with json_path.open("r", encoding="utf-8") as f:
                ticker_map = json.load(f)
            matching_names = [k for k, v in ticker_map.items() if v == ticker.upper()]
            if matching_names:
                # Use the longest name version (e.g. "tata consultancy services")
                company_name = max(matching_names, key=len).title()
        except Exception:
            pass

    # Build search query: e.g. 'TCS OR "Tata Consultancy Services"'
    if company_name:
        search_query = f"{ticker} OR \"{company_name}\""
    else:
        search_query = ticker
        
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": search_query,
        "from": thirty_days_ago,
        "sortBy": "relevancy",
        "language": "en",
        "apiKey": settings.NEWS_API_KEY,
        "pageSize": 100  # Max 100 articles as per Master Prompt
    }
    
    context_chunks = []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            articles = data.get("articles", [])
            if not articles:
                return [f"No recent significant news found for {ticker} in the last 30 days."]
                
            for i, article in enumerate(articles, 1):
                date_pub = article.get("publishedAt", "")[:10]
                title = article.get("title", "No Title")
                desc = article.get("description", "No Description")
                source = article.get("source", {}).get("name", "Unknown Source")
                
                chunk = f"[{date_pub}] {source} - {title}: {desc}"
                context_chunks.append(chunk)
                
            return context_chunks
            
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error occurred while fetching news for {ticker}: {e.response.status_code}")
        # Re-raise to trigger tenacity retry
        raise
    except httpx.RequestError as e:
        logger.error(f"Request error occurred while fetching news for {ticker}: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in news_service: {e}")
        return [f"Error fetching news for {ticker}."]
async def fetch_news_articles(ticker: str) -> List[Dict[str, Any]]:
    """
    Fetches the latest news articles for a given ticker over the last 30 days.
    Returns a list of article dictionaries with relevant fields.
    """
    if not settings.NEWS_API_KEY:
        logger.warning("NEWS_API_KEY is not set. Skipping real news fetch.")
        # return [{"title": f"News context for {ticker}: API Key missing. Simulating news..."}]
        return []
    
    # Calculate date 30 days ago for news search
    thirty_days_ago = (datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    # Attempt to do a reverse lookup on indian_tickers.json to find company name for better search precision
    company_name = ""
    import json
    from pathlib import Path
    json_path = Path(__file__).resolve().parents[1] / "indian_tickers.json"
    if json_path.exists():
        try:
            with json_path.open("r", encoding="utf-8") as f:
                ticker_map = json.load(f)
            matching_names = [k for k, v in ticker_map.items() if v == ticker.upper()]
            if matching_names:
                # Use the longest name version (e.g. "tata consultancy services")
                company_name = max(matching_names, key=len).title()
        except Exception:
            pass

    # Build search query: e.g. 'TCS OR "Tata Consultancy Services"'
    if company_name:
        search_query = f"{ticker} OR \"{company_name}\""
    else:
        search_query = ticker
        
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": search_query,
        "from": thirty_days_ago,
        "sortBy": "relevancy",
        "language": "en",
        "apiKey": settings.NEWS_API_KEY,
        "pageSize": 100  # Max 100 articles as per Master Prompt
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            articles = data.get("articles", [])
            if not articles:
                # return [{"title": f"No recent significant news found for {ticker} in the last 30 days."}]
                return []
            formatted_articles = []
            for article in articles:
                formatted_articles.append({
                    "title": article.get("title", "No Title"),
                    "description": article.get("description", "No Description"),
                    "url": article.get("url", ""),
                    "source": article.get("source", {}).get("name", "Unknown Source"),
                    "publishedAt": article.get("publishedAt", ""),
                    "provider": "NewsAPI",
                    "relevance_score": 0
                })
            return formatted_articles
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error occurred while fetching news for {ticker}: {e.response.status_code}")
        # Re-raise to trigger tenacity retry
        raise
    except httpx.RequestError as e:
        logger.error(f"Request error occurred while fetching news for {ticker}: {e}")
        raise   
    except Exception as e:
        logger.error(f"Unexpected error in fetch_news_articles: {e}")
        return []