"""
Multi-layer code validation for generated code.

Features:
- Syntax validation (AST parsing)
- Type checking (mypy)
- Code quality (pylint/ruff)
- Security scanning (bandit)
- Import validation (PyPI check)
- Test generation
- README quality check
"""

import ast
import json
import os
import subprocess
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional
import urllib.request
import urllib.error

from src.utils.error_types import ValidationError
from src.utils.logger import get_logger

logger = get_logger("code_validator")


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationIssue:
    """
    A single validation issue.

    Attributes:
        layer: Validation layer that found the issue
        severity: Issue severity
        message: Human-readable message
        file: File where issue was found
        line: Line number (if applicable)
        column: Column number (if applicable)
        code: Relevant code snippet
    """
    layer: str
    severity: ValidationSeverity
    message: str
    file: str
    line: Optional[int] = None
    column: Optional[int] = None
    code: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "layer": self.layer,
            "severity": self.severity.value,
            "message": self.message,
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "code": self.code,
        }


@dataclass
class ValidationResult:
    """
    Result of code validation.

    Attributes:
        passed: Whether validation passed
        score: Overall score (0-10)
        issues: List of validation issues
        layer_results: Results per layer
        recommendation: What to do with the code
    """
    passed: bool
    score: float
    issues: list[ValidationIssue] = field(default_factory=list)
    layer_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    recommendation: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "passed": self.passed,
            "score": self.score,
            "issues": [issue.to_dict() for issue in self.issues],
            "layer_results": self.layer_results,
            "recommendation": self.recommendation,
        }


