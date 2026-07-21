"""
Market data service using yfinance for Indian NSE stocks.
Automatically appends .NS suffix for NSE ticker lookups.
Integrated with screener.com for institutional-grade metrics.
All financial figures are displayed in INR (₹) where applicable.
"""
from soupsieve import match
import yfinance as yf
import logging
from typing import Optional, Any, Dict, List
import asyncio

logger = logging.getLogger(__name__)

import json
from pathlib import Path

_indian_symbols = set()
try:
    json_path = Path(__file__).resolve().parents[1] / "indian_tickers.json"
    if json_path.exists():
        with json_path.open("r", encoding="utf-8") as f:
            ticker_map = json.load(f)
            _indian_symbols = {sym.upper().strip() for sym in ticker_map.values()}
except Exception as e:
    pass

def _to_nse_ticker(ticker: str) -> str:
    """
    Converts a raw NSE ticker symbol to the yfinance-compatible format.
    For Indian NSE stocks, yfinance requires the '.NS' suffix.
    e.g. 'RELIANCE' → 'RELIANCE.NS', 'TCS' → 'TCS.NS'
    Already-suffixed tickers are returned as-is.
    """
    ticker = ticker.upper().strip()
    if ticker.endswith(".NS") or ticker.endswith(".BO"):
        return ticker
    
    # Common US stock symbols
    us_tickers = {"NVDA", "AAPL", "MSFT", "GOOG", "GOOGL", "AMZN", "META", "TSLA", "NFLX", "AMD", "INTC"}
    if ticker in us_tickers:
        return ticker
        
    # If Nifty 500 JSON is loaded and symbol is not in it, do not append .NS
    if _indian_symbols and ticker not in _indian_symbols:
        return ticker
        
    return f"{ticker}.NS"


def _format_inr(value: Optional[float]) -> str:
    """Format a number into readable INR units (Cr, L, etc.)."""
    if value is None:
        return "N/A"
    if value >= 1e12:
        return f"₹{value / 1e12:.2f}L Cr"
    if value >= 1e9:
        return f"₹{value / 1e7:.2f} Cr"
    if value >= 1e6:
        return f"₹{value / 1e5:.2f} L"
    return f"₹{value:,.2f}"


