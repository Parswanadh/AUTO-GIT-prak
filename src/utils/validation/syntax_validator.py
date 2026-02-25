"""
Syntax validator using Python's AST module.

Checks Python code for syntax errors by attempting to parse it.
"""

import ast
from typing import Optional

from ..validation.error_types import ValidationResult, CodeError, ErrorType


class SyntaxValidator:
    """Validates Python syntax using AST parsing."""

    def __init__(self):
        """Initialize the syntax validator."""
        self.name = "SyntaxValidator"

    def validate(self, code: str, file_name: str = "") -> ValidationResult:
        """Validate Python code for syntax errors.

        Args:
            code: Python source code to validate
            file_name: Optional file name for error reporting

        Returns:
            ValidationResult with syntax errors if any
        """
        errors = []
        warnings = []

        # Skip non-Python files
        if file_name and not file_name.endswith('.py'):
            return ValidationResult(
                is_valid=True,
                errors=[],
                warnings=["Skipped syntax validation (not a Python file)"],
                file_name=file_name
            )

        try:
            # Try to parse the code
            ast.parse(code)

        except SyntaxError as e:
            # Create a CodeError for the syntax error
            context = self._extract_context(code, e.lineno or 0)

            error = CodeError(
                type=ErrorType.SYNTAX,
                file=file_name,
                line=e.lineno or 0,
                column=e.offset or 0,
                message=e.msg or "Syntax error",
                context=context,
                fixable=True,  # Most syntax errors are fixable
                suggestion=self._get_suggestion(e.msg, e.text)
            )
            errors.append(error)

        except Exception as e:
            # Unexpected error during parsing
            errors.append(CodeError(
                type=ErrorType.SYNTAX,
                file=file_name,
                line=0,
                message=f"Unexpected parsing error: {str(e)}",
                fixable=True
            ))

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            file_name=file_name
        )

    def _extract_context(self, code: str, line_number: int, context_lines: int = 3) -> str:
        """Extract context lines around an error.

        Args:
            code: The source code
            line_number: Line number of error (1-indexed)
            context_lines: Number of lines before/after to include

        Returns:
            Code snippet with context
        """
        lines = code.split('\n')
        if not lines:
            return ""

        start = max(0, line_number - context_lines - 1)
        end = min(len(lines), line_number + context_lines)

        context = []
        for i in range(start, end):
            marker = " >>> " if i == line_number - 1 else "     "
            line_text = lines[i] if i < len(lines) else ""
            context.append(f"{marker}{i+1:4d}: {line_text}")

        return "\n".join(context)

    def _get_suggestion(self, error_msg: str, error_line: Optional[str]) -> Optional[str]:
        """Get a suggestion for fixing common syntax errors.

        Args:
            error_msg: The syntax error message
            error_line: The line of code with the error

        Returns:
            Suggestion string or None
        """
        error_msg_lower = error_msg.lower()

        # Common syntax errors and their fixes
        suggestions = {
            "invalid syntax": "Check for missing colons, parentheses, or operators",
            "unexpected eof": "Check for missing closing parentheses, brackets, or quotes",
            "unterminated string literal": "Check for missing closing quote",
            "unterminated triple-quoted string": "Check for missing closing triple quotes",
            "unexpected indent": "Check indentation consistency (use 4 spaces, not tabs)",
            "unindent does not match": "Check indentation levels match",
            "invalid character": "Check for non-ASCII characters or incorrect quotes",
        }

        for key, suggestion in suggestions.items():
            if key in error_msg_lower:
                return suggestion

        # Check for specific patterns
        if error_line:
            if ":" in error_line and "def " not in error_line and "class " not in error_line:
                if not error_line.strip().endswith(":"):
                    return "Missing colon at end of statement"

            if "=" in error_line and "==" not in error_line:
                if " if " in error_line or " while " in error_line or " for " in error_line:
                    return "Use == for comparison, not ="

        return None


# Convenience function
def validate_syntax(code: str, file_name: str = "") -> ValidationResult:
    """Convenience function to validate Python syntax.

    Args:
        code: Python source code to validate
        file_name: Optional file name for error reporting

    Returns:
        ValidationResult with syntax errors if any
    """
    validator = SyntaxValidator()
    return validator.validate(code, file_name)
