import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def calculate_sma(data: pd.Series, window: int) -> pd.Series:
    return data.rolling(window=window).mean()

def calculate_ema(data: pd.Series, window: int) -> pd.Series:
    return data.ewm(span=window, adjust=False).mean()

def calculate_rsi(data: pd.Series, window: int = 14) -> pd.Series:
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)
    
    avg_gain = gain.rolling(window=window, min_periods=1).mean()
    avg_loss = loss.rolling(window=window, min_periods=1).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(data: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = calculate_ema(data, fast)
    ema_slow = calculate_ema(data, slow)
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def calculate_bollinger_bands(data: pd.Series, window: int = 20, num_std: int = 2):
    sma = calculate_sma(data, window)
    rolling_std = data.rolling(window=window).std()
    upper_band = sma + (rolling_std * num_std)
    lower_band = sma - (rolling_std * num_std)
    return upper_band, lower_band

def get_programmatic_technical_indicators(price_history: list[dict]) -> Dict[str, Any]:
    """
    Computes standard technical indicators from a list of dicts:
    [{"date": "YYYY-MM-DD", "close": 100.5, "volume": 1000}, ...]
    Returns a dictionary of current values and trend signals.
    """
    if not price_history or len(price_history) < 50:
        return {"error": "Insufficient data to calculate technical indicators."}
    
    try:
        df = pd.DataFrame(price_history)
        df['close'] = pd.to_numeric(df['close'])
        df['volume'] = pd.to_numeric(df['volume'])
        
        # Calculate indicators
        df['SMA_20'] = calculate_sma(df['close'], 20)
        df['SMA_50'] = calculate_sma(df['close'], 50)
        df['RSI_14'] = calculate_rsi(df['close'], 14)
        
        macd_line, signal_line, hist = calculate_macd(df['close'])
        df['MACD'] = macd_line
        df['MACD_Signal'] = signal_line
        
        upper, lower = calculate_bollinger_bands(df['close'])
        df['BB_Upper'] = upper
        df['BB_Lower'] = lower
        
        # Get the latest row for current values
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Determine signals
        current_price = latest['close']
        sma_20 = latest['SMA_20']
        sma_50 = latest['SMA_50']
        rsi = latest['RSI_14']
        macd = latest['MACD']
        macd_sig = latest['MACD_Signal']
        
        # Trend Strength
        trend = "Neutral"
        if current_price > sma_20 and current_price > sma_50 and sma_20 > sma_50:
            trend = "Strong Uptrend"
        elif current_price < sma_20 and current_price < sma_50 and sma_20 < sma_50:
            trend = "Strong Downtrend"
        elif current_price > sma_50:
            trend = "Mild Uptrend"
        elif current_price < sma_50:
            trend = "Mild Downtrend"
            
        # Momentum
        momentum = "Neutral"
        if rsi > 70:
            momentum = "Overbought"
        elif rsi < 30:
            momentum = "Oversold"
            
        if macd > macd_sig and prev['MACD'] <= prev['MACD_Signal']:
            momentum += " (MACD Bullish Crossover)"
        elif macd < macd_sig and prev['MACD'] >= prev['MACD_Signal']:
            momentum += " (MACD Bearish Crossover)"
            
        return {
            "current_price": round(current_price, 2),
            "SMA_20": round(sma_20, 2) if not np.isnan(sma_20) else None,
            "SMA_50": round(sma_50, 2) if not np.isnan(sma_50) else None,
            "RSI_14": round(rsi, 2) if not np.isnan(rsi) else None,
            "MACD": round(macd, 2) if not np.isnan(macd) else None,
            "MACD_Signal": round(macd_sig, 2) if not np.isnan(macd_sig) else None,
            "BB_Upper": round(latest['BB_Upper'], 2) if not np.isnan(latest['BB_Upper']) else None,
            "BB_Lower": round(latest['BB_Lower'], 2) if not np.isnan(latest['BB_Lower']) else None,
            "Trend_Analysis": trend,
            "Momentum_Analysis": momentum
        }
        
    except Exception as e:
        logger.error(f"Error computing technical indicators: {e}")
        return {"error": f"Failed to compute indicators: {str(e)}"}
