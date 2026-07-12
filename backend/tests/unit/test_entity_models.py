import pytest
from src.services.entity_models import ResolvedEntity, EntityCollection

def test_resolved_entity_instantiation():
    entity = ResolvedEntity(
        ticker="TCS",
        company_name="Tata Consultancy Services Limited",
        exchange="NSE",
        country="IN",
        confidence=1.0,
        resolution_source="EXACT_TICKER",
        aliases=["tcs", "tata consultancy"],
        is_primary=True,
        query_span="TCS"
    )
    assert entity.ticker == "TCS"
    assert entity.company_name == "Tata Consultancy Services Limited"
    assert entity.exchange == "NSE"
    assert entity.country == "IN"
    assert entity.confidence == 1.0
    assert entity.resolution_source == "EXACT_TICKER"
    assert entity.aliases == ["tcs", "tata consultancy"]
    assert entity.is_primary is True
    assert entity.query_span == "TCS"

def test_entity_collection_properties():
    e1 = ResolvedEntity(
        ticker="INFY",
        company_name="Infosys Limited",
        confidence=0.97,
        resolution_source="EXACT_NAME"
    )
    e2 = ResolvedEntity(
        ticker="TCS",
        company_name="Tata Consultancy Services Limited",
        confidence=0.95,
        resolution_source="EXACT_NAME"
    )
    
    # Test empty collection
    empty_col = EntityCollection(entities=[], query="Explain PE ratio", resolution_mode="EDUCATIONAL", total_found=0)
    assert empty_col.primary is None
    assert empty_col.primary_ticker is None
    assert empty_col.all_tickers == []
    assert empty_col.is_empty is True
    assert empty_col.is_single is False
    assert empty_col.is_multi is False
    
    # Test single collection
    single_col = EntityCollection(entities=[e1], query="Analyze Infosys", resolution_mode="SINGLE", total_found=1)
    assert single_col.primary == e1
    assert single_col.primary_ticker == "INFY"
    assert single_col.all_tickers == ["INFY"]
    assert single_col.is_empty is False
    assert single_col.is_single is True
    assert single_col.is_multi is False
    
    # Test multi collection
    multi_col = EntityCollection(entities=[e1, e2], query="Compare Infosys and TCS", resolution_mode="MULTI", total_found=2)
    assert multi_col.primary == e1
    assert multi_col.primary_ticker == "INFY"
    assert multi_col.all_tickers == ["INFY", "TCS"]
    assert multi_col.is_empty is False
    assert multi_col.is_single is False
    assert multi_col.is_multi is True

def test_to_from_dict():
    e1 = ResolvedEntity(
        ticker="INFY",
        company_name="Infosys Limited",
        confidence=0.97,
        resolution_source="EXACT_NAME"
    )
    col = EntityCollection(entities=[e1], query="Analyze Infosys", resolution_mode="SINGLE", total_found=1)
    
    data = col.to_dict()
    assert isinstance(data, dict)
    assert data["query"] == "Analyze Infosys"
    assert data["entities"][0]["ticker"] == "INFY"
    
    col_recovered = EntityCollection.from_dict(data)
    assert col_recovered.query == col.query
    assert len(col_recovered.entities) == 1
    assert col_recovered.entities[0].ticker == "INFY"
    
    # Test from_dict with None
    col_none = EntityCollection.from_dict(None)
    assert col_none.is_empty is True
    assert col_none.resolution_mode == "EDUCATIONAL"

def test_get_entity():
    e1 = ResolvedEntity(
        ticker="INFY",
        company_name="Infosys Limited",
        confidence=0.97,
        resolution_source="EXACT_NAME"
    )
    e2 = ResolvedEntity(
        ticker="TCS",
        company_name="Tata Consultancy Services Limited",
        confidence=0.95,
        resolution_source="EXACT_NAME"
    )
    col = EntityCollection(entities=[e1, e2], query="Compare Infosys and TCS", resolution_mode="MULTI", total_found=2)
    
    found = col.get_entity("INFY")
    assert found == e1
    
    found_case = col.get_entity("infy ")
    assert found_case == e1
    
    not_found = col.get_entity("RELIANCE")
    assert not_found is None
