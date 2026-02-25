"""Tests for intelligent model router"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.model_router import ModelRouter, TaskType


def test_model_selection():
    """Test basic model selection"""
    print("\n" + "="*70)
    print("TEST: Model Selection")
    print("="*70)
    
    router = ModelRouter()
    
    # Test coding task
    model = router.select_model(TaskType.CODE_GENERATION)
    print(f"\nCode generation: {model}")
    assert model == "qwen2.5-coder:7b", f"Expected qwen2.5-coder:7b, got {model}"
    
    # Test reasoning task
    model = router.select_model(TaskType.REASONING)
    print(f"Reasoning: {model}")
    assert model == "deepseek-r1:8b", f"Expected deepseek-r1:8b, got {model}"
    
    # Test tool calling
    model = router.select_model(TaskType.TOOL_CALLING)
    print(f"Tool calling: {model}")
    assert model == "phi4-mini:3.8b", f"Expected phi4-mini:3.8b, got {model}"
    
    # Test embeddings
    model = router.select_model(TaskType.EMBEDDINGS)
    print(f"Embeddings: {model}")
    assert model == "nomic-embed-text:latest", f"Expected nomic-embed-text, got {model}"
    
    print("\nAll model selections correct!")
    return True


def test_routing_strategies():
    """Test pipeline routing strategies"""
    print("\n" + "="*70)
    print("TEST: Routing Strategies")
    print("="*70)
    
    router = ModelRouter()
    
    # Quality strategy
    quality = router.get_routing_strategy("quality")
    print("\nQuality strategy:")
    for stage, model in quality.items():
        print(f"  - {stage}: {model}")
    
    # Fast strategy
    fast = router.get_routing_strategy("fast")
    print("\nFast strategy:")
    for stage, model in fast.items():
        print(f"  - {stage}: {model}")
    
    print("\nRouting strategy tests passed!")
    return True


def test_model_recommendations():
    """Test model recommendations"""
    print("\n" + "="*70)
    print("TEST: Model Recommendations")
    print("="*70)
    
    router = ModelRouter()
    
    recommendations = router.get_recommended_models()
    
    print("\nTop 3 models for each task:")
    for task, models in recommendations.items():
        if models:
            print(f"\n  {task}:")
            for i, model in enumerate(models[:3], 1):
                print(f"    {i}. {model}")
    
    print("\nRecommendation test passed!")
    return True


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("INTELLIGENT MODEL ROUTER TEST SUITE")
    print("="*70)
    
    tests = [
        ("Model Selection", test_model_selection),
        ("Routing Strategies", test_routing_strategies),
        ("Model Recommendations", test_model_recommendations),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"\n✓ {name} PASSED")
        except Exception as e:
            print(f"\n✗ {name} FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "="*70)
    print("FINAL RESULTS")
    print("="*70)
    print(f"Passed: {passed}/{len(tests)}")
    print(f"Failed: {failed}/{len(tests)}")
    print(f"Success Rate: {passed/len(tests):.1%}")
    
    if failed == 0:
        print("\n✓ ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n✗ {failed} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
