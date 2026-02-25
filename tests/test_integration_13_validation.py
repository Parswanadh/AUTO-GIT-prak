"""
Quick validation test for Integration #13 - Tests core functionality without external API dependencies.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.llm.consensus_selector import ConsensusSelector
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def test_consensus_selector():
    """Test consensus selector with mock responses."""
    logger.info("\n" + "="*80)
    logger.info("TEST: ConsensusSelector Core Functionality")
    logger.info("="*80)
    
    # Mock responses from different models
    responses = [
        {
            'content': '''def binary_search(arr, target):
    """Search for target in sorted array."""
    left, right = 0, len(arr) - 1
    while left <= right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return -1''',
            'model': 'model1',
            'backend': 'test',
            'latency': 1.0,
            'tokens': 100
        },
        {
            'content': '''def binary_search(arr, target):
    """
    Binary search implementation.
    
    Args:
        arr: Sorted array to search
        target: Value to find
        
    Returns:
        Index of target or -1 if not found
        
    Example:
        >>> binary_search([1, 2, 3, 4, 5], 3)
        2
        
    Time Complexity: O(log n)
    Space Complexity: O(1)
    """
    left, right = 0, len(arr) - 1
    
    while left <= right:
        mid = left + (right - left) // 2  # Avoid overflow
        
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
            
    return -1

# Example usage
if __name__ == "__main__":
    arr = [1, 3, 5, 7, 9, 11]
    result = binary_search(arr, 7)
    print(f"Found at index: {result}")''',
            'model': 'model2',
            'backend': 'test',
            'latency': 1.5,
            'tokens': 200
        },
        {
            'content': 'def bs(a,t):\n  l=0;r=len(a)-1\n  while l<=r:\n    m=(l+r)//2\n    if a[m]==t:return m\n    if a[m]<t:l=m+1\n    else:r=m-1\n  return -1',
            'model': 'model3',
            'backend': 'test',
            'latency': 0.8,
            'tokens': 50
        }
    ]
    
    # Test quality_score strategy
    selector = ConsensusSelector(strategy="quality_score")
    best_content, metadata = selector.select_best(responses, task_type="code_generation")
    
    logger.info(f"\n{'='*80}")
    logger.info(f"Results:")
    logger.info(f"{'='*80}")
    logger.info(f"Best Model: {metadata['best_model']}")
    logger.info(f"Best Score: {metadata['best_score']:.3f}")
    
    if 'quality_scores' in metadata:
        logger.info(f"\nAll Quality Scores:")
        for model, score in metadata['quality_scores'].items():
            logger.info(f"  {model}: {score:.3f}")
    
    if 'scores_breakdown' in metadata:
        logger.info(f"\nQuality Breakdown (Winner):")
        for criterion, score in metadata['scores_breakdown'].items():
            logger.info(f"  {criterion}: {score:.3f}")
    
    # Assertions
    assert metadata['best_model'] == 'model2', "Model2 should win (most complete)"
    assert metadata['best_score'] > 0.7, f"Best score should be >0.7, got {metadata['best_score']:.3f}"
    assert 'scores_breakdown' in metadata, "Should have scores breakdown"
    
    logger.info("\n✅ ConsensusSelector test PASSED\n")
    return True


async def test_hybrid_router_structure():
    """Test that HybridRouter has the new methods."""
    logger.info("\n" + "="*80)
    logger.info("TEST: HybridRouter Method Availability")
    logger.info("="*80)
    
    from src.llm.hybrid_router import HybridRouter
    from src.llm.multi_backend_manager import MultiBackendLLMManager
    
    backend_manager = MultiBackendLLMManager()
    router = HybridRouter(backend_manager)
    
    # Check methods exist
    methods = [
        'parallel_generate',
        'parallel_multi_model_generate',
        'parallel_generate_with_consensus',
        '_generate_single_model'
    ]
    
    logger.info(f"\nChecking for required methods:")
    for method in methods:
        has_method = hasattr(router, method)
        status = "✅" if has_method else "❌"
        logger.info(f"  {status} {method}: {has_method}")
        assert has_method, f"Missing method: {method}"
    
    logger.info("\n✅ HybridRouter structure test PASSED\n")
    return True


async def main():
    """Run all validation tests."""
    logger.info("\n" + "="*80)
    logger.info("INTEGRATION #13 VALIDATION TESTS")
    logger.info("(No external API calls - testing core functionality only)")
    logger.info("="*80 + "\n")
    
    tests = [
        ("ConsensusSelector", test_consensus_selector),
        ("HybridRouter Structure", test_hybrid_router_structure),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                success = await test_func()
            else:
                success = test_func()
            results[test_name] = "✅ PASSED" if success else "❌ FAILED"
        except Exception as e:
            logger.error(f"❌ Test failed: {test_name}")
            logger.error(f"Error: {e}", exc_info=True)
            results[test_name] = f"❌ FAILED: {str(e)}"
    
    # Summary
    logger.info("\n" + "="*80)
    logger.info("VALIDATION SUMMARY")
    logger.info("="*80)
    
    for test_name, result in results.items():
        logger.info(f"{result} - {test_name}")
    
    passed = sum(1 for r in results.values() if "✅" in r)
    total = len(results)
    
    logger.info(f"\n{passed}/{total} tests passed ({passed/total*100:.0f}%)")
    
    if passed == total:
        logger.info("\n🎉 ALL VALIDATION TESTS PASSED!")
        logger.info("Core functionality is working correctly.\n")
        logger.info("Note: End-to-end tests may fail due to:")
        logger.info("  - OpenRouter free model availability (404 errors)")
        logger.info("  - Rate limiting (429 errors)")
        logger.info("  - These are external issues, not code bugs.\n")
    else:
        logger.error("\n⚠️ Some tests failed. Review logs above.\n")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