def get_market_context(ticker: str) -> list[str]:
    """
    Fetches real-time market data for a given NSE ticker using yfinance.
    Automatically adds .NS suffix for Indian stock lookup.
    Returns a list of context strings ready for LLM injection.
    """
    context_chunks = []
    nse_ticker = _to_nse_ticker(ticker)

    try:
        stock = yf.Ticker(nse_ticker)
        info = stock.info

        # Check if data was actually returned (yfinance silently returns
        # empty dicts for invalid tickers)
        if not info or info.get("quoteType") is None:
            logger.warning(f"No data returned from yfinance for {nse_ticker}, trying BSE fallback")
            # Try BSE fallback
            bse_ticker = ticker.upper() + ".BO"
            stock = yf.Ticker(bse_ticker)
            info = stock.info
            if not info or info.get("quoteType") is None:
                raise ValueError(f"No market data found for ticker: {ticker}")

        # Validation Layer
        from src.services.entity_resolver import EntityResolver, TickerMismatchError, log_entity_validation
        yahoo_ticker = info.get("symbol", "").upper().split(".")[0].split("-")[0] if info.get("symbol") else ticker.upper()
        yahoo_name = info.get("longName") or info.get("shortName") or ""
        name_resolved_ticker = None
        if yahoo_name:
            name_resolved_ticker, _ = EntityResolver.resolve_sync(yahoo_name)

        if (yahoo_ticker and yahoo_ticker != ticker.upper()) or \
           (name_resolved_ticker and name_resolved_ticker != ticker.upper()):
            log_entity_validation(
                query="N/A (Market Data)",
                req_company=EntityResolver._ticker_to_company.get(ticker.upper()) or ticker.upper(),
                req_ticker=ticker.upper(),
                res_company=EntityResolver._ticker_to_company.get(ticker.upper()) or ticker.upper(),
                res_ticker=ticker.upper(),
                ret_company=yahoo_name,
                ret_ticker=yahoo_ticker,
                status="FAILED",
                reason="Ticker mismatch detected (Yahoo ticker or company name mismatch)"
            )
            raise TickerMismatchError(
                f"TickerMismatchError: Resolved ticker: {ticker.upper()}, "
                f"but market loaded ticker: {yahoo_ticker} and company name: {yahoo_name}."
            )
        else:
            log_entity_validation(
                query="N/A (Market Data)",
                req_company=EntityResolver._ticker_to_company.get(ticker.upper()) or ticker.upper(),
                req_ticker=ticker.upper(),
                res_company=EntityResolver._ticker_to_company.get(ticker.upper()) or ticker.upper(),
                res_ticker=ticker.upper(),
                ret_company=yahoo_name,
                ret_ticker=yahoo_ticker,
                status="PASS"
            )

        # Company overview
        name = info.get("longName") or info.get("shortName", ticker)
        sector = info.get("sector", "N/A")
        industry = info.get("industry", "N/A")
        summary = info.get("longBusinessSummary", "No description available.")
        if len(summary) > 250:
            summary = summary[:250] + "..."
        exchange = info.get("exchange", "NSE")

        context_chunks.append(
            f"Company Overview: {name} is listed on {exchange} and operates in the "
            f"{industry} industry within the {sector} sector.\n{summary}"
        )

        # Financial snapshot (in INR)
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
        pe_ratio = info.get("trailingPE")
        pb_ratio = info.get("priceToBook")
        market_cap = info.get("marketCap")
        revenue = info.get("totalRevenue")
        profit_margin = info.get("profitMargins")
        roe = info.get("returnOnEquity")
        debt_to_equity = info.get("debtToEquity")
        eps = info.get("trailingEps")
        dividend_yield = info.get("dividendYield")
        week_52_high = info.get("fiftyTwoWeekHigh")
        week_52_low = info.get("fiftyTwoWeekLow")

        financial_lines = [f"Financial Snapshot for {name} ({ticker.upper()} | NSE):"]

        if price:
            change = ""
            if prev_close:
                pct = ((price - prev_close) / prev_close) * 100
                change = f"  ({'+' if pct >= 0 else ''}{pct:.2f}% vs prev close)"
            financial_lines.append(f"- Current Price: ₹{price:,.2f}{change}")
        if week_52_high:
            financial_lines.append(f"- 52-Week High: ₹{week_52_high:,.2f}")
        if week_52_low:
            financial_lines.append(f"- 52-Week Low: ₹{week_52_low:,.2f}")
        if market_cap:
            financial_lines.append(f"- Market Cap: {_format_inr(market_cap)}")
        if pe_ratio:
            financial_lines.append(f"- P/E Ratio (TTM): {pe_ratio:.2f}x")
        if pb_ratio:
            financial_lines.append(f"- Price/Book: {pb_ratio:.2f}x")
        if eps:
            financial_lines.append(f"- EPS (TTM): ₹{eps:.2f}")
        if revenue:
            financial_lines.append(f"- Annual Revenue: {_format_inr(revenue)}")
        if profit_margin:
            financial_lines.append(f"- Net Profit Margin: {profit_margin * 100:.1f}%")
        if roe:
            financial_lines.append(f"- Return on Equity (ROE): {roe * 100:.1f}%")
        if debt_to_equity:
            financial_lines.append(f"- Debt/Equity Ratio: {debt_to_equity:.2f}")
        if dividend_yield:
            financial_lines.append(f"- Dividend Yield: {dividend_yield * 100:.2f}%")

        context_chunks.append("\n".join(financial_lines))

        # Fetch Financial Statement growth (QoQ and YoY) and margins
        history_lines = ["\nFinancial Statements Growth & Margins History:"]
        
        def find_col(df, keywords):
            for c in df.columns:
                c_str = str(c).lower()
                if any(kw in c_str for kw in keywords):
                    return c
            return None

        # 1. Quarterly Financials
        try:
            q_fin = stock.quarterly_financials
            if q_fin is not None and not q_fin.empty:
                q_fin_t = q_fin.T
                rev_col = find_col(q_fin_t, ["total revenue", "revenue"])
                net_col = find_col(q_fin_t, ["net income"])
                gross_col = find_col(q_fin_t, ["gross profit"])
                op_col = find_col(q_fin_t, ["operating income"])

                history_lines.append("- Quarterly Metrics:")
                for index, row in q_fin_t.head(2).iterrows():
                    date_str = index.strftime('%Y-%m-%d') if hasattr(index, 'strftime') else str(index)
                    r_val = row.get(rev_col) if rev_col else None
                    n_val = row.get(net_col) if net_col else None
                    g_val = row.get(gross_col) if gross_col else None
                    o_val = row.get(op_col) if op_col else None

                    g_margin = f"{(g_val / r_val) * 100:.1f}%" if g_val is not None and r_val else "N/A"
                    o_margin = f"{(o_val / r_val) * 100:.1f}%" if o_val is not None and r_val else "N/A"
                    n_margin = f"{(n_val / r_val) * 100:.1f}%" if n_val is not None and r_val else "N/A"

                    r_fmt = _format_inr(r_val) if r_val is not None else "N/A"
                    n_fmt = _format_inr(n_val) if n_val is not None else "N/A"

                    history_lines.append(
                        f"  * Quarter Ending {date_str}: Revenue = {r_fmt}, Net Income = {n_fmt}, "
                        f"Gross Margin = {g_margin}, Operating Margin = {o_margin}, Net Margin = {n_margin}"
                    )

                if len(q_fin_t) >= 2:
                    lat_idx = q_fin_t.index[0]
                    prev_idx = q_fin_t.index[1]
                    
                    lat_date = lat_idx.strftime('%Y-%m-%d') if hasattr(lat_idx, 'strftime') else str(lat_idx)
                    prev_date = prev_idx.strftime('%Y-%m-%d') if hasattr(prev_idx, 'strftime') else str(prev_idx)

                    if rev_col:
                        lat_r = q_fin_t.loc[lat_idx, rev_col]
                        prev_r = q_fin_t.loc[prev_idx, rev_col]
                        if lat_r and prev_r:
                            qoq_r = ((lat_r - prev_r) / prev_r) * 100
                            history_lines.append(f"  * Revenue QoQ Growth (latest vs prev quarter): {qoq_r:.1f}% ({lat_date} vs {prev_date})")

                    if net_col:
                        lat_n = q_fin_t.loc[lat_idx, net_col]
                        prev_n = q_fin_t.loc[prev_idx, net_col]
                        if lat_n and prev_n:
                            qoq_n = ((lat_n - prev_n) / prev_n) * 100
                            history_lines.append(f"  * Net Income QoQ Growth (latest vs prev quarter): {qoq_n:.1f}% ({lat_date} vs {prev_date})")

                if len(q_fin_t) >= 5:
                    lat_idx = q_fin_t.index[0]
                    yoy_idx = q_fin_t.index[4]
                    
                    lat_date = lat_idx.strftime('%Y-%m-%d') if hasattr(lat_idx, 'strftime') else str(lat_idx)
                    yoy_date = yoy_idx.strftime('%Y-%m-%d') if hasattr(yoy_idx, 'strftime') else str(yoy_idx)

                    if rev_col:
                        lat_r = q_fin_t.loc[lat_idx, rev_col]
                        yoy_r = q_fin_t.loc[yoy_idx, rev_col]
                        if lat_r and yoy_r:
                            yoy_r_q = ((lat_r - yoy_r) / yoy_r) * 100
                            history_lines.append(f"  * Revenue YoY Quarterly Growth: {yoy_r_q:.1f}% ({lat_date} vs {yoy_date})")

                    if net_col:
                        lat_n = q_fin_t.loc[lat_idx, net_col]
                        yoy_n = q_fin_t.loc[yoy_idx, net_col]
                        if lat_n and yoy_n:
                            yoy_n_q = ((lat_n - yoy_n) / yoy_n) * 100
                            history_lines.append(f"  * Net Income YoY Quarterly Growth: {yoy_n_q:.1f}% ({lat_date} vs {yoy_date})")

        except Exception as e:
            logger.warning(f"Error extracting quarterly financials for {ticker}: {e}")

        # 2. Annual Financials
        try:
            ann_fin = stock.financials
            if ann_fin is not None and not ann_fin.empty:
                ann_fin_t = ann_fin.T
                rev_col = find_col(ann_fin_t, ["total revenue", "revenue"])
                net_col = find_col(ann_fin_t, ["net income"])
                gross_col = find_col(ann_fin_t, ["gross profit"])
                op_col = find_col(ann_fin_t, ["operating income"])

                history_lines.append("- Annual Metrics:")
                for index, row in ann_fin_t.head(2).iterrows():
                    date_str = index.strftime('%Y-%m-%d') if hasattr(index, 'strftime') else str(index)
                    r_val = row.get(rev_col) if rev_col else None
                    n_val = row.get(net_col) if net_col else None
                    g_val = row.get(gross_col) if gross_col else None
                    o_val = row.get(op_col) if op_col else None

                    g_margin = f"{(g_val / r_val) * 100:.1f}%" if g_val is not None and r_val else "N/A"
                    o_margin = f"{(o_val / r_val) * 100:.1f}%" if o_val is not None and r_val else "N/A"
                    n_margin = f"{(n_val / r_val) * 100:.1f}%" if n_val is not None and r_val else "N/A"

                    r_fmt = _format_inr(r_val) if r_val is not None else "N/A"
                    n_fmt = _format_inr(n_val) if n_val is not None else "N/A"

                    history_lines.append(
                        f"  * Year Ending {date_str}: Revenue = {r_fmt}, Net Income = {n_fmt}, "
                        f"Gross Margin = {g_margin}, Operating Margin = {o_margin}, Net Margin = {n_margin}"
                    )

                if len(ann_fin_t) >= 2:
                    lat_idx = ann_fin_t.index[0]
                    prev_idx = ann_fin_t.index[1]
                    
                    lat_date = lat_idx.strftime('%Y-%m-%d') if hasattr(lat_idx, 'strftime') else str(lat_idx)
                    prev_date = prev_idx.strftime('%Y-%m-%d') if hasattr(prev_idx, 'strftime') else str(prev_idx)

                    if rev_col:
                        lat_r = ann_fin_t.loc[lat_idx, rev_col]
                        prev_r = ann_fin_t.loc[prev_idx, rev_col]
                        if lat_r and prev_r:
                            yoy_r = ((lat_r - prev_r) / prev_r) * 100
                            history_lines.append(f"  * Annual Revenue YoY Growth: {yoy_r:.1f}% ({lat_date} vs {prev_date})")

                    if net_col:
                        lat_n = ann_fin_t.loc[lat_idx, net_col]
                        prev_n = ann_fin_t.loc[prev_idx, net_col]
                        if lat_n and prev_n:
                            yoy_n = ((lat_n - prev_n) / prev_n) * 100
                            history_lines.append(f"  * Annual Net Income YoY Growth: {yoy_n:.1f}% ({lat_date} vs {prev_date})")

        except Exception as e:
            logger.warning(f"Error extracting annual financials for {ticker}: {e}")

        if len(history_lines) > 1:
            context_chunks.append("\n".join(history_lines))

        # Compute ROCE (Return on Capital Employed)
        roce = None
        try:
            ebit = None
            ann_fin = stock.financials
            if ann_fin is not None and not ann_fin.empty:
                ann_fin_t = ann_fin.T
                ebit_col = find_col(ann_fin_t, ["operating income", "ebit"])
                if ebit_col:
                    ebit = ann_fin_t[ebit_col].iloc[0]
            
            bal_sheet = stock.balance_sheet
            if bal_sheet is not None and not bal_sheet.empty:
                bal_sheet_t = bal_sheet.T
                assets_col = find_col(bal_sheet_t, ["total assets", "assets"])
                curr_liab_col = find_col(bal_sheet_t, ["total current liabilities", "current liabilities"])
                
                if assets_col:
                    total_assets = bal_sheet_t[assets_col].iloc[0]
                    curr_liab = bal_sheet_t[curr_liab_col].iloc[0] if curr_liab_col else 0
                    cap_employed = total_assets - curr_liab
                    if cap_employed and ebit is not None:
                        roce = (ebit / cap_employed) * 100
        except Exception as e:
            logger.warning(f"Failed to calculate ROCE for {ticker}: {e}")

        # Format and compile Screener.in Key Statistics
        screener_lines = ["\nScreener.in Key Statistics:"]
        
        m_cap = info.get("marketCap")
        curr_p = info.get("currentPrice") or info.get("regularMarketPrice")
        high_52 = info.get("fiftyTwoWeekHigh")
        low_52 = info.get("fiftyTwoWeekLow")
        pe = info.get("trailingPE")
        book_v = info.get("bookValue")
        div_y = info.get("dividendYield")
        roe_val = info.get("returnOnEquity")
        face_v = info.get("faceValue")
        peg_r = info.get("pegRatio")
        pb_r = info.get("priceToBook")

        m_cap_cr = f"₹{m_cap / 10000000:,.1f} Cr" if m_cap else "N/A"
        curr_p_fmt = f"₹{curr_p:,.2f}" if curr_p else "N/A"
        high_low_52 = f"₹{high_52:,.2f} / ₹{low_52:,.2f}" if high_52 and low_52 else "N/A"
        pe_fmt = f"{pe:.2f}" if pe else "N/A"
        book_v_fmt = f"₹{book_v:.2f}" if book_v else "N/A"
        div_y_fmt = f"{div_y * 100:.2f}%" if div_y else "N/A"
        roe_fmt = f"{roe_val * 100:.2f}%" if roe_val else "N/A"
        roce_fmt = f"{roce:.2f}%" if roce is not None else "N/A"
        face_v_fmt = f"₹{face_v}" if face_v else "N/A"
        peg_fmt = f"{peg_r:.2f}" if peg_r else "N/A"
        pb_fmt = f"{pb_r:.2f}" if pb_r else "N/A"

        screener_lines.append(f"- Market Cap: {m_cap_cr}")
        screener_lines.append(f"- Current Price: {curr_p_fmt}")
        screener_lines.append(f"- High / Low: {high_low_52}")
        screener_lines.append(f"- Stock P/E: {pe_fmt}")
        screener_lines.append(f"- PEG Ratio: {peg_fmt}")
        screener_lines.append(f"- Price to Book: {pb_fmt}")
        screener_lines.append(f"- Book Value: {book_v_fmt}")
        screener_lines.append(f"- Dividend Yield: {div_y_fmt}")
        screener_lines.append(f"- ROCE: {roce_fmt}")
        screener_lines.append(f"- ROE: {roe_fmt}")
        screener_lines.append(f"- Face Value: {face_v_fmt}")

        context_chunks.append("\n".join(screener_lines))

        # # Analyst recommendations
        # target_price = info.get("targetMeanPrice")
        # analyst_count = info.get("numberOfAnalystOpinions")
        # recommendation = info.get("recommendationKey", "N/A").replace("_", " ").title()
        # target_high = info.get("targetHighPrice")
        # target_low = info.get("targetLowPrice")

        # if target_price:
        #     rec_text = (
        #         f"Analyst Consensus for {name}: Recommendation is '{recommendation}'. "
        #         f"Mean target price is ₹{target_price:.2f}"
        #     )
        #     if analyst_count:
        #         rec_text += f" across {analyst_count} analyst opinions"
        #     if target_high and target_low:
        #         rec_text += f". Target range: ₹{target_low:.2f} – ₹{target_high:.2f}."
            # context_chunks.append(rec_text)

    except Exception as e:
        logger.warning(f"yfinance data fetch failed for {ticker} ({nse_ticker}): {e}")
        context_chunks.append(
            f"Note: Real-time market data for '{ticker}' (NSE) could not be retrieved. "
            f"Analysis will be based on available news and qualitative context."
        )

    return context_chunks


