"""
Code Quality Validator

Validates code quality metrics: complexity, maintainability, style compliance.
"""

import ast
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class QualityMetric:
    """Represents a code quality metric"""
    name: str
    value: float
    threshold: float
    passed: bool
    message: str


class QualityValidator:
    """
    Validates code quality without external dependencies.
    Checks complexity, maintainability, and style.
    """
    
    def __init__(self):
        self.metrics: Dict[str, QualityMetric] = {}
    
    def calculate_cyclomatic_complexity(self, code: str) -> int:
        """
        Calculate cyclomatic complexity (number of decision points + 1).
        Simple version without proper AST visitor.
        """
        try:
            tree = ast.parse(code)
            
            complexity = 1  # Start at 1
            
            for node in ast.walk(tree):
                # Add 1 for each decision point
                if isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                    complexity += 1
                elif isinstance(node, ast.BoolOp):
                    # Each and/or adds complexity
                    complexity += len(node.values) - 1
                elif isinstance(node, ast.comprehension):
                    complexity += 1
            
            return complexity
        except:
            return 0
    
    def calculate_maintainability_index(self, code: str) -> float:
        """
        Calculate maintainability index (simplified version).
        
        MI = 171 - 5.2 * ln(Halstead Volume) - 0.23 * (Cyclomatic Complexity) - 16.2 * ln(Lines of Code)
        
        Simplified: Focus on LOC and complexity
        Returns: 0-100 (higher is better)
        """
        lines = [l for l in code.split('\n') if l.strip() and not l.strip().startswith('#')]
        loc = len(lines)
        
        complexity = self.calculate_cyclomatic_complexity(code)
        
        # Simplified formula (0-100 scale)
        if loc == 0:
            return 100.0
        
        # Penalize high LOC and complexity
        mi = 100 - (loc / 10) - (complexity * 2)
        return max(0.0, min(100.0, mi))
    
    def count_code_lines(self, code: str) -> Dict[str, int]:
        """Count different types of lines"""
        lines = code.split('\n')
        
        total = len(lines)
        blank = len([l for l in lines if not l.strip()])
        comments = len([l for l in lines if l.strip().startswith('#')])
        code_lines = total - blank - comments
        
        return {
            'total': total,
            'code': code_lines,
            'blank': blank,
            'comments': comments,
            'comment_ratio': comments / code_lines if code_lines > 0 else 0
        }
    
    def check_naming_conventions(self, code: str) -> Dict[str, Any]:
        """Check Python naming conventions"""
        issues = []
        
        try:
            tree = ast.parse(code)
            
            for node in ast.walk(tree):
                # Check function names (should be snake_case)
                if isinstance(node, ast.FunctionDef):
                    if not re.match(r'^[a-z_][a-z0-9_]*$', node.name) and not node.name.startswith('_'):
                        if node.name != node.name.lower():
                            issues.append(f"Function '{node.name}' should be snake_case")
                
                # Check class names (should be PascalCase)
                if isinstance(node, ast.ClassDef):
                    if not re.match(r'^[A-Z][a-zA-Z0-9]*$', node.name):
                        issues.append(f"Class '{node.name}' should be PascalCase")
                
                # Check constant names (should be UPPER_CASE)
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            name = target.id
                            # If at module level and all caps expected
                            if name.isupper() and '_' in name:
                                pass  # Good constant
                            elif name.isupper():
                                pass  # Good constant
        except:
            pass
        
        return {
            'issues': issues,
            'passed': len(issues) == 0
        }
    
    def check_function_length(self, code: str, max_lines: int = 50) -> Dict[str, Any]:
        """Check if functions are too long"""
        long_functions = []
        
        try:
            tree = ast.parse(code)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    func_lines = node.end_lineno - node.lineno if hasattr(node, 'end_lineno') else 0
                    if func_lines > max_lines:
                        long_functions.append({
                            'name': node.name,
                            'lines': func_lines,
                            'max': max_lines
                        })
        except:
            pass
        
        return {
            'long_functions': long_functions,
            'passed': len(long_functions) == 0
        }
    
    def validate_code(self, code: str, language: str = "python") -> Dict[str, Any]:
        """
        Run all quality validations on code.
        
        Returns:
            Dictionary with all quality metrics and pass/fail status
        """
        if language != "python":
            return {'error': 'Only Python supported currently'}
        
        results = {}
        
        # Cyclomatic complexity
        complexity = self.calculate_cyclomatic_complexity(code)
        complexity_passed = complexity <= 15
        results['complexity'] = QualityMetric(
            name='Cyclomatic Complexity',
            value=complexity,
            threshold=15,
            passed=complexity_passed,
            message=f'Complexity: {complexity} (threshold: 15)'
        )
        
        # Maintainability index
        mi = self.calculate_maintainability_index(code)
        mi_passed = mi >= 60
        results['maintainability'] = QualityMetric(
            name='Maintainability Index',
            value=mi,
            threshold=60,
            passed=mi_passed,
            message=f'MI: {mi:.1f} (threshold: 60)'
        )
        
        # Line counts
        line_stats = self.count_code_lines(code)
        results['lines'] = {
            'code_lines': line_stats['code'],
            'comment_ratio': line_stats['comment_ratio'],
            'passed': line_stats['comment_ratio'] >= 0.1,
            'message': f"Code lines: {line_stats['code']}, Comment ratio: {line_stats['comment_ratio']:.1%}"
        }
        
        # Naming conventions
        naming = self.check_naming_conventions(code)
        results['naming'] = {
            'issues': naming['issues'],
            'passed': naming['passed'],
            'message': f"Naming issues: {len(naming['issues'])}"
        }
        
        # Function length
        func_length = self.check_function_length(code)
        results['function_length'] = {
            'long_functions': func_length['long_functions'],
            'passed': func_length['passed'],
            'message': f"Long functions: {len(func_length['long_functions'])}"
        }
        
        # Overall score
        passed_checks = sum(1 for v in results.values() 
                          if isinstance(v, dict) and v.get('passed', False))
        passed_checks += sum(1 for v in results.values() 
                           if isinstance(v, QualityMetric) and v.passed)
        total_checks = len(results)
        
        results['overall'] = {
            'score': passed_checks / total_checks if total_checks > 0 else 0,
            'passed': passed_checks,
            'total': total_checks,
            'quality_level': self._get_quality_level(passed_checks / total_checks if total_checks > 0 else 0)
        }
        
        return results
    
    def _get_quality_level(self, score: float) -> str:
        """Get quality level from score"""
        if score >= 0.9:
            return "EXCELLENT"
        elif score >= 0.7:
            return "GOOD"
        elif score >= 0.5:
            return "ACCEPTABLE"
        else:
            return "NEEDS IMPROVEMENT"
    
    def generate_report(self, results: Dict[str, Any]) -> str:
        """Generate quality validation report"""
        report = []
        report.append("=" * 70)
        report.append("CODE QUALITY VALIDATION REPORT")
        report.append("=" * 70)
        
        # Overall score
        if 'overall' in results:
            overall = results['overall']
            report.append(f"\nOverall Quality: {overall['quality_level']}")
            report.append(f"Score: {overall['passed']}/{overall['total']} checks passed ({overall['score']:.1%})")
        
        report.append("\n" + "-" * 70)
        report.append("Detailed Metrics:")
        report.append("-" * 70)
        
        # Complexity
        if 'complexity' in results:
            metric = results['complexity']
            status = "✅" if metric.passed else "❌"
            report.append(f"\n{status} {metric.name}: {metric.value} (max: {metric.threshold})")
        
        # Maintainability
        if 'maintainability' in results:
            metric = results['maintainability']
            status = "✅" if metric.passed else "❌"
            report.append(f"{status} {metric.name}: {metric.value:.1f} (min: {metric.threshold})")
        
        # Lines
        if 'lines' in results:
            lines = results['lines']
            status = "✅" if lines['passed'] else "⚠️ "
            report.append(f"\n{status} Code Structure:")
            report.append(f"  - Code lines: {lines['code_lines']}")
            report.append(f"  - Comment ratio: {lines['comment_ratio']:.1%}")
        
        # Naming
        if 'naming' in results:
            naming = results['naming']
            status = "✅" if naming['passed'] else "⚠️ "
            report.append(f"\n{status} Naming Conventions:")
            if naming['issues']:
                for issue in naming['issues']:
                    report.append(f"  - {issue}")
            else:
                report.append("  - All names follow conventions")
        
        # Function length
        if 'function_length' in results:
            func = results['function_length']
            status = "✅" if func['passed'] else "⚠️ "
            report.append(f"\n{status} Function Length:")
            if func['long_functions']:
                for f in func['long_functions']:
                    report.append(f"  - {f['name']}: {f['lines']} lines (max: {f['max']})")
            else:
                report.append("  - All functions within acceptable length")
        
        report.append("\n" + "=" * 70)
        return '\n'.join(report)
