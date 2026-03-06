"""
Feature Verifier — Runtime Feature Verification in Sandbox

Unlike syntax/import checks or LLM-as-Judge (which reads code and guesses),
this module ACTUALLY RUNS each feature in an isolated subprocess and checks
whether it produces the expected behaviour without crashing.

How it works:
1. Takes the generated code files + structured requirements (key_features list)
2. Uses LLM to generate a `feature_tests.py` script with one test function per feature
3. Runs feature_tests.py in the project's venv via subprocess
4. Parses structured JSON output to get per-feature PASS/FAIL/ERROR results
5. Returns a feature verification report that feeds into the fix loop

This catches the #1 class of bugs: "code generates, imports fine, but features
don't actually work" (wrong dict keys, missing method calls, broken wiring, etc.)
"""

import json
import logging
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ─── Test harness template ──────────────────────────────────────────────────
# This gets prepended to the LLM-generated feature tests.
# It provides a structured JSON output format so we can parse results reliably.
HARNESS_TEMPLATE = r'''
"""Auto-generated feature verification tests."""
import sys
import os
import json
import traceback
import io
from contextlib import redirect_stdout, redirect_stderr

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_RESULTS = []

def feature_test(name: str, importance: str = "important"):
    """Decorator that wraps a test function with exception handling and result capture."""
    def decorator(func):
        def wrapper():
            result = {
                "feature": name,
                "importance": importance,
                "status": "PASS",
                "output": "",
                "error": "",
            }
            # Capture stdout/stderr from the test
            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()
            try:
                with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                    func()
                result["output"] = stdout_capture.getvalue()[:500]
            except AssertionError as e:
                result["status"] = "FAIL"
                result["error"] = f"Assertion failed: {e}"
                result["output"] = stdout_capture.getvalue()[:300]
            except Exception as e:
                result["status"] = "ERROR"
                result["error"] = f"{type(e).__name__}: {e}"
                result["output"] = traceback.format_exc()[-500:]
            _RESULTS.append(result)
        wrapper._test_name = name
        wrapper._is_feature_test = True
        return wrapper
    return decorator


def run_all_tests():
    """Discover and run all @feature_test decorated functions, print JSON results."""
    # Collect all test functions from the global scope
    test_funcs = []
    for name, obj in list(globals().items()):
        if callable(obj) and getattr(obj, '_is_feature_test', False):
            test_funcs.append((name, obj))

    for name, func in test_funcs:
        func()

    # Print structured JSON that the harness can parse
    print("===FEATURE_RESULTS_START===")
    print(json.dumps(_RESULTS, indent=2))
    print("===FEATURE_RESULTS_END===")


# ─── LLM-generated tests below this line ───────────────────────────────────
'''


