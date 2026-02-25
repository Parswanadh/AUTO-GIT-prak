"""
AUTO-GIT Code Validation System

A comprehensive validation system for generated code with automatic error fixing.
"""

from .error_types import (
    ErrorType,
    CodeError,
    ValidationResult,
    ExecutionResult,
    ValidationReport
)

__all__ = [
    "ErrorType",
    "CodeError",
    "ValidationResult",
    "ExecutionResult",
    "ValidationReport",
]
