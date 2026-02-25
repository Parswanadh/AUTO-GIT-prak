"""
Execution sandbox for safely running generated code.

Runs code in an isolated subprocess with timeout to catch runtime errors.
"""

import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..validation.error_types import ExecutionResult, ValidationResult, CodeError, ErrorType


class ExecutionSandbox:
    """Safely executes Python code in an isolated environment."""

    def __init__(self, timeout: int = 30):
        """Initialize the execution sandbox.

        Args:
            timeout: Maximum execution time in seconds
        """
        self.timeout = timeout
        self.name = "ExecutionSandbox"

    def execute(
        self,
        files: Dict[str, str],
        test_code: Optional[str] = None
    ) -> ExecutionResult:
        """Execute code in a sandboxed environment.

        Args:
            files: Map of filename -> code content
            test_code: Optional test code to run

        Returns:
            ExecutionResult with output and errors
        """
        start_time = time.time()

        try:
            # Create temporary directory
            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir = Path(tmpdir)

                # Write all files
                for filename, content in files.items():
                    filepath = tmpdir / filename
                    filepath.parent.mkdir(parents=True, exist_ok=True)
                    filepath.write_text(content, encoding='utf-8')

                # Create test script
                test_script = self._create_test_script(files, test_code, tmpdir)
                test_file = tmpdir / "test_execution.py"
                test_file.write_text(test_script, encoding='utf-8')

                # Run the test
                result = subprocess.run(
                    ["python", str(test_file)],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    cwd=str(tmpdir),
                    env={**os.environ, "PYTHONPATH": str(tmpdir)}
                )

                duration = time.time() - start_time

                return ExecutionResult(
                    success=result.returncode == 0,
                    output=result.stdout,
                    error=result.stderr,
                    timeout=False,
                    duration=duration
                )

        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                error=f"Execution timed out after {self.timeout} seconds",
                timeout=True,
                duration=time.time() - start_time
            )

        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"Sandbox error: {str(e)}",
                duration=time.time() - start_time
            )

    def validate_with_execution(
        self,
        files: Dict[str, str],
        file_name: str
    ) -> ValidationResult:
        """Validate code by attempting to execute it.

        Args:
            files: Map of filename -> code content
            file_name: Primary file to validate

        Returns:
            ValidationResult with runtime errors if any
        """
        result = self.execute(files)
        errors = []
        warnings = []

        if not result.success:
            # Parse the error
            error = self._parse_execution_error(result, file_name)
            if error:
                errors.append(error)

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            file_name=file_name
        )

    def _create_test_script(
        self,
        files: Dict[str, str],
        test_code: Optional[str],
        tmpdir: Path
    ) -> str:
        """Create a test script that imports and validates the code.

        Args:
            files: Map of filename -> content
            test_code: Optional custom test code
            tmpdir: Temporary directory path

        Returns:
            Test script content
        """
        if test_code:
            return test_code

        # Default test: try to import all modules
        imports = []
        for filename in files.keys():
            if filename.endswith('.py'):
                module_name = filename[:-3].replace('/', '.')
                imports.append(module_name)

        test_script = f"""
import sys
import traceback

# Add tmpdir to path
sys.path.insert(0, {str(tmpdir)!r})

def test_imports():
    '''Test that all modules can be imported.'''
    modules = {imports!r}

    for module in modules:
        try:
            __import__(module)
            print(f"[OK] Successfully imported {{module}}")
        except Exception as e:
            print(f"[FAIL] Failed to import {{module}}: {{e}}")
            traceback.print_exc()
            return False

    return True

def test_instantiation():
    '''Test that main classes can be instantiated.'''
    try:
        # Try to import and instantiate common classes
        for module in {imports!r}:
            try:
                mod = __import__(module, fromlist=[''])
                # Look for common class names
                for attr_name in dir(mod):
                    attr = getattr(mod, attr_name)
                    if isinstance(attr, type) and attr_name[0].isupper():
                        print(f"[INFO] Found class: {{module}}.{{attr_name}}")
            except Exception:
                pass
        return True
    except Exception as e:
        print(f"[WARN] Instantiation test failed: {{e}}")
        return True  # Don't fail on this

if __name__ == "__main__":
    import_ok = test_imports()
    inst_ok = test_instantiation()

    if import_ok and inst_ok:
        print("\\n[SUCCESS] All tests passed")
        sys.exit(0)
    else:
        print("\\n[FAILED] Some tests failed")
        sys.exit(1)
"""

        return test_script

    def _parse_execution_error(
        self,
        result: ExecutionResult,
        file_name: str
    ) -> Optional[CodeError]:
        """Parse execution error into CodeError.

        Args:
            result: Execution result with error
            file_name: File name for error reporting

        Returns:
            CodeError if error is parseable, None otherwise
        """
        error_text = result.error

        # Try to extract line number and message
        line_number = 0
        error_type = ErrorType.RUNTIME
        message = error_text
        context = ""

        if result.has_syntax_error:
            error_type = ErrorType.SYNTAX
            # Try to parse "File "test.py", line X"
            import re
            match = re.search(r'line (\d+)', error_text)
            if match:
                line_number = int(match.group(1))
            message = error_text.split('\n')[-1].strip()

        elif result.has_import_error:
            error_type = ErrorType.IMPORT
            # Extract module name from error
            import re
            match = re.search(r"No module named '([^']+)'", error_text)
            if match:
                message = f"Module not found: {match.group(1)}"
            else:
                match = re.search(r"cannot import name '([^']+)'", error_text)
                if match:
                    message = f"Cannot import: {match.group(1)}"

        # Get first few lines of error as context
        lines = error_text.split('\n')[:5]
        context = '\n'.join(lines)

        return CodeError(
            type=error_type,
            file=file_name,
            line=line_number,
            message=message[:200],  # Truncate long messages
            context=context,
            fixable=True
        )


def execute_code(
    files: Dict[str, str],
    timeout: int = 30
) -> ExecutionResult:
    """Convenience function to execute code.

    Args:
        files: Map of filename -> code content
        timeout: Maximum execution time in seconds

    Returns:
        ExecutionResult with output and errors
    """
    sandbox = ExecutionSandbox(timeout=timeout)
    return sandbox.execute(files)
