"""
Prompt templates for fixing code errors using LLM.
"""

from typing import List, Dict, Any


# ============================================================================
# ERROR-SPECIFIC FIX PROMPTS
# ============================================================================

SYNTAX_FIX_PROMPT = """You are a Python syntax expert. Fix this syntax error:

ERROR: {error_message} at line {line_number}

CODE:
```python
{code}
```

CONTEXT (lines around the error):
```python
{context}
```

Analyze the syntax error and provide the complete fixed code.
Make minimal changes to fix only the syntax error.
Output only the fixed code, no explanation.
"""

IMPORT_FIX_PROMPT = """You are a Python import expert. Fix this import error:

ERROR: {error_message}

PROBLEMATIC IMPORT:
```python
{import_statement}
```

AVAILABLE FILES:
{available_files}

FULL CODE:
```python
{code}
```

The import is trying to import a module that doesn't exist or has wrong name.
Choose the correct file from the available files or fix the import statement.

Provide the complete fixed code with the corrected import.
Output only the fixed code, no explanation.
"""

CONFIG_FIX_PROMPT = """You are a Python configuration expert. Fix this config key error:

ERROR: Key "{key}" not found in config

AVAILABLE CONFIG KEYS:
{available_keys}

CODE ACCESSING THE KEY:
```python
{code_snippet}
```

FULL CODE:
```python
{code}
```

Either:
1. Add the missing key to config with appropriate value
2. Fix the code to use the correct existing key

Provide the complete fixed code.
Output only the fixed code, no explanation.
"""

SHAPE_FIX_PROMPT = """You are a PyTorch tensor shape expert. Fix this shape mismatch:

ERROR: {error_message}

INPUT SHAPE: {input_shape}
LAYER EXPECTING: {expected_shape}
ACTUAL RECEIVED: {actual_shape}

CODE:
```python
{code}
```

The issue is a tensor shape mismatch in the neural network forward pass.
Common fixes:
1. Calculate correct input size for Linear layer based on conv output
2. Add AdaptiveAvgPool2d before flatten to get fixed size
3. Fix the Linear layer input dimension
4. Adjust view/reshape operations

Provide the complete fixed code with corrected tensor dimensions.
Output only the fixed code, no explanation.
"""

RUNTIME_FIX_PROMPT = """You are a Python debugging expert. Fix this runtime error:

ERROR: {error_message}

TRACEBACK:
```
{traceback}
```

CODE:
```python
{code}
```

Analyze the error and provide the complete fixed code.
Address the specific issue mentioned in the error message.

Provide the complete fixed code.
Output only the fixed code, no explanation.
"""

MULTI_ERROR_FIX_PROMPT = """You are a Python code expert. Fix these errors in the code:

ERRORS:
{error_list}

CODE:
```python
{code}
```

Fix all the errors listed above. Make minimal necessary changes.
Ensure the code is syntactically correct and will run without errors.

Provide the complete fixed code.
Output only the fixed code, no explanation.
"""


# ============================================================================
# ERROR FORMATTING
# ============================================================================

def format_errors_for_llm(errors: List[Dict[str, Any]], code: str) -> str:
    """Format errors for LLM consumption.

    Args:
        errors: List of error dictionaries
        code: The source code

    Returns:
        Formatted error string for LLM prompt
    """
    lines = []
    for i, error in enumerate(errors, 1):
        lines.append(f"{i}. [{error.get('type', 'UNKNOWN')}] {error.get('file', 'unknown')}:{error.get('line', 0)}")
        lines.append(f"   {error.get('message', 'No message')}")
        if error.get('suggestion'):
            lines.append(f"   Suggestion: {error['suggestion']}")
        lines.append("")

    return "\n".join(lines)


def format_code_context(code: str, line_number: int, context_lines: int = 3) -> str:
    """Extract context lines around an error.

    Args:
        code: The source code
        line_number: Line number of error (1-indexed)
        context_lines: Number of lines before/after to include

    Returns:
        Code snippet with context
    """
    lines = code.split('\n')
    start = max(0, line_number - context_lines - 1)
    end = min(len(lines), line_number + context_lines)

    context = []
    for i in range(start, end):
        prefix = ">>> " if i == line_number - 1 else "    "
        context.append(f"{prefix}{i+1:4d}: {lines[i]}")

    return "\n".join(context)


