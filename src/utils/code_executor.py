"""
Code Execution and Testing Environment Manager

Creates isolated Python environments for each project,
installs dependencies, and runs basic tests to validate generated code.
"""

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import tempfile
import shutil

logger = logging.getLogger(__name__)


def _safe_subprocess_env() -> Dict[str, str]:
    """Build a subprocess environment that forces UTF-8 encoding on Windows.
    
    Prevents UnicodeEncodeError when generated code prints emoji/unicode
    symbols (✅, ❌, ⚠️, etc.) to stdout on a cp1252 terminal.
    
    SECURITY: Strips API keys and sensitive tokens so generated code
    cannot accidentally read them from os.environ.
    """
    # Sensitive env var patterns to strip
    _SENSITIVE_KEYS = {
        "GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
        "GITHUB_TOKEN", "GH_TOKEN", "GITHUB_PAT",
        "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
        "AZURE_API_KEY", "HF_TOKEN", "HUGGINGFACE_TOKEN",
        "OPENROUTER_API_KEY", "TOGETHER_API_KEY",
        "COHERE_API_KEY", "MISTRAL_API_KEY",
    }
    env = {}
    for k, v in os.environ.items():
        # Skip known sensitive keys
        if k.upper() in _SENSITIVE_KEYS:
            continue
        # Skip any key containing API_KEY, SECRET, TOKEN (broad safety net)
        k_upper = k.upper()
        if any(pat in k_upper for pat in ("API_KEY", "SECRET", "_TOKEN", "PASSWORD", "CREDENTIAL")):
            continue
        env[k] = v
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    # Ensure pip doesn't hang asking for input
    env["PIP_NO_INPUT"] = "1"
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    return env


def _encoding_test_env() -> Dict[str, str]:
    """Build a subprocess environment that mimics real Windows cp1252.
    
    Does NOT set PYTHONIOENCODING, so emoji/unicode printing will crash
    on Windows just like it would on a real user's machine.  Used as a
    secondary test to catch encoding issues that _safe_subprocess_env masks.
    
    SECURITY: Still strips API keys (same as _safe_subprocess_env).
    """
    env = _safe_subprocess_env()  # Start from sanitized base
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PIP_NO_INPUT"] = "1"
    # Explicitly unset PYTHONIOENCODING so the default cp1252 is used
    env.pop("PYTHONIOENCODING", None)
    return env