async def get_enhanced_market_context(ticker: str) -> list[str]:
    """
    Async function to fetch comprehensive market context including:
    - yfinance data (prices, financials, historical)
    - Screener.com institutional metrics (PEG, ROCE, peer comparison)
    - Technical indicators (RSI, MACD, SMA20, SMA50, Bollinger Bands)
    - Additional growth and valuation metrics

    Returns a list of context strings ready for LLM injection.
    """
    from src.services.technical_analysis_engine import get_programmatic_technical_indicators

    # Get base market context from yfinance
    context_chunks = get_market_context(ticker)

    # Fetch and compute technical indicators
    try:
        price_history = get_price_history(ticker, period="3mo")
        if price_history and len(price_history) >= 50:
            tech_indicators = get_programmatic_technical_indicators(price_history)
            if "error" not in tech_indicators:
                tech_text = "Technical Indicators (Computed from price history):\n"
                tech_text += f"- Current Price: ₹{tech_indicators.get('current_price', 'N/A')}\n"
                tech_text += f"- RSI (14): {tech_indicators.get('RSI_14', 'N/A')}\n"
                tech_text += f"- SMA 20: ₹{tech_indicators.get('SMA_20', 'N/A')}\n"
                tech_text += f"- SMA 50: ₹{tech_indicators.get('SMA_50', 'N/A')}\n"
                tech_text += f"- MACD: {tech_indicators.get('MACD', 'N/A')}\n"
                tech_text += f"- MACD Signal: {tech_indicators.get('MACD_Signal', 'N/A')}\n"
                tech_text += f"- Bollinger Band Upper: ₹{tech_indicators.get('BB_Upper', 'N/A')}\n"
                tech_text += f"- Bollinger Band Lower: ₹{tech_indicators.get('BB_Lower', 'N/A')}\n"
                tech_text += f"- Trend: {tech_indicators.get('Trend_Analysis', 'N/A')}\n"
                tech_text += f"- Momentum: {tech_indicators.get('Momentum_Analysis', 'N/A')}"
                context_chunks.append(tech_text)
                logger.info(f"Technical indicators computed for {ticker}")
        else:
            logger.warning(f"Insufficient price history for technical analysis: {len(price_history) if price_history else 0} candles")
    except Exception as e:
        logger.warning(f"Failed to compute technical indicators for {ticker}: {e}")

    print("MARKET CONTEXT =")
    print("\n".join(context_chunks))
    
    # Try to enhance with screener metrics
    # try:
    #     from src.services.screener_service import (
    #         ScreenerService,
    #         enrich_with_screener_metrics
    #     )
    try:
        from src.services.screener_service import (
            ScreenerService,
            enrich_with_screener_metrics
        )

        print("IMPORT SUCCESS")
        print("CLASS =", ScreenerService)
        print(
            "METHOD =",
            hasattr(ScreenerService, "fetch_peer_comparison")
        )

        # Fetch screener institutional metrics
        context_chunks = await enrich_with_screener_metrics(ticker, context_chunks)
        print("AFTER ENRICH")
        print("REACHED PEER SECTION")
        print("TOTAL CHUNKS =", len(context_chunks))
        # Fetch peer comparison if sector is available
        sector = None
        print("CONTEXT CHUNKS =", context_chunks)
        print("CLASS =", ScreenerService)
        print("METHOD =", hasattr(ScreenerService, "fetch_peer_comparison"))
        print("IMPORTING SCREENER SERVICE"),
        for chunk in context_chunks:
            print("CHUNK START")
            print(chunk[:300])
            import re

            match = re.search(
             r'within the\s+([A-Za-z\s&]+?)\s+sector',
             chunk,
                re.IGNORECASE
              )

            if match:
                print("MATCH FOUND")
                print("SECTOR =", match.group(1))
                sector = match.group(1).strip()
                break
        print("DETECTED SECTOR =", sector)
        print("SECTOR BEFORE IF =", sector)
        print("SECTOR =", sector)
        if True:
            # peer_data = await ScreenerService.fetch_peer_comparison(
            #     ticker,
            #     sector
            # )
            try:
                peer_data = await ScreenerService.fetch_peer_comparison(
                    ticker,
                    sector
                )
            except Exception as e:
                print("ERROR INSIDE fetch_peer_comparison:", e)
                raise
            print(peer_data)
            print("CALLING PEER COMPARISON")
            print(type(peer_data))
            print(type(peer_data.get("peers")))
            print(peer_data)

            for i, peer in enumerate(peer_data["peers"]):
                print(i, type(peer), peer)
            if peer_data.get('peers'):
                self_data = peer_data.get("self", {})
                peer_names = []
                market_caps = []
                pes = []
                roes = []
                print("ENTERED IF BLOCK")
                print("=" * 80)
                print("PEER DATA =", peer_data)
                print("PEERS =", peer_data.get("peers"))
                print("PEER COUNT =", peer_data.get("peer_count"))
                print("=" * 80)
                for peer in peer_data.get("peers", []):
                    print("TYPE =", type(peer))
                    print("VALUE =", peer)

                    if not isinstance(peer, dict):
                        print("INVALID PEER FOUND!")
                        continue
                    peer_names.append(peer.get("name") or "N/A")
                    market_caps.append(peer.get("market_cap", "N/A"))
                    pes.append(peer.get("stock_pe", "N/A"))
                    roes.append(peer.get("roe", "N/A"))
                peer_text = (
                    f"| Metric | {ticker.upper()} | {' | '.join(peer_names)} |\n"
                    f"|---------|---------|{'|'.join(['---------'] * len(peer_names))}|\n"
                )
                peer_text += f"| Market Cap | {self_data.get('market_cap', 'N/A')} | {' | '.join(market_caps)} |\n"
                peer_text += f"| P/E Ratio | {self_data.get('stock_pe', 'N/A')} | {' | '.join(pes)} |\n"
                peer_text += f"| ROE | {self_data.get('roe', 'N/A')} | {' | '.join(roes)} |\n"

                context_chunks.append(peer_text)
                print("CONTEXT CHUNKS LENGTH =", len(context_chunks))
                print("LAST CONTEXT =", context_chunks[-1])
                print("PEER TEXT =", peer_text)
                print("FINAL CONTEXT CHUNKS =")
                print("INSIDE IF BLOCK")
                for chunk in context_chunks:
                    print(chunk)
        else:
            print("Skipping peer comparison due to missing sector")
