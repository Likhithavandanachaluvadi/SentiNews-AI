import logging
from typing import List, Dict, Any

from datetime import datetime, timezone

# from src.services.news_service import fetch_news_for_ticker
from src.services.news_service import fetch_news_articles
from src.services.google_news_service import GoogleNewsService
from src.services.finnhub_news_service import FinnhubNewsService

logger = logging.getLogger(__name__)


class NewsAggregator:

    @staticmethod
    async def fetch_all_news(company_name: str) -> List[Any]:

        articles = []

        # -------------------------------
        # NewsAPI
        # -------------------------------
        try:
            newsapi_articles = await fetch_news_articles(company_name)
            articles.extend(newsapi_articles)
        except Exception as e:
            logger.exception(f"NewsAPI Error: {e}")

        # -------------------------------
        # Google News RSS
        # -------------------------------
        try:
            google_articles = await GoogleNewsService.fetch_news(company_name)
            articles.extend(google_articles)
        except Exception as e:
            logger.exception(f"Google News Error: {e}")

        # -------------------------------
        # Finnhub
        # -------------------------------
        try:
            finnhub_articles = await FinnhubNewsService.fetch_news(company_name)
            articles.extend(finnhub_articles)
        except Exception as e:
            logger.exception(f"Finnhub Error: {e}")

        # -------------------------------
        # Remove Duplicates
        # -------------------------------
        articles = NewsAggregator.remove_duplicates(articles)

        # -------------------------------
        # Sort by Date
        # -------------------------------
        articles = NewsAggregator.sort_by_date(articles)

        # -------------------------------
        # Keep Top 30
        # -------------------------------
        articles = articles[:5]

        logger.info(
            f"Total aggregated articles: {len(articles)}"
        )

        return articles

    @staticmethod
    def remove_duplicates(
            articles: List[Dict[str, Any]]
        ) -> List[Dict[str, Any]]:

            seen = set()
            unique = []

            for article in articles:

                key = (
                    article.get("url", "").strip().lower()
                    or article.get("title", "").strip().lower()
                )

                if key and key not in seen:
                    seen.add(key)
                    unique.append(article)

            return unique

    @staticmethod
    def sort_by_date(
        articles: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:

        return sorted(
            articles,
            key=lambda x: x.get("publishedAt", ""),
            reverse=True
        )