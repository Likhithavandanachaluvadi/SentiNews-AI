import sys
import os

sys.path.append(
    os.path.join(
        os.path.dirname(__file__),
        ".."
    )
)
import json
import asyncio
import yfinance as yf
from sqlalchemy.dialects.postgresql import insert

from src.database.session import async_session_factory
from src.models.company_master import CompanyMaster

# with open("src/services/indian_ticker.json", "r") as f:
#     ticker_map = json.load(f)
json_path = os.path.join(
    os.path.dirname(__file__),
    "..",
    "src",
    "indian_tickers.json"
)

with open(json_path, "r", encoding="utf-8") as f:
    ticker_map = json.load(f)

COMPANIES = sorted(
    {
        symbol.upper()
        for symbol in ticker_map.values()
    }
)
# COMPANIES = [
#     "TCS",
#     "INFY",
#     "HCLTECH",
#     "WIPRO",
#     "TECHM",
#     "RELIANCE",
#     "HDFCBANK",
#     "ICICIBANK",
#     "AXISBANK",
#     "KOTAKBANK",
#     "LTIM",
#     "MPHASIS",
#     "PERSISTENT",
#     "COFORGE",
#     "SBIN",
#     "INDUSINDBK",
#     "IOC",
#     "BPCL",
#     "HINDPETRO",
#     "BAJFINANCE",
#     "MARUTI",
#     "TATAMOTORS",
#     "M&M",
#     "HEROMOTOCO",
#     "SUNPHARMA",
#     "DRREDDY",
#     "CIPLA"
# ]


async def populate_companies():

    async with async_session_factory() as session:

        for symbol in COMPANIES:

            try:
                print(f"Fetching {symbol}...")
                if not symbol:
                    continue
                stock = yf.Ticker(f"{symbol}.NS")
                info = stock.info
                if not info:
                    print(f"No data for {symbol}")
                    continue

                stmt = insert(CompanyMaster).values(
                    symbol=symbol,
                    company_name=info.get("longName", symbol),
                    industry=info.get("industry"),
                    sector=info.get("sector"),
                    market_cap=info.get("marketCap")
                ).on_conflict_do_update(
                    index_elements=[CompanyMaster.symbol],
                    set_={
                        "company_name": info.get("longName", symbol),
                        "industry": info.get("industry"),
                        "sector": info.get("sector"),
                        "market_cap": info.get("marketCap"),
                    }
                )

                await session.execute(stmt)

                print(
                    f"Upserted: {symbol} | "
                    f"{info.get('industry')} | "
                    f"{info.get('sector')}"
                )

            except Exception as e:
                print(f"Failed for {symbol}: {e}")

        await session.commit()

        print("Company Master populated successfully!")


if __name__ == "__main__":
    asyncio.run(populate_companies())
