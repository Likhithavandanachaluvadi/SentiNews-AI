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

COMMON_ENGLISH_TICKER_WORDS = {
    "am", "an", "as", "at", "be", "by", "can", "do", "for", "go", "he",
    "i", "if", "in", "is", "it", "may", "me", "my", "no", "of", "on", "or",
    "so", "to", "up", "us", "we",
    "are", "but", "did", "had", "has", "her", "his", "how", "new", "not",
    "now", "one", "our", "out", "own", "see", "she", "the", "too", "was",
    "who", "why", "yes", "yet", "you",
    "been", "best", "does", "from", "good", "have", "just", "like", "long",
    "more", "most", "must", "news", "only", "over", "same", "some", "such",
    "than", "that", "then", "they", "this", "very", "what", "when", "will",
    "with", "would",
}

ACTION_VERBS = {
    "analyze", "analyse", "rank", "identify", "compare", "evaluate",
    "research", "tell", "show", "find", "list", "check", "study",
    "report", "predict", "forecast", "explain", "describe", "summarize",
    "suggest", "recommend", "give", "get", "look", "outlook", "overview"
}

QUESTION_WORDS = {
    "why", "what", "when", "where", "who", "which", "how", "whose", "whom"
}

COUNTRY_DEMONYMS = {
    "india", "indian", "us", "usa", "american", "america", "china", "chinese",
    "japan", "japanese", "uk", "british", "germany", "german", "france", "french",
    "global", "world", "international"
}

TIME_UNITS = {
    "month", "months", "year", "years", "day", "days", "week", "weeks",
    "quarter", "quarters", "q1", "q2", "q3", "q4", "annual", "annually",
    "quarterly", "yoy", "qoq"
}

