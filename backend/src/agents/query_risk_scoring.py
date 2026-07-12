"""
Query Risk Scoring System for SentiNews AI.
Detects advisory-risk queries and assigns risk levels.
"""
import re
import logging
from typing import Tuple, List
from enum import Enum

logger = logging.getLogger(__name__)


class QueryRiskLevel(str, Enum):
    """Risk levels for queries."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


# ============================================================================
# RISK DETECTION PATTERNS
# ============================================================================

# High-risk advisory phrases (SEBI compliance violations)
HIGH_RISK_PATTERNS = [
    r"\bshould\s+i\s+(buy|sell|invest)\b",
    r"\bgive\s+me\s+(a\s+)?(tip|recommendation|pick)\b",
    r"\bbest\s+stock\s+(today|now|to\s+buy)\b",
    r"\bguaranteed\s+(returns|gains|profit|multibagger)\b",
    r"\b(sure|certain)\s+(shot|tip|multibagger)\b",
    r"\bwhich\s+stock\s+(will\s+)?(go\s+up|rise|moon|rocket)\b",
    r"\b(bullish|bearish)\s+for\s+(tomorrow|next\s+week)\b",
    r"\bprice\s+target\b",
    r"\brecommend\s+(i\s+)?(buy|sell)\b",
    r"\bwill\s+it\s+(go\s+up|rise|make\s+money)\b",
    r"\bmake\s+money\s+from\b",
    r"\bget\s+rich\b",
    r"\bguarantee.*returns\b",
    r"\b(pump|moon|rocket)\s+(stock|share)\b",
]

# Medium-risk advisory phrases (borderline)
MEDIUM_RISK_PATTERNS = [
    r"\sis\s+it\s+(a\s+)?(good\s+)?time\s+to\s+(buy|invest)\b",
    r"\sis\s+it\s+worth\s+investing\b",
    r"\bshould\s+i\s+invest\b",
    r"\bis\s+it\s+a\s+good\s+(buy|investment)\b",
    r"\bwhen\s+should\s+i\s+(buy|sell)\b",
    r"\bhow\s+much\s+to\s+invest\b",
    r"\bportfolio\s+(recommendation|suggestion|advice)\b",
    r"\bentry\s+point\b",
    r"\bexit\s+strategy\b",
]

# Low-risk analytical phrases (safe)
SAFE_PATTERNS = [
    r"\b(analyse|analyze|research|study|explain|tell\s+me\s+about)\b",
    r"\b(what\s+is|what\s+are|how\s+are|how\s+is)\b",
    r"\b(recent\s+)?news\s+(about|on|for)\b",
    r"\b(technical|fundamental|sentiment)\s+(analysis|report)\b",
    r"\bwhy\s+did\b",
    r"\bwhy\s+is\b",
    r"\bcompare\b",
    r"\b(charts?|indicators?|trends?)\b",
]


def score_advisory_risk(query: str) -> Tuple[QueryRiskLevel, float, List[str]]:
    """
    Score the advisory risk level of a query.
    
    Returns:
        Tuple of (risk_level, confidence_score, detected_patterns)
    """
    query_lower = query.lower()
    detected_patterns = []
    risk_score = 0.0
    
    # Check for HIGH risk patterns
    for pattern in HIGH_RISK_PATTERNS:
        if re.search(pattern, query_lower):
            detected_patterns.append(pattern)
            risk_score += 0.5
    
    # Check for MEDIUM risk patterns
    for pattern in MEDIUM_RISK_PATTERNS:
        if re.search(pattern, query_lower):
            detected_patterns.append(pattern)
            risk_score += 0.2
    
    # Check for SAFE patterns (reduce risk)
    for pattern in SAFE_PATTERNS:
        if re.search(pattern, query_lower):
            risk_score = max(0, risk_score - 0.1)
    
    # Clamp risk score between 0 and 1
    risk_score = min(1.0, max(0.0, risk_score))
    
    # Determine risk level
    if risk_score >= 0.5:
        risk_level = QueryRiskLevel.HIGH
    elif risk_score >= 0.2:
        risk_level = QueryRiskLevel.MEDIUM
    else:
        risk_level = QueryRiskLevel.LOW
    
    logger.debug(
        f"Risk Scoring: query='{query[:50]}...' | risk_level={risk_level} | "
        f"score={risk_score:.2f} | patterns={len(detected_patterns)}"
    )
    
    return risk_level, risk_score, detected_patterns


def get_safe_refusal_response(
    query: str,
    risk_level: QueryRiskLevel,
    detected_patterns: List[str],
) -> str:
    """
    Generate a SEBI-compliant educational redirect for high-risk queries.
    
    Instead of hard-refusing, we redirect to educational intelligence.
    """
    if risk_level == QueryRiskLevel.HIGH:
        return (
            "I cannot provide personalized investment advice or specific buy/sell recommendations, "
            "as this would violate SEBI regulations.\n\n"
            "However, I can provide you with:\n"
            "• Educational analysis of market context and fundamentals\n"
            "• Technical indicators and trend analysis\n"
            "• News sentiment and market drivers\n"
            "• Risk factors and valuation context\n"
            "• Peer comparisons and sector analysis\n\n"
            "Would you like me to analyze the underlying company or market fundamentals instead?"
        )
    elif risk_level == QueryRiskLevel.MEDIUM:
        return (
            "I can provide educational market analysis and factual information, "
            "but cannot make personalized investment recommendations.\n\n"
            "Let me analyze the market context, fundamentals, and risks for you instead."
        )
    else:
        return ""


# ============================================================================
# COMPLIANCE CHECKER
# ============================================================================

def validate_sebi_compliance(query: str, response_text: str) -> Tuple[bool, List[str]]:
    """
    Validate that a response is SEBI-compliant.
    
    Returns:
        Tuple of (is_compliant, violations_list)
    """
    violations = []
    response_lower = response_text.lower()
    
    # Check for banned words
    banned_words = [
        "buy now",
        "sell now",
        "guaranteed",
        "sure shot",
        "tip",
        "target price",
        "price target",
        "multibagger",
        "will go up",
        "will rise",
        "best stock",
        "recommended to buy",
        "must buy",
    ]
    
    for word in banned_words:
        if re.search(r"\b" + re.escape(word) + r"\b", response_lower):
            violations.append(f"Banned phrase detected: '{word}'")
    
    is_compliant = len(violations) == 0
    
    if not is_compliant:
        logger.warning(f"SEBI compliance violations detected: {violations}")
    
    return is_compliant, violations