#                 peer_text = "\n=== PEER COMPARISON ===\n"
# #                 peer_text = """
# # | Metric | TCS | Infosys | HCL Tech | Wipro |
# # |---------|---------|---------|---------|---------|
# # | Market Cap | ₹8.4L Cr | ₹6.5L Cr | ₹4L Cr | ₹2L Cr |
# # | P/E Ratio | 17.1 | 25 | 22 | 18 |
# # | ROE | 48.4% | 30% | 24% | 18% |
# # """
#                 context_chunks.append(peer_text)
#                 print("PEER TEXT =", peer_text)
#                 peer_text += f"Top competitors in {sector}:\n"
#                 for i, peer in enumerate(peer_data['peers'], 1):
#                     name = peer.get('name', 'Unknown')
#                     market_cap = peer.get('market_cap', 'N/A')
#                     pe = peer.get('stock_pe', 'N/A')
#                     roe = peer.get('roe', 'N/A')
#                     peer_text += f"{i}. {name} - Market Cap: {market_cap}, P/E: {pe}, ROE: {roe}\n"

    except ImportError:
        logger.warning("Screener service not available, using basic market context only")
    except Exception as e:
        logger.warning(f"Failed to fetch enhanced metrics for {ticker}: {e}")
    print("LAST CONTEXT CHUNK =", context_chunks[-1])
    print("AFTER LAST CONTEXT")
    return context_chunks


def get_price_history(ticker: str, period: str = "1mo") -> list[dict]:
    """
    Returns price history data for charting. Automatically appends .NS suffix.
    """
    nse_ticker = _to_nse_ticker(ticker)
    try:
        stock = yf.Ticker(nse_ticker)
        hist = stock.history(period=period)

        if hist.empty:
            # Try BSE fallback
            stock = yf.Ticker(ticker.upper() + ".BO")
            hist = stock.history(period=period)

        return [
            {
                "date": str(index.date()),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"])
            }
            for index, row in hist.iterrows()
        ]
    except Exception as e:
        logger.warning(f"Price history fetch failed for {ticker}: {e}")
        return []

def _format_inr(val: float) -> str:
    """Format raw float Rupees to string representation."""
    if val is None:
        return "N/A"
    return f"₹{val:,.2f}"

def _clean_and_normalize(val: Any, source: str, name: str) -> Optional[float]:
    if val is None:
        return None
    try:
        val_float = None
        if isinstance(val, (int, float)):
            val_float = float(val)
        elif isinstance(val, str):
            clean_str = val.replace("₹", "").replace("$", "").replace("x", "").replace("%", "").replace(",", "").strip()
            if clean_str.lower() in ("n/a", "none", "", "—", "data unavailable"):
                return None
            val_float = float(clean_str)
        else:
            val_float = float(val)

        # Finite checks
        import math
        if not math.isfinite(val_float):
            return None

        # Provider-specific normalization
        src_lower = source.lower()
        if name in ("dividend_yield", "roe", "roce", "profit_margin", "operating_margin", "fcf_yield"):
            if "screener" in src_lower or "finnhub" in src_lower:
                return val_float / 100.0
        elif name == "market_cap" and "finnhub" in src_lower:
            # Finnhub market cap is in millions, convert to raw float units
            return val_float * 1e6
            
        return val_float
    except Exception:
        return None

