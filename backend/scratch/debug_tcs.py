import asyncio
import os
import sys

# Ensure src is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.services.entity_resolver import EntityResolver
from src.services.entity_resolution_pipeline import EntityResolutionPipeline

async def main():
    print("Initializing...")
    await EntityResolver.initialize_async()
    
    print("\nLocal cache stats:")
    print("Ticker to Company keys count:", len(EntityResolver._ticker_to_company))
    print("Company to Ticker keys count:", len(EntityResolver._company_to_ticker))
    
    print("\nIs 'TCS' in ticker_to_company?", "TCS" in EntityResolver._ticker_to_company)
    print("Is 'TCS.NS' in ticker_to_company?", "TCS.NS" in EntityResolver._ticker_to_company)
    
    query = "I'm new to investing. Should I buy Reliance Industries now?"
    print(f"\nResolving query: '{query}'")
    
    # Run the n-gram matching phase manually to print candidate matches
    # Run the n-gram matching phase manually to print candidate matches
    raw_words = query.strip().split()
    words = []
    import re
    for w in raw_words:
        cleaned_w = w.strip(" ?.,!():;\"'")
        cleaned_w = re.sub(r"'[sS]$", "", cleaned_w)
        cleaned_w = cleaned_w.rstrip("'")
        if cleaned_w:
            words.append(cleaned_w)
    print("Words list:", words)
    
    candidate_matches = []
    num_words = len(words)
    generic_words = {
        "bank", "industries", "limited", "corp", "corporation", "ltd", "inc", "company",
        "services", "motors", "holding", "holdings", "group", "india", "state", "national",
        "mutual", "fund", "funds", "general", "steel", "power", "chemicals", "pharma"
    }
    for n in range(min(5, num_words), 0, -1):
        for start in range(num_words - n + 1):
            end = start + n - 1
            candidate_span = " ".join(words[start:end+1])
            entity = EntityResolutionPipeline._match_candidate(candidate_span)
            if not entity:
                entity = EntityResolutionPipeline._fuzzy_match(candidate_span)
            if entity:
                print(f"Matched candidate '{candidate_span}' -> ticker {entity.ticker}")
                candidate_matches.append(entity)
                
    collection = await EntityResolutionPipeline.resolve_entities(query)
    print("\nResolved collection:")
    print("Entities found:", [e.model_dump() for e in collection.entities])

if __name__ == "__main__":
    asyncio.run(main())
