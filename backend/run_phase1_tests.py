import sys
import os
import asyncio

# Adjust path to import backend modules correctly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Define custom context manager for pytest.raises behavior
class raises:
    def __init__(self, expected_exception):
        self.expected_exception = expected_exception
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            raise AssertionError(f"Expected exception {self.expected_exception} was not raised")
        if issubclass(exc_type, self.expected_exception):
            return True
        return False

# Mock pytest module so test files don't fail on "import pytest"
class MockPytest:
    def raises(self, expected_exception):
        return raises(expected_exception)
    class fixture:
        def __init__(self, *args, **kwargs):
            pass
        def __call__(self, func):
            return func
    class mark:
        @staticmethod
        def asyncio(func):
            return func

sys.modules["pytest"] = MockPytest()

# Import the test files
import tests.unit.test_entity_models as test_models
import tests.unit.test_entity_resolution_pipeline as test_pipeline
import tests.unit.test_entity_resolver_shim as test_shim

def run_sync_test(test_name, test_func):
    try:
        # If it has fixture setup, we run it manually
        if hasattr(test_pipeline, "setup_caches"):
            test_pipeline.setup_caches()
        if hasattr(test_shim, "setup_caches"):
            test_shim.setup_caches()
            
        test_func()
        print(f"PASS: {test_name}")
        return True
    except Exception as e:
        import traceback
        print(f"FAIL: {test_name}")
        traceback.print_exc()
        return False

async def run_async_test(test_name, test_func):
    try:
        if hasattr(test_pipeline, "setup_caches"):
            test_pipeline.setup_caches()
        if hasattr(test_shim, "setup_caches"):
            test_shim.setup_caches()
            
        # Run the async test
        if asyncio.iscoroutinefunction(test_func):
            await test_func()
        else:
            res = test_func()
            if asyncio.iscoroutine(res):
                await res
        print(f"PASS: {test_name}")
        return True
    except Exception as e:
        import traceback
        print(f"FAIL: {test_name}")
        traceback.print_exc()
        return False

def main():
    print("================================================")
    print("Running Sprint 3.1 Phase 1 Unit Tests")
    print("================================================\n")
    
    passed = 0
    failed = 0
    
    # 1. Models tests
    print("--- 1. Testing Entity Models ---")
    model_tests = [
        ("test_resolved_entity_instantiation", test_models.test_resolved_entity_instantiation),
        ("test_entity_collection_properties", test_models.test_entity_collection_properties),
        ("test_to_from_dict", test_models.test_to_from_dict),
        ("test_get_entity", test_models.test_get_entity),
    ]
    for name, func in model_tests:
        if run_sync_test(name, func):
            passed += 1
        else:
            failed += 1
            
    # 2. Pipeline tests
    print("\n--- 2. Testing Entity Resolution Pipeline ---")
    pipeline_tests_sync = [
        ("test_extract_candidates", test_pipeline.test_extract_candidates),
        ("test_match_candidate_exact_ticker", test_pipeline.test_match_candidate_exact_ticker),
        ("test_match_candidate_legacy_alias", test_pipeline.test_match_candidate_legacy_alias),
        ("test_match_candidate_exact_name", test_pipeline.test_match_candidate_exact_name),
        ("test_match_candidate_whole_word", test_pipeline.test_match_candidate_whole_word),
        ("test_fuzzy_match", test_pipeline.test_fuzzy_match),
        ("test_rank_and_deduplicate", test_pipeline.test_rank_and_deduplicate),
        ("test_validation_gate", test_pipeline.test_validation_gate),
        ("test_yahoo_discovery_sync", test_pipeline.test_yahoo_discovery_sync),
    ]
    for name, func in pipeline_tests_sync:
        if run_sync_test(name, func):
            passed += 1
        else:
            failed += 1
            
    # Async pipeline tests
    loop = asyncio.get_event_loop()
    
    # Setup test_resolve_entities_async
    try:
        if loop.run_until_complete(run_async_test("test_resolve_entities_async", test_pipeline.test_resolve_entities_async)):
            passed += 1
        else:
            failed += 1
    except Exception as e:
        import traceback
        print("FAIL: test_resolve_entities_async")
        traceback.print_exc()
        failed += 1
        
    # 3. Shim tests
    print("\n--- 3. Testing Entity Resolver Shim ---")
    shim_tests_sync = [
        ("test_resolver_sync_success", test_shim.test_resolver_sync_success),
        ("test_resolver_sync_multiple", test_shim.test_resolver_sync_multiple),
        ("test_resolver_sync_no_match", test_shim.test_resolver_sync_no_match),
        ("test_resolver_sync_raise_on_fail", test_shim.test_resolver_sync_raise_on_fail),
    ]
    for name, func in shim_tests_sync:
        if run_sync_test(name, func):
            passed += 1
        else:
            failed += 1
            
    # Async shim tests
    try:
        if loop.run_until_complete(run_async_test("test_resolver_async_success", test_shim.test_resolver_async_success)):
            passed += 1
        else:
            failed += 1
            
        if loop.run_until_complete(run_async_test("test_resolver_async_no_match", test_shim.test_resolver_async_no_match)):
            passed += 1
        else:
            failed += 1
    except Exception as e:
        import traceback
        print("FAIL: test_resolver_async")
        traceback.print_exc()
        failed += 1

    print("\n================================================")
    print(f"Test Summary: Passed: {passed} | Failed: {failed}")
    print("================================================")
    
    if failed == 0:
        print("ALL PHASE 1 TESTS PASSED SUCCESSFULLY!")
        sys.exit(0)
    else:
        print("SOME TESTS FAILED.")
        sys.exit(1)

if __name__ == "__main__":
    main()
