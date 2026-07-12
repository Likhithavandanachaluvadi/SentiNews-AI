import feedparser
import logging

from urllib.parse import quote
from typing import List, Dict, Any
from email.utils import parsedate_to_datetime

logger = logging.getLogger(__name__)


class GoogleNewsService:

    @staticmethod
    async def fetch_news(company_name: str) -> List[Dict[str, Any]]:
        """
        Fetch news articles from Google News RSS.
        """

        try:
            encoded_company = quote(company_name)

            rss_url = (
                f"https://news.google.com/rss/search?q={encoded_company}"
                "&hl=en-IN&gl=IN&ceid=IN:en"
            )

            feed = feedparser.parse(rss_url)

            articles = []

            for entry in feed.entries:

                articles.append({
                    "title": entry.get("title", ""),
                    "description": entry.get("summary", ""),
                    "url": entry.get("link", ""),
                    "source": (
                        entry.get("source", {}).get("title", "Google News")
                        if isinstance(entry.get("source"), dict)
                        else "Google News"
                    ),
                    "publishedAt": (
                        parsedate_to_datetime(entry.get("published", "")).isoformat()
                        if entry.get("published")
                        else ""
                    ),
                    "provider": "Google News RSS",
                    "relevance_score": 0
                })

            logger.info(
                f"Fetched {len(articles)} Google News articles for {company_name}"
            )

            return articles

        except Exception as e:
            logger.exception(f"Google News RSS Error: {e}")
            return []