import os
import httpx

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

class FinnhubService:

    @staticmethod
    async def fetch_peers(symbol: str):
        if not FINNHUB_API_KEY:
            return []
        url = (
            f"https://finnhub.io/api/v1/stock/peers"
            f"?symbol={symbol}&token={FINNHUB_API_KEY}"
        )
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                if response.status_code == 200:
                    return response.json()
        except Exception:
            pass
        return []

    @staticmethod
    async def fetch_quote(symbol: str) -> dict:
        if not FINNHUB_API_KEY:
            return {}
        url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    return response.json()
        except Exception:
            pass
        return {}

    @staticmethod
    async def fetch_financials(symbol: str) -> dict:
        if not FINNHUB_API_KEY:
            return {}
        url = f"https://finnhub.io/api/v1/stock/metric?symbol={symbol}&metric=all&token={FINNHUB_API_KEY}"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    return response.json()
        except Exception:
            pass
        return {}