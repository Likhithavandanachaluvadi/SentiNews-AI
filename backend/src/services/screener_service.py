"""
Screener.com Service - Institutional-grade Indian stock metrics
Fetches comprehensive fundamental data for Indian NSE stocks
"""
from http import client
import logging
from urllib import response
import httpx
import json
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup
import re
from tenacity import retry, stop_after_attempt, wait_exponential
import yfinance as yf
from bs4 import BeautifulSoup
import httpx
from sqlalchemy import select
from src.models.company_master import CompanyMaster
from src.database.session import async_session_factory
from src.services.market_data import _to_nse_ticker

logger = logging.getLogger(__name__)

print("SCREENER SERVICE FILE LOADED")

class ScreenerService:
    """
    Provides comprehensive stock metrics from screener.com and other sources.
    Includes PEG ratio, ROCE, debt metrics, and peer comparison data.
    """
    
    BASE_URL = "https://www.screener.in/api/company/"
    
    @staticmethod
    def _clean_number(value: str) -> Optional[float]:
        """Parse numeric values with Crore, Lakh, or % suffixes."""
        if not value or value == "—":
            return None
        
        multipliers = {
            'Cr': 1e7,
            'L': 1e5,
            '%': 1,
        }
        
        for suffix, mult in multipliers.items():
            if suffix in value:
                try:
                    num = float(value.replace(suffix, '').strip())
                    return num * mult
                except ValueError:
                    return None
        
        try:
            return float(value.replace(',', ''))
        except ValueError:
            return None
    
    @staticmethod
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def fetch_company_metrics(ticker: str) -> Dict[str, Any]:
        """
        Fetch comprehensive metrics from screener.com API.
        Falls back to web scraping if API unavailable.
        """
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # Try direct API endpoint
                url = f"{ScreenerService.BASE_URL}{ticker.upper()}/"
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    return ScreenerService._parse_screener_response(data, ticker)
                else:
                    logger.warning(f"Screener API returned {response.status_code} for {ticker}")
                    return {}
        
        except Exception as e:
            logger.warning(f"Screener API fetch failed for {ticker}: {e}")
            return {}
    
    @staticmethod
    def _parse_screener_response(data: Dict, ticker: str) -> Dict[str, Any]:
        """Parse screener.com API response into our metrics structure."""
        try:
            company = data.get('company', {})
            quarters = data.get('quarters', [])
            
            metrics = {
                'ticker': ticker,
                'company_name': company.get('name', ''),
                'sector': company.get('sector', ''),
                'industry': company.get('industry', ''),
            }
            
            # Current metrics
            if quarters:
                latest = quarters[0]
                metrics.update({
                    'market_cap': latest.get('market_cap'),
                    'stock_pe': latest.get('stock_pe'),
                    'pb_ratio': latest.get('book_value'),
                    'dividend_yield': latest.get('dividend_yield'),
                    'roce': latest.get('roce'),
                    'roe': latest.get('roe'),
                    'debt_to_equity': latest.get('debt_to_equity'),
                    'face_value': latest.get('face_value'),
                    'book_value': latest.get('book_value_per_share'),
                    'eps': latest.get('eps'),
                })
            
            return metrics
        except Exception as e:
            logger.error(f"Error parsing screener response: {e}")
            return {}
    @staticmethod
    async def get_dynamic_peers(ticker: str):

        current_stock = yf.Ticker(_to_nse_ticker(ticker))

        industry = current_stock.info.get("industry", "")

        print("INDUSTRY =", industry)
        print("ENTERED FETCH_PEER_COMPARISON")
        print("TICKER =", ticker)

        return industry
    @staticmethod
    async def get_dynamic_peers_from_db(
    industry: str,
    ticker: str
):
        try:
            async with async_session_factory() as session:
                result = await session.execute(
                    select(CompanyMaster)
                    .where(
                        CompanyMaster.industry == industry,
                        CompanyMaster.market_cap.is_not(None),
                        CompanyMaster.symbol != ticker.upper()
                    )
                    .order_by(
                        CompanyMaster.market_cap.desc()
                    )
                    .limit(5)
                )

                companies = result.scalars().all()

                peer_symbols = [
                    f"{company.symbol}.NS"
                    for company in companies
                ]

                print("DB PEERS =", peer_symbols)

                return peer_symbols

        except Exception as e:
            print("DB PEER ERROR =", e)
            return []

    @staticmethod
    async def fetch_peer_comparison(ticker: str, sector: str) -> Dict[str, Any]:
        # industry = await ScreenerService.get_dynamic_peers(ticker)

        # peers = await ScreenerService.get_dynamic_peers_from_db(
        #     industry,
        #     ticker
        # )
        print("="*60)
        print("Ticker =", ticker)
        print("===== NEW SCREENER SERVICE CODE RUNNING =====")
        industry = await ScreenerService.get_dynamic_peers(ticker)

        print("Industry =", industry)

        # peers = await ScreenerService.get_dynamic_peers_from_db(industry, ticker)
        peer_symbols = await ScreenerService.get_dynamic_peers_from_db(
            industry,
            ticker
        )

        peers = []
        print("DB Peers =", peers)

        print("="*60)
        
        # industry = await ScreenerService.get_dynamic_peers(ticker)

        # print("DYNAMIC INDUSTRY =", industry)

        # peers = []

        # industry_peers = {
        #     "Information Technology Services": [
        #         "TCS.NS",
        #         "INFY.NS",
        #         "HCLTECH.NS",
        #         "WIPRO.NS",
        #         "TECHM.NS"
        #     ],

        #     "Banks - Regional": [
        #         "HDFCBANK.NS",
        #         "ICICIBANK.NS",
        #         "AXISBANK.NS",
        #         "KOTAKBANK.NS"
        #     ],

        #     "Oil & Gas Refining & Marketing": [
        #         "RELIANCE.NS",
        #         "IOC.NS",
        #         "BPCL.NS",
        #         "HINDPETRO.NS"
        #     ]
        # }

        try:
            current_stock = yf.Ticker(_to_nse_ticker(ticker))
            url = f"https://www.screener.in/company/{ticker.upper()}/"

            async with httpx.AsyncClient() as client:
                 response = await client.get(url)

            print("SCREENER STATUS =", response.status_code)

            soup = BeautifulSoup(response.text, "html.parser")

            print("PAGE TITLE =",soup.title.text)
            current_info = current_stock.info or {}

            industry = current_stock.info.get("industry", "")

            print("DETECTED INDUSTRY =", industry)

            # peer_symbols = industry_peers.get(industry, [])
            
            # peer_symbols = await ScreenerService.get_dynamic_peers_from_db(industry, ticker)

            peer_symbols = [
                p for p in peer_symbols
                if p != f"{ticker.upper()}.NS"
            ]

            for peer_symbol in peer_symbols:

                print("FETCHING =", peer_symbol)

                stock = yf.Ticker(peer_symbol)
                info = stock.info or {}

                peers.append({
                    "ticker": peer_symbol.replace(".NS", "").replace(".BO", ""),
                    "name": info.get("longName", info.get("shortName", peer_symbol)),

                    "market_cap": (
                        str(round(info.get("marketCap", 0) / 10000000, 2)) + " Cr"
                        if info.get("marketCap")
                        else "N/A"
                    ),

                    "stock_pe": str(info.get("trailingPE", "N/A")),

                    "roe": (
                        str(round(info.get("returnOnEquity", 0) * 100, 2)) + "%"
                        if info.get("returnOnEquity")
                        else "N/A"
                    )
                })

        except Exception as e:
            logger.warning(f"Failed to build peer list: {e}")
        print("=" * 60)
        print("FINAL PEERS =", peers)
        print("PEER COUNT =", len(peers))
        print("=" * 60)
        return {
    "self": {
        "market_cap": (
            str(round(current_info.get("marketCap", 0) / 10000000, 2)) + " Cr"
            if current_info.get("marketCap")
            else "N/A"
        ),
        "stock_pe": str(current_info.get("trailingPE", "N/A")),
        "roe": (
            str(round(current_info.get("returnOnEquity", 0) * 100, 2)) + "%"
            if current_info.get("returnOnEquity")
            else "N/A"
        )
    },
    
    "peers": peers,
    "peer_count": len(peers)
}

    @staticmethod
    async def fetch_enhanced_metrics(ticker: str) -> Dict[str, Any]:
        """
        Fetch enhanced metrics including:
        - PEG ratio
        - ROCE trends
        - FCF yield
        - Debt structure
        - Growth rates
        """
        try:
            async with httpx.AsyncClient(timeout=10) as client:

                url = f"https://www.screener.in/company/{ticker.upper()}/"

                headers = {
                    "User-Agent": "Mozilla/5.0"
                }

                response = await client.get(url, headers=headers)

                if response.status_code != 200:
                    return {}

                soup = BeautifulSoup(response.text, "html.parser")

                metrics = {}

                metric_divs = soup.find_all(
                    "div",
                    class_=["metric", "metric-value"]
                )

                for div in metric_divs:

                    text = div.get_text(strip=True)

                    if "ROCE" in text:
                        match = re.search(
                            r"ROCE:?\s*([\d.]+)%?",
                            text
                        )
                        if match:
                            metrics["roce"] = float(match.group(1))

                    elif "PEG" in text:
                        match = re.search(
                            r"PEG:?\s*([\d.]+)",
                            text
                        )
                        if match:
                            metrics["peg_ratio"] = float(match.group(1))

                    elif "FCF Yield" in text:
                        match = re.search(
                            r"FCF Yield:?\s*([\d.]+)%?",
                            text
                        )
                        if match:
                            metrics["fcf_yield"] = float(match.group(1))

                return metrics

        except Exception as e:
            logger.warning(
                f"Enhanced metrics fetch failed for {ticker}: {e}"
            )
            return {}


# Function to enrich market context with screener metrics
async def enrich_with_screener_metrics(ticker: str, context_chunks: list) -> list:
    """
    Enhance market context with screener.com institutional-grade metrics.
    Compares common metrics between Yahoo Finance and Screener.com for validation.
    """
    try:
        screener_metrics = await ScreenerService.fetch_company_metrics(ticker)
        enhanced_metrics = await ScreenerService.fetch_enhanced_metrics(ticker)
        
        # Load Yahoo Finance data for cross-validation
        nse_ticker = _to_nse_ticker(ticker)
        try:
            stock = yf.Ticker(nse_ticker)
            yahoo_info = stock.info or {}
        except Exception as e:
            logger.warning(f"Could not load Yahoo Finance info for cross-validation: {e}")
            yahoo_info = {}

        # Combine Screener metrics
        all_metrics = {**screener_metrics, **enhanced_metrics}
        
        if all_metrics:
            metrics_chunk = "\n=== SCREENER.COM INSTITUTIONAL METRICS ===\n"
            
            if all_metrics.get('stock_pe'):
                metrics_chunk += f"PE Ratio: {all_metrics['stock_pe']:.2f}x\n"
            if all_metrics.get('peg_ratio'):
                metrics_chunk += f"PEG Ratio: {all_metrics['peg_ratio']:.2f}x\n"
            if all_metrics.get('pb_ratio'):
                metrics_chunk += f"Price to Book: {all_metrics['pb_ratio']:.2f}x\n"
            if all_metrics.get('roce'):
                metrics_chunk += f"ROCE: {all_metrics['roce']:.1f}%\n"
            if all_metrics.get('roe'):
                metrics_chunk += f"ROE: {all_metrics['roe']:.1f}%\n"
            if all_metrics.get('dividend_yield'):
                metrics_chunk += f"Dividend Yield: {all_metrics['dividend_yield']:.2f}%\n"
            if all_metrics.get('debt_to_equity'):
                metrics_chunk += f"Debt-to-Equity: {all_metrics['debt_to_equity']:.2f}x\n"
            if all_metrics.get('fcf_yield'):
                metrics_chunk += f"FCF Yield: {all_metrics['fcf_yield']:.2f}%\n"
            if all_metrics.get('book_value'):
                metrics_chunk += f"Book Value per Share: ₹{all_metrics['book_value']:.2f}\n"
            if all_metrics.get('face_value'):
                metrics_chunk += f"Face Value: ₹{all_metrics['face_value']:.2f}\n"

            # Perform Provider Validation & Conflict Resolution
            validation_reports = []
            confidence_penalty = 0.0

            # 1. PE Ratio Validation
            pe_scr = all_metrics.get('stock_pe')
            pe_yh = yahoo_info.get('trailingPE') or yahoo_info.get('forwardPE')
            if pe_scr and pe_yh:
                diff = abs(pe_scr - pe_yh) / max(pe_scr, pe_yh)
                if diff > 0.10:  # 10% tolerance
                    log_msg = f"[CONFLICT] PE Ratio: Screener={pe_scr}x, Yahoo={pe_yh:.2f}x (Diff: {diff*100:.1f}%) -> Preferred: Screener"
                    print(log_msg)
                    logger.warning(log_msg)
                    validation_reports.append(log_msg)
                    confidence_penalty += 0.05
                else:
                    validation_reports.append(f"[OK] PE Ratio validated (Diff: {diff*100:.1f}%)")

            # 2. Market Cap Validation
            mc_scr = all_metrics.get('market_cap')
            mc_yh = yahoo_info.get('marketCap')
            if mc_scr and mc_yh:
                diff = abs(mc_scr - mc_yh) / max(mc_scr, mc_yh)
                if diff > 0.05:  # 5% tolerance
                    log_msg = f"[CONFLICT] Market Cap: Screener={mc_scr:,.0f}, Yahoo={mc_yh:,.0f} (Diff: {diff*100:.1f}%) -> Preferred: Screener"
                    print(log_msg)
                    logger.warning(log_msg)
                    validation_reports.append(log_msg)
                    confidence_penalty += 0.05
                else:
                    validation_reports.append(f"[OK] Market Cap validated (Diff: {diff*100:.1f}%)")

            # 3. Dividend Yield Validation
            dy_scr = all_metrics.get('dividend_yield')
            dy_yh = yahoo_info.get('dividendYield')
            if dy_scr is not None and dy_yh is not None:
                dy_yh_pct = dy_yh * 100
                diff = abs(dy_scr - dy_yh_pct) / max(dy_scr, dy_yh_pct) if max(dy_scr, dy_yh_pct) > 0 else 0
                if diff > 0.10:  # 10% tolerance
                    log_msg = f"[CONFLICT] Dividend Yield: Screener={dy_scr:.2f}%, Yahoo={dy_yh_pct:.2f}% (Diff: {diff*100:.1f}%) -> Preferred: Screener"
                    print(log_msg)
                    logger.warning(log_msg)
                    validation_reports.append(log_msg)
                    confidence_penalty += 0.05
                else:
                    validation_reports.append(f"[OK] Dividend Yield validated (Diff: {diff*100:.1f}%)")

            # 4. PEG Ratio Validation
            peg_scr = all_metrics.get('peg_ratio')
            peg_yh = yahoo_info.get('pegRatio')
            if peg_scr and peg_yh:
                diff = abs(peg_scr - peg_yh) / max(peg_scr, peg_yh)
                if diff > 0.10:  # 10% tolerance
                    log_msg = f"[CONFLICT] PEG Ratio: Screener={peg_scr:.2f}x, Yahoo={peg_yh:.2f}x (Diff: {diff*100:.1f}%) -> Preferred: Screener"
                    print(log_msg)
                    logger.warning(log_msg)
                    validation_reports.append(log_msg)
                    confidence_penalty += 0.05
                else:
                    validation_reports.append(f"[OK] PEG Ratio validated (Diff: {diff*100:.1f}%)")

            # Add Provider Metadata and Grounding logs to Chunk
            metrics_chunk += "\n=== PROVIDER VALIDATION REPORT ===\n"
            metrics_chunk += f"Primary Provider: Screener.com (NSE), Yahoo Finance (Global)\n"
            metrics_chunk += f"Resolution Confidence: {max(0.70, 1.0 - confidence_penalty) * 100:.1f}%\n"
            metrics_chunk += f"Validation Status: {'Disagreements Found' if confidence_penalty > 0 else 'Verified'}\n"
            for report in validation_reports:
                metrics_chunk += f"- {report}\n"
            
            context_chunks.append(metrics_chunk)
            
    except Exception as e:
        logger.warning(f"Failed to enrich with screener metrics: {e}")
    
    print("SCREENER SERVICE LOADED SUCCESSFULLY WITH VALIDATION")
    return context_chunks