def format_available_files(files: List[str]) -> str:
    """Format list of available files for LLM.

    Args:
        files: List of file names

    Returns:
        Formatted file list
    """
    if not files:
        return "No files available"

    return "\n".join(f"  - {f}" for f in sorted(files))


def format_available_keys(keys: List[str]) -> str:
    """Format list of available config keys for LLM.

    Args:
        keys: List of config keys

    Returns:
        Formatted key list
    """
    if not keys:
        return "No keys available"

    return "\n".join(f"  - {k}" for k in sorted(keys))


# ============================================================================
# PROMPT BUILDER
# ============================================================================

class FixPromptBuilder:
    """Build appropriate fix prompts based on error type."""

    @staticmethod
    def build_syntax_fix(code: str, error: Dict[str, Any]) -> str:
        """Build prompt for syntax error fix."""
        return SYNTAX_FIX_PROMPT.format(
            error_message=error.get('message', 'Unknown syntax error'),
            line_number=error.get('line', 0),
            code=code,
            context=format_code_context(code, error.get('line', 0))
        )

    @staticmethod
    def build_import_fix(code: str, error: Dict[str, Any], available_files: List[str]) -> str:
        """Build prompt for import error fix."""
        import_stmt = error.get('context', error.get('message', ''))

        return IMPORT_FIX_PROMPT.format(
            error_message=error.get('message', 'Unknown import error'),
            import_statement=import_stmt,
            available_files=format_available_files(available_files),
            code=code
        )

    @staticmethod
    def build_config_fix(code: str, error: Dict[str, Any], available_keys: List[str]) -> str:
        """Build prompt for config error fix."""
        return CONFIG_FIX_PROMPT.format(
            key=error.get('missing_key', 'unknown'),
            available_keys=format_available_keys(available_keys),
            code_snippet=error.get('context', ''),
            code=code
        )

    @staticmethod
    def build_shape_fix(code: str, error: Dict[str, Any]) -> str:
        """Build prompt for shape error fix."""
        return SHAPE_FIX_PROMPT.format(
            error_message=error.get('message', 'Shape mismatch'),
            input_shape=error.get('input_shape', 'unknown'),
            expected_shape=error.get('expected_shape', 'unknown'),
            actual_shape=error.get('actual_shape', 'unknown'),
            code=code
        )

    @staticmethod
    def build_runtime_fix(code: str, error: Dict[str, Any]) -> str:
        """Build prompt for runtime error fix."""
        return RUNTIME_FIX_PROMPT.format(
            error_message=error.get('message', 'Runtime error'),
            traceback=error.get('traceback', 'No traceback available'),
            code=code
        )

    @staticmethod
    def build_multi_error_fix(code: str, errors: List[Dict[str, Any]]) -> str:
        """Build prompt for fixing multiple errors."""
        return MULTI_ERROR_FIX_PROMPT.format(
            error_list=format_errors_for_llm(errors, code),
            code=code
        )

    @classmethod
    def build_fix_prompt(
        cls,
        code: str,
        errors: List[Dict[str, Any]],
        available_files: List[str] = None,
        available_keys: List[str] = None
    ) -> str:
        """Build appropriate fix prompt based on error type(s).

        Args:
            code: The source code to fix
            errors: List of errors found
            available_files: List of available file names (for import fixes)
            available_keys: List of available config keys (for config fixes)

        Returns:
            Prompt string for LLM
        """
        if not errors:
            return code  # No errors, return as-is

        # Single error - use specific prompt
        if len(errors) == 1:
            error = errors[0]
            error_type = error.get('type', 'UNKNOWN')

            if error_type == 'SYNTAX':
                return cls.build_syntax_fix(code, error)
            elif error_type == 'IMPORT':
                return cls.build_import_fix(code, error, available_files or [])
            elif error_type == 'CONFIG':
                return cls.build_config_fix(code, error, available_keys or [])
            elif error_type == 'SHAPE':
                return cls.build_shape_fix(code, error)
            elif error_type == 'RUNTIME':
                return cls.build_runtime_fix(code, error)

        # Multiple errors - use multi-error prompt
        return cls.build_multi_error_fix(code, errors)
