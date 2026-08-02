import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from src.services.entity_resolution_pipeline import EntityResolutionPipeline
from src.services.entity_resolver import EntityResolver

def test_pipeline():
    EntityResolver.initialize_sync()

    test_cases = [
        # Problem cases from user request
        ("Analyze", 0, None, "action"),
        ("Rank", 0, None, "action"),
        ("Identify", 0, None, "action"),
        ("The Indian", 0, None, "country"),
        ("12", 0, None, "number"),
        ("supporting evidence", 0, None, "generic_phrase"),
        
        # Phase 5 Test Cases
        ("Compare TCS and Infosys", 2, ["TCS", "INFY"], "comparison"),
        ("Rank AI companies", 0, [], "theme/action"),
        ("The Indian government is increasing investment in renewable energy.", 0, [], "country/theme"),
        ("Impact over next 12 months", 0, [], "time_period"),
    ]

    print("==================================================")
    print("VERIFYING ENTITY RESOLUTION PIPELINE")
    print("==================================================")

    all_passed = True
    for query, expected_count, expected_tickers, description in test_cases:
        candidates = EntityResolutionPipeline._extract_candidates(query)
        classified = [(c, EntityResolutionPipeline._classify_candidate(c, query)) for c in candidates]
        collection = EntityResolutionPipeline.resolve_entities_sync(query)

        resolved_tickers = [e.ticker for e in collection.entities]
        
        print(f"\nQuery: '{query}' ({description})")
        print(f"  Candidates Extracted: {candidates}")
        print(f"  Classifications: {classified}")
        print(f"  Resolved Companies: {resolved_tickers} (Total: {collection.total_found})")

        if collection.total_found != expected_count:
            print(f"  [FAILED]: Expected {expected_count} entities, got {collection.total_found}")
            all_passed = False
        elif expected_tickers is not None and sorted(resolved_tickers) != sorted(expected_tickers):
            print(f"  [FAILED]: Expected tickers {expected_tickers}, got {resolved_tickers}")
            all_passed = False
        else:
            print(f"  [PASSED]")

    print("\n==================================================")
    if all_passed:
        print("ALL ENTITY RESOLUTION VERIFICATION TESTS PASSED!")
    else:
        print("SOME TESTS FAILED!")
    print("==================================================")

if __name__ == "__main__":
    test_pipeline()