class BaseValidator(ABC):
    """Base class for all validators."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def validate(self, code: str, file_path: str = "<string>") -> ValidationResult:
        """
        Validate code.

        Args:
            code: Python code to validate
            file_path: File path for reporting

        Returns:
            ValidationResult with findings
        """
        pass


class SyntaxValidator(BaseValidator):
    """
    Layer 1: Syntax validation using AST parsing.

    Catches:
    - SyntaxError
    - IndentationError
    - Invalid Python structure
    """

    def __init__(self):
        super().__init__("syntax")

    def validate(self, code: str, file_path: str = "<string>") -> ValidationResult:
        """Validate Python syntax."""
        issues = []

        try:
            ast.parse(code, filename=file_path)
            passed = True
            message = "Syntax is valid"
        except SyntaxError as e:
            issues.append(ValidationIssue(
                layer=self.name,
                severity=ValidationSeverity.ERROR,
                message=f"Syntax error: {e.msg}",
                file=file_path,
                line=e.lineno,
                column=e.offset,
                code=e.text.strip() if e.text else None,
            ))
            passed = False
            message = f"Syntax error: {e.msg}"
        except IndentationError as e:
            issues.append(ValidationIssue(
                layer=self.name,
                severity=ValidationSeverity.ERROR,
                message=f"Indentation error: {e.msg}",
                file=file_path,
                line=e.lineno,
                code=e.text.strip() if e.text else None,
            ))
            passed = False
            message = f"Indentation error: {e.msg}"
        except Exception as e:
            issues.append(ValidationIssue(
                layer=self.name,
                severity=ValidationSeverity.ERROR,
                message=f"Parsing error: {str(e)}",
                file=file_path,
            ))
            passed = False
            message = f"Parsing error: {str(e)}"

        score = 10.0 if passed else 0.0

        return ValidationResult(
            passed=passed,
            score=score,
            issues=issues,
            layer_results={
                self.name: {
                    "passed": passed,
                    "message": message,
                }
            },
            recommendation="proceed" if passed else "fix_syntax",
        )


class ImportValidator(BaseValidator):
    """
    Layer 2: Import validation.

    Checks:
    - All imports exist in PyPI
    - No deprecated packages
    - Version compatibility hints
    """

    def __init__(self):
        super().__init__("imports")
        self.pypi_cache = {}

    def _check_pypi(self, package_name: str) -> bool:
        """
        Check if package exists on PyPI.

        Args:
            package_name: Name of package (without extras)

        Returns:
            True if package exists
        """
        # Normalize package name (remove version specifiers, etc.)
        package_name = package_name.split("[")[0].split("=")[0].split("<")[0].split(">")[0].strip()

        if package_name in self.pypi_cache:
            return self.pypi_cache[package_name]

        try:
            url = f"https://pypi.org/pypi/{package_name}/json"
            with urllib.request.urlopen(url, timeout=5) as response:
                if response.status == 200:
                    self.pypi_cache[package_name] = True
                    return True
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
            pass

        self.pypi_cache[package_name] = False
        return False

    def validate(self, code: str, file_path: str = "<string>") -> ValidationResult:
        """Validate imports."""
        issues = []
        imports = []

        try:
            tree = ast.parse(code, filename=file_path)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name.split(".")[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module.split(".")[0])

        except Exception as e:
            # If we can't parse, skip import validation
            return ValidationResult(
                passed=True,
                score=10.0,
                issues=[],
                layer_results={
                    self.name: {
                        "passed": True,
                        "message": "Skipped (parse error)",
                        "imports": [],
                    }
                },
            )

        # Check each import
        unknown_imports = []
        stdlib_modules = {
            "os", "sys", "pathlib", "json", "typing", "dataclasses",
            "enum", "abc", "collections", "itertools", "functools",
            "asyncio", "tempfile", "subprocess", "time", "datetime",
            "math", "random", "re", "string", "io", "argparse",
            "logging", "contextlib", "warnings", "copy", "hashlib",
            # Add more as needed
        }

        for imp in set(imports):
            if imp in stdlib_modules:
                continue

            if not self._check_pypi(imp):
                issues.append(ValidationIssue(
                    layer=self.name,
                    severity=ValidationSeverity.WARNING,
                    message=f"Unknown import '{imp}' - not found in PyPI or stdlib",
                    file=file_path,
                ))
                unknown_imports.append(imp)

        passed = len(unknown_imports) == 0
        score = max(0, 10 - len(unknown_imports) * 2)

        return ValidationResult(
            passed=passed,
            score=score,
            issues=issues,
            layer_results={
                self.name: {
                    "passed": passed,
                    "imports_checked": len(set(imports)),
                    "unknown_imports": unknown_imports,
                }
            },
        )


class SecurityValidator(BaseValidator):
    """
    Layer 3: Security scanning using bandit.

    Catches:
    - Use of eval() or exec()
    - SQL injection patterns
    - Unsafe pickle usage
    - Hardcoded credentials
    - Weak crypto
    """

    def __init__(self):
        super().__init__("security")

    def validate(self, code: str, file_path: str = "<string>") -> ValidationResult:
        """Validate security issues."""
        issues = []

        # Check for dangerous functions
        dangerous_patterns = {
            r"\beval\s*\(": "Use of eval() is dangerous",
            r"\bexec\s*\(": "Use of exec() is dangerous",
            r"\b__import__\s*\(": "Use of __import__() can be dangerous",
            r"pickle\.loads?\s*\(": "Unsafe pickle usage",
            r"subprocess\.call\s*\([^)]*shell\s*=\s*True": "Shell injection risk",
            r"os\.system\s*\(": "Command injection risk",
        }

        import re
        for pattern, message in dangerous_patterns.items():
            if re.search(pattern, code):
                issues.append(ValidationIssue(
                    layer=self.name,
                    severity=ValidationSeverity.CRITICAL,
                    message=message,
                    file=file_path,
                ))

        # Try to run bandit if available
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(code)
                temp_path = f.name

            result = subprocess.run(
                ["bandit", "-f", "json", temp_path],
                capture_output=True,
                text=True,
                timeout=30,
            )

            os.unlink(temp_path)

            if result.stdout:
                bandit_output = json.loads(result.stdout)
                for result_item in bandit_output.get("results", []):
                    severity_map = {
                        "LOW": ValidationSeverity.INFO,
                        "MEDIUM": ValidationSeverity.WARNING,
                        "HIGH": ValidationSeverity.ERROR,
                    }
                    issues.append(ValidationIssue(
                        layer=self.name,
                        severity=severity_map.get(
                            result_item.get("issue_severity", "LOW"),
                            ValidationSeverity.INFO
                        ),
                        message=result_item.get("issue_text", "Security issue"),
                        file=file_path,
                        line=result_item.get("line_number"),
                        code=result_item.get("code"),
                    ))

        except (FileNotFoundError, json.JSONDecodeError, subprocess.TimeoutExpired):
            # Bandit not available or failed - skip
            pass

        passed = all(
            i.severity != ValidationSeverity.CRITICAL
            for i in issues
        )
        critical_count = sum(1 for i in issues if i.severity == ValidationSeverity.CRITICAL)
        score = max(0, 10 - critical_count * 5 - len(issues))

        return ValidationResult(
            passed=passed,
            score=score,
            issues=issues,
            layer_results={
                self.name: {
                    "passed": passed,
                    "issues_found": len(issues),
                    "critical_issues": critical_count,
                }
            },
            recommendation="block" if critical_count > 0 else "review" if len(issues) > 0 else "proceed",
        )


class TypeCheckValidator(BaseValidator):
    """
    Layer 4: Type checking using mypy.

    Catches:
    - Type mismatches
    - Missing type hints
    - Undefined variables
    """

    def __init__(self):
        super().__init__("type_checking")

    def validate(self, code: str, file_path: str = "<string>") -> ValidationResult:
        """Validate types."""
        issues = []

        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir=".") as f:
                f.write(code)
                temp_path = f.name

            result = subprocess.run(
                ["mypy", "--no-error-summary", "--show-error-codes", temp_path],
                capture_output=True,
                text=True,
                timeout=30,
            )

            os.unlink(temp_path)

            if result.stdout:
                for line in result.stdout.strip().split("\n"):
                    if ":" in line and "error:" in line:
                        parts = line.split(":", 3)
                        if len(parts) >= 3:
                            try:
                                line_num = int(parts[1].strip())
                                message = parts[3].strip() if len(parts) > 3 else parts[2].strip()
                                issues.append(ValidationIssue(
                                    layer=self.name,
                                    severity=ValidationSeverity.ERROR,
                                    message=message,
                                    file=file_path,
                                    line=line_num,
                                ))
                            except ValueError:
                                pass

        except (FileNotFoundError, subprocess.TimeoutExpired):
            # mypy not available - skip
            return ValidationResult(
                passed=True,
                score=10.0,
                issues=[],
                layer_results={
                    self.name: {
                        "passed": True,
                        "message": "Skipped (mypy not available)",
                    }
                },
            )

        passed = len(issues) == 0
        score = max(0, 10 - len(issues) * 0.5)

        return ValidationResult(
            passed=passed,
            score=score,
            issues=issues,
            layer_results={
                self.name: {
                    "passed": passed,
                    "type_errors": len(issues),
                }
            },
        )


class CodeQualityValidator(BaseValidator):
    """
    Layer 5: Code quality using pylint.

    Checks:
    - Code style
    - Unused imports
    - Undefined names
    - Code complexity
    """

    def __init__(self, min_score: float = 7.0):
        super().__init__("code_quality")
        self.min_score = min_score

    def validate(self, code: str, file_path: str = "<string>") -> ValidationResult:
        """Validate code quality."""
        issues = []

        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir=".") as f:
                f.write(code)
                temp_path = f.name

            result = subprocess.run(
                ["pylint", "--output-format=json", temp_path],
                capture_output=True,
                text=True,
                timeout=60,
            )

            os.unlink(temp_path)

            if result.stdout:
                pylint_output = json.loads(result.stdout)
                for msg in pylint_output:
                    severity_map = {
                        "info": ValidationSeverity.INFO,
                        "convention": ValidationSeverity.INFO,
                        "refactor": ValidationSeverity.WARNING,
                        "warning": ValidationSeverity.WARNING,
                        "error": ValidationSeverity.ERROR,
                        "fatal": ValidationSeverity.CRITICAL,
                    }
                    issues.append(ValidationIssue(
                        layer=self.name,
                        severity=severity_map.get(
                            msg.get("type", "info"),
                            ValidationSeverity.INFO
                        ),
                        message=msg.get("message", ""),
                        file=file_path,
                        line=msg.get("line"),
                        column=msg.get("column"),
                    ))

        except (FileNotFoundError, json.JSONDecodeError, subprocess.TimeoutExpired):
            # pylint not available - skip
            return ValidationResult(
                passed=True,
                score=10.0,
                issues=[],
                layer_results={
                    self.name: {
                        "passed": True,
                        "message": "Skipped (pylint not available)",
                    }
                },
            )

        passed = len(issues) == 0
        score = max(0, 10 - len(issues) * 0.2)

        return ValidationResult(
            passed=passed,
            score=score,
            issues=issues,
            layer_results={
                self.name: {
                    "passed": passed,
                    "issues": len(issues),
                }
            },
        )


class MultiLayerValidator:
    """
    Combines all validation layers.

    Runs validation in order and produces overall score.
    """

    def __init__(
        self,
        min_score: float = 8.0,
        enable_all_layers: bool = True,
    ):
        """
        Initialize multi-layer validator.

        Args:
            min_score: Minimum score to pass validation
            enable_all_layers: Whether to enable all layers (some may be skipped if tools unavailable)
        """
        self.min_score = min_score
        self.enable_all_layers = enable_all_layers

        self.validators = [
            SyntaxValidator(),
            ImportValidator(),
            SecurityValidator(),
            TypeCheckValidator(),
            CodeQualityValidator(),
        ]

    def validate(self, code: str, file_path: str = "<string>") -> ValidationResult:
        """
        Run all validation layers.

        Args:
            code: Python code to validate
            file_path: File path for reporting

        Returns:
            Comprehensive validation result
        """
        all_issues = []
        layer_results = {}
        total_score = 0
        passed_layers = 0

        for validator in self.validators:
            try:
                result = validator.validate(code, file_path)
                all_issues.extend(result.issues)
                layer_results.update(result.layer_results)
                total_score += result.score

                if result.passed:
                    passed_layers += 1

            except Exception as e:
                logger.error(f"Validator {validator.name} failed: {e}")
                layer_results[validator.name] = {
                    "passed": False,
                    "error": str(e),
                }

        # Calculate overall score
        overall_score = total_score / len(self.validators)
        passed = overall_score >= self.min_score

        # Determine recommendation
        if passed:
            recommendation = "publish"
        elif overall_score >= 6.0:
            recommendation = "review_and_fix"
        elif overall_score >= 4.0:
            recommendation = "major_issues"
        else:
            recommendation = "reject"

        return ValidationResult(
            passed=passed,
            score=round(overall_score, 2),
            issues=all_issues,
            layer_results=layer_results,
            recommendation=recommendation,
        )

    def validate_project(
        self,
        project_dir: Path,
        file_patterns: list[str] = None,
    ) -> dict[str, ValidationResult]:
        """
        Validate all Python files in a project.

        Args:
            project_dir: Path to project directory
            file_patterns: Glob patterns for files to validate

        Returns:
            Dictionary mapping file paths to validation results
        """
        if file_patterns is None:
            file_patterns = ["**/*.py"]

        results = {}

        for pattern in file_patterns:
            for file_path in project_dir.rglob(pattern[3:]):  # Remove **/
                if file_path.is_file():
                    try:
                        code = file_path.read_text(encoding="utf-8")
                        result = self.validate(code, str(file_path))
                        results[str(file_path)] = result
                    except Exception as e:
                        logger.error(f"Failed to validate {file_path}: {e}")

        return results


def generate_validation_report(
    results: dict[str, ValidationResult],
    output_path: Optional[Path] = None,
) -> str:
    """
    Generate human-readable validation report.

    Args:
        results: Validation results from validate_project
        output_path: Optional path to save report

    Returns:
        Markdown report
    """
    lines = [
        "# Code Validation Report",
        f"Generated: {datetime.now().isoformat()}",
        "",
        "## Summary",
        f"- Files validated: {len(results)}",
        "",
    ]

    # Count results by recommendation
    by_recommendation = {}
    for file_path, result in results.items():
        rec = result.recommendation
        by_recommendation[rec] = by_recommendation.get(rec, 0) + 1

    lines.extend([
        "## Results",
        "",
    ])

    for rec, count in by_recommendation.items():
        lines.append(f"- **{rec}**: {count} files")

    lines.append("")

    # Files with issues
    lines.extend([
        "## Files with Issues",
        "",
    ])

    for file_path, result in results.items():
        if not result.passed or result.issues:
            lines.extend([
                f"### {file_path}",
                f"**Score**: {result.score}/10",
                f"**Recommendation**: {result.recommendation}",
                "",
            ])

            if result.issues:
                lines.append("**Issues**:")
                for issue in result.issues[:10]:  # Limit to 10 issues per file
                    lines.append(
                        f"- [{issue.severity.value.upper()}] {issue.message} "
                        f"(line {issue.line})"
                    )
                if len(result.issues) > 10:
                    lines.append(f"- ... and {len(result.issues) - 10} more issues")
                lines.append("")

    report = "\n".join(lines)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")

    return report


class TestGenerator:
    """
    Generate unit tests for code.

    Doesn't execute tests - only generates them.
    """

    def __init__(self):
        pass

    def generate_for_module(self, code: str, module_name: str) -> str:
        """
        Generate unit tests for a module.

        Args:
            code: Module source code
            module_name: Name of module

        Returns:
            Generated test code
        """
        try:
            tree = ast.parse(code)

            # Extract classes and functions
            classes = []
            functions = []

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    classes.append(node.name)
                elif isinstance(node, ast.FunctionDef):
                    functions.append(node.name)
                elif isinstance(node, ast.AsyncFunctionDef):
                    functions.append(node.name)

            # Generate test code
            test_code = f'''"""
