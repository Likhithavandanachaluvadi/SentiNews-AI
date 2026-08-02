import asyncio
import os
import sys
import re

# Ensure backend root is in Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.services.entity_resolver import EntityResolver
from src.services.entity_resolution_pipeline import EntityResolutionPipeline

# Test cases mapping queries to expected results
TEST_CASES = [
    {
        "query": "Latest news about HDFC Bank",
        "expected_tickers": ["HDFCBANK"],
        "check_classifications": [("HDFC Bank", "company")]
    },
    {
        "query": "Analyze Reliance Industries",
        "expected_tickers": ["RELIANCE"],
        "check_classifications": [("Reliance Industries", "company")]
    },
    {
        "query": "What is the valuation of ICICI Bank?",
        "expected_tickers": ["ICICIBANK"],
        "check_classifications": [("ICICI Bank", "company")]
    },
    {
        "query": "Explain Infosys's recent performance",
        "expected_tickers": ["INFY"],
        "check_classifications": [("Infosys", "company")]
    },
    {
        "query": "Compare TCS and Infosys",
        "expected_tickers": ["TCS", "INFY"],
        "check_classifications": [("TCS", "ticker"), ("Infosys", "company")]
    },
    {
        "query": "Should I buy State Bank of India?",
        "expected_tickers": ["SBIN"],
        "check_classifications": [("State Bank of India", "company")]
    },
    {
        "query": "Review Larsen & Toubro",
        "expected_tickers": ["LT"],
        "check_classifications": [("Larsen & Toubro", "company")]
    },
    {
        "query": "How is Mahindra & Mahindra doing?",
        "expected_tickers": ["M&M"],
        "check_classifications": [("Mahindra & Mahindra", "company")]
    },
    {
        "query": "Analyze Tata Motors",
        "expected_tickers": ["TMCV"],
        "check_classifications": [("Tata Motors", "company")]
    },
    {
        "query": "Latest news on Sun Pharma",
        "expected_tickers": ["SUNPHARMA-BL"],
        "check_classifications": [("Sun Pharma", "company")]
    },
    {
        "query": "Show me AI theme stocks",
        "expected_tickers": [],
        "check_classifications": [("AI", "technology_concept"), ("stocks", "industry_theme")]
    },
    {
        "query": "What are the top semiconductor companies?",
        "expected_tickers": [],
        "check_classifications": [("companies", "industry_theme")]
    },
    {
        "query": "I'm new to investing. Should I buy Reliance Industries now?",
        "expected_tickers": ["RELIANCE"],
        "check_classifications": [("Reliance Industries", "company")]
    }
]