# Centralized Metric Registry Configuration
METRIC_REGISTRY = {
    "company_name": {
        "preferred_providers": ["yFinance", "Screener", "Finnhub"],
        "tolerance": 0.0,
        "sanity_range": None,
        "formatter": lambda val: str(val) if val is not None else "Unavailable",
        "normalize": lambda val, source: val
    },
    "current_price": {
        "preferred_providers": ["yFinance", "Finnhub", "Screener"],
        "tolerance": 0.01,
        "sanity_range": (0.01, 10000000.0),
        "formatter": lambda val: f"₹{val:,.2f}" if val is not None else "Unavailable",
        "normalize": lambda val, source: _clean_and_normalize(val, source, "current_price")
    },
    "change_percent": {
        "preferred_providers": ["yFinance", "Finnhub"],
        "tolerance": 0.05,
        "sanity_range": (-100.0, 1000.0),
        "formatter": lambda val: f"{val:.2f}%" if val is not None else "Unavailable",
        "normalize": lambda val, source: _clean_and_normalize(val, source, "change_percent")
    },
    "fifty_two_week_high": {
        "preferred_providers": ["yFinance", "Screener", "Finnhub"],
        "tolerance": 0.05,
        "sanity_range": (0.01, 10000000.0),
        "formatter": lambda val: f"₹{val:,.2f}" if val is not None else "Unavailable",
        "normalize": lambda val, source: _clean_and_normalize(val, source, "fifty_two_week_high")
    },
    "fifty_two_week_low": {
        "preferred_providers": ["yFinance", "Screener", "Finnhub"],
        "tolerance": 0.05,
        "sanity_range": (0.01, 10000000.0),
        "formatter": lambda val: f"₹{val:,.2f}" if val is not None else "Unavailable",
        "normalize": lambda val, source: _clean_and_normalize(val, source, "fifty_two_week_low")
    },
    "market_cap": {
        "preferred_providers": ["Screener", "yFinance", "Finnhub"],
        "tolerance": 0.05,
        "sanity_range": (0.01, 1e16),
        "formatter": lambda val: f"₹{val / 10000000:,.2f} Cr" if val is not None else "Unavailable",
        "normalize": lambda val, source: _clean_and_normalize(val, source, "market_cap")
    },
    "pe_ratio": {
        "preferred_providers": ["Screener", "yFinance", "Finnhub"],
        "tolerance": 0.05,
        "sanity_range": (-100.0, 1000.0),
        "formatter": lambda val: f"{val:.2f}x" if val is not None else "Unavailable",
        "normalize": lambda val, source: _clean_and_normalize(val, source, "pe_ratio")
    },
    "pb_ratio": {
        "preferred_providers": ["Screener", "yFinance", "Finnhub"],
        "tolerance": 0.05,
        "sanity_range": (0.0, 100.0),
        "formatter": lambda val: f"{val:.2f}x" if val is not None else "Unavailable",
        "normalize": lambda val, source: _clean_and_normalize(val, source, "pb_ratio")
    },
    "book_value": {
        "preferred_providers": ["yFinance", "Screener", "Finnhub"],
        "tolerance": 0.05,
        "sanity_range": (-1000.0, 1000000.0),
        "formatter": lambda val: f"₹{val:,.2f}" if val is not None else "Unavailable",
        "normalize": lambda val, source: _clean_and_normalize(val, source, "book_value")
    },
    "eps": {
        "preferred_providers": ["yFinance", "Screener", "Finnhub"],
        "tolerance": 0.05,
        "sanity_range": (-1000.0, 100000.0),
        "formatter": lambda val: f"₹{val:,.2f}" if val is not None else "Unavailable",
        "normalize": lambda val, source: _clean_and_normalize(val, source, "eps")
    },
    "dividend_yield": {
        "preferred_providers": ["Screener", "yFinance", "Finnhub"],
        "tolerance": 0.10,
        "sanity_range": (0.0, 0.15),
        "formatter": lambda val: f"{val * 100:.2f}%" if val is not None else "Unavailable",
        "normalize": lambda val, source: _clean_and_normalize(val, source, "dividend_yield")
    },
    "roe": {
        "preferred_providers": ["Screener", "yFinance", "Finnhub"],
        "tolerance": 0.05,
        "sanity_range": (-1.0, 1.0),
        "formatter": lambda val: f"{val * 100:.2f}%" if val is not None else "Unavailable",
        "normalize": lambda val, source: _clean_and_normalize(val, source, "roe")
    },
    "roce": {
        "preferred_providers": ["Screener", "Programmatic yFinance", "yFinance"],
        "tolerance": 0.05,
        "sanity_range": (-1.0, 1.0),
        "formatter": lambda val: f"{val * 100:.2f}%" if val is not None else "Unavailable",
        "normalize": lambda val, source: _clean_and_normalize(val, source, "roce")
    },
    "debt_to_equity": {
        "preferred_providers": ["Screener", "yFinance", "Finnhub"],
        "tolerance": 0.05,
        "sanity_range": (0.0, 2.5),
        "formatter": lambda val: f"{val:.2f}x" if val is not None else "Unavailable",
        "normalize": lambda val, source: _clean_and_normalize(val, source, "debt_to_equity")
    },
    "peg_ratio": {
        "preferred_providers": ["Screener", "yFinance", "Finnhub"],
        "tolerance": 0.05,
        "sanity_range": (0.0, 50.0),
        "formatter": lambda val: f"{val:.2f}x" if val is not None else "Unavailable",
        "normalize": lambda val, source: _clean_and_normalize(val, source, "peg_ratio")
    },
    "enterprise_value": {
        "preferred_providers": ["yFinance", "Screener"],
        "tolerance": 0.05,
        "sanity_range": (0.01, 1e16),
        "formatter": lambda val: _format_inr(val),
        "normalize": lambda val, source: _clean_and_normalize(val, source, "enterprise_value")
    },
    "operating_cash_flow": {
        "preferred_providers": ["yFinance", "Screener"],
        "tolerance": 0.05,
        "sanity_range": (-1e16, 1e16),
        "formatter": lambda val: _format_inr(val),
        "normalize": lambda val, source: _clean_and_normalize(val, source, "operating_cash_flow")
    },
    "free_cash_flow": {
        "preferred_providers": ["yFinance", "Screener"],
        "tolerance": 0.05,
        "sanity_range": (-1e16, 1e16),
        "formatter": lambda val: _format_inr(val),
        "normalize": lambda val, source: _clean_and_normalize(val, source, "free_cash_flow")
    },
    "annual_revenue": {
        "preferred_providers": ["yFinance", "Screener"],
        "tolerance": 0.05,
        "sanity_range": (0.01, 1e16),
        "formatter": lambda val: _format_inr(val),
        "normalize": lambda val, source: _clean_and_normalize(val, source, "annual_revenue")
    },
    "net_income": {
        "preferred_providers": ["yFinance", "Screener"],
        "tolerance": 0.05,
        "sanity_range": (-1e16, 1e16),
        "formatter": lambda val: _format_inr(val),
        "normalize": lambda val, source: _clean_and_normalize(val, source, "net_income")
    },
    "rsi_14": {
        "preferred_providers": ["Programmatic yFinance"],
        "tolerance": 0.0,
        "sanity_range": (0.0, 100.0),
        "formatter": lambda val: f"{val:.2f}" if val is not None else "Unavailable",
        "normalize": lambda val, source: _clean_and_normalize(val, source, "rsi_14")
    },
    "sma_20": {
        "preferred_providers": ["Programmatic yFinance"],
        "tolerance": 0.0,
        "sanity_range": (0.01, 10000000.0),
        "formatter": lambda val: f"₹{val:,.2f}" if val is not None else "Unavailable",
        "normalize": lambda val, source: _clean_and_normalize(val, source, "sma_20")
    },
    "sma_50": {
        "preferred_providers": ["Programmatic yFinance"],
        "tolerance": 0.0,
        "sanity_range": (0.01, 10000000.0),
        "formatter": lambda val: f"₹{val:,.2f}" if val is not None else "Unavailable",
        "normalize": lambda val, source: _clean_and_normalize(val, source, "sma_50")
    },
    "macd": {
        "preferred_providers": ["Programmatic yFinance"],
        "tolerance": 0.0,
        "sanity_range": None,
        "formatter": lambda val: f"{val:.4f}" if val is not None else "Unavailable",
        "normalize": lambda val, source: _clean_and_normalize(val, source, "macd")
    },
    "macd_signal": {
        "preferred_providers": ["Programmatic yFinance"],
        "tolerance": 0.0,
        "sanity_range": None,
        "formatter": lambda val: f"{val:.4f}" if val is not None else "Unavailable",
        "normalize": lambda val, source: _clean_and_normalize(val, source, "macd_signal")
    },
    "technical_trend": {
        "preferred_providers": ["Programmatic yFinance"],
        "tolerance": 0.0,
        "sanity_range": None,
        "formatter": lambda val: str(val) if val is not None else "Unavailable",
        "normalize": lambda val, source: val
    },
    "technical_momentum": {
        "preferred_providers": ["Programmatic yFinance"],
        "tolerance": 0.0,
        "sanity_range": None,
        "formatter": lambda val: str(val) if val is not None else "Unavailable",
        "normalize": lambda val, source: val
    }
}

