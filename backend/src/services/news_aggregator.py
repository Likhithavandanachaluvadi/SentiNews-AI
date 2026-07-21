import logging
from typing import List, Dict, Any

from datetime import datetime, timezone

# from src.services.news_service import fetch_news_for_ticker
from src.services.news_service import fetch_news_articles
from src.services.google_news_service import GoogleNewsService
from src.services.finnhub_news_service import FinnhubNewsService
from src.services.financial_news_filter import FinancialNewsFilter

logger = logging.getLogger(__name__)


class NewsAggregator:

    @staticmethod
    async def fetch_all_news(
        company_name: str,
        ticker: str | None = None,
    ) -> List[Any]:
        """
        Fetches, deduplicates, and financially ranks news articles.

        Pipeline:
          1. Collect from NewsAPI, Google News RSS, Finnhub
          2. Deduplicate by URL / title
          3. Apply 4-pillar FinancialNewsFilter scoring:
               P1 — Financial keyword quality  (max 40 pts)
               P2 — Publisher / source quality (max 20 pts)
               P3 — Article freshness          (max 20 pts)
               P4 — Company name relevance     (max 20 pts)
          4. Drop articles below min_score=20
          5. Return top 10 by financial_relevance_score
        """
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

        logger.info(f"Raw articles collected: {len(articles)}")

        # -------------------------------
        # Remove Duplicates
        # -------------------------------
        articles = NewsAggregator.remove_duplicates(articles)

        # -------------------------------
        # Financial Relevance Filtering
        # (scores, classifies, filters, and ranks)
        # -------------------------------
        articles = FinancialNewsFilter.filter_and_rank(
            articles,
            company_name=company_name,
            ticker=ticker,
            top_n=10,
            min_score=20,
        )

        logger.info(
            f"Articles after financial filter: {len(articles)}"
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