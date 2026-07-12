"""
Market endpoints.
Provides historical price data for charting and index status for the dashboard.
"""
from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any, List
import logging
import yfinance as yf
import time
from datetime import datetime

from src.services.market_data import get_price_history, _to_nse_ticker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/market", tags=["market"])

# Simple in-memory cache configurations
CACHE_DURATION_SECONDS = 300.0 # 5 minutes cache

_INDICES_CACHE = None
_INDICES_CACHE_TIMESTAMP = 0.0

_HISTORY_CACHE = {} # ticker -> (timestamp, data)

@router.get("/history/{ticker}")
def get_ticker_history(ticker: str) -> Dict[str, Any]:
    """
    Returns price history for a given ticker symbol.
    Expected response format matching frontend StockChart requirement.
    """
    global _HISTORY_CACHE
    try:
        if not ticker:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ticker parameter is required"
            )
        
        ticker_symbol = ticker.strip().upper()
        now = time.time()
        
        # Check cache
        if ticker_symbol in _HISTORY_CACHE:
            ts, cached_data = _HISTORY_CACHE[ticker_symbol]
            if (now - ts) < CACHE_DURATION_SECONDS:
                logger.info(f"Cache hit for ticker history: {ticker_symbol}")
                return cached_data
        
        history = get_price_history(ticker_symbol)
        response_data = {
            "ticker": ticker_symbol,
            "history": history
        }
        
        # Save cache
        _HISTORY_CACHE[ticker_symbol] = (now, response_data)
        return response_data
        
    except Exception as e:
        logger.error(f"Error fetching price history for {ticker}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve price history: {str(e)}"
        )

@router.get("/indices")
def get_market_indices() -> List[Dict[str, Any]]:
    """
    Returns data for major market indices (Nifty 50, Sensex, Nifty Bank, Nifty IT).
    Includes last price, price change, percentage change, and 7-day sparkline coordinates.
    """
    global _INDICES_CACHE, _INDICES_CACHE_TIMESTAMP
    now = time.time()
    
    # Check cache
    if _INDICES_CACHE is not None and (now - _INDICES_CACHE_TIMESTAMP) < CACHE_DURATION_SECONDS:
        logger.info("Cache hit for market indices")
        return _INDICES_CACHE

    indices_config = [
        {"name": "NIFTY 50", "ticker": "^NSEI"},
        {"name": "SENSEX", "ticker": "^BSESN"},
        {"name": "NIFTY BANK", "ticker": "^NSEBANK"},
        {"name": "NIFTY IT", "ticker": "^CNXIT"},
    ]
    
    results = []
    
    for item in indices_config:
        try:
            ticker_symbol = item["ticker"]
            stock = yf.Ticker(ticker_symbol)
            
            # Fetch 7d historical data for sparkline
            hist = stock.history(period="7d")
            
            if hist.empty:
                logger.warning(f"No history returned from yfinance for index: {ticker_symbol}")
                results.append({
                    "name": item["name"],
                    "ticker": ticker_symbol,
                    "price": 0.0,
                    "change": 0.0,
                    "change_percent": 0.0,
                    "sparkline": []
                })
                continue
                
            # Grab close prices for sparkline
            sparkline = [round(float(val), 2) for val in hist["Close"].tolist()]
            
            # Current price and previous close calculation
            current_price = hist["Close"].iloc[-1]
            
            # Previous close can be from history or fallback info
            if len(hist) > 1:
                prev_close = hist["Close"].iloc[-2]
            else:
                prev_close = stock.info.get("previousClose") or current_price
                
            change = current_price - prev_close
            change_percent = (change / prev_close * 100) if prev_close else 0.0
            
            results.append({
                "name": item["name"],
                "ticker": ticker_symbol,
                "price": round(float(current_price), 2),
                "change": round(float(change), 2),
                "change_percent": round(float(change_percent), 2),
                "sparkline": sparkline
            })
            
        except Exception as e:
            logger.error(f"Error fetching data for index {item['name']}: {e}")
            results.append({
                "name": item["name"],
                "ticker": item["ticker"],
                "price": 0.0,
                "change": 0.0,
                "change_percent": 0.0,
                "sparkline": []
            })
            
    # Save cache
    _INDICES_CACHE = results
    _INDICES_CACHE_TIMESTAMP = now
    
    return results