def resolve_metric_consensus(
    name: str,
    raw_provider_vals: Dict[str, Any],
    provider_health: Dict[str, str]
) -> dict:
    """
    Consensus Stage: Resolves conflicting metric values dynamically using the METRIC_REGISTRY configuration.
    """
    from datetime import datetime

    registry = METRIC_REGISTRY.get(name)
    if not registry:
        registry = {
            "preferred_providers": list(raw_provider_vals.keys()),
            "tolerance": 0.05,
            "sanity_range": None,
            "formatter": lambda val: str(val) if val is not None else "Unavailable",
            "normalize": lambda val, source: val
        }

    # Normalize metrics from healthy providers
    normalized_values = {}
    raw_values = {}
    for prov, val in raw_provider_vals.items():
        if val is not None:
            health = provider_health.get(prov, "HEALTHY")
            if health != "HEALTHY":
                logger.warning(f"[PROVIDER IGNORED] Metric {name} from {prov} ignored because provider health is {health}")
                continue
            
            norm_val = registry["normalize"](val, prov)
            if norm_val is not None:
                normalized_values[prov] = norm_val
                raw_values[prov] = val

    # Determine Winner
    selected_val = None
    selected_provider = None
    for p in registry["preferred_providers"]:
        if p in normalized_values:
            selected_val = normalized_values[p]
            selected_provider = p
            break

    # If no data is available
    if selected_val is None:
        timestamp = datetime.utcnow().isoformat()
        return {
            "value": None,
            "source": "N/A",
            "timestamp": timestamp,
            "confidence": 0.0,
            "raw_value": None,
            "normalized_value": None,
            "display_value": "Unavailable",
            "validation_status": "MISSING",
            "other_provider_values": {},
            "selected_provider": "N/A",
            "validation_reason": "No data available from any healthy provider"
        }

    # Calculate difference, determine status, and confidence
    validation_status = "PASS"
    validation_reason = "Within expected sanity range and matching tolerances."
    other_provider_values = {}
    
    for prov, p_val in normalized_values.items():
        if prov != selected_provider:
            other_provider_values[prov] = p_val

    diff_percent = 0.0
    if len(normalized_values) == 1:
        validation_status = "SINGLE_SOURCE"
        confidence = 0.8
        validation_reason = f"Only one healthy provider ({selected_provider}) returned data."
    else:
        # Multiple providers exist, compare differences
        has_warning = False
        exceeded_msg = ""
        for prov, p_val in normalized_values.items():
            if prov != selected_provider:
                diff = 0.0
                if selected_val != 0.0:
                    diff = abs(selected_val - p_val) / abs(selected_val)
                elif p_val != 0.0:
                    diff = abs(selected_val - p_val) / abs(p_val)
                
                diff_percent = max(diff_percent, diff)

                tol = registry["tolerance"]
                if tol > 0.0 and diff > tol:
                    has_warning = True
                    exceeded_msg = (
                        f"Provider mismatch: {selected_provider} ({selected_val}) vs "
                        f"{prov} ({p_val}) differs by {diff*100:.2f}%, which exceeds "
                        f"tolerance of {tol*100:.1f}%."
                    )
                    break
        
        if has_warning:
            validation_status = "WARNING"
            confidence = 0.5
            validation_reason = exceeded_msg
        else:
            validation_status = "PASS"
            confidence = 1.0

    # Adjust confidence if any provider is unhealthy
    for prov, health in provider_health.items():
        if health != "HEALTHY" and prov in registry["preferred_providers"]:
            confidence = round(max(0.1, confidence - 0.1), 2)

    # Format Display Value
    display_value = registry["formatter"](selected_val)

    # Output structured logging exactly matching the required layout
    pe_title = name.replace("_", " ").title()
    if name == "pe_ratio":
        pe_title = "PE Ratio"
    elif name == "pb_ratio":
        pe_title = "Price to Book"
    elif name == "peg_ratio":
        pe_title = "PEG Ratio"
    elif name == "dividend_yield":
        pe_title = "Dividend Yield"

    provider_outputs = []
    for prov, p_val in normalized_values.items():
        provider_outputs.append(f"{prov}:\n{p_val:.2f}" if isinstance(p_val, (int, float)) else f"{prov}:\n{p_val}")

    provider_section = "\n\n".join(provider_outputs)
    diff_pct_str = f"{diff_percent * 100:.2f}%" if len(normalized_values) > 1 else "N/A"

    log_str = (
        f"\nPROVIDER CONSENSUS\n"
        f"Metric:\n{pe_title}\n\n"
        f"{provider_section}\n\n"
        f"Difference:\n{diff_pct_str}\n\n"
        f"Winner:\n{selected_provider}\n\n"
        f"Confidence:\n{confidence:.1f}\n\n"
        f"Status:\n{validation_status}\n"
    )
    print(log_str)
    logger.info(log_str)

    timestamp = datetime.utcnow().isoformat()
    display_value = registry["formatter"](selected_val)

    normalized_value = (
        float(selected_val)
        if isinstance(selected_val, (int, float))
        else None
    )
    return {
        "value": selected_val,
        "source": selected_provider,
        "timestamp": timestamp,
        "confidence": confidence,
        "source_url": None,
        "raw_value": raw_values.get(selected_provider),
        "normalized_value": normalized_value,
        "display_value": display_value,
        "validation_status": validation_status,
        "other_provider_values": other_provider_values,
        "selected_provider": selected_provider,
        "validation_reason": validation_reason
    }

def validate_grounded_metric(
    name: str,
    yfinance_val: Any = None,
    screener_val: Any = None,
    calculated_val: Any = None,
    sector: Optional[str] = None,
    finnhub_val: Any = None
) -> dict:
    """
    Validation Stage: Checks sanity boundaries and sector-aware limits.
    """
    if isinstance(yfinance_val, dict) and "validation_status" in yfinance_val:
        consensus_res = yfinance_val
    else:
        # Backward compatibility mode
        raw_vals = {}
        if yfinance_val is not None:
            raw_vals["yFinance"] = yfinance_val
        if screener_val is not None:
            raw_vals["Screener"] = screener_val
        if calculated_val is not None:
            raw_vals["Programmatic yFinance"] = calculated_val
        if finnhub_val is not None:
            raw_vals["Finnhub"] = finnhub_val
        
        health = {k: "HEALTHY" for k in raw_vals.keys()}
        consensus_res = resolve_metric_consensus(name, raw_vals, health)

    registry = METRIC_REGISTRY.get(name)
    if not registry or not registry.get("sanity_range"):
        return consensus_res

    # Check boundaries
    min_val, max_val = registry["sanity_range"]
    
    if name == "debt_to_equity" and sector:
        sec_lower = sector.lower()
        if any(kw in sec_lower for kw in ("financial", "bank", "lending", "insurance")):
            max_val = 6.0
            logger.info(f"Sector-aware boundary applied to debt_to_equity for financial sector '{sector}': [0.0, 6.0]")

    selected_val = consensus_res["value"]
    validation_status = consensus_res["validation_status"]
    validation_reason = consensus_res["validation_reason"]
    confidence = consensus_res["confidence"]

    if selected_val is not None:
        if selected_val < min_val or selected_val > max_val:
            validation_status = "FAIL"
            validation_reason = f"Value {selected_val} is outside sanity boundaries [{min_val}, {max_val}]."
            confidence = 0.1
            logger.warning(
                f"[VALIDATION FAIL] Metric '{name}' value {selected_val} is outside expected range [{min_val}, {max_val}]. "
                f"Setting validation_status to FAIL."
            )

    display_value = consensus_res["display_value"]
    final_value = selected_val
    if validation_status == "FAIL":
        final_value = None
        display_value = "Unavailable"

    return {
        "value": final_value,
        "source": consensus_res["source"],
        "timestamp": consensus_res["timestamp"],
        "confidence": confidence,
        "source_url": consensus_res["source_url"],
        "raw_value": consensus_res["raw_value"],
        "normalized_value": consensus_res["normalized_value"],
        "display_value": display_value,
        "validation_status": validation_status,
        "other_provider_values": consensus_res["other_provider_values"],
        "selected_provider": consensus_res["selected_provider"],
        "validation_reason": validation_reason
    }