STOP_WORDS_GENERIC = {
    "the", "a", "an", "in", "on", "at", "by", "for", "with", "about", "against",
    "between", "into", "through", "during", "before", "after", "above", "below",
    "to", "from", "up", "down", "over", "under", "and", "or", "but", "so", "if",
    "than", "then", "of", "supporting", "evidence", "government", "investment",
    "investments", "investing", "companies", "company", "stock", "stocks",
    "share", "shares", "price", "prices", "market", "markets", "industry",
    "industries", "sector", "sectors", "impact", "next", "future", "trend",
    "trends", "growth", "prospects", "performance", "analysis", "data",
    "details", "info", "information", "over", "latest", "update", "updates",
    "increasing", "decreasing", "rising", "falling", "top", "best", "worst",
    "high", "low", "with", "without", "among"
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
        "EV": "industry_theme",
        "Renewable Energy": "industry_theme",
        "Clean Energy": "industry_theme"
    }

    @classmethod
    def _is_explicit_ticker_mention(cls, candidate: str, query: str) -> bool:
        candidate_clean = candidate.strip()
        candidate_upper = candidate_clean.upper()

        if not candidate_clean:
            return False

        # Tickers are normally typed in uppercase. Preserve that path so
        # legitimate short symbols such as CAN, MAY, IT, or AI still work.
        if candidate_clean == candidate_upper and re.search(r"[A-Z]", candidate_clean):
            return True

        # Symbols with exchange-style punctuation are intentional ticker inputs.
        if re.search(r"[0-9&\-._]", candidate_clean):
            return True

        query_lower = query.lower()
        token = re.escape(candidate_clean.lower())
        explicit_patterns = [
            rf"\bticker\s+{token}\b",
            rf"\bsymbol\s+{token}\b",
            rf"\bquote\s+{token}\b",
            rf"\b{token}\s+ticker\b",
            rf"\b{token}\s+symbol\b",
        ]
        return any(re.search(pattern, query_lower) for pattern in explicit_patterns)

    @classmethod
    def _is_common_word_ticker_false_positive(cls, candidate: str, query: str) -> bool:
        cand_lower = candidate.lower().strip()
        if cand_lower not in COMMON_ENGLISH_TICKER_WORDS:
            return False

        return not cls._is_explicit_ticker_mention(candidate, query)

    @classmethod
    def _classify_candidate(cls, candidate: str, query: str) -> str:
        cand_upper = candidate.upper().strip()
        cand_lower = candidate.lower().strip()
        query_lower = query.lower()

        # Clean articles from start if present (e.g. "The Indian" -> "indian")
        cand_clean_word = re.sub(r'^(the|a|an)\s+', '', cand_lower).strip()

        # Step 0.0: Check if candidate is a financial action word or generic query phrase
        ignored_phrases = {
            "buy", "sell", "invest", "investing", "hold", "purchase", "recommend",
            "should i", "should", "would", "could", "investor", "investors", "portfolio",
            "i", "me", "my", "to", "now"
        }
        if cls._is_common_word_ticker_false_positive(candidate, query):
            return "generic_phrase"
        if cand_lower in ignored_phrases:
            return "generic_phrase"
        span_tokens = [w for w in re.findall(r'\b[a-z]+\b', cand_lower) if w]
        if (
            span_tokens
            and all(t in COMMON_ENGLISH_TICKER_WORDS for t in span_tokens)
            and not cls._is_explicit_ticker_mention(candidate, query)
        ):
            return "generic_phrase"
        if span_tokens and all(t in ignored_phrases for t in span_tokens):
            return "generic_phrase"

        # Step 0.1: Check if single word candidate is a corporate stopword
        corporate_stopwords = {
            "corporation", "corp", "limited", "ltd", "inc", "incorporated", "company", "bank", "industries", "group", "holdings", "private", "pvt",
            "services", "motors", "holding", "holdings", "steel", "power", "chemicals", "pharma"
        }
        if len(cand_lower.split()) == 1 and cand_lower in corporate_stopwords:
            return "generic_phrase"

        # Step 0.2: Direct database lookup check to ensure known companies are classified as company/ticker first
        # But skip for protected concepts (like "AI" or "IT") so that registry logic handles them case-specifically
        is_protected = cand_upper in cls.PROTECTED_CONCEPTS or candidate in cls.PROTECTED_CONCEPTS
        if not is_protected:
            from src.services.entity_resolver import EntityResolver, LEGACY_EDGE_CASES
            EntityResolver.initialize_sync()
            if candidate in EntityResolver._ticker_to_company or cand_upper in EntityResolver._ticker_to_company:
                return "ticker"
            if cand_lower in EntityResolver._company_to_ticker or cand_lower in LEGACY_EDGE_CASES:
                return "company"
            from src.services.entity_resolver import clean_company_name
            cand_clean_name = clean_company_name(cand_lower)
            for comp_name in EntityResolver._company_to_ticker:
                if clean_company_name(comp_name) == cand_clean_name:
                    return "company"

        # 1. Numbers & Time Periods
        if cand_lower.isdigit():
            words_near = re.findall(r'\b[a-z0-9]+\b', query_lower)
            if any(tu in words_near for tu in TIME_UNITS):
                return "time_period"
            return "number"

        if re.search(r'^\d+\s*(months?|years?|days?|weeks?|quarters?)$', cand_lower):
            return "time_period"

        # 2. Action Verbs
        if cand_lower in ACTION_VERBS or cand_clean_word in ACTION_VERBS:
            return "action"

        # 3. Question Words
        if cand_lower in QUESTION_WORDS:
            return "question_word"

        # 4. Country / Demonym
        if cand_lower in COUNTRY_DEMONYMS or cand_clean_word in COUNTRY_DEMONYMS:
            from src.services.entity_resolver import EntityResolver
            EntityResolver.initialize_sync()
            if cand_upper not in EntityResolver._ticker_to_company and cand_lower not in EntityResolver._company_to_ticker:
                return "country"

        # 5. Sector & Theme Handling
        theme_indicators = {"companies", "stocks", "shares", "sectors", "industries", "trends", "themes", "sector", "industry", "theme"}
        cand_words = set(re.findall(r'\b[a-z]+\b', cand_lower))
        if cand_words.intersection(theme_indicators):
            sector_names = {"banking", "it", "pharma", "energy", "auto", "technology", "fmcg", "telecom", "infrastructure"}
            if any(sn in cand_lower for sn in sector_names):
                return "sector"
            return "industry_theme"

        sector_keywords = ["banking", "it", "pharma", "energy", "auto", "technology", "renewable energy", "clean energy"]
        sector_indicators = ["sector", "industry", "companies"]
        
        for sect in sector_keywords:
            for ind in sector_indicators:
                phrase = f"{sect} {ind}"
                if phrase in cand_lower or cand_lower == phrase:
                    return "sector" if sect in ["banking", "it", "pharma", "energy", "auto", "technology"] else "industry_theme"
                if cand_lower == sect:
                    pattern = rf"\b{re.escape(cand_lower)}\s+{re.escape(ind)}\b"
                    if re.search(pattern, query_lower):
                        return "sector"
                    pattern_pre = rf"\b{re.escape(ind)}\s+of\s+{re.escape(cand_lower)}\b"
                    if re.search(pattern_pre, query_lower):
                        return "sector"

        if cand_lower in ["renewable energy", "clean energy", "solar", "ev", "electric vehicles"]:
            return "industry_theme"

        # 6. Protected Concepts Registry Lookup
        for concept, concept_type in cls.PROTECTED_CONCEPTS.items():
            if cand_upper == concept.upper() or cand_lower == concept.lower():
                if cand_upper == "AI":
                    theme_words = ["theme", "trends", "stocks", "companies", "shares", "sectors", "industries"]
                    if any(tw in query_lower for tw in theme_words):
                        return "technology_concept"
                    positive_company_signals = ["stock ", "share ", "listed", "earnings", "market cap", "valuation", "fundamentals", "ticker"]
                    if any(sig in query_lower for sig in positive_company_signals):
                        return "company"
                    return "technology_concept"
                if cand_upper == "IT":
                    for ind in ["sector", "industry", "companies"]:
                        if f"it {ind}" in query_lower:
                            return "sector"
                    return "sector"
                return concept_type

        # 7. Suffix / Local Database matching
        company_suffixes = ["ltd", "limited", "inc", "corp", "corporation", "co", "pvt", "private"]
        if any(rf"\b{re.escape(suff)}\b" in cand_lower for suff in company_suffixes):
            return "company"

        from src.services.entity_resolver import EntityResolver, LEGACY_EDGE_CASES
        EntityResolver.initialize_sync()
        if candidate in EntityResolver._ticker_to_company or cand_upper in EntityResolver._ticker_to_company:
            return "ticker"

        if cand_lower in EntityResolver._company_to_ticker or cand_lower in LEGACY_EDGE_CASES:
            return "company"

        # 8. Stop Words & Generic English Phrases
        cand_tokens = [w for w in cand_lower.split() if w]
        if any(w in ACTION_VERBS for w in cand_tokens) and not any(suff in cand_lower for suff in company_suffixes):
            return "action" if len(cand_tokens) == 1 else "generic_phrase"

        if all(w in STOP_WORDS_GENERIC or w in ACTION_VERBS or w in QUESTION_WORDS or w in COUNTRY_DEMONYMS for w in cand_tokens):
            return "generic_phrase"

        # 9. Fallback Classification
        if re.match(r"^[A-Z0-9&\-._]{2,6}$", candidate) and cand_lower not in NON_ENTITY_CANDIDATES:
            return "company"

        if re.match(r"^[A-Z][a-zA-Z0-9&\-._\s]*$", candidate) and len(candidate) >= 3 and len(cand_tokens) <= 4:
            # Check if it contains action verbs, demonyms, or all generic tokens
            has_action = any(w in ACTION_VERBS for w in cand_tokens)
            all_generic = all(w in STOP_WORDS_GENERIC or w in ACTION_VERBS or w in QUESTION_WORDS or w in COUNTRY_DEMONYMS for w in cand_tokens)
            if not has_action and not all_generic:
                return "company"

        return "generic_phrase"

    @classmethod
    def _validate_context(cls, candidate: str, query: str) -> bool:
        from src.services.entity_resolver import EntityResolver, LEGACY_EDGE_CASES
        EntityResolver.initialize_sync()
        cand_upper = candidate.upper().strip()
        cand_lower = candidate.lower().strip()

        # Exact tickers and exact company names in local baseline/DB are always valid stock queries
        if cand_upper in EntityResolver._ticker_to_company or cand_lower in EntityResolver._company_to_ticker or cand_lower in LEGACY_EDGE_CASES:
            return True

        query_lower = query.lower()
        
        # If the query contains thematic indicators (plural company/stock terms, sector/theme descriptors),
        # then restrict matching only to exact local database matches. Prevent generic terms from dynamically 
        # resolving to single stocks.
        theme_keywords = {
            "companies", "stocks", "shares", "sectors", "industries", "trends", "themes",
            "sector", "industry", "theme", "adoption", "concepts", "concept"
        }
        query_words = set(re.findall(r'\b[a-z]+\b', query_lower))
        if query_words.intersection(theme_keywords):
            return False
        positive_company_signals = ["stock", "share", "company", "listed", "ticker", "valuation", "earnings", "market cap", "fundamentals", "outlook"]
        negative_company_signals = ["industry", "sector", "explain", "meaning", "concept", "technology", "adoption", "trend", "beginner"]
        
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

        # 1. Initialize & load DB
        from src.services.entity_resolver import EntityResolver
        EntityResolver.initialize_sync()

        # 2. Tokenize query
        raw_words = query.strip().split()
        words = []
        for w in raw_words:
            cleaned_w = w.strip(" ?.,!():;\"'")
            cleaned_w = re.sub(r"'[sS]$", "", cleaned_w)
            cleaned_w = cleaned_w.rstrip("'")
            if cleaned_w:
                words.append(cleaned_w)

        num_words = len(words)
        candidate_matches = []

        generic_words = {
            "bank", "industries", "limited", "corp", "corporation", "ltd", "inc", "company",
            "services", "motors", "holding", "holdings", "group", "india", "state", "national",
            "mutual", "fund", "funds", "general", "steel", "power", "chemicals", "pharma"
        }

        # 3. Generate and match n-grams (5 down to 1)
        blocked_connectors = {"and", "or", "vs", "versus", "compare", "between", "against", "with", "compared"}
        for n in range(min(5, num_words), 0, -1):
            for start in range(num_words - n + 1):
                end = start + n - 1
                candidate_span = " ".join(words[start:end+1])
                candidate_lower = candidate_span.lower().strip()

                # Skip candidate if it contains comparison/conjunction connectors
                span_words = set(re.findall(r'\b[a-z]+\b', candidate_lower))
                if span_words.intersection(blocked_connectors):
                    continue

                # Skip single-word generic lookups
                if n == 1 and candidate_lower in generic_words:
                    continue

                # Skip if not classified as company/ticker
                ent_type = cls._classify_candidate(candidate_span, query)
                if ent_type not in ("company", "ticker"):
                    continue

                # Perform match
                entity = cls._match_candidate(candidate_span)
                if not entity:
                    entity = cls._fuzzy_match(candidate_span)

                if entity:
                    candidate_matches.append({
                        "entity": entity,
                        "start_idx": start,
                        "end_idx": end,
                        "length": n,
                        "confidence": entity.confidence
                    })

        # 4. Greedy Selection (by length descending, then confidence descending)
        candidate_matches.sort(key=lambda x: (x["length"], x["confidence"]), reverse=True)

        selected_indices = set()
        accepted_entities = []

        for match in candidate_matches:
            start = match["start_idx"]
            end = match["end_idx"]
            span_indices = set(range(start, end + 1))

            if not span_indices.intersection(selected_indices):
                if cls._validate_context(match["entity"].query_span, query):
                    accepted_entities.append(match["entity"])
                    selected_indices.update(span_indices)

        # 5. Fallback Yahoo Discovery for unresolved candidates
        extracted = cls._extract_candidates(query)
        for cand in extracted:
            ent_type = cls._classify_candidate(cand, query)
            if ent_type not in ("company", "ticker"):
                continue

            if cls._is_candidate_covered_by_high_confidence_local_entity(cand, accepted_entities):
                continue

            # Substring cover check
            cand_lower = cand.lower().strip()
            is_covered = False
            for ae in accepted_entities:
                if cand_lower in ae.company_name.lower() or cand_lower in ae.query_span.lower() or ae.ticker.lower() == cand_lower:
                    is_covered = True
                    break
            if is_covered:
                continue

            discovered = cls._discover_via_yahoo_sync(cand, existing_entities=accepted_entities)
            if discovered:
                accepted_entities.append(discovered)

        # 6. Rank and Deduplicate
        collection = cls._rank_and_deduplicate(accepted_entities, query)

        # 7. Validation Gate
        if intent:
            cls._validate(collection, intent)

        return collection

    @classmethod
    async def resolve_entities(cls, query: str, intent: Optional[str] = None) -> EntityCollection:
        """Asynchronous multi-entity resolver pipeline."""
        if not query or not query.strip():
            return EntityCollection(entities=[], query=query, resolution_mode="EDUCATIONAL", total_found=0)

        # 1. Initialize & load DB
        from src.services.entity_resolver import EntityResolver
        await EntityResolver.initialize_async()

        # 2. Tokenize query
        raw_words = query.strip().split()
        words = []
        for w in raw_words:
            cleaned_w = w.strip(" ?.,!():;\"'")
            cleaned_w = re.sub(r"'[sS]$", "", cleaned_w)
            cleaned_w = cleaned_w.rstrip("'")
            if cleaned_w:
                words.append(cleaned_w)

        num_words = len(words)
        candidate_matches = []

        generic_words = {
            "bank", "industries", "limited", "corp", "corporation", "ltd", "inc", "company",
            "services", "motors", "holding", "holdings", "group", "india", "state", "national",
            "mutual", "fund", "funds", "general", "steel", "power", "chemicals", "pharma"
        }

        # 3. Generate and match n-grams (5 down to 1)
        blocked_connectors = {"and", "or", "vs", "versus", "compare", "between", "against", "with", "compared"}
        for n in range(min(5, num_words), 0, -1):
            for start in range(num_words - n + 1):
                end = start + n - 1
                candidate_span = " ".join(words[start:end+1])
                candidate_lower = candidate_span.lower().strip()

                # Skip candidate if it contains comparison/conjunction connectors
                span_words = set(re.findall(r'\b[a-z]+\b', candidate_lower))
                if span_words.intersection(blocked_connectors):
                    continue

                # Skip single-word generic lookups
                if n == 1 and candidate_lower in generic_words:
                    continue

                # Skip if not classified as company/ticker
                ent_type = cls._classify_candidate(candidate_span, query)
                if ent_type not in ("company", "ticker"):
                    continue

                # Perform match
                entity = cls._match_candidate(candidate_span)
                if not entity:
                    entity = cls._fuzzy_match(candidate_span)

                if entity:
                    candidate_matches.append({
                        "entity": entity,
                        "start_idx": start,
                        "end_idx": end,
                        "length": n,
                        "confidence": entity.confidence
                    })

        # 4. Greedy Selection (by length descending, then confidence descending)
        candidate_matches.sort(key=lambda x: (x["length"], x["confidence"]), reverse=True)

        selected_indices = set()
        accepted_entities = []

        for match in candidate_matches:
            start = match["start_idx"]
            end = match["end_idx"]
            span_indices = set(range(start, end + 1))

            if not span_indices.intersection(selected_indices):
                if cls._validate_context(match["entity"].query_span, query):
                    accepted_entities.append(match["entity"])
                    selected_indices.update(span_indices)

        # 5. Fallback Yahoo Discovery for unresolved candidates
        extracted = cls._extract_candidates(query)
        tasks = []
        for cand in extracted:
            ent_type = cls._classify_candidate(cand, query)
            if ent_type not in ("company", "ticker"):
                continue

            if cls._is_candidate_covered_by_high_confidence_local_entity(cand, accepted_entities):
                continue

            # Substring cover check
            cand_lower = cand.lower().strip()
            is_covered = False
            for ae in accepted_entities:
                if cand_lower in ae.company_name.lower() or cand_lower in ae.query_span.lower() or ae.ticker.lower() == cand_lower:
                    is_covered = True
                    break
            if is_covered:
                continue

            tasks.append(cls._discover_via_yahoo_async(cand, existing_entities=list(accepted_entities)))

        if tasks:
            yahoo_results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in yahoo_results:
                if res and isinstance(res, ResolvedEntity):
                    accepted_entities.append(res)

        # 6. Rank and Deduplicate
        collection = cls._rank_and_deduplicate(accepted_entities, query)

        # 7. Validation Gate
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

            # 1. Tickers (All-caps 1-15 chars, exclude pure numbers)
            all_caps = re.findall(r'\b[A-Z0-9&\-._]{1,15}\b', seg_stripped)
            for ac in all_caps:
                if ac.lower() in NON_ENTITY_CANDIDATES or ac.isdigit():
                    continue
                if ac not in candidates and ac not in ["THE", "IS", "AND", "FOR", "OF", "IN", "TO", "A", "AN", "AT", "BY"]:
                    candidates.append(ac)

            # 2. Title-case words (2-4 words)
            title_case = re.findall(r'\b[A-Z][a-z0-9&\-._]*(?:\s+[A-Z][a-z0-9&\-._]*){0,3}\b', seg_stripped)
            for tc in title_case:
                if tc.lower().strip() in NON_ENTITY_CANDIDATES:
                    continue
                if tc not in candidates and len(tc) >= 2:
                    candidates.append(tc)

            # 3. Cleaned segment itself (only if span is <= 4 words)
            if seg_stripped.lower().strip() in NON_ENTITY_CANDIDATES:
                continue
            if seg_stripped not in candidates and len(seg_stripped) >= 2 and len(seg_stripped.split()) <= 4:
                candidates.append(seg_stripped)

        # Extract primary action verb or lead word if present at start of query
        first_word = query_clean.split()[0].strip(" ?,.!").lower() if query_clean.split() else ""
        if first_word in ACTION_VERBS and first_word.capitalize() not in candidates and first_word not in candidates:
            candidates.insert(0, first_word.capitalize())

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

        candidate_clean = clean_company_name(candidate_lower)
        for comp_name, sym in EntityResolver._company_to_ticker.items():
            if clean_company_name(comp_name) == candidate_clean:
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
        # Only run for single-word candidates to avoid matching multi-word spans to incorrect companies
        if len(candidate_lower.split()) == 1:
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
                "investment", "investments", "investing", "finance", "financial", "equity", "securities", "capital", "services", "service", "wealth", "advisory",
                "indian", "india", "american", "america", "global", "national", "international", "central", "overseas", "state", "general", "sun", "life"
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
            r'^(is|should i buy|should i invest in|what is|outlook for|evaluate|analyze|analyse|rank|identify|compare|tell me about|how is|price of)\b',
            '', cleaned, flags=re.IGNORECASE
        ).strip()
        cleaned = re.sub(
            r'\b(stock|share|shares|investment|financials|fundamentals|technical|news|analysis|report|a good buy|overvalued|undervalued|today|supporting|evidence|government|months?|years?)\b',
            '', cleaned, flags=re.IGNORECASE
        ).strip()

        cleaned = re.sub(r'[^\w\s&.\-]', '', cleaned).strip()
        words = [w for w in cleaned.split() if w.lower() not in STOP_WORDS_GENERIC and w.lower() not in ACTION_VERBS and w.lower() not in COUNTRY_DEMONYMS and not w.isdigit()]
        if len(words) > 0:
            return " ".join(words[:4])
        return None

    @classmethod
    def _discover_via_yahoo_sync(
        cls,
        candidate: str,
        existing_entities: Optional[List[ResolvedEntity]] = None,
    ) -> Optional[ResolvedEntity]:
        import difflib
        from src.services.entity_resolver import EntityResolver, clean_company_name
        candidate_normalized = candidate.lower().strip()

        if candidate_normalized in cls._yahoo_lru_cache:
            return cls._yahoo_lru_cache[candidate_normalized]

        cand_term = cls._extract_candidate_search_term_pipeline(candidate_normalized)
        if not cand_term:
            return None

        # Check if candidate is a low-confidence misspelling of a local entity
        for sym, name in EntityResolver._ticker_to_company.items():
            name_clean = clean_company_name(name)
            ratio = difflib.SequenceMatcher(None, candidate_normalized, name_clean).ratio()
            if 0.75 <= ratio < cls.FUZZY_MATCH_THRESHOLD:
                logger.info(
                    f"Skipping Yahoo discovery for candidate='{candidate}' "
                    f"because it is a low-confidence misspelling of local entity '{name}' ({ratio:.2f})."
                )
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
                threading.Thread(target=run_async, daemon=True).start()

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
        import difflib
        from src.services.entity_resolver import EntityResolver, clean_company_name
        candidate_normalized = candidate.lower().strip()

        if candidate_normalized in cls._yahoo_lru_cache:
            return cls._yahoo_lru_cache[candidate_normalized]

        cand_term = cls._extract_candidate_search_term_pipeline(candidate_normalized)
        if not cand_term:
            return None

        # Check if candidate is a low-confidence misspelling of a local entity
        for sym, name in EntityResolver._ticker_to_company.items():
            name_clean = clean_company_name(name)
            ratio = difflib.SequenceMatcher(None, candidate_normalized, name_clean).ratio()
            if 0.75 <= ratio < cls.FUZZY_MATCH_THRESHOLD:
                logger.info(
                    f"Skipping Yahoo discovery for candidate='{candidate}' "
                    f"because it is a low-confidence misspelling of local entity '{name}' ({ratio:.2f})."
                )
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
