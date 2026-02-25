"""
Property-Based Testing with Hypothesis

Generates test cases automatically based on properties that should always hold true.
"""

from typing import Callable, Any, List, Dict, Optional
import ast
import re
from dataclasses import dataclass


@dataclass
class TestProperty:
    """Represents a property that should hold for all inputs"""
    name: str
    description: str
    property_fn: Callable
    strategy: str  # Type of inputs to generate
    examples: List[Any]


class PropertyTester:
    """
    Property-based testing without external dependencies.
    Generates test cases based on properties that code should satisfy.
    """
    
    def __init__(self):
        self.properties: List[TestProperty] = []
        self.test_results: Dict[str, List[Dict]] = {}
    
    def add_property(self, name: str, description: str, 
                    property_fn: Callable, strategy: str = "any") -> TestProperty:
        """
        Add a property to test.
        
        Args:
            name: Property name
            description: What this property tests
            property_fn: Function that returns True if property holds
            strategy: Type of test data to generate ('int', 'str', 'list', 'any')
        
        Returns:
            The created TestProperty
        """
        prop = TestProperty(
            name=name,
            description=description,
            property_fn=property_fn,
            strategy=strategy,
            examples=[]
        )
        self.properties.append(prop)
        return prop
    
    def generate_test_cases(self, strategy: str, count: int = 10) -> List[Any]:
        """
        Generate test cases based on strategy.
        Simple implementation without Hypothesis library.
        """
        import random
        
        if strategy == "int":
            return [
                random.randint(-1000, 1000) for _ in range(count)
            ]
        elif strategy == "positive_int":
            return [
                random.randint(1, 1000) for _ in range(count)
            ]
        elif strategy == "str":
            chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
            return [
                ''.join(random.choice(chars) for _ in range(random.randint(0, 20)))
                for _ in range(count)
            ]
        elif strategy == "list_int":
            return [
                [random.randint(-100, 100) for _ in range(random.randint(0, 10))]
                for _ in range(count)
            ]
        elif strategy == "list_str":
            chars = "abcdefghijklmnopqrstuvwxyz"
            return [
                [''.join(random.choice(chars) for _ in range(random.randint(1, 5))) 
                 for _ in range(random.randint(0, 5))]
                for _ in range(count)
            ]
        elif strategy == "dict":
            return [
                {f"key_{i}": random.randint(0, 100) for i in range(random.randint(0, 5))}
                for _ in range(count)
            ]
        else:  # "any"
            return [
                random.choice([
                    random.randint(-100, 100),
                    ''.join(random.choice("abc") for _ in range(5)),
                    [1, 2, 3],
                    {"key": "value"}
                ])
                for _ in range(count)
            ]
    
    def test_property(self, prop: TestProperty, num_cases: int = 20) -> Dict[str, Any]:
        """
        Test a property with generated test cases.
        
        Returns:
            Results dictionary with pass/fail info
        """
        test_cases = self.generate_test_cases(prop.strategy, num_cases)
        
        passed = 0
        failed = 0
        errors = []
        
        for i, test_case in enumerate(test_cases):
            try:
                result = prop.property_fn(test_case)
                if result:
                    passed += 1
                else:
                    failed += 1
                    errors.append({
                        'case': i,
                        'input': test_case,
                        'error': 'Property returned False'
                    })
            except Exception as e:
                failed += 1
                errors.append({
                    'case': i,
                    'input': test_case,
                    'error': str(e)
                })
        
        result = {
            'property': prop.name,
            'description': prop.description,
            'total_cases': num_cases,
            'passed': passed,
            'failed': failed,
            'pass_rate': passed / num_cases if num_cases > 0 else 0,
            'errors': errors[:5]  # First 5 errors
        }
        
        if prop.name not in self.test_results:
            self.test_results[prop.name] = []
        self.test_results[prop.name].append(result)
        
        return result
    
    def test_all_properties(self, num_cases: int = 20) -> Dict[str, Any]:
        """Test all registered properties"""
        results = {}
        
        for prop in self.properties:
            results[prop.name] = self.test_property(prop, num_cases)
        
        # Summary
        total_passed = sum(r['passed'] for r in results.values())
        total_failed = sum(r['failed'] for r in results.values())
        
        return {
            'properties_tested': len(self.properties),
            'total_cases': total_passed + total_failed,
            'passed': total_passed,
            'failed': total_failed,
            'pass_rate': total_passed / (total_passed + total_failed) if (total_passed + total_failed) > 0 else 0,
            'results': results
        }
    
    def validate_code_properties(self, code: str, language: str = "python") -> List[Dict[str, Any]]:
        """
        Validate common properties for generated code.
        
        Args:
            code: Code to validate
            language: Programming language
        
        Returns:
            List of validation results
        """
        validations = []
        
        if language == "python":
            # Property 1: Code is syntactically valid
            try:
                ast.parse(code)
                validations.append({
                    'property': 'syntax_valid',
                    'passed': True,
                    'message': 'Code is syntactically valid'
                })
            except SyntaxError as e:
                validations.append({
                    'property': 'syntax_valid',
                    'passed': False,
                    'message': f'Syntax error: {e}'
                })
            
            # Property 2: No obvious security issues
            dangerous_patterns = [
                r'eval\s*\(',
                r'exec\s*\(',
                r'__import__\s*\(',
                r'open\s*\([^)]*[\'"]w',
                r'os\.system\s*\(',
            ]
            
            security_issues = []
            for pattern in dangerous_patterns:
                if re.search(pattern, code):
                    security_issues.append(pattern)
            
            validations.append({
                'property': 'security_safe',
                'passed': len(security_issues) == 0,
                'message': f'Security issues found: {security_issues}' if security_issues else 'No obvious security issues'
            })
            
            # Property 3: Has proper structure (functions/classes)
            has_functions = bool(re.search(r'def\s+\w+\s*\(', code))
            has_classes = bool(re.search(r'class\s+\w+', code))
            
            validations.append({
                'property': 'has_structure',
                'passed': has_functions or has_classes,
                'message': f'Functions: {has_functions}, Classes: {has_classes}'
            })
            
            # Property 4: Has docstrings (for public functions)
            functions_with_docs = len(re.findall(r'def\s+\w+\s*\([^)]*\)\s*:\s*"""', code))
            total_functions = len(re.findall(r'def\s+\w+\s*\(', code))
            
            doc_coverage = functions_with_docs / total_functions if total_functions > 0 else 0
            
            validations.append({
                'property': 'has_docstrings',
                'passed': doc_coverage >= 0.5,
                'message': f'Documentation coverage: {doc_coverage:.1%} ({functions_with_docs}/{total_functions})'
            })
            
            # Property 5: Reasonable length
            lines = code.strip().split('\n')
            non_empty_lines = [l for l in lines if l.strip()]
            
            validations.append({
                'property': 'reasonable_length',
                'passed': 5 <= len(non_empty_lines) <= 500,
                'message': f'{len(non_empty_lines)} non-empty lines'
            })
        
        return validations
    
    def generate_report(self) -> str:
        """Generate a text report of all test results"""
        report = []
        report.append("=" * 70)
        report.append("PROPERTY-BASED TESTING REPORT")
        report.append("=" * 70)
        
        for prop_name, results in self.test_results.items():
            report.append(f"\nProperty: {prop_name}")
            report.append("-" * 70)
            
            for result in results:
                report.append(f"Description: {result['description']}")
                report.append(f"Test cases: {result['total_cases']}")
                report.append(f"Passed: {result['passed']} ({result['pass_rate']:.1%})")
                report.append(f"Failed: {result['failed']}")
                
                if result['errors']:
                    report.append("\nSample failures:")
                    for err in result['errors'][:3]:
                        report.append(f"  - Case {err['case']}: {err['error']}")
                        report.append(f"    Input: {err['input']}")
        
        report.append("\n" + "=" * 70)
        return '\n'.join(report)