def normalize_and_validate_financial_metric(name: str, val: Any, source: str) -> dict:
    return validate_grounded_metric(name, val, None, None)


def validate_and_normalize_metric(name: str, val: Any) -> Optional[Any]:
    res = validate_grounded_metric(name, val, None, None)
    return res["value"]


def create_grounded_metric(value: Any, source: str, priority_tier: str) -> Optional[dict]:
    if value is None:
        return None
    confidence = 1.0
    if priority_tier == "Tier 2":
        confidence = 0.8
    elif priority_tier == "Tier 3":
        confidence = 0.6
    elif priority_tier == "Tier 4":
        confidence = 0.7
    from datetime import datetime
    return {
        "value": value,
        "source": source,
        "timestamp": datetime.utcnow().isoformat(),
        "confidence": confidence,
        "source_url": None,
        "raw_value": value,
        "normalized_value": value,
        "display_value": str(value),
        "validation_status": "PASS",
        "other_provider_values": None,
        "selected_provider": source,
        "validation_reason": "Direct creation"
    }


async def get_grounding_data(ticker: str) -> dict:
    """
    Fetches, normalizes, and constructs the structured StockGroundingData.
    Implements validation rules, conflict resolutions, and technical indicator calculations.
    """
    from src.agents.schemas import StockGroundingData, GroundingPeerItem, GroundingHistoricalReport
    from src.services.screener_service import ScreenerService
    from src.services.technical_analysis_engine import get_programmatic_technical_indicators
    from typing import Any

    nse_ticker = _to_nse_ticker(ticker)
    ticker_upper = ticker.upper().strip()

    # Initialize defaults
    data = {
        "ticker": ticker_upper,
        "company_name": ticker_upper,
        "exchange": "NSE",
        "peers": [],
        "quarterly_reports": [],
        "annual_reports": []
    }

    try:
        stock = yf.Ticker(nse_ticker)
        info = stock.info

        if not info or info.get("quoteType") is None:
            # try BSE fallback
            bse_ticker = ticker_upper + ".BO"
            stock = yf.Ticker(bse_ticker)
            info = stock.info
            data["exchange"] = "BSE"

        if info:
            sector = info.get("sector")
            screener_all = {}

            # Fetch Screener metrics in parallel/sequence
            try:
                screener_metrics = await ScreenerService.fetch_company_metrics(ticker_upper)
                if screener_metrics:
                    screener_all.update(screener_metrics)
            except Exception as e:
                logger.warning(f"Screener company metrics fetch failed for {ticker_upper}: {e}")

            try:
                enhanced_metrics = await ScreenerService.fetch_enhanced_metrics(ticker_upper)
                if enhanced_metrics:
                    screener_all.update(enhanced_metrics)
            except Exception as e:
                logger.warning(f"Screener enhanced metrics fetch failed for {ticker_upper}: {e}")

            # Fetch Finnhub metrics in parallel
            finnhub_quote = {}
            finnhub_financials = {}
            provider_health = {"yFinance": "HEALTHY", "Screener": "HEALTHY", "Finnhub": "HEALTHY"}

            try:
                from src.services.finnhub_service import FinnhubService
                from src.services.entity_resolver import EntityResolver
                resolved_ticker, _ = await EntityResolver.resolve(ticker_upper)
                clean_symbol = resolved_ticker or ticker_upper
                
                finnhub_quote, finnhub_financials = await asyncio.gather(
                    FinnhubService.fetch_quote(clean_symbol),
                    FinnhubService.fetch_financials(clean_symbol)
                )
                if not finnhub_quote and not finnhub_financials:
                    provider_health["Finnhub"] = "UNAVAILABLE"
                    logger.warning(f"[PROVIDER HEALTH] Finnhub returned empty responses -> UNAVAILABLE")
            except asyncio.TimeoutError:
                provider_health["Finnhub"] = "TIMEOUT"
                logger.warning(f"[PROVIDER HEALTH] Finnhub request timed out -> TIMEOUT")
            except Exception as e:
                provider_health["Finnhub"] = "UNAVAILABLE"
                logger.warning(f"[PROVIDER HEALTH] Finnhub fetch failed: {e} -> UNAVAILABLE")

            # yfinance health check
            if not info or info.get("quoteType") is None:
                provider_health["yFinance"] = "UNAVAILABLE"
                logger.warning(f"[PROVIDER HEALTH] yFinance returned no info -> UNAVAILABLE")

            # Screener health check
            if not screener_all:
                provider_health["Screener"] = "UNAVAILABLE"
                logger.warning(f"[PROVIDER HEALTH] Screener returned no data -> UNAVAILABLE")

            # Calculated values
            calc_values = {}
            try:
                ebit = None
                ann_fin = stock.financials
                if ann_fin is not None and not ann_fin.empty:
                    ann_fin_t = ann_fin.T
                    def find_col(df, keywords):
                        for c in df.columns:
                            c_str = str(c).lower()
                            if any(kw in c_str for kw in keywords):
                                return c
                        return None
                    ebit_col = find_col(ann_fin_t, ["operating income", "ebit"])
                    if ebit_col:
                        ebit = ann_fin_t[ebit_col].iloc[0]

                bal_sheet = stock.balance_sheet
                if bal_sheet is not None and not bal_sheet.empty:
                    bal_sheet_t = bal_sheet.T
                    assets_col = find_col(bal_sheet_t, ["total assets", "assets"])
                    curr_liab_col = find_col(bal_sheet_t, ["total current liabilities", "current liabilities"])

                    if assets_col:
                        total_assets = bal_sheet_t[assets_col].iloc[0]
                        curr_liab = bal_sheet_t[curr_liab_col].iloc[0] if curr_liab_col else 0
                        cap_employed = total_assets - curr_liab
                        if cap_employed and ebit is not None:
                            calc_values["roce"] = ebit / cap_employed
            except Exception as e:
                logger.warning(f"Calculated ROCE computation failed: {e}")

            # Define per-metric sources
            prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
            curr_price = info.get("currentPrice") or info.get("regularMarketPrice")
            chg = None
            if curr_price and prev_close:
                chg = ((curr_price - prev_close) / prev_close) * 100

            target_mappings = {
                "company_name": (info.get("longName") or info.get("shortName") or ticker_upper, screener_all.get("company_name"), None),
                "current_price": (curr_price, screener_all.get("current_price"), None),
                "change_percent": (chg, None, None),
                "fifty_two_week_high": (info.get("fiftyTwoWeekHigh"), screener_all.get("fifty_two_week_high"), None),
                "fifty_two_week_low": (info.get("fiftyTwoWeekLow"), screener_all.get("fifty_two_week_low"), None),
                "market_cap": (info.get("marketCap"), screener_all.get("market_cap"), None),
                "pe_ratio": (info.get("trailingPE"), screener_all.get("stock_pe"), None),
                "pb_ratio": (info.get("priceToBook"), screener_all.get("pb_ratio"), None),
                "book_value": (info.get("bookValue"), screener_all.get("book_value"), None),
                "eps": (info.get("trailingEps"), screener_all.get("eps"), None),
                "dividend_yield": (info.get("dividendYield"), screener_all.get("dividend_yield"), None),
                "roe": (info.get("returnOnEquity"), screener_all.get("roe"), None),
                "roce": (None, screener_all.get("roce"), calc_values.get("roce")),
                "debt_to_equity": (info.get("debtToEquity"), screener_all.get("debt_to_equity"), None),
                "peg_ratio": (info.get("pegRatio"), screener_all.get("peg_ratio"), None),
                "enterprise_value": (info.get("enterpriseValue"), screener_all.get("enterprise_value"), None),
                "operating_cash_flow": (info.get("operatingCashflow"), screener_all.get("operating_cash_flow"), None),
                "free_cash_flow": (info.get("freeCashflow"), screener_all.get("free_cash_flow"), None),
                "annual_revenue": (info.get("totalRevenue"), screener_all.get("annual_revenue"), None),
                "net_income": (info.get("netIncomeToCommon") or info.get("netIncome"), screener_all.get("net_income"), None),
            }

            # Map Finnhub metric values
            fin_metric = finnhub_financials.get("metric", {})
            finnhub_vals = {
                "company_name": None,
                "current_price": finnhub_quote.get("c"),
                "change_percent": None,
                "fifty_two_week_high": fin_metric.get("52WeekHigh"),
                "fifty_two_week_low": fin_metric.get("52WeekLow"),
                "market_cap": fin_metric.get("marketCapitalization"),
                "pe_ratio": fin_metric.get("peTTM") or fin_metric.get("peExclExtraTTM"),
                "pb_ratio": fin_metric.get("pb"),
                "book_value": fin_metric.get("bookValuePerShareQuarterly") or fin_metric.get("bookValuePerShareAnnual"),
                "eps": fin_metric.get("epsTTM"),
                "dividend_yield": fin_metric.get("currentDividendYieldTTM"),
                "roe": fin_metric.get("roeTTM"),
                "roce": None,
                "debt_to_equity": fin_metric.get("totalDebt/totalEquityQuarterly"),
                "peg_ratio": fin_metric.get("pegTTM") or fin_metric.get("forwardPEG"),
                "enterprise_value": None,
                "operating_cash_flow": None,
                "free_cash_flow": None,
                "annual_revenue": None,
                "net_income": None,
            }

            # Run cross-provider validation engine for target metrics
            for name in target_mappings.keys():
                yf_val, scr_val, calc_val = target_mappings[name]
                fh_val = finnhub_vals.get(name)

                # Build provider mappings
                raw_vals = {}
                if yf_val is not None:
                    raw_vals["yFinance"] = yf_val
                if scr_val is not None:
                    raw_vals["Screener"] = scr_val
                if calc_val is not None:
                    raw_vals["Programmatic yFinance"] = calc_val
                if fh_val is not None:
                    raw_vals["Finnhub"] = fh_val

                # 1. Consensus Stage
                consensus_res = resolve_metric_consensus(name, raw_vals, provider_health)

                # 2. Validation Stage
                res = validate_grounded_metric(name, consensus_res, sector)

                if name == "company_name":
                    data["company_name"] = str(res["value"]) if res["value"] is not None else ticker_upper
                else:
                    data[name] = res

            # Get technical indicators
            try:
                price_history = get_price_history(ticker_upper, period="3mo")
                if price_history and len(price_history) >= 50:
                    tech_indicators = get_programmatic_technical_indicators(price_history)
                    if "error" not in tech_indicators:
                        for k, v in [
                            ("rsi_14", tech_indicators.get("RSI_14")),
                            ("sma_20", tech_indicators.get("SMA_20")),
                            ("sma_50", tech_indicators.get("SMA_50")),
                            ("macd", tech_indicators.get("MACD")),
                            ("macd_signal", tech_indicators.get("MACD_Signal")),
                            ("technical_trend", tech_indicators.get("Trend_Analysis", "Neutral")),
                            ("technical_momentum", tech_indicators.get("Momentum_Analysis", "Neutral")),
                        ]:
                            data[k] = validate_grounded_metric(k, None, None, v)
            except Exception as e:
                logger.warning(f"Technical indicators calculation failed: {e}")

            # Peer Comparison (Tier 4 priority for peer lists)
            try:
                if sector:
                    peer_data = await ScreenerService.fetch_peer_comparison(ticker_upper, sector)
                    if peer_data and peer_data.get("peers"):
                        for peer in peer_data["peers"]:
                            data["peers"].append(GroundingPeerItem(
                                ticker=peer.get("ticker", ""),
                                name=peer.get("name", "Unknown"),
                                market_cap=peer.get("market_cap", "N/A"),
                                stock_pe=peer.get("stock_pe", "N/A"),
                                roe=peer.get("roe", "N/A")
                            ))
            except Exception as e:
                logger.warning(f"Peers calculation failed: {e}")

            # Quarterly Reports Ingestion
            try:
                q_fin = stock.quarterly_financials
                if q_fin is not None and not q_fin.empty:
                    q_fin_t = q_fin.T
                    def find_col(df, keywords):
                        for c in df.columns:
                            c_str = str(c).lower()
                            if any(kw in c_str for kw in keywords):
                                return c
                        return None
                    rev_col = find_col(q_fin_t, ["total revenue", "revenue"])
                    net_col = find_col(q_fin_t, ["net income"])
                    gross_col = find_col(q_fin_t, ["gross profit"])
                    op_col = find_col(q_fin_t, ["operating income"])

                    for index, row in q_fin_t.head(4).iterrows():
                        date_str = index.strftime('%Y-%m-%d') if hasattr(index, 'strftime') else str(index)
                        r_val = row.get(rev_col) if rev_col else None
                        n_val = row.get(net_col) if net_col else None
                        g_val = row.get(gross_col) if gross_col else None
                        o_val = row.get(op_col) if op_col else None

                        g_margin = f"{(g_val / r_val) * 100:.2f}%" if g_val is not None and r_val else "N/A"
                        o_margin = f"{(o_val / r_val) * 100:.2f}%" if o_val is not None and r_val else "N/A"
                        n_margin = f"{(n_val / r_val) * 100:.2f}%" if n_val is not None and r_val else "N/A"

                        data["quarterly_reports"].append(GroundingHistoricalReport(
                            date=date_str,
                            revenue=_format_inr(r_val),
                            net_income=_format_inr(n_val),
                            gross_margin=g_margin,
                            operating_margin=o_margin,
                            net_margin=n_margin
                        ))
            except Exception as e:
                logger.warning(f"Quarterly financials ingestion failed: {e}")

            # Annual Reports Ingestion
            try:
                ann_fin = stock.financials
                if ann_fin is not None and not ann_fin.empty:
                    ann_fin_t = ann_fin.T
                    def find_col(df, keywords):
                        for c in df.columns:
                            c_str = str(c).lower()
                            if any(kw in c_str for kw in keywords):
                                return c
                        return None
                    rev_col = find_col(ann_fin_t, ["total revenue", "revenue"])
                    net_col = find_col(ann_fin_t, ["net income"])
                    gross_col = find_col(ann_fin_t, ["gross profit"])
                    op_col = find_col(ann_fin_t, ["operating income"])

                    for index, row in ann_fin_t.head(4).iterrows():
                        date_str = index.strftime('%Y-%m-%d') if hasattr(index, 'strftime') else str(index)
                        r_val = row.get(rev_col) if rev_col else None
                        n_val = row.get(net_col) if net_col else None
                        g_val = row.get(gross_col) if gross_col else None
                        o_val = row.get(op_col) if op_col else None

                        g_margin = f"{(g_val / r_val) * 100:.2f}%" if g_val is not None and r_val else "N/A"
                        o_margin = f"{(o_val / r_val) * 100:.2f}%" if o_val is not None and r_val else "N/A"
                        n_margin = f"{(n_val / r_val) * 100:.2f}%" if n_val is not None and r_val else "N/A"

                        data["annual_reports"].append(GroundingHistoricalReport(
                            date=date_str,
                            revenue=_format_inr(r_val),
                            net_income=_format_inr(n_val),
                            gross_margin=g_margin,
                            operating_margin=o_margin,
                            net_margin=n_margin
                        ))
            except Exception as e:
                logger.warning(f"Annual financials ingestion failed: {e}")

    except Exception as e:
        logger.error(f"yfinance/Screener grounding fetch failed: {e}")

    # Enforce Pydantic validation
    try:
        validated_model = StockGroundingData(**data)
        return validated_model.model_dump()
    except Exception as e:
        logger.error(f"Grounding Pydantic validation failed: {e}")
        return data
