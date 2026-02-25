"""
Import validator for checking local imports and module references.

Validates that all local imports reference actual files in the generated code.
"""

import re
from typing import Dict, List, Set, Tuple
from pathlib import Path

from ..validation.error_types import ValidationResult, CodeError, ErrorType


class ImportValidator:
    """Validates import statements against available files."""

    # Patterns for matching import statements
    IMPORT_PATTERNS = [
        r'from\s+([a-zA-Z_][a-zA-Z0-9_.]*)\s+import',
        r'import\s+([a-zA-Z_][a-zA-Z0-9_.]*)',
    ]

    # Standard library modules (don't validate these)
    STDLIB_MODULES = {
        'os', 'sys', 're', 'json', 'time', 'datetime', 'pathlib',
        'collections', 'itertools', 'functools', 'typing', 'dataclasses',
        'asyncio', 'threading', 'multiprocessing', 'subprocess',
        'math', 'random', 'statistics', 'decimal', 'fractions',
        'io', 'StringIO', 'BytesIO',
        'abc', 'enum', 'warnings', 'contextlib',
        'copy', 'pickle', 'shelve', 'csv',
        'inspect', 'importlib', 'pkgutil',
        # Common third-party (assume installed)
        'torch', 'numpy', 'pandas', 'matplotlib', 'scipy',
        'sklearn', 'tensorflow', 'jax', 'flax',
        'pytorch_lightning', 'pytorch_lightning.utilities',
        'torch_geometric', 'torch_geometric.nn', 'torch_geometric.data',
        'gym', 'gymnasium', 'wandb', 'tqdm', 'yaml',
    }

    def __init__(self):
        """Initialize the import validator."""
        self.name = "ImportValidator"

    def validate(
        self,
        code: str,
        file_name: str,
        available_files: Dict[str, str],
        project_root: str = ""
    ) -> ValidationResult:
        """Validate import statements in code.

        Args:
            code: Python source code to validate
            file_name: Name of the file being validated
            available_files: Map of filename -> content
            project_root: Root directory of project (for resolving paths)

        Returns:
            ValidationResult with import errors if any
        """
        errors = []
        warnings = []

        # Extract all import statements
        imports = self._extract_imports(code)

        # Check each import
        for module_info in imports:
            module_name = module_info['module']
            line_number = module_info['line']
            full_statement = module_info['statement']

            # Skip standard library and common third-party modules
            if self._is_stdlib_or_common(module_name):
                continue

            # Check if it's a local import
            base_module = module_name.split('.')[0]
            if self._is_local_import(module_name, available_files):
                # Validate the file exists
                error = self._validate_local_import(
                    base_module,
                    module_name,
                    available_files,
                    file_name,
                    line_number,
                    full_statement
                )
                if error:
                    errors.append(error)

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            file_name=file_name
        )

    def _extract_imports(self, code: str) -> List[Dict]:
        """Extract all import statements from code.

        Args:
            code: Python source code

        Returns:
            List of dicts with 'module', 'line', 'statement' keys
        """
        imports = []
        lines = code.split('\n')

        for line_num, line in enumerate(lines, 1):
            line = line.strip()

            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue

            # Try each import pattern
            for pattern in self.IMPORT_PATTERNS:
                match = re.match(pattern, line)
                if match:
                    module_name = match.group(1)
                    imports.append({
                        'module': module_name,
                        'line': line_num,
                        'statement': line
                    })
                    break

        return imports

    def _is_stdlib_or_common(self, module_name: str) -> bool:
        """Check if module is standard library or common third-party.

        Args:
            module_name: Module name to check

        Returns:
            True if module is stdlib or common third-party
        """
        base_module = module_name.split('.')[0]
        return base_module in self.STDLIB_MODULES

    def _is_local_import(self, module_name: str, available_files: Dict[str, str]) -> bool:
        """Check if import appears to be a local module.

        Args:
            module_name: Module name from import statement
            available_files: Available files in project

        Returns:
            True if appears to be a local import
        """
        # Check if base module name matches any file
        base_module = module_name.split('.')[0].lower()

        for filename in available_files.keys():
            file_base = Path(filename).stem.lower()
            if file_base == base_module:
                return True

        return False

    def _validate_local_import(
        self,
        base_module: str,
        full_module: str,
        available_files: Dict[str, str],
        current_file: str,
        line_number: int,
        statement: str
    ) -> CodeError:
        """Validate a local import references an existing file.

        Args:
            base_module: Base module name
            full_module: Full module path (could have dots)
            available_files: Map of filename -> content
            current_file: File being validated
            line_number: Line number of import
            statement: Full import statement

        Returns:
            CodeError if file doesn't exist, None otherwise
        """
        # Try to find matching file
        matching_files = []
        for filename in available_files.keys():
            file_stem = Path(filename).stem

            # Direct match
            if file_stem == base_module:
                matching_files.append((filename, 0))
            # Fuzzy match (case-insensitive)
            elif file_stem.lower() == base_module.lower():
                matching_files.append((filename, 1))

        if not matching_files:
            # No matching file found
            suggestion = self._suggest_file(base_module, available_files)
            return CodeError(
                type=ErrorType.IMPORT,
                file=current_file,
                line=line_number,
                message=f"Cannot import '{base_module}': file not found",
                context=statement,
                fixable=True,
                suggestion=f"Did you mean: {suggestion}?" if suggestion else None
            )

        # Check for case mismatch (warning only)
        if matching_files:
            best_match, score = min(matching_files, key=lambda x: x[1])
            if score > 0:  # Case mismatch
                # This is a warning, not an error
                pass  # We could add a warning here

        return None

    def _suggest_file(self, module_name: str, available_files: Dict[str, str]) -> str:
        """Suggest a file name based on module name.

        Args:
            module_name: Module name that wasn't found
            available_files: Available files

        Returns:
            Suggested file name or empty string
        """
        # Direct suggestions
        suggestions = [
            f"{module_name}.py",
            f"{module_name}_model.py",
            f"{module_name}_utils.py",
        ]

        # Check if any suggestions exist
        for suggestion in suggestions:
            if suggestion in available_files:
                return suggestion

        # Try fuzzy matching
        module_lower = module_name.lower()
        for filename in available_files.keys():
            file_stem = Path(filename).stem.lower()
            if module_lower in file_stem or file_stem in module_lower:
                return filename

        return ""


def validate_imports(
    code: str,
    file_name: str,
    available_files: Dict[str, str]
) -> ValidationResult:
    """Convenience function to validate imports.

    Args:
        code: Python source code to validate
        file_name: Name of the file being validated
        available_files: Map of filename -> content

    Returns:
        ValidationResult with import errors if any
    """
    validator = ImportValidator()
    return validator.validate(code, file_name, available_files)
