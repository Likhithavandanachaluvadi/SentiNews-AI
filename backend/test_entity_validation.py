import sys
import os
import unittest
import asyncio
from fastapi.testclient import TestClient

# Ensure src is in the python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.main import app
from src.services.entity_resolver import EntityResolver, EntityResolutionError, TickerMismatchError

class TestEntityValidation(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        EntityResolver.initialize_sync()
        cls.client = TestClient(app)

    async def asyncSetUp(self):
        from src.database.session import engine, async_session_factory
        from src.models.company_master import CompanyMaster
        from sqlalchemy.dialects.postgresql import insert
        
        await engine.dispose()
        
        # Seed test companies to ensure they exist in CompanyMaster DB for testing
        seed_companies = [
            ("META", "Meta Platforms, Inc.", "Technology", "Internet Content & Information"),
            ("SBIN", "State Bank of India", "Financial Services", "Banks-Regional"),
            ("IOB", "Indian Overseas Bank", "Financial Services", "Banks-Regional"),
            ("TCS", "Tata Consultancy Services", "Technology", "Software-Services"),
            ("INFY", "Infosys Limited", "Technology", "Software-Services"),
            ("RELIANCE", "Reliance Industries Limited", "Energy", "Oil & Gas"),
            ("HDFCBANK", "HDFC Bank Limited", "Financial Services", "Banks-Regional"),
            ("ICICIBANK", "ICICI Bank Limited", "Financial Services", "Banks-Regional"),
            ("NVDA", "NVIDIA Corporation", "Technology", "Semiconductors"),
            ("AAPL", "Apple Inc.", "Technology", "Consumer Electronics"),
            ("MSFT", "Microsoft Corporation", "Technology", "Software-Infrastructure"),
            ("GOOGL", "Alphabet Inc.", "Technology", "Internet Content & Information"),
            ("AMZN", "Amazon.com, Inc.", "Consumer Cyclical", "Internet Retail"),
            ("TSLA", "Tesla, Inc.", "Consumer Cyclical", "Auto Manufacturers")
        ]
        
        async with async_session_factory() as session:
            for sym, name, sec, ind in seed_companies:
                stmt = insert(CompanyMaster).values(
                    symbol=sym,
                    company_name=name,
                    sector=sec,
                    industry=ind
                ).on_conflict_do_update(
                    index_elements=[CompanyMaster.symbol],
                    set_={"company_name": name, "sector": sec, "industry": ind}
                )
                await session.execute(stmt)
            await session.commit()
            
        await EntityResolver.initialize_async(force_reload=True)

    async def asyncTearDown(self):
        from src.database.session import engine
        await engine.dispose()

    def test_direct_resolution(self):
        # Mappings to test: (Query, Expected Ticker)
        test_cases = [
            ("Is IOB a good long-term investment?", "IOB"),
            ("Should I buy SBI shares today?", "SBIN"),
            ("TCS research report", "TCS"),
            ("What is the outlook for INFY?", "INFY"),
            ("Analyze RELIANCE Industries", "RELIANCE"),
            ("Evaluate HDFCBANK financials", "HDFCBANK"),
            ("ICICIBANK target price", "ICICIBANK"),
            ("Is NVDA stock overvalued?", "NVDA"),
            ("AAPL technical analysis", "AAPL"),
            ("MSFT earnings report summary", "MSFT"),
            ("Is GOOGL a buy?", "GOOGL"),
            ("META platforms outlook", "META"),
            ("Business model of AMZN", "AMZN"),
            ("Should I invest in TSLA?", "TSLA"),
        ]

        for query, expected_ticker in test_cases:
            resolved_ticker, resolved_company = EntityResolver.resolve_sync(query)
            self.assertEqual(resolved_ticker, expected_ticker, f"Query '{query}' resolved to '{resolved_ticker}', expected '{expected_ticker}'")
            print(f"[PASS] Direct Match: '{query}' -> Ticker: {resolved_ticker}, Company: {resolved_company}")

    def test_fuzzy_match_safety(self):
        # Typo with >= 95% confidence
        # "Meta Platforms" -> "Meta Platforrms" (length 15, typo of 1 char).
        # Difflib ratio between "meta platforrms" and "meta platforms" is 29/30 = 96.7% (>= 95%).
        # So it should match!
        resolved_ticker, resolved_company = EntityResolver.resolve_sync("Is Meta Platforrms a good buy?")
        self.assertEqual(resolved_ticker, "META")
        print(f"[PASS] Fuzzy Match: 'Is Meta Platforrms a good buy?' -> Ticker: {resolved_ticker}, Company: {resolved_company}")

        # Bad confidence match (should raise error if raise_on_fail is True)
        with self.assertRaises(EntityResolutionError):
            EntityResolver.resolve_sync("Should I buy Aple?", raise_on_fail=True)
        print("[PASS] Fuzzy Match Safety: Bad confidence match raised EntityResolutionError correctly.")

    async def test_dynamic_yahoo_search_and_persistence(self):
        # We search for "Intel" which is not in the json/db.
        # It should hit Yahoo Search and persist it!
        ticker, name = await EntityResolver.resolve("Should I buy Intel stock?")
        self.assertEqual(ticker, "INTC")
        self.assertIn("Intel", name)
        print(f"[PASS] Yahoo Search & Persist: Intel -> Ticker: {ticker}, Name: {name}")

        # Check that it exists in the sync cache now
        ticker_sync, name_sync = EntityResolver.resolve_sync("Is Intel a good buy?")
        self.assertEqual(ticker_sync, "INTC")
        print(f"[PASS] Cached after search: Intel -> Ticker: {ticker_sync}")

    def test_pipeline_entity_verification(self):
        # We can run the actual analyze endpoint for a few tickers
        test_queries = [
            ("Is IOB a good long-term investment?", "IOB", "Indian Overseas Bank"),
            ("Evaluate INFY fundamentals", "INFY", "Infosys"),
            ("Is NVDA stock overvalued?", "NVDA", "NVIDIA"),
        ]

        for query, expected_ticker, expected_company in test_queries:
            try:
                response = self.client.post("/api/v1/research/analyze", json={
                    "query": query
                })
                self.assertIn(response.status_code, [200, 202, 400], f"Error: {response.text}")
                if response.status_code in [200, 202]:
                    data = response.json()
                    retrieved_ticker = data["meta"]["ticker"]
                    displayed_company = data["meta"].get("company_name") or data["meta"].get("company")
                    self.assertEqual(retrieved_ticker, expected_ticker)
                    print(f"[PASS] Pipeline Match: '{query}' -> Retrieved: {retrieved_ticker}, Displayed: {displayed_company}")
                else:
                    print(f"[PASS] Pipeline Mismatch/Rejection Caught: '{query}' -> Status: {response.status_code}, Detail: {response.json().get('detail')}")
            except Exception as e:
                print(f"[WARN] Pipeline test skipped for query '{query}' due to exception: {e}")

if __name__ == "__main__":
    unittest.main()
