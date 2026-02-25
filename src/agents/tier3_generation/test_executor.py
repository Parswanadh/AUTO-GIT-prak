"""
Test Execution System
Executes generated tests in isolated environment and reports results.
"""

import subprocess
import tempfile
import sys
import json
import time
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """Result from test execution"""
    passed: bool
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int = 0
    failures: List[Dict[str, str]] = field(default_factory=list)
    coverage_percent: float = 0.0
    execution_time: float = 0.0
    stdout: str = ""
    stderr: str = ""


class TestExecutor:
    """
    Execute tests in isolated environment.
    
    Features:
    - Isolated execution (temp directory)
    - Timeout protection
    - Detailed error reporting
    - pytest integration
    """
    
    def __init__(self, timeout: int = 60):
        """
        Initialize test executor.
        
        Args:
            timeout: Maximum execution time in seconds
        """
        self.timeout = timeout
        logger.info(f"TestExecutor initialized (timeout={timeout}s)")
    
    async def execute_tests(
        self,
        code: str,
        tests: str,
        module_name: str = "implementation"
    ) -> TestResult:
        """
        Execute tests against code.
        
        Args:
            code: Implementation code to test
            tests: Test code (pytest format)
            module_name: Name for the implementation module
        
        Returns:
            TestResult with execution details
        """
        logger.info("Executing tests in isolated environment...")
        
        # Create temporary directory for isolated execution
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            # Write implementation code
            code_file = tmpdir_path / f"{module_name}.py"
            code_file.write_text(code, encoding='utf-8')
            logger.debug(f"Wrote code to {code_file}")
            
            # Write test code
            test_file = tmpdir_path / f"test_{module_name}.py"
            
            # Modify tests to import from implementation
            modified_tests = self._prepare_tests(tests, module_name)
            test_file.write_text(modified_tests, encoding='utf-8')
            logger.debug(f"Wrote tests to {test_file}")
            
            # Run pytest
            result = await self._run_pytest(tmpdir_path, test_file)
            
            logger.info(f"Test execution complete: {result.passed_tests}/{result.total_tests} passed")
            
            return result
    
    def _prepare_tests(self, tests: str, module_name: str) -> str:
        """
        Prepare test code for execution.
        
        Adds necessary imports and cleans up the test code.
        """
        # Check if import already exists
        import_line = f"from {module_name} import *"
        
        if import_line not in tests:
            # Add import after pytest import
            lines = tests.split('\n')
            new_lines = []
            import_added = False
            
            for line in lines:
                new_lines.append(line)
                
                # Add import after pytest import
                if not import_added and ('import pytest' in line or 'from typing' in line):
                    new_lines.append(import_line)
                    import_added = True
            
            # If we didn't add it yet, add at the beginning
            if not import_added:
                new_lines.insert(0, import_line)
                new_lines.insert(0, "import pytest")
            
            tests = '\n'.join(new_lines)
        
        return tests
    
    async def _run_pytest(
        self,
        working_dir: Path,
        test_file: Path
    ) -> TestResult:
        """Run pytest and parse results"""
        
        start_time = time.time()
        
        try:
            # Run pytest with JSON report
            result = subprocess.run(
                [
                    sys.executable, "-m", "pytest",
                    str(test_file),
                    "-v",
                    "--tb=short",
                    "--color=no",
                    "-ra"  # Show summary of all test outcomes
                ],
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            execution_time = time.time() - start_time
            
            # Parse pytest output
            return self._parse_pytest_output(
                result.stdout,
                result.stderr,
                result.returncode,
                execution_time
            )
        
        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            logger.error(f"Test execution timeout after {self.timeout}s")
            
            return TestResult(
                passed=False,
                total_tests=0,
                passed_tests=0,
                failed_tests=0,
                failures=[{
                    "test": "timeout",
                    "error": f"Test execution exceeded {self.timeout}s timeout"
                }],
                execution_time=execution_time,
                stderr=f"Timeout after {self.timeout}s"
            )
        
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Test execution error: {e}")
            
            return TestResult(
                passed=False,
                total_tests=0,
                passed_tests=0,
                failed_tests=0,
                failures=[{
                    "test": "execution_error",
                    "error": str(e)
                }],
                execution_time=execution_time,
                stderr=str(e)
            )
    
    def _parse_pytest_output(
        self,
        stdout: str,
        stderr: str,
        returncode: int,
        execution_time: float
    ) -> TestResult:
        """Parse pytest output to extract test results"""
        
        # Initialize counters
        passed_tests = 0
        failed_tests = 0
        skipped_tests = 0
        total_tests = 0
        failures = []
        
        # Parse the output line by line
        lines = stdout.split('\n')
        
        # Look for test outcome lines
        current_test = None
        current_error = []
        
        for line in lines:
            # Test result lines: test_file.py::test_name PASSED
            if '::' in line and any(outcome in line for outcome in ['PASSED', 'FAILED', 'SKIPPED', 'ERROR']):
                if 'PASSED' in line:
                    passed_tests += 1
                    total_tests += 1
                elif 'FAILED' in line or 'ERROR' in line:
                    failed_tests += 1
                    total_tests += 1
                    # Extract test name
                    test_name = line.split('::')[1].split()[0] if '::' in line else "unknown"
                    current_test = test_name
                elif 'SKIPPED' in line:
                    skipped_tests += 1
                    total_tests += 1
            
            # Capture error messages (lines starting with E or FAILED)
            if current_test and (line.startswith('E ') or line.startswith('FAILED')):
                current_error.append(line)
        
        # If we captured an error, add it to failures
        if current_test and current_error:
            failures.append({
                "test": current_test,
                "error": '\n'.join(current_error)
            })
        
        # Parse summary line: "=== 5 passed, 2 failed in 1.23s ==="
        for line in lines:
            if 'passed' in line or 'failed' in line:
                # Try to extract numbers from summary
                import re
                passed_match = re.search(r'(\d+) passed', line)
                failed_match = re.search(r'(\d+) failed', line)
                skipped_match = re.search(r'(\d+) skipped', line)
                
                if passed_match:
                    passed_tests = int(passed_match.group(1))
                if failed_match:
                    failed_tests = int(failed_match.group(1))
                if skipped_match:
                    skipped_tests = int(skipped_match.group(1))
                
                total_tests = passed_tests + failed_tests + skipped_tests
                break
        
        # If no tests found in summary, but we have returncode, estimate
        if total_tests == 0 and returncode != 5:  # 5 = no tests collected
            # Count "def test_" in output
            total_tests = stdout.count("def test_")
        
        passed = (returncode == 0) and (failed_tests == 0)
        
        return TestResult(
            passed=passed,
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            skipped_tests=skipped_tests,
            failures=failures,
            execution_time=execution_time,
            stdout=stdout,
            stderr=stderr
        )
    
    def print_results(self, result: TestResult):
        """Print test results in a readable format"""
        
        print("\n" + "="*70)
        print("  TEST EXECUTION RESULTS")
        print("="*70)
        print(f"\nTotal Tests: {result.total_tests}")
        print(f"  ✅ Passed: {result.passed_tests}")
        print(f"  ❌ Failed: {result.failed_tests}")
        if result.skipped_tests > 0:
            print(f"  ⏭️  Skipped: {result.skipped_tests}")
        
        if result.total_tests > 0:
            pass_rate = (result.passed_tests / result.total_tests) * 100
            print(f"\nPass Rate: {pass_rate:.1f}%")
        
        print(f"Execution Time: {result.execution_time:.2f}s")
        
        if result.failures:
            print(f"\n❌ Failures ({len(result.failures)}):")
            for failure in result.failures:
                print(f"\n  Test: {failure['test']}")
                print(f"  Error: {failure['error'][:200]}...")
        
        if result.passed:
            print("\n✅ ALL TESTS PASSED!")
        else:
            print("\n⚠️  SOME TESTS FAILED")
        
        print("="*70 + "\n")


# Singleton instance
_executor_instance: Optional[TestExecutor] = None


def get_test_executor() -> TestExecutor:
    """Get or create global test executor instance"""
    global _executor_instance
    
    if _executor_instance is None:
        _executor_instance = TestExecutor()
    
    return _executor_instance