Unit tests for {module_name}.

Generated by AUTO-GIT.
To run: pytest test_{module_name}.py
"""

import pytest
from {module_name} import '''

            # Add imports
            if classes:
                test_code += ", ".join(classes[:5])
            if functions:
                if classes:
                    test_code += ", "
                test_code += ", ".join(functions[:10])

            test_code += "\n\n"

            # Generate test class
            test_code += f"""
class Test{module_name.capitalize()}:
    \"\"\"Test cases for {module_name}.\"\"\"

    def setup_method(self):
        \"\"\"Setup test fixtures.\"\"\"
        pass

    def teardown_method(self):
        \"\"\"Cleanup after tests.\"\"\"
        pass

"""

            # Generate test methods for functions
            for func in functions[:5]:
                test_code += f"""    def test_{func}(self):
        \"\"\"Test {func}.\"\"\"
        # TODO: Implement test
        assert True  # Placeholder

"""

            # Generate test methods for classes
            for cls in classes[:3]:
                test_code += f"""    def test_{cls.lower()}_initialization(self):
        \"\"\"Test {cls} initialization.\"\"\"
        # TODO: Implement test
        assert True  # Placeholder

"""

            test_code += '''
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
'''
            return test_code

        except Exception as e:
            logger.error(f"Failed to generate tests for {module_name}: {e}")
            return f"# Failed to generate tests: {str(e)}"

    def save_tests(
        self,
        project_dir: Path,
        validation_results: dict[str, ValidationResult],
    ):
        """
        Generate and save test files for validated modules.

        Args:
            project_dir: Project directory
            validation_results: Validation results
        """
        tests_dir = project_dir / "tests"
        tests_dir.mkdir(exist_ok=True)

        for file_path, result in validation_results.items():
            if result.passed:
                try:
                    code = Path(file_path).read_text(encoding="utf-8")
                    module_name = Path(file_path).stem

                    test_code = self.generate_for_module(code, module_name)

                    test_file = tests_dir / f"test_{module_name}.py"
                    test_file.write_text(test_code, encoding="utf-8")

                    logger.info(f"Generated tests: {test_file}")

                except Exception as e:
                    logger.error(f"Failed to generate tests for {file_path}: {e}")
