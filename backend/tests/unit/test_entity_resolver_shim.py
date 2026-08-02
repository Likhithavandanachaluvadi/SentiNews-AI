import pytest
from unittest.mock import AsyncMock, patch
from src.services.entity_resolver import EntityResolver, EntityResolutionError

@pytest.fixture(autouse=True)
def setup_caches():
    EntityResolver.initialize_sync()

def test_resolver_sync_success():
    ticker, name = EntityResolver.resolve_sync("Analyze TCS")
    assert ticker == "TCS"
    assert name.lower().startswith("tata consultancy services")

def test_resolver_sync_multiple():
    ticker, name = EntityResolver.resolve_sync("Compare Infosys and TCS")
    assert ticker in ["INFY", "TCS"]
    assert name.lower() in ["infosys limited", "infosys", "tata consultancy services limited", "tata consultancy services", "tata consultancy services ltd."]

def test_resolver_sync_no_match():
    ticker, name = EntityResolver.resolve_sync("What is PE ratio")
    assert ticker is None
    assert name is None

def test_resolver_sync_raise_on_fail():
    with pytest.raises(EntityResolutionError):
        EntityResolver.resolve_sync("Analyze somefakecompany", raise_on_fail=True)
        
    # Should not raise if no stock keywords are present
    ticker, name = EntityResolver.resolve_sync("What is inflation?", raise_on_fail=True)
    assert ticker is None
    assert name is None

@pytest.mark.asyncio
async def test_resolver_async_success():
    async def initialize_without_db(*args, **kwargs):
        EntityResolver.initialize_sync()

    with patch.object(EntityResolver, "initialize_async", new=AsyncMock(side_effect=initialize_without_db)):
        ticker, name = await EntityResolver.resolve("Analyze TCS")
    assert ticker == "TCS"
    assert name.lower().startswith("tata consultancy services")

@pytest.mark.asyncio
async def test_resolver_async_no_match():
    async def initialize_without_db(*args, **kwargs):
        EntityResolver.initialize_sync()

    with patch.object(EntityResolver, "initialize_async", new=AsyncMock(side_effect=initialize_without_db)):
        ticker, name = await EntityResolver.resolve("What is PE ratio")
    assert ticker is None
    assert name is None