async def run_tests():
    print("==================================================")
    print("RUNNING SPRINT 2.3 REGRESSION TESTS")
    print("==================================================")
    
    # Initialize the resolver
    await EntityResolver.initialize_async()
    
    failed = 0
    passed = 0
    
    for i, tc in enumerate(TEST_CASES, start=1):
        query = tc["query"]
        expected_tickers = tc["expected_tickers"]
        print(f"\n[Test Case {i}] Query: '{query}'")
        
        # Test 1: Classifications
        classification_failed = False
        for phrase, expected_type in tc["check_classifications"]:
            actual_type = EntityResolutionPipeline._classify_candidate(phrase, query)
            if actual_type != expected_type:
                print(f"  [FAIL] Classification Mismatch for '{phrase}': Expected '{expected_type}', got '{actual_type}'")
                classification_failed = True
            else:
                print(f"  [OK] Classification Match for '{phrase}': '{actual_type}'")
        
        # Test 2: Entity Resolution
        try:
            collection = await EntityResolutionPipeline.resolve_entities(query)
            resolved_tickers = [e.ticker.upper().strip() for e in collection.entities]
            
            # Remove duplicate/empty symbols for comparison
            resolved_tickers = sorted(list(set(resolved_tickers)))
            
            def matches_expected(resolved, expected):
                expected_sorted = sorted([t.upper().strip() for t in expected])
                if resolved == expected_sorted:
                    return True
                alt_map = {
                    "TMCV": "TATAMOTORS",
                    "TATAMOTORS": "TMCV",
                    "SUNPHARMA": "SUNPHARMA-BL",
                    "SUNPHARMA-BL": "SUNPHARMA"
                }
                alt_expected = sorted([alt_map.get(t.upper().strip(), t.upper().strip()) for t in expected])
                return resolved == alt_expected

            if not matches_expected(resolved_tickers, expected_tickers):
                print(f"  [FAIL] Resolution Mismatch: Expected {expected_tickers}, got {resolved_tickers}")
                classification_failed = True
            else:
                print(f"  [OK] Resolution Match: Got {resolved_tickers}")
                
            # Test 3: Multiple Companies validation
            try:
                from src.core.middleware import validate_query_multiple_companies, validate_query
                await validate_query(query, check_multiple_companies=False)
                intent = "COMPARISON" if "compare" in query.lower() or " vs " in query.lower() else "STOCK_ANALYSIS"
                validate_query_multiple_companies(query, intent, collection.model_dump())
                print("  [OK] Multiple Companies Validation check passed")
            except Exception as ex:
                print(f"  [FAIL] Multiple Companies Validation failed: {ex}")
                classification_failed = True
        except Exception as e:
            print(f"  [FAIL] Resolution raised an exception: {e}")
            classification_failed = True
            
        # Test 4: News formatting check
        if tc["query"] == "Latest news about HDFC Bank":
            news_query = "Why is HDFC Bank in the news today?"
            print(f"\n[Test News Formatting] Query: '{news_query}'")
            try:
                from fastapi.testclient import TestClient
                from src.main import app
                client = TestClient(app)
                # Sleep to avoid Groq rate limit
                await asyncio.sleep(5.0)
                response = client.post("/api/v1/research/analyze", json={"query": news_query})
                if response.status_code in (200, 202):
                    res_data = response.json()
                    summary = res_data.get("summary", "")
                    print("Generated News Summary:")
                    print("-" * 40)
                    try:
                        print(summary)
                    except UnicodeEncodeError:
                        print(summary.encode('ascii', errors='replace').decode('ascii'))
                    print("-" * 40)
                    
                    # 1. NEWS_ANALYSIS classification
                    actual_intent = res_data.get("intent", {}).get("primary_intent", "")
                    if actual_intent == "NEWS_ANALYSIS":
                        print("  [OK] Intent classified as NEWS_ANALYSIS")
                    else:
                        print(f"  [FAIL] Intent classification Mismatch: expected 'NEWS_ANALYSIS', got '{actual_intent}'")
                        classification_failed = True
                        
                    # 2. Correct company resolution
                    actual_ticker = res_data.get("meta", {}).get("ticker", "")
                    if actual_ticker == "HDFCBANK":
                        print("  [OK] Company resolved correctly to HDFCBANK")
                    else:
                        print(f"  [FAIL] Company resolution Mismatch: expected 'HDFCBANK', got '{actual_ticker}'")
                        classification_failed = True
                        
                    # 3. Seven required markdown sections & 4. Correct heading order
                    required_headings = [
                        "# Executive Summary",
                        "# Why is the Company in the News?",
                        "# Key Developments",
                        "# Market Impact",
                        "# Overall Sentiment",
                        "# Key Risks",
                        "# Key Takeaway"
                    ]
                    
                    indices = [summary.find(h) for h in required_headings]
                    order_ok = True
                    for j in range(len(indices)):
                        if indices[j] == -1:
                            print(f"  [FAIL] News heading missing: '{required_headings[j]}'")
                            classification_failed = True
                            order_ok = False
                        elif j > 0 and indices[j] < indices[j-1]:
                            print(f"  [FAIL] Incorrect heading order: '{required_headings[j]}' appears before '{required_headings[j-1]}'")
                            classification_failed = True
                            order_ok = False
                    
                    if order_ok:
                        print("  [OK] All 7 headings present in correct order")

                    # 5. First paragraph answers the user's question
                    exec_summary_index = summary.find("# Executive Summary")
                    why_index = summary.find("# Why is the Company in the News?")
                    if exec_summary_index != -1 and why_index != -1:
                        exec_summary_text = summary[exec_summary_index + len("# Executive Summary"):why_index].strip()
                        exec_summary_lines = [l.strip() for l in exec_summary_text.splitlines() if l.strip()]
                        if exec_summary_lines and not exec_summary_lines[0].startswith("#"):
                            first_p = exec_summary_lines[0]
                            # Check that it answers the question directly and doesn't start with boilerplate introduction of the company or generic market sentiment
                            banned_intro_words = ["hdfc bank is", "hdfc bank (", "established in", "leading private sector"]
                            starts_with_banned = any(first_p.lower().startswith(word) for word in banned_intro_words)
                            if not starts_with_banned:
                                print(f"  [OK] First paragraph directly answers query: '{first_p[:100]}...'")
                            else:
                                print(f"  [FAIL] First paragraph contains generic company introduction: '{first_p}'")
                                classification_failed = True
                        else:
                            print("  [FAIL] No direct answer text found in the first paragraph under # Executive Summary")
                            classification_failed = True
                    else:
                        print("  [FAIL] Executive Summary or Catalyst headings missing, cannot verify first paragraph answer")
                        classification_failed = True

                    # 6. Section uniqueness, paragraph and sentence deduplication
                    sections = {}
                    current_heading = None
                    current_lines = []
                    for line in summary.splitlines():
                        line_stripped = line.strip()
                        if line_stripped.startswith("#"):
                            if current_heading:
                                sections[current_heading] = "\n".join(current_lines).strip()
                            current_heading = line_stripped
                            current_lines = []
                        elif current_heading:
                            current_lines.append(line)
                    if current_heading:
                        sections[current_heading] = "\n".join(current_lines).strip()

                    # Check that headings appear exactly once
                    unique_headings_count = sum(summary.count(h) for h in required_headings)
                    if unique_headings_count == len(required_headings):
                        print("  [OK] Headings appear exactly once (no duplication)")
                    else:
                        print(f"  [FAIL] Duplicate headings detected: expected {len(required_headings)}, got {unique_headings_count}")
                        classification_failed = True

                    # Verify no repeated paragraphs across sections
                    all_paragraphs = []
                    has_dup_p = False
                    for sec_h, sec_c in sections.items():
                        paragraphs = [p.strip() for p in sec_c.split("\n\n") if len(p.strip()) > 10]
                        for p in paragraphs:
                            p_clean = p.lstrip("* -•\t").strip()
                            if p_clean in all_paragraphs:
                                print(f"  [FAIL] Repeated paragraph found across sections: '{p_clean[:50]}...'")
                                classification_failed = True
                                has_dup_p = True
                            all_paragraphs.append(p_clean)
                    if not has_dup_p:
                        print("  [OK] Unique paragraphs per section (no repeated paragraphs)")

                    # Verify no duplicated sentences
                    sentences = [s.strip() for s in re.split(r'\. |\n', "\n".join(sections.values())) if len(s.strip()) > 15]
                    sentences_clean = [s.lstrip("* -•\t").strip() for s in sentences]
                    duplicates_s = set([s for s in sentences_clean if sentences_clean.count(s) > 1])
                    if not duplicates_s:
                        print("  [OK] No sentence duplicated in the entire report")
                    else:
                        print(f"  [FAIL] Duplicate sentences detected: {list(duplicates_s)}")
                        classification_failed = True

                    # Verify Executive Summary is not repeated later
                    exec_sum_content = sections.get("# Executive Summary", "")
                    exec_sentences = [s.strip() for s in re.split(r'\. |\n', exec_sum_content) if len(s.strip()) > 15]
                    exec_sentences_clean = [s.lstrip("* -•\t").strip() for s in exec_sentences]
                    repeated_exec = False
                    for sec_h, sec_c in sections.items():
                        if sec_h == "# Executive Summary":
                            continue
                        sec_sentences = [s.strip() for s in re.split(r'\. |\n', sec_c) if len(s.strip()) > 15]
                        sec_sentences_clean = [s.lstrip("* -•\t").strip() for s in sec_sentences]
                        for s in exec_sentences_clean:
                            if s in sec_sentences_clean:
                                print(f"  [FAIL] Executive Summary sentence repeated in '{sec_h}': '{s}'")
                                classification_failed = True
                                repeated_exec = True
                    if not repeated_exec:
                        print("  [OK] Executive Summary is not repeated later in the report")

                    # 7. Absence of generic boilerplate & banned generic phrases
                    banned_phrases = [
                        "based on the provided context", "according to the data", "as an ai", 
                        "to summarize", "refer to the dashboard", "the following analysis", 
                        "placeholder", "lorem ipsum", "market activity", "recent developments", 
                        "price fluctuations", "investor sentiment", "current market conditions"
                    ]
                    found_banned = [p for p in banned_phrases if p in summary.lower()]
                    if not found_banned:
                        print("  [OK] Grounding check passed: no placeholder, boilerplate, or banned generic phrases found")
                    else:
                        print(f"  [FAIL] Generic boilerplate or banned phrase detected: {found_banned}")
                        classification_failed = True

                    # Check preference for concrete evidence-backed facts over abstract summaries
                    all_text_no_headings = "\n".join(sections.values())
                    has_numbers = bool(re.search(r'\d+', all_text_no_headings))
                    if has_numbers:
                        print("  [OK] Fact-grounding check passed (numerical or date facts present)")
                    else:
                        print("  [FAIL] Concrete facts preference violation: response contains only abstract summaries without numbers, dates, or percentages")
                        classification_failed = True

                    # 8. Markdown formatting preserved
                    if summary.strip().startswith("# Executive Summary") and not summary.startswith('"') and not summary.startswith("'"):
                        print("  [OK] Markdown formatting preserved (starts with heading, not quoted)")
                    else:
                        print("  [FAIL] Markdown formatting not preserved or response is wrapped in quotes")
                        classification_failed = True
                else:
                    print(f"  [FAIL] News query failed with status code {response.status_code}: {response.text}")
                    classification_failed = True
            except Exception as e:
                print(f"  [FAIL] News query raised exception: {e}")
                classification_failed = True

        if classification_failed:
            failed += 1
        else:
            passed += 1
            
    print("\n==================================================")
    print(f"TEST RESULTS: PASSED = {passed}, FAILED = {failed}")
    print("==================================================")
    
    if failed > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(run_tests())
