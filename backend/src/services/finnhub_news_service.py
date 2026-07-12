import logging
import httpx

from typing import List, Dict, Any
from src.core.config import settings
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class FinnhubNewsService:

    @staticmethod
    async def fetch_news(company_name: str) -> List[Dict[str, Any]]:

        try:

            url = "https://finnhub.io/api/v1/company-news"

            params = {
                "symbol": company_name,
                "from": "2026-01-01",
                "to": "2026-12-31",
                "token": settings.FINNHUB_API_KEY
            }

            async with httpx.AsyncClient(timeout=20) as client:

                response = await client.get(
                    url,
                    params=params
                )

                response.raise_for_status()

                data = response.json()

            articles = []

            for article in data:

                articles.append({
                    "title": article.get("headline", ""),
                    "description": article.get("summary", ""),
                    "url": article.get("url", ""),
                    "source": article.get("source", "Finnhub"),
                    "publishedAt": datetime.fromtimestamp(
                        article.get("datetime", 0),
                        tz=timezone.utc
                    ).isoformat(),
                    "provider": "Finnhub",
                    "relevance_score": 0
                })

            logger.info(
                f"Fetched {len(articles)} Finnhub articles for {company_name}"
            )

            return articles

        except Exception as e:

            logger.exception(
                f"Finnhub Error: {e}"
            )

            return []