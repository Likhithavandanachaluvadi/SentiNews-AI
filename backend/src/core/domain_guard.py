import re
import logging
from typing import Optional, NamedTuple
from src.services.entity_resolver import EntityResolver, clean_company_name
from src.core.financial_domain_registry import (
    SUPPORTED_ASSET_CLASSES,
    SUPPORTED_MARKETS,
    FINANCIAL_VOCABULARY,
    FINANCIAL_INTENT_PATTERNS
)

logger = logging.getLogger(__name__)

class DomainValidationResult(NamedTuple):
    """Immutable validation result containing diagnostic outcomes of the domain check."""
    allowed: bool
    confidence: float
    reason: str
    matched_stage: str
    matched_entity: str = "None"
    matched_vocab: str = "None"
    matched_intent: str = "None"
    matched_asset_class: str = "None"

class FinancialDomainGuard:
    """
    Production Financial Domain Guard.
    Deterministic, data-driven gatekeeper to validate whether user queries
    belong to the supported financial domain using local resources only.
    """

    @staticmethod
    def validate(query: str) -> DomainValidationResult:
        """
        Validates if a query belongs to the supported financial ecosystem.
        Runs a 4-tier validation pipeline:
        1. Local Entity Resolution (with generic word false positive filter)
        2. Financial Vocabulary Check
        3. Financial Intent Pattern Matching (requires accompanying financial vocabulary)
        4. Supported Asset Class Gating
        """
        query_clean = query.strip()
        query_lower = query_clean.lower()

        # Tier 1: Local Entity Resolution Check (Strict Local Mode)
        ticker, company = EntityResolver.resolve_sync(query_clean)
        if ticker:
            # Filter out generic matching false positives
            words_in_query = set(re.findall(r'\b[a-zA-Z0-9&\-._]+\b', query_lower))
            ticker_lower = ticker.lower()
            
            if ticker_lower in words_in_query:
                # Direct ticker match in query (e.g. "TCS")
                entity_pass = True
            else:
                # Resolved via company name. Check overlapping words.
                company_clean = clean_company_name(company).lower()
                company_words = set(re.findall(r'\b[a-zA-Z0-9&\-._]+\b', company_clean))
                
                # Exclude standard corporate stop words
                corporate_stopwords = {
                    "corporation", "corp", "limited", "ltd", "inc", "incorporated", 
                    "company", "bank", "industries", "group", "holdings", "private", 
                    "pvt", "ltd.", "co.", "co"
                }
                company_words = {w for w in company_words if w not in corporate_stopwords and len(w) >= 3}
                query_words = {w for w in words_in_query if len(w) >= 3}
                
                overlap = company_words.intersection(query_words)
                
                # Generic company terms that shouldn't trigger matching on their own
                GENERIC_COMPANY_KEYWORDS = {
                    "systems", "system", "power", "chemicals", "chemical", "engineering", 
                    "technologies", "technology", "housing", "infrastructure", "industries", 
                    "industry", "holdings", "holding", "solutions", "solution", "labs", 
                    "laboratory", "laboratories", "ventures", "venture", "associates", 
                    "associate", "projects", "project", "products", "product", "developers", 
                    "developer", "capital", "services", "service", "steel", "metals", "metal",
                    "finance", "financial", "investment", "investments"
                }
                
                # If overlap consists ONLY of generic words, reject the match
                if not overlap or overlap.issubset(GENERIC_COMPANY_KEYWORDS):
                    entity_pass = False
                else:
                    entity_pass = True
            
            if entity_pass:
                # Determine asset class for whitelisted tickers (default to Stocks, index to Indices)
                asset_class = "Indices" if ticker.upper() in ("NIFTY", "SENSEX") else "Stocks"
                
                # Tier 4: Supported Asset Class Check
                if asset_class in SUPPORTED_ASSET_CLASSES:
                    result = DomainValidationResult(
                        allowed=True,
                        confidence=1.00,
                        reason=f"Matched local company entity: {company} ({ticker})",
                        matched_stage="Entity Resolution",
                        matched_entity=f"{company} ({ticker})",
                        matched_asset_class=asset_class
                    )
                    FinancialDomainGuard._log_decision(query_clean, result)
                    return result

        # Check Tier 2 and Tier 3 with Tier 4 Gating
        matched_vocab_text = None
        matched_vocab_asset_class = None
        
        # Check if there is any vocabulary match first
        for pattern, asset_class in FINANCIAL_VOCABULARY:
            match = re.search(pattern, query_lower)
            if match:
                matched_vocab_text = match.group(0)
                matched_vocab_asset_class = asset_class
                break
                
        if matched_vocab_text:
            # Check for Tier 3: Financial Intent
            # Requires that the query matches both a vocabulary term and an intent pattern
            for pattern, intent_name, intent_asset_class in FINANCIAL_INTENT_PATTERNS:
                match = re.search(pattern, query_lower)
                if match:
                    # Gated by asset class check (Tier 4)
                    if matched_vocab_asset_class in SUPPORTED_ASSET_CLASSES:
                        result = DomainValidationResult(
                            allowed=True,
                            confidence=0.90,
                            reason=f"Matched Financial Intent: '{intent_name}'",
                            matched_stage="Financial Intent",
                            matched_intent=intent_name,
                            matched_vocab=matched_vocab_text,
                            matched_asset_class=matched_vocab_asset_class
                        )
                        FinancialDomainGuard._log_decision(query_clean, result)
                        return result
            
            # Tier 2: Vocabulary match without explicit intent pattern
            if matched_vocab_asset_class in SUPPORTED_ASSET_CLASSES:
                result = DomainValidationResult(
                    allowed=True,
                    confidence=0.95,
                    reason=f"Matched Financial Vocabulary: '{matched_vocab_text}'",
                    matched_stage="Financial Vocabulary",
                    matched_vocab=matched_vocab_text,
                    matched_asset_class=matched_vocab_asset_class
                )
                FinancialDomainGuard._log_decision(query_clean, result)
                return result

        # FAIL: Query did not pass any tier
        result = DomainValidationResult(
            allowed=False,
            confidence=0.00,
            reason="No company detected, no financial vocabulary, no financial intent, no supported asset class",
            matched_stage="None"
        )
        FinancialDomainGuard._log_decision(query_clean, result)
        return result

    @staticmethod
    def _log_decision(query: str, result: DomainValidationResult) -> None:
        """Outputs structured diagnostic logs matching product requirements."""
        log_msg = (
            f"\n================================================\n"
            f"FINANCIAL DOMAIN VALIDATION\n"
            f"================================================\n"
            f"Query:                {query}\n"
            f"Matched Entity:       {result.matched_entity}\n"
            f"Matched Vocabulary:   {result.matched_vocab}\n"
            f"Matched Intent:       {result.matched_intent}\n"
            f"Matched Asset Class:  {result.matched_asset_class}\n"
            f"Decision:             {'PASS' if result.allowed else 'FAIL'}\n"
            f"Confidence:           {result.confidence:.2f}\n"
            f"Reason:               {result.reason}\n"
            f"Validation Stage:     {result.matched_stage}\n"
            f"================================================"
        )
        logger.info(log_msg)
        print(log_msg)  # Ensure visible in stdout/console logs
