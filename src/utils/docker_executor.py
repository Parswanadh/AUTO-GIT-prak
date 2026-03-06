"""
Docker Sandbox Executor — Run generated code safely in Docker containers.

Replaces unsafe local subprocess execution with Docker containers that have:
  - CPU limits (1 core)
  - Memory limits (512MB)
  - Network isolation (--network=none)
  - Filesystem isolation
  - Auto-cleanup after execution
  - Configurable timeout

Falls back to local subprocess if Docker is not available.

Requirements:
  - Docker installed and running (docker desktop or docker engine)
  - No paid services needed — fully local

Usage:
    executor = DockerSandboxExecutor(project_dir)
    result = executor.run_sandboxed("main.py", timeout=30)
    print(result.stdout, result.returncode)
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("docker_executor")

# Default Docker image for Python code execution
DEFAULT_IMAGE = "python:3.10-slim"
# Fallback images if the default isn't available
FALLBACK_IMAGES = ["python:3.11-slim", "python:3.9-slim", "python:3-slim"]


@dataclass
class SandboxResult:
    """Result of a sandboxed code execution."""
    stdout: str = ""
    stderr: str = ""
    returncode: int = -1
    timed_out: bool = False
    used_docker: bool = False
    execution_time_ms: int = 0
    error: str = ""


def is_docker_available() -> bool:
    """Check if Docker is installed and the daemon is running."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        return False


def ensure_docker_image(image: str = DEFAULT_IMAGE) -> bool:
    """Pull the Docker image if not already available.
    
    Returns True if image is available, False if pull failed.
    """
    try:
        # Check if image exists locally
        result = subprocess.run(
            ["docker", "image", "inspect", image],
            capture_output=True,
            timeout=10,
        )
        if result.returncode == 0:
            return True
        
        # Pull the image
        logger.info(f"  🐳 Pulling Docker image: {image}")
        result = subprocess.run(
            ["docker", "pull", image],
            capture_output=True,
            timeout=300,  # 5 minutes for pull
        )
        return result.returncode == 0
    except Exception as e:
        logger.warning(f"  Docker image check failed: {e}")
        return False