class FeatureVerifier:
    """
    Generates and runs per-feature runtime tests in an isolated sandbox.
    
    Usage:
        verifier = FeatureVerifier()
        report = await verifier.verify_features(
            files={"main.py": "...", "auth.py": "..."},
            requirements={"key_features": ["login system", "RBAC", ...]},
            idea="Build a code review system with ...",
            project_dir=Path("/tmp/test_project"),
            python_exe=Path("/path/to/venv/python"),
        )
    """

    def __init__(self, timeout: int = 60):
        """
        Args:
            timeout: Max seconds to run feature_tests.py (default 60s)
        """
        self.timeout = timeout

    async def generate_test_script(
        self,
        files: Dict[str, str],
        requirements: Dict[str, Any],
        idea: str,
        get_llm_func,
    ) -> str:
        """
        Use LLM to generate feature_tests.py that exercises each feature.
        
        Returns the full test script (harness + LLM-generated tests).
        """
        from langchain_core.messages import HumanMessage

        # Build code context (show all files so LLM knows the real APIs)
        code_blocks = []
        for fname, fcode in files.items():
            if not fname.endswith((".py", ".txt")):
                continue
            lines = (fcode or "").splitlines()
            # Show full files up to 300 lines, truncate longer ones
            if len(lines) > 300:
                preview = "\n".join(lines[:200]) + f"\n# ... {len(lines) - 300} lines omitted ...\n" + "\n".join(lines[-100:])
            else:
                preview = fcode or ""
            code_blocks.append(f"=== {fname} ({len(lines)} lines) ===\n{preview}")
        code_context = "\n\n".join(code_blocks)

        # Extract features list
        key_features = requirements.get("key_features", [])
        test_scenarios = requirements.get("test_scenarios", [])
        core_components = requirements.get("core_components", [])

        features_text = ""
        if key_features:
            features_text += "KEY FEATURES TO TEST:\n" + "\n".join(f"  {i+1}. {f}" for i, f in enumerate(key_features))
        if test_scenarios:
            features_text += "\n\nTEST SCENARIOS FROM REQUIREMENTS:\n"
            for ts in test_scenarios:
                features_text += f"  - {ts.get('name', '?')}: input={ts.get('input', '?')}, expected={ts.get('expected', '?')}\n"
        if core_components:
            features_text += "\n\nCORE COMPONENTS:\n" + "\n".join(f"  - {c}" for c in core_components)

        prompt = (
            "You are a QA engineer writing feature verification tests for auto-generated Python code.\n\n"
            "Your goal is to write tests that ACTUALLY IMPORT AND CALL the real code to verify each feature works.\n"
            "These are NOT mock tests — they exercise the REAL implementation.\n\n"
            f"USER'S IDEA:\n{idea}\n\n"
            f"{features_text}\n\n"
            f"GENERATED CODE:\n{code_context}\n\n"
            "INSTRUCTIONS:\n"
            "1. Write one @feature_test decorated function per feature/requirement.\n"
            "2. Each test must IMPORT from the actual modules and CALL real methods.\n"
            "3. Use assert statements to verify expected behavior.\n"
            "4. Handle interactive input by NOT calling functions that need stdin (like input()).\n"
            "   Instead, test the underlying logic directly (e.g., test ReviewManager.submit_review()\n"
            "   rather than the CLI input loop).\n"
            "5. For database-backed features, create a fresh instance (the code should auto-create tables).\n"
            "6. For auth features, create test users and verify login/permissions.\n"
            "7. Each test should be independent — no shared state between tests.\n"
            "8. Clean up any created files/databases in finally blocks.\n"
            "9. NEVER call sys.exit(), input(), or start infinite loops.\n"
            "10. Use ONLY classes/functions that ACTUALLY EXIST in the code (check the imports carefully).\n"
            "11. PAY CLOSE ATTENTION to actual method signatures, parameter names, and return types\n"
            "    visible in the code above. Do NOT guess API shapes.\n\n"
            "CRITICAL: Look at the ACTUAL dict keys, method names, and return types in the code.\n"
            "If ReviewManager.get_stats() returns 'average_approved_complexity', use THAT key, not 'avg_complexity'.\n"
            "If a method is named '_show_main_menu', don't call 'main_menu'.\n\n"
            "The test harness is already provided (the @feature_test decorator and run_all_tests()).\n"
            "You just need to write the test functions.\n\n"
            "Return ONLY the Python test functions (no imports for the harness, no if __name__ block,\n"
            "no markdown fences). Start directly with the first @feature_test.\n\n"
            "Example format:\n"
            '@feature_test("User Authentication", importance="critical")\n'
            "def test_user_authentication():\n"
            "    from auth import AuthManager\n"
            "    am = AuthManager(db_path=':memory:')\n"
            "    am.create_user('testuser', 'pass123', 'admin')\n"
            "    uid = am.login('testuser', 'pass123')\n"
            "    assert uid is not None, 'Login should return user ID'\n"
            "    assert am.login('testuser', 'wrong') is None, 'Wrong password should fail'\n"
        )

        llm = get_llm_func("powerful")
        response = await llm.ainvoke([HumanMessage(content=prompt)])

        raw_tests = response.content.strip()
        # Strip markdown fences if present
        import re
        raw_tests = re.sub(r"^```[a-z]*\n?", "", raw_tests)
        raw_tests = re.sub(r"\n?```$", "", raw_tests.strip())
        # Strip thinking tags
        if "<think>" in raw_tests:
            te = raw_tests.rfind("</think>")
            if te != -1:
                raw_tests = raw_tests[te + len("</think>"):].strip()

        # Combine harness + generated tests + runner
        full_script = HARNESS_TEMPLATE + "\n" + raw_tests + "\n\n"
        full_script += 'if __name__ == "__main__":\n    run_all_tests()\n'

        # ── Syntax validation (catches LLM-generated syntax errors like
        #    unclosed f-string braces, missing quotes, etc.) ──────────────
        try:
            compile(full_script, "feature_tests.py", "exec")
        except SyntaxError as syn_err:
            logger.warning(
                f"  ⚠️  LLM-generated feature tests have syntax error: "
                f"{syn_err.msg} (line {syn_err.lineno})"
            )
            # Attempt basic auto-repairs on the raw LLM output
            repaired = self._attempt_syntax_repair(raw_tests, syn_err)
            if repaired is not None:
                full_script = HARNESS_TEMPLATE + "\n" + repaired + "\n\n"
                full_script += 'if __name__ == "__main__":\n    run_all_tests()\n'
                try:
                    compile(full_script, "feature_tests.py", "exec")
                    logger.info("  ✅ Auto-repaired feature test syntax error")
                except SyntaxError:
                    logger.warning(
                        "  ❌ Auto-repair failed — using fallback test script"
                    )
                    full_script = self._fallback_test_script(requirements)
            else:
                logger.warning(
                    "  ❌ Cannot auto-repair — using fallback test script"
                )
                full_script = self._fallback_test_script(requirements)

        return full_script

    @staticmethod
    def _attempt_syntax_repair(raw_tests: str, err: SyntaxError) -> Optional[str]:
        """
        Try simple syntax repairs on LLM-generated test code.
        
        Handles common LLM mistakes:
        - Unclosed f-string braces: f"value is {x" → f"value is {x}"
        - Unclosed quotes: 'hello → 'hello'
        - Missing closing parenthesis
        """
        lines = raw_tests.splitlines()
        # err.lineno is relative to the FULL script (harness + raw_tests).
        # The harness has a fixed number of lines.  We need the offset into
        # raw_tests.  Since we can't easily count harness lines here, we try
        # ALL lines in raw_tests looking for the pattern.
        repaired = False
        for idx in range(len(lines)):
            line = lines[idx]
            # Fix unclosed f-string / regular braces
            open_braces = line.count("{") - line.count("}")
            if open_braces > 0:
                lines[idx] = line + "}" * open_braces
                repaired = True
            # Fix unclosed triple-quotes
            for q in ('"""', "'''"):
                if line.count(q) % 2 != 0:
                    lines[idx] = lines[idx] + q
                    repaired = True
            # Fix unclosed single/double quotes (only if not inside a triple-quote)
            if '"""' not in line and "'''" not in line:
                for q in ('"', "'"):
                    # Count unescaped occurrences
                    cnt = len(re.findall(rf'(?<!\\){re.escape(q)}', line))
                    if cnt % 2 != 0:
                        lines[idx] = lines[idx] + q
                        repaired = True
            # Fix unclosed parentheses
            open_parens = line.count("(") - line.count(")")
            if open_parens > 0:
                lines[idx] = lines[idx] + ")" * open_parens
                repaired = True

        return "\n".join(lines) if repaired else None

    def _fallback_test_script(self, requirements: Dict[str, Any]) -> str:
        """
        Generate a minimal VALID fallback test script when the LLM output
        has unfixable syntax errors.  Each feature gets a SKIP test so the
        harness still produces structured JSON output.
        """
        features = requirements.get("key_features", [])
        test_funcs = []
        for i, feat in enumerate(features[:10]):
            safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", str(feat))[:40]
            test_funcs.append(
                f'@feature_test("{feat}", importance="important")\n'
                f"def test_{safe_name}_{i}():\n"
                f'    """Skipped — test generation had syntax error."""\n'
                f'    raise AssertionError("UNTESTED: test generation had syntax error — feature not verified")\n'
            )
        fallback_tests = "\n\n".join(test_funcs) if test_funcs else (
            '@feature_test("basic_import", importance="important")\n'
            "def test_basic():\n"
            '    """Fallback test."""\n'
            '    raise AssertionError("UNTESTED: test generation had syntax error")\n'
        )
        full = HARNESS_TEMPLATE + "\n" + fallback_tests + "\n\n"
        full += 'if __name__ == "__main__":\n    run_all_tests()\n'
        return full

    def run_tests_in_sandbox(
        self,
        test_script: str,
        project_dir: Path,
        python_exe: Path,
    ) -> Dict[str, Any]:
        """
        Write feature_tests.py to project_dir and run it in subprocess.
        
        Returns parsed results dict with per-feature PASS/FAIL/ERROR.
        """
        test_file = project_dir / "feature_tests.py"
        try:
            test_file.write_text(test_script, encoding="utf-8")
            logger.info(f"  Wrote feature_tests.py ({len(test_script)} chars)")
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to write feature_tests.py: {e}",
                "features": [],
                "summary": {"total": 0, "passed": 0, "failed": 0, "errors": 0},
            }

        try:
            # --- V1 FIX: Strip API keys from env (same as code_executor) ---
            _fv_env = {}
            _SENSITIVE = {"GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
                          "GITHUB_TOKEN", "GH_TOKEN", "OPENAI_ORG", "AWS_ACCESS_KEY_ID",
                          "AWS_SECRET_ACCESS_KEY"}
            _SENS_PATS = ("API_KEY", "SECRET", "_TOKEN", "PASSWORD", "CREDENTIAL", "_KEY")
            for k, v in __import__('os').environ.items():
                if k in _SENSITIVE or any(p in k.upper() for p in _SENS_PATS):
                    continue
                _fv_env[k] = v
            _fv_env["PYTHONDONTWRITEBYTECODE"] = "1"
            _fv_env["PYTHONIOENCODING"] = "utf-8"
            result = subprocess.run(
                [str(python_exe), "feature_tests.py"],
                capture_output=True,
                timeout=self.timeout,
                cwd=str(project_dir),
                env=_fv_env,
            )
            stdout = result.stdout.decode(errors="replace")
            stderr = result.stderr.decode(errors="replace")

            logger.info(f"  feature_tests.py exit code: {result.returncode}")
            if stderr.strip():
                logger.debug(f"  stderr: {stderr[:500]}")

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"feature_tests.py timed out after {self.timeout}s",
                "features": [],
                "summary": {"total": 0, "passed": 0, "failed": 0, "errors": 0},
                "raw_stdout": "",
                "raw_stderr": "",
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to run feature_tests.py: {e}",
                "features": [],
                "summary": {"total": 0, "passed": 0, "failed": 0, "errors": 0},
            }

        # Parse structured results from stdout
        return self._parse_results(stdout, stderr, result.returncode)

    def _parse_results(self, stdout: str, stderr: str, exit_code: int) -> Dict[str, Any]:
        """Parse the ===FEATURE_RESULTS_START=== JSON block from stdout."""
        features = []
        raw_json = ""

        if "===FEATURE_RESULTS_START===" in stdout and "===FEATURE_RESULTS_END===" in stdout:
            start = stdout.index("===FEATURE_RESULTS_START===") + len("===FEATURE_RESULTS_START===")
            end = stdout.index("===FEATURE_RESULTS_END===")
            raw_json = stdout[start:end].strip()

            try:
                features = json.loads(raw_json)
            except json.JSONDecodeError as e:
                logger.warning(f"  Failed to parse feature results JSON: {e}")
                features = []

        # If we couldn't parse JSON results, create a single "harness crash" entry
        if not features:
            # Check if the test script itself crashed before producing results
            error_detail = stderr.strip() or stdout.strip() or "Unknown error"
            # Extract just the last traceback
            if "Traceback" in error_detail:
                tb_start = error_detail.rfind("Traceback")
                error_detail = error_detail[tb_start:]
            features = [{
                "feature": "Test Harness Execution",
                "importance": "critical",
                "status": "ERROR",
                "output": "",
                "error": f"feature_tests.py crashed before producing results: {error_detail[-500:]}",
            }]

        # Compute summary
        passed = sum(1 for f in features if f.get("status") == "PASS")
        failed = sum(1 for f in features if f.get("status") == "FAIL")
        errors = sum(1 for f in features if f.get("status") == "ERROR")
        total = len(features)

        return {
            "success": failed == 0 and errors == 0 and total > 0,
            "features": features,
            "summary": {
                "total": total,
                "passed": passed,
                "failed": failed,
                "errors": errors,
                "pass_rate": (passed / total * 100) if total > 0 else 0,
            },
            "raw_stdout": stdout[:3000],
            "raw_stderr": stderr[:2000],
            "exit_code": exit_code,
        }

    async def verify_features(
        self,
        files: Dict[str, str],
        requirements: Dict[str, Any],
        idea: str,
        project_dir: Path,
        python_exe: Path,
        get_llm_func,
    ) -> Dict[str, Any]:
        """
        End-to-end feature verification: generate tests → run in sandbox → report.
        
        Args:
            files: Dict of filename → code content
            requirements: Structured requirements from requirements_extraction_node
            idea: Original user idea string
            project_dir: Path to the project directory (with venv)
            python_exe: Path to the Python executable in the project's venv
            get_llm_func: Function to get LLM instance (e.g., get_fallback_llm)
            
        Returns:
            Feature verification report dict
        """
        logger.info("🔍 Feature Verification — generating runtime tests...")

        # Step 1: Generate the test script
        try:
            test_script = await self.generate_test_script(
                files=files,
                requirements=requirements,
                idea=idea,
                get_llm_func=get_llm_func,
            )
        except Exception as e:
            logger.error(f"  Failed to generate feature tests: {e}")
            return {
                "success": False,
                "error": f"Test generation failed: {e}",
                "features": [],
                "summary": {"total": 0, "passed": 0, "failed": 0, "errors": 0},
                "test_script": "",
            }

        # Step 2: Run in sandbox
        report = self.run_tests_in_sandbox(
            test_script=test_script,
            project_dir=project_dir,
            python_exe=python_exe,
        )

        # Attach the generated test script for debugging
        report["test_script"] = test_script

        # Step 3: Log results
        summary = report.get("summary", {})
        total = summary.get("total", 0)
        passed = summary.get("passed", 0)
        failed = summary.get("failed", 0)
        errors = summary.get("errors", 0)
        pass_rate = summary.get("pass_rate", 0)

        logger.info(f"  Feature Verification: {passed}/{total} passed ({pass_rate:.0f}%)")
        logger.info(f"  Failed: {failed}, Errors: {errors}")

        for feat in report.get("features", []):
            status = feat.get("status", "?")
            name = feat.get("feature", "?")
            if status == "PASS":
                logger.info(f"    ✅ {name}")
            elif status == "FAIL":
                logger.warning(f"    ❌ {name}: {feat.get('error', '')[:100]}")
            else:
                logger.error(f"    💥 {name}: {feat.get('error', '')[:100]}")

        return report


def create_feature_error_messages(report: Dict[str, Any]) -> List[str]:
    """
    Convert a feature verification report into error messages suitable for
    injection into test_results["execution_errors"] so the fix loop can act on them.
    
    Only includes FAIL and ERROR features — PASSed features are ignored.
    """
    errors = []
    for feat in report.get("features", []):
        status = feat.get("status", "?")
        if status in ("FAIL", "ERROR"):
            name = feat.get("feature", "unknown feature")
            importance = feat.get("importance", "important")
            error_detail = feat.get("error", "no details")
            errors.append(
                f"FEATURE_VERIFICATION_{status}: [{importance.upper()}] "
                f"Feature '{name}' {status.lower()}ed at runtime — {error_detail}"
            )
    return errors
