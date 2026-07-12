import re
import os

# Asset Class Configuration
ENABLE_CRYPTO = os.getenv("ENABLE_CRYPTO", "false").lower() == "true"

# Whitelisted asset classes
SUPPORTED_ASSET_CLASSES = [
    "Stocks",
    "ETFs",
    "Mutual Funds",
    "Bonds",
    "Commodities",
    "Indices",
    "Financial Concepts"
]
if ENABLE_CRYPTO:
    SUPPORTED_ASSET_CLASSES.append("Crypto")

# Whitelisted exchanges and markets
SUPPORTED_MARKETS = ["NSE", "BSE", "NYSE", "NASDAQ"]

# Financial vocabulary patterns mapped to their respective asset class/category.
# Format: (compiled_regex, asset_class_name)
FINANCIAL_VOCABULARY = [
    # Stocks & Companies
    (re.compile(r"\b(stocks?|shares?|equit(y|ies))\b", re.IGNORECASE), "Stocks"),
    # ETFs
    (re.compile(r"\b(etfs?)\b", re.IGNORECASE), "ETFs"),
    # Mutual Funds
    (re.compile(r"\b(mutual\s+funds?)\b", re.IGNORECASE), "Mutual Funds"),
    # Bonds & Treasuries
    (re.compile(r"\b(bonds?|treasur(y|ies))\b", re.IGNORECASE), "Bonds"),
    # Commodities
    (re.compile(r"\b(commodit(y|ies)|gold|silver)\b", re.IGNORECASE), "Commodities"),
    # Crypto (gated by Tier 4 check if whitelisted)
    (re.compile(r"\b(crypto(currencies|currency)?|bitcoins?|ethereum|solana|btc|eth|sol)\b", re.IGNORECASE), "Crypto"),
    # Market Indices
    (re.compile(r"\b(nse|bse|nyse|nasdaq|nifty|sensex|dow\s+jones|s&p\s*500|ftse|hang\s+seng|nikkei)\b", re.IGNORECASE), "Indices"),
    # Financial Concepts / Ratios / Accounting / Metrics
    (re.compile(r"\b(pe\s+ratios?|pb\s+ratios?|peg\s+ratios?|roe|roce|eps|ebitda|valuation|yields?|market\s+caps?|market\s+capitalizations?)\b", re.IGNORECASE), "Financial Concepts"),
    (re.compile(r"\b(financial\s+statements?|balance\s+sheets?|income\s+statements?|cash\s+flows?|revenues?|profits?|losses?|quarterly|margins?)\b", re.IGNORECASE), "Financial Concepts"),
    (re.compile(r"\b(rsi|macd|smas?|emas?|moving\s+averages?|support\s+(level|line)s?|resistance\s+(level|line)s?|technical\s+indicators?)\b", re.IGNORECASE), "Financial Concepts"),
    (re.compile(r"\b(inflation|gdp|interest\s+rates?|macroeconomics?|microeconomics?|central\s+banks?|fiscal|monetary)\b", re.IGNORECASE), "Financial Concepts"),
    (re.compile(r"\b(rbi|sebi|sec|fed|federal\s+reserves?)\b", re.IGNORECASE), "Financial Concepts"),
    (re.compile(r"\b(invest|investing|investment|brokerage|wealth|capital(?!s?\s+of)|ipo|buybacks?|dividends?|bullish|bearish|shorts?|longs?|analyse|analyze|analysis|research|reports?|outlooks?|risks?|drivers?)\b", re.IGNORECASE), "Financial Concepts")
]

# Patterns representing query intents for conceptual explanations and price movement questions.
# Format: (compiled_regex, intent_name, asset_class_name)
FINANCIAL_INTENT_PATTERNS = [
    (re.compile(r"\b(explain|define|what\s+is|what\s+are|how\s+does|how\s+to\s+calculate|formula\s+for)\b", re.IGNORECASE), "Explain Financial Concept", "Financial Concepts"),
    (re.compile(r"\b(why\s+did|why\s+is|reasons\s+for|drivers\s+of)\s+([a-z0-9&\-._\s]+)\s+(fall|rise|drop|rally|gain|lose|crash|skyrocket)\b", re.IGNORECASE), "Price Action Query", "Financial Concepts")
]
