import re
import logging
import asyncio
from typing import List, Optional
from src.services.entity_models import ResolvedEntity, EntityCollection

logger = logging.getLogger(__name__)

# Constants
INTENT_KEYWORDS = [
    "analyse", "analyze", "tell me about", "give me analysis of",
    "research", "look up", "check", "study", "report on",
    "what about", "how is", "how are", "what is", "what are",
    "should i buy", "is it a good buy", "should i invest in",
    "news about", "news on", "latest on", "update on",
    "overview of", "analysis on", "fundamentals of",
    "stock of", "shares of", "share price of", "stock price of",
    "the company", "this company", "the stock", "future of",
    "growth of", "prospects of", "outlook for",
    "compare", "comparison", "versus", "vs", "between",
]

NON_ENTITY_CANDIDATES = {
    "why", "what", "when", "where", "who", "which", "how",
    "is", "are", "was", "were", "do", "does", "did",
    "today", "tomorrow", "yesterday", "falling", "rising",
    "up", "down", "stock", "share", "shares", "price",
}

class EntityResolutionPipeline:
    MINIMUM_CONFIDENCE_THRESHOLD = 0.60
    FUZZY_MATCH_THRESHOLD = 0.80
    MAX_ENTITIES_PER_COLLECTION = 5

    # Process-level LRU cache for Yahoo Finance searches
    _yahoo_lru_cache = {}

    PROTECTED_CONCEPTS = {
        "AI": "technology_concept",
        "Artificial Intelligence": "technology_concept",
        "ML": "technology_concept",
        "LLM": "technology_concept",
        "GenAI": "technology_concept",

        "ROE": "financial_metric",
        "ROCE": "financial_metric",
        "EPS": "financial_metric",
        "P/E": "financial_metric",
        "PEG": "financial_metric",

        "RSI": "technical_indicator",
        "MACD": "technical_indicator",
        "Bollinger": "technical_indicator",

        "GDP": "economic_indicator",
        "CPI": "economic_indicator",
        "Inflation": "economic_indicator",
        "Repo Rate": "economic_indicator",

        "Banking": "sector",
        "IT": "sector",
        "Technology": "sector",
        "Pharma": "sector",
        "Energy": "sector",
        "Auto": "sector",
        "FMCG": "sector",

        "Cloud": "industry_theme",
        "Cybersecurity": "industry_theme",
        "Semiconductor": "industry_theme",
        "EV": "industry_theme"
    }

    @classmethod
    def _classify_candidate(cls, candidate: str, query: str) -> str:
        cand_upper = candidate.upper().strip()
        cand_lower = candidate.lower().strip()
        query_lower = query.lower()

        # Step 5: Sector Handling
        sector_keywords = ["banking", "it", "pharma", "energy", "auto", "technology", "renewable energy"]
        sector_indicators = ["sector", "industry", "companies"]
        
        for sect in sector_keywords:
            for ind in sector_indicators:
                phrase = f"{sect} {ind}"
                if phrase in cand_lower:
                    return "sector"
                if cand_lower == sect:
                    pattern = rf"\b{re.escape(cand_lower)}\s+{re.escape(ind)}\b"
                    if re.search(pattern, query_lower):
                        return "sector"
                    pattern_pre = rf"\b{re.escape(ind)}\s+of\s+{re.escape(cand_lower)}\b"
                    if re.search(pattern_pre, query_lower):
                        return "sector"

        # Protected Concepts Registry Lookup
        for concept, concept_type in cls.PROTECTED_CONCEPTS.items():
            if cand_upper == concept.upper() or cand_lower == concept.lower():
                # Step 6: Ambiguous Token Handling (AI / IT)
                if cand_upper == "AI":
                    positive_company_signals = ["stock", "share", "listed", "earnings", "market cap", "valuation", "fundamentals", "ticker"]
                    if any(sig in query_lower for sig in positive_company_signals):
                        return "company"
                    return "technology_concept"
                if cand_upper == "IT":
                    for ind in ["sector", "industry", "companies"]:
                        if f"it {ind}" in query_lower:
                            return "sector"
                    return "sector"
                return concept_type

        # Suffix / local database matching
        company_suffixes = ["ltd", "limited", "inc", "corp", "corporation", "co", "pvt", "private"]
        if any(rf"\b{re.escape(suff)}\b" in cand_lower for suff in company_suffixes):
            return "company"

        if re.match(r"^[A-Z0-9&\-._]{1,10}$", candidate) and cand_lower not in NON_ENTITY_CANDIDATES:
            from src.services.entity_resolver import EntityResolver
            EntityResolver.initialize_sync()
            if candidate in EntityResolver._ticker_to_company:
                return "ticker"

        from src.services.entity_resolver import EntityResolver
        EntityResolver.initialize_sync()
        if cand_lower in EntityResolver._company_to_ticker:
            return "company"

        return "company"

    @classmethod
    def _validate_context(cls, candidate: str, query: str) -> bool:
        query_lower = query.lower()
        positive_company_signals = ["stock", "share", "company", "listed", "ticker", "valuation", "earnings", "market cap", "fundamentals"]
        negative_company_signals = ["industry", "sector", "explain", "meaning", "concept", "technology", "adoption", "trend", "outlook", "beginner"]
        
        has_negative = any(sig in query_lower for sig in negative_company_signals)
        has_positive = any(sig in query_lower for sig in positive_company_signals)
        
        if has_negative and not has_positive:
            return False
        return True

    @classmethod
    def resolve_entities_sync(cls, query: str, intent: Optional[str] = None) -> EntityCollection:
        """Synchronous multi-entity resolver pipeline."""
        if not query or not query.strip():
            return EntityCollection(entities=[], query=query, resolution_mode="EDUCATIONAL", total_found=0)

        # Stage 1: Candidate Extraction
        candidates = cls._extract_candidates(query)
        logger.info(f"Pipeline sync: extracted candidates={candidates} from query='{query}'")

        resolved_list = []
        for cand in candidates:
            # Step 1: Candidate Classification
            ent_type = cls._classify_candidate(cand, query)
            
            # Step 7: Improved debug logging
            context_val = "educational" if "explain" in query.lower() or "what is" in query.lower() else "analytical"
            
            # Step 4: Resolution Rules
            if ent_type not in ("company", "ticker"):
                logger.info(
                    f"\nCandidate: {cand}\n"
                    f"Classification: {ent_type}\n"
                    f"Context: {context_val}\n"
                    f"Resolution Decision: Skip ticker lookup\n"
                    f"Reason: Protected concept or non-company entity.\n"
                )
                continue
                
            # Step 3: Context Validation
            if not cls._validate_context(cand, query):
                logger.info(
                    f"\nCandidate: {cand}\n"
                    f"Classification: {ent_type}\n"
                    f"Context: {context_val}\n"
                    f"Resolution Decision: Skip ticker lookup\n"
                    f"Reason: Context validation blocked company resolution due to negative context/signals.\n"
                )
                continue
                
            logger.info(
                f"\nCandidate: {cand}\n"
                f"Classification: {ent_type}\n"
                f"Context: {context_val}\n"
                f"Resolution Decision: Proceed with ticker lookup\n"
                f"Reason: Candidate classified as company/ticker with valid stock context.\n"
            )

            # Stage 2: Per-Candidate Multi-Source Matching
            matched = cls._match_candidate(cand)
            if matched:
                resolved_list.append(matched)
                continue

            # Stage 4: Fuzzy Matching
            matched_fuzzy = cls._fuzzy_match(cand)
            if matched_fuzzy:
                resolved_list.append(matched_fuzzy)
                continue

            # Stage 5: Yahoo Finance Discovery (Sync cached check/fetch)
            # Only unresolved, uncovered candidates are eligible for discovery.
            if cls._is_candidate_covered_by_high_confidence_local_entity(cand, resolved_list):
                logger.info(f"Skipping Yahoo discovery for covered candidate='{cand}'")
                continue

            matched_yahoo = cls._discover_via_yahoo_sync(cand, existing_entities=resolved_list)
            if matched_yahoo:
                resolved_list.append(matched_yahoo)

        # Stage 6: Ranking and Deduplication
        collection = cls._rank_and_deduplicate(resolved_list, query)

        # Stage 7: Validation Gate
        if intent:
            cls._validate(collection, intent)

        return collection

    @classmethod
    async def resolve_entities(cls, query: str, intent: Optional[str] = None) -> EntityCollection:
        """Asynchronous multi-entity resolver pipeline."""
        if not query or not query.strip():
            return EntityCollection(entities=[], query=query, resolution_mode="EDUCATIONAL", total_found=0)

        # Stage 1: Candidate Extraction
        candidates = cls._extract_candidates(query)
        logger.info(f"Pipeline async: extracted candidates={candidates} from query='{query}'")

        resolved_list = []
        tasks = []

        # We resolve matches sequentially or concurrently for Stage 2/4
        # Since Stage 5 is async, we separate candidate resolution
        for cand in candidates:
            # Step 1: Candidate Classification
            ent_type = cls._classify_candidate(cand, query)
            
            # Step 7: Improved debug logging
            context_val = "educational" if "explain" in query.lower() or "what is" in query.lower() else "analytical"
            
            # Step 4: Resolution Rules
            if ent_type not in ("company", "ticker"):
                logger.info(
                    f"\nCandidate: {cand}\n"
                    f"Classification: {ent_type}\n"
                    f"Context: {context_val}\n"
                    f"Resolution Decision: Skip ticker lookup\n"
                    f"Reason: Protected concept or non-company entity.\n"
                )
                continue
                
            # Step 3: Context Validation
            if not cls._validate_context(cand, query):
                logger.info(
                    f"\nCandidate: {cand}\n"
                    f"Classification: {ent_type}\n"
                    f"Context: {context_val}\n"
                    f"Resolution Decision: Skip ticker lookup\n"
                    f"Reason: Context validation blocked company resolution due to negative context/signals.\n"
                )
                continue
                
            logger.info(
                f"\nCandidate: {cand}\n"
                f"Classification: {ent_type}\n"
                f"Context: {context_val}\n"
                f"Resolution Decision: Proceed with ticker lookup\n"
                f"Reason: Candidate classified as company/ticker with valid stock context.\n"
            )

            matched = cls._match_candidate(cand)
            if matched:
                resolved_list.append(matched)
                continue

            matched_fuzzy = cls._fuzzy_match(cand)
            if matched_fuzzy:
                resolved_list.append(matched_fuzzy)
                continue

            # For Stage 5, create async tasks for parallel discovery.
            # Discovery must enrich only unresolved candidates, never duplicate
            # a high-confidence local ticker/name/alias resolution.
            if cls._is_candidate_covered_by_high_confidence_local_entity(cand, resolved_list):
                logger.info(f"Skipping Yahoo discovery for covered candidate='{cand}'")
                continue

            tasks.append(cls._discover_via_yahoo_async(cand, existing_entities=list(resolved_list)))

        if tasks:
            yahoo_results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in yahoo_results:
                if res and isinstance(res, ResolvedEntity):
                    resolved_list.append(res)

        # Stage 6: Ranking and Deduplication
        collection = cls._rank_and_deduplicate(resolved_list, query)

        # Stage 7: Validation Gate
        if intent:
            cls._validate(collection, intent)

        return collection

    @classmethod
    def _extract_candidates(cls, query: str) -> List[str]:
        if not query or not query.strip():
            return []

        query_clean = query.strip()
        query_lower = query_clean.lower()

        # Step 1: Conjunction split safety heuristic
        has_comparison_verb = any(v in query_lower for v in [" vs ", " versus ", " compared to ", " compare "])

        split_connectors = [" vs ", " versus ", " compared to ", " compare ", " or ", " with ", " against "]
        conjunctions = [" and ", " & "]

        should_split_conjunction = has_comparison_verb
        if not should_split_conjunction:
            for conj in conjunctions:
                if conj in query_lower:
                    segments = re.split(re.escape(conj), query_clean, flags=re.IGNORECASE)
                    for seg in segments:
                        if cls._is_resolvable_company_simple(seg.strip()):
                            should_split_conjunction = True
                            break

        if should_split_conjunction:
            split_connectors.extend(conjunctions)

        # Build regex for splitting
        pattern = "|".join(re.escape(conn) for conn in split_connectors)
        segments = re.split(pattern, query_clean, flags=re.IGNORECASE)

        candidates = []
        for seg in segments:
            seg_clean = seg.strip()
            if not seg_clean:
                continue

            seg_stripped = seg_clean
            for kw in sorted(INTENT_KEYWORDS, key=len, reverse=True):
                pattern_kw = rf"^\b{re.escape(kw)}\b"
                seg_stripped = re.sub(pattern_kw, "", seg_stripped, flags=re.IGNORECASE).strip()
                pattern_kw_end = rf"\b{re.escape(kw)}\b$"
                seg_stripped = re.sub(pattern_kw_end, "", seg_stripped, flags=re.IGNORECASE).strip()

            seg_stripped = seg_stripped.strip(" ?.,!&")
            seg_stripped = re.sub(
                r'\b(why|what|when|where|who|which|how|is|are|was|were|falling|rising|today|tomorrow|yesterday|stock|share|shares|price)\b',
                "",
                seg_stripped,
                flags=re.IGNORECASE,
            )
            seg_stripped = re.sub(r"\s+", " ", seg_stripped).strip(" ?.,!&")
            if not seg_stripped:
                continue

            # 1. Tickers (All-caps 1-15 chars)
            all_caps = re.findall(r'\b[A-Z0-9&\-._]{1,15}\b', seg_stripped)
            for ac in all_caps:
                if ac.lower() in NON_ENTITY_CANDIDATES:
                    continue
                if ac not in candidates and ac not in ["THE", "IS", "AND", "FOR", "OF", "IN", "TO", "A", "AN", "AT", "BY"]:
                    candidates.append(ac)

            # 2. Title-case words (2-4 words)
            title_case = re.findall(r'\b[A-Z][a-z0-9&\-._]*(?:\s+[A-Z][a-z0-9&\-._]*){0,3}\b', seg_stripped)
            for tc in title_case:
                if tc.lower().strip() in NON_ENTITY_CANDIDATES:
                    continue
                if tc not in candidates and len(tc) >= 3:
                    candidates.append(tc)

            # 3. Cleaned segment itself
            if seg_stripped.lower().strip() in NON_ENTITY_CANDIDATES:
                continue
            if seg_stripped not in candidates and len(seg_stripped) >= 3:
                candidates.append(seg_stripped)

        unique_candidates = []
        for c in candidates:
            if c not in unique_candidates:
                unique_candidates.append(c)
        return unique_candidates

    @classmethod
    def _is_resolvable_company_simple(cls, text: str) -> bool:
        from src.services.entity_resolver import EntityResolver, LEGACY_EDGE_CASES
        text_lower = text.lower().strip()
        text_upper = text.upper().strip()

        if text_upper in EntityResolver._ticker_to_company:
            return True

        if text_lower in LEGACY_EDGE_CASES:
            return True

        if text_lower in EntityResolver._company_to_ticker:
            return True

        for comp_name in EntityResolver._company_to_ticker:
            if text_lower in comp_name:
                pattern = rf"\b{re.escape(text_lower)}\b"
                if re.search(pattern, comp_name):
                    return True
        return False

    @classmethod
    def _match_candidate(cls, candidate: str) -> Optional[ResolvedEntity]:
        from src.services.entity_resolver import EntityResolver, LEGACY_EDGE_CASES, clean_company_name

        candidate_lower = candidate.lower().strip()
        candidate_upper = candidate.upper().strip()

        # Step 2.1: Exact Ticker Lookup
        if candidate_upper in EntityResolver._ticker_to_company:
            sym = candidate_upper
            company_name = EntityResolver._ticker_to_company[sym]
            return ResolvedEntity(
                ticker=sym,
                company_name=company_name,
                exchange="NASDAQ" if sym in ["GOOGL", "TSLA", "AAPL", "NVDA"] else "NSE",
                country="US" if sym in ["GOOGL", "TSLA", "AAPL", "NVDA"] else "IN",
                confidence=1.00,
                resolution_source="EXACT_TICKER",
                aliases=cls._build_aliases(sym),
                query_span=candidate
            )

        # Step 2.3: Legacy Alias Lookup
        if candidate_lower in LEGACY_EDGE_CASES:
            sym = LEGACY_EDGE_CASES[candidate_lower]
            if sym == "GOOGL":
                company_name = "Alphabet Inc."
            elif sym == "TSLA":
                company_name = "Tesla, Inc."
            else:
                company_name = "State Bank of India"
            return ResolvedEntity(
                ticker=sym,
                company_name=company_name,
                exchange="NASDAQ" if sym == "GOOGL" else "NSE",
                country="US" if sym == "GOOGL" else "IN",
                confidence=0.95,
                resolution_source="LEGACY_ALIAS",
                aliases=cls._build_aliases(sym),
                query_span=candidate
            )

        # Step 2.2: Exact Company Name Lookup
        if candidate_lower in EntityResolver._company_to_ticker:
            sym = EntityResolver._company_to_ticker[candidate_lower]
            company_name = EntityResolver._ticker_to_company[sym]
            return ResolvedEntity(
                ticker=sym,
                company_name=company_name,
                exchange="NASDAQ" if sym in ["GOOGL", "TSLA", "AAPL", "NVDA"] else "NSE",
                country="US" if sym in ["GOOGL", "TSLA", "AAPL", "NVDA"] else "IN",
                confidence=0.97,
                resolution_source="EXACT_NAME",
                aliases=cls._build_aliases(sym),
                query_span=candidate
            )

        # Step 2.4: Word boundary name lookup
        for comp_name, sym in EntityResolver._company_to_ticker.items():
            pattern = rf"\b{re.escape(comp_name)}\b"
            if re.search(pattern, candidate_lower):
                company_name = EntityResolver._ticker_to_company[sym]
                return ResolvedEntity(
                    ticker=sym,
                    company_name=company_name,
                    exchange="NASDAQ" if sym in ["GOOGL", "TSLA", "AAPL", "NVDA"] else "NSE",
                    country="US" if sym in ["GOOGL", "TSLA", "AAPL", "NVDA"] else "IN",
                    confidence=0.97,
                    resolution_source="EXACT_NAME",
                    aliases=cls._build_aliases(sym),
                    query_span=candidate
                )

        # Step 2.5: Whole-Word Significant Token Match
        corporate_stopwords = {
            "corporation", "corp", "limited", "ltd", "inc", "incorporated", "company", "bank", "industries", "group", "holdings", "private", "pvt",
            "the", "and", "for", "out", "yes", "not", "buy", "sell", "good", "grow", "news", "risk", "risks",
            "what", "are", "about", "with", "this", "that", "from", "your", "will", "than", "then",
            "should", "invest", "today", "stock", "share", "shares", "how", "why", "who", "which",
            "where", "when", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
            "do", "does", "did", "but", "if", "or", "because", "as", "until", "while", "of", "at", "by",
            "for", "about", "against", "between", "into", "through", "during", "before", "after",
            "above", "below", "to", "from", "up", "down", "in", "out", "on", "off", "over", "under",
            "again", "further", "then", "once", "here", "there", "when", "where", "why", "how", "all",
            "any", "both", "each", "few", "more", "most", "other", "some", "such", "no", "nor", "not",
            "only", "own", "same", "so", "than", "too", "very", "can", "will", "just", "should", "now", "new",
            "investment", "investments", "investing", "finance", "financial", "equity", "securities", "capital", "services", "service", "wealth", "advisory"
        }
        for comp_name, sym in EntityResolver._company_to_ticker.items():
            cleaned_name = clean_company_name(comp_name)
            name_words = [nw for nw in re.split(r'\W+', cleaned_name) if nw and len(nw) >= 3 and nw not in corporate_stopwords]
            for nw in name_words:
                pattern = rf"\b{re.escape(nw)}\b"
                if re.search(pattern, candidate_lower):
                    return ResolvedEntity(
                        ticker=sym,
                        company_name=EntityResolver._ticker_to_company[sym],
                        exchange="NASDAQ" if sym in ["GOOGL", "TSLA", "AAPL", "NVDA"] else "NSE",
                        country="US" if sym in ["GOOGL", "TSLA", "AAPL", "NVDA"] else "IN",
                        confidence=0.80,
                        resolution_source="WHOLE_WORD",
                        aliases=cls._build_aliases(sym),
                        query_span=candidate
                    )
        return None

    @classmethod
    def _is_high_confidence_local_entity(cls, entity: ResolvedEntity) -> bool:
        return entity.confidence >= 0.95 and entity.resolution_source != "YAHOO_FINANCE"

    @classmethod
    def _normalize_entity_text(cls, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

    @classmethod
    def _entity_match_tokens(cls, entity: ResolvedEntity) -> List[str]:
        tokens = [entity.ticker]
        tokens.extend(entity.aliases or [])
        tokens.append(entity.company_name)

        normalized_tokens = []
        for token in tokens:
            normalized = cls._normalize_entity_text(token)
            if normalized and normalized not in normalized_tokens:
                normalized_tokens.append(normalized)
        return normalized_tokens

    @classmethod
    def _is_candidate_covered_by_high_confidence_local_entity(
        cls,
        candidate: str,
        existing_entities: List[ResolvedEntity],
    ) -> bool:
        candidate_norm = cls._normalize_entity_text(candidate)
        if not candidate_norm:
            return False

        for entity in existing_entities:
            if not cls._is_high_confidence_local_entity(entity):
                continue

            for token in cls._entity_match_tokens(entity):
                if not token:
                    continue

                # Exact ticker/name/alias and longer candidate spans containing
                # that exact token are considered already resolved locally.
                pattern = rf"\b{re.escape(token)}\b"
                if re.search(pattern, candidate_norm):
                    return True

        return False

    @classmethod
    def _is_yahoo_duplicate_of_existing(
        cls,
        *,
        candidate: str,
        symbol: str,
        company_name: str,
        existing_entities: Optional[List[ResolvedEntity]] = None,
    ) -> bool:
        for entity in existing_entities or []:
            if not cls._is_high_confidence_local_entity(entity):
                continue

            if symbol.upper().strip() == entity.ticker.upper().strip():
                return True

            discovered_name = cls._normalize_entity_text(company_name)
            for token in cls._entity_match_tokens(entity):
                if token and token == discovered_name:
                    return True

            if cls._is_candidate_covered_by_high_confidence_local_entity(candidate, [entity]):
                return True

        return False

    @classmethod
    def _build_aliases(cls, ticker: str) -> List[str]:
        from src.services.entity_resolver import EntityResolver
        aliases = [ticker.lower()]
        ticker_upper = ticker.upper()
        for name, sym in EntityResolver._company_to_ticker.items():
            if sym == ticker_upper:
                aliases.append(name.lower())

        import json
        from pathlib import Path
        try:
            json_path = Path(__file__).resolve().parents[1] / "indian_tickers.json"
            if json_path.exists():
                with json_path.open("r", encoding="utf-8") as f:
                    ticker_map = json.load(f)
                aliases.extend([name.lower() for name, symbol in ticker_map.items() if symbol.upper().strip() == ticker_upper])
        except Exception:
            pass

        unique_aliases = []
        for alias in aliases:
            if alias not in unique_aliases:
                unique_aliases.append(alias)
        return unique_aliases

    @classmethod
    def _fuzzy_match(cls, candidate: str) -> Optional[ResolvedEntity]:
        import difflib
        from src.services.entity_resolver import EntityResolver, clean_company_name
        candidate_lower = candidate.lower().strip()
        candidate_clean = clean_company_name(candidate_lower)

        best_ratio = 0.0
        best_sym = None

        for sym, name in EntityResolver._ticker_to_company.items():
            name_clean = clean_company_name(name)
            ratio = difflib.SequenceMatcher(None, candidate_clean, name_clean).ratio()

            cand_term = cls._extract_candidate_search_term_pipeline(candidate_lower)
            if cand_term:
                cand_ratio = difflib.SequenceMatcher(None, clean_company_name(cand_term), name_clean).ratio()
                ratio = max(ratio, cand_ratio)

            if ratio > best_ratio:
                best_ratio = ratio
                best_sym = sym

        if best_ratio >= cls.FUZZY_MATCH_THRESHOLD and best_sym:
            return ResolvedEntity(
                ticker=best_sym,
                company_name=EntityResolver._ticker_to_company[best_sym],
                exchange="NASDAQ" if best_sym in ["GOOGL", "TSLA", "AAPL", "NVDA"] else "NSE",
                country="US" if best_sym in ["GOOGL", "TSLA", "AAPL", "NVDA"] else "IN",
                confidence=best_ratio,
                resolution_source="FUZZY_MATCH",
                aliases=cls._build_aliases(best_sym),
                query_span=candidate
            )
        return None

    @classmethod
    def _extract_candidate_search_term_pipeline(cls, query: str) -> Optional[str]:
        cleaned = query.strip()
        cleaned = re.sub(
            r'^(is|should i buy|should i invest in|what is|outlook for|evaluate|analyze|tell me about|how is|price of)\b',
            '', cleaned, flags=re.IGNORECASE
        ).strip()
        cleaned = re.sub(
            r'\b(stock|share|shares|investment|financials|fundamentals|technical|news|analysis|report|a good buy|overvalued|undervalued|today)\b',
            '', cleaned, flags=re.IGNORECASE
        ).strip()

        cleaned = re.sub(r'[^\w\s&.\-]', '', cleaned).strip()
        words = cleaned.split()
        if len(words) > 0:
            return " ".join(words[:4])
        return None

    @classmethod
    def _discover_via_yahoo_sync(
        cls,
        candidate: str,
        existing_entities: Optional[List[ResolvedEntity]] = None,
    ) -> Optional[ResolvedEntity]:
        from src.services.entity_resolver import EntityResolver
        candidate_normalized = candidate.lower().strip()

        if candidate_normalized in cls._yahoo_lru_cache:
            return cls._yahoo_lru_cache[candidate_normalized]

        cand_term = cls._extract_candidate_search_term_pipeline(candidate_normalized)
        if not cand_term:
            return None

        result = EntityResolver._search_yahoo_finance_sync(cand_term)
        if result:
            symbol = result["symbol"]
            company_name = result["company_name"]

            if cls._is_yahoo_duplicate_of_existing(
                candidate=candidate,
                symbol=symbol,
                company_name=company_name,
                existing_entities=existing_entities,
            ):
                logger.info(
                    f"Skipping Yahoo result '{symbol}' for candidate='{candidate}' "
                    "because a high-confidence local entity already covers it."
                )
                return None

            entity = ResolvedEntity(
                ticker=symbol,
                company_name=company_name,
                exchange="NASDAQ" if symbol in ["GOOGL", "TSLA", "AAPL", "NVDA"] else "NSE",
                country="US" if symbol in ["GOOGL", "TSLA", "AAPL", "NVDA"] else "IN",
                confidence=0.85,
                resolution_source="YAHOO_FINANCE",
                aliases=cls._build_aliases(symbol),
                query_span=candidate
            )

            # Background persistence
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(EntityResolver._persist_new_company(
                    symbol=symbol,
                    company_name=company_name,
                    industry=result.get("industry", "N/A"),
                    sector=result.get("sector", "N/A")
                ))
            except RuntimeError:
                import threading
                def run_async():
                    asyncio.run(EntityResolver._persist_new_company(
                        symbol=symbol,
                        company_name=company_name,
                        industry=result.get("industry", "N/A"),
                        sector=result.get("sector", "N/A")
                    ))
                threading.Thread(target=run_async).start()

            EntityResolver._ticker_to_company[symbol] = company_name
            EntityResolver._company_to_ticker[company_name.lower().strip()] = symbol

            cls._yahoo_lru_cache[candidate_normalized] = entity
            return entity
        return None

    @classmethod
    async def _discover_via_yahoo_async(
        cls,
        candidate: str,
        existing_entities: Optional[List[ResolvedEntity]] = None,
    ) -> Optional[ResolvedEntity]:
        from src.services.entity_resolver import EntityResolver
        candidate_normalized = candidate.lower().strip()

        if candidate_normalized in cls._yahoo_lru_cache:
            return cls._yahoo_lru_cache[candidate_normalized]

        cand_term = cls._extract_candidate_search_term_pipeline(candidate_normalized)
        if not cand_term:
            return None

        result = await EntityResolver._search_yahoo_finance_async(cand_term)
        if result:
            symbol = result["symbol"]
            company_name = result["company_name"]

            if cls._is_yahoo_duplicate_of_existing(
                candidate=candidate,
                symbol=symbol,
                company_name=company_name,
                existing_entities=existing_entities,
            ):
                logger.info(
                    f"Skipping Yahoo result '{symbol}' for candidate='{candidate}' "
                    "because a high-confidence local entity already covers it."
                )
                return None

            entity = ResolvedEntity(
                ticker=symbol,
                company_name=company_name,
                exchange="NASDAQ" if symbol in ["GOOGL", "TSLA", "AAPL", "NVDA"] else "NSE",
                country="US" if symbol in ["GOOGL", "TSLA", "AAPL", "NVDA"] else "IN",
                confidence=0.85,
                resolution_source="YAHOO_FINANCE",
                aliases=cls._build_aliases(symbol),
                query_span=candidate
            )

            await EntityResolver._persist_new_company(
                symbol=symbol,
                company_name=company_name,
                industry=result.get("industry", "N/A"),
                sector=result.get("sector", "N/A")
            )

            EntityResolver._ticker_to_company[symbol] = company_name
            EntityResolver._company_to_ticker[company_name.lower().strip()] = symbol

            cls._yahoo_lru_cache[candidate_normalized] = entity
            return entity
        return None

    @classmethod
    def _rank_and_deduplicate(cls, entities: List[ResolvedEntity], query: str) -> EntityCollection:
        ticker_map = {}
        for e in entities:
            ticker_upper = e.ticker.upper().strip()
            if ticker_upper not in ticker_map or e.confidence > ticker_map[ticker_upper].confidence:
                ticker_map[ticker_upper] = e

        filtered_entities = []
        resolution_warnings = []
        for ticker, e in ticker_map.items():
            if e.confidence >= cls.MINIMUM_CONFIDENCE_THRESHOLD:
                filtered_entities.append(e)
            else:
                resolution_warnings.append(f"Entity '{e.company_name}' ({e.ticker}) filtered out due to low confidence ({e.confidence:.2f})")

        filtered_entities.sort(key=lambda x: x.confidence, reverse=True)

        if len(filtered_entities) > cls.MAX_ENTITIES_PER_COLLECTION:
            discarded = filtered_entities[cls.MAX_ENTITIES_PER_COLLECTION:]
            filtered_entities = filtered_entities[:cls.MAX_ENTITIES_PER_COLLECTION]
            for de in discarded:
                resolution_warnings.append(f"Entity '{de.company_name}' ({de.ticker}) discarded due to max entities limit of {cls.MAX_ENTITIES_PER_COLLECTION}")

        for i, e in enumerate(filtered_entities):
            e.is_primary = (i == 0)

        if len(filtered_entities) == 0:
            mode = "EDUCATIONAL"
        elif len(filtered_entities) == 1:
            mode = "SINGLE"
        else:
            mode = "MULTI"

        return EntityCollection(
            entities=filtered_entities,
            query=query,
            resolution_mode=mode,
            total_found=len(filtered_entities),
            resolution_warnings=resolution_warnings
        )

    @classmethod
    def _validate(cls, collection: EntityCollection, intent: str) -> None:
        if not intent:
            return

        from src.services.entity_resolver import EntityResolutionError

        single_company_intents = {
            "STOCK_ANALYSIS",
            "FUNDAMENTAL_ANALYSIS",
            "TECHNICAL_ANALYSIS",
            "STOCK_MOVEMENT",
            "NEWS_ANALYSIS",
            "RISK_ANALYSIS",
            "COMPANY_OVERVIEW"
        }

        num_entities = len(collection.entities)

        if intent in single_company_intents:
            if num_entities > 1:
                raise EntityResolutionError("Please proceed with only one stock or company at a time.")
        elif intent == "COMPARISON":
            if num_entities < 2:
                raise EntityResolutionError("Comparison requires at least two companies.")
            if num_entities > 5:
                raise EntityResolutionError("Please proceed with up to 5 stocks or companies at a time for comparison.")
        elif intent == "PEER_COMPARISON":
            if num_entities < 1:
                raise EntityResolutionError("Peer comparison requires at least one company.")
        elif intent == "GENERALIZED":
            if num_entities > 2:
                raise EntityResolutionError("Please proceed with up to 2 stocks or companies at a time for generalized queries.")
