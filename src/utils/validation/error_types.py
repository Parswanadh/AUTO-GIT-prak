"""
Error types and validation result classes for the AUTO-GIT validation system.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime


class ErrorType(Enum):
    """Types of errors that can be detected during validation."""
    SYNTAX = "SYNTAX"        # Python syntax errors
    IMPORT = "IMPORT"        # Module/file not found
    CONFIG = "CONFIG"        # Missing config keys
    SHAPE = "SHAPE"          # Tensor shape mismatches
    RUNTIME = "RUNTIME"      # Execution errors
    TYPE = "TYPE"           # Type errors
    STYLE = "STYLE"         # Code style (warnings only)


@dataclass
class CodeError:
    """Represents a single code error found during validation."""
    type: ErrorType
    file: str
    line: int
    column: int = 0
    message: str = ""
    context: str = ""  # Code snippet around error
    suggestion: Optional[str] = None  # Suggested fix
    fixable: bool = True  # Whether LLM can likely fix this

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "type": self.type.value,
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "message": self.message,
            "context": self.context[:100] if self.context else "",  # Truncate for display
            "suggestion": self.suggestion,
            "fixable": self.fixable
        }

    def __str__(self) -> str:
        """Human-readable error message."""
        location = f"{self.file}:{self.line}"
        if self.column:
            location += f":{self.column}"
        return f"[{self.type.value}] {location} - {self.message}"


@dataclass
class ValidationResult:
    """Result of validating a single file or code snippet."""
    is_valid: bool
    errors: List[CodeError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    file_name: str = ""

    @property
    def critical_errors(self) -> List[CodeError]:
        """Get only critical errors (syntax, import, runtime)."""
        return [e for e in self.errors if e.type in {
            ErrorType.SYNTAX, ErrorType.IMPORT, ErrorType.RUNTIME
        }]

    @property
    def fixable_errors(self) -> List[CodeError]:
        """Get only fixable errors."""
        return [e for e in self.errors if e.fixable]

    def merge(self, other: 'ValidationResult') -> 'ValidationResult':
        """Merge two validation results."""
        return ValidationResult(
            is_valid=self.is_valid and other.is_valid,
            errors=self.errors + other.errors,
            warnings=self.warnings + other.warnings,
            file_name=self.file_name or other.file_name
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "is_valid": self.is_valid,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "errors": [e.to_dict() for e in self.errors],
            "warnings": self.warnings
        }


@dataclass
class ExecutionResult:
    """Result of executing code in a sandbox."""
    success: bool
    output: str = ""
    error: str = ""
    timeout: bool = False
    duration: float = 0.0  # seconds

    @property
    def has_syntax_error(self) -> bool:
        """Check if error is a syntax error."""
        return "SyntaxError" in self.error

    @property
    def has_import_error(self) -> bool:
        """Check if error is an import error."""
        return any(x in self.error for x in ["ModuleNotFoundError", "ImportError"])

    @property
    def has_runtime_error(self) -> bool:
        """Check if error is a runtime error."""
        return bool(self.error) and not self.has_syntax_error and not self.has_import_error


@dataclass
class ValidationReport:
    """Complete report from validating all generated code."""
    total_files: int = 0
    files_checked: List[str] = field(default_factory=list)
    errors_by_file: Dict[str, List[CodeError]] = field(default_factory=dict)
    warnings_by_file: Dict[str, List[str]] = field(default_factory=dict)
    fix_attempts: int = 0
    final_status: str = "UNKNOWN"  # PASS, PARTIAL, FAIL
    timestamp: str = ""
    execution_results: Dict[str, ExecutionResult] = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    @property
    def total_errors(self) -> int:
        """Total number of errors across all files."""
        return sum(len(errors) for errors in self.errors_by_file.values())

    @property
    def total_warnings(self) -> int:
        """Total number of warnings across all files."""
        return sum(len(warnings) for warnings in self.warnings_by_file.values())

    @property
    def files_with_errors(self) -> List[str]:
        """Files that have errors."""
        return [f for f, errors in self.errors_by_file.items() if errors]

    @property
    def critical_errors(self) -> List[CodeError]:
        """All critical errors across all files."""
        critical = []
        for errors in self.errors_by_file.values():
            critical.extend([e for e in errors if e.type in {
                ErrorType.SYNTAX, ErrorType.IMPORT, ErrorType.RUNTIME
            }])
        return critical

    def add_file_result(self, file_name: str, result: ValidationResult) -> None:
        """Add validation result for a file."""
        if file_name not in self.files_checked:
            self.files_checked.append(file_name)
            self.total_files += 1

        if result.errors:
            self.errors_by_file[file_name] = result.errors

        if result.warnings:
            self.warnings_by_file[file_name] = result.warnings

    def set_execution_result(self, file_name: str, result: ExecutionResult) -> None:
        """Set execution result for a file."""
        self.execution_results[file_name] = result

    def determine_status(self) -> str:
        """Determine final status based on results."""
        if self.total_errors == 0:
            return "PASS"
        elif len(self.critical_errors) == 0:
            return "PARTIAL"  # Only warnings or non-critical errors
        else:
            return "FAIL"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_files": self.total_files,
            "files_checked": self.files_checked,
            "total_errors": self.total_errors,
            "total_warnings": self.total_warnings,
            "files_with_errors": self.files_with_errors,
            "errors_by_file": {
                f: [e.to_dict() for e in errors]
                for f, errors in self.errors_by_file.items()
            },
            "warnings_by_file": self.warnings_by_file,
            "fix_attempts": self.fix_attempts,
            "final_status": self.final_status,
            "timestamp": self.timestamp
        }

    def get_summary(self) -> str:
        """Get a human-readable summary."""
        lines = [
            f"Validation Report - {self.timestamp}",
            "=" * 60,
            f"Files Checked: {self.total_files}",
            f"Total Errors: {self.total_errors}",
            f"Total Warnings: {self.total_warnings}",
            f"Fix Attempts: {self.fix_attempts}",
            f"Final Status: {self.final_status}",
        ]
        if self.files_with_errors:
            lines.append("\nFiles with Errors:")
            for f in self.files_with_errors:
                lines.append(f"  - {f}: {len(self.errors_by_file[f])} errors")
        return "\n".join(lines)
