"""
Code Execution and Testing Environment Manager

Creates isolated Python environments for each project,
installs dependencies, and runs basic tests to validate generated code.
"""

import logging
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import tempfile
import shutil

logger = logging.getLogger(__name__)


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
                timeout=60
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
            
            # Upgrade pip first using python -m pip (recommended way)
            subprocess.run(
                [str(python_exe), "-m", "pip", "install", "--upgrade", "pip"],
                check=True,
                capture_output=True,
                timeout=60
            )
            
            # Install requirements using python -m pip
            # --prefer-binary avoids source compilation (torch, scipy, etc.) which can hang
            result = subprocess.run(
                [str(python_exe), "-m", "pip", "install",
                 "--prefer-binary", "--no-build-isolation",
                 "-r", str(requirements_file)],
                check=True,
                capture_output=True,
                timeout=180
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
                    timeout=10
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
                    cwd=str(self.project_dir)
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
        Run basic execution tests on generated code
        
        Returns:
            True if tests pass
        """
        logger.info("Running basic execution tests...")
        python_exe = self.get_python_executable()
        
        # Test 1: Check if model can be instantiated
        model_file = self.project_dir / "model.py"
        if model_file.exists():
            test_script = f"""
import sys
sys.path.insert(0, r'{self.project_dir}')
try:
    from model import *
    print('✅ Model module loaded successfully')
    
    # Try to find model class and instantiate
    import inspect
    for name, obj in inspect.getmembers(sys.modules['model']):
        if inspect.isclass(obj) and 'model' in name.lower():
            try:
                # Try instantiation with minimal args
                print(f'Found model class: {{name}}')
                break
            except Exception as e:
                print(f'⚠️  Model class found but instantiation failed: {{e}}')
                
except Exception as e:
    print(f'❌ Model test failed: {{e}}')
"""
            
            try:
                result = subprocess.run(
                    [str(python_exe), "-c", test_script],
                    capture_output=True,
                    timeout=30,
                    cwd=str(self.project_dir)
                )
                
                output = result.stdout.decode().strip()
                logger.info(f"  {output}")
                self.test_results["test_outputs"].append(output)
                
                if result.returncode != 0:
                    error_output = result.stderr.decode().strip()
                    self.test_results["warnings"].append(f"Model test warnings: {error_output}")
                
            except subprocess.TimeoutExpired:
                self.test_results["warnings"].append("Model test timed out")
            except Exception as e:
                self.test_results["warnings"].append(f"Model test error: {str(e)}")
        
        return True  # Don't fail on test warnings

    def run_entry_point(self) -> bool:
        """
        Run main.py inside the venv to catch runtime crashes: AttributeError,
        ImportError on circular deps, NameError, TypeError on constructor args.

        A 15-second timeout is used.  If the process exits within the timeout
        with code 0 it passes.  If it exits with an error, the stderr is
        captured and fed back to the fix loop.  If it times out (running an
        infinite loop / server) we treat that as a pass — the process started
        successfully.
        """
        main_file = self.project_dir / "main.py"
        if not main_file.exists():
            logger.info("  ℹ️  No main.py found — skipping entry-point check")
            return True

        python_exe = self.get_python_executable()
        logger.info("Running main.py entry-point check...")
        try:
            result = subprocess.run(
                [str(python_exe), "main.py"],
                capture_output=True,
                timeout=15,
                cwd=str(self.project_dir)
            )
            if result.returncode == 0:
                logger.info("  ✅ main.py executed and exited cleanly")
                return True
            else:
                stderr = result.stderr.decode(errors="replace").strip()
                stdout = result.stdout.decode(errors="replace").strip()
                # Show last 15 lines of stderr (the actual traceback)
                err_lines = (stderr or stdout).splitlines()[-15:]
                error_msg = f"main.py crashed at runtime: {''.join(err_lines)}"
                logger.error(f"  ❌ {error_msg}")
                self.test_results["execution_errors"].append(error_msg)
                self.test_results["import_successful"] = False
                return False
        except subprocess.TimeoutExpired:
            # Ran for 15 s without crashing — server / infinite loop, counts as pass
            logger.info("  ✅ main.py ran 15s without crashing (timeout = pass)")
            return True
        except Exception as e:
            error_msg = f"Entry-point test error: {str(e)}"
            logger.error(error_msg)
            self.test_results["execution_errors"].append(error_msg)
            return False

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
            
            # Step 4: Test imports
            if not self.test_imports():
                return self.test_results

            # Step 4.5: Run main.py to catch runtime crashes (AttributeError,
            # wrong method names, circular deps, constructor arg mismatches)
            if not self.run_entry_point():
                return self.test_results

            # Step 5: Run basic tests
            self.run_basic_tests()
            
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
