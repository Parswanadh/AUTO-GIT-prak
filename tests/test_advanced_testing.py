"""
Test Advanced Testing Integration (#24)
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.advanced_testing.property_tester import PropertyTester, TestProperty
from src.advanced_testing.mutation_tester import MutationTester, Mutation
from src.advanced_testing.quality_validator import QualityValidator


async def test_property_based_testing():
    """Test 1: Property-based testing"""
    print("\n" + "="*70)
    print("Test 1: Property-Based Testing")
    print("="*70)
    
    tester = PropertyTester()
    
    # Property 1: List reversal is idempotent
    def reverse_idempotent(lst):
        """Reversing twice should give original list"""
        if not isinstance(lst, list):
            return True
        return list(reversed(list(reversed(lst)))) == lst
    
    tester.add_property(
        name="reverse_idempotent",
        description="Reversing a list twice returns the original",
        property_fn=reverse_idempotent,
        strategy="list_int"
    )
    
    # Property 2: Adding element increases length
    def add_increases_length(lst):
        """Adding an element should increase length by 1"""
        if not isinstance(lst, list):
            return True
        original_len = len(lst)
        lst.append(1)
        new_len = len(lst)
        return new_len == original_len + 1
    
    tester.add_property(
        name="add_increases_length",
        description="Adding element increases list length by 1",
        property_fn=add_increases_length,
        strategy="list_int"
    )
    
    # Run tests
    results = tester.test_all_properties(num_cases=30)
    
    print(f"✓ Properties tested: {results['properties_tested']}")
    print(f"✓ Total test cases: {results['total_cases']}")
    print(f"✓ Pass rate: {results['pass_rate']:.1%}")
    print(f"✓ Passed: {results['passed']}, Failed: {results['failed']}")
    
    return results['pass_rate'] >= 0.9


async def test_code_property_validation():
    """Test 2: Code property validation"""
    print("\n" + "="*70)
    print("Test 2: Code Property Validation")
    print("="*70)
    
    tester = PropertyTester()
    
    # Good code
    good_code = '''
def calculate_sum(numbers):
    """Calculate sum of numbers."""
    total = 0
    for num in numbers:
        total += num
    return total

class Calculator:
    """A simple calculator."""
    
    def add(self, a, b):
        """Add two numbers."""
        return a + b
'''
    
    validations = tester.validate_code_properties(good_code)
    
    passed = sum(1 for v in validations if v['passed'])
    total = len(validations)
    
    print(f"✓ Code validations: {total}")
    print(f"✓ Passed: {passed}/{total}")
    
    for v in validations:
        status = "✅" if v['passed'] else "❌"
        print(f"  {status} {v['property']}: {v['message']}")
    
    return passed >= 4


async def test_mutation_testing():
    """Test 3: Mutation testing"""
    print("\n" + "="*70)
    print("Test 3: Mutation Testing")
    print("="*70)
    
    tester = MutationTester()
    
    # Sample code to test
    code = '''
def add(a, b):
    return a + b

def is_positive(x):
    return x > 0

def factorial(n):
    if n == 0:
        return 1
    return n * factorial(n - 1)
'''
    
    # Generate mutations
    mutations = tester.generate_mutations(code)
    
    print(f"✓ Generated {len(mutations)} mutations")
    print(f"✓ Mutation types: {set(m.mutation_type for m in mutations)}")
    
    # Show sample mutations
    for i, m in enumerate(mutations[:3], 1):
        print(f"\n  Mutation {i}: {m.description}")
        print(f"    Line {m.line_number}: {m.original} -> {m.mutated}")
    
    return len(mutations) >= 5


async def test_mutation_detection():
    """Test 4: Mutation detection with tests"""
    print("\n" + "="*70)
    print("Test 4: Mutation Detection")
    print("="*70)
    
    tester = MutationTester()
    
    code = '''
def add(a, b):
    return a + b
'''
    
    # Test function that should catch mutations
    def test_add(code_to_test):
        """Test that should catch mutations in add function"""
        # Execute code and test
        namespace = {}
        try:
            exec(code_to_test, namespace)
            add_func = namespace.get('add')
            
            if add_func is None:
                return False
            
            # Test cases
            if add_func(2, 3) != 5:
                return False
            if add_func(0, 0) != 0:
                return False
            if add_func(-1, 1) != 0:
                return False
            
            return True
        except:
            return False
    
    # Run mutation testing
    results = tester.run_mutation_testing(code, test_add, max_mutations=5)
    
    print(f"✓ Mutations tested: {results['total_mutations']}")
    print(f"✓ Detected (killed): {results['detected']}")
    print(f"✓ Survived: {results['not_detected']}")
    print(f"✓ Mutation score: {results['mutation_score']:.1%}")
    
    return results['mutation_score'] >= 0.5


async def test_quality_validation():
    """Test 5: Code quality validation"""
    print("\n" + "="*70)
    print("Test 5: Code Quality Validation")
    print("="*70)
    
    validator = QualityValidator()
    
    # Good quality code
    good_code = '''
def calculate_average(numbers):
    """Calculate the average of a list of numbers.
    
    Args:
        numbers: List of numbers
        
    Returns:
        Average value
    """
    if not numbers:
        return 0
    
    total = sum(numbers)
    count = len(numbers)
    return total / count

class DataProcessor:
    """Process data efficiently."""
    
    def __init__(self):
        self.data = []
    
    def process(self, item):
        """Process a single item."""
        self.data.append(item)
        return len(self.data)
'''
    
    results = validator.validate_code(good_code)
    
    print(f"✓ Quality level: {results['overall']['quality_level']}")
    print(f"✓ Score: {results['overall']['score']:.1%}")
    print(f"✓ Checks passed: {results['overall']['passed']}/{results['overall']['total']}")
    
    # Show specific metrics
    if 'complexity' in results:
        metric = results['complexity']
        status = "✅" if metric.passed else "❌"
        print(f"  {status} Complexity: {metric.value} (max: {metric.threshold})")
    
    if 'maintainability' in results:
        metric = results['maintainability']
        status = "✅" if metric.passed else "❌"
        print(f"  {status} Maintainability: {metric.value:.1f} (min: {metric.threshold})")
    
    return results['overall']['score'] >= 0.7


async def test_complex_code_validation():
    """Test 6: Validate complex code"""
    print("\n" + "="*70)
    print("Test 6: Complex Code Validation")
    print("="*70)
    
    validator = QualityValidator()
    
    # More complex code
    complex_code = '''
def complex_function(data, threshold, mode='default'):
    """Complex function with multiple branches."""
    results = []
    
    for item in data:
        if mode == 'strict':
            if item > threshold and item < threshold * 2:
                results.append(item * 2)
            elif item <= threshold:
                results.append(item)
        elif mode == 'default':
            if item > threshold:
                results.append(item + 10)
            else:
                results.append(item - 10)
        else:
            results.append(item)
    
    return results
'''
    
    # Calculate complexity
    complexity = validator.calculate_cyclomatic_complexity(complex_code)
    mi = validator.calculate_maintainability_index(complex_code)
    line_stats = validator.count_code_lines(complex_code)
    
    print(f"✓ Cyclomatic complexity: {complexity}")
    print(f"✓ Maintainability index: {mi:.1f}")
    print(f"✓ Code lines: {line_stats['code']}")
    print(f"✓ Comment ratio: {line_stats['comment_ratio']:.1%}")
    
    return complexity > 0 and mi > 0


async def test_report_generation():
    """Test 7: Report generation"""
    print("\n" + "="*70)
    print("Test 7: Report Generation")
    print("="*70)
    
    # Property testing report
    prop_tester = PropertyTester()
    prop_tester.add_property(
        "test_prop",
        "Test property",
        lambda x: True,
        "int"
    )
    prop_tester.test_all_properties(num_cases=10)
    prop_report = prop_tester.generate_report()
    
    # Mutation testing report
    mut_tester = MutationTester()
    code = "def add(a, b):\n    return a + b"
    mut_tester.generate_mutations(code)
    mut_tester.test_mutation(code, mut_tester.mutations[0], lambda c: True)
    mut_report = mut_tester.generate_report()
    
    # Quality validation report
    validator = QualityValidator()
    results = validator.validate_code("def test():\n    return 1")
    quality_report = validator.generate_report(results)
    
    print(f"✓ Property testing report: {len(prop_report)} chars")
    print(f"✓ Mutation testing report: {len(mut_report)} chars")
    print(f"✓ Quality validation report: {len(quality_report)} chars")
    
    return all([
        len(prop_report) > 100,
        len(mut_report) > 100,
        len(quality_report) > 100
    ])


async def main():
    """Run all advanced testing tests"""
    print("\n" + "="*70)
    print("🧪 ADVANCED TESTING INTEGRATION TEST SUITE (#24)")
    print("="*70)
    
    tests = [
        ("Property-Based Testing", test_property_based_testing),
        ("Code Property Validation", test_code_property_validation),
        ("Mutation Generation", test_mutation_testing),
        ("Mutation Detection", test_mutation_detection),
        ("Quality Validation", test_quality_validation),
        ("Complex Code Validation", test_complex_code_validation),
        ("Report Generation", test_report_generation),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = await test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ {name} failed: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "="*70)
    print("📊 TEST RESULTS")
    print("="*70)
    
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{name:35s} {status}")
    
    passed_count = sum(1 for _, p in results if p)
    total_count = len(results)
    
    print(f"\nRESULTS: {passed_count}/{total_count} tests passed ({passed_count/total_count*100:.0f}%)")
    
    if passed_count == total_count:
        print("\n🎉 ALL ADVANCED TESTING TESTS PASSED!")
        print("\n🎯 System Capabilities:")
        print("   • Property-based test generation")
        print("   • Code property validation")
        print("   • Mutation testing for test quality")
        print("   • Cyclomatic complexity analysis")
        print("   • Maintainability index calculation")
        print("   • Code quality scoring")
        print("   • Automated report generation")
    
    return passed_count == total_count


if __name__ == "__main__":
    asyncio.run(main())
