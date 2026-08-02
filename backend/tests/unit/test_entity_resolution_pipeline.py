import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from src.services.entity_models import ResolvedEntity, EntityCollection
from src.services.entity_resolution_pipeline import EntityResolutionPipeline
from src.services.entity_resolver import EntityResolver, EntityResolutionError

@pytest.fixture(autouse=True)
def setup_caches():
    # Make sure caches are initialized
    EntityResolver.initialize_sync()

def test_extract_candidates():
    # Standard single company
    cands = EntityResolutionPipeline._extract_candidates("Analyze TCS")
    assert "TCS" in cands
    
    # Conjunction safety - should not split since no comparison keyword and segments aren't resolvable
    cands = EntityResolutionPipeline._extract_candidates("Infosys and its subsidiaries")
    assert "Infosys and its subsidiaries" in cands or "Infosys" in cands
    
    # Comparison connector split
    cands = EntityResolutionPipeline._extract_candidates("Compare Infosys and TCS")
    assert "Infosys" in cands or "infosys" in cands
    assert "TCS" in cands
    
    # Title case extraction
    cands = EntityResolutionPipeline._extract_candidates("Tell me about Tata Consultancy Services")
    assert "Tata Consultancy Services" in cands

def test_match_candidate_exact_ticker():
    # Exact ticker NSE
    entity = EntityResolutionPipeline._match_candidate("TCS")
    assert entity is not None
    assert entity.ticker == "TCS"
    assert entity.resolution_source == "EXACT_TICKER"
    assert entity.confidence == 1.00
    assert entity.exchange == "NSE"

def test_match_candidate_legacy_alias():
    # sbi -> SBIN
    entity = EntityResolutionPipeline._match_candidate("sbi")
    assert entity is not None
    assert entity.ticker == "SBIN"
    assert entity.resolution_source == "LEGACY_ALIAS"
    assert entity.confidence == 0.95

def test_match_candidate_exact_name():
    # exact name
    entity = EntityResolutionPipeline._match_candidate("tata consultancy services limited")
    assert entity is not None
    assert entity.ticker == "TCS"
    assert entity.resolution_source == "EXACT_NAME"

def test_match_candidate_normalized_industry_alias():
    entity = EntityResolutionPipeline._match_candidate("Sun Pharma")
    assert entity is not None
    assert entity.ticker == "SUNPHARMA"
    assert entity.resolution_source == "EXACT_NAME"
    
    # exact name match
    entity = EntityResolutionPipeline._match_candidate("tata consultancy services")
    assert entity is not None
    assert entity.ticker == "TCS"
    assert entity.resolution_source == "EXACT_NAME"

def test_match_candidate_whole_word():
    # Whole word match in name
    entity = EntityResolutionPipeline._match_candidate("consultancy")
    assert entity is not None
    assert entity.ticker == "TCS"
    assert entity.resolution_source == "WHOLE_WORD"

def test_fuzzy_match():
    # Typos in company name
    entity = EntityResolutionPipeline._fuzzy_match("Infosiss")
    assert entity is not None
    assert entity.ticker == "INFY"
    assert entity.resolution_source == "FUZZY_MATCH"
    assert entity.confidence >= 0.80

def test_common_sentence_word_does_not_resolve_as_ticker():
    EntityResolver._ticker_to_company["CAN"] = "Canaan Inc."
    EntityResolver._company_to_ticker["canaan inc."] = "CAN"

    q = (
        "I'm a beginner investor. I noticed HDFC Bank shares have been in the news "
        "recently. Can you explain what happened, why it's important, and whether "
        "this could affect the bank's long-term business?"
    )

    col = EntityResolutionPipeline.resolve_entities_sync(q, intent="NEWS_ANALYSIS")

    assert col.total_found == 1
    assert col.primary_ticker == "HDFCBANK"
    assert "CAN" not in col.all_tickers

def test_common_modal_words_are_not_discovered_as_companies():
    for word in ["Can", "Will", "May"]:
        assert EntityResolutionPipeline._classify_candidate(word, f"{word} you explain HDFC Bank?") == "generic_phrase"
    assert EntityResolutionPipeline._classify_candidate("May I", "May I know latest Reliance news?") == "generic_phrase"

def test_explicit_uppercase_common_word_ticker_still_resolves():
    EntityResolver._ticker_to_company["CAN"] = "Canaan Inc."
    EntityResolver._company_to_ticker["canaan inc."] = "CAN"

    assert EntityResolutionPipeline._classify_candidate("CAN", "Analyze CAN stock") == "ticker"
    entity = EntityResolutionPipeline._match_candidate("CAN")
    assert entity is not None
    assert entity.ticker == "CAN"

def test_rank_and_deduplicate():
    e1 = ResolvedEntity(
        ticker="INFY",
        company_name="Infosys Limited",
        confidence=0.97,
        resolution_source="EXACT_NAME"
    )
    e2 = ResolvedEntity(
        ticker="INFY",
        company_name="Infosys Limited",
        confidence=1.00,
        resolution_source="EXACT_TICKER"
    )
    e3 = ResolvedEntity(
        ticker="TCS",
        company_name="Tata Consultancy Services Limited",
        confidence=0.95,
        resolution_source="EXACT_NAME"
    )
    
    col = EntityResolutionPipeline._rank_and_deduplicate([e1, e2, e3], "Compare INFY and TCS")
    assert col.total_found == 2
    assert col.resolution_mode == "MULTI"
    assert col.entities[0].ticker == "INFY"
    assert col.entities[0].confidence == 1.00
    assert col.entities[0].is_primary is True
    assert col.entities[1].ticker == "TCS"
    assert col.entities[1].is_primary is False

