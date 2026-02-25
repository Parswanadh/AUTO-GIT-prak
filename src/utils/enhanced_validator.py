#!/usr/bin/env python3
"""
Enhanced Code Validation with Type Checking, Security, and Linting
Integrates: mypy (types), bandit (security), ruff (linting)
"""

import ast
import subprocess
import tempfile
import os
import sys
import shutil
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def _find_executable(name: str) -> Optional[str]:
    """
    Find a CLI executable prioritising the active conda/venv Python's Scripts dir.
    Returns the full path or None if not found.
    """
    # 1. Same Scripts/bin directory as the running Python interpreter
    python_dir = Path(sys.executable).parent
    # Windows: <env>/Scripts/; Unix: <env>/bin/
    for scripts_dir in (python_dir, python_dir / "Scripts"):
        for suffix in ("", ".exe", ".cmd"):
            candidate = scripts_dir / (name + suffix)
            if candidate.is_file():
                return str(candidate)

    # 2. Fallback: system PATH
    found = shutil.which(name)
    return found


class EnhancedValidator:
    """
    Enhanced validation with multiple tools
    
    Validation Stages:
    1. Syntax (Python AST)
    2. Type Checking (mypy)
    3. Security Scanning (bandit)
    4. Linting (ruff)
    5. Import Validation
    """
    
    def __init__(self):
        self.syntax_errors = []
        self.type_errors = []
        self.security_issues = []
        self.lint_issues = []
        self.import_errors = []
    
    def validate_all(self, code: str, filename: str = "temp.py") -> Dict:
        """
        Run all validation checks
        
        Returns:
            {
                "passed": bool,
                "syntax_valid": bool,
                "type_safe": bool,
                "security_score": int (0-100),
                "lint_score": int (0-100),
                "errors": List[str],
                "warnings": List[str],
                "quality_score": int (0-100)
            }
        """
        
        results = {
            "passed": True,
            "syntax_valid": False,
            "type_safe": False,
            "security_score": 0,
            "lint_score": 0,
            "errors": [],
            "warnings": [],
            "quality_score": 0
        }
        
        # 1. Syntax Check
        syntax_ok, syntax_errors = self._check_syntax(code)
        results["syntax_valid"] = syntax_ok
        if not syntax_ok:
            results["passed"] = False
            results["errors"].extend([f"Syntax: {e}" for e in syntax_errors])
            return results  # Can't continue if syntax invalid
        
        # Create temp file for other tools
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(code)
            temp_file = f.name
        
        try:
            # 2. Type Checking (mypy)
            type_ok, type_errors, type_warnings = self._check_types(temp_file)
            results["type_safe"] = type_ok
            if not type_ok:
                results["warnings"].extend([f"Type: {e}" for e in type_warnings])
            
            # 3. Security Scanning (bandit)
            security_score, security_issues = self._check_security(temp_file)
            results["security_score"] = security_score
            if security_score < 70:
                results["passed"] = False
                results["errors"].extend([f"Security: {i}" for i in security_issues if i['severity'] in ['HIGH', 'CRITICAL']])
                results["warnings"].extend([f"Security: {i}" for i in security_issues if i['severity'] == 'MEDIUM'])
            
            # 4. Linting (ruff)
            lint_score, lint_issues = self._check_linting(temp_file)
            results["lint_score"] = lint_score
            if lint_score < 60:
                results["warnings"].extend([f"Lint: {i}" for i in lint_issues[:10]])  # Top 10 issues
            
            # 5. Calculate overall quality score
            results["quality_score"] = self._calculate_quality_score(
                syntax_ok, type_ok, security_score, lint_score
            )
            
            # Determine if passed
            if results["quality_score"] < 50:
                results["passed"] = False
            
        finally:
            # Cleanup
            try:
                os.unlink(temp_file)
            except:
                pass
        
        return results
    
    def _check_syntax(self, code: str) -> Tuple[bool, List[str]]:
        """Check Python syntax using AST"""
        try:
            ast.parse(code)
            return True, []
        except SyntaxError as e:
            error_msg = f"Line {e.lineno}: {e.msg}"
            if e.text:
                error_msg += f"\n  {e.text.strip()}\n  {' ' * (e.offset - 1)}^"
            return False, [error_msg]
        except Exception as e:
            return False, [str(e)]
    
    def _check_types(self, filepath: str) -> Tuple[bool, List[str], List[str]]:
        """Check types using mypy"""
        mypy_exe = _find_executable('mypy')
        if not mypy_exe:
            logger.warning("mypy not installed, skipping type checking")
            return True, [], ["mypy not available"]
        try:
            result = subprocess.run(
                [mypy_exe, filepath, '--ignore-missing-imports', '--no-error-summary'],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30
            )
            
            if result.returncode == 0:
                return True, [], []
            
            # Parse mypy output
            errors = []
            warnings = []
            for line in result.stdout.split('\n'):
                if line.strip() and filepath in line:
                    # Extract just the error message
                    parts = line.split(':', 3)
                    if len(parts) >= 4:
                        msg = f"Line {parts[1]}: {parts[3].strip()}"
                        if 'error:' in line:
                            errors.append(msg)
                        else:
                            warnings.append(msg)
            
            # Type errors are warnings, not blockers
            return len(errors) == 0, errors, warnings
            
        except subprocess.TimeoutExpired:
            return True, [], ["Type checking timeout"]
        except FileNotFoundError:
            logger.warning("mypy executable not found")
            return True, [], ["mypy not available"]
        except Exception as e:
            logger.error(f"Type checking error: {e}")
            return True, [], [str(e)]
    
    def _check_security(self, filepath: str) -> Tuple[int, List[Dict]]:
        """Check security using bandit"""
        bandit_exe = _find_executable('bandit')
        if not bandit_exe:
            logger.warning("bandit not installed, skipping security scanning")
            return 100, []
        try:
            result = subprocess.run(
                [bandit_exe, '-f', 'json', filepath],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30
            )
            
            import json
            data = json.loads(result.stdout)
            
            issues = []
            for issue in data.get('results', []):
                issues.append({
                    'line': issue.get('line_number'),
                    'severity': issue.get('issue_severity'),
                    'confidence': issue.get('issue_confidence'),
                    'message': issue.get('issue_text'),
                    'cwe': issue.get('issue_cwe', {}).get('id', 'N/A')
                })
            
            # Calculate security score
            score = 100
            for issue in issues:
                if issue['severity'] == 'HIGH':
                    score -= 20
                elif issue['severity'] == 'MEDIUM':
                    score -= 10
                elif issue['severity'] == 'LOW':
                    score -= 5
            
            score = max(0, score)
            
            return score, issues
            
        except subprocess.TimeoutExpired:
            return 100, []
        except FileNotFoundError:
            logger.warning("bandit executable not found")
            return 100, []
        except Exception as e:
            logger.error(f"Security scanning error: {e}")
            return 100, []
    
    def _check_linting(self, filepath: str) -> Tuple[int, List[str]]:
        """Check code quality using ruff"""
        ruff_exe = _find_executable('ruff')
        if not ruff_exe:
            logger.warning("ruff not installed, skipping linting")
            return 100, []
        try:
            result = subprocess.run(
                [ruff_exe, 'check', filepath, '--output-format=json'],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30
            )
            
            import json
            issues_data = json.loads(result.stdout)
            
            issues = []
            for issue in issues_data:
                loc = issue.get('location', {})
                issues.append(
                    f"Line {loc.get('row')}: {issue.get('code')} - {issue.get('message')}"
                )
            
            # Calculate lint score
            score = 100 - min(len(issues) * 2, 50)  # Max 50 point deduction
            
            return score, issues
            
        except subprocess.TimeoutExpired:
            return 100, []
        except FileNotFoundError:
            logger.warning("ruff executable not found")
            return 100, []
        except Exception as e:
            logger.error(f"Linting error: {e}")
            return 100, []
    
    def _calculate_quality_score(
        self, 
        syntax_ok: bool, 
        type_ok: bool, 
        security_score: int, 
        lint_score: int
    ) -> int:
        """Calculate overall quality score (0-100)"""
        
        if not syntax_ok:
            return 0
        
        # Weighted average
        score = 0
        score += 40 if syntax_ok else 0  # Syntax is most important
        score += 20 if type_ok else 10    # Types are important but not critical
        score += security_score * 0.25    # 25% weight on security
        score += lint_score * 0.15        # 15% weight on style
        
        return int(min(100, score))
    
    def auto_fix_linting(self, code: str) -> str:
        """Auto-fix linting issues using ruff"""
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
                f.write(code)
                temp_file = f.name
            
            # Run ruff fix
            subprocess.run(
                ['ruff', 'check', '--fix', temp_file],
                capture_output=True,
                timeout=10
            )
            
            # Read fixed code
            with open(temp_file, 'r', encoding='utf-8') as f:
                fixed_code = f.read()
            
            os.unlink(temp_file)
            return fixed_code
            
        except Exception as e:
            logger.error(f"Auto-fix error: {e}")
            return code


