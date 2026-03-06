"""
Error Pattern Auto-Fix Database — Instant fixes for common code generation errors.

Instead of wasting an LLM call on errors we've seen hundreds of times,
this module provides DETERMINISTIC regex-based fixes for the most common
patterns. Falls back to the LLM only for unknown/complex errors.

Architecture:
  1. Each pattern has: signature regex, description, auto-fix function
  2. On error, we match against all patterns
  3. If matched: apply fix directly (no LLM call needed)
  4. If not: fall through to LLM fix loop

Expected impact: ~40% of recurring errors fixed instantly (0 latency).
"""

from __future__ import annotations

import re
import ast
import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("error_pattern_db")


@dataclass
class ErrorPattern:
    """A single auto-fixable error pattern."""
    name: str                          # Human-readable name
    signature_regex: str               # Regex to match against error signature
    description: str                   # What this pattern catches
    fix_fn: Callable[[str, str, re.Match], Optional[str]]  # (code, error_msg, match) → fixed_code or None
    priority: int = 50                 # Higher = tried first (0-100)
    success_count: int = 0             # How many times this pattern was applied
    failure_count: int = 0             # How many times fix_fn returned None


class ErrorPatternDB:
    """Database of auto-fixable error patterns with deterministic fixes."""
    
    def __init__(self):
        self.patterns: List[ErrorPattern] = []
        self._register_builtin_patterns()
    
    def _register_builtin_patterns(self):
        """Register all built-in error patterns."""
        
        # ── Pattern 1: Missing self parameter ────────────────────────────
        self.register(ErrorPattern(
            name="missing_self",
            signature_regex=r"TypeError::.*takes N positional argument.*but N .*given",
            description="Method missing 'self' parameter",
            fix_fn=self._fix_missing_self,
            priority=90,
        ))
        
        # ── Pattern 2: Missing __init__ in class ─────────────────────────
        self.register(ErrorPattern(
            name="missing_init",
            signature_regex=r"TypeError::.*__init__.*takes.*argument",
            description="Class __init__ has wrong number of parameters",
            fix_fn=self._fix_init_args,
            priority=85,
        ))
        
        # ── Pattern 3: Undefined variable / NameError ────────────────────
        self.register(ErrorPattern(
            name="undefined_name",
            signature_regex=r"NameError::name 'X' is not defined",
            description="Variable used before definition",
            fix_fn=self._fix_name_error,
            priority=80,
        ))
        
        # ── Pattern 4: Import from wrong module ──────────────────────────
        self.register(ErrorPattern(
            name="import_from_wrong_module",
            signature_regex=r"ImportError::cannot import name 'X' from 'X'",
            description="Importing a name that doesn't exist in the target module",
            fix_fn=self._fix_import_name,
            priority=85,
        ))
        
        # ── Pattern 5: ModuleNotFoundError for local file ────────────────
        self.register(ErrorPattern(
            name="local_module_not_found",
            signature_regex=r"ModuleNotFoundError::No module named 'X'",
            description="Import of a local module that doesn't exist",
            fix_fn=self._fix_module_not_found,
            priority=75,
        ))
        
        # ── Pattern 6: Missing f-string prefix ──────────────────────────
        self.register(ErrorPattern(
            name="missing_fstring",
            signature_regex=r"SyntaxError::.*",
            description="String with {var} but missing f prefix",
            fix_fn=self._fix_missing_fstring,
            priority=70,
        ))
        
        # ── Pattern 7: Relative import in flat project ───────────────────
        self.register(ErrorPattern(
            name="relative_import",
            signature_regex=r"ImportError::attempted relative import",
            description="Relative import in a non-package project",
            fix_fn=self._fix_relative_import,
            priority=95,
        ))
        
        # ── Pattern 8: Missing return statement ──────────────────────────
        self.register(ErrorPattern(
            name="none_attribute",
            signature_regex=r"AttributeError::'X' object has no attribute 'X'",
            description="Accessing attribute on None (missing return)",
            fix_fn=self._fix_none_attribute,
            priority=60,
        ))
        
        # ── Pattern 9: Encoding/emoji issue ──────────────────────────────
        self.register(ErrorPattern(
            name="encoding_error",
            signature_regex=r"UnicodeEncodeError::.*codec can't encode",
            description="Non-ASCII characters in print statements",
            fix_fn=self._fix_encoding_error,
            priority=95,
        ))
        
        # ── Pattern 10: IndentationError ─────────────────────────────────
        self.register(ErrorPattern(
            name="indentation_error",
            signature_regex=r"IndentationError::.*",
            description="Inconsistent indentation (tabs vs spaces)",
            fix_fn=self._fix_indentation,
            priority=90,
        ))
        
        # ── Pattern 11: Missing colon after def/class/if/for ─────────────
        self.register(ErrorPattern(
            name="missing_colon",
            signature_regex=r"SyntaxError::expected ':'",
            description="Missing colon after control statement",
            fix_fn=self._fix_missing_colon,
            priority=85,
        ))
        
        # ── Pattern 12: Type mismatch in f-string ────────────────────────
        self.register(ErrorPattern(
            name="type_error_format",
            signature_regex=r"TypeError::.*not all arguments converted.*format",
            description="Wrong string formatting",
            fix_fn=self._fix_format_string,
            priority=65,
        ))

        # Sort by priority (highest first)
        self.patterns.sort(key=lambda p: p.priority, reverse=True)
    
    def register(self, pattern: ErrorPattern):
        """Register a new error pattern."""
        self.patterns.append(pattern)
    
    def try_auto_fix(
        self,
        code: str,
        error_type: str,
        error_message: str,
        file_contents: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        """Try to auto-fix the code using pattern matching.
        
        Args:
            code: The source code to fix
            error_type: Error type (e.g. "AttributeError")
            error_message: Error message
            file_contents: All project files (for cross-file fixes)
            
        Returns:
            Fixed code if a pattern matched and fix succeeded, None otherwise
        """
        # Build normalized signature
        msg_norm = error_message.lower()
        msg_norm = re.sub(r"'[^']*'", "'X'", msg_norm)
        msg_norm = re.sub(r'"[^"]*"', "'X'", msg_norm)
        msg_norm = re.sub(r'\d+', 'N', msg_norm)
        signature = f"{error_type}::{msg_norm}"
        
        for pattern in self.patterns:
            try:
                match = re.search(pattern.signature_regex, signature, re.IGNORECASE)
                if match:
                    logger.info(f"  🎯 Pattern match: {pattern.name} → {error_type}: {error_message[:80]}")
                    fixed = pattern.fix_fn(code, error_message, match)
                    if fixed and fixed != code:
                        # Verify the fix is syntactically valid
                        try:
                            ast.parse(fixed)
                            pattern.success_count += 1
                            logger.info(f"  ✅ Auto-fix applied: {pattern.name} (success #{pattern.success_count})")
                            return fixed
                        except SyntaxError:
                            logger.warning(f"  ⚠️ Auto-fix for {pattern.name} produced invalid syntax — skipping")
                            pattern.failure_count += 1
                    else:
                        pattern.failure_count += 1
            except Exception as e:
                logger.debug(f"  Pattern {pattern.name} raised: {e}")
                pattern.failure_count += 1
        
        return None
    
    def try_auto_fix_batch(
        self,
        files: Dict[str, str],
        errors: list,
    ) -> Tuple[Dict[str, str], List[str], List[str]]:
        """Try to auto-fix all files against all errors.
        
        Args:
            files: Dict of {filename: code}
            errors: List of error dicts with 'error_type', 'error_message', 'file' keys
            
        Returns:
            Tuple of (fixed_files, fixed_error_msgs, remaining_error_msgs)
        """
        fixed_files = dict(files)
        fixed_errors: List[str] = []
        remaining_errors: List[str] = []
        
        for err in errors:
            if isinstance(err, dict):
                etype = err.get("error_type", "")
                emsg = err.get("error_message", "")
                efile = err.get("file", "")
                err_str = f"{etype}: {emsg}"
            else:
                err_str = str(err)
                # Try to parse error type from string
                m = re.match(r'(\w+(?:Error|Exception))\s*:\s*(.+)', err_str)
                if m:
                    etype = m.group(1)
                    emsg = m.group(2)
                else:
                    etype = ""
                    emsg = err_str
                # Try to find file reference
                fm = re.search(r'(?:in|File)\s+["\']?(\w+\.py)["\']?', err_str)
                efile = fm.group(1) if fm else ""
            
            if not etype:
                remaining_errors.append(err_str)
                continue
            
            # Try to fix the relevant file
            target_file = efile if efile in fixed_files else None
            if not target_file:
                # Try fuzzy match
                for fname in fixed_files:
                    if fname.endswith('.py') and fname in err_str:
                        target_file = fname
                        break
            
            if target_file:
                fixed = self.try_auto_fix(
                    fixed_files[target_file], etype, emsg, fixed_files
                )
                if fixed:
                    fixed_files[target_file] = fixed
                    fixed_errors.append(err_str)
                    continue
            
            remaining_errors.append(err_str)
        
        return fixed_files, fixed_errors, remaining_errors
    
    def get_stats(self) -> Dict[str, dict]:
        """Get stats for each registered pattern."""
        return {
            p.name: {
                "description": p.description,
                "priority": p.priority,
                "successes": p.success_count,
                "failures": p.failure_count,
                "hit_rate": (
                    f"{p.success_count / (p.success_count + p.failure_count) * 100:.0f}%"
                    if (p.success_count + p.failure_count) > 0 else "N/A"
                ),
            }
            for p in self.patterns
        }

    # ══════════════════════════════════════════════════════════════════════
    # FIX FUNCTIONS (deterministic — no LLM needed)
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _fix_missing_self(code: str, error_msg: str, match: re.Match) -> Optional[str]:
        """Add 'self' parameter to methods that are missing it."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return None
        
        lines = code.splitlines()
        fixed = False
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if not item.args.args or item.args.args[0].arg != 'self':
                            # Skip @staticmethod
                            is_static = any(
                                isinstance(d, ast.Name) and d.id == 'staticmethod'
                                for d in item.decorator_list
                            )
                            if not is_static:
                                line_idx = item.lineno - 1
                                line = lines[line_idx]
                                # Add self as first parameter
                                lines[line_idx] = re.sub(
                                    r'def\s+' + re.escape(item.name) + r'\s*\(',
                                    f'def {item.name}(self, ',
                                    line, count=1
                                )
                                # Fix "self, )" → "self)"
                                lines[line_idx] = lines[line_idx].replace('self, )', 'self)')
                                fixed = True
        
        return '\n'.join(lines) if fixed else None

    @staticmethod
    def _fix_init_args(code: str, error_msg: str, match: re.Match) -> Optional[str]:
        """Fix __init__ parameter count issues."""
        # This is too context-specific for a deterministic fix
        return None

    @staticmethod
    def _fix_name_error(code: str, error_msg: str, match: re.Match) -> Optional[str]:
        """Try to fix undefined name errors."""
        # Extract the undefined name
        m = re.search(r"name '(\w+)' is not defined", error_msg)
        if not m:
            return None
        undefined_name = m.group(1)
        
        # Common case: 'Optional' used without importing from typing
        typing_names = {
            'Optional', 'List', 'Dict', 'Tuple', 'Set', 'Any',
            'Union', 'Callable', 'Iterator', 'Generator', 'Sequence',
            'Mapping', 'TypeVar', 'ClassVar', 'Final', 'Literal',
        }
        
        if undefined_name in typing_names:
            # Add import at top of file
            lines = code.splitlines()
            # Check if 'from typing import' already exists
            for i, line in enumerate(lines):
                if line.strip().startswith('from typing import'):
                    # Add the missing name to existing import
                    if undefined_name not in line:
                        lines[i] = line.rstrip() + f', {undefined_name}'
                        return '\n'.join(lines)
                    return None  # Already imported?
            
            # No typing import found — add one after other imports
            import_end = 0
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith(('import ', 'from ')):
                    import_end = i + 1
                elif stripped and not stripped.startswith('#') and import_end > 0:
                    break
            
            lines.insert(import_end, f'from typing import {undefined_name}')
            return '\n'.join(lines)
        
        # Common case: 'json', 'os', 'sys', etc. used without import
        common_stdlib = {
            'json', 'os', 'sys', 're', 'math', 'random', 'time',
            'datetime', 'pathlib', 'logging', 'hashlib', 'uuid',
            'collections', 'itertools', 'functools', 'copy',
            'subprocess', 'threading', 'asyncio', 'io', 'csv',
            'sqlite3', 'base64', 'secrets', 'shutil', 'tempfile',
            'textwrap', 'string', 'struct', 'enum', 'dataclasses',
            'abc', 'contextlib', 'warnings', 'traceback', 'inspect',
        }
        
        if undefined_name in common_stdlib:
            lines = code.splitlines()
            # Already imported?
            for line in lines:
                if line.strip() == f'import {undefined_name}':
                    return None
            
            # Add import at the top (after existing imports)
            import_end = 0
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith(('import ', 'from ')):
                    import_end = i + 1
                elif stripped and not stripped.startswith('#') and import_end > 0:
                    break
            
            lines.insert(import_end, f'import {undefined_name}')
            return '\n'.join(lines)
        
        return None

    @staticmethod
    def _fix_import_name(code: str, error_msg: str, match: re.Match) -> Optional[str]:
        """Fix importing a name that doesn't exist in the target module."""
        # Parse: "cannot import name 'X' from 'module'"
        m = re.search(r"cannot import name '(\w+)' from '(\w+)'", error_msg)
        if not m:
            return None
        # Can't fix this deterministically without knowing the module contents
        return None

    @staticmethod
    def _fix_module_not_found(code: str, error_msg: str, match: re.Match) -> Optional[str]:
        """Fix ModuleNotFoundError for dotted imports of local files."""
        m = re.search(r"No module named '([^']+)'", error_msg)
        if not m:
            return None
        module_path = m.group(1)
        
        if '.' in module_path:
            # Dotted import: from project.utils import X → from utils import X
            parts = module_path.split('.')
            local_module = parts[-1]
            
            lines = code.splitlines()
            fixed = False
            for i, line in enumerate(lines):
                if module_path in line and line.strip().startswith(('from ', 'import ')):
                    # Replace dotted import with flat import
                    new_line = line.replace(module_path, local_module)
                    if new_line != line:
                        lines[i] = new_line
                        fixed = True
            
            return '\n'.join(lines) if fixed else None
        
        return None

    @staticmethod
    def _fix_missing_fstring(code: str, error_msg: str, match: re.Match) -> Optional[str]:
        """Add f prefix to strings that contain {variable} references."""
        lines = code.splitlines()
        fixed = False
        
        # Pattern: string with {name} but no f prefix
        fstring_pattern = re.compile(
            r'''(?<![fFbBrRuU])(["'])((?:(?!\1).)*\{[a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)*(?:\[.+?\])?\}(?:(?!\1).)*)\1'''
        )
        
        for i, line in enumerate(lines):
            # Skip comments and docstrings
            stripped = line.strip()
            if stripped.startswith('#'):
                continue
            
            # Find strings with {var} that aren't f-strings
            for m in fstring_pattern.finditer(line):
                quote = m.group(1)
                content = m.group(2)
                # Verify {name} is a variable reference (not a dict literal or set)
                var_refs = re.findall(r'\{([a-zA-Z_]\w*)', content)
                if var_refs:
                    # Add f prefix
                    old = m.group(0)
                    new = 'f' + old
                    lines[i] = lines[i].replace(old, new, 1)
                    fixed = True
        
        return '\n'.join(lines) if fixed else None

    @staticmethod
    def _fix_relative_import(code: str, error_msg: str, match: re.Match) -> Optional[str]:
        """Convert relative imports to absolute imports."""
        lines = code.splitlines()
        fixed = False
        
        for i, line in enumerate(lines):
            # from .module import X → from module import X
            m = re.match(r'^(\s*from\s+)\.(\w+)(\s+import\s+.*)$', line)
            if m:
                lines[i] = f"{m.group(1)}{m.group(2)}{m.group(3)}"
                fixed = True
            
            # from ..module import X → from module import X
            m = re.match(r'^(\s*from\s+)\.\.+(\w+)(\s+import\s+.*)$', line)
            if m:
                lines[i] = f"{m.group(1)}{m.group(2)}{m.group(3)}"
                fixed = True
        
        return '\n'.join(lines) if fixed else None

    @staticmethod
    def _fix_none_attribute(code: str, error_msg: str, match: re.Match) -> Optional[str]:
        """Try to fix NoneType attribute access — too context-specific usually."""
        return None

    @staticmethod
    def _fix_encoding_error(code: str, error_msg: str, match: re.Match) -> Optional[str]:
        """Replace emoji/unicode characters with ASCII equivalents."""
        emoji_map = {
            '✅': '[OK]', '❌': '[FAIL]', '⚠️': '[!]', '⚠': '[!]',
            '🔄': '[...]', '✓': '[v]', '✗': '[x]', '📊': '[stats]',
            '🔧': '[fix]', '💡': '[!]', '🚀': '[>>]', '📝': '[note]',
            '🎯': '[>]', '⭐': '[*]', '🔑': '[key]', '📂': '[dir]',
            '📁': '[dir]', '🗂️': '[files]', '🔍': '[search]',
            '💾': '[save]', '🖥️': '[pc]', '🌐': '[web]', '📈': '[up]',
            '📉': '[down]', '🏷️': '[tag]', '🔒': '[lock]', '🔓': '[unlock]',
            '➡️': '->', '⬅️': '<-', '⬆️': '^', '⬇️': 'v',
            '▶': '>', '◀': '<', '🔴': '[!]', '🟢': '[OK]', '🟡': '[?]',
            '─': '-', '│': '|', '┌': '+', '┐': '+', '└': '+', '┘': '+',
            '├': '+', '┤': '+', '┬': '+', '┴': '+', '┼': '+',
            '═': '=', '║': '|', '╔': '+', '╗': '+', '╚': '+', '╝': '+',
        }
        
        fixed_code = code
        for emoji, replacement in emoji_map.items():
            fixed_code = fixed_code.replace(emoji, replacement)
        
        # Also replace any remaining non-ASCII in string literals
        # This is aggressive but necessary for cp1252 compatibility
        if fixed_code != code:
            return fixed_code
        
        return None

    @staticmethod
    def _fix_indentation(code: str, error_msg: str, match: re.Match) -> Optional[str]:
        """Fix mixed tabs and spaces indentation."""
        # Replace all tabs with 4 spaces
        fixed = code.expandtabs(4)
        return fixed if fixed != code else None

    @staticmethod
    def _fix_missing_colon(code: str, error_msg: str, match: re.Match) -> Optional[str]:
        """Add missing colon after def/class/if/for/while/else/elif/try/except/finally."""
        lines = code.splitlines()
        fixed = False
        
        colon_keywords = ('def ', 'class ', 'if ', 'elif ', 'else', 'for ', 'while ',
                          'try', 'except', 'finally', 'with ', 'async def ', 'async for ')
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            
            for keyword in colon_keywords:
                if stripped.startswith(keyword) and not stripped.endswith(':') and not stripped.endswith(':\\'):
                    # Check it's not a multi-line statement
                    if '\\' not in stripped and stripped.count('(') <= stripped.count(')'):
                        lines[i] = line.rstrip() + ':'
                        fixed = True
                        break
        
        return '\n'.join(lines) if fixed else None

    @staticmethod
    def _fix_format_string(code: str, error_msg: str, match: re.Match) -> Optional[str]:
        """Fix % formatting issues — convert to f-strings."""
        # Too complex to fix deterministically without knowing types
        return None


# ══════════════════════════════════════════════════════════════════════════
# Module-level singleton
# ══════════════════════════════════════════════════════════════════════════
_instance: Optional[ErrorPatternDB] = None


def get_pattern_db() -> ErrorPatternDB:
    """Get or create the singleton ErrorPatternDB instance."""
    global _instance
    if _instance is None:
        _instance = ErrorPatternDB()
    return _instance