@patch("src.services.entity_resolver.EntityResolver._search_yahoo_finance_sync")
def test_high_confidence_local_match_skips_yahoo_false_positive(mock_yahoo_search):
    mock_yahoo_search.return_value = {
        "symbol": "0221",
        "company_name": "TCS Group Holdings Berhad",
        "industry": "Technology",
        "sector": "Technology"
    }

    EntityResolutionPipeline._yahoo_lru_cache.clear()

    col = EntityResolutionPipeline.resolve_entities_sync("TCS stock analysis", intent="STOCK_ANALYSIS")

    assert col.total_found == 1
    assert col.primary_ticker == "TCS"
    assert col.primary.company_name.lower().startswith("tata consultancy")
    mock_yahoo_search.assert_not_called()

@patch("src.services.entity_resolver.EntityResolver._search_yahoo_finance_sync")
def test_yahoo_result_duplicate_of_local_entity_is_not_persisted(mock_yahoo_search):
    mock_yahoo_search.return_value = {
        "symbol": "0221",
        "company_name": "TCS Group Holdings Berhad",
        "industry": "Technology",
        "sector": "Technology"
    }

    local = ResolvedEntity(
        ticker="TCS",
        company_name="Tata Consultancy Services Limited",
        confidence=1.0,
        resolution_source="EXACT_TICKER",
        aliases=["tcs", "tata consultancy services"],
        query_span="TCS"
    )

    EntityResolutionPipeline._yahoo_lru_cache.clear()

    entity = EntityResolutionPipeline._discover_via_yahoo_sync(
        "TCS stock analysis",
        existing_entities=[local],
    )

    assert entity is None
    mock_yahoo_search.assert_called_once()

def test_validation_gate():
    # Valid single company
    e1 = ResolvedEntity(ticker="INFY", company_name="Infosys Limited", confidence=1.0, resolution_source="EXACT_TICKER")
    col_single = EntityCollection(entities=[e1], query="Analyze INFY", resolution_mode="SINGLE", total_found=1)
    
    # Valid intent STOCK_ANALYSIS
    EntityResolutionPipeline._validate(col_single, "STOCK_ANALYSIS") # Should not raise
    
    # Invalid multi-company for STOCK_ANALYSIS
    e2 = ResolvedEntity(ticker="TCS", company_name="TCS Ltd", confidence=1.0, resolution_source="EXACT_TICKER")
    col_multi = EntityCollection(entities=[e1, e2], query="Analyze INFY and TCS", resolution_mode="MULTI", total_found=2)
    
    with pytest.raises(EntityResolutionError):
        EntityResolutionPipeline._validate(col_multi, "STOCK_ANALYSIS")
        
    # Valid COMPARISON
    EntityResolutionPipeline._validate(col_multi, "COMPARISON") # Should not raise
    
    # Invalid COMPARISON with 1 entity
    with pytest.raises(EntityResolutionError):
        EntityResolutionPipeline._validate(col_single, "COMPARISON")

    # GENERALIZED with 2 entities should pass
    EntityResolutionPipeline._validate(col_multi, "GENERALIZED") # Should not raise

@patch("src.services.entity_resolver.EntityResolver._search_yahoo_finance_sync")
def test_yahoo_discovery_sync(mock_yahoo_search):
    mock_yahoo_search.return_value = {
        "symbol": "TSLA",
        "company_name": "Tesla, Inc.",
        "industry": "Auto Manufacturers",
        "sector": "Consumer Cyclical"
    }
    
    # Clear cache
    EntityResolutionPipeline._yahoo_lru_cache.clear()
    
    entity = EntityResolutionPipeline._discover_via_yahoo_sync("tesla")
    assert entity is not None
    assert entity.ticker == "TSLA"
    assert entity.resolution_source == "YAHOO_FINANCE"
    assert entity.exchange == "NASDAQ"
    assert entity.country == "US"
    
    # Verify cached call
    mock_yahoo_search.reset_mock()
    entity_cached = EntityResolutionPipeline._discover_via_yahoo_sync("tesla")
    assert entity_cached == entity
    mock_yahoo_search.assert_not_called()

@pytest.mark.asyncio
@patch("src.services.entity_resolver.EntityResolver._search_yahoo_finance_async")
@patch("src.services.entity_resolver.EntityResolver._persist_new_company")
async def test_resolve_entities_async(mock_persist, mock_yahoo_search):
    async def initialize_without_db(*args, **kwargs):
        EntityResolver.initialize_sync()

    mock_yahoo_search.return_value = {
        "symbol": "AAPL",
        "company_name": "Apple Inc.",
        "industry": "Consumer Electronics",
        "sector": "Technology"
    }
    
    EntityResolutionPipeline._yahoo_lru_cache.clear()
    
    # Async resolution of an unknown title-case company should use Yahoo discovery.
    with patch.object(EntityResolver, "initialize_async", new=AsyncMock(side_effect=initialize_without_db)):
        col = await EntityResolutionPipeline.resolve_entities("Analyze Example Robotics")
    assert col.total_found == 1
    assert col.primary_ticker == "AAPL"
    assert col.primary.resolution_source == "YAHOO_FINANCE"
    mock_yahoo_search.assert_called_once()
    mock_persist.assert_called_once()
