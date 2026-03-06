"""
Traceback Parser — Extract structured error info from Python tracebacks.

Takes raw stderr/error text and extracts:
  - File, line number, function name
  - Error type and message
  - The offending source line
  - ±N lines of context around the error

This lets the fix-loop LLM see EXACTLY where the error is instead of
scanning the entire file, reducing fix time and improving accuracy.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("traceback_parser")


@dataclass
class ParsedError:
    """A single structured error extracted from a traceback."""
    error_type: str                # e.g. "AttributeError"
    error_message: str             # e.g. "'NoneType' object has no attribute 'split'"
    file: str = ""                 # e.g. "main.py"
    line: int = 0                  # e.g. 42
    function: str = ""             # e.g. "process_data"
    source_line: str = ""          # e.g. "    result = data.split(',')"
    context_before: List[str] = field(default_factory=list)  # lines before error
    context_after: List[str] = field(default_factory=list)   # lines after error

    def format_for_llm(self, code_content: str = "", context_lines: int = 10) -> str:
        """Format this error for injection into an LLM fix prompt.
        
        If code_content is provided, extracts ±context_lines around the error line.
        """
        parts = [f"ERROR: {self.error_type}: {self.error_message}"]
        if self.file:
            parts.append(f"  File: {self.file}")
        if self.line:
            parts.append(f"  Line: {self.line}")
        if self.function:
            parts.append(f"  Function: {self.function}()")
        if self.source_line:
            parts.append(f"  Code: {self.source_line.strip()}")
        
        # Add code context around the error line
        if code_content and self.line > 0:
            lines = code_content.splitlines()
            start = max(0, self.line - context_lines - 1)
            end = min(len(lines), self.line + context_lines)
            
            parts.append(f"\n  Code context ({self.file} lines {start+1}-{end}):")
            for i in range(start, end):
                marker = " >>>" if i == self.line - 1 else "    "
                parts.append(f"  {marker} {i+1:4d} | {lines[i]}")
        
        return "\n".join(parts)

    def signature(self) -> str:
        """A normalized signature for pattern matching.
        
        Used to match against the ErrorPatternDB for instant auto-fixes.
        """
        # Normalize: strip specifics, keep error type + pattern
        msg = self.error_message.lower()
        # Remove specific names but keep the pattern
        msg = re.sub(r"'[^']*'", "'X'", msg)
        msg = re.sub(r"\"[^\"]*\"", "'X'", msg)
        msg = re.sub(r"\d+", "N", msg)
        return f"{self.error_type}::{msg}"


def parse_python_traceback(error_text: str) -> List[ParsedError]:
    """Parse Python traceback text into structured ParsedError objects.
    
    Handles:
      - Standard Python tracebacks (Traceback (most recent call last):)
      - SyntaxError with caret indicators
      - Multiple tracebacks in one output
      - Runtime errors without full tracebacks
      - ModuleNotFoundError / ImportError
    
    Args:
        error_text: Raw stderr or error string from code execution
        
    Returns:
        List of ParsedError objects, most recent error first
    """
    if not error_text or not error_text.strip():
        return []
    
    errors: List[ParsedError] = []
    
    # Pattern: File "path/to/file.py", line 42, in function_name
    frame_pattern = re.compile(
        r'File\s+"([^"]+)",\s+line\s+(\d+)(?:,\s+in\s+(\S+))?'
    )
    
    # Pattern: ErrorType: message
    error_line_pattern = re.compile(
        r'^(\w+(?:Error|Exception|Warning|Interrupt))\s*:\s*(.+)$',
        re.MULTILINE
    )
    
    # Pattern: SyntaxError with caret
    syntax_error_pattern = re.compile(
        r'File\s+"([^"]+)",\s+line\s+(\d+)\n\s+(.+)\n\s+\^+\n'
        r'SyntaxError:\s*(.+)',
        re.MULTILINE
    )
    
    # Pattern: ModuleNotFoundError: No module named 'xxx'
    module_error_pattern = re.compile(
        r"(?:ModuleNotFoundError|ImportError):\s*No module named\s+['\"]([^'\"]+)['\"]"
    )
    
    # Split into individual tracebacks
    traceback_blocks = re.split(r'(?=Traceback \(most recent call last\):)', error_text)
    
    for block in traceback_blocks:
        block = block.strip()
        if not block:
            continue
        
        # Find the final error line
        error_matches = list(error_line_pattern.finditer(block))
        if not error_matches:
            # Try to find any "Error:" pattern
            simple_error = re.search(r'(\w+Error):\s*(.+)', block)
            if simple_error:
                errors.append(ParsedError(
                    error_type=simple_error.group(1),
                    error_message=simple_error.group(2).strip(),
                ))
            continue
        
        # Use the LAST error match (most recent in the traceback)
        error_match = error_matches[-1]
        error_type = error_match.group(1)
        error_message = error_match.group(2).strip()
        
        # Find all frame references
        frames = list(frame_pattern.finditer(block))
        
        # Use the LAST frame (closest to the error)
        file_name = ""
        line_num = 0
        func_name = ""
        source_line = ""
        
        if frames:
            last_frame = frames[-1]
            file_name = last_frame.group(1)
            # Extract just the filename, not the full path
            if '/' in file_name or '\\' in file_name:
                file_name = file_name.replace('\\', '/').split('/')[-1]
            line_num = int(last_frame.group(2))
            func_name = last_frame.group(3) or ""
            
            # Try to get the source line (it's usually the line after the File reference)
            frame_end = last_frame.end()
            remaining = block[frame_end:].lstrip('\n')
            if remaining:
                first_line = remaining.split('\n')[0].strip()
                # Don't capture the error line itself as source
                if not re.match(r'^\w+(?:Error|Exception)', first_line):
                    source_line = first_line
        
        errors.append(ParsedError(
            error_type=error_type,
            error_message=error_message,
            file=file_name,
            line=line_num,
            function=func_name,
            source_line=source_line,
        ))
    
    # Also catch standalone module errors not in a traceback block
    for m in module_error_pattern.finditer(error_text):
        module_name = m.group(1)
        # Check if we already have this error
        already = any(
            e.error_type in ("ModuleNotFoundError", "ImportError") and module_name in e.error_message
            for e in errors
        )
        if not already:
            errors.append(ParsedError(
                error_type="ModuleNotFoundError",
                error_message=f"No module named '{module_name}'",
            ))
    
    return errors


def build_smart_fix_context(
    errors: List[ParsedError],
    file_contents: Dict[str, str],
    context_lines: int = 10,
) -> Dict[str, str]:
    """Build per-file error context with code snippets for the fix LLM.
    
    Groups errors by file, and for each file returns a focused error summary
    with code context around each error line.
    
    Args:
        errors: Parsed errors from parse_python_traceback()
        file_contents: Dict of {filename: code_content}
        context_lines: Number of lines of context around each error
        
    Returns:
        Dict of {filename: formatted_error_context}
    """
    per_file: Dict[str, List[ParsedError]] = {}
    unlocated: List[ParsedError] = []
    
    for err in errors:
        if err.file and err.file in file_contents:
            per_file.setdefault(err.file, []).append(err)
        elif err.file:
            # Try fuzzy match (error might have full path, we have just filename)
            matched = False
            for fname in file_contents:
                if fname in err.file or err.file in fname:
                    per_file.setdefault(fname, []).append(err)
                    matched = True
                    break
            if not matched:
                unlocated.append(err)
        else:
            unlocated.append(err)
    
    result: Dict[str, str] = {}
    
    for fname, file_errors in per_file.items():
        code = file_contents.get(fname, "")
        parts = [f"ERRORS IN {fname} ({len(file_errors)} error(s)):"]
        
        for i, err in enumerate(file_errors, 1):
            parts.append(f"\n--- Error {i} ---")
            parts.append(err.format_for_llm(code, context_lines))
        
        result[fname] = "\n".join(parts)
    
    # Add unlocated errors to all Python files as general context
    if unlocated:
        unlocated_text = "\n\nGENERAL ERRORS (could not locate source file):\n"
        for err in unlocated:
            unlocated_text += f"  - {err.error_type}: {err.error_message}\n"
        for fname in result:
            result[fname] += unlocated_text
    
    return result


def extract_error_signatures(errors: List[ParsedError]) -> List[str]:
    """Extract normalized error signatures for pattern matching.
    
    Used to look up instant auto-fixes from the ErrorPatternDB.
    """
    return [err.signature() for err in errors]