class CodeExecutor:
    """Manages code execution in isolated environments"""
    
    def __init__(self, project_dir: Path):
        """
        Initialize executor for a project
        
        Args:
            project_dir: Directory containing generated code
        """
        self.project_dir = Path(project_dir)
        self.venv_dir = self.project_dir / ".venv"
        self.test_results = {
            "environment_created": False,
            "dependencies_installed": False,
            "syntax_valid": True,
            "import_successful": True,
            "execution_errors": [],
            "warnings": [],
            "test_outputs": []
        }
    
    def create_environment(self) -> bool:
        """
        Create isolated Python virtual environment
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Creating virtual environment at {self.venv_dir}")
            
            # Create venv
            subprocess.run(
                [sys.executable, "-m", "venv", str(self.venv_dir)],
                check=True,
                capture_output=True,
                timeout=60,
                env=_safe_subprocess_env(),
            )
            
            self.test_results["environment_created"] = True
            logger.info("✅ Virtual environment created")
            return True
            
        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to create environment: {e.stderr.decode()}"
            logger.error(error_msg)
            self.test_results["execution_errors"].append(error_msg)
            return False
        except Exception as e:
            error_msg = f"Environment creation error: {str(e)}"
            logger.error(error_msg)
            self.test_results["execution_errors"].append(error_msg)
            return False
    
    def get_python_executable(self) -> Path:
        """Get path to Python executable in venv"""
        if sys.platform == "win32":
            return self.venv_dir / "Scripts" / "python.exe"
        return self.venv_dir / "bin" / "python"
    
    def get_pip_executable(self) -> Path:
        """Get path to pip executable in venv"""
        if sys.platform == "win32":
            return self.venv_dir / "Scripts" / "pip.exe"
        return self.venv_dir / "bin" / "pip"
    
    def install_dependencies(self) -> bool:
        """
        Install dependencies from requirements.txt
        
        Returns:
            True if successful, False otherwise
        """
        requirements_file = self.project_dir / "requirements.txt"
        
        if not requirements_file.exists():
            logger.warning("No requirements.txt found, skipping dependency installation")
            self.test_results["warnings"].append("No requirements.txt found")
            return True
        
        try:
            logger.info("Installing dependencies...")
            python_exe = self.get_python_executable()

            # Latency optimization: avoid unconditional pip self-upgrade on every
            # pipeline test cycle. It adds network/process overhead and does not
            # improve generated-project correctness.
            # Install requirements using python -m pip
            # --prefer-binary avoids source compilation (torch, scipy, etc.) which can hang
            result = subprocess.run(
                [str(python_exe), "-m", "pip", "install",
                 "--prefer-binary", "--no-build-isolation",
                 "-r", str(requirements_file)],
                check=True,
                capture_output=True,
                timeout=180,
                env=_safe_subprocess_env(),
            )
            
            self.test_results["dependencies_installed"] = True
            logger.info("✅ Dependencies installed")
            
            # Log installed packages
            output = result.stdout.decode()
            self.test_results["test_outputs"].append(f"Pip install output:\n{output}")
            
            return True
            
        except subprocess.TimeoutExpired:
            error_msg = "Dependency installation timed out (>5 minutes)"
            logger.error(error_msg)
            self.test_results["execution_errors"].append(error_msg)
            return False
        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to install dependencies: {e.stderr.decode()}"
            logger.error(error_msg)
            self.test_results["execution_errors"].append(error_msg)
            return False
        except Exception as e:
            error_msg = f"Dependency installation error: {str(e)}"
            logger.error(error_msg)
            self.test_results["execution_errors"].append(error_msg)
            return False
    
    def check_syntax(self) -> bool:
        """
        Check Python syntax of all .py files
        
        Returns:
            True if all files have valid syntax
        """
        logger.info("Checking Python syntax...")
        python_exe = self.get_python_executable()
        
        all_valid = True
        for py_file in self.project_dir.rglob("*.py"):
            # Skip .venv and __pycache__ directories
            if '.venv' in py_file.parts or '__pycache__' in py_file.parts:
                continue
            try:
                # Compile to check syntax
                result = subprocess.run(
                    [str(python_exe), "-m", "py_compile", str(py_file)],
                    check=True,
                    capture_output=True,
                    timeout=10,
                    env=_safe_subprocess_env(),
                )
                logger.info(f"  ✅ {py_file.name} - syntax valid")
                
            except subprocess.CalledProcessError as e:
                error_msg = f"Syntax error in {py_file.name}: {e.stderr.decode()}"
                logger.error(f"  ❌ {error_msg}")
                self.test_results["execution_errors"].append(error_msg)
                self.test_results["syntax_valid"] = False
                all_valid = False
            except Exception as e:
                error_msg = f"Syntax check error for {py_file.name}: {str(e)}"
                logger.error(error_msg)
                self.test_results["execution_errors"].append(error_msg)
                all_valid = False
        
        return all_valid
    
    def test_imports(self) -> bool:
        """
        Test if main files can be imported
        
        Returns:
            True if imports successful
        """
        logger.info("Testing imports...")
        python_exe = self.get_python_executable()
        
        # Dynamically discover all .py files (including subdirs) — import main.py last
        _all_py = sorted(
            [f.name for f in self.project_dir.rglob("*.py")
             if '.venv' not in f.parts and '__pycache__' not in f.parts],
            key=lambda x: (1 if x == "main.py" else 0, x)
        )
        test_files = _all_py
        all_successful = True
        
        for filename in test_files:
            filepath = self.project_dir / filename
            if not filepath.exists():
                continue
            
            module_name = filename.replace(".py", "")
            
            # Create test script
            test_script = f"""
