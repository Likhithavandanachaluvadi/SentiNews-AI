import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class PromptContextBuilder:
    """
    Dedicated Prompt Context Builder service.
    Compiles verified grounding data, news timelines, and validation metadata
    into a structured prompt context to guide downstream LLM analysts.
    """
    
    @staticmethod
    def build(
        query: str,
        grounding_data: dict,
        news_articles: list,
        retrieval_context: Optional[list] = None
    ) -> str:
        if not grounding_data:
            grounding_data = {}
        if not retrieval_context:
            retrieval_context = []

        # =================================================
        # 1. COMPANY OVERVIEW
        # =================================================
        company = grounding_data.get("company_name", "Data unavailable.")
        if isinstance(company, dict):
            company = company.get("value") or "Data unavailable."
        
        ticker = grounding_data.get("ticker", "Data unavailable.")
        if isinstance(ticker, dict):
            ticker = ticker.get("value") or "Data unavailable."

        # Prefer structured sector/industry if present in grounding_data
        sector = grounding_data.get("sector")
        industry = grounding_data.get("industry")
        
        if isinstance(sector, dict):
            sector = sector.get("value")
        if isinstance(industry, dict):
            industry = industry.get("value")

        # Fall back to retrieval_context if unavailable
        if not sector or sector == "Data unavailable.":
            sector = "Data unavailable."
            for c in retrieval_context:
                c_str = str(c).strip()
                if c_str.startswith("Sector:"):
                    sector = c_str.split("Sector:", 1)[1].strip()
                    break

        if not industry or industry == "Data unavailable.":
            industry = "Data unavailable."
            for c in retrieval_context:
                c_str = str(c).strip()
                if c_str.startswith("Industry:"):
                    industry = c_str.split("Industry:", 1)[1].strip()
                    break

        # =================================================
        # 2. VERIFIED FUNDAMENTALS
        # =================================================
        fundamentals_list = []
        metrics_mapping = [
            ("current_price", "Current Price"),
            ("market_cap", "Market Cap"),
            ("pe_ratio", "PE"),
            ("pb_ratio", "PB"),
            ("eps", "EPS"),
            ("dividend_yield", "Dividend Yield"),
            ("roe", "ROE"),
            ("roce", "ROCE"),
            ("debt_to_equity", "Debt to Equity")
        ]
        
        for key, label in metrics_mapping:
            metric = grounding_data.get(key)
            if metric and isinstance(metric, dict):
                val = metric.get("display_value")
                prov = metric.get("source", "N/A")
                conf = metric.get("confidence", 0.0)
                status = metric.get("validation_status", "PASS")
                
                if val is None or val == "Unavailable":
                    fundamentals_list.append(f"{label}:\nData unavailable.")
                else:
                    fundamentals_list.append(
                        f"{label}:\n"
                        f"  Value: {val}\n"
                        f"  Provider: {prov}\n"
                        f"  Confidence: {conf:.1f}\n"
                        f"  Validation Status: {status}"
                    )
            else:
                fundamentals_list.append(f"{label}:\nData unavailable.")
        
        fundamentals_str = "\n\n".join(fundamentals_list)

        # =================================================
        # 3. TECHNICAL ANALYSIS
        # =================================================
        tech_indicators = {
            "technical_trend": "Trend",
            "rsi_14": "RSI",
            "sma_20": "SMA 20",
            "sma_50": "SMA 50"
        }
        
        tech_vals = {}
        for key in tech_indicators.keys():
            metric = grounding_data.get(key)
            if metric and isinstance(metric, dict):
                tech_vals[key] = metric.get("display_value") or "Data unavailable."
            else:
                tech_vals[key] = "Data unavailable."
                
        trend = tech_vals.get("technical_trend", "Data unavailable.")
        rsi = tech_vals.get("rsi_14", "Data unavailable.")
        
        # Combine SMAs for Moving Averages
        sma20_val = tech_vals.get("sma_20", "Data unavailable.")
        sma50_val = tech_vals.get("sma_50", "Data unavailable.")
        moving_averages = f"SMA 20: {sma20_val} and SMA 50: {sma50_val}"
        if sma20_val == "Data unavailable." and sma50_val == "Data unavailable.":
            moving_averages = "Data unavailable."

        # Support and Resistance fallbacks
        support = "Data unavailable."
        resistance = "Data unavailable."
        for c in retrieval_context:
            c_str = str(c).strip()
            if "support:" in c_str.lower():
                support = c_str.split(":", 1)[1].strip()
            if "resistance:" in c_str.lower():
                resistance = c_str.split(":", 1)[1].strip()

        # =================================================
        # 4. LATEST NEWS (Only verified news from context)
        # =================================================
        news_lines = []
        for c in retrieval_context:
            c_str = str(c).strip()
            if c_str.startswith("[") and " - " in c_str:
                news_lines.append(c_str)
                
        news_str = "\n\n".join(news_lines) if news_lines else "Data unavailable."

        # =================================================
        # 5. PROVIDER VALIDATION
        # =================================================
        agreement_lines = []
        warning_lines = []
        conflict_lines = []
        
        for key, metric in grounding_data.items():
            if not isinstance(metric, dict) or "validation_status" not in metric:
                continue
            
            status = metric.get("validation_status")
            reason = metric.get("validation_reason")
            display_name = key.replace("_", " ").title()
            if key == "pe_ratio":
                display_name = "PE Ratio"
            elif key == "pb_ratio":
                display_name = "Price to Book"
            elif key == "peg_ratio":
                display_name = "PEG Ratio"
            elif key == "dividend_yield":
                display_name = "Dividend Yield"
            
            if status in ("PASS", "SINGLE_SOURCE"):
                agreement_lines.append(f"- {display_name}: {status} ({reason})")
            elif status == "WARNING":
                warning_lines.append(f"- {display_name}: {reason}")
            elif status in ("FAIL", "CONFLICT"):
                conflict_lines.append(f"- {display_name}: {reason}")
                
        agreement_str = "\n".join(agreement_lines) if agreement_lines else "No provider agreements to report."
        warnings_str = "\n".join(warning_lines) if warning_lines else "No warnings to report."
        conflicts_str = "\n".join(conflict_lines) if conflict_lines else "No conflicts to report."

        # =================================================
        # Build Structured Output Prompt
        # =================================================
        output = (
            "=================================================\n"
            "COMPANY OVERVIEW\n"
            "=================================================\n"
            f"Company: {company}\n"
            f"Ticker: {ticker}\n"
            f"Sector: {sector}\n"
            f"Industry: {industry}\n\n"
            "=================================================\n"
            "VERIFIED FUNDAMENTALS\n"
            "=================================================\n"
            f"{fundamentals_str}\n\n"
            "=================================================\n"
            "TECHNICAL ANALYSIS\n"
            "=================================================\n"
            f"Trend: {trend}\n"
            f"RSI: {rsi}\n"
            f"Moving Averages: {moving_averages}\n"
            f"Support: {support}\n"
            f"Resistance: {resistance}\n\n"
            "=================================================\n"
            "LATEST NEWS\n"
            "=================================================\n"
            f"{news_str}\n\n"
            "=================================================\n"
            "PROVIDER VALIDATION\n"
            "=================================================\n"
            f"Provider Agreement:\n{agreement_str}\n\n"
            f"Warnings:\n{warnings_str}\n\n"
            f"Conflicts:\n{conflicts_str}\n\n"
            "=================================================\n"
            "STRICT INSTRUCTIONS\n"
            "=================================================\n"
            "Never invent facts.\n"
            "Never estimate missing values.\n"
            "If unavailable, explicitly say \"Data unavailable.\"\n"
            "Use only verified metrics.\n"
        )
        return output
