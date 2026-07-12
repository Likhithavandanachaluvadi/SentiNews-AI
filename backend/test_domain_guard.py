import sys
import os

# Adjust path to import backend modules correctly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.domain_guard import FinancialDomainGuard

def run_tests():
    print("================================================")
    print("Running Financial Domain Guard Production Tests")
    print("================================================\n")
    
    pass_queries = [
        "Explain PE Ratio",
        "Why did Reliance fall?",
        "Explain inflation and its impact on stocks.",
        "Compare TCS and Infosys.",
        "Explain ETFs."
    ]
    
    fail_queries = [
        "Write a Python program.",
        "Explain Operating Systems.",
        "Tell me a joke.",
        "Translate this paragraph.",
        "Who won yesterday's IPL match?",
        "What is the capital of Japan?"
    ]
    
    failures = 0
    
    print("--- 1. TESTING ALLOWED QUERIES (PASS) ---")
    for q in pass_queries:
        result = FinancialDomainGuard.validate(q)
        status = "PASS (OK)" if result.allowed else "FAIL (ERROR)"
        print(f"Query: '{q}'\nStatus: {status} | Stage: {result.matched_stage} | Confidence: {result.confidence:.2f}\n")
        if not result.allowed:
            failures += 1
            
    print("--- 2. TESTING REJECTED QUERIES (FAIL) ---")
    for q in fail_queries:
        result = FinancialDomainGuard.validate(q)
        status = "FAIL (OK)" if not result.allowed else "PASS (ERROR)"
        print(f"Query: '{q}'\nStatus: {status} | Stage: {result.matched_stage} | Confidence: {result.confidence:.2f}\n")
        if result.allowed:
            failures += 1
            
    print("================================================")
    print(f"Test Summary: {failures} Failures Detected.")
    print("================================================")
    
    if failures == 0:
        print("ALL TESTS PASSED SUCCESSFULLY!")
        sys.exit(0)
    else:
        print("SOME TESTS FAILED.")
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
