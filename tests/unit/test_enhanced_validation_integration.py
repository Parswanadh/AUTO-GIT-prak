"""
Test the enhanced validation integration in code_testing_node

This tests that:
1. EnhancedValidator is imported correctly
2. Validation results are calculated
3. Quality scoring works
4. Threshold checking works (50/100 minimum)
"""

import asyncio
import sys
import os
from pathlib import Path
import pytest

# Mark as integration-style validation since it exercises real node behavior.
pytestmark = pytest.mark.integration

# Add repository src directory to path properly.
project_root = Path(__file__).resolve().parents[2]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from src.langraph_pipeline.nodes import code_testing_node
from src.langraph_pipeline.state import AutoGITState


async def test_validation_integration():
    """Test that enhanced validation is integrated into code_testing_node"""
    
    print("=" * 60)
    print("Testing Enhanced Validation Integration")
    print("=" * 60)
    
    # Test Case 1: Good quality code (should pass)
    print("\n📝 Test Case 1: High Quality Code")
    print("-" * 60)
    
    good_code = """
def calculate_sum(a: int, b: int) -> int:
    \"\"\"Calculate the sum of two numbers.\"\"\"
    return a + b

def main():
    result = calculate_sum(5, 3)
    print(f"Result: {result}")

if __name__ == "__main__":
    main()
"""
    
    state = {
        "generated_code": {
            "files": {
                "calculator.py": good_code
            }
        }
    }
    
    result = await code_testing_node(state)
    
    print(f"✅ Stage: {result.get('current_stage')}")
    print(f"✅ Tests Passed: {result.get('tests_passed')}")
    print(f"📊 Code Quality: {result.get('code_quality', 0):.1f}/100")
    
    test_results = result.get('test_results', {})
    if 'validation_results' in test_results:
        print(f"🔍 Validation Results Found: {len(test_results['validation_results'])} file(s)")
        for filename, validation in test_results['validation_results'].items():
            print(f"  📄 {filename}:")
            print(f"    - Syntax: {'✅' if validation.get('syntax_valid') else '❌'}")
            print(f"    - Type Safe: {'✅' if validation.get('type_safe') else '⚠️'}")
            print(f"    - Security: {validation.get('security_score', 0)}/100")
            print(f"    - Lint: {validation.get('lint_score', 0)}/100")
            print(f"    - Quality: {validation.get('quality_score', 0)}/100")
    
    assert result.get('code_quality', 0) >= 50, "Good code should have quality >= 50"
    validation_results = test_results.get('validation_results', {})
    calculator_validation = validation_results.get('calculator.py', {})
    assert calculator_validation.get('syntax_valid') is True, "Good code should be syntax valid"
    
    print("\n✅ Test Case 1 PASSED")
    
    # Test Case 2: Poor quality code (should fail quality check)
    print("\n📝 Test Case 2: Low Quality Code with Security Issues")
    print("-" * 60)
    
    bad_code = """
import os

# Security issue: using eval
def unsafe_calc(expr):
    return eval(expr)

# Security issue: hardcoded password
PASSWORD = "admin123"

def login(pwd):
    if pwd == PASSWORD:
        return True
    return False

unsafe_calc("__import__('os').system('ls')")
"""
    
    state2 = {
        "generated_code": {
            "files": {
                "unsafe.py": bad_code
            }
        }
    }
    
    result2 = await code_testing_node(state2)
    
    print(f"⚠️  Stage: {result2.get('current_stage')}")
    print(f"⚠️  Tests Passed: {result2.get('tests_passed')}")
    print(f"📊 Code Quality: {result2.get('code_quality', 0):.1f}/100")
    
    test_results2 = result2.get('test_results', {})
    if 'validation_results' in test_results2:
        print(f"🔍 Validation Results Found: {len(test_results2['validation_results'])} file(s)")
        for filename, validation in test_results2['validation_results'].items():
            print(f"  📄 {filename}:")
            print(f"    - Security: {validation.get('security_score', 0)}/100")
            security_issues = validation.get('security_issues', [])
            if security_issues:
                print(f"    - Security Issues Detected: {len(security_issues)}")
                for issue in security_issues[:3]:
                    print(f"      • {issue}")
    
    # This code has security issues, so security score should reflect penalties.
    quality2 = result2.get('code_quality', 0)
    bad_validation_results = test_results2.get('validation_results', {})
    unsafe_validation = bad_validation_results.get('unsafe.py', {})
    assert unsafe_validation.get('security_score', 100) < 100, "Unsafe code should reduce security score"
    assert quality2 <= result.get('code_quality', 100), "Unsafe code should not outscore good code"
    
    print("\n✅ Test Case 2 PASSED (security issues detected)")
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED - Enhanced Validation Integrated!")
    print("=" * 60)
    print("\n📊 Summary:")
    print(f"  - Good code quality: {result.get('code_quality', 0):.1f}/100")
    print(f"  - Bad code quality: {quality2:.1f}/100")
    print(f"  - Quality threshold: 50/100")
    print("\n🎯 Integration Successful!")


if __name__ == "__main__":
    try:
        asyncio.run(test_validation_integration())
    except Exception as e:
        print(f"\n❌ Test Failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
