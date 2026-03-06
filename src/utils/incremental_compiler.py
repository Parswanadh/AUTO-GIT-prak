"""
Incremental Compilation Feedback — Validate each file as it's generated.

Instead of generating ALL files and THEN testing (finding 15 errors at once),
this module validates each file immediately after generation:
  1. AST parse (syntax check)
  2. Import analysis (are referenced modules available?)
  3. Cross-file consistency (does this file's usage match already-generated APIs?)

If issues are found, they're fed back as context to subsequent file generation
prompts, preventing cascading errors.

Expected impact: -40% cascading errors, +20% first-time correctness.
"""

from __future__ import annotations

import ast
import re
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger("incremental_compiler")


@dataclass
class FileValidationResult:
    """Result of validating a single generated file."""
    filename: str
    is_valid: bool = True
    syntax_ok: bool = True
    syntax_error: str = ""
    undefined_imports: List[str] = field(default_factory=list)
    missing_attrs: List[str] = field(default_factory=list)    # calls to methods/attrs that don't exist
    circular_deps: List[str] = field(default_factory=list)    # circular import warnings
    warnings: List[str] = field(default_factory=list)
    
    def format_for_prompt(self) -> str:
        """Format validation results for injection into the next file's prompt."""
        if self.is_valid:
            return f"  ✓ {self.filename}: OK"
        
        parts = [f"  ⚠ {self.filename} has issues:"]
        if not self.syntax_ok:
            parts.append(f"    - SYNTAX ERROR: {self.syntax_error}")
        for imp in self.undefined_imports:
            parts.append(f"    - Missing import: {imp}")
        for attr in self.missing_attrs:
            parts.append(f"    - Missing attribute/method: {attr}")
        for circ in self.circular_deps:
            parts.append(f"    - Circular dependency risk: {circ}")
        for warn in self.warnings:
            parts.append(f"    - Warning: {warn}")
        
        return "\n".join(parts)


