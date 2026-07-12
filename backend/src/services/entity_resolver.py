import json
import logging
import re
import difflib
import asyncio
from pathlib import Path
from typing import Tuple, Optional, Dict, List

logger = logging.getLogger(__name__)

class EntityResolutionError(ValueError):
    pass

class TickerMismatchError(ValueError):
    pass

# Unavoidable legacy edge cases
LEGACY_EDGE_CASES = {
    "google": "GOOGL",
    "googl": "GOOGL",
    "goog": "GOOGL",
    "alphabet": "GOOGL",
    "tesla": "TSLA",
    "tsla": "TSLA",
    "sbi": "SBIN",
}

def log_entity_validation(query: str, req_company: str, req_ticker: str, res_company: str, res_ticker: str, ret_company: str, ret_ticker: str, status: str, reason: str = "", provider: str = "EntityResolver"):
    from datetime import datetime
    log_msg = (
        f"\nENTITY VALIDATION\n"
        f"Requested Query: {query}\n"
        f"Requested Company: {req_company}\n"
        f"Requested Ticker: {req_ticker}\n"
        f"Resolved Company: {res_company}\n"
        f"Resolved Ticker: {res_ticker}\n"
        f"Retrieved Company: {ret_company}\n"
        f"Retrieved Ticker: {ret_ticker}\n"
        f"Validation Result: {status}\n"
        f"Reason: {reason or 'N/A'}\n"
        f"Action: {'Analysis aborted' if status == 'FAILED' else 'Proceed'}\n"
        f"Timestamp: {datetime.utcnow().isoformat()}\n"
        f"Provider: {provider}\n"
    )
    print(log_msg)
    if status == "FAILED":
        logger.error(log_msg)
    else:
        logger.info(log_msg)


def clean_company_name(name: str) -> str:
    """Clean corporate suffixes from company names for robust matching."""
    name_lower = name.lower().strip()
    cleaned = re.sub(
        r'\b(corp|corporation|limited|ltd|inc|incorporated|plc|co|company|private|pvt)\b\.?',
        '', name_lower, flags=re.IGNORECASE
    )
    return re.sub(r'[\s,.\-]+$', '', cleaned).strip()