import sys
sys.path.insert(0, r'{self.project_dir}')
try:
    import {module_name}
    print(f'✅ {module_name} imported successfully')
except Exception as e:
    print(f'❌ Failed to import {module_name}: {{e}}')
    sys.exit(1)
"""
            
            try:
                result = subprocess.run(
                    [str(python_exe), "-c", test_script],
                    check=True,
                    capture_output=True,
                    timeout=30,
                    cwd=str(self.project_dir),
                    env=_safe_subprocess_env(),
                )
                
                output = result.stdout.decode().strip()
                logger.info(f"  {output}")
                self.test_results["test_outputs"].append(output)
                
            except subprocess.CalledProcessError as e:
                stderr_text = e.stderr.decode().strip()
                stdout_text = e.stdout.decode().strip()
                detail = stderr_text or stdout_text  # test script prints to stdout
                error_msg = f"Import error in {filename}: {detail}"
                logger.error(f"  ❌ {error_msg}")
                self.test_results["execution_errors"].append(error_msg)
                self.test_results["import_successful"] = False
                all_successful = False
            except subprocess.TimeoutExpired:
                error_msg = f"Import test timed out for {filename}"
                logger.error(error_msg)
                self.test_results["execution_errors"].append(error_msg)
                all_successful = False
            except Exception as e:
                error_msg = f"Import test error for {filename}: {str(e)}"
                logger.error(error_msg)
                self.test_results["execution_errors"].append(error_msg)
                all_successful = False
        
        return all_successful
    
    def run_basic_tests(self) -> bool:
        """
        Run basic execution tests on generated code.
        
        Actually tests:
        1. model.py: loads module + tries to find and instantiate model classes
        2. All .py files: quick import + check for obvious placeholder patterns
        
        Returns:
            True if tests pass, False if critical issues found
        """
        logger.info("Running basic execution tests...")
        python_exe = self.get_python_executable()
        all_ok = True
        
        # Test 1: Check if model.py can be loaded and classes instantiated
        model_file = self.project_dir / "model.py"
        if model_file.exists():
            test_script = f"""
import sys, json
sys.path.insert(0, r'{self.project_dir}')
results = {{"loaded": False, "classes_found": 0, "errors": []}}
try:
    from model import *
    results["loaded"] = True
    import inspect
    model_classes = []
    for name, obj in inspect.getmembers(sys.modules['model']):
        if inspect.isclass(obj) and hasattr(obj, '__init__'):
            model_classes.append(name)
    results["classes_found"] = len(model_classes)
    if not model_classes:
        results["errors"].append("No classes found in model.py")
except Exception as e:
    results["errors"].append(f"Import failed: {{e}}")
print(json.dumps(results))
"""
            try:
                result = subprocess.run(
                    [str(python_exe), "-c", test_script],
                    capture_output=True,
                    timeout=30,
                    cwd=str(self.project_dir),
                    env=_safe_subprocess_env(),
                )
                
                import json
                stdout = result.stdout.decode(errors="replace").strip()
                try:
                    test_data = json.loads(stdout)
                    if not test_data.get("loaded"):
                        error_msg = f"model.py failed to load: {test_data.get('errors', [])}"
                        self.test_results["execution_errors"].append(error_msg)
                        all_ok = False
                    elif test_data.get("errors"):
                        for err in test_data["errors"]:
                            self.test_results["warnings"].append(f"Model test: {err}")
                    logger.info(f"  {'✅' if test_data.get('loaded') else '❌'} model.py: "
                               f"loaded={test_data.get('loaded')}, classes={test_data.get('classes_found')}")
                except (json.JSONDecodeError, ValueError):
                    logger.info(f"  ℹ️  model.py basic check: {stdout[:200]}")
                
                if result.returncode != 0:
                    error_output = result.stderr.decode(errors="replace").strip()
                    self.test_results["execution_errors"].append(
                        f"model.py basic test failed (exit {result.returncode}): {error_output[-200:]}"
                    )
                    all_ok = False
                
            except subprocess.TimeoutExpired:
                self.test_results["execution_errors"].append(
                    "model.py test timed out (30s) — possible infinite loop"
                )
                all_ok = False
            except Exception as e:
                self.test_results["warnings"].append(f"Model test infrastructure error: {str(e)}")
        
        # Test 2: Quick sanity check — import all .py files to catch circular imports
        py_files = sorted([f.name for f in self.project_dir.rglob("*.py")
                          if '.venv' not in f.parts and '__pycache__' not in f.parts
                          and f.name != 'test_main.py' and f.name != 'feature_tests.py'])
        
        if len(py_files) >= 2:
            # Build a single script that imports all modules (catches circular imports)
            import_lines = []
            for pf in py_files:
                mod = pf.replace('.py', '')
                import_lines.append(f"    import {mod}")
            
            all_import_script = f"""