class DockerSandboxExecutor:
    """Execute code in Docker containers with resource limits and isolation."""
    
    def __init__(
        self,
        project_dir: Path,
        image: str = DEFAULT_IMAGE,
        cpu_limit: float = 1.0,       # CPU cores
        memory_limit: str = "512m",    # Memory limit
        network: str = "none",         # Network mode (none = isolated)
        timeout: int = 60,             # Default timeout in seconds
    ):
        self.project_dir = Path(project_dir)
        self.image = image
        self.cpu_limit = cpu_limit
        self.memory_limit = memory_limit
        self.network = network
        self.timeout = timeout
        self._docker_available: Optional[bool] = None
    
    @property
    def docker_available(self) -> bool:
        """Cached check for Docker availability."""
        if self._docker_available is None:
            self._docker_available = is_docker_available()
            if self._docker_available:
                logger.info("  🐳 Docker is available — using container sandbox")
            else:
                logger.info("  ⚠️ Docker not available — falling back to local subprocess")
        return self._docker_available
    
    def run_sandboxed(
        self,
        script: str = "main.py",
        args: Optional[List[str]] = None,
        timeout: Optional[int] = None,
        install_deps: bool = True,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> SandboxResult:
        """Run a Python script in a sandboxed environment.
        
        Tries Docker first, falls back to local subprocess.
        
        Args:
            script: Python file to run (relative to project_dir)
            args: Command-line arguments
            timeout: Override default timeout
            install_deps: Whether to pip install requirements.txt first
            env_vars: Additional environment variables
            
        Returns:
            SandboxResult with stdout, stderr, returncode
        """
        timeout = timeout or self.timeout
        args = args or []
        
        if self.docker_available:
            return self._run_in_docker(script, args, timeout, install_deps, env_vars)
        else:
            return self._run_local(script, args, timeout, install_deps, env_vars)
    
    def _run_in_docker(
        self,
        script: str,
        args: List[str],
        timeout: int,
        install_deps: bool,
        env_vars: Optional[Dict[str, str]],
    ) -> SandboxResult:
        """Run code inside a Docker container."""
        import time as _time
        
        result = SandboxResult(used_docker=True)
        
        # Ensure image is available
        if not ensure_docker_image(self.image):
            # Try fallback images
            image_found = False
            for fallback in FALLBACK_IMAGES:
                if ensure_docker_image(fallback):
                    self.image = fallback
                    image_found = True
                    break
            if not image_found:
                logger.warning("  No Docker Python image available — falling back to local")
                return self._run_local(script, args, timeout, install_deps, env_vars)
        
        # Build the run command inside the container
        container_workdir = "/app"
        
        # Build setup + run script that runs inside the container
        setup_commands = []
        if install_deps:
            req_file = self.project_dir / "requirements.txt"
            if req_file.exists():
                setup_commands.append(
                    "pip install --no-cache-dir --prefer-binary "
                    "-r /app/requirements.txt 2>/dev/null || true"
                )
        
        run_cmd = f"python /app/{script}"
        if args:
            run_cmd += " " + " ".join(f'"{a}"' if " " in a else a for a in args)
        
        full_script = " && ".join(setup_commands + [run_cmd]) if setup_commands else run_cmd
        
        # Build Docker command
        docker_cmd = [
            "docker", "run",
            "--rm",                              # Auto-remove container
            f"--cpus={self.cpu_limit}",          # CPU limit
            f"--memory={self.memory_limit}",     # Memory limit
            f"--network={self.network}",         # Network isolation
            "--read-only",                       # Read-only filesystem
            "--tmpfs", "/tmp:rw,size=100m",      # Writable /tmp (limited)
            "--tmpfs", "/root/.cache:rw,size=200m",  # pip cache
            "-w", container_workdir,             # Working directory
            "-v", f"{self.project_dir.resolve()}:{container_workdir}:ro",  # Mount project read-only
        ]
        
        # Add environment variables
        docker_cmd.extend(["-e", "PYTHONIOENCODING=utf-8"])
        docker_cmd.extend(["-e", "PYTHONDONTWRITEBYTECODE=1"])
        if env_vars:
            for k, v in env_vars.items():
                docker_cmd.extend(["-e", f"{k}={v}"])
        
        # If we need to install deps, we can't use read-only + need writable mount
        if install_deps and (self.project_dir / "requirements.txt").exists():
            # Re-build with writable mount for pip install
            docker_cmd = [
                "docker", "run",
                "--rm",
                f"--cpus={self.cpu_limit}",
                f"--memory={self.memory_limit}",
                f"--network=bridge",  # Need network for pip install
                "-w", container_workdir,
                "-v", f"{self.project_dir.resolve()}:{container_workdir}:ro",
                "--tmpfs", "/tmp:rw,size=200m",
                "-e", "PYTHONIOENCODING=utf-8",
                "-e", "PYTHONDONTWRITEBYTECODE=1",
                "-e", "PIP_NO_INPUT=1",
            ]
            if env_vars:
                for k, v in env_vars.items():
                    docker_cmd.extend(["-e", f"{k}={v}"])
        
        docker_cmd.extend([self.image, "sh", "-c", full_script])
        
        start_time = _time.monotonic()
        try:
            proc = subprocess.run(
                docker_cmd,
                capture_output=True,
                timeout=timeout + 30,  # Extra 30s for container startup
                stdin=subprocess.DEVNULL,
            )
            
            result.stdout = proc.stdout.decode(errors="replace").strip()
            result.stderr = proc.stderr.decode(errors="replace").strip()
            result.returncode = proc.returncode
            result.execution_time_ms = int((_time.monotonic() - start_time) * 1000)
            
            logger.info(
                f"  🐳 Docker run completed: exit={result.returncode}, "
                f"time={result.execution_time_ms}ms, "
                f"stdout={len(result.stdout)} chars"
            )
            
        except subprocess.TimeoutExpired as te:
            result.timed_out = True
            result.execution_time_ms = int((_time.monotonic() - start_time) * 1000)
            result.stdout = te.stdout.decode(errors="replace").strip() if te.stdout else ""
            result.stderr = te.stderr.decode(errors="replace").strip() if te.stderr else ""
            result.error = f"Docker execution timed out after {timeout}s"
            logger.warning(f"  ⏰ Docker sandbox timed out ({timeout}s)")
            
            # Force kill any lingering container
            try:
                subprocess.run(
                    ["docker", "kill", "--signal=KILL"],
                    capture_output=True, timeout=5,
                )
            except Exception:
                pass
                
        except Exception as e:
            result.error = str(e)
            result.execution_time_ms = int((_time.monotonic() - start_time) * 1000)
            logger.error(f"  ❌ Docker sandbox error: {e}")
        
        return result
    
    def _run_local(
        self,
        script: str,
        args: List[str],
        timeout: int,
        install_deps: bool,
        env_vars: Optional[Dict[str, str]],
    ) -> SandboxResult:
        """Fallback: Run code locally with subprocess (less safe)."""
        import time as _time
        
        result = SandboxResult(used_docker=False)
        
        # Build safe environment
        env = self._safe_env()
        if env_vars:
            env.update(env_vars)
        
        # Install deps first if needed
        if install_deps:
            req_file = self.project_dir / "requirements.txt"
            if req_file.exists():
                try:
                    subprocess.run(
                        [sys.executable, "-m", "pip", "install", "--prefer-binary",
                         "-r", str(req_file)],
                        capture_output=True,
                        timeout=180,
                        env=env,
                    )
                except Exception as e:
                    logger.warning(f"  Dep install failed (local): {e}")
        
        cmd = [sys.executable, str(self.project_dir / script)] + args
        
        start_time = _time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                timeout=timeout,
                cwd=str(self.project_dir),
                env=env,
                stdin=subprocess.DEVNULL,
            )
            
            result.stdout = proc.stdout.decode(errors="replace").strip()
            result.stderr = proc.stderr.decode(errors="replace").strip()
            result.returncode = proc.returncode
            result.execution_time_ms = int((_time.monotonic() - start_time) * 1000)
            
        except subprocess.TimeoutExpired as te:
            result.timed_out = True
            result.execution_time_ms = int((_time.monotonic() - start_time) * 1000)
            result.stdout = te.stdout.decode(errors="replace").strip() if te.stdout else ""
            result.stderr = te.stderr.decode(errors="replace").strip() if te.stderr else ""
            result.error = f"Local execution timed out after {timeout}s"
            
        except Exception as e:
            result.error = str(e)
            result.execution_time_ms = int((_time.monotonic() - start_time) * 1000)
        
        return result
    
    @staticmethod
    def _safe_env() -> Dict[str, str]:
        """Build a subprocess environment with security stripping."""
        _SENSITIVE_PATTERNS = ("API_KEY", "SECRET", "_TOKEN", "PASSWORD", "CREDENTIAL")
        env = {}
        for k, v in os.environ.items():
            if any(pat in k.upper() for pat in _SENSITIVE_PATTERNS):
                continue
            env[k] = v
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PIP_NO_INPUT"] = "1"
        return env
    
    def run_all_tests(
        self,
        files: Dict[str, str],
        timeout: int = 60,
    ) -> SandboxResult:
        """Write all files to a temp dir and run main.py in the sandbox.
        
        This is the main entry point for the code_testing_node.
        
        Args:
            files: Dict of {filename: code_content}
            timeout: Execution timeout
            
        Returns:
            SandboxResult
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "project"
            tmp_path.mkdir()
            
            # Write all files
            for fname, content in files.items():
                fpath = tmp_path / fname
                fpath.parent.mkdir(parents=True, exist_ok=True)
                fpath.write_text(content, encoding="utf-8")
            
            # Create a fresh executor for this temp dir
            executor = DockerSandboxExecutor(
                project_dir=tmp_path,
                image=self.image,
                cpu_limit=self.cpu_limit,
                memory_limit=self.memory_limit,
                network=self.network,
                timeout=timeout,
            )
            executor._docker_available = self._docker_available
            
            return executor.run_sandboxed(
                "main.py",
                timeout=timeout,
                install_deps=True,
            )


# ══════════════════════════════════════════════════════════════════════════
# Module-level convenience functions
# ══════════════════════════════════════════════════════════════════════════

_docker_checked: Optional[bool] = None


def docker_is_available() -> bool:
    """Cached module-level Docker availability check."""
    global _docker_checked
    if _docker_checked is None:
        _docker_checked = is_docker_available()
    return _docker_checked


def run_code_sandboxed(
    project_dir: Path,
    script: str = "main.py",
    args: Optional[List[str]] = None,
    timeout: int = 60,
    install_deps: bool = True,
) -> SandboxResult:
    """Convenience function: run a script in the best available sandbox."""
    executor = DockerSandboxExecutor(project_dir)
    return executor.run_sandboxed(script, args, timeout, install_deps)