class EntityResolver:
    _ticker_to_company: Dict[str, str] = {}
    _company_to_ticker: Dict[str, str] = {}
    _db_loaded: bool = False
    _sync_loaded: bool = False

    @classmethod
    def initialize_sync(cls):
        if cls._sync_loaded:
            return
        
        # Load legacy edge cases
        for name, sym in LEGACY_EDGE_CASES.items():
            if sym == "GOOGL":
                company_name = "Alphabet Inc."
            elif sym == "TSLA":
                company_name = "Tesla, Inc."
            else:
                company_name = "State Bank of India"
            cls._ticker_to_company[sym] = company_name
            cls._company_to_ticker[name] = sym

        # Load from indian_tickers.json as a seed baseline
        try:
            json_path = Path(__file__).resolve().parents[1] / "indian_tickers.json"
            if json_path.exists():
                with json_path.open("r", encoding="utf-8") as f:
                    ticker_map = json.load(f)
                for company_name, ticker in ticker_map.items():
                    sym = ticker.upper().strip()
                    cls._ticker_to_company[sym] = company_name
                    cls._company_to_ticker[company_name.lower().strip()] = sym
        except Exception as e:
            logger.warning(f"EntityResolver seed load error: {e}")
        cls._sync_loaded = True

    @classmethod
    async def initialize_async(cls, force_reload: bool = False):
        cls.initialize_sync()
        if cls._db_loaded and not force_reload:
            return
        
        # Load from CompanyMaster database (Primary)
        try:
            from sqlalchemy import select
            from src.models.company_master import CompanyMaster
            from src.database.session import async_session_factory

            async with async_session_factory() as session:
                result = await session.execute(select(CompanyMaster))
                companies = result.scalars().all()
                for c in companies:
                    sym = c.symbol.upper().strip()
                    cls._ticker_to_company[sym] = c.company_name
                    cls._company_to_ticker[c.company_name.lower().strip()] = sym
            cls._db_loaded = True
            logger.info(f"EntityResolver: Preloaded {len(companies)} companies from database.")
        except Exception as e:
            logger.warning(f"Could not load from CompanyMaster DB: {e}")

    @classmethod
    def resolve_sync(cls, query: str, raise_on_fail: bool = False) -> Tuple[Optional[str], Optional[str]]:
        """Synchronous resolver using the cache populated from DB & JSON files."""
        cls.initialize_sync()
        from src.services.entity_resolution_pipeline import EntityResolutionPipeline
        collection = EntityResolutionPipeline.resolve_entities_sync(query)
        if collection.entities:
            return collection.primary_ticker, collection.primary.company_name

        if raise_on_fail:
            query_lower = query.lower().strip()
            stock_keywords = ["stock", "share", "company", "invest", "buy", "sell", "dividend", "pe ratio", "price"]
            if any(kw in query_lower for kw in stock_keywords):
                raise EntityResolutionError(
                    f"EntityResolutionError: Unable to resolve stock or company for query '{query}'."
                )

        return None, None

    @classmethod
    async def resolve(cls, query: str, raise_on_fail: bool = False) -> Tuple[Optional[str], Optional[str]]:
        """Asynchronous resolver with dynamic database updates and Yahoo Search integration."""
        await cls.initialize_async()
        from src.services.entity_resolution_pipeline import EntityResolutionPipeline
        collection = await EntityResolutionPipeline.resolve_entities(query)
        if collection.entities:
            return collection.primary_ticker, collection.primary.company_name

        if raise_on_fail:
            query_lower = query.lower().strip()
            stock_keywords = ["stock", "share", "company", "invest", "buy", "sell", "dividend", "pe ratio", "price"]
            if any(kw in query_lower for kw in stock_keywords):
                raise EntityResolutionError(
                    f"EntityResolutionError: Unable to resolve stock or company for query '{query}'."
                )

        return None, None

    @classmethod
    def _extract_candidate_search_term(cls, query: str) -> Optional[str]:
        cleaned = query.strip()
        cleaned = re.sub(
            r'^(is|should i buy|should i invest in|what is|outlook for|evaluate|analyze|tell me about|how is|price of)\b',
            '', cleaned, flags=re.IGNORECASE
        ).strip()
        cleaned = re.sub(
            r'\b(stock|share|shares|investment|financials|fundamentals|technical|news|analysis|report|a good buy|overvalued|undervalued|today)\b',
            '', cleaned, flags=re.IGNORECASE
        ).strip()
        
        cleaned = re.sub(r'[^\w\s&.\-]', '', cleaned).strip()
        words = cleaned.split()
        if len(words) > 0:
            return " ".join(words[:4])
        return None

    @classmethod
    async def _search_yahoo_finance_async(cls, query_term: str) -> Optional[dict]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, cls._search_yahoo_finance_sync, query_term)

    @classmethod
    def _search_yahoo_finance_sync(cls, query_term: str) -> Optional[dict]:
        import urllib.request
        import urllib.parse
        import json
        try:
            url = f"https://query2.finance.yahoo.com/v1/finance/search?q={urllib.parse.quote(query_term)}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                quotes = res_data.get("quotes", [])
                for q in quotes:
                    if q.get("quoteType") == "EQUITY":
                        symbol = q.get("symbol", "")
                        symbol_base = symbol.split(".")[0].upper().strip()
                        return {
                            "symbol": symbol_base,
                            "company_name": q.get("longname") or q.get("shortname") or symbol_base,
                            "industry": q.get("industry") or "N/A",
                            "sector": q.get("sector") or "N/A"
                        }
        except Exception as e:
            logger.warning(f"Yahoo Search sync failed for '{query_term}': {e}")
        return None

    @classmethod
    async def _persist_new_company(cls, symbol: str, company_name: str, industry: Optional[str] = None, sector: Optional[str] = None, market_cap: Optional[int] = None):
        try:
            from sqlalchemy.dialects.postgresql import insert
            from src.models.company_master import CompanyMaster
            from src.database.session import async_session_factory

            async with async_session_factory() as session:
                stmt = insert(CompanyMaster).values(
                    symbol=symbol.upper(),
                    company_name=company_name,
                    industry=industry,
                    sector=sector,
                    market_cap=market_cap
                ).on_conflict_do_update(
                    index_elements=[CompanyMaster.symbol],
                    set_={
                        "company_name": company_name,
                        "industry": industry,
                        "sector": sector,
                        "market_cap": market_cap
                    }
                )
                await session.execute(stmt)
                await session.commit()
            logger.info(f"EntityResolver: Persisted newly discovered company {symbol} -> {company_name}")
        except Exception as e:
            logger.warning(f"EntityResolver: Failed to persist new company {symbol} to DB: {e}")