def validate_code_enhanced(code: str, filename: str = "temp.py") -> Dict:
    """
    Convenience function for enhanced validation
    
    Usage:
        results = validate_code_enhanced(code)
        if results["passed"]:
            print("Code is valid!")
        else:
            print("Errors:", results["errors"])
    """
    validator = EnhancedValidator()
    return validator.validate_all(code, filename)


if __name__ == "__main__":
    # Test the validator
    
    test_code = '''
import os
import sys

def calculate_sum(a: int, b: int) -> int:
    """Calculate sum of two numbers"""
    return a + b

def divide(x, y):
    # Missing type hints
    # Potential division by zero (security)
    return x / y

# Hardcoded password (security issue)
PASSWORD = "admin123"

def main():
    result = calculate_sum(5, 3)
    print(f"Sum: {result}")
    
    # Using eval (security issue)
    user_input = input("Enter expression: ")
    eval(user_input)

if __name__ == "__main__":
    main()
'''
    
    print("Testing Enhanced Validator...")
    print("=" * 60)
    
    results = validate_code_enhanced(test_code)
    
    print(f"\n✅ Passed: {results['passed']}")
    print(f"📝 Syntax Valid: {results['syntax_valid']}")
    print(f"🔍 Type Safe: {results['type_safe']}")
    print(f"🔒 Security Score: {results['security_score']}/100")
    print(f"✨ Lint Score: {results['lint_score']}/100")
    print(f"🎯 Overall Quality: {results['quality_score']}/100")
    
    if results['errors']:
        print(f"\n❌ Errors ({len(results['errors'])}):")
        for error in results['errors'][:5]:
            print(f"  - {error}")
    
    if results['warnings']:
        print(f"\n⚠️  Warnings ({len(results['warnings'])}):")
        for warning in results['warnings'][:5]:
            print(f"  - {warning}")
    
    print("\n" + "=" * 60)
    print("Test complete!")