class IncrementalCompiler:
    """Validates files incrementally during code generation.
    
    Usage:
        compiler = IncrementalCompiler()
        
        # After generating each file:
        result = compiler.validate_file("utils.py", generated_code)
        compiler.register_file("utils.py", generated_code)
        
        # Get feedback for the next file's prompt:
        feedback = compiler.get_feedback_for_next_file("main.py")
    """
    
    def __init__(self):
        # Already-generated files: {filename: code}
        self.generated_files: Dict[str, str] = {}
        # Exported symbols per file: {filename: {symbol_names}}
        self.exported_symbols: Dict[str, Set[str]] = {}
        # Import graph: {filename: set of files it imports from}
        self.import_graph: Dict[str, Set[str]] = {}
        # Validation results history
        self.results: List[FileValidationResult] = []
        # Known project file names (planned files, may not be generated yet)
        self.planned_files: Set[str] = set()
    
    def set_planned_files(self, file_list: List[str]):
        """Tell the compiler about all planned files (so import checks know
        which imports are project-local vs external)."""
        self.planned_files = {f for f in file_list if f.endswith('.py')}
    
    def register_file(self, filename: str, code: str):
        """Register a generated file and extract its exported symbols."""
        self.generated_files[filename] = code
        self.exported_symbols[filename] = self._extract_exports(code)
        self.import_graph[filename] = self._extract_local_imports(code)
        
        logger.debug(
            f"  Registered {filename}: {len(self.exported_symbols[filename])} exports, "
            f"imports from {self.import_graph[filename]}"
        )
    
    def validate_file(self, filename: str, code: str) -> FileValidationResult:
        """Validate a single file against all already-generated files.
        
        Checks:
          1. Syntax (AST parse)
          2. Local imports (do the referenced modules exist and have the symbols?)
          3. Cross-file API consistency (method names, class names)
          4. Circular dependency detection
        """
        result = FileValidationResult(filename=filename)
        
        # ── 1. Syntax check ──────────────────────────────────────────────
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            result.is_valid = False
            result.syntax_ok = False
            result.syntax_error = f"{e.msg} (line {e.lineno})"
            self.results.append(result)
            return result
        
        # ── 2. Import analysis ───────────────────────────────────────────
        local_imports = self._extract_local_imports(code)
        for imp_module in local_imports:
            imp_file = imp_module + ".py" if not imp_module.endswith(".py") else imp_module
            
            if imp_file in self.generated_files:
                # Module exists — check if imported names exist
                imported_names = self._extract_imported_names(code, imp_module)
                available = self.exported_symbols.get(imp_file, set())
                for name in imported_names:
                    if name != '*' and available and name not in available:
                        result.undefined_imports.append(
                            f"'{name}' imported from {imp_module} but not found "
                            f"(available: {', '.join(sorted(available)[:10])})"
                        )
                        result.is_valid = False
            elif imp_file in self.planned_files:
                # Module is planned but not generated yet — just warn
                result.warnings.append(
                    f"{filename} imports from {imp_module} which hasn't been generated yet"
                )
            # If not in planned_files, assume it's a pip/stdlib package
        
        # ── 3. Cross-file API consistency ────────────────────────────────
        # Check: does this file reference methods that exist in other files?
        attr_accesses = self._extract_attribute_accesses(code, tree)
        for obj_name, attr_name, line_no in attr_accesses:
            # Try to find what module 'obj_name' comes from
            source_module = self._find_import_source(code, obj_name)
            if source_module:
                source_file = source_module + ".py"
                if source_file in self.exported_symbols:
                    available = self.exported_symbols[source_file]
                    # Check if the class has the method
                    # (Our export extraction includes class methods as ClassName.method)
                    if attr_name not in available and f"{obj_name}.{attr_name}" not in available:
                        result.missing_attrs.append(
                            f"Line {line_no}: {obj_name}.{attr_name}() — "
                            f"'{attr_name}' not found in {source_module} "
                            f"(available: {', '.join(sorted(available)[:10])})"
                        )
                        result.is_valid = False
        
        # ── 4. Circular dependency check ─────────────────────────────────
        if local_imports:
            # Check if any of our imports would create a cycle
            for imp_module in local_imports:
                imp_file = imp_module + ".py"
                if imp_file in self.import_graph:
                    their_imports = self.import_graph[imp_file]
                    my_module = filename.replace(".py", "")
                    if my_module in their_imports:
                        result.circular_deps.append(
                            f"{filename} ↔ {imp_file} (mutual import)"
                        )
                        result.warnings.append(
                            f"Circular import between {filename} and {imp_file}. "
                            f"Consider using a shared constants module or lazy imports."
                        )
        
        self.results.append(result)
        return result
    
    def get_feedback_for_next_file(self, next_filename: str) -> str:
        """Generate feedback text to inject into the next file's generation prompt.
        
        Includes:
          - Validation status of all previously generated files
          - Any known API mismatches to avoid
          - Circular dependency warnings
        """
        if not self.results:
            return ""
        
        parts = ["INCREMENTAL COMPILATION FEEDBACK (from already-generated files):"]
        
        has_issues = False
        for r in self.results:
            parts.append(r.format_for_prompt())
            if not r.is_valid:
                has_issues = True
        
        if has_issues:
            parts.append("\n⚠️ FIX INSTRUCTIONS: When generating " + next_filename + ":")
            # Compile specific fix instructions
            for r in self.results:
                if not r.is_valid:
                    for imp_err in r.undefined_imports:
                        parts.append(f"  - Avoid: {imp_err}")
                    for attr_err in r.missing_attrs:
                        parts.append(f"  - Check: {attr_err}")
        
        # Add available APIs from generated files
        if self.exported_symbols:
            parts.append("\nAVAILABLE APIs (use THESE EXACT names):")
            for fname, symbols in sorted(self.exported_symbols.items()):
                if symbols:
                    top_symbols = sorted(symbols)[:20]
                    parts.append(f"  {fname}: {', '.join(top_symbols)}")
        
        return "\n".join(parts)
    
    def get_summary(self) -> str:
        """Get a summary of all validation results."""
        if not self.results:
            return "No files validated yet."
        
        valid = sum(1 for r in self.results if r.is_valid)
        total = len(self.results)
        
        parts = [f"Incremental compilation: {valid}/{total} files valid"]
        for r in self.results:
            if not r.is_valid:
                parts.append(f"  ⚠ {r.filename}: {r.format_for_prompt()}")
        
        return "\n".join(parts)
    
    # ══════════════════════════════════════════════════════════════════════
    # Internal helpers
    # ══════════════════════════════════════════════════════════════════════
    
    def _extract_exports(self, code: str) -> Set[str]:
        """Extract all public names defined in a Python file.
        
        Returns class names, function names, and top-level constants.
        Also includes ClassName.method for public methods.
        """
        exports: Set[str] = set()
        
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return exports
        
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                exports.add(node.name)
                # Add public methods
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if not item.name.startswith('_') or item.name == '__init__':
                            exports.add(item.name)
                            exports.add(f"{node.name}.{item.name}")
            
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                exports.add(node.name)
            
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.isupper():
                        exports.add(target.id)
            
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name):
                    exports.add(node.target.id)
        
        return exports
    
    def _extract_local_imports(self, code: str) -> Set[str]:
        """Extract module names imported from local project files."""
        local_imports: Set[str] = set()
        planned_modules = {f.replace('.py', '') for f in self.planned_files}
        
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return local_imports
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and node.module.split('.')[0] in planned_modules:
                    local_imports.add(node.module.split('.')[0])
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split('.')[0] in planned_modules:
                        local_imports.add(alias.name.split('.')[0])
        
        return local_imports
    
    def _extract_imported_names(self, code: str, module_name: str) -> Set[str]:
        """Extract the specific names imported from a given module."""
        names: Set[str] = set()
        
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return names
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.split('.')[0] == module_name:
                    for alias in (node.names or []):
                        names.add(alias.name)
        
        return names
    
    def _extract_attribute_accesses(
        self, code: str, tree: ast.AST
    ) -> List[Tuple[str, str, int]]:
        """Extract obj.attr patterns that might reference cross-file APIs.
        
        Returns list of (object_name, attribute_name, line_number).
        Only tracks accesses where the object comes from an import.
        """
        accesses: List[Tuple[str, str, int]] = []
        
        # First, find all imported names → their source module
        imported_objects: Set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                mod_base = node.module.split('.')[0]
                if mod_base + ".py" in self.planned_files or mod_base + ".py" in self.generated_files:
                    for alias in (node.names or []):
                        name = alias.asname or alias.name
                        imported_objects.add(name)
        
        # Then find attribute accesses on imported objects
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name) and node.value.id in imported_objects:
                    accesses.append((node.value.id, node.attr, getattr(node, 'lineno', 0)))
        
        return accesses
    
    def _find_import_source(self, code: str, name: str) -> Optional[str]:
        """Find which local module a name was imported from."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return None
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                for alias in (node.names or []):
                    actual_name = alias.asname or alias.name
                    if actual_name == name:
                        return node.module.split('.')[0]
        
        return None
