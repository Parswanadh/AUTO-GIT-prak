"""
AUTO-GIT Validation Prompts

Prompt templates for LLM-based code error fixing.
"""

from .validation_prompts import (
    SYNTAX_FIX_PROMPT,
    IMPORT_FIX_PROMPT,
    CONFIG_FIX_PROMPT,
    SHAPE_FIX_PROMPT,
    RUNTIME_FIX_PROMPT,
    MULTI_ERROR_FIX_PROMPT,
    format_errors_for_llm,
    format_code_context,
    format_available_files,
    format_available_keys,
    FixPromptBuilder
)

__all__ = [
    "SYNTAX_FIX_PROMPT",
    "IMPORT_FIX_PROMPT",
    "CONFIG_FIX_PROMPT",
    "SHAPE_FIX_PROMPT",
    "RUNTIME_FIX_PROMPT",
    "MULTI_ERROR_FIX_PROMPT",
    "format_errors_for_llm",
    "format_code_context",
    "format_available_files",
    "format_available_keys",
    "FixPromptBuilder",
]