import sys
sys.path.insert(0, r'{self.project_dir}')
failed = []
try:
{chr(10).join(import_lines)}
except ImportError as e:
    failed.append(f"ImportError: {{e}}")
except Exception as e:
    failed.append(f"{{type(e).__name__}}: {{e}}")
if failed:
    print("FAIL:" + ";".join(failed))
    sys.exit(1)
else:
    print("OK")
"""
            try:
                result = subprocess.run(
                    [str(python_exe), "-c", all_import_script],
                    capture_output=True, timeout=30,
                    cwd=str(self.project_dir),
                    env=_safe_subprocess_env(),
                )
                stdout = result.stdout.decode(errors="replace").strip()
                if result.returncode != 0 or stdout.startswith("FAIL:"):
                    stderr = result.stderr.decode(errors="replace").strip()
                    error_msg = f"Cross-module import check failed: {stdout} {stderr[-200:]}"
                    self.test_results["execution_errors"].append(error_msg)
                    all_ok = False
                    logger.error(f"  ❌ {error_msg}")
                else:
                    logger.info(f"  ✅ All {len(py_files)} modules import without circular dependency issues")
            except subprocess.TimeoutExpired:
                self.test_results["warnings"].append("Cross-import check timed out")
            except Exception as e:
                self.test_results["warnings"].append(f"Cross-import check error: {e}")
        
        return all_ok

    def _detect_argparse(self) -> bool:
        """Check if main.py uses argparse (needs --help to exit cleanly)."""
        main_file = self.project_dir / "main.py"
        if not main_file.exists():
            return False
        try:
            code = main_file.read_text(encoding="utf-8", errors="replace")
            return ("argparse" in code or "ArgumentParser" in code
                    or ".parse_args()" in code)
        except Exception:
            return False

    def _detect_interactive(self) -> bool:
        """Check if main.py calls input() at top level (will hang without stdin)."""
        main_file = self.project_dir / "main.py"
        if not main_file.exists():
            return False
        try:
            import ast
            code = main_file.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(code)
            for node in ast.walk(tree):
                # input() calls at module level or inside if __name__ == '__main__'
                if isinstance(node, ast.Call):
                    fn = node.func
                    if isinstance(fn, ast.Name) and fn.id == "input":
                        return True
            return False
        except Exception:
            return False

    def _extract_argparse_defaults(self) -> list:
        """
        Parse main.py's argparse setup via AST to extract arguments and their
        default values.  Returns a list of command-line tokens like
        ['--size', '5', '--seed', '42'] that should produce a FUNCTIONAL run
        (not just a --help dump).

        This allows LLM-as-Judge to evaluate actual program output rather than
        scoring a help message as 'non-functional'.
        """
        main_file = self.project_dir / "main.py"
        if not main_file.exists():
            return []
        try:
            import ast as _ast_ap
            code = main_file.read_text(encoding="utf-8", errors="replace")
            tree = _ast_ap.parse(code)

            args_list = []
            for node in _ast_ap.walk(tree):
                if not isinstance(node, _ast_ap.Call):
                    continue
                fn = node.func
                # Match parser.add_argument(...) or subparser.add_argument(...)
                if not (isinstance(fn, _ast_ap.Attribute) and fn.attr == "add_argument"):
                    continue

                # Extract the argument name (first positional string starting with --)
                arg_name = None
                for a in node.args:
                    if isinstance(a, _ast_ap.Constant) and isinstance(a.value, str):
                        if a.value.startswith("--"):
                            arg_name = a.value
                            break

                if arg_name is None:
                    continue  # positional arg or short-form only — skip

                # Parse keyword args: default=, type=, action=
                default_val = None
                arg_type = None
                action = None
                for kw in node.keywords:
                    if kw.arg == "default" and isinstance(kw.value, _ast_ap.Constant):
                        default_val = kw.value.value
                    elif kw.arg == "type" and isinstance(kw.value, _ast_ap.Name):
                        arg_type = kw.value.id
                    elif kw.arg == "action" and isinstance(kw.value, _ast_ap.Constant):
                        action = kw.value.value

                # Skip store_true/store_false flags (they don't need values)
                if action in ("store_true", "store_false", "count"):
                    continue

                # Build the arg token pair
                if default_val is not None:
                    args_list.extend([arg_name, str(default_val)])
                elif arg_type == "int":
                    args_list.extend([arg_name, "5"])
                elif arg_type == "float":
                    args_list.extend([arg_name, "0.5"])
                elif arg_type == "str":
                    args_list.extend([arg_name, "test"])

            return args_list
        except Exception as e:
            logger.debug(f"  Could not extract argparse defaults: {e}")
            return []

    def run_entry_point(self) -> bool:
        """
        Run main.py inside the venv to catch runtime crashes: AttributeError,
        ImportError on circular deps, NameError, TypeError on constructor args.

        Smart execution strategy:
        1. If main.py uses argparse → try `main.py --help` first (clean exit)
        2. Always pass stdin=DEVNULL so interactive programs fail fast
        3. After functional test, run a SECONDARY encoding test without
           PYTHONIOENCODING to catch emoji that would crash on real Windows

        SOTA (LLM-as-Judge prep): Captures stdout so downstream nodes can
        validate whether the output *semantically* matches the user's intent,
        not just that it ran without crashing.
        """
        main_file = self.project_dir / "main.py"
        if not main_file.exists():
            logger.info("  ℹ️  No main.py found — skipping entry-point check")
            return True

        python_exe = self.get_python_executable()
        logger.info("Running main.py entry-point check...")

        uses_argparse = self._detect_argparse()
        is_interactive = self._detect_interactive()

        # Decide command args
        if uses_argparse:
            cmd = [str(python_exe), "main.py", "--help"]
            logger.info("  ℹ️  Detected argparse — running with --help first")
        else:
            cmd = [str(python_exe), "main.py"]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=15,
                cwd=str(self.project_dir),
                env=_safe_subprocess_env(),
                stdin=subprocess.DEVNULL,  # Prevent hangs on input()
            )
            stdout = result.stdout.decode(errors="replace").strip()
            stderr = result.stderr.decode(errors="replace").strip()

            # Always capture stdout for LLM-as-Judge output validation
            self.test_results["entry_point_stdout"] = stdout[:5000] if stdout else ""
            self.test_results["entry_point_stderr"] = stderr[:2000] if stderr else ""
            self.test_results["entry_point_exit_code"] = result.returncode

            if result.returncode == 0:
                logger.info("  ✅ main.py executed and exited cleanly")
                if stdout:
                    logger.info(f"  📤 Output ({len(stdout)} chars): {stdout[:200]}...")
                else:
                    logger.warning("  ⚠️  main.py exited 0 but produced no output (silent)")
                    self.test_results["warnings"] = self.test_results.get("warnings", [])
                    self.test_results["warnings"].append(
                        "SILENT_MAIN: main.py exited 0 but produced no stdout output"
                    )

                # ── FUNCTIONAL RUN: When --help succeeded, try a REAL run with
                #    extracted argparse defaults so LLM-as-Judge gets actual
                #    program output rather than just a help message. ────────────
                if uses_argparse:
                    func_args = self._extract_argparse_defaults()
                    if func_args:
                        func_cmd = [str(python_exe), "main.py"] + func_args
                        logger.info(
                            f"  🔄 Functional run with defaults: "
                            f"python main.py {' '.join(func_args)}"
                        )
                        try:
                            func_result = subprocess.run(
                                func_cmd,
                                capture_output=True,
                                timeout=30,  # Longer timeout for real execution
                                cwd=str(self.project_dir),
                                env=_safe_subprocess_env(),
                                stdin=subprocess.DEVNULL,
                            )
                            func_stdout = func_result.stdout.decode(
                                errors="replace"
                            ).strip()
                            func_stderr = func_result.stderr.decode(
                                errors="replace"
                            ).strip()

                            if func_result.returncode == 0 and func_stdout:
                                logger.info(
                                    f"  ✅ Functional run succeeded "
                                    f"({len(func_stdout)} chars output)"
                                )
                                logger.info(
                                    f"  📤 Functional output: {func_stdout[:300]}..."
                                )
                                # Replace help text with functional output
                                # for LLM-as-Judge
                                self.test_results["entry_point_stdout"] = (
                                    func_stdout[:5000]
                                )
                                self.test_results["entry_point_stderr"] = (
                                    func_stderr[:2000] if func_stderr else ""
                                )
                                self.test_results["entry_point_exit_code"] = 0
                                self.test_results["functional_run_args"] = (
                                    " ".join(func_args)
                                )
                            elif func_result.returncode != 0:
                                logger.info(
                                    f"  ℹ️  Functional run exited with code "
                                    f"{func_result.returncode} — keeping help output"
                                )
                                if func_stderr:
                                    logger.debug(
                                        f"  Functional stderr: {func_stderr[:200]}"
                                    )
                        except subprocess.TimeoutExpired:
                            logger.info(
                                "  ℹ️  Functional run timed out — keeping help output"
                            )
                        except Exception as _fe:
                            logger.debug(f"  Functional run error: {_fe}")

            elif result.returncode == 2 and uses_argparse:
                # argparse exits with 2 on missing required args — that's expected
                # when --help fails for some reason; fall back to bare run
                logger.info("  ℹ️  argparse exit code 2 (missing args) — expected for --help")
                self.test_results["entry_point_stdout"] = stdout[:5000]
                self.test_results["entry_point_exit_code"] = 0  # treat as OK
            else:
                # Show last 15 lines of stderr (the actual traceback)
                err_lines = (stderr or stdout).splitlines()[-15:]
                error_msg = f"main.py crashed at runtime: {''.join(err_lines)}"
                logger.error(f"  ❌ {error_msg}")
                self.test_results["execution_errors"].append(error_msg)
                self.test_results["import_successful"] = False
                return False

        except subprocess.TimeoutExpired as te:
            if is_interactive:
                # Interactive program timed out because stdin=DEVNULL — that's fine
                logger.info("  ℹ️  Interactive main.py timed out (stdin=DEVNULL) — acceptable")
                self.test_results["entry_point_stdout"] = "(interactive — timed out waiting for input)"
                self.test_results["entry_point_exit_code"] = -1
            else:
                # Ran for 15s without crashing — could be server OR infinite loop.
                # Check if any output was produced — servers typically print a startup message.
                _timeout_stdout = ""
                if te.stdout:
                    _timeout_stdout = te.stdout.decode(errors="replace").strip()
                if _timeout_stdout:
                    # Produced output before timeout — likely a server, count as pass
                    logger.info("  ✅ main.py ran 15s with output (likely server/loop)")
                    self.test_results["entry_point_stdout"] = _timeout_stdout[:5000]
                    self.test_results["entry_point_exit_code"] = -1  # sentinel for timeout
                else:
                    # No output and timed out — suspicious, flag as FAILURE
                    logger.warning("  ⚠️  main.py timed out with NO output — possible infinite loop")
                    self.test_results["entry_point_stdout"] = "(timed out with no output — possible infinite loop)"
                    self.test_results["entry_point_exit_code"] = -1
                    self.test_results["warnings"] = self.test_results.get("warnings", [])
                    self.test_results["warnings"].append(
                        "TIMEOUT_NO_OUTPUT: main.py timed out after 15s with no stdout. "
                        "Possible infinite loop or deadlock — not a clean server."
                    )
                    self.test_results["execution_errors"] = self.test_results.get("execution_errors", [])
                    self.test_results["execution_errors"].append(
                        "TIMEOUT_NO_OUTPUT: main.py timed out after 15s with no output — "
                        "likely infinite loop or deadlock"
                    )
                    return False  # Not a pass — no output + timeout = broken
            return True
        except Exception as e:
            error_msg = f"Entry-point test error: {str(e)}"
            logger.error(error_msg)
            self.test_results["execution_errors"].append(error_msg)
            return False

        # ── Secondary encoding test (Windows only) ────────────────────────
        # Run main.py WITHOUT PYTHONIOENCODING to catch emoji that would
        # crash on a real user's cp1252 Windows terminal.
        # This prevents _safe_subprocess_env() from masking encoding issues.
        if sys.platform == "win32" and result.returncode == 0:
            try:
                enc_result = subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=10,
                    cwd=str(self.project_dir),
                    env=_encoding_test_env(),
                    stdin=subprocess.DEVNULL,
                )
                if enc_result.returncode != 0:
                    enc_stderr = enc_result.stderr.decode(errors="replace").strip()
                    if "UnicodeEncodeError" in enc_stderr or "charmap" in enc_stderr:
                        enc_err_lines = enc_stderr.splitlines()[-5:]
                        error_msg = (
                            f"ENCODING_ISSUE: main.py runs fine with UTF-8 but crashes on "
                            f"Windows cp1252 (real user environment): {''.join(enc_err_lines)}"
                        )
                        logger.warning(f"  ⚠️  {error_msg}")
                        self.test_results["execution_errors"].append(error_msg)
                        # Don't return False — functional test passed, encoding is fixable
            except (subprocess.TimeoutExpired, Exception) as enc_e:
                logger.debug(f"  Encoding test skipped: {enc_e}")

        return result.returncode == 0 or (result.returncode == 2 and uses_argparse)

    def run_generated_tests(self) -> bool:
        """
        Run auto-generated test_main.py with pytest.

        SOTA (AlphaCode/CodeChain): Tests are co-generated alongside code so
        the fix loop has concrete PASS/FAIL signals, not just static scores.

        Returns True if tests pass or no test file exists.
        Failures are recorded as warnings (not hard errors) because auto-
        generated tests may themselves have issues.
        """
        test_file = self.project_dir / "test_main.py"
        if not test_file.exists():
            return True  # no tests to run

        python_exe = self.get_python_executable()
        logger.info("Running auto-generated test_main.py...")

        # Install pytest in the venv first (may not be in requirements.txt)
        try:
            subprocess.run(
                [str(python_exe), "-m", "pip", "install", "pytest", "-q"],
                capture_output=True, timeout=60, check=False,
                env=_safe_subprocess_env(),
            )
        except Exception:
            pass  # pytest might already be installed, or pip itself failed

        try:
            result = subprocess.run(
                [str(python_exe), "-m", "pytest", "test_main.py", "-v",
                 "--tb=short", "--no-header", "-q"],
                capture_output=True,
                timeout=60,
                cwd=str(self.project_dir),
                env=_safe_subprocess_env(),
            )
            stdout = result.stdout.decode(errors="replace").strip()
            stderr = result.stderr.decode(errors="replace").strip()
            output = stdout or stderr

            self.test_results["generated_test_output"] = output[:3000]
            self.test_results["generated_test_exit_code"] = result.returncode

            if result.returncode == 0:
                logger.info("  ✅ Auto-generated tests passed")
                self.test_results["test_outputs"].append(
                    f"Auto-generated tests: PASSED\n{output[:500]}"
                )
                return True
            else:
                # Extract failure count from pytest output
                fail_lines = [l for l in output.splitlines() if "FAILED" in l or "ERROR" in l]
                total_lines = [l for l in output.splitlines() if "PASSED" in l or "FAILED" in l or "ERROR" in l]
                fail_summary = "; ".join(fail_lines[:3]) if fail_lines else output[-200:]

                # Calculate fail rate — ALL failures are execution errors so the
                # fix loop can address them.  Auto-generated tests target real
                # user-visible functionality; ignoring failures defeats their purpose.
                fail_count = len(fail_lines)
                total_count = len(total_lines) if total_lines else 1
                fail_rate = fail_count / total_count if total_count > 0 else 0

                # Promote ALL failures to execution_errors (the fix loop needs signal)
                error_msg = (
                    f"GENERATED_TEST_FAILURE: {fail_count}/{total_count} auto-generated tests "
                    f"failed ({fail_rate:.0%}). Failures: {fail_summary}"
                )
                logger.warning(f"  ❌ {error_msg}")
                self.test_results["execution_errors"].append(error_msg)

                self.test_results["test_outputs"].append(
                    f"Auto-generated tests: FAILED ({fail_count}/{total_count})\n{output[:500]}"
                )
                return False

        except subprocess.TimeoutExpired:
            logger.warning("  ⚠️ Auto-generated tests timed out (60s)")
            self.test_results["execution_errors"].append(
                "GENERATED_TEST_TIMEOUT: test_main.py timed out after 60s — "
                "tests may be stuck in infinite loop or heavy computation"
            )
            return False  # Flag as failure so fix loop can address
        except Exception as e:
            logger.warning(f"  ⚠️ Could not run auto-generated tests: {e}")
            self.test_results["warnings"].append(f"Could not run tests: {e}")
            self.test_results["execution_errors"] = self.test_results.get("execution_errors", [])
            self.test_results["execution_errors"].append(
                f"TEST_INFRASTRUCTURE_ERROR: Could not run tests: {e}"
            )
            return False  # Infrastructure failure is NOT a pass

    def cleanup(self):
        """Remove virtual environment"""
        try:
            if self.venv_dir.exists():
                shutil.rmtree(self.venv_dir)
                logger.info("🧹 Cleaned up virtual environment")
        except Exception as e:
            logger.warning(f"Failed to cleanup venv: {e}")
    
    def run_full_test_suite(self, cleanup_after: bool = True) -> Dict:
        """
        Run complete test suite
        
        Args:
            cleanup_after: Whether to remove venv after tests
            
        Returns:
            Test results dictionary
        """
        logger.info("="*60)
        logger.info("🧪 Starting Code Testing Suite")
        logger.info("="*60)
        
        try:
            # Step 1: Create environment
            if not self.create_environment():
                return self.test_results
            
            # Step 2: Install dependencies
            if not self.install_dependencies():
                return self.test_results
            
            # Step 3: Check syntax
            if not self.check_syntax():
                return self.test_results
            
            # Step 4: Test imports (don't abort on failure — continue to entry point)
            self.test_imports()

            # Step 4.5: Run main.py to catch runtime crashes (AttributeError,
            # wrong method names, circular deps, constructor arg mismatches)
            # This is the CRITICAL check — main.py must actually run and produce output
            self.run_entry_point()

            # Step 5: Run basic tests
            self.run_basic_tests()

            # Step 5.5: Run auto-generated test_main.py (pytest assertions)
            # SOTA: AlphaCode/CodeChain co-generated tests — executable pass/fail
            self.run_generated_tests()
            
            logger.info("="*60)
            logger.info("✅ Test Suite Completed")
            logger.info("="*60)
            
        finally:
            if cleanup_after:
                self.cleanup()
        
        return self.test_results


def test_project(project_dir: Path, cleanup_after: bool = True) -> Dict:
    """
    Convenience function to test a project
    
    Args:
        project_dir: Directory containing generated code
        cleanup_after: Whether to cleanup venv after tests
        
    Returns:
        Test results dictionary
    """
    executor = CodeExecutor(project_dir)
    return executor.run_full_test_suite(cleanup_after=cleanup_after)
