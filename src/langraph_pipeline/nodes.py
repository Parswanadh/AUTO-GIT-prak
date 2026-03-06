"""
LangGraph Pipeline Nodes for Auto-GIT

Each node is a function that takes the current state and returns updates.
LangGraph handles the orchestration and state management.
"""

import sys
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from dotenv import load_dotenv
import time
import uuid
import gc

# Fix Windows cp1252 codec crashing on emoji in Rich console output
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import re as _re

from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from rich.console import Console

# Load environment variables from .env file
load_dotenv()

# ── Requirements.txt cleaner ─────────────────────────────────────────────────
# Python 3.10+ exposes sys.stdlib_module_names; augment with a common fallback set.
_STDLIB_MODULES: set = getattr(sys, "stdlib_module_names", set()) | {
    "abc", "ast", "asyncio", "atexit", "builtins", "cgi", "chunk",
    "cmath", "code", "codecs", "codeop", "collections", "concurrent",
    "contextlib", "contextvars", "copy", "copyreg", "csv", "dataclasses",
    "datetime", "dbm", "decimal", "difflib", "dis", "email", "encodings",
    "enum", "errno", "faulthandler", "filecmp", "fnmatch", "fractions",
    "ftplib", "functools", "gc", "getopt", "getpass", "gettext", "glob",
    "grp", "gzip", "hashlib", "heapq", "hmac", "html", "http",
    "imaplib", "importlib", "inspect", "io", "ipaddress", "itertools",
    "json", "keyword", "linecache", "locale", "logging", "lzma",
    "math", "mimetypes", "mmap", "multiprocessing", "netrc", "numbers",
    "operator", "os", "pathlib", "pickle", "pickletools", "pkgutil",
    "platform", "pprint", "profile", "pstats", "pty", "pwd", "py_compile",
    "queue", "random", "re", "reprlib", "rlcompleter", "runpy", "sched",
    "secrets", "select", "shelve", "shlex", "shutil", "signal", "socket",
    "socketserver", "sqlite3", "ssl", "stat", "statistics", "string",
    "stringprep", "struct", "subprocess", "sys", "sysconfig", "tarfile",
    "tempfile", "textwrap", "threading", "time", "timeit", "token",
    "tokenize", "tomllib", "traceback", "tracemalloc", "typing",
    "unicodedata", "unittest", "urllib", "uu", "uuid", "venv",
    "warnings", "weakref", "webbrowser", "wsgiref", "xml", "xmlrpc",
    "zipfile", "zipimport", "zlib", "zoneinfo",
}

# Common import-name → pip-package-name aliases
_IMPORT_TO_PKG: dict = {
    "cv2": "opencv-python", "PIL": "pillow",
    "sklearn": "scikit-learn", "yaml": "pyyaml", "bs4": "beautifulsoup4",
    "dateutil": "python-dateutil", "Crypto": "pycryptodome",
    "dotenv": "python-dotenv", "wx": "wxPython", "OpenGL": "PyOpenGL",
    "attr": "attrs", "gi": "pygobject",
    # Web frameworks & common third-party packages
    "flask": "flask", "django": "django", "fastapi": "fastapi",
    "uvicorn": "uvicorn", "gunicorn": "gunicorn", "starlette": "starlette",
    "sqlalchemy": "sqlalchemy", "alembic": "alembic",
    "celery": "celery", "redis": "redis", "pymongo": "pymongo",
    "psycopg2": "psycopg2-binary", "aiohttp": "aiohttp",
    "httpx": "httpx", "requests": "requests",
    "pytest": "pytest", "hypothesis": "hypothesis",
    "pydantic": "pydantic", "marshmallow": "marshmallow",
    "click": "click", "typer": "typer", "rich": "rich",
    "jinja2": "jinja2", "mako": "mako",
    "boto3": "boto3", "paramiko": "paramiko",
    "cryptography": "cryptography", "jwt": "pyjwt",
    "websockets": "websockets", "aioredis": "aioredis",
    "kombu": "kombu", "dramatiq": "dramatiq", "rq": "rq",
    "apscheduler": "apscheduler", "schedule": "schedule",
    "colorama": "colorama", "tqdm": "tqdm",
    "numpy": "numpy", "pandas": "pandas", "scipy": "scipy",
    "matplotlib": "matplotlib", "seaborn": "seaborn",
    "torch": "torch", "tensorflow": "tensorflow",
    "transformers": "transformers",
}

# ── Shared Emoji → ASCII map (single source of truth) ────────────────────────
# Used by code_generation, code_fixing, and post-LLM sanitization.
# Adding an emoji here propagates to ALL sanitization passes automatically.
_EMOJI_TO_ASCII: dict = {
    "✅": "[OK]", "❌": "[FAIL]", "⚠️": "[!]", "⚠": "[!]",
    "🔄": "[...]", "✓": "[v]", "✗": "[x]", "✘": "[x]",
    "📊": "[stats]", "📈": "[up]", "📉": "[down]", "📋": "[list]",
    "🔍": "[search]", "💡": "[tip]", "🚀": "[go]", "🎯": "[target]",
    "⭐": "[*]", "★": "[*]", "☆": "[*]", "●": "[o]", "○": "[o]",
    "◉": "[o]", "◐": "[-]", "◑": "[-]", "▶": "[>]", "◀": "[<]",
    "▲": "[^]", "▼": "[v]", "✶": "[*]", "•": "*", "→": "->",
    "←": "<-", "↑": "^", "↓": "v", "─": "-", "│": "|",
    "┌": "+", "┐": "+", "└": "+", "┘": "+", "├": "+", "┤": "+",
    "┬": "+", "┴": "+", "┼": "+", "━": "=", "║": "||",
    "╔": "+", "╗": "+", "╚": "+", "╝": "+", "╠": "+", "╣": "+",
    "╦": "+", "╩": "+", "╬": "+",
    "█": "#", "▌": "|", "▐": "|", "░": ".", "▒": ":", "▓": "#",
    "▏": "|", "▎": "|", "▍": "|", "▋": "|", "▊": "|", "▉": "#",
    "═": "=", "╭": "+", "╮": "+", "╰": "+", "╯": "+",
    "🔑": "[key]", "📁": "[dir]", "📂": "[dir]", "💰": "[$]",
    "📝": "[note]", "🏆": "[win]", "⏱": "[time]", "⏱️": "[time]",
    "🎉": "[!]", "💻": "[pc]", "🔒": "[lock]", "🔓": "[unlock]",
    "🧪": "[test]", "📦": "[pkg]", "🌐": "[web]", "🎵": "[audio]",
    "🔥": "[hot]", "💾": "[save]", "📌": "[pin]", "🏷️": "[tag]",
    "⚙️": "[cfg]", "⚙": "[cfg]", "🛡️": "[shield]", "🛡": "[shield]",
    "📡": "[net]", "🧩": "[mod]", "🗑️": "[del]", "🗑": "[del]",
}


def _sanitize_emoji(files: Dict[str, str], label: str = "") -> int:
    """Strip emoji/unicode from all .py files in-place. Returns count of files changed."""
    changed = 0
    for fname in list(files.keys()):
        if not fname.endswith(".py"):
            continue
        code = str(files[fname])
        new_code = code
        for emoji, ascii_repr in _EMOJI_TO_ASCII.items():
            if emoji in new_code:
                new_code = new_code.replace(emoji, ascii_repr)
        if new_code != code:
            files[fname] = new_code
            changed += 1
            logger.info(f"  🧹 Emoji sanitized: {fname} ({label})")
    return changed


# ── LLM Artifact Stripper ────────────────────────────────────────────────
# LLMs occasionally leave XML/HTML/markdown artifacts in generated Python
# code: </function>, </code>, ```python, etc.  These cause SyntaxError.
# We strip them deterministically (no LLM needed) after every generation
# and every fix pass.
import re as _re_artifact

_LLM_ARTIFACT_PATTERNS = [
    # XML closing tags (</function>, </code>, </module>, </script>, etc.)
    (_re_artifact.compile(r'^[ \t]*</\w+>[ \t]*$', _re_artifact.MULTILINE), ""),
    # XML opening tags that are clearly not Python (<function>, <code>, etc.)
    (_re_artifact.compile(r'^[ \t]*<(?:function|code|module|script|output|response|result|answer|solution|file|content)(?:\s[^>]*)?>[ \t]*$', _re_artifact.MULTILINE), ""),
    # Markdown code fences (```python, ```, ```py)
    (_re_artifact.compile(r'^[ \t]*```(?:python|py)?[ \t]*$', _re_artifact.MULTILINE), ""),
    # XML CDATA markers
    (_re_artifact.compile(r'^[ \t]*<!\[CDATA\[[ \t]*$', _re_artifact.MULTILINE), ""),
    (_re_artifact.compile(r'^[ \t]*\]\]>[ \t]*$', _re_artifact.MULTILINE), ""),
    # Stray XML self-closing tags on their own line (e.g., <br/>, <hr/>)
    (_re_artifact.compile(r'^[ \t]*<\w+\s*/>[ \t]*$', _re_artifact.MULTILINE), ""),
]


def _sanitize_llm_artifacts(files: Dict[str, str], label: str = "") -> int:
    """Strip XML/HTML/markdown artifacts from all .py files in-place.
    
    Returns count of files that were modified.
    Common artifacts:
    - </function>, </code>, </module> (XML closing tags)
    - ```python ... ``` (markdown fences)
    - <![CDATA[ ... ]]> (XML CDATA)
    """
    changed = 0
    for fname in list(files.keys()):
        if not fname.endswith(".py"):
            continue
        code = str(files[fname])
        new_code = code
        for pattern, replacement in _LLM_ARTIFACT_PATTERNS:
            new_code = pattern.sub(replacement, new_code)
        # Remove blank lines left behind by stripping (collapse 3+ consecutive
        # blank lines to 2)
        new_code = _re_artifact.sub(r'\n{3,}', '\n\n', new_code)
        if new_code != code:
            files[fname] = new_code
            changed += 1
            logger.info(f"  🧹 LLM artifact stripped: {fname} ({label})")
    return changed


def _flatten_file_keys(files: Dict[str, str], source: str = "") -> Dict[str, str]:
    """Strip directory prefixes from file keys.
    
    LLMs sometimes return keys like 'baby_dragon/model.py' — this flattens
    them to just 'model.py' so CodeExecutor can find them.
    """
    import os.path
    flat: Dict[str, str] = {}
    for key, content in files.items():
        basename = os.path.basename(key) if ('/' in key or '\\' in key) else key
        if basename != key:
            logger.warning(f"  ⚠️  [{source}] Flattened key '{key}' → '{basename}'")
        # On collision, keep the longer content
        if basename in flat:
            if len(content) > len(flat[basename]):
                flat[basename] = content
        else:
            flat[basename] = content
    return flat


def _clean_requirements_txt(req_text: str, py_sources: dict | None = None) -> str:
    """
    Filter requirements.txt to remove:
    - stdlib / builtin modules (not pip-installable)
    - _internal_ modules starting with underscore
    - 'pkg @ file://...' editable / VCS installs
    - Lines that aren't valid package specifiers
    If py_sources {filename: code} is provided, also restricts to packages
    that are actually imported in the source files (with alias resolution).
    """
    if not req_text or not req_text.strip():
        return req_text

    # Collect top-level import roots from .py source files
    imported_roots: set | None = None
    if py_sources:
        imported_roots = set()
        for code in py_sources.values():
            for m in _re.findall(r"^(?:import|from)\s+(\w+)", code, _re.M):
                imported_roots.add(m.lower())
        # Expand aliases: if 'cv2' imported → also accept 'opencv-python' in reqs
        alias_extras: set = set()
        for imp, pkg in _IMPORT_TO_PKG.items():
            if imp.lower() in imported_roots:
                alias_extras.add(pkg.lower().replace("-", "_"))
                alias_extras.add(pkg.lower())
        imported_roots |= alias_extras

    kept: list = []
    for line in req_text.splitlines():
        stripped = line.strip()
        # Blank / comments: keep as-is
        if not stripped or stripped.startswith("#"):
            kept.append(stripped)
            continue
        # Editable installs, VCS URLs, -r includes: skip
        if " @ " in stripped or stripped.startswith((
            "git+", "http://", "https://", "-e ", "-r ", "--index", "--extra"
        )):
            continue
        # Extract package name (before any version/bracket/semicolon)
        pkg_name = _re.split(r"[>=<!;\[\s]", stripped)[0].strip()
        if not pkg_name:
            continue
        # Rename known import-alias names to real pip package names
        # e.g. sklearn>=1.2 → scikit-learn>=1.2, yaml → pyyaml, bs4 → beautifulsoup4
        _alias_map_lower = {k.lower(): v for k, v in _IMPORT_TO_PKG.items()}
        if pkg_name.lower() in _alias_map_lower:
            real_pkg = _alias_map_lower[pkg_name.lower()]
            stripped = real_pkg + stripped[len(pkg_name):]
            pkg_name = real_pkg
        # Strip stdlib internals (_bisect, _thread, _collections_abc, …)
        if pkg_name.startswith("_"):
            continue
        # Strip stdlib modules
        pkg_lower = pkg_name.lower().replace("-", "_")
        if pkg_lower in _STDLIB_MODULES or pkg_name.lower() in _STDLIB_MODULES:
            continue
        # Strip multi-word invalid lines e.g. 'torch schedulers' or 'numpy arrays'
        # Valid pip specifier after pkg_name: [extras], version spec (>=<!=), env marker (;)
        remainder = stripped[len(pkg_name):].lstrip()
        if remainder and not _re.match(r'^[\[>=<!~;,\s]', remainder):
            continue  # description text after pkg name — not a valid pip specifier
        # If we know what's imported, only keep packages that match
        if imported_roots is not None:
            if pkg_lower not in imported_roots:
                # Also allow packages whose name starts with or matches any imported root
                # (e.g. 'torch' covers 'torchvision', 'torchaudio')
                if not any(
                    pkg_lower.startswith(r) or r.startswith(pkg_lower)
                    for r in imported_roots
                ):
                    continue
        kept.append(stripped)  # use `stripped` so alias-renames (e.g. sklearn→scikit-learn) are preserved

    return "\n".join(kept)


def _fix_dotted_local_imports(files: Dict[str, str], label: str = "") -> int:
    """Convert dotted package imports to flat imports for local project files.

    LLMs often generate `from project_name.module import X` treating the project
    as a Python package with subdirectories, but files are flat in one directory.

    Converts:
        from task_queue.task import Task   →  from task import Task
        from my_app.utils import helper    →  from utils import helper
        from project.config import Config  →  from config import Config
        import task_queue.task             →  import task          (and adds alias)

    Only converts when the *leaf module* (last dotted segment) matches a
    generated .py file AND the *root segment* is NOT a stdlib or known
    third-party package.

    Returns total number of import lines converted.
    """
    _known_pkgs = _STDLIB_MODULES | set(_IMPORT_TO_PKG.keys()) | {
        v.replace("-", "_").lower() for v in _IMPORT_TO_PKG.values()
    }
    py_module_names = {f[:-3] for f in files if f.endswith(".py")}
    total_fixes = 0

    for fname, content in list(files.items()):
        if not fname.endswith(".py") or not content:
            continue
        new_lines = []
        fixes = 0
        for line in content.splitlines():
            # Pattern 1: from X.Y.Z import A  →  from Z import A
            m = _re.match(
                r"^(\s*from\s+)(\w+(?:\.\w+)*\.)(\w+)(\s+import\s+.*)$", line
            )
            if m:
                prefix_pkg = m.group(2).rstrip(".")     # e.g. "task_queue" or "task_queue.sub"
                root_pkg = prefix_pkg.split(".")[0]      # e.g. "task_queue"
                leaf_module = m.group(3)                 # e.g. "task"
                if (
                    root_pkg.lower() not in _known_pkgs
                    and leaf_module in py_module_names
                ):
                    new_lines.append(
                        f"{m.group(1)}{leaf_module}{m.group(4)}"
                    )
                    fixes += 1
                    continue

            # Pattern 2: import X.Y  →  import Y  (when Y.py exists locally)
            m2 = _re.match(
                r"^(\s*import\s+)(\w+(?:\.\w+)*\.)(\w+)\s*$", line
            )
            if m2:
                prefix_pkg = m2.group(2).rstrip(".")
                root_pkg = prefix_pkg.split(".")[0]
                leaf_module = m2.group(3)
                if (
                    root_pkg.lower() not in _known_pkgs
                    and leaf_module in py_module_names
                ):
                    new_lines.append(f"{m2.group(1)}{leaf_module}")
                    fixes += 1
                    continue

            new_lines.append(line)

        if fixes:
            files[fname] = "\n".join(new_lines)
            total_fixes += fixes
            logger.info(f"  🔧 [{label}] {fname}: flattened {fixes} dotted package import(s)")

    return total_fixes
# ─────────────────────────────────────────────────────────────────────────────

# Import local cached LLM (no Docker required)
try:
    from .local_cached_llm import LocalCachedLLM
    CACHE_ENABLED = True
except ImportError:
    CACHE_ENABLED = False
    LocalCachedLLM = ChatOllama  # Fallback to standard

from ..utils.web_search import ResearchSearcher
from ..research.extensive_researcher import ExtensiveResearcher
from ..llm.hybrid_router import HybridRouter
from ..llm.multi_backend_manager import get_backend_manager
from ..utils.model_manager import get_model_manager, get_fallback_llm
from .state import (
    AutoGITState,
    ResearchContext,
    SolutionProposal,
    Critique,
    DebateRound,
    EXPERT_PERSPECTIVES,
    get_perspective_by_name
)
from ..utils.json_parser import extract_json_from_text, safe_parse_solutions
from ..analytics.tracker import AnalyticsTracker

logger = logging.getLogger(__name__)

# Initialize global analytics tracker
_analytics_tracker = None

# Initialize global model manager
_model_manager = None

def get_analytics_tracker() -> AnalyticsTracker:
    """Get or create analytics tracker singleton"""
    global _analytics_tracker
    if _analytics_tracker is None:
        _analytics_tracker = AnalyticsTracker()
    return _analytics_tracker


# ── Smart model routing ────────────────────────────────────────────────────────
# Detected complexity from requirements_extraction → profile override.
# "simple" tasks can use fast models everywhere, "complex" tasks get powerful.
_COMPLEXITY_OVERRIDE: Optional[str] = None  # set by requirements_extraction_node

_SMART_ROUTING_MAP: Dict[str, Dict[str, str]] = {
    # complexity → { requested_profile → actual_profile }
    "simple": {
        "balanced":  "fast",
        "powerful":  "balanced",
        "reasoning": "balanced",
    },
    "moderate": {
        # no overrides — use as-is
    },
    "complex": {
        "fast":      "balanced",
        "balanced":  "powerful",
    },
}


def get_llm(profile: str = "balanced"):
    """
    Get LLM model from model manager (prevents VRAM thrashing).
    Applies smart routing overrides based on detected task complexity.
    
    Args:
        profile: Model profile (fast/balanced/powerful/reasoning)
    
    Returns:
        FallbackLLM instance with retry logic.
    """
    global _model_manager
    if _model_manager is None:
        _model_manager = get_model_manager()
    
    # Smart routing: remap profile if complexity was detected
    actual_profile = profile
    if _COMPLEXITY_OVERRIDE and _COMPLEXITY_OVERRIDE in _SMART_ROUTING_MAP:
        actual_profile = _SMART_ROUTING_MAP[_COMPLEXITY_OVERRIDE].get(profile, profile)
        if actual_profile != profile:
            logger.debug(f"  Smart routing: {profile} → {actual_profile} (complexity={_COMPLEXITY_OVERRIDE})")
    
    return _model_manager.get_fallback_llm(actual_profile)


# ============================================
# Node 0: Requirements Extraction (CoT Decomposition)
# ============================================

async def requirements_extraction_node(state: AutoGITState) -> Dict[str, Any]:
    """
    Node 0: SOTA Chain-of-Thought Task Decomposition

    Before any research, decompose the user's idea into structured requirements.
    This is inspired by:
    - Chain-of-Thought (Wei et al. 2022) — think step by step
    - Task decomposition from AutoGPT/BabyAGI — break complex tasks into subtasks
    - SWE-bench's localization step — understand WHAT before doing HOW

    Outputs a structured requirements dict that gets passed to all downstream
    nodes, ensuring research is targeted, code generation is aligned, and
    validation checks the RIGHT things.
    """
    logger.info("📋 Requirements Extraction Node — decomposing idea")

    idea = state.get("idea", "")
    user_reqs = state.get("user_requirements", "") or ""

    console = Console()
    console.print(f"\n[bold cyan]📋 Requirements Extraction — decomposing your idea...[/bold cyan]")

    if not idea:
        logger.warning("  No idea provided — skipping requirements extraction")
        return {"current_stage": "requirements_skipped"}

    try:
        llm = get_fallback_llm("fast")

        req_prompt = (
            "You are a senior software architect. Decompose this idea into structured requirements.\n"
            "Think step by step about what needs to be built.\n\n"
            f"IDEA: {idea}\n"
        )
        if user_reqs:
            req_prompt += f"ADDITIONAL REQUIREMENTS: {user_reqs}\n"

        req_prompt += (
            "\nReturn ONLY valid JSON (no markdown fences):\n"
            "{\n"
            '  "project_type": "cli_tool|web_api|library|ml_model|data_pipeline|full_app",\n'
            '  "complexity": "simple|moderate|complex",\n'
            '  "core_components": ["list ALL main modules needed — no limit"],\n'
            '  "key_features": ["list ALL must-have features — no limit"],\n'
            '  "data_flow": "brief description of how data moves through the system",\n'
            '  "external_deps": ["list of likely pip packages needed"],\n'
            '  "test_scenarios": [\n'
            '    {"name": "test name", "input": "sample input", "expected": "expected output"}\n'
            '  ],\n'
            '  "success_criteria": "one sentence: how do we know it works?",\n'
            '  "risk_areas": ["potential implementation challenges"]\n'
            "}\n"
        )

        messages = [HumanMessage(content=req_prompt)]
        response = await llm.ainvoke(messages)

        import json as _jsr_req
        raw = response.content.strip()
        raw = _re.sub(r"^```[a-z]*\n?", "", raw)
        raw = _re.sub(r"\n?```$", "", raw.strip())
        # Handle thinking tags
        if "<think>" in raw:
            _te = raw.rfind("</think>")
            if _te != -1:
                raw = raw[_te + len("</think>"):].strip()

        requirements = _jsr_req.loads(raw)

        # Display extracted requirements
        project_type = requirements.get("project_type", "unknown")
        complexity = requirements.get("complexity", "unknown")
        components = requirements.get("core_components", [])
        features = requirements.get("key_features", [])
        success = requirements.get("success_criteria", "")

        console.print(f"  [bold]Type:[/bold] {project_type} | [bold]Complexity:[/bold] {complexity}")
        console.print(f"  [bold]Components:[/bold] {', '.join(components[:5])}")
        console.print(f"  [bold]Features:[/bold] {', '.join(features[:4])}")
        console.print(f"  [bold]Success:[/bold] {success}")

        logger.info(f"  Requirements: type={project_type}, complexity={complexity}, "
                     f"components={len(components)}, features={len(features)}")

        # Smart model routing: set complexity for downstream profile overrides
        global _COMPLEXITY_OVERRIDE
        if complexity in ("simple", "moderate", "complex"):
            _COMPLEXITY_OVERRIDE = complexity
            console.print(f"  [dim]🧠 Smart routing: complexity={complexity} → model profiles adjusted[/dim]")

        # V13 FIX: Also store in state so it doesn't rely solely on mutable global
        _complexity_state = complexity if complexity in ("simple", "moderate", "complex") else None

        # Multi-language detection
        try:
            from src.utils.language_support import detect_language
            detected_lang = detect_language(requirements, idea)
            requirements["detected_language"] = detected_lang
            if detected_lang != "python":
                console.print(f"  [bold magenta]🌐 Detected language: {detected_lang}[/bold magenta]")
            else:
                console.print(f"  [dim]🌐 Language: Python (default)[/dim]")
        except Exception as lang_err:
            logger.debug(f"Language detection failed: {lang_err}")
            requirements["detected_language"] = "python"

        return {
            "current_stage": "requirements_extracted",
            "requirements": requirements,
            "complexity_override": _complexity_state,  # V13: store in state for thread-safety
        }

    except Exception as e:
        logger.warning(f"Requirements extraction failed ({e}) — continuing without structured requirements")
        console.print(f"  [dim yellow]Extraction failed ({e}) — proceeding with raw idea[/dim yellow]")
        return {"current_stage": "requirements_extraction_failed"}


# ============================================
# Node 1: Research & Context Gathering
# ============================================

async def research_node(state: AutoGITState) -> Dict[str, Any]:
    """
    Node 1: SOTA Research using Groq compound-beta (built-in web search).

    compound-beta automatically searches the web when needed, so a single LLM
    call gives us grounded, up-to-date results without managing a search API.
    Fallback chain: compound-beta → gpt-oss-120b (also has web search) →
                    SearXNG ExtensiveResearcher → basic arXiv/DDG searcher.
    """
    idea = state['idea']
    run_id = state.get('run_id', str(uuid.uuid4()))
    tracker = get_analytics_tracker()

    start_time = time.time()
    logger.info(f"🔍 Research Node (compound-beta/web-search): '{idea}'")

    console = Console()
    try:
        from ..utils.model_manager import get_profile_primary as _gpp
    except Exception:
        from utils.model_manager import get_profile_primary as _gpp  # type: ignore
    console.print(f"\n[cyan]🔍 SOTA Research:[/cyan] [bold]{idea}[/bold]  [dim](model profile: research → {_gpp('research')})[/dim]")

    if not state.get("use_web_search", True):
        logger.info("Web search disabled — skipping research")
        return {
            "current_stage": "research_skipped",
            "research_context": None,
            "run_id": run_id,
        }

    research_context: ResearchContext = {}
    summary = ""

    # ------------------------------------------------------------------
    # Primary path: compound-beta (Groq) or gpt-oss-120b with web search
    # ------------------------------------------------------------------
    try:
        console.print(f"[dim]  Attempting compound-beta (grounded web search)...[/dim]")
        llm = get_llm("research")  # compound-beta first in this profile

        research_system = (
            "You are a world-class research analyst with access to real-time web search. "
            "Search for recent papers, benchmarks, open-source implementations, and SOTA results. "
            "Be comprehensive and cite specific sources (ArXiv IDs, GitHub repos, blog posts). "
            "Structure your entire response as VALID JSON only — no prose outside the JSON."
        )
        research_user = f"""Research topic: {idea}

Perform a THOROUGH, EXTENSIVE SOTA literature survey. Dig deep — aim for at least 12 key papers.
Return ONLY this JSON structure:

{{
  "sota_summary": "3-5 sentence summary of current state of the art, including recent breakthroughs",
  "key_papers": [
    {{"title": "...", "authors": "...", "year": 2024, "url": "arxiv.org/...", "contribution": "..."}},
    ... (at least 12 papers)
  ],
  "open_problems": [
    "Problem 1: specific gap or challenge with technical detail",
    "Problem 2: ...",
    ... (at least 7 problems)
  ],
  "recent_advances": [
    "Advance 1: what changed recently, specific numbers/metrics, why it matters",
    ... (at least 6 advances)
  ],
  "implementations": [
    {{"name": "...", "url": "github.com/...", "description": "..."}},
    ... (all known open-source implementations)
  ],
  "benchmarks": [
    {{"name": "...", "metric": "...", "best_result": "...", "model": "..."}},
    ... (all relevant benchmarks with numbers)
  ],
  "hardware_or_systems": [
    {{"name": "...", "specs": "...", "advantage": "...", "limitation": "..."}}
  ],
  "key_insights": [
    "Insight 1 relevant to building something novel in this area — be specific",
    ... (at least 6 insights)
  ]
}}"""

        messages = [
            SystemMessage(content=research_system),
            HumanMessage(content=research_user),
        ]

        response = await llm.ainvoke(messages)
        raw = response.content or ""

        # Parse JSON from the response
        parsed = extract_json_from_text(raw)
        if not isinstance(parsed, dict):
            raise ValueError(f"compound-beta returned non-dict: {type(parsed)}")

        # Build research_context from the rich structured response
        papers = []
        for p in parsed.get("key_papers", []):
            papers.append({
                "title": p.get("title", ""),
                "url": p.get("url", ""),
                "summary": p.get("contribution", ""),
                "authors": p.get("authors", ""),
                "year": p.get("year", ""),
                "relevance_score": 0.9,
            })

        web_results = []
        for adv in parsed.get("recent_advances", []):
            web_results.append({"title": adv, "url": "", "snippet": adv, "relevance_score": 0.8})

        implementations = []
        for imp in parsed.get("implementations", []):
            implementations.append({
                "title": imp.get("name", ""),
                "url": imp.get("url", ""),
                "description": imp.get("description", ""),
                "source": "web_search",
            })

        research_context = {
            "papers": papers,
            "web_results": web_results,
            "implementations": implementations,
            "search_timestamp": datetime.now().isoformat(),
            "compound_beta_research": {
                "sota_summary":    parsed.get("sota_summary", ""),
                "open_problems":   parsed.get("open_problems", []),
                "recent_advances": parsed.get("recent_advances", []),
                "benchmarks":      parsed.get("benchmarks", []),
                "key_insights":    parsed.get("key_insights", []),
            },
        }

        summary = (
            f"compound-beta SOTA research complete:\n"
            f"  - {len(papers)} key papers\n"
            f"  - {len(parsed.get('open_problems', []))} open problems identified\n"
            f"  - {len(implementations)} implementations found\n"
            f"  - {len(parsed.get('benchmarks', []))} benchmarks\n"
            f"  SOTA summary: {parsed.get('sota_summary', '')[:200]}"
        )

        console.print(f"[green]✅ compound-beta research complete:[/green]")
        console.print(f"  • [bold]{len(papers)}[/bold] papers, [bold]{len(implementations)}[/bold] implementations")
        console.print(f"  • [bold]{len(parsed.get('open_problems', []))}[/bold] open problems")
        console.print(f"  • [bold]{len(parsed.get('benchmarks', []))}[/bold] benchmarks\n")
        logger.info(f"✅ compound-beta research: {len(papers)} papers, {len(implementations)} impls")

        # ── Deep-dive second pass: hardware / implementation specifics ─────
        try:
            console.print("[dim]  🧪 Deep-dive research pass (hardware, datasets, algorithms)...[/dim]")
            open_probs_text = "\n".join(
                f"- {p}" for p in parsed.get("open_problems", [])[:5]
            )
            deepdive_user = (
                f"Follow-up deep-dive on: {idea}\n\n"
                f"We already know the high-level SOTA. Now go deeper on these specific angles:\n"
                f"1. Hardware implementations / chip designs: specs, power consumption, die area, throughput\n"
                f"2. Key datasets and evaluation protocols used in this domain\n"
                f"3. Algorithmic innovations: exact mechanisms, training tricks, efficiency techniques\n"
                f"4. Open-source tools, simulators, frameworks\n"
                f"5. For each of these known open problems, propose a concrete research approach:\n"
                f"{open_probs_text}\n\n"
                "Return ONLY this JSON:\n"
                "{\n"
                '  "hardware_deep_dive": [\n'
                '    {"name": "...", "type": "chip|fpga|sim", "specs": "...", "power_w": "...", "throughput": "...", "paper": "..."}\n'
                "  ],\n"
                '  "datasets": [\n'
                '    {"name": "...", "size": "...", "task": "...", "url": "..."}\n'
                "  ],\n"
                '  "algorithm_details": [\n'
                '    {"name": "...", "key_mechanism": "...", "advantage_over_baseline": "..."}\n'
                "  ],\n"
                '  "tools_and_frameworks": [\n'
                '    {"name": "...", "url": "...", "purpose": "..."}\n'
                "  ],\n"
                '  "problem_solutions": [\n'
                '    {"problem": "...", "proposed_approach": "...", "feasibility": "high|medium|low"}\n'
                "  ]\n"
                "}"
            )
            dd_response = await llm.ainvoke([
                SystemMessage(content=(
                    "You are a deep technical research analyst specialising in hardware architecture, "
                    "chip design, and AI systems. Search for specific hardware specs, papers, and "
                    "implementation details. Return ONLY valid JSON."
                )),
                HumanMessage(content=deepdive_user),
            ])
            dd_parsed = extract_json_from_text(dd_response.content or "")
            if isinstance(dd_parsed, dict):
                research_context["deep_dive"] = dd_parsed
                hw_count   = len(dd_parsed.get("hardware_deep_dive", []))
                ds_count   = len(dd_parsed.get("datasets", []))
                algo_count = len(dd_parsed.get("algorithm_details", []))
                tool_count = len(dd_parsed.get("tools_and_frameworks", []))
                console.print(
                    f"[green]  ✅ Deep-dive:[/green] "
                    f"{hw_count} hardware specs · {ds_count} datasets · "
                    f"{algo_count} algorithms · {tool_count} tools"
                )
                logger.info(f"  Deep-dive: {hw_count} hw, {ds_count} ds, {algo_count} algos, {tool_count} tools")
        except Exception as dd_err:
            logger.warning(f"  Deep-dive pass skipped: {dd_err}")
        # ── End deep-dive ──────────────────────────────────────────────────

    except Exception as compound_err:
        logger.warning(f"compound-beta research failed ({compound_err}), falling back to SearXNG/arXiv")
        console.print(f"[yellow]⚠️  Web-search LLM unavailable ({compound_err})[/yellow] — falling back to arXiv")

        # ------------------------------------------------------------------
        # Fallback: SearXNG ExtensiveResearcher or basic arXiv/DDG search
        # ------------------------------------------------------------------
        try:
            from src.research.searxng_client import SearXNGClient
            manager = get_backend_manager()
            router = HybridRouter(manager)
            searxng = SearXNGClient()

            if searxng.is_available():
                researcher = ExtensiveResearcher(
                    hybrid_router=router,
                    max_iterations=3,
                    results_per_query=10,
                )
                synthesis = await researcher.research(topic=idea, focus_areas=None)

                research_context = {
                    "papers": [
                        {"title": r.title, "url": r.url, "summary": (r.content or "")[:500],
                         "relevance_score": r.relevance_score}
                        for r in synthesis.sources if r.category in ["academic", "technical"]
                    ],
                    "web_results": [
                        {"title": r.title, "url": r.url, "snippet": (r.content or "")[:300],
                         "relevance_score": r.relevance_score}
                        for r in synthesis.sources if r.category == "general"
                    ],
                    "implementations": [
                        {"title": r.title, "url": r.url, "description": (r.content or "")[:200],
                         "source": r.engine}
                        for r in synthesis.sources
                        if "github" in r.url.lower() or "gitlab" in r.url.lower()
                    ],
                    "search_timestamp": synthesis.timestamp,
                    "extensive_research": {
                        "iterations": synthesis.iterations,
                        "key_findings": synthesis.key_findings,
                        "gaps_identified": synthesis.gaps_identified,
                        "quality_score": synthesis.quality_score,
                    },
                }
                summary = (
                    f"SearXNG research: {synthesis.unique_results} sources, "
                    f"quality={synthesis.quality_score:.1f}/10"
                )
                console.print(f"[green]✅ SearXNG fallback:[/green] {synthesis.unique_results} sources")

            else:
                # Last resort: basic arXiv/DDG
                searcher = ResearchSearcher(max_arxiv=5, max_web=5)
                results = searcher.search_comprehensive(idea)
                research_context = {
                    "papers": results["papers"],
                    "web_results": results["web_results"],
                    "implementations": results["implementations"],
                    "search_timestamp": datetime.now().isoformat(),
                }
                summary = (
                    f"Basic search: {len(results['papers'])} papers, "
                    f"{len(results['web_results'])} web results"
                )
                console.print(f"[green]✅ Basic arXiv fallback:[/green] {len(results['papers'])} papers")

        except Exception as fallback_err:
            logger.error(f"All research fallbacks failed: {fallback_err}")
            research_context = {
                "papers": [], "web_results": [], "implementations": [],
                "search_timestamp": datetime.now().isoformat(),
            }
            summary = f"Research failed: {fallback_err}"

    # ── Citation verification: check arXiv IDs are real ──────────────────
    try:
        import aiohttp
        papers = research_context.get("papers", [])
        verified = 0
        hallucinated = 0
        checked = 0
        console.print("[dim]  🔍 Verifying paper citations...[/dim]")
        for paper in papers[:5]:  # Check top 5 papers only (avoid rate limits)
            url = paper.get("url", "")
            # Extract arXiv ID from various URL formats
            arxiv_id = None
            if "arxiv.org" in url:
                import re as _cite_re
                m = _cite_re.search(r'(\d{4}\.\d{4,5}(?:v\d+)?)', url)
                if m:
                    arxiv_id = m.group(1)
            if arxiv_id:
                try:
                    async with aiohttp.ClientSession() as _sess:
                        async with _sess.head(
                            f"https://arxiv.org/abs/{arxiv_id}",
                            timeout=aiohttp.ClientTimeout(total=5),
                            allow_redirects=True,
                        ) as resp:
                            checked += 1
                            if resp.status == 200:
                                verified += 1
                                paper["citation_verified"] = True
                            else:
                                hallucinated += 1
                                paper["citation_verified"] = False
                                logger.warning(f"  ⚠️ Possibly hallucinated paper: {paper.get('title', '')} (HTTP {resp.status})")
                except Exception:
                    paper["citation_verified"] = None  # could not verify (network issue)
        if checked:
            console.print(f"  [green]✅ Citations: {verified}/{checked} verified[/green]"
                          + (f", [red]{hallucinated} hallucinated[/red]" if hallucinated else ""))
            research_context["citation_stats"] = {
                "checked": checked, "verified": verified, "hallucinated": hallucinated
            }
    except ImportError:
        logger.debug("aiohttp not installed — skipping citation verification")
    except Exception as cite_err:
        logger.debug(f"Citation verification skipped: {cite_err}")

    # Track
    latency = time.time() - start_time
    try:
        tracker.record_run(
            run_id=run_id, idea=idea, model="compound-beta",
            stage="research", success=bool(research_context.get("papers") is not None),
            tokens=0, latency=latency,
        )
    except Exception:
        pass

    return {
        "current_stage": "research_complete",
        "research_context": research_context,
        "related_work_summary": summary.strip(),
        "run_id": run_id,
    }



# ============================================
# Node 1.5: Dynamic Expert Perspective Generation
# ============================================

async def generate_perspectives_node(state: AutoGITState) -> Dict[str, Any]:
    """
    Node 1.5: Generate domain-specific expert perspectives via LLM.

    Instead of always using [ML Researcher, Systems Engineer, Applied Scientist],
    the LLM invents 3 experts who are most useful for THIS specific topic.
    Examples:
      'custom GPU for sparse transformers' →
         VLSI Architect, GPU Microarchitecture Researcher, HPC Systems Engineer
      'privacy-preserving federated learning' →
         Cryptography Researcher, Distributed Systems Engineer, ML Privacy Scientist
    """
    idea = state["idea"]
    logger.info(f"🧠 Generating domain-specific expert perspectives for: '{idea}'")

    console = Console()
    console.print(f"\n[magenta]🧠 Generating expert perspectives...[/magenta]")

    try:
        llm = get_llm("balanced")

        system_prompt = (
            "You are an expert in research methodology. Given a topic, identify the 3 most "
            "relevant expert perspectives that would produce the best multi-angle analysis. "
            "Each expert should bring a distinct, non-overlapping viewpoint. "
            "Return ONLY valid JSON — no prose outside the JSON."
        )

        # Include SOTA context if available
        sota_summary = ""
        rc = state.get("research_context") or {}
        cb = rc.get("compound_beta_research") or {}
        if cb.get("sota_summary"):
            sota_summary = f"\n\nSOTA context: {cb['sota_summary']}"

        user_prompt = f"""Topic: {idea}{sota_summary}

Generate exactly 3 expert perspectives that would best evaluate solutions for this specific domain.
Choose experts whose distinct expertise will surface different critical dimensions of the problem.

Return this EXACT JSON structure:
{{
  "perspectives": [
    {{
      "name": "Short Expert Title (2-4 words)",
      "role": "Full professional role description (1 sentence)",
      "expertise": "Core technical expertise area",
      "focus_areas": ["area1", "area2", "area3"],
      "evaluation_criteria": ["criterion1", "criterion2", "criterion3"]
    }},
    {{ ... }},
    {{ ... }}
  ],
  "reasoning": "One sentence explaining why these 3 perspectives complement each other for this topic"
}}"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        response = await llm.ainvoke(messages)
        parsed = extract_json_from_text(response.content or "")

        if not isinstance(parsed, dict) or not parsed.get("perspectives"):
            raise ValueError(f"Unexpected response structure: {type(parsed)}")

        perspectives_raw = parsed["perspectives"]
        if not isinstance(perspectives_raw, list) or len(perspectives_raw) < 2:
            raise ValueError(f"Need at least 2 perspectives, got: {perspectives_raw}")

        # Validate and clean each perspective
        dynamic_configs = []
        for p in perspectives_raw:
            if not isinstance(p, dict):
                continue
            config = {
                "name": str(p.get("name", "Expert"))[:50],
                "role": str(p.get("role", "Domain Expert")),
                "expertise": str(p.get("expertise", "")),
                "focus_areas": list(p.get("focus_areas", [])),
                "evaluation_criteria": list(p.get("evaluation_criteria", [])),
            }
            dynamic_configs.append(config)

        perspective_names = [c["name"] for c in dynamic_configs]
        reasoning = parsed.get("reasoning", "")

        console.print(f"[green]✅ Generated {len(dynamic_configs)} domain experts:[/green]")
        for cfg in dynamic_configs:
            console.print(f"  • [bold]{cfg['name']}[/bold] — {cfg['role']}")
        if reasoning:
            console.print(f"  [dim]Rationale: {reasoning}[/dim]\n")

        logger.info(f"✅ Dynamic perspectives: {perspective_names}")

        return {
            "current_stage": "perspectives_generated",
            "perspectives": perspective_names,
            "dynamic_perspective_configs": dynamic_configs,
        }

    except Exception as e:
        logger.warning(f"Perspective generation failed ({e}) — using default EXPERT_PERSPECTIVES")
        console.print(f"[yellow]⚠ Perspective generation failed ({e}) — using defaults[/yellow]")
        # Return defaults so pipeline can continue
        from src.langraph_pipeline.state import EXPERT_PERSPECTIVES
        return {
            "current_stage": "perspectives_default",
            "perspectives": [p["name"] for p in EXPERT_PERSPECTIVES],
            "dynamic_perspective_configs": list(EXPERT_PERSPECTIVES),
        }


# ============================================
# Node 2: Problem Extraction
# ============================================

async def problem_extraction_node(state: AutoGITState) -> Dict[str, Any]:
    """
    Node 2: Extract research problems from the idea + research context
    
    IMPORTANT: Uses the user's ACTUAL requirements from conversation agent
    """
    logger.info("🎯 Problem Extraction Node")
    
    try:
        # Get requirements from conversation agent (if available)
        requirements = state.get("requirements")
        
        # CRITICAL: Handle None requirements
        if requirements and isinstance(requirements, dict):
            core_idea = requirements.get("core_idea", state.get('idea', ''))
            target_task = requirements.get("target_task", "")
            model_type = requirements.get("model_type", "")
            approach = requirements.get("approach", "")
            
            # Build problem statement from actual user requirements
            problem_statement = f"Build {core_idea}"
            if target_task:
                problem_statement = f"{target_task}: {core_idea}"
            
            problems = [problem_statement]
            selected_problem = problem_statement
            
            logger.info(f"✅ Using user's actual requirement: {selected_problem}")
            
            return {
                "current_stage": "problems_extracted",
                "problems": problems,
                "selected_problem": selected_problem
            }
        
        # Fallback: Extract from idea directly if no requirements
        idea = state.get('idea', '')
        if not idea:
            logger.warning("No idea or requirements provided")
            return {
                "current_stage": "problem_extraction_failed",
                "errors": ["No idea or requirements provided"],
                "problems": [],
                "selected_problem": None
            }
        
        # Fallback: Use LLM extraction if no requirements
        llm = get_llm("fast")  # Use fast model for extraction
        
        # Build context from research
        context = ""

        # PRIMARY: compound-beta rich research (SOTA summary, open problems, insights)
        research_context_raw = state.get("research_context") or {}
        cb_research = research_context_raw.get("compound_beta_research") or {}
        if cb_research:
            if cb_research.get("sota_summary"):
                context += f"\n\n=== SOTA SUMMARY ===\n{cb_research['sota_summary']}\n"
            if cb_research.get("open_problems"):
                context += "\n\n=== KNOWN OPEN PROBLEMS (from SOTA research) ===\n"
                for op in cb_research["open_problems"]:
                    context += f"  - {op}\n"
            if cb_research.get("recent_advances"):
                context += "\n\n=== RECENT ADVANCES ===\n"
                for ra in cb_research["recent_advances"]:
                    context += f"  - {ra}\n"
            if cb_research.get("key_insights"):
                context += "\n\n=== KEY INSIGHTS FOR BUILDERS ===\n"
                for ki in cb_research["key_insights"]:
                    context += f"  - {ki}\n"
            if cb_research.get("benchmarks"):
                context += "\n\n=== BENCHMARKS ===\n"
                for bm in cb_research["benchmarks"]:
                    context += f"  - {bm.get('name','')}: {bm.get('metric','')} = {bm.get('best_result','')} ({bm.get('model','')})\n"

        # Integration #11: Use new research_report if available
        if state.get("research_report"):
            research_summary = state.get("research_summary", "")
            if research_summary:
                context += f"\n\n=== RECENT RESEARCH (Integration #11) ===\n{research_summary}\n"

        # Legacy paper/implementation context (keep for compatibility)
        if research_context_raw and isinstance(research_context_raw, dict) and not cb_research:
            searcher = ResearchSearcher()
            context += "\n\n=== RELATED WORK ===\n"
            papers = research_context_raw.get("papers", [])
            if papers and isinstance(papers, list):
                context += searcher.format_papers_for_prompt(papers)
            implementations = research_context_raw.get("implementations", [])
            if implementations and isinstance(implementations, list):
                context += "\n\n" + searcher.format_web_results_for_prompt(implementations)
        
        # Build expert-lens context from dynamic perspectives
        expert_lenses = ""
        dynamic_cfgs = state.get("dynamic_perspective_configs") or []
        if dynamic_cfgs:
            expert_lenses = "\n\nExpert lenses to consider when extracting problems:\n"
            for cfg in dynamic_cfgs:
                if isinstance(cfg, dict):
                    expert_lenses += (
                        f"  • {cfg.get('name','?')} ({cfg.get('expertise','')}):"
                        f" focus on {', '.join(cfg.get('focus_areas',[]))}\n"
                    )

        # Create domain-aware prompt
        system_prompt = (
            f"You are a research problem extraction expert specializing in the domain of: {state['idea']}.\n"
            "Your task is to identify SPECIFIC, NOVEL, and IMPLEMENTABLE research problems.\n\n"
            "Focus on:\n"
            "1. Concrete gaps in SOTA — things that don't work yet or work poorly\n"
            "2. Practical limitations of existing methods that matter for real applications\n"
            "3. Emerging opportunities at the intersection of multiple research threads\n"
            "4. Problems whose solution would have high impact (citations, deployments, patents)\n\n"
            "Output format (JSON array):\n"
            '[\n  "Problem 1: Specific, actionable problem statement",\n'
            '  "Problem 2: Another distinct problem with clear success criteria",\n'
            '  "Problem 3: ..."\n]'
        )

        user_prompt = (
            f"Idea / Domain: {state['idea']}\n"
            f"{expert_lenses}"
            f"{context}\n\n"
            "Based on the SOTA research context and expert perspectives above, "
            "identify 3-5 NOVEL research problems worth solving. "
            "Each problem must be:\n"
            "  - Specific (not generic like 'improve performance')\n"
            "  - Not already fully solved by existing work\n"
            "  - Feasible for a prototype implementation\n"
            "  - High impact in this domain\n\n"
            "Return ONLY a JSON array of problem statements."
        )
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        response = await llm.ainvoke(messages)
        
        # Parse response
        problems_text = response.content
        problems_json = extract_json_from_text(problems_text)
        
        if isinstance(problems_json, list):
            problems = problems_json
        else:
            problems = [problems_json.get("problems", [])]

        logger.info(f"✅ Extracted {len(problems)} problems")

        # LLM-driven problem selection: pick the most impactful/novel problem
        selected_problem = problems[0] if problems else None
        if len(problems) > 1:
            try:
                sel_llm = get_llm("fast")
                # Include SOTA context if available
                sota_ctx = ""
                rc2 = state.get("research_context") or {}
                cb2 = rc2.get("compound_beta_research") or {}
                if cb2.get("open_problems"):
                    sota_ctx = "\nKnown open problems from SOTA research: " + "; ".join(cb2["open_problems"])

                sel_prompt = f"""Topic: {state['idea']}{sota_ctx}

The following research problems were identified:
{chr(10).join(f'{i+1}. {p}' for i, p in enumerate(problems))}

Which ONE problem is the MOST impactful, novel, and well-scoped for building a working implementation?
Consider: novelty, feasibility, real-world impact, and alignment with SOTA gaps.

Return ONLY a JSON object:
{{"selected_index": 0, "reasoning": "one sentence"}}
(index is 0-based)"""

                sel_resp = await sel_llm.ainvoke([HumanMessage(content=sel_prompt)])
                sel_json = extract_json_from_text(sel_resp.content or "")
                if isinstance(sel_json, dict) and "selected_index" in sel_json:
                    idx = int(sel_json["selected_index"])
                    if 0 <= idx < len(problems):
                        selected_problem = problems[idx]
                        logger.info(f"  LLM selected problem #{idx}: {selected_problem[:80]}...")
                        logger.info(f"  Reasoning: {sel_json.get('reasoning', '')}")
            except Exception as sel_err:
                logger.warning(f"Problem selection LLM failed ({sel_err}) — using first problem")

        return {
            "current_stage": "problems_extracted",
            "problems": problems,
            "selected_problem": selected_problem
        }

    except Exception as e:
        logger.error(f"Problem extraction failed: {e}")
        return {
            "current_stage": "problem_extraction_failed",
            "errors": [f"Problem extraction failed: {str(e)}"],
            "problems": [],
            "selected_problem": None
        }


def _get_perspective_config(state: AutoGITState, perspective_name: str) -> Optional[Dict]:
    """
    Resolve a perspective config dict for the given name.
    Checks dynamic_perspective_configs (LLM-generated) first,
    then falls back to the hardcoded EXPERT_PERSPECTIVES.
    """
    dynamic = state.get("dynamic_perspective_configs") or []
    for cfg in dynamic:
        if isinstance(cfg, dict) and cfg.get("name") == perspective_name:
            return cfg
    # Fall back to hardcoded defaults
    return get_perspective_by_name(perspective_name)


# ============================================
# Node 3: Multi-Perspective Solution Generation
# ============================================

async def solution_generation_node(state: AutoGITState) -> Dict[str, Any]:
    """
    Node 3: Generate solutions from multiple expert perspectives
    
    Each perspective (ML Researcher, Systems Engineer, Applied Scientist)
    proposes solutions based on their expertise.
    All perspectives run IN PARALLEL — ~3x speedup vs sequential.
    """
    logger.info(f"💡 Solution Generation Node (Round {state['current_round'] + 1})")
    
    try:
        # Use balanced model for solution generation
        llm = get_fallback_llm("balanced")
        
        problem = state["selected_problem"]
        
        # Create console for user feedback
        console = Console()
        try:
            from ..utils.model_manager import get_profile_primary as _gpp2
        except Exception:
            from utils.model_manager import get_profile_primary as _gpp2  # type: ignore
        console.print(f"  [dim]🤖 Model: balanced → {_gpp2('balanced')}[/dim]")

        import asyncio as _asyncio_solgen

        async def _generate_one_proposal(perspective_name: str):
            """Generate a single proposal from one perspective — runs concurrently."""
            perspective = _get_perspective_config(state, perspective_name)
            if not perspective:
                return None

            logger.info(f"  📝 Generating solution from: {perspective['name']}")

            system_prompt = f"""You are a {perspective['role']}.

Your expertise: {perspective['expertise']}
Your focus areas: {', '.join(perspective['focus_areas'])}

Propose a solution to the research problem from your expert perspective.
Consider your specific focus areas and evaluation criteria.

Output format (JSON):
{{
  "approach_name": "Descriptive name for your approach",
  "key_innovation": "Core novel contribution",
  "architecture_design": "High-level architecture description",
  "implementation_plan": ["Step 1", "Step 2", "..."],
  "expected_advantages": ["Advantage 1", "..."],
  "potential_challenges": ["Challenge 1", "..."],
  "novelty_score": 0.0-1.0,
  "feasibility_score": 0.0-1.0
}}"""

            user_prompt = f"""Problem: {problem}

Propose a solution from your perspective as a {perspective['role']}.
Focus on: {', '.join(perspective['focus_areas'])}

Return ONLY valid JSON."""

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]

            try:
                response = await llm.ainvoke(messages)
            except Exception as _e:
                logger.warning(f"  ⚠️  Solution gen failed for {perspective['name']}: {_e}")
                return None

            solution_json = extract_json_from_text(response.content)

            if solution_json and isinstance(solution_json, dict):
                solution: SolutionProposal = {
                    "approach_name": solution_json.get("approach_name", "Unnamed Approach"),
                    "perspective": perspective_name,
                    "key_innovation": solution_json.get("key_innovation", ""),
                    "architecture_design": solution_json.get("architecture_design", ""),
                    "implementation_plan": solution_json.get("implementation_plan", []),
                    "expected_advantages": solution_json.get("expected_advantages", []),
                    "potential_challenges": solution_json.get("potential_challenges", []),
                    "novelty_score": float(solution_json.get("novelty_score", 0.5)),
                    "feasibility_score": float(solution_json.get("feasibility_score", 0.5))
                }
                console.print(f"    [green]✓[/green] [bold]{solution['approach_name']}[/bold]")
                console.print(f"       [dim]{solution['key_innovation'][:80]}...[/dim]")
                logger.info(f"    ✅ Generated: {solution['approach_name']}")
                return solution
            return None

        # ── Run ALL perspectives in parallel ─────────────────────────────────
        # critique_node already does this; solution_generation was the last
        # sequential bottleneck in the debate loop.
        console.print(f"  [cyan]🧠 Running {len(state['perspectives'])} expert proposals in parallel...[/cyan]")
        raw_results = await _asyncio_solgen.gather(
            *[_generate_one_proposal(p) for p in state["perspectives"]],
            return_exceptions=True
        )
        proposals = [
            r for r in raw_results
            if r is not None and not isinstance(r, Exception)
        ]
        _n_failed_proposals = len(raw_results) - len(proposals)
        if _n_failed_proposals > 0:
            logger.warning(
                f"  ⚠️  {_n_failed_proposals}/{len(raw_results)} perspective proposals FAILED "
                f"(LLM errors) — debate has only {len(proposals)} perspectives"
            )
            console.print(
                f"  [yellow]⚠️  {_n_failed_proposals}/{len(raw_results)} proposals failed — "
                f"debate continues with {len(proposals)} perspectives[/yellow]"
            )
        
        logger.info(f"✅ Generated {len(proposals)} solutions from {len(state['perspectives'])} perspectives")
        
        return {
            "current_stage": "solutions_generated",
            "current_round": state["current_round"] + 1,
            "debate_rounds": [{
                "round_number": state["current_round"] + 1,
                "proposals": proposals,
                "critiques": [],
                "consensus_reached": False,
                "round_summary": f"Generated {len(proposals)} proposals"
            }]
        }
        
    except Exception as e:
        logger.error(f"Solution generation failed: {e}")
        return {
            "current_stage": "solution_generation_failed",
            "errors": [f"Solution generation failed: {str(e)}"]
        }


# ============================================
# Node 4: Multi-Perspective Critique
# ============================================

async def critique_node(state: AutoGITState) -> Dict[str, Any]:
    """
    Node 4: Each perspective critiques all proposals
    
    Cross-perspective review to identify strengths and weaknesses.
    """
    logger.info("🔍 Critique Node: Multi-perspective review")
    
    try:
        # Use reasoning model for critique
        llm = get_llm("reasoning")
        try:
            from ..utils.model_manager import get_profile_primary as _gpp3
        except Exception:
            from utils.model_manager import get_profile_primary as _gpp3  # type: ignore
        from rich.console import Console as _RC3
        _RC3().print(f"  [dim]🤖 Model: reasoning → {_gpp3('reasoning')}[/dim]")
        
        # Get current round's proposals — guard against empty debate_rounds
        debate_rounds = state.get("debate_rounds") or []
        if not debate_rounds:
            logger.warning("Critique node: no debate rounds found, skipping critique")
            return {
                "current_stage": "no_debate_rounds",
                "errors": ["Critique skipped: no debate rounds available"]
            }
        current_round = debate_rounds[-1]
        proposals = current_round.get("proposals") or []
        if not proposals:
            logger.warning("Critique node: no proposals in current round, skipping critique")
            return {
                "current_stage": "no_debate_rounds",
                "errors": ["Critique skipped: no proposals in current round"]
            }
        all_critiques: List[Critique] = []

        
        # Create console for user feedback
        console = Console()
        import asyncio as _asyncio_critique

        # Build all (reviewer, proposal) critique tasks first, then run in parallel.
        # This cuts critique time from ~(6 × avg_latency) → ~max_single_latency.
        async def _run_one_critique(reviewer, reviewer_perspective_name, proposal):
            system_prompt = f"""You are a {reviewer['role']} reviewing a proposed solution.

Your expertise: {reviewer['expertise']}
Evaluation criteria: {', '.join(reviewer['evaluation_criteria'])}

Provide constructive critique focusing on:
- Technical feasibility
- Potential issues
- Improvement suggestions

Output format (JSON):
{{
  "overall_assessment": "promising" | "needs-work" | "flawed",
  "strengths": ["Strength 1", "..."],
  "weaknesses": ["Weakness 1", "..."],
  "specific_concerns": ["Concern 1", "..."],
  "improvement_suggestions": ["Suggestion 1", "..."],
  "feasibility_score": 0.0-1.0,
  "recommendation": "accept" | "revise" | "reject"
}}"""

            user_prompt = f"""Review this proposal:

Approach: {proposal['approach_name']}
Innovation: {proposal['key_innovation']}
Architecture: {proposal['architecture_design']}
Implementation: {', '.join(proposal['implementation_plan'])}

From your perspective as {reviewer['role']}, provide a detailed critique.
Return ONLY valid JSON."""

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            try:
                response = await _asyncio_critique.wait_for(
                    llm.ainvoke(messages),
                    timeout=90
                )
            except Exception as _err:
                logger.warning(f"Critique LLM call failed ({reviewer['name']} → {proposal['approach_name'][:40]}): {_err}")
                return None
            critique_json = extract_json_from_text(response.content)
            if critique_json and isinstance(critique_json, dict):
                return {
                    "solution_id": proposal["approach_name"],
                    "reviewer_perspective": reviewer_perspective_name,
                    "overall_assessment": critique_json.get("overall_assessment", "needs-work"),
                    "strengths": critique_json.get("strengths", []),
                    "weaknesses": critique_json.get("weaknesses", []),
                    "specific_concerns": critique_json.get("specific_concerns", []),
                    "improvement_suggestions": critique_json.get("improvement_suggestions", []),
                    "feasibility_score": float(critique_json.get("feasibility_score", 0.5)),
                    "recommendation": critique_json.get("recommendation", "revise")
                }
            return None

        # Collect all tasks (skip self-review)
        critique_tasks = []
        for reviewer_perspective_name in state["perspectives"]:
            reviewer = _get_perspective_config(state, reviewer_perspective_name)
            if not reviewer:
                continue
            for proposal in proposals:
                if proposal["perspective"] == reviewer_perspective_name:
                    continue  # skip self-review
                critique_tasks.append((reviewer, reviewer_perspective_name, proposal))

        console.print(f"\n  [magenta]🔍 Running {len(critique_tasks)} critiques in parallel...[/magenta]")
        logger.info(f"  🔍 Running {len(critique_tasks)} critiques in parallel")

        # Run all critiques concurrently
        results = await _asyncio_critique.gather(
            *[_run_one_critique(r, rn, p) for r, rn, p in critique_tasks],
            return_exceptions=True
        )

        for (reviewer, reviewer_perspective_name, proposal), result in zip(critique_tasks, results):
            if isinstance(result, Exception):
                logger.warning(
                    f"  ⚠️  Critique by {reviewer.get('name', '?')} on "
                    f"'{proposal.get('approach_name', '?')[:40]}' FAILED: {result}"
                )
                continue
            if result is None:
                continue
            critique = result
            all_critiques.append(critique)
            recommendation = critique["recommendation"]
            if recommendation == "accept":
                console.print(f"    [green]✓[/green] [bold]{proposal['approach_name'][:50]}[/bold] ← {reviewer['name']}: [green]Accept[/green]")
            elif recommendation == "revise":
                console.print(f"    [yellow]⚠[/yellow] [bold]{proposal['approach_name'][:50]}[/bold] ← {reviewer['name']}: [yellow]Revise[/yellow]")
            else:
                console.print(f"    [red]×[/red] [bold]{proposal['approach_name'][:50]}[/bold] ← {reviewer['name']}: [red]Reject[/red]")
            logger.info(f"    ✅ {reviewer['name']}: {critique['overall_assessment']} ({critique['recommendation']})")
        
        
        # Update current round with critiques
        updated_round = current_round.copy()
        updated_round["critiques"] = all_critiques
        updated_round["round_summary"] = f"{len(proposals)} proposals, {len(all_critiques)} critiques"
        
        # Update state (replace last round)
        updated_rounds = state["debate_rounds"][:-1] + [updated_round]
        
        logger.info(f"✅ Generated {len(all_critiques)} critiques")
        
        return {
            "current_stage": "critiques_complete",
            "debate_rounds": [updated_round]  # LangGraph will append this
        }
        
    except Exception as e:
        logger.error(f"Critique node failed: {e}")
        return {
            "current_stage": "critique_failed",
            "errors": [f"Critique failed: {str(e)}"]
        }


# ============================================
# Node 5: Consensus Check
# ============================================

def consensus_check_node(state: AutoGITState) -> Dict[str, Any]:
    """
    Node 5: Check if consensus is reached
    
    Determines if we should continue debating or select the best solution.
    """
    logger.info("⚖️  Consensus Check Node")
    
    # Check if we have any debate rounds
    if not state.get("debate_rounds") or len(state["debate_rounds"]) == 0:
        logger.warning("No debate rounds found, skipping to solution selection")
        return {"current_stage": "no_debate_rounds", "should_continue_debate": False}
    
    current_round = state["debate_rounds"][-1]
    critiques = current_round.get("critiques", [])
    
    # Calculate consensus score:
    #   "accept"  = 1.0 (full agreement)
    #   "revise"  = 0.5 (partial — no hard rejection; common for complex problems)
    #   "reject"  = 0.0 (hard disagreement)
    # This prevents the score from always being 0 when LLMs legitimately say "revise"
    # instead of "accept" for novel/complex problems.
    if not critiques:
        consensus_score = 0.0
    else:
        weights = {"accept": 1.0, "revise": 0.5, "reject": 0.0}
        total = sum(weights.get(c["recommendation"], 0.5) for c in critiques)
        consensus_score = total / len(critiques)
    
    consensus_reached = consensus_score >= state["min_consensus_score"]
    max_rounds_reached = state["current_round"] >= state["max_debate_rounds"]
    
    logger.info(f"  Consensus score: {consensus_score:.2f} (threshold: {state['min_consensus_score']})")
    logger.info(f"  Round: {state['current_round']}/{state['max_debate_rounds']}")
    
    if consensus_reached:
        logger.info("✅ Consensus reached!")
        return {
            "current_stage": "consensus_reached"
        }
    elif max_rounds_reached:
        logger.info("⚠️  Max rounds reached, forcing selection")
        return {
            "current_stage": "max_rounds_reached"
        }
    else:
        logger.info("🔄 Continue debate")
        return {
            "current_stage": "continue_debate"
        }


# ============================================
# Node 6: Solution Selection
# ============================================

async def solution_selection_node(state: AutoGITState) -> Dict[str, Any]:
    """
    Node 6: Select the best solution based on all debate rounds
    
    Analyzes all proposals and critiques to pick the winner.
    """
    logger.info("🏆 Solution Selection Node")
    
    try:
        # Use reasoning model for solution selection
        llm = get_llm("reasoning")
        
        # Collect all proposals and critiques
        all_proposals = []
        all_critiques = []
        for round_data in state["debate_rounds"]:
            all_proposals.extend(round_data["proposals"])
            all_critiques.extend(round_data["critiques"])
        
        # Build summary
        summary = "# Debate Summary\n\n"
        for i, proposal in enumerate(all_proposals, 1):
            summary += f"\n## Proposal {i}: {proposal['approach_name']}\n"
            summary += f"Perspective: {proposal['perspective']}\n"
            summary += f"Innovation: {proposal['key_innovation']}\n"
            summary += f"Novelty: {proposal['novelty_score']}, Feasibility: {proposal['feasibility_score']}\n"
            
            # Find critiques for this proposal
            proposal_critiques = [c for c in all_critiques if c["solution_id"] == proposal["approach_name"]]
            if proposal_critiques:
                summary += f"Critiques ({len(proposal_critiques)}):\n"
                for critique in proposal_critiques:
                    summary += f"  - {critique['reviewer_perspective']}: {critique['overall_assessment']} ({critique['recommendation']})\n"
        
        system_prompt = """You are an expert research evaluator. Review all proposals and critiques to select the best solution.

Consider:
- Technical merit and novelty
- Feasibility and practicality
- Consensus across perspectives
- Balance of innovation and implementability

Output format (JSON):
{
  "selected_approach": "Name of selected approach",
  "reasoning": "Detailed explanation of selection",
  "confidence": 0.0-1.0
}"""
        
        user_prompt = f"""{summary}

Based on the debate above, select the BEST solution and explain your reasoning.
Return ONLY valid JSON."""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        response = await llm.ainvoke(messages)
        selection_json = extract_json_from_text(response.content)
        
        # Handle JSON extraction failure
        if selection_json is None:
            logger.warning(f"Failed to extract JSON from text (length: {len(response.content)})")
            logger.debug(f"Response content: {response.content[:500]}")
            
            # Fallback: select highest scoring proposal
            if all_proposals:
                final_solution = max(all_proposals, key=lambda p: p["novelty_score"] + p["feasibility_score"])
                reasoning = f"Auto-selected highest scoring proposal (JSON parsing failed)"
                logger.info(f"✅ Fallback Selected: {final_solution['approach_name']}")
                
                return {
                    "current_stage": "solution_selected",
                    "final_solution": final_solution,
                    "selection_reasoning": reasoning
                }
            else:
                logger.error("No proposals available for fallback selection")
                return {
                    "current_stage": "selection_failed",
                    "errors": ["JSON extraction failed and no proposals available"]
                }
        
        selected_name = selection_json.get("selected_approach", "")
        reasoning = selection_json.get("reasoning", "")
        
        # Find the selected proposal
        final_solution = None
        for proposal in all_proposals:
            if proposal["approach_name"] == selected_name or selected_name in proposal["approach_name"]:
                final_solution = proposal
                break
        
        if not final_solution and all_proposals:
            # Fallback: select highest scoring proposal
            final_solution = max(all_proposals, key=lambda p: p["novelty_score"] + p["feasibility_score"])
            reasoning += f"\n(Fallback: Selected highest scoring proposal)"
        
        logger.info(f"✅ Selected: {final_solution['approach_name'] if final_solution else 'None'}")
        
        return {
            "current_stage": "solution_selected",
            "final_solution": final_solution,
            "selection_reasoning": reasoning
        }
        
    except Exception as e:
        logger.error(f"Solution selection failed: {e}")
        
        # Try to salvage by selecting highest scoring proposal
        try:
            all_proposals = []
            for round_data in state.get("debate_rounds", []):
                all_proposals.extend(round_data.get("proposals", []))
            
            if all_proposals:
                final_solution = max(all_proposals, key=lambda p: p.get("novelty_score", 0) + p.get("feasibility_score", 0))
                logger.info(f"✅ Emergency Fallback Selected: {final_solution['approach_name']}")
                return {
                    "current_stage": "solution_selected",
                    "final_solution": final_solution,
                    "selection_reasoning": f"Emergency selection due to error: {str(e)}"
                }
        except Exception as fallback_error:
            logger.error(f"Fallback selection also failed: {fallback_error}")
        
        return {
            "current_stage": "selection_failed",
            "errors": [f"Selection failed: {str(e)}"]
        }


# ============================================
# Research Report Builder (no LLM — uses state data)
# ============================================

def _build_research_report(state: AutoGITState) -> str:
    """
    Build a comprehensive RESEARCH_REPORT.md from all collected state data.
    Includes: SOTA papers with citations, novelty analysis, debate history,
    selection reasoning, and implementation notes. No LLM call needed.
    """
    from datetime import datetime as _dt

    idea          = state.get("idea", "Unknown")
    sel_problem   = state.get("selected_problem", "")
    sel_reasoning = state.get("selection_reasoning", "")
    final_sol     = state.get("final_solution") or {}
    rc            = state.get("research_context") or {}
    cb            = rc.get("compound_beta_research") or {}
    papers        = rc.get("papers") or []
    impls         = rc.get("implementations") or []
    debate_rounds = state.get("debate_rounds") or []
    persp_cfgs    = state.get("dynamic_perspective_configs") or []

    # Import resolved-model tracking (lazy, so it never breaks if import fails)
    try:
        from src.utils.model_manager import get_resolved_models as _grm
        _resolved_models = _grm()
    except Exception:
        try:
            from utils.model_manager import get_resolved_models as _grm
            _resolved_models = _grm()
        except Exception:
            _resolved_models = {}

    lines: list[str] = []
    def h(n, t):  lines.append(f"\n{'#' * n} {t}\n")
    def hr():     lines.append("\n---\n")
    def p(t=""):  lines.append(t)

    # ── Title ──────────────────────────────────────────────────────────────
    lines.append(f"# Research Report: {idea}")
    lines.append(f"\n*Generated by Auto-GIT on {_dt.now().strftime('%Y-%m-%d %H:%M')} UTC*\n")
    hr()

    # ── 0. Pipeline Configuration ─────────────────────────────────────────
    h(2, "0. Pipeline Configuration — Models Used")
    _STAGE_PROFILES = [
        ("🔍 Research & SOTA Web Search",         "research"),
        ("🧠 Expert Perspective Generation",      "balanced"),
        ("📋 Problem Extraction",                  "fast"),
        ("💡 Solution Generation (per expert)",   "balanced"),
        ("🔎 Critique & Cross-Review",             "reasoning"),
        ("🏆 Solution Selection & Ranking",        "reasoning"),
        ("💻 Code Generation",                     "powerful"),
        ("🔧 Code Fixing (if needed)",             "fast"),
    ]
    p("| Pipeline Stage | Profile | Resolved Model |")
    p("|----------------|---------|----------------|")
    for stage, prof in _STAGE_PROFILES:
        resolved = _resolved_models.get(prof, "*(not used this run)*")
        p(f"| {stage} | `{prof}` | `{resolved}` |")
    p()
    if _resolved_models:
        p("> **Profile strategy:** `research` = Groq compound-beta first (live web search) · "
          "`balanced/fast/powerful/reasoning` = `openrouter/free` meta-router first "
          "(auto-picks best of 27+ free models, 200K ctx) → named models → Groq fallback")
    hr()

    # ── 1. Research Question ───────────────────────────────────────────────
    h(2, "1. Research Question")
    p(f"**Goal:** {idea}")
    if sel_problem:
        p(f"\n**Focused Problem:**")
        p(f"> {sel_problem}")

    # ── 2. State of the Art ────────────────────────────────────────────────
    h(2, "2. State of the Art")
    sota = cb.get("sota_summary", "")
    if sota:
        p(sota)
    else:
        p("*(Web search not available — see papers below)*")

    # Benchmarks
    benchmarks = cb.get("benchmarks") or []
    if benchmarks:
        h(3, "Current Benchmarks")
        p("| Benchmark | Metric | Best Result | Model |")
        p("|-----------|--------|-------------|-------|")
        for b in benchmarks:
            p(f"| {b.get('name','?')} | {b.get('metric','?')} | {b.get('best_result','?')} | {b.get('model','?')} |")

    # Recent advances
    advances = cb.get("recent_advances") or []
    if advances:
        h(3, "Recent Advances")
        for a in advances:
            p(f"- {a}")

    # ── 3. Literature Review & Citations ──────────────────────────────────
    h(2, "3. Literature Review")
    if papers:
        for i, paper in enumerate(papers, 1):
            title   = paper.get("title", "Unknown")
            authors = paper.get("authors", "")
            year    = paper.get("year", "")
            url     = paper.get("url", "")
            contrib = paper.get("summary", paper.get("contribution", ""))

            p(f"**[{i}] {title}**")
            if authors or year:
                meta = []
                if authors: meta.append(authors)
                if year:    meta.append(str(year))
                p(f"*{' · '.join(meta)}*")
            if url:
                p(f"🔗 <{url}>")
            if contrib:
                p(f"\n> {contrib}")
            p()
    else:
        p("No papers found in research context.")

    # Open problems from SOTA
    open_probs = cb.get("open_problems") or []
    if open_probs:
        h(3, "Open Problems Identified by Research")
        for op in open_probs:
            p(f"- {op}")

    # Key insights
    insights = cb.get("key_insights") or []
    if insights:
        h(3, "Key Insights for Implementation")
        for ins in insights:
            p(f"- {ins}")

    # Existing implementations
    if impls:
        h(3, "Existing Implementations")
        for imp in impls:
            name = imp.get("title", imp.get("name", "?"))
            url  = imp.get("url", "")
            desc = imp.get("description", "")
            link = f" — <{url}>" if url else ""
            p(f"- **{name}**{link}")
            if desc:
                p(f"  {desc}")

    # ── 4. Expert Perspectives ────────────────────────────────────────────
    h(2, "4. Expert Perspectives")
    if persp_cfgs:
        for pc in persp_cfgs:
            name = pc.get("name", "?")
            role = pc.get("role", "")
            focus = pc.get("focus_areas") or pc.get("expertise") or []
            p(f"**{name}**")
            if role: p(f"*{role}*")
            if focus:
                if isinstance(focus, list):
                    p(f"Focus: {', '.join(str(f) for f in focus)}")
                else:
                    p(f"Focus: {focus}")
            p()
    else:
        p("Standard perspectives: ML Researcher · Systems Engineer · Applied Scientist")

    # ── 5. Debate & Proposals ─────────────────────────────────────────────
    h(2, "5. Multi-Agent Debate")
    all_proposals: list = []
    all_critiques: list = []
    for rd in debate_rounds:
        all_proposals.extend(rd.get("proposals") or [])
        all_critiques.extend(rd.get("critiques") or [])

    if all_proposals:
        h(3, f"Proposals ({len(all_proposals)} total)")
        for i, prop in enumerate(all_proposals, 1):
            name     = prop.get("approach_name", f"Proposal {i}")
            persp    = prop.get("perspective", "")
            innov    = prop.get("key_innovation", "")
            approach = prop.get("approach", "")
            novelty  = prop.get("novelty_score", "?")
            feasib   = prop.get("feasibility_score", "?")

            p(f"**{i}. {name}**  *(by {persp})*")
            if approach: p(f"{approach[:300]}{'...' if len(approach) > 300 else ''}")
            if innov:    p(f"\n🔑 **Key Innovation:** {innov}")
            p(f"📊 Novelty: `{novelty}` · Feasibility: `{feasib}`")

            crits = [c for c in all_critiques if c.get("solution_id") == name]
            if crits:
                p("\n*Expert Critiques:*")
                for c in crits:
                    rec       = c.get("recommendation", "")
                    rec_icon  = {"accept": "✅", "revise": "⚠️", "reject": "❌"}.get(rec, "•")
                    reviewer  = c.get("reviewer_perspective", "?")
                    assessment = c.get("overall_assessment", "")
                    feas      = c.get("feasibility_score", "")
                    strengths  = c.get("strengths") or []
                    weaknesses = c.get("weaknesses") or []
                    concerns   = c.get("specific_concerns") or []
                    suggestions = c.get("improvement_suggestions") or []

                    feas_str = f" | Feasibility: `{feas}`" if feas != "" else ""
                    p(f"\n  {rec_icon} **{reviewer}** — Recommendation: `{rec}` | Assessment: `{assessment}`{feas_str}")
                    if strengths:
                        p("  *Strengths:*")
                        for s in strengths:
                            p(f"    - ✅ {s}")
                    if weaknesses:
                        p("  *Weaknesses:*")
                        for w in weaknesses:
                            p(f"    - ⚠️ {w}")
                    if concerns:
                        p("  *Specific Concerns:*")
                        for cn in concerns:
                            p(f"    - 🔍 {cn}")
                    if suggestions:
                        p("  *Improvement Suggestions:*")
                        for sg in suggestions:
                            p(f"    - 💡 {sg}")
            p()

    # ── 6. Selected Solution & Novelty Analysis ───────────────────────────
    h(2, "6. Selected Solution")
    sol_name = final_sol.get("approach_name", final_sol.get("title", "Unknown"))
    p(f"## 🏆 {sol_name}")

    approach_desc = final_sol.get("approach", "")
    if approach_desc:
        p(f"\n{approach_desc}")

    innovation = final_sol.get("key_innovation", "")
    if innovation:
        h(3, "Key Innovation")
        p(innovation)

    architecture = final_sol.get("architecture", "")
    if architecture:
        h(3, "Architecture")
        if isinstance(architecture, dict):
            for k, v in architecture.items():
                p(f"**{k}:** {v}")
        else:
            p(str(architecture)[:600])

    # Why this solution was chosen
    h(3, "Why This Solution Was Selected")
    if sel_reasoning:
        p(sel_reasoning)
    elif final_sol.get("rationale"):
        p(final_sol["rationale"])
    else:
        p("*(Selection reasoning not captured)*")

    # Proposal comparison table — shows why winner beat the others
    if all_proposals:
        h(4, "Proposal Comparison (all candidates ranked)")
        # Deduplicate by approach_name, keeping best composite score
        seen_props: dict = {}
        for prop in all_proposals:
            pname = prop.get("approach_name", "?")
            try:
                composite = (float(prop.get("novelty_score") or 0) + float(prop.get("feasibility_score") or 0)) / 2
            except (TypeError, ValueError):
                composite = 0.0
            if pname not in seen_props or composite > seen_props[pname]["_composite"]:
                seen_props[pname] = dict(prop)
                seen_props[pname]["_composite"] = composite
        ranked_props = sorted(seen_props.values(), key=lambda x: x["_composite"], reverse=True)

        p("| Rank | Proposal | Expert | Novelty | Feasibility | Score | Peer Votes |")
        p("|------|----------|--------|---------|-------------|-------|------------|")
        for idx, prop in enumerate(ranked_props, 1):
            pname   = prop.get("approach_name", "?")
            persp   = prop.get("perspective", "?")
            n_score = prop.get("novelty_score", "?")
            f_score = prop.get("feasibility_score", "?")
            comp    = prop.get("_composite", 0.0)
            prop_crits = [c for c in all_critiques if c.get("solution_id") == pname]
            accepts = sum(1 for c in prop_crits if c.get("recommendation") == "accept")
            revises = sum(1 for c in prop_crits if c.get("recommendation") == "revise")
            rejects = sum(1 for c in prop_crits if c.get("recommendation") == "reject")
            rec_summary = f"{accepts}✅ {revises}⚠️ {rejects}❌"
            winner_marker = " 🏆" if pname == sol_name else ""
            p(f"| {idx} | **{pname}{winner_marker}** | {persp} | {n_score} | {f_score} | {comp:.2f} | {rec_summary} |")
        p()

        if len(ranked_props) > 1:
            runner_up = ranked_props[1] if ranked_props[0].get("approach_name") == sol_name else ranked_props[0]
            runner_name = runner_up.get("approach_name", "?")
            runner_innovation = runner_up.get("key_innovation", "")
            winner_innovation = final_sol.get("key_innovation", "")
            p(f"**Why {sol_name} over {runner_name}:**")
            if winner_innovation and runner_innovation:
                p(f"- Winner's key advantage: *{winner_innovation}*")
                p(f"- Runner-up's approach: *{runner_innovation}*")
            winner_crits  = [c for c in all_critiques if c.get("solution_id") == sol_name]
            runner_crits  = [c for c in all_critiques if c.get("solution_id") == runner_name]
            winner_accepts = sum(1 for c in winner_crits if c.get("recommendation") == "accept")
            runner_accepts = sum(1 for c in runner_crits if c.get("recommendation") == "accept")
            if winner_accepts != runner_accepts:
                p(f"- Peer acceptance votes: {sol_name} = {winner_accepts} accept(s) vs {runner_name} = {runner_accepts} accept(s)")
            p()

    # Novelty analysis
    h(3, "Novelty Analysis")
    novelty_score = final_sol.get("novelty_score", "?")
    feasib_score  = final_sol.get("feasibility_score", "?")
    p(f"- **Novelty Score:** {novelty_score}/1.0")
    p(f"- **Feasibility Score:** {feasib_score}/1.0")

    # Compare against existing work
    if papers:
        p(f"\n**Compared to existing work ({len(papers)} papers reviewed):**")
        p(
            "The selected solution builds upon the surveyed literature while "
            "addressing the open problems identified above. Key differentiators:"
        )
        if innovation:
            p(f"- {innovation}")
        for op in (open_probs or []):
            p(f"- Directly addresses: *{op}*")
    if insights:
        p("\n**Grounded in these research insights:**")
        for ins in insights:
            p(f"- {ins}")

    # ── 7. References ─────────────────────────────────────────────────────
    h(2, "7. References")
    if papers:
        for i, paper in enumerate(papers, 1):
            title   = paper.get("title", "Unknown")
            authors = paper.get("authors", "")
            year    = paper.get("year", "")
            url     = paper.get("url", "")
            ref = f"[{i}] "
            if authors: ref += f"{authors}. "
            ref += f'"{title}"'
            if year: ref += f" ({year})"
            if url:  ref += f". <{url}>"
            p(ref)
    else:
        p("No references available.")

    hr()
    p(f"*Report generated automatically by Auto-GIT pipeline · {_dt.now().strftime('%Y-%m-%d')}*")

    return "\n".join(lines)


# ============================================
# Node 6.5: Architecture Specification (Pre-Code-Gen Planning)
# ============================================

async def architect_spec_node(state: AutoGITState) -> Dict[str, Any]:
    """
    Node 6.5: Generate detailed technical specification before code generation.

    This replaces the ad-hoc file planning inside code_generation_node with a
    dedicated reasoning step that produces a comprehensive technical spec:

    1. File plan with PURPOSE and ESTIMATED LINE COUNT for each file
    2. Data flow diagram (which file calls which, in what order)
    3. Key algorithms with pseudocode (not just names)
    4. External dependencies with exact versions
    5. Entry point behavior (what main.py prints/returns)
    6. Test scenarios (what would a user run to verify it works)

    The spec is stored in state["architecture_spec"] and injected into every
    code_generation prompt, giving the LLM a clear blueprint to follow.
    """
    logger.info("📐 Architect Spec Node — designing technical blueprint")

    from rich.console import Console as _RCAS
    _console = _RCAS()
    _console.print("\n[bold blue]📐 Generating Technical Architecture Specification...[/bold blue]")

    try:
        idea = state.get("idea", "")
        solution = state.get("final_solution") or {}
        approach = solution.get("approach_name", "")
        innovation = solution.get("key_innovation", "")
        architecture = solution.get("architecture_design", "")
        implementation_plan = solution.get("implementation_plan", [])
        research_summary = state.get("research_summary", "") or ""

        llm = get_fallback_llm("balanced")

        spec_prompt = (
            "You are a senior software architect creating a DETAILED technical specification "
            "for a production-quality Python project.\n\n"
            f"PROJECT IDEA: {idea}\n"
            f"APPROACH: {approach}\n"
            f"KEY INNOVATION: {innovation}\n"
            f"ARCHITECTURE: {architecture}\n"
            f"IMPLEMENTATION PLAN: {implementation_plan}\n\n"
            "Generate a comprehensive technical specification. Return ONLY valid JSON:\n"
            "{\n"
            '  "project_name": "short-descriptive-name",\n'
            '  "one_line_description": "What this does in one sentence",\n'
            '  "files": [\n'
            '    {\n'
            '      "name": "filename.py",\n'
            '      "purpose": "What this file does and why it exists",\n'
            '      "estimated_lines": 150,\n'
            '      "key_classes": [{"name": "ClassName", "purpose": "...", '
            '"key_methods": ["method1(self, arg: type) -> return_type"]}],\n'
            '      "key_functions": ["function_name(arg: type) -> return_type"],\n'
            '      "imports_from_project": ["other_file.ClassName"],\n'
            '      "external_deps": ["numpy", "torch"]\n'
            "    }\n"
            "  ],\n"
            '  "data_flow": "A imports B.X, B imports C.Y, main.py imports A and runs A.run()",\n'
            '  "key_algorithms": [\n'
            '    {"name": "Algorithm Name", "file": "filename.py", '
            '"pseudocode": "step-by-step logic (as detailed as needed)"}\n'
            "  ],\n"
            '  "entry_point_behavior": "What main.py does when run: parses args, creates X, runs Y, prints Z",\n'
            '  "expected_output": "What the user sees when they run python main.py",\n'
            '  "test_scenarios": [\n'
            '    "python main.py → should print X",\n'
            '    "python main.py --verbose → should show detailed output"\n'
            "  ],\n"
            '  "total_estimated_lines": "as many as the project needs — no artificial limit"\n'
            "}\n\n"
            "RULES:\n"
            "1. Total project should have AS MANY lines as the idea requires — write everything fully, never truncate to hit a line target\n"
            "2. Each implementation file should be as long as needed — no upper limit; fully implement every class and function\n"
            "3. main.py must produce VISIBLE OUTPUT when run (not just exit silently)\n"
            "4. NO file should be named after a Python package (torch.py, numpy.py, flask.py, pytest.py, etc.)\n"
            "5. NO circular imports — if A imports B, B must NOT import A\n"
            "6. Every algorithm must have real pseudocode, not just a name\n"
            "7. List ALL cross-file dependencies explicitly\n"
            "8. Include requirements.txt and README.md in the file list\n"
            "9. SELF-CONTAINED DEMO: main.py must work WITHOUT external services (Redis, PostgreSQL, RabbitMQ, etc.)\n"
            "   - Use Python stdlib fallbacks: queue.PriorityQueue instead of Redis, sqlite3 instead of PostgreSQL\n"
            "   - Use threading instead of Celery/RQ, http.server instead of gunicorn\n"
            "   - The demo should create sample data, process it, and print clear results\n"
            "10. requirements.txt should ONLY list packages the code ACTUALLY imports — no phantom deps\n"
            "11. ALL cross-file imports must be ABSOLUTE (from module import X), NEVER relative (from .module import X) — the project has no __init__.py\n"
            "12. ALL project files are in a FLAT directory (no subdirectories). NEVER use dotted package imports for local files (e.g. `from task_queue.task import Task`). Instead use `from task import Task` directly.\n"
            "13. Do NOT add a demo/interactive mode that calls input() when run without arguments. "
            "If the user wants to run interactively, they should pass --demo or --interactive explicitly. "
            "The DEFAULT behavior (no args) should produce meaningful output and exit cleanly.\n"
            "14. If a data structure (grid, matrix, table) already has boundary/border elements built into it, "
            "the renderer/display function must NOT add ANOTHER border on top — no double borders."
        )

        messages = [HumanMessage(content=spec_prompt)]
        # FIX: timeout kwarg was silently ignored by LangChain's ainvoke().
        # Use asyncio.wait_for() for a REAL timeout.
        import asyncio as _asyncio_spec
        try:
            response = await _asyncio_spec.wait_for(
                llm.ainvoke(messages),
                timeout=300  # 5 minutes hard cap
            )
        except _asyncio_spec.TimeoutError:
            logger.warning("  ⏰ Architect spec LLM call timed out after 300s — retrying with fast model")
            _console.print("  [yellow]⏰ Spec timed out — retrying with faster model...[/yellow]")
            _fast_llm = get_fallback_llm("fast")
            try:
                response = await _asyncio_spec.wait_for(
                    _fast_llm.ainvoke(messages),
                    timeout=120
                )
            except _asyncio_spec.TimeoutError:
                logger.error("  ❌ Architect spec timed out on retry — proceeding without spec")
                _console.print("  [red]❌ Spec generation timed out — code gen will proceed without blueprint[/red]")
                return {
                    "current_stage": "architect_spec_failed",
                    "architecture_spec": None,
                    "_architecture_spec_text": "",
                }

        import json as _jsa, re as _resa
        raw = response.content.strip()
        # Strip markdown fences
        raw = _resa.sub(r"^```[a-z]*\n?", "", raw)
        raw = _resa.sub(r"\n?```$", "", raw.strip())
        # Handle thinking models (<think>...</think> prefix)
        if "<think>" in raw:
            think_end = raw.rfind("</think>")
            if think_end != -1:
                raw = raw[think_end + len("</think>"):].strip()
        # Strip any leading/trailing non-JSON prose
        # Find first { and last }
        first_brace = raw.find("{")
        last_brace = raw.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            raw = raw[first_brace:last_brace + 1]
        # Try to parse JSON; if it fails, try fixing common issues
        try:
            spec = _jsa.loads(raw)
        except _jsa.JSONDecodeError:
            # Try removing trailing commas before } or ]
            cleaned = _resa.sub(r',\s*([}\]])', r'\1', raw)
            # Try removing control characters
            cleaned = _resa.sub(r'[\x00-\x1f\x7f]', ' ', cleaned)
            spec = _jsa.loads(cleaned)

        # Display spec summary
        total_lines = spec.get("total_estimated_lines", 0)
        file_count = len(spec.get("files", []))
        algo_count = len(spec.get("key_algorithms", []))

        _console.print(f"  [bold]Project:[/bold] {spec.get('project_name', 'N/A')}")
        _console.print(f"  [bold]Files:[/bold] {file_count} | [bold]Est. lines:[/bold] {total_lines}"
                       f" | [bold]Algorithms:[/bold] {algo_count}")
        _console.print(f"  [bold]Entry point:[/bold] {spec.get('entry_point_behavior', 'N/A')[:100]}")

        for f in spec.get("files", []):
            _console.print(f"    {f['name']}: {f.get('estimated_lines', '?')} lines — {f.get('purpose', '')[:60]}")

        logger.info(f"  📐 Spec: {file_count} files, {total_lines} est. lines, {algo_count} algorithms")

        # Build human-readable spec text to inject into code gen prompts
        spec_text_lines = [
            "ARCHITECTURE SPECIFICATION (you MUST follow this blueprint):",
            f"Project: {spec.get('project_name', '')} — {spec.get('one_line_description', '')}",
            f"Data flow: {spec.get('data_flow', '')}",
            f"Entry point: {spec.get('entry_point_behavior', '')}",
            f"Expected output: {spec.get('expected_output', '')}",
            "",
        ]
        for f in spec.get("files", []):
            spec_text_lines.append(f"FILE: {f['name']} ({f.get('estimated_lines', 100)}+ lines)")
            spec_text_lines.append(f"  Purpose: {f.get('purpose', '')}")
            for cls in f.get("key_classes", []):
                spec_text_lines.append(f"  class {cls['name']}: {cls.get('purpose', '')}")
                for m in cls.get("key_methods", []):
                    spec_text_lines.append(f"    {m}")
            for fn in f.get("key_functions", []):
                spec_text_lines.append(f"  {fn}")
            if f.get("imports_from_project"):
                spec_text_lines.append(f"  Imports: {', '.join(f.get('imports_from_project', []))}")
            spec_text_lines.append("")

        if spec.get("key_algorithms"):
            spec_text_lines.append("KEY ALGORITHMS:")
            for algo in spec.get("key_algorithms", []):
                spec_text_lines.append(f"  {algo['name']} (in {algo.get('file', '?')}):")
                for line in algo.get("pseudocode", "").splitlines():
                    spec_text_lines.append(f"    {line}")
                spec_text_lines.append("")

        spec_text = "\n".join(spec_text_lines)

        return {
            "current_stage": "architect_spec_complete",
            "architecture_spec": spec,
            "_architecture_spec_text": spec_text,
        }

    except Exception as e:
        logger.warning(f"Architect spec failed ({e}) — proceeding without spec")
        _console.print(f"  [dim yellow]Spec generation failed ({e}) — code gen will proceed without blueprint[/dim yellow]")
        return {
            "current_stage": "architect_spec_failed",
            "architecture_spec": None,
            "_architecture_spec_text": "",
        }


# ============================================
# Node 7: Code Generation
# ============================================

async def code_generation_node(state: AutoGITState) -> Dict[str, Any]:
    """
    Node 7: Generate implementation code using DeepSeek Coder
    
    Generates:
    - model.py: Core model implementation
    - train.py: Training loop
    - evaluate.py: Evaluation metrics
    - data_loader.py: Data handling
    - utils.py: Helper functions
    - README.md: Documentation
    - requirements.txt: Dependencies
    """
    logger.info("💻 Code Generation Node")
    
    # Track code-gen-level errors (contract violations, circular imports, etc.)
    # so they propagate to downstream nodes (testing/fixing).
    execution_errors: list = []
    
    try:
        # Use powerful model for code generation
        llm = get_llm("powerful")
        try:
            from ..utils.model_manager import get_profile_primary as _gpp7
        except Exception:
            from utils.model_manager import get_profile_primary as _gpp7  # type: ignore
        from rich.console import Console as _RC7
        console = _RC7()
        console.print(f"  [dim]🤖 Model: powerful → {_gpp7('powerful')}[/dim]")
        
        solution = state.get("final_solution")
        if not solution:
            logger.warning("No solution found, skipping code generation")
            return {
                "current_stage": "code_generation_skipped",
                "generated_code": {}
            }
        
        idea = state["idea"]
        approach = solution["approach_name"]
        innovation = solution["key_innovation"]
        architecture = solution["architecture_design"]
        implementation_plan = solution.get("implementation_plan", [])

        # ── Load structured requirements (from Node 0) ──────────────────
        _requirements = state.get("requirements") or {}
        _req_context = ""
        if _requirements:
            _req_parts = ["PROJECT REQUIREMENTS (from analysis):"]
            if _requirements.get("project_type"):
                _req_parts.append(f"  Type: {_requirements['project_type']}")
            if _requirements.get("complexity"):
                _req_parts.append(f"  Complexity: {_requirements['complexity']}")
            if _requirements.get("core_components"):
                _req_parts.append(f"  Core components: {', '.join(_requirements['core_components'])}")
            if _requirements.get("key_features"):
                _req_parts.append(f"  Must-have features: {', '.join(_requirements['key_features'])}")
            if _requirements.get("data_flow"):
                _req_parts.append(f"  Data flow: {_requirements['data_flow']}")
            if _requirements.get("success_criteria"):
                _req_parts.append(f"  Success criteria: {_requirements['success_criteria']}")
            if _requirements.get("test_scenarios"):
                for _t in _requirements['test_scenarios']:
                    if isinstance(_t, dict):
                        _req_parts.append(f"  Test: {_t.get('name','')} — input: {_t.get('input','')}, expect: {_t.get('expected','')}")
            if _requirements.get("risk_areas"):
                _req_parts.append(f"  Risk areas: {', '.join(_requirements['risk_areas'])}")
            _req_context = "\n".join(_req_parts)
            logger.info(f"  📋 Injecting {len(_req_parts)-1} requirement fields into code gen")

        # ── Load research context (from Node 1) ─────────────────────────
        _research_ctx = ""
        _research_summary = state.get("research_summary", "") or ""
        if _research_summary:
            _research_ctx = f"RESEARCH FINDINGS (use these to inform implementation):\n{_research_summary}"
            logger.info(f"  🔬 Injecting research summary ({len(_research_summary)} chars) into code gen")

        # ── Load lessons from past runs ──────────────────────────────────
        _codegen_lessons = ""
        try:
            from ..utils.codegen_error_memory import get_error_memory as _gem_cg
            _codegen_lessons = _gem_cg().get_top_lessons(n=15)
            if _codegen_lessons:
                logger.info(f"  📚 Loaded {_codegen_lessons.count(chr(10))} lessons from past runs")
        except Exception as _le:
            logger.debug(f"  Could not load codegen lessons: {_le}")

        # ── Read architecture spec (from Node 6.5) ──────────────────────────
        _arch_spec_text = state.get("_architecture_spec_text") or ""
        _arch_spec = state.get("architecture_spec") or {}

        # ── Multi-language support ──────────────────────────────────────
        _target_language = (_requirements.get("detected_language") or "python").lower()
        _lang_instructions = ""
        _scaffold_files: Dict[str, str] = {}
        try:
            from src.utils.language_support import (
                get_code_gen_instructions, get_scaffolding, get_file_extension,
            )
            _lang_instructions = get_code_gen_instructions(_target_language)
            if _target_language != "python":
                _scaffold_files = get_scaffolding(_target_language, approach.replace(" ", "-"))
                console.print(f"  [magenta]🌐 Generating {_target_language.upper()} code[/magenta]")
        except Exception as _lang_err:
            logger.debug(f"  Language support import failed: {_lang_err}")
            _target_language = "python"
        
        # If architect spec provided a file list, prefer it over LLM re-planning
        _spec_file_list = [f["name"] for f in _arch_spec.get("files", []) if f.get("name")]
        
        # ── Step 1: Ask the LLM what files this project actually needs ──────────
        plan_messages = [
            SystemMessage(content=(
                "You are a senior software architect. "
                "Given a project idea and chosen approach, decide what source files to create. "
                "Reply with ONLY a JSON object like:\n"
                '{"files": ["main.py", "utils.py", "README.md", "requirements.txt"]}\n'
                "Rules:\n"
                "- Include as many files as the project needs — split by responsibility, not by a count limit; complex projects should have more files\n"
                "- Always include a main.py (entry point), README.md, and requirements.txt\n"
                "- Use FULL descriptive names (scheduler.py, spike_encoder.py, anomaly_detector.py, router.py) — NEVER 2-4 letter abbreviations like 'die.py', 'grm.py', 'rl.py', 'mll.py'\n"
                "- File names must be readable by a human who has not seen the project before\n"
                "- Do NOT include test files or __init__.py\n"
                "- Only include files whose code you will fully implement (no stub-only files)\n"
                "- CRITICAL: NEVER name a file after an existing Python package or stdlib module. "
                "Forbidden names include (but are not limited to): torch.py, numpy.py, pandas.py, "
                "scipy.py, sklearn.py, tensorflow.py, keras.py, math.py, os.py, sys.py, "
                "random.py, time.py, typing.py, json.py, logging.py, pathlib.py, abc.py, "
                "io.py, re.py, copy.py, enum.py, functools.py, itertools.py, collections.py, "
                "threading.py, asyncio.py, dataclasses.py, unittest.py, warnings.py. "
                "If the project uses PyTorch, name the file after what IT DOES: "
                "e.g. dragon_model.py, evolution_trainer.py, gating_layer.py\n"
                "Reply with ONLY the JSON, no markdown fences."
            )),
            HumanMessage(content=(
                f"Project idea: {idea}\n"
                f"Chosen approach: {approach}\n"
                f"Architecture: {architecture}"
            )),
        ]
        plan_response = await llm.ainvoke(plan_messages)
        file_list = ["main.py", "utils.py", "README.md", "requirements.txt"]  # fallback
        try:
            import json, re
            raw = plan_response.content.strip()
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
            parsed = json.loads(raw)
            if isinstance(parsed.get("files"), list) and parsed["files"]:
                file_list = parsed["files"]
                logger.info(f"  File plan: {file_list}")
        except Exception:
            logger.warning("  Could not parse file plan, using defaults")

        # ── Override with architect spec file list if available ──────────────
        if _spec_file_list:
            # Ensure main.py, README.md, requirements.txt are included
            for _required in ["main.py", "README.md", "requirements.txt"]:
                if _required not in _spec_file_list:
                    _spec_file_list.append(_required)
            file_list = _spec_file_list
            logger.info(f"  📐 Using architect spec file list: {file_list}")

        # ── Post-parse: strip any file that shadows a known package/stdlib module ──
        # This catches whatever the LLM sneaks past the prompt rule.
        import sys as _sys
        _KNOWN_PKG_STEMS = {
            # popular third-party
            "torch", "numpy", "pandas", "scipy", "sklearn", "tensorflow", "keras",
            "matplotlib", "seaborn", "plotly", "PIL", "cv2", "transformers",
            "datasets", "tokenizers", "accelerate", "diffusers", "langchain",
            "openai", "anthropic", "groq", "fastapi", "flask", "django",
            "requests", "httpx", "aiohttp", "pydantic", "sqlalchemy", "redis",
            "celery", "pytest", "hypothesis", "click", "typer", "rich",
            # stdlib modules that are often accidentally shadowed
            "os", "sys", "re", "io", "abc", "gc", "math", "cmath", "time",
            "random", "copy", "enum", "json", "csv", "logging", "pathlib",
            "typing", "types", "collections", "functools", "itertools",
            "operator", "threading", "asyncio", "concurrent", "multiprocessing",
            "subprocess", "socket", "ssl", "http", "urllib", "email", "html",
            "xml", "sqlite3", "hashlib", "hmac", "secrets", "base64",
            "struct", "array", "queue", "heapq", "bisect", "datetime",
            "calendar", "locale", "string", "textwrap", "unicodedata",
            "unittest", "dataclasses", "warnings", "traceback", "inspect",
            "importlib", "pkgutil", "ast", "dis", "token", "tokenize",
        }
        _sanitised = []
        for _fn in file_list:
            _stem = _fn.rsplit(".", 1)[0].lower()  # "torch.py" → "torch"
            if _stem in _KNOWN_PKG_STEMS:
                _safe = f"project_{_stem}.py"
                logger.warning(
                    f"  ⚠️  File planner proposed '{_fn}' — shadows package/stdlib '{_stem}'. "
                    f"Renamed to '{_safe}'."
                )
                _sanitised.append(_safe)
            else:
                _sanitised.append(_fn)
        file_list = _sanitised

        # ── Step 1b: Generate interface contracts for cross-file consistency ───
        # One LLM call that defines ALL class names, method signatures, and
        # module-level constants BEFORE any file is generated.  Every parallel
        # _gen_file() call receives this contract so they all agree on the API.
        _contract_text: str = ""
        _parsed_c: dict = {}  # parsed contract JSON — shared with enforcement below
        _py_files_only = [f for f in file_list if f.endswith(".py") and f != "main.py"]
        if len(_py_files_only) >= 1:
            try:
                import json as _json_c, re as _re_c
                _contract_msgs = [
                    SystemMessage(content=(
                        "You are a software architect designing API contracts for a multi-file Python project.\n"
                        "Output ONLY valid JSON — no markdown fences, no explanation.\n"
                        "Format:\n"
                        "{\n"
                        '  \"module_name_no_extension\": {\n'
                        '    \"classes\": [\n'
                        '      {\"name\": \"ClassName\", \"constructor\": \"def __init__(self, param: type = default) -> None\", \"public_methods\": [\"def method(self, x: int) -> str\"]}\n'
                        "    ],\n"
                        '    \"module_constants\": [\"CONST_NAME: int = 1\"],\n'
                        '    \"module_functions\": [\"def func(x: int) -> str\"]\n'
                        "  }\n"
                        "}\n\n"
                        "Rules:\n"
                        "1. Define contracts for ALL listed .py files\n"
                        "2. List EVERY constant that will be imported by other modules\n"
                        "3. List EVERY public class method that will be called from other files\n"
                        "4. NO circular imports — if A imports B, B must NOT import A\n"
                        "5. Use correct Python type hints: Optional[X], List[X], Dict[K,V]\n"
                        "6. Keep it minimal — only cross-file public interfaces"
                    )),
                    HumanMessage(content=(
                        f"Project: {idea}\nApproach: {approach}\n"
                        f"Architecture: {architecture}\n\n"
                        f"Generate contracts for these files: {_py_files_only}"
                    )),
                ]
                _contract_resp = await llm.ainvoke(_contract_msgs)
                _raw_c = _contract_resp.content.strip()
                _raw_c = _re_c.sub(r"^```[a-z]*\n?", "", _raw_c)
                _raw_c = _re_c.sub(r"\n?```$", "", _raw_c.strip())
                _parsed_c = _json_c.loads(_raw_c)
                # Build human-readable block to inject into every file prompt
                _clines = ["INTERFACE CONTRACT — you MUST implement these EXACT signatures (no other names allowed):"]
                for _mod, _spec in _parsed_c.items():
                    _clines.append(f"\n=== {_mod}.py ===")
                    for _k in _spec.get("module_constants", []):
                        _clines.append(f"  {_k}")
                    for _fn in _spec.get("module_functions", []):
                        _clines.append(f"  {_fn}")
                    for _cls in _spec.get("classes", []):
                        _clines.append(f"  class {_cls['name']}:")
                        if _cls.get("constructor"):
                            _clines.append(f"    {_cls['constructor']}")
                        for _m in _cls.get("public_methods", []):
                            _clines.append(f"    {_m}")
                _contract_text = "\n".join(_clines)
                logger.info(f"  📋 Interface contract generated for {len(_parsed_c)} module(s)")
            except Exception as _ce:
                logger.warning(f"  ⚠️  Contract generation failed ({_ce}) — proceeding without contract")
                _contract_text = ""
        # ─────────────────────────────────────────────────────────────────────

        # ── Step 2: Build per-file prompts based on actual content ────────────
        def _build_readme_skeleton() -> str:
            """Dynamically build a README skeleton based on what we know about this project."""
            idea_lower = (idea + " " + approach + " " + architecture).lower()

            # ── Detect which optional sections apply ─────────────────────────
            has_cli      = any(k in idea_lower for k in ("cli", "command", "script", "argparse", "entrypoint", "entry point"))
            has_api      = any(k in idea_lower for k in ("api", "rest", "fastapi", "flask", "endpoint", "http", "server"))
            has_config   = any(k in idea_lower for k in ("config", "env", "environment variable", "yaml", "token", "secret", "key"))
            has_docker   = any(k in idea_lower for k in ("docker", "container", "kubernetes", "k8s", "helm"))
            has_ml       = any(k in idea_lower for k in ("model", "train", "inference", "embedding", "llm", "transformer", "neural", "torch", "tensorflow"))
            has_tests    = "test" in idea_lower or any(f.startswith("test_") for f in file_list)
            has_database = any(k in idea_lower for k in ("database", "sqlite", "postgres", "redis", "sql", "vector db", "vectordb"))
            has_async    = any(k in idea_lower for k in ("async", "asyncio", "concurrent", "parallel", "worker", "queue"))

            # ── File overview table rows from actual planned file list ────────
            file_rows = "\n".join(
                f"| `{f}` | <describe what {f} does> |"
                for f in file_list
            )

            # ── Architecture section ──────────────────────────────────────────
            # Never dump raw architecture/code into the README prompt — it confuses the model
            arch_hint = "<ASCII diagram or prose describing components and data flow — summarise the architecture in plain English>"

            # ── Build sections list dynamically ──────────────────────────────
            sections = []

            sections.append(
                "# <project name — short & descriptive>\n\n"
                "<one-sentence description of what this does and why it matters>\n\n"
                "---\n"
            )

            sections.append(
                "## Features\n\n"
                "- <core feature 1>\n"
                "- <core feature 2>\n"
                "- <core feature 3>\n"
                + ("- <ML/model capability>\n" if has_ml else "")
                + ("- <async/concurrent capability>\n" if has_async else "")
                + ("- <API endpoint or REST capability>\n" if has_api else "")
            )

            sections.append(
                "## Architecture\n\n"
                f"{arch_hint}\n"
            )

            install_steps = (
                "```bash\n"
                "git clone <repo-url>\n"
                "cd <repo-dir>\n"
                "pip install -r requirements.txt\n"
                + ("```\n\n> Requires Docker: `docker build -t <image> .`\n" if has_docker else "```\n")
            )
            sections.append(f"## Installation\n\n{install_steps}")

            # Usage: Python API
            python_usage = (
                "## Usage\n\n"
                "### Python API\n\n"
                "```python\n"
                "# <import the main class or function from main.py>\n"
                "# <show a minimal 3-5 line working example>\n"
                "```\n"
            )
            if has_cli:
                python_usage += (
                    "\n### CLI\n\n"
                    "```bash\n"
                    "python main.py --help\n"
                    "python main.py <required-arg> [--option value]\n"
                    "```\n"
                )
            if has_api:
                python_usage += (
                    "\n### API\n\n"
                    "```bash\n"
                    "# Start server\n"
                    "python main.py\n\n"
                    "# Example request\n"
                    "curl -X POST http://localhost:8000/<endpoint> -H 'Content-Type: application/json' -d '{\"key\": \"value\"}'\n"
                    "```\n"
                )
            sections.append(python_usage)

            sections.append(
                "## File Overview\n\n"
                "| File | Description |\n"
                "|------|-------------|\n"
                f"{file_rows}\n"
            )

            if has_ml:
                sections.append(
                    "## Models\n\n"
                    "| Model / Component | Purpose |\n"
                    "|-------------------|---------|\n"
                    "| `<model name>` | <what it's used for> |\n"
                )

            if has_database:
                sections.append(
                    "## Data Storage\n\n"
                    "<describe what is stored, schema or collection structure, how to initialise>\n"
                )

            if has_config:
                sections.append(
                    "## Configuration\n\n"
                    "| Variable | Default | Description |\n"
                    "|----------|---------|-------------|\n"
                    "| `<ENV_VAR>` | `<default>` | <what it controls> |\n\n"
                    "Copy `.env.example` to `.env` and fill in your values.\n"
                )
            else:
                sections.append("## Configuration\n\nNo external configuration required.\n")

            if has_tests:
                sections.append(
                    "## Testing\n\n"
                    "```bash\n"
                    "pytest tests/\n"
                    "```\n"
                )

            sections.append(
                "## Limitations\n\n"
                "- <known limitation or future work item 1>\n"
                "- <known limitation or future work item 2>\n"
            )

            sections.append("## License\n\nMIT\n")

            skeleton = "\n".join(sections)

            return (
                "You are a senior technical writer creating a README.md for an open-source project.\n\n"
                "PROJECT CONTEXT\n"
                f"  Idea      : {idea}\n"
                f"  Approach  : {approach}\n"
                f"  Innovation: {innovation}\n\n"
                "STRICT RULES — violating any of these will cause rejection:\n"
                "1. Write ONLY Markdown prose, tables, and lists. No standalone Python scripts.\n"
                "2. Code fences (```python) are ONLY allowed inside ## Usage as short illustrative examples (max 15 lines each).\n"
                "3. Replace EVERY <...> placeholder with real, specific, descriptive text about THIS project.\n"
                "4. Do NOT output a bare Python script. Do NOT wrap the whole README in a code fence.\n"
                "5. The document MUST start with a # heading and end with ## License.\n"
                "6. Write complete English sentences explaining what each component does and why.\n\n"
                "─────────────────── SKELETON (complete every section below) ───────────────────\n\n"
                f"{skeleton}\n"
                "────────────────────────────────────────────────────────────────────────────────\n\n"
                "OUTPUT: Return ONLY the completed Markdown document. No surrounding code fences."
            )

        def _file_prompt(fname: str) -> str:
            if fname == "README.md":
                return _build_readme_skeleton()
            if fname == "requirements.txt":
                return (
                    f"Generate requirements.txt for this project.\n\n"
                    f"Project: {idea}\nApproach: {approach}\n\n"
                    "CRITICAL RULES for requirements.txt:\n"
                    "1. List ONLY packages that are ACTUALLY imported in the code\n"
                    "2. Use ONLY modern, non-deprecated package versions available on PyPI today (2024/2025)\n"
                    "3. NEVER pin pytorch-lightning to versions before 2.0.0 — use 'lightning>=2.3' instead\n"
                    "4. NEVER use 'torch>=1.8.*' — use exact version like 'torch>=2.0.0' or just 'torch'\n"
                    "5. Prefer loose version bounds (>=X.Y) over exact pins (==X.Y.Z) for heavy packages\n"
                    "6. If the project uses only Python stdlib, write '# no external dependencies'\n"
                    "7. DO NOT invent packages — only list what the .py files actually import\n\n"
                    "Return ONLY package specifiers, one per line. No comments except if no deps needed."
                )
            return (
                f"You are an expert Python developer. Generate the file `{fname}` for this project.\n\n"
                f"Project: {idea}\n"
                f"Approach: {approach}\n"
                f"Innovation: {innovation}\n"
                f"Architecture: {architecture}\n"
                f"Implementation plan: {implementation_plan}\n\n"
                f"Other files in this project: {[f for f in file_list if f != fname]}\n\n"
                f"Generate ONLY the `{fname}` file.\n"
                "STRICT REQUIREMENTS — violating any of these will be rejected:\n"
                "1. COMPLETE, RUNNABLE Python code — every method must have real logic, not placeholders\n"
                "2. NEVER write `# Implement logic here`, `pass`, or stub bodies — write actual code\n"
                "3. NEVER write `# TODO` or `raise NotImplementedError` in the final code\n"
                "4. ONLY import from: (a) Python stdlib, (b) packages in requirements.txt, (c) other files listed in 'Other files in this project' above\n"
                "5. Do NOT import from modules that are not in the 'Other files' list — no phantom imports\n"
                "6. NEVER use relative imports (from .module import X). Always use absolute imports (from module import X). The project is NOT a Python package — there is no __init__.py.\n"
                "6b. NEVER use dotted/package-style imports for local files (e.g. `from task_queue.task import Task`). All project files are FLAT in one directory — use `from task import Task` directly.\n"
                "7. Proper docstrings and type hints on all public functions/classes\n"
                "8. If this is main.py, it MUST have a working `if __name__ == '__main__':` entry point that:\n"
                "   - Produces VISIBLE terminal output (print statements showing the system in action)\n"
                "   - Runs a complete DEMO/PROTOTYPE without requiring external services (databases, APIs, etc.)\n"
                "   - For web servers: start the server AND print a message like 'Server running on http://localhost:8000'\n"
                "   - For CLI tools: run an example calculation/operation and print the result\n"
                "   - For libraries: demonstrate 3-5 core features with printed output\n"
                "   - NEVER exit silently — the user must see output proving it works\n"
                "   - If the project needs a database/Redis/external service, include a FALLBACK in-memory mode that works without them\n"
                "9. NEVER assign placeholder objects like `model = nn.Module()` — always use the REAL class. If model.py defines `MyModel`, you MUST write `model = MyModel(...)` with real arguments, not a bare nn.Module()\n"
                "10. NEVER comment out real initialization and replace it with a placeholder — the uncommented code MUST use the actual classes\n"
                "11. If main.py uses an object from another module, call ONLY methods that EXIST in that class. Check the class definition. If the class has `execute_command(args)` or `run()`, use THAT — do NOT invent methods like `add_task()`, `list_tasks()`.\n"
                "12. If a database/storage function returns List[Dict], ALWAYS access fields with `row['key']` not `row.key`. If it returns dataclass/namedtuple, use dot notation. Match the return type.\n"
                "13. Inside a class, EVERY `self.xxx()` call MUST refer to a method that EXISTS in the same class. If the class has `_write_metadata()`, do NOT call `self._save_metadata()`.\n"
                "14. Initialize ALL instance attributes in `__init__` BEFORE calling any method that uses them. If `_load()` uses `self._data`, set `self._data = {}` before calling `self._load()`.\n"
                + (f"\n{_req_context}\n\n" if _req_context else "")
                + (f"\n{_research_ctx}\n\n" if _research_ctx else "")
                + (f"\n{_contract_text}\n\n" if _contract_text else "")
                + (f"\n{_arch_spec_text}\n\n" if _arch_spec_text else "")
                + (f"\n{_codegen_lessons}\n\n" if _codegen_lessons else "")
                + """COMPLETENESS REQUIREMENTS — the file MUST be substantial and production-ready:
- Write EVERY function and class in FULL. No shortened bodies, no cut-off code.
- Each non-trivial function should have as many lines as needed to implement real logic — never stub or shorten.
- Core implementation files (model, trainer, encoder, etc.) should be as long as they need to be — no upper limit; write everything completely.
- main.py must demonstrate end-to-end usage with argument parsing and meaningful output.
- Prefer depth over breadth: fewer files done completely > many files done shallowly.
- Treat this like a production open-source repository others will clone and run.

DEMO/PROTOTYPE REQUIREMENTS (CRITICAL — the output is TESTED):
- `python main.py` MUST work out of the box with ZERO configuration
- If a service (Redis, PostgreSQL, RabbitMQ, etc.) is needed, provide an IN-MEMORY FALLBACK:
    * Use Python's built-in `queue.PriorityQueue` instead of Redis
    * Use `sqlite3` (stdlib) instead of PostgreSQL/MySQL
    * Use `threading` instead of Celery/RQ for workers
    * Use `http.server` or Flask's built-in server instead of gunicorn/uvicorn
- main.py should run a COMPLETE DEMO that shows all features working:
    * Create sample data, process it, print results
    * For web APIs: start server in a background thread, make test requests, print responses, then shut down
    * For task queues: submit jobs, process them, show results
    * The demo should take <10 seconds and print clear, formatted output
- At the end of the demo, print a summary like:
    ✅ All features demonstrated successfully
    * Feature 1: [result]
    * Feature 2: [result]
Return ONLY valid Python code. No markdown fences."""
            )

        files_to_generate = {fname: _file_prompt(fname) for fname in file_list}
        
        generated_files = {}
        
        logger.info(f"  Generating {len(files_to_generate)} files...")
        
        def _system_msg_for(fname: str) -> str:
            """Return the right system prompt depending on file type."""
            if fname == "README.md":
                return (
                    "You are a senior technical writer. "
                    "Your job is to write clear, descriptive README documentation in Markdown. "
                    "You do NOT write standalone Python scripts. "
                    "You do NOT wrap the entire response in a code fence. "
                    "Every section must contain real prose describing this specific project."
                )
            lang_label = _target_language.capitalize() if _target_language != "python" else "Python"
            return (
                f"You are an expert {lang_label} developer. Generate clean, production-ready code. "
                + (_lang_instructions if _lang_instructions else "")
            )

        def _clean_md_output(raw: str) -> str:
            """Strip an outer wrapping code fence if the LLM disobeyed instructions."""
            stripped = raw.strip()
            for fence_tag in ("```markdown", "```md", "```"):
                if stripped.startswith(fence_tag):
                    inner = stripped[len(fence_tag):]
                    if inner.endswith("```"):
                        inner = inner[:-3]
                    candidate = inner.strip()
                    if candidate.startswith("#"):
                        return candidate
            return stripped

        def _readme_looks_valid(content: str) -> bool:
            """Return True only if this looks like a real README (not raw code)."""
            lines = content.strip().splitlines()
            if not lines:
                return False
            if not lines[0].startswith("#"):
                return False
            h2_count = sum(1 for ln in lines if ln.startswith("## "))
            if h2_count < 3:
                return False
            non_blank = [l for l in lines if l.strip()]
            # Reject if it opens with a bare import (pure Python script, not markdown)
            if non_blank and non_blank[0].startswith(("import ", "from ", "class ", "def ")):
                return False
            return True

        # ── Shared constants for all parallel generation tasks ────────────────
        _TYPO_MAP = {
            '\u202f': ' ', '\u2011': '-', '\u2013': '-', '\u2014': '--',
            '\u2015': '--', '\u2018': "'", '\u2019': "'", '\u201a': "'",
            '\u201c': '"', '\u201d': '"', '\u201e': '"', '\u00a0': ' ',
            '\u2026': '...', '\u2212': '-', '\u2215': '/', '\u2216': '\\',
            '\ufeff': '',
        }
        _STUB_PATTERNS = ("# Implement", "# TODO", "raise NotImplementedError",
                          "pass  #", "# implement", "# your code here",
                          "# Add your", "# Write your")

        async def _gen_file(filename: str, prompt: str):
            """Generate + stub-check one file. Runs concurrently with all other files."""
            logger.info(f"  📝 [{filename}] generating...")
            messages = [
                SystemMessage(content=_system_msg_for(filename)),
                HumanMessage(content=prompt)
            ]
            response = await llm.ainvoke(messages)
            code = response.content

            # ── Post-process by file type ────────────────────────────────────
            if filename.endswith(".md"):
                code = _clean_md_output(code)
                if not _readme_looks_valid(code):
                    logger.warning(f"  ⚠️  [{filename}] structure check failed — retrying...")
                    retry_prompt = (
                        f"{prompt}\n\n"
                        "IMPORTANT: Your previous response was rejected because it did not start with a # heading "
                        "or did not contain enough ## sections. "
                        "Do NOT output a Python script. Output ONLY a valid Markdown document starting with # and "
                        "containing at least ## Overview, ## Installation, ## Usage, ## Architecture, and ## License."
                    )
                    retry_response = await llm.ainvoke([
                        SystemMessage(content=_system_msg_for(filename)),
                        HumanMessage(content=retry_prompt)
                    ])
                    retry_code = _clean_md_output(retry_response.content)
                    if _readme_looks_valid(retry_code):
                        code = retry_code
                        logger.info(f"  ✅ [{filename}] retry succeeded")
                    else:
                        if retry_code.count("## ") > code.count("## "):
                            code = retry_code
            elif "```python" in code:
                code = code.split("```python")[1].split("```")[0].strip()
            elif "```" in code and filename.endswith(".py"):
                code = code.split("```")[1].split("```")[0].strip()
            elif "```" in code and filename == "requirements.txt":
                code = code.split("```")[1].split("```")[0].strip()
                if code.startswith(("plaintext", "txt", "text")):
                    code = "\n".join(code.split("\n")[1:]).strip()

            code = code.translate(str.maketrans(_TYPO_MAP))

            if filename == "README.md":
                h2_count = code.count("## ")
                logger.info(f"  📄 README.md: {len(code)} chars, {h2_count} sections, valid={_readme_looks_valid(code)}")

            # ── Stub detection + regen (same task, no extra round-trip cost) ─
            if filename.endswith(".py"):
                real_lines = [l for l in code.splitlines()
                              if l.strip() and not l.strip().startswith("#")]
                has_stubs = any(p in code for p in _STUB_PATTERNS)
                # Adaptive threshold: main.py and core files need more code,
                # but helper/util/config files can legitimately be short.
                _is_main = filename in ("main.py", "app.py", "run.py")
                _min_lines = 40 if _is_main else 15  # was 80 — too aggressive for utils
                _stub_min = 60 if _is_main else 30   # was 100
                if len(real_lines) < _min_lines or (has_stubs and len(real_lines) < _stub_min):
                    logger.warning(f"  ⚠️  [{filename}] stub/empty ({len(real_lines)} real lines) — regenerating...")
                    regen_prompt = (
                        f"{_file_prompt(filename)}\n\n"
                        "CRITICAL: Your previous attempt was rejected because it was empty, "
                        "contained only placeholder comments, or stub implementations. "
                        "You MUST write complete, functional code with real logic in every method."
                    )
                    regen_resp = await llm.ainvoke([
                        SystemMessage(content="You are an expert Python developer. Generate complete, working Python code."),
                        HumanMessage(content=regen_prompt)
                    ])
                    regen_code = regen_resp.content
                    if "```python" in regen_code:
                        regen_code = regen_code.split("```python")[1].split("```")[0].strip()
                    elif "```" in regen_code:
                        regen_code = regen_code.split("```")[1].split("```")[0].strip()
                    regen_code = regen_code.translate(str.maketrans(_TYPO_MAP))
                    real_after = [l for l in regen_code.splitlines()
                                  if l.strip() and not l.strip().startswith("#")]
                    # FIX A: was `len(real_after) > len(real_lines)` — when both=0 this is
                    # always False so the regen result was never applied.  Use `> 0` instead.
                    if len(real_after) > 0:
                        code = regen_code
                        logger.info(f"  ✅ [{filename}] regenerated: {len(real_lines)} → {len(real_after)} real lines")
                    else:
                        # Still empty — force one last try with a different reliable model
                        logger.warning(f"  ⚠️  [{filename}] still empty after regen — forcing retry with balanced model...")
                        # Use get_fallback_llm which is already imported at module level
                        _fb_llm = get_fallback_llm("balanced")
                        fb_resp = await _fb_llm.ainvoke([
                            SystemMessage(content="You are an expert Python developer. Generate complete, working Python code. Return ONLY valid Python code, no markdown fences."),
                            HumanMessage(content=regen_prompt)
                        ])
                        fb_code = fb_resp.content
                        if "```python" in fb_code:
                            fb_code = fb_code.split("```python")[1].split("```")[0].strip()
                        elif "```" in fb_code:
                            fb_code = fb_code.split("```")[1].split("```")[0].strip()
                        fb_code = fb_code.translate(str.maketrans(_TYPO_MAP))
                        fb_real = [l for l in fb_code.splitlines()
                                   if l.strip() and not l.strip().startswith("#")]
                        if len(fb_real) > 0:
                            code = fb_code
                            logger.info(f"  ✅ [{filename}] fallback model produced {len(fb_real)} real lines")
                        else:
                            # FIX B: all 3 attempts returned empty — write a minimal runnable
                            # skeleton so the fix loop has something to patch (can't fix nothing).
                            logger.error(f"  ❌ [{filename}] all regen attempts failed — inserting minimal skeleton")
                            code = (
                                f"# AUTO-GENERATED SKELETON — all LLM attempts returned empty output.\n"
                                f"# The fix loop will attempt to complete this file automatically.\n"
                                f"\n"
                                f"import sys\n"
                                f"\n"
                                f"def main():\n"
                                f"    \"\"\"Entry point — generation failed, fix loop will complete.\"\"\"\n"
                                f"    print('WARNING: {filename} was not fully generated.')\n"
                                f"    print('The auto-fix loop will attempt to implement this file.')\n"
                                f"    sys.exit(1)\n"
                                f"\n"
                                f"\nif __name__ == '__main__':\n"
                                f"    main()\n"
                            )

            logger.info(f"  ✅ [{filename}] done ({len(code)} chars)")
            return filename, code

        # ── Dependency-ordered generation with cross-file context ──────────
        # ROOT CAUSE FIX: Previously all files were generated in parallel, so
        # each file had ZERO knowledge of other files' actual content — only
        # the architect spec's *planned* signatures.  This caused the #1 class
        # of bugs: File A calls FileB.process() but FileB defines FileB.run().
        #
        # New approach:
        #   1. Build an import dependency graph from the architect spec
        #   2. Topological-sort files so dependencies are generated first
        #   3. Non-.py files (README.md, requirements.txt) run in parallel (no deps)
        #   4. Each .py file's prompt includes the ACTUAL generated content of
        #      the files it imports from, so method names / signatures match.
        import asyncio as _asyncio_gen

        # Separate non-Python files (no cross-deps) from Python files
        _non_py = {f: p for f, p in files_to_generate.items() if not f.endswith(".py")}
        _py_files_to_gen = {f: p for f, p in files_to_generate.items() if f.endswith(".py")}

        generated_files = {}

        # Generate non-Python files in parallel (README.md, requirements.txt)
        if _non_py:
            logger.info(f"  ⚡ Generating {len(_non_py)} non-Python files in parallel...")
            _non_py_results = await _asyncio_gen.gather(
                *[_gen_file(fname, prompt) for fname, prompt in _non_py.items()],
                return_exceptions=True
            )
            for _gr in _non_py_results:
                if isinstance(_gr, Exception):
                    logger.error(f"  ❌ File generation task failed: {_gr}")
                    continue
                _gfname, _gcode = _gr
                generated_files[_gfname] = _gcode

        # Build dependency graph from architect spec for topological ordering
        _spec = state.get("architecture_spec") or {}
        _spec_files = {sf["name"]: sf for sf in _spec.get("files", []) if isinstance(sf, dict)}
        _dep_graph: dict = {f: set() for f in _py_files_to_gen}
        for _sfn, _sfd in _spec_files.items():
            if _sfn not in _dep_graph:
                continue
            for _imp in (_sfd.get("imports_from_project") or []):
                # "other_file.ClassName" → "other_file.py"
                _dep_mod = _imp.split(".")[0]
                _dep_file = _dep_mod + ".py" if not _dep_mod.endswith(".py") else _dep_mod
                if _dep_file in _dep_graph and _dep_file != _sfn:
                    _dep_graph[_sfn].add(_dep_file)

        # Topological sort (Kahn's algorithm) — files with no deps first
        _in_degree = {f: 0 for f in _dep_graph}
        for _f, _deps in _dep_graph.items():
            for _d in _deps:
                if _d in _in_degree:
                    _in_degree[_d] = _in_degree.get(_d, 0)  # ensure key exists
        # Actually: in_degree counts how many files DEPEND ON this file
        # We want to generate files that have no DEPENDENCIES first
        _in_degree = {f: len(deps) for f, deps in _dep_graph.items()}
        _sorted_files = []
        _queue = [f for f, d in _in_degree.items() if d == 0]
        _queue.sort()  # deterministic ordering
        _visited = set()
        while _queue:
            _f = _queue.pop(0)
            if _f in _visited:
                continue
            _visited.add(_f)
            _sorted_files.append(_f)
            # Find files that depend on _f and decrement their in-degree
            for _other, _deps in _dep_graph.items():
                if _f in _deps and _other not in _visited:
                    _in_degree[_other] -= 1
                    if _in_degree[_other] <= 0:
                        _queue.append(_other)
            _queue.sort()
        # Add any remaining files (cycles or missing from graph)
        for _f in _py_files_to_gen:
            if _f not in _visited:
                _sorted_files.append(_f)

        logger.info(f"  📐 Dependency-ordered generation: {' → '.join(_sorted_files)}")

        # ── Incremental Compiler — validate each file as it's generated ────
        try:
            from ..utils.incremental_compiler import IncrementalCompiler
        except ImportError:
            try:
                from utils.incremental_compiler import IncrementalCompiler  # type: ignore
            except ImportError:
                IncrementalCompiler = None  # type: ignore
        
        _inc_compiler = None
        if IncrementalCompiler:
            _inc_compiler = IncrementalCompiler()
            _inc_compiler.set_planned_files(file_list)
            logger.info("  📐 Incremental compiler initialized")

        # Generate Python files in dependency order with cross-file context
        for _gen_fname in _sorted_files:
            _gen_prompt = _py_files_to_gen[_gen_fname]

            # Inject ACTUAL content of already-generated dependency files
            _deps_for_file = _dep_graph.get(_gen_fname, set())
            _dep_context_parts = []
            for _dep_fn in _deps_for_file:
                if _dep_fn in generated_files and generated_files[_dep_fn].strip():
                    _dep_context_parts.append(
                        f"=== ALREADY GENERATED: {_dep_fn} ===\n"
                        f"(You MUST use the EXACT class/function names defined below)\n"
                        f"{generated_files[_dep_fn]}"
                    )
            # Also include any already-generated non-dependency .py files as reference
            for _prev_fn, _prev_code in generated_files.items():
                if _prev_fn.endswith(".py") and _prev_fn != _gen_fname and _prev_fn not in _deps_for_file:
                    if _prev_code.strip():
                        _dep_context_parts.append(
                            f"=== ALREADY GENERATED (reference): {_prev_fn} ===\n"
                            f"{_prev_code[:3000]}"  # truncate reference files
                        )

            if _dep_context_parts:
                _cross_file_ctx = (
                    "\n\nCROSS-FILE CONTEXT — these files are ALREADY GENERATED. "
                    "You MUST match their class names, method signatures, and constructor args EXACTLY. "
                    "Do NOT invent methods that don't exist in these files.\n\n"
                    + "\n\n".join(_dep_context_parts)
                )
                _gen_prompt = _gen_prompt + _cross_file_ctx

            # ── Inject incremental compilation feedback ──────────────────
            if _inc_compiler:
                _ic_feedback = _inc_compiler.get_feedback_for_next_file(_gen_fname)
                if _ic_feedback:
                    _gen_prompt = _gen_prompt + "\n\n" + _ic_feedback

            try:
                _result = await _gen_file(_gen_fname, _gen_prompt)
                if isinstance(_result, Exception):
                    logger.error(f"  ❌ [{_gen_fname}] generation failed: {_result}")
                else:
                    generated_files[_result[0]] = _result[1]
                    logger.info(f"  ✅ [{_gen_fname}] generated with {len(_dep_context_parts)} dep contexts")
                    
                    # ── Incremental validation ───────────────────────────
                    if _inc_compiler and _result[1]:
                        _iv_result = _inc_compiler.validate_file(_result[0], _result[1])
                        _inc_compiler.register_file(_result[0], _result[1])
                        if not _iv_result.is_valid:
                            logger.warning(f"  ⚠️ [{_result[0]}] incremental check: {_iv_result.format_for_prompt()}")
                            console.print(f"  [yellow]⚠ {_result[0]}: incremental validation found issues[/yellow]")
                        else:
                            logger.info(f"  ✅ [{_result[0]}] incremental validation passed")
            except Exception as _gen_err:
                logger.error(f"  ❌ [{_gen_fname}] generation raised: {_gen_err}")

        # Log incremental compilation summary
        if _inc_compiler:
            _ic_summary = _inc_compiler.get_summary()
            logger.info(f"  📐 {_ic_summary}")
            console.print(f"  [dim]{_ic_summary}[/dim]")

        logger.info(f"✅ Generated {len(generated_files)} files in dependency order")

        # ── Post-gather shadow-file sanitization ──────────────────────────
        # The file planner already strips shadow names, but the LLM may
        # return a filename that differs from the plan (or the plan-parse
        # may fail).  Re-check the ACTUAL generated filenames here.
        _SHADOW_PKG_STEMS = {
            "torch", "numpy", "pandas", "scipy", "sklearn", "tensorflow",
            "keras", "matplotlib", "seaborn", "plotly", "cv2",
            "transformers", "datasets", "tokenizers", "accelerate",
            "diffusers", "langchain", "openai", "anthropic", "groq",
            "fastapi", "flask", "django", "requests", "httpx", "aiohttp",
            "pydantic", "sqlalchemy", "redis", "celery", "pytest",
            "hypothesis", "click", "typer", "rich",
            "jwt", "bcrypt", "websockets", "websocket", "cryptography",
            "yaml", "toml", "dotenv", "paramiko", "fabric",
            # stdlib
            "os", "sys", "re", "io", "abc", "gc", "math", "cmath",
            "time", "random", "copy", "enum", "json", "csv", "logging",
            "pathlib", "typing", "types", "collections", "functools",
            "itertools", "operator", "threading", "asyncio",
            "concurrent", "multiprocessing", "subprocess", "socket",
            "ssl", "http", "urllib", "email", "html", "xml", "sqlite3",
            "hashlib", "hmac", "secrets", "base64", "struct", "array",
            "queue", "heapq", "bisect", "datetime", "calendar",
            "string", "textwrap", "unicodedata", "unittest",
            "dataclasses", "warnings", "traceback", "inspect",
            "importlib", "pkgutil", "ast", "dis", "token", "tokenize",
        }
        _shadow_renames = {}
        for _sfn in list(generated_files.keys()):
            if not _sfn.endswith(".py"):
                continue
            _sstem = _sfn.rsplit(".", 1)[0].lower()
            if _sstem in _SHADOW_PKG_STEMS:
                _safe_name = f"project_{_sstem}.py"
                _shadow_renames[_sfn] = _safe_name
                generated_files[_safe_name] = generated_files.pop(_sfn)
                logger.warning(
                    f"  ⚠️  Post-gather shadow sanitization: '{_sfn}' → '{_safe_name}'"
                )
                console.print(
                    f"  [yellow]⚠️  Shadow file '{_sfn}' renamed to '{_safe_name}'[/yellow]"
                )
        # Update cross-file imports if any files were renamed
        if _shadow_renames:
            for _rfn, _rcontent in list(generated_files.items()):
                if not _rfn.endswith(".py"):
                    continue
                _updated = _rcontent
                for _old_shadow, _new_safe in _shadow_renames.items():
                    _old_mod = _old_shadow.rsplit(".", 1)[0]   # "numpy.py" → "numpy"
                    _new_mod = _new_safe.rsplit(".", 1)[0]     # "project_numpy.py" → "project_numpy"
                    # Replace `import numpy` → `import project_numpy`
                    _updated = _re.sub(
                        rf"^(import\s+){_re.escape(_old_mod)}(\s|$|,)",
                        rf"\g<1>{_new_mod}\2",
                        _updated, flags=_re.MULTILINE
                    )
                    # Replace `from numpy import X` → `from project_numpy import X`
                    _updated = _re.sub(
                        rf"^(from\s+){_re.escape(_old_mod)}(\s+import)",
                        rf"\g<1>{_new_mod}\2",
                        _updated, flags=_re.MULTILINE
                    )
                if _updated != _rcontent:
                    generated_files[_rfn] = _updated
                    logger.info(f"  🔄 Updated imports in {_rfn} after shadow rename")

        # ── FIX C: Post-gather audit — catch any .py files still empty/tiny ───
        # A file can slip through if the LLM returned only whitespace/fences, or if
        # the regen coroutine threw an exception caught by return_exceptions=True.
        _empty_py = [
            fn for fn, fc in generated_files.items()
            if fn.endswith(".py") and len(fc.strip()) < 50
        ]
        if _empty_py:
            logger.warning(f"  ⚠️  Post-gather audit: {len(_empty_py)} near-empty .py file(s): {_empty_py} — retrying serially")
            for _efn in _empty_py:
                try:
                    _ep_prompt = (
                        f"{_file_prompt(_efn)}\n\n"
                        "CRITICAL: Return ONLY complete, working Python code. "
                        "No markdown fences, no explanations, no placeholders. "
                        "Every function must have a real implementation."
                    )
                    _ep_resp = await llm.ainvoke([
                        SystemMessage(content="You are an expert Python developer. Generate complete Python code only."),
                        HumanMessage(content=_ep_prompt)
                    ])
                    _ep_code = _ep_resp.content
                    if "```python" in _ep_code:
                        _ep_code = _ep_code.split("```python")[1].split("```")[0].strip()
                    elif "```" in _ep_code:
                        _ep_code = _ep_code.split("```")[1].split("```")[0].strip()
                    _ep_real = [l for l in _ep_code.splitlines() if l.strip() and not l.strip().startswith("#")]
                    if len(_ep_real) > 0:
                        generated_files[_efn] = _ep_code
                        logger.info(f"  ✅ [{_efn}] post-gather retry succeeded: {len(_ep_real)} real lines")
                    else:
                        # Last resort: minimal skeleton
                        generated_files[_efn] = (
                            f"# SKELETON: post-gather retry also returned empty output for {_efn!r}\n"
                            f"import sys\n"
                            f"def main():\n"
                            f"    print('WARNING: {_efn} generation failed — fix loop will implement.')\n"
                            f"    sys.exit(1)\n"
                            f"\nif __name__ == '__main__':\n    main()\n"
                        )
                        logger.error(f"  ❌ [{_efn}] post-gather retry failed — minimal skeleton written")
                except Exception as _ep_err:
                    logger.error(f"  ❌ [{_efn}] post-gather retry raised: {_ep_err}")
        # ─────────────────────────────────────────────────────────────────────
        # ── Convert ALL relative imports → absolute imports ──────────────────
        # `from .task import X` → `from task import X`
        # Relative imports fail when running `python main.py` because the
        # generated project is NOT a Python package (no __init__.py).
        py_module_names = {f[:-3] for f in generated_files if f.endswith(".py")}
        import re as _re_imports
        for fname, content in list(generated_files.items()):
            if not fname.endswith(".py"):
                continue
            new_lines = []
            _rel_fixes = 0
            for line in content.splitlines():
                # Match: from .module import X  →  from module import X
                m = _re_imports.match(r"^(\s*from\s+)\.(\w+)(\s+import\s+.*)$", line)
                if m:
                    mod_name = m.group(2)
                    if mod_name in py_module_names:
                        # Valid local module — convert to absolute import
                        new_line = f"{m.group(1)}{m.group(2)}{m.group(3)}"
                        new_lines.append(new_line)
                        _rel_fixes += 1
                    else:
                        # Module not in project — comment it out
                        new_lines.append(f"# REMOVED phantom import (module '{mod_name}' not in project): {line.strip()}")
                        _rel_fixes += 1
                else:
                    new_lines.append(line)
            if _rel_fixes:
                logger.info(f"  🔧 {fname}: converted {_rel_fixes} relative import(s) → absolute")
                generated_files[fname] = "\n".join(new_lines)

        # ── Convert dotted package imports → flat imports ────────────────────
        # `from task_queue.task import Task` → `from task import Task`
        # Generated projects are FLAT (no subdirectories / no __init__.py).
        _dotted_fixes = _fix_dotted_local_imports(generated_files, "code_gen")
        if _dotted_fixes:
            console.print(f"  [green]✓[/green] Flattened {_dotted_fixes} dotted package import(s) → flat")

        # ── Post-process requirements.txt ─────────────────────────────────────
        if "requirements.txt" in generated_files:
            py_srcs = {k: v for k, v in generated_files.items() if k.endswith(".py")}
            raw_req = generated_files["requirements.txt"]
            raw_lines = len([l for l in raw_req.splitlines() if l.strip() and not l.startswith("#")])
            cleaned = _clean_requirements_txt(raw_req, py_srcs)
            clean_lines = len([l for l in cleaned.splitlines() if l.strip() and not l.startswith("#")])
            if clean_lines < raw_lines:
                logger.info(f"  🧹 Trimmed requirements.txt: {raw_lines} → {clean_lines} packages (removed stdlib/internals)")
            generated_files["requirements.txt"] = cleaned
        # ──────────────────────────────────────────────────────────────────────

        # ── Inject RESEARCH_REPORT.md ──────────────────────────────────────────
        try:
            report_md = _build_research_report(state)
            generated_files["RESEARCH_REPORT.md"] = report_md
            report_lines = len(report_md.splitlines())
            logger.info(f"  📄 Generated RESEARCH_REPORT.md ({report_lines} lines)")
        except Exception as _re_err:
            logger.warning(f"  ⚠️  Could not build RESEARCH_REPORT.md: {_re_err}")
        # ──────────────────────────────────────────────────────────────────────

        # ── Option 6: LLM Self-Review Pass ────────────────────────────────────
        # After all files are generated, send .py files to LLM for cross-file
        # consistency check.  Issues are fixed immediately before the test suite
        # runs — so the fix loop starts from a much cleaner baseline.
        _py_review = {k: v for k, v in generated_files.items() if k.endswith(".py") and v.strip()}
        if len(_py_review) >= 2:
            try:
                import json as _json_rv
                _review_ctx = "\n\n".join(
                    f"=== {fn} ===\n{fc}" for fn, fc in _py_review.items()
                )
                _review_msgs = [
                    SystemMessage(content=(
                        "You are a strict Python code reviewer performing a CROSS-FILE consistency audit.\n"
                        "Look ONLY for these concrete bugs:\n"
                        "1. Method called on an object but NOT defined in that class\n"
                        "2. Name imported from a file but that name is NOT defined in that file\n"
                        "3. Class instantiated with args that do NOT match its __init__ signature\n"
                        "4. Circular import: A imports B and B imports A\n"
                        "5. File imports from a module not present in the file list\n\n"
                        "Output ONLY valid JSON, no explanation:\n"
                        '{\"issues\": [{\"file\": \"filename.py\", \"problem\": \"exact description\", \"fix_hint\": \"how to fix\"}]}\n'
                        'If no issues found: {\"issues\": []}'
                    )),
                    HumanMessage(content=f"Review these files for cross-file bugs:\n\n{_review_ctx}")
                ]
                _review_llm = get_fallback_llm("fast")
                _review_resp = await _review_llm.ainvoke(_review_msgs)
                _raw_rv = _review_resp.content.strip()
                _raw_rv = _re_imports.sub(r"^```[a-z]*\n?", "", _raw_rv)
                _raw_rv = _re_imports.sub(r"\n?```$", "", _raw_rv.strip())
                _rv_parsed = _json_rv.loads(_raw_rv)
                _rv_issues = _rv_parsed.get("issues", [])
                if _rv_issues:
                    logger.info(f"  🔍 Self-review found {len(_rv_issues)} cross-file issue(s) — pre-fixing...")
                    # Group issues by file
                    _rv_by_file: dict = {}
                    for _i in _rv_issues:
                        _f = _i.get("file", "")
                        if _f in generated_files:
                            _rv_by_file.setdefault(_f, []).append(_i)
                    # Fix each affected file individually
                    _fix_llm_rv = get_fallback_llm("fast")
                    for _fixf, _fixissues in _rv_by_file.items():
                        _issue_desc = "\n".join(
                            f"- {_ii['problem']} → {_ii.get('fix_hint', 'apply correct implementation')}"
                            for _ii in _fixissues
                        )
                        _other_ctx = "\n\n".join(
                            f"=== {n} ===\n{c}" for n, c in _py_review.items() if n != _fixf
                        )
                        _prefix_msgs = [
                            SystemMessage(content="You are an expert Python developer. Fix the reported cross-file bugs. Return ONLY the complete corrected Python file. No markdown fences."),
                            HumanMessage(content=(
                                f"Fix these bugs in `{_fixf}`:\n{_issue_desc}\n\n"
                                f"Current `{_fixf}`:\n{generated_files[_fixf]}\n\n"
                                f"Other project files for context:\n{_other_ctx}"
                            ))
                        ]
                        _pf_resp = await _fix_llm_rv.ainvoke(_prefix_msgs)
                        _pf_code = _pf_resp.content
                        if "```python" in _pf_code:
                            _pf_code = _pf_code.split("```python")[1].split("```")[0].strip()
                        elif "```" in _pf_code:
                            _pf_code = _pf_code.split("```")[1].split("```")[0].strip()
                        if _pf_code.strip():
                            # Validate that the fix didn't introduce syntax errors
                            import ast as _ast_rv
                            try:
                                _ast_rv.parse(_pf_code)
                                generated_files[_fixf] = _pf_code
                                logger.info(f"  ✅ Pre-fixed: {_fixf}")
                            except SyntaxError as _se:
                                logger.warning(f"  ⚠️  Self-review fix for {_fixf} has syntax error — keeping original")
                else:
                    logger.info("  ✅ Self-review: no cross-file issues found")
            except Exception as _rv_err:
                logger.warning(f"  ⚠️  Self-review pass failed ({type(_rv_err).__name__}: {_rv_err}) — continuing without pre-fix")
        # ──────────────────────────────────────────────────────────────────────

        # ── Deterministic cross-file import validator (AST-based, no LLM) ─────
        # Mechanically parse every .py file:
        #   1. Build an export map:  {module_stem: set(ClassName, func_name, CONST)}
        #   2. Scan every `from <local_module> import <name>` statement
        #   3. If <name> not in export map for <local_module>, find which file
        #      actually defines it and rewrite the import
        #   4. Catch duplicate top-level class definitions across files
        import ast as _ast_val
        _py_gen = {k: v for k, v in generated_files.items() if k.endswith(".py") and v.strip()}
        _module_stems = {fn.rsplit(".", 1)[0] for fn in _py_gen}

        # Step 1: Build export map via AST
        _export_map: dict = {}  # stem → set of exported names
        _ast_trees: dict = {}   # stem → parsed AST (reuse later)
        for _fn, _code in _py_gen.items():
            _stem = _fn.rsplit(".", 1)[0]
            try:
                _tree = _ast_val.parse(_code)
                _ast_trees[_stem] = _tree
                _names = set()
                for _node in _ast_val.iter_child_nodes(_tree):
                    if isinstance(_node, (_ast_val.ClassDef, _ast_val.FunctionDef, _ast_val.AsyncFunctionDef)):
                        _names.add(_node.name)
                    elif isinstance(_node, _ast_val.Assign):
                        for _tgt in _node.targets:
                            if isinstance(_tgt, _ast_val.Name):
                                _names.add(_tgt.id)
                    elif isinstance(_node, _ast_val.AnnAssign) and isinstance(getattr(_node, 'target', None), _ast_val.Name):
                        _names.add(_node.target.id)
                _export_map[_stem] = _names
            except SyntaxError:
                _export_map[_stem] = set()
                logger.warning(f"  ⚠️  AST parse failed for {_fn} — skipping import validation")

        # Step 2: Scan cross-file imports and fix mismatches
        # Also catch imports from modules that DON'T EXIST as files.
        _import_fixes_applied = 0

        # Build a set of known stdlib + common third-party top-level module names
        # so we don't accidentally rewrite `from torch import nn` etc.
        _STDLIB_AND_THIRDPARTY = {
            "os", "sys", "json", "math", "re", "io", "abc", "copy", "time",
            "datetime", "logging", "warnings", "enum", "typing", "pathlib",
            "functools", "collections", "itertools", "dataclasses", "random",
            "argparse", "textwrap", "string", "struct", "hashlib", "base64",
            "unittest", "pytest", "torch", "numpy", "scipy", "sklearn",
            "matplotlib", "pandas", "tqdm", "rich", "requests", "flask",
            "fastapi", "pydantic", "transformers", "datasets", "PIL",
            "cv2", "tensorflow", "jax", "einops", "wandb", "hydra",
            "omegaconf", "yaml", "toml", "dotenv", "click", "typer",
            "__future__", "ast", "inspect", "importlib", "contextlib",
            "concurrent", "multiprocessing", "threading", "asyncio",
            "subprocess", "signal", "atexit", "gc", "traceback",
        }

        for _fn, _code in list(_py_gen.items()):
            _stem = _fn.rsplit(".", 1)[0]
            _lines = _code.split("\n")
            _changed = False
            for _li, _line in enumerate(_lines):
                # Match: from <module> import <names>  OR  from .<module> import <names>
                _m = _re.match(r"^(\s*from\s+)\.?(\w+)(\s+import\s+)(.+?)(\s*#.*)?$", _line)
                if not _m:
                    continue
                _prefix, _src_mod, _imp_kw, _names_str, _comment = _m.group(1), _m.group(2), _m.group(3), _m.group(4), _m.group(5) or ""
                # Normalize prefix to remove relative dot for rewriting
                _prefix = _re.sub(r"from\s+\.\s*", "from ", _prefix)
                if _src_mod == _stem:
                    continue  # self-import — skip

                # Case A: importing from a module that EXISTS as a generated file
                if _src_mod in _module_stems:
                    _src_exports = _export_map.get(_src_mod, set())
                    _imported_names = [n.strip().split(" as ")[0].strip() for n in _names_str.split(",")]
                    _missing = [n for n in _imported_names if n and n not in _src_exports]
                    if not _missing:
                        continue

                # Case B: importing from a module that DOESN'T EXIST as a generated file
                elif _src_mod not in _STDLIB_AND_THIRDPARTY:
                    _imported_names = [n.strip().split(" as ")[0].strip() for n in _names_str.split(",")]
                    _missing = list(_imported_names)  # all names are "missing" since the file doesn't exist
                    logger.warning(f"  ⚠️  {_fn} imports from '{_src_mod}' which is NOT a generated file — fixing")
                else:
                    continue  # stdlib/third-party import — leave alone

                # For each missing name, find which file actually defines it
                for _miss_name in _missing:
                    if not _miss_name:
                        continue
                    _actual_file = None
                    for _cand_stem, _cand_exports in _export_map.items():
                        if _miss_name in _cand_exports and _cand_stem != _stem:
                            _actual_file = _cand_stem
                            break
                    if _actual_file and _actual_file != _src_mod:
                        # Rewrite the import line to use the correct source file
                        _old_import = _line
                        if len(_imported_names) == 1:
                            # Simple case: only one name, rewrite entire line
                            _lines[_li] = f"{_prefix}{_actual_file}{_imp_kw}{_names_str}{_comment}"
                        else:
                            # Multiple names: remove the bad one and add a new import
                            _remaining = [n for n in _names_str.split(",") if _miss_name not in n]
                            _lines[_li] = f"{_prefix}{_src_mod}{_imp_kw}{', '.join(n.strip() for n in _remaining)}{_comment}"
                            _lines.insert(_li + 1, f"{_prefix}{_actual_file}{_imp_kw}{_miss_name}")
                        _changed = True
                        _import_fixes_applied += 1
                        logger.info(f"  🔧 Import fix: {_fn}: '{_miss_name}' not in {_src_mod}.py → rewritten to import from {_actual_file}.py")
                    elif _actual_file is None:
                        # Name doesn't exist anywhere — comment out the import
                        _lines[_li] = f"# REMOVED ('{_miss_name}' not defined in any project file): {_line.strip()}"
                        _changed = True
                        _import_fixes_applied += 1
                        logger.warning(f"  ⚠️  Import removed: {_fn}: '{_miss_name}' not found in any project file")

            if _changed:
                _new_code = "\n".join(_lines)
                generated_files[_fn] = _new_code
                _py_gen[_fn] = _new_code

        # Step 3: Detect duplicate class defs across files (e.g. Config in both config.py and reward.py)
        _class_owners: dict = {}  # class_name → [files that define it]
        for _fn, _code in _py_gen.items():
            _stem = _fn.rsplit(".", 1)[0]
            _tree = _ast_trees.get(_stem)
            if not _tree:
                continue
            for _node in _ast_val.iter_child_nodes(_tree):
                if isinstance(_node, _ast_val.ClassDef):
                    _class_owners.setdefault(_node.name, []).append(_fn)
        _dupes = {name: files for name, files in _class_owners.items() if len(files) > 1}
        if _dupes:
            for _dname, _dfiles in _dupes.items():
                # Determine the canonical file (shortest filename or the one whose stem matches the class)
                _canonical = None
                for _df in _dfiles:
                    if _dname.lower() in _df.lower():
                        _canonical = _df
                        break
                if not _canonical:
                    _canonical = sorted(_dfiles, key=len)[0]
                _non_canonical = [f for f in _dfiles if f != _canonical]
                for _ncf in _non_canonical:
                    # Replace the duplicate class with an import from the canonical file
                    _canon_stem = _canonical.rsplit(".", 1)[0]
                    _ncf_code = generated_files[_ncf]
                    _ncf_lines = _ncf_code.split("\n")
                    # Find the class definition and comment it out
                    _in_dup_class = False
                    _dup_start = -1
                    _dup_end = -1
                    _class_indent = 0
                    for _dli, _dl in enumerate(_ncf_lines):
                        if _re.match(rf"^(\s*)class\s+{_re.escape(_dname)}\s*[\(:]", _dl):
                            _in_dup_class = True
                            _dup_start = _dli
                            _class_indent = len(_dl) - len(_dl.lstrip())
                            continue
                        if _in_dup_class:
                            _stripped = _dl.strip()
                            if _stripped and not _dl.startswith(" " * (_class_indent + 1)) and not _stripped.startswith("#") and not _stripped.startswith("@"):
                                _dup_end = _dli
                                _in_dup_class = False
                                break
                    if _dup_start >= 0:
                        if _dup_end < 0:
                            _dup_end = len(_ncf_lines)
                        # Replace duplicate class with import
                        _replacement = [f"from {_canon_stem} import {_dname}  # using canonical definition from {_canonical}"]
                        _ncf_lines = _ncf_lines[:_dup_start] + _replacement + _ncf_lines[_dup_end:]
                        generated_files[_ncf] = "\n".join(_ncf_lines)
                        _import_fixes_applied += 1
                        logger.info(f"  🔧 Dedup: removed duplicate class '{_dname}' from {_ncf} → importing from {_canonical}")

        if _import_fixes_applied > 0:
            console.print(f"  [green]✓[/green] AST import validator: {_import_fixes_applied} cross-file import fix(es) applied")
            logger.info(f"  ✅ AST import validator applied {_import_fixes_applied} fixes")
        else:
            logger.info(f"  ✅ AST import validator: all cross-file imports correct")
        # ──────────────────────────────────────────────────────────────────────

        # ── Contract enforcement: verify generated code matches interface contracts ──
        # After generation, mechanically verify that every class/method defined in
        # the interface contract actually exists in the generated code with matching names.
        # If a class/method is missing, log a warning and auto-insert a stub to prevent
        # ImportError / AttributeError at runtime.
        if _contract_text and _parsed_c:
            try:
                import re as _re_cv
                _contract_violations = 0
                _contract_violation_msgs: list = []  # collect for execution_errors
                for _c_mod, _c_spec in _parsed_c.items():
                    _c_fname = f"{_c_mod}.py"
                    if _c_fname not in generated_files:
                        _msg = f"CONTRACT: file '{_c_fname}' defined in contract but not generated"
                        _contract_violation_msgs.append(_msg)
                        logger.warning(f"  ⚠️  {_msg}")
                        _contract_violations += 1
                        continue
                    _c_code = generated_files[_c_fname]
                    _c_stem = _c_mod
                    _c_exports = _export_map.get(_c_stem, set())

                    # Check module-level constants
                    for _const_sig in _c_spec.get("module_constants", []):
                        _const_name = _const_sig.split(":")[0].split("=")[0].strip()
                        if _const_name and _const_name not in _c_exports:
                            _msg = f"CONTRACT: {_c_fname} missing constant '{_const_name}'"
                            _contract_violation_msgs.append(_msg)
                            logger.warning(f"  ⚠️  {_msg}")
                            _c_code = _c_code + f"\n{_const_name} = None  # CONTRACT: auto-stub\n"
                            _contract_violations += 1

                    # Check module-level functions
                    for _fn_sig in _c_spec.get("module_functions", []):
                        _fn_match = _re_cv.match(r"def\s+(\w+)\s*\(", _fn_sig)
                        if _fn_match:
                            _fn_name = _fn_match.group(1)
                            if _fn_name not in _c_exports:
                                _msg = f"CONTRACT: {_c_fname} missing function '{_fn_name}'"
                                _contract_violation_msgs.append(_msg)
                                logger.warning(f"  ⚠️  {_msg}")
                                _c_code = _c_code + f"\ndef {_fn_name}(*args, **kwargs):\n    raise NotImplementedError('CONTRACT: {_fn_name} must be implemented')\n"
                                _contract_violations += 1

                    # Check classes and their methods
                    for _cls_spec_entry in _c_spec.get("classes", []):
                        _cls_name = _cls_spec_entry.get("name", "")
                        if not _cls_name:
                            continue
                        if _cls_name not in _c_exports:
                            _msg = f"CONTRACT: {_c_fname} missing class '{_cls_name}'"
                            _contract_violation_msgs.append(_msg)
                            logger.warning(f"  ⚠️  {_msg}")
                            _c_code = _c_code + f"\nclass {_cls_name}:\n    '''CONTRACT: auto-stub — implement this class'''\n    pass\n"
                            _contract_violations += 1
                        else:
                            # Class exists — verify required methods via AST
                            _c_tree = _ast_trees.get(_c_stem)
                            if _c_tree:
                                _cls_methods: set = set()
                                for _n in _ast_val.walk(_c_tree):
                                    if isinstance(_n, _ast_val.ClassDef) and _n.name == _cls_name:
                                        for _m in _n.body:
                                            if isinstance(_m, (_ast_val.FunctionDef, _ast_val.AsyncFunctionDef)):
                                                _cls_methods.add(_m.name)
                                for _meth_sig in _cls_spec_entry.get("public_methods", []):
                                    _meth_match = _re_cv.match(r"(?:async\s+)?def\s+(\w+)\s*\(", _meth_sig)
                                    if _meth_match:
                                        _meth_name = _meth_match.group(1)
                                        if _meth_name not in _cls_methods:
                                            _msg = f"CONTRACT: {_c_fname}.{_cls_name} missing method '{_meth_name}'"
                                            _contract_violation_msgs.append(_msg)
                                            logger.warning(f"  ⚠️  {_msg}")
                                            _contract_violations += 1

                    if _c_code != generated_files[_c_fname]:
                        generated_files[_c_fname] = _c_code

                if _contract_violations > 0:
                    console.print(f"  [yellow]⚠[/yellow] Contract enforcement: {_contract_violations} violation(s) found and stubbed")
                    logger.warning(f"  ⚠️  Contract enforcement: {_contract_violations} violations auto-stubbed")
                    # Feed violations into execution_errors so fix loop can address them
                    _existing_errors = list(execution_errors) if execution_errors else []
                    for _cv_msg in _contract_violation_msgs:
                        _existing_errors.append(_cv_msg)
                    execution_errors = _existing_errors
                else:
                    logger.info("  ✅ Contract enforcement: all signatures match")
            except Exception as _cv_err:
                logger.warning(f"  ⚠️  Contract enforcement check failed ({_cv_err}) — continuing")
        # ──────────────────────────────────────────────────────────────────────

        # ── Flatten file keys: strip any directory prefix ───────────────────
        generated_files = _flatten_file_keys(generated_files, "code_generation")
        # ──────────────────────────────────────────────────────────────────────

        # ── Post-Generation: Encoding Sanitizer (uses shared _EMOJI_TO_ASCII) ──
        _cg_count = _sanitize_emoji(generated_files, "post-codegen")
        if _cg_count:
            logger.info(f"  ✅ Post-codegen encoding sanitizer: cleaned {_cg_count} file(s)")
            console.print(f"  [green]✓[/green] Encoding sanitizer: cleaned {_cg_count} file(s)")
        # ── End Encoding Sanitizer ───────────────────────────────────────

        # ── Post-Generation: LLM Artifact Stripper ───────────────────────
        # Strip XML/HTML/markdown artifacts (</function>, ```, etc.) that
        # LLMs sometimes leave in generated Python code.
        _art_count = _sanitize_llm_artifacts(generated_files, "post-codegen")
        if _art_count:
            logger.info(f"  ✅ Post-codegen artifact stripper: cleaned {_art_count} file(s)")
            console.print(f"  [green]✓[/green] LLM artifact stripper: cleaned {_art_count} file(s)")
        # ── End LLM Artifact Stripper ────────────────────────────────────

        # ── Post-Generation: Import Wiring Check ─────────────────────────
        # Verify that all `from X import Y` statements between generated
        # files actually resolve: X.py exists and defines Y.  This catches
        # cross-file wiring mistakes BEFORE testing, so the error messages
        # are clear and the fix loop can address them.
        import ast as _ast_wc
        _wiring_errors = []
        _wc_module_exports: Dict[str, set] = {}
        for _wcf, _wcc in generated_files.items():
            if not _wcf.endswith(".py") or not _wcc:
                continue
            _wc_mod = _wcf.rsplit(".", 1)[0]
            _wc_names = set()
            try:
                _wc_tree = _ast_wc.parse(str(_wcc))
                for _wn in _ast_wc.iter_child_nodes(_wc_tree):
                    if isinstance(_wn, _ast_wc.ClassDef):
                        _wc_names.add(_wn.name)
                    elif isinstance(_wn, (_ast_wc.FunctionDef, _ast_wc.AsyncFunctionDef)):
                        _wc_names.add(_wn.name)
                    elif isinstance(_wn, _ast_wc.Assign):
                        for _wt in _wn.targets:
                            if isinstance(_wt, _ast_wc.Name):
                                _wc_names.add(_wt.id)
                    elif isinstance(_wn, _ast_wc.ImportFrom) and _wn.names:
                        for _alias in _wn.names:
                            _wc_names.add(_alias.asname or _alias.name)
            except SyntaxError:
                pass
            _wc_module_exports[_wc_mod] = _wc_names

        for _wcf, _wcc in generated_files.items():
            if not _wcf.endswith(".py") or not _wcc:
                continue
            try:
                _wc_tree = _ast_wc.parse(str(_wcc))
            except SyntaxError:
                continue
            for _wn in _ast_wc.walk(_wc_tree):
                if not isinstance(_wn, _ast_wc.ImportFrom) or not _wn.module:
                    continue
                _wc_mod = _wn.module.split(".")[0]
                if _wc_mod not in _wc_module_exports:
                    continue  # External package
                _available = _wc_module_exports[_wc_mod]
                for _alias in (_wn.names or []):
                    if _alias.name == "*":
                        continue
                    if _alias.name not in _available:
                        import difflib as _dl_wc
                        _close = _dl_wc.get_close_matches(_alias.name, _available, n=1, cutoff=0.5)
                        if _close:
                            # Auto-fix the import in the generated code
                            _old_import = _alias.name
                            _new_import = _close[0]
                            _wcc_new = str(generated_files[_wcf])
                            _wcc_new = _wcc_new.replace(
                                f"import {_old_import}", f"import {_new_import}"
                            )
                            # Also update all identifier usages (word-boundary safe)
                            import re as _re_wiring
                            _wcc_new = _re_wiring.sub(r'\b' + _re_wiring.escape(_old_import) + r'\b', _new_import, _wcc_new)
                            generated_files[_wcf] = _wcc_new
                            _wiring_errors.append(
                                f"  Fixed: {_wcf}: `from {_wn.module} import {_old_import}` "
                                f"→ `{_new_import}` (auto-corrected)"
                            )
                            logger.info(f"  🔧 Wiring fix: {_old_import} → {_new_import} in {_wcf}")
                        else:
                            _wiring_errors.append(
                                f"  Warning: {_wcf}: `from {_wn.module} import {_alias.name}` "
                                f"— name not found in {_wc_mod}.py (available: "
                                f"{sorted(n for n in _available if not n.startswith('_'))[:10]})"
                            )
        if _wiring_errors:
            console.print(f"  [yellow]⚠[/yellow] Import wiring check found {len(_wiring_errors)} issue(s):")
            for _we in _wiring_errors[:5]:
                console.print(f"    {_we}")
            logger.info(f"  Import wiring check: {len(_wiring_errors)} issues found/fixed")
        else:
            logger.info("  ✅ Import wiring check: all cross-file imports resolve")
        # ── End Import Wiring Check ──────────────────────────────────────

        # ── Circular Import Detector ─────────────────────────────────────
        # Detect A→B→A import cycles that crash at runtime with ImportError.
        # Uses a simple DFS on the project-internal import graph.
        _ci_graph: Dict[str, set] = {}  # module_name → set of imported module names
        for _cif, _cic in generated_files.items():
            if not _cif.endswith(".py") or not _cic:
                continue
            _ci_mod = _cif.rsplit(".", 1)[0]
            _ci_deps: set = set()
            try:
                _ci_tree = _ast_wc.parse(str(_cic))
                for _cin in _ast_wc.walk(_ci_tree):
                    if isinstance(_cin, _ast_wc.ImportFrom) and _cin.module:
                        _ci_dep = _cin.module.split(".")[0]
                        if _ci_dep in _wc_module_exports:  # Only project-internal
                            _ci_deps.add(_ci_dep)
                    elif isinstance(_cin, _ast_wc.Import):
                        for _ci_alias in _cin.names:
                            _ci_dep = _ci_alias.name.split(".")[0]
                            if _ci_dep in _wc_module_exports:
                                _ci_deps.add(_ci_dep)
            except SyntaxError:
                pass
            _ci_graph[_ci_mod] = _ci_deps

        def _find_cycles(graph: Dict[str, set]) -> list:
            """Find all cycles in the import graph using DFS."""
            visited: set = set()
            path: list = []
            path_set: set = set()
            cycles: list = []

            def _dfs(node: str):
                if node in path_set:
                    cycle_start = path.index(node)
                    cycle = path[cycle_start:] + [node]
                    cycles.append(" → ".join(cycle))
                    return
                if node in visited:
                    return
                visited.add(node)
                path.append(node)
                path_set.add(node)
                for dep in graph.get(node, set()):
                    _dfs(dep)
                path.pop()
                path_set.discard(node)

            for mod in graph:
                _dfs(mod)
            return cycles

        _cycles = _find_cycles(_ci_graph)
        if _cycles:
            for _cyc in _cycles[:3]:
                console.print(f"  [yellow]⚠[/yellow] Circular import detected: {_cyc}")
                logger.warning(f"  ⚠️  Circular import: {_cyc}")
                # Add as execution error so fix loop knows about it
                if isinstance(execution_errors, list):
                    execution_errors.append(f"CIRCULAR_IMPORT: {_cyc}")
        else:
            logger.info("  ✅ No circular imports detected")
        # ── End Circular Import Detector ─────────────────────────────────

        # ── SQL Schema Consistency Check ──────────────────────────────────
        # For projects using SQLite/SQL, verify that column names referenced
        # in queries (INSERT, SELECT, WHERE) match the CREATE TABLE definitions.
        # This catches the common LLM mistake of defining a schema with one
        # column name but querying with a different one.
        import re as _re_sql
        _sql_tables: Dict[str, set] = {}  # table_name → {column_names}
        _sql_warnings: list = []
        
        # Collect all CREATE TABLE definitions across all .py files
        _create_table_re = _re_sql.compile(
            r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?["\']?(\w+)["\']?\s*\((.*?)\)',
            _re_sql.IGNORECASE | _re_sql.DOTALL
        )
        _col_def_re = _re_sql.compile(r'^\s*["\']?(\w+)["\']?\s+(?:TEXT|INTEGER|REAL|BLOB|NUMERIC|VARCHAR|BOOLEAN|DATE|DATETIME|TIMESTAMP|FLOAT|DOUBLE|INT|BIGINT|SMALLINT|DECIMAL|PRIMARY\s+KEY)', _re_sql.IGNORECASE)
        
        for _sqf, _sqc in generated_files.items():
            if not _sqf.endswith(".py") or not _sqc:
                continue
            for _match in _create_table_re.finditer(str(_sqc)):
                _tbl_name = _match.group(1).lower()
                _cols_block = _match.group(2)
                _cols = set()
                for _col_line in _cols_block.split(","):
                    _col_match = _col_def_re.match(_col_line.strip())
                    if _col_match:
                        _cols.add(_col_match.group(1).lower())
                if _cols:
                    _sql_tables[_tbl_name] = _cols
        
        if _sql_tables:
            logger.info(f"  📊 Found {len(_sql_tables)} SQL table definition(s): {list(_sql_tables.keys())}")
            
            # Check INSERT/SELECT/WHERE references against known schemas
            _insert_re = _re_sql.compile(
                r'INSERT\s+(?:OR\s+\w+\s+)?INTO\s+["\']?(\w+)["\']?\s*\(([^)]+)\)',
                _re_sql.IGNORECASE
            )
            _select_col_re = _re_sql.compile(
                r'(?:SELECT|WHERE|ORDER\s+BY|GROUP\s+BY|SET)\s+.*?\b(\w+)\b\s*(?:=|<|>|!=|LIKE|IN|IS|ASC|DESC|,)',
                _re_sql.IGNORECASE
            )
            
            for _sqf, _sqc in generated_files.items():
                if not _sqf.endswith(".py") or not _sqc:
                    continue
                _code_str = str(_sqc)
                
                # Check INSERT column lists
                for _ins_match in _insert_re.finditer(_code_str):
                    _ins_table = _ins_match.group(1).lower()
                    if _ins_table not in _sql_tables:
                        continue
                    _ins_cols = [c.strip().strip('"').strip("'").lower() 
                                 for c in _ins_match.group(2).split(",")]
                    _known_cols = _sql_tables[_ins_table]
                    for _ins_col in _ins_cols:
                        if _ins_col and _ins_col not in _known_cols and not _ins_col.startswith("?"):
                            _sql_warnings.append(
                                f"SQL_COLUMN_MISMATCH: {_sqf} — INSERT INTO {_ins_table} "
                                f"references column '{_ins_col}' but CREATE TABLE defines: "
                                f"{sorted(_known_cols)}"
                            )
            
            if _sql_warnings:
                console.print(f"  [yellow]⚠[/yellow] SQL schema check found {len(_sql_warnings)} issue(s):")
                for _sw in _sql_warnings[:5]:
                    console.print(f"    {_sw}")
                    execution_errors.append(_sw)
                logger.warning(f"  ⚠️  SQL schema: {len(_sql_warnings)} column mismatch(es)")
            else:
                logger.info("  ✅ SQL schema check: all column references consistent")
        # ── End SQL Schema Consistency Check ──────────────────────────────

        # ── SOTA: Automated Test Generation ───────────────────────────────
        # Generate a test_main.py that verifies the generated code actually
        # works.  Uses assertion-driven development — each test case checks
        # a concrete property of the output (imports work, classes instantiate,
        # main runs without error, output is non-empty).
        #
        # This is inspired by AlphaCode/CodeChain: generate code + tests
        # together so the fix loop has EXECUTABLE PASS/FAIL signals, not
        # just static analysis scores.
        if "test_main.py" not in generated_files and any(
            f.endswith(".py") for f in generated_files
        ):
            try:
                _test_llm = get_fallback_llm("fast")
                _py_file_list = [f for f in generated_files if f.endswith(".py") and f != "test_main.py"]
                _test_file_info = "\n".join(
                    f"  - {f}: {len(generated_files[f].splitlines())} lines"
                    for f in _py_file_list
                )
                # Build a brief class/function summary for better tests
                import ast as _ast_tg
                _test_symbols = []
                for _tgf in _py_file_list:
                    try:
                        _tgt = _ast_tg.parse(generated_files[_tgf])
                        for _tgn in _ast_tg.iter_child_nodes(_tgt):
                            if isinstance(_tgn, _ast_tg.ClassDef):
                                _tg_methods = [m.name for m in _tgn.body
                                                if isinstance(m, (_ast_tg.FunctionDef, _ast_tg.AsyncFunctionDef))]
                                _test_symbols.append(f"  {_tgf}: class {_tgn.name} — methods: {_tg_methods}")
                            elif isinstance(_tgn, _ast_tg.FunctionDef):
                                _test_symbols.append(f"  {_tgf}: function {_tgn.name}()")
                    except SyntaxError:
                        pass
                _symbols_text = "\n".join(_test_symbols[:20]) if _test_symbols else "(no parseable symbols)"

                _test_prompt = (
                    "Generate a pytest test file `test_main.py` for this project.\n\n"
                    f"PROJECT IDEA: {state.get('idea', '')[:300]}\n\n"
                    f"FILES:\n{_test_file_info}\n\n"
                    f"SYMBOLS:\n{_symbols_text}\n\n"
                    "RULES:\n"
                    "1. Import from the project files (e.g., `from model import MyModel`)\n"
                    "2. Write as many test functions as needed, each starting with `test_`\n"
                    "3. Test cases MUST be:\n"
                    "   - test_imports(): verify all modules can be imported\n"
                    "   - test_classes_instantiate(): create instances of each main class\n"
                    "   - test_main_runs(): run main logic and check it doesn't crash\n"
                    "   - test_output_not_empty(): verify the program produces output\n"
                    "4. Use assert statements, NOT print()\n"
                    "5. Handle optional heavy deps (torch, tensorflow) with:\n"
                    "   pytest.importorskip('torch')\n"
                    "6. Each test should be as thorough as needed\n"
                    "7. Do NOT test internal implementation details\n\n"
                    "Return ONLY the Python code for test_main.py, no explanations."
                )
                _test_resp = await _test_llm.ainvoke([HumanMessage(content=_test_prompt)])
                _test_code = _test_resp.content.strip()
                if "```python" in _test_code:
                    _test_code = _test_code.split("```python")[1].split("```")[0].strip()
                elif "```" in _test_code:
                    _test_code = _test_code.split("```")[1].split("```")[0].strip()
                # Strip thinking tags
                if "<think>" in _test_code:
                    _te = _test_code.rfind("</think>")
                    if _te != -1:
                        _test_code = _test_code[_te + len("</think>"):].strip()

                # Validate: must have at least one test function and valid syntax
                if "def test_" in _test_code and len(_test_code) > 50:
                    try:
                        compile(_test_code, "test_main.py", "exec")
                        generated_files["test_main.py"] = _test_code
                        logger.info(f"  🧪 Auto-generated test_main.py ({len(_test_code.splitlines())} lines)")
                        console.print(f"  [green]🧪 Auto-generated test_main.py[/green]")
                    except SyntaxError as _tse:
                        logger.warning(f"  ⚠️  Generated test_main.py has syntax error ({_tse}) — skipping")
                else:
                    logger.warning("  ⚠️  Test generation returned invalid output — skipping")
            except Exception as _tg_err:
                logger.debug(f"  Test generation failed (non-critical): {_tg_err}")
        # ── End Test Generation ──────────────────────────────────────────

        # ── Multi-language: merge scaffold files ─────────────────────────
        if _scaffold_files:
            for _sfname, _sfcontent in _scaffold_files.items():
                if _sfname not in generated_files:
                    generated_files[_sfname] = _sfcontent
                    logger.info(f"  🌐 Added scaffold: {_sfname}")

        # ── Proactive emoji sanitization (uses shared _EMOJI_TO_ASCII) ──
        import sys as _sys_gen_enc
        if _sys_gen_enc.platform == "win32":
            _sanitized_count = _sanitize_emoji(generated_files, "proactive-codegen")
            if _sanitized_count:
                logger.info(f"  🧹 Proactively sanitized emoji in {_sanitized_count} file(s)")
                console.print(f"  [green]🧹 Sanitized emoji/unicode in {_sanitized_count} .py file(s)[/green]")
        # ── End emoji sanitization ───────────────────────────────────────

        # ── Proactive LLM artifact stripping ─────────────────────────────
        _proactive_art = _sanitize_llm_artifacts(generated_files, "proactive-codegen")
        if _proactive_art:
            logger.info(f"  🧹 Proactively stripped LLM artifacts from {_proactive_art} file(s)")
            console.print(f"  [green]🧹 Stripped LLM artifacts from {_proactive_art} .py file(s)[/green]")
        # ── End LLM artifact stripping ───────────────────────────────────

        # Memory cleanup after heavy generation
        gc.collect()
        
        _codegen_return: Dict[str, Any] = {
            "current_stage": "code_generated",
            "generated_code": {
                "files": generated_files,
                "approach": approach,
                "total_files": len(generated_files)
            }
        }
        # Forward code-gen-level errors (contract violations, circular imports)
        # so code_testing_node / code_fixing_node can act on them.
        if execution_errors:
            _codegen_return["test_results"] = {
                "execution_errors": execution_errors,
                "codegen_warnings": execution_errors,
            }
            logger.info(f"  ⚠️  Forwarding {len(execution_errors)} codegen-level error(s) to downstream nodes")
        return _codegen_return
        
    except Exception as e:
        logger.error(f"Code generation failed: {e}")
        gc.collect()  # Cleanup on error too
        return {
            "current_stage": "code_generation_failed",
            "errors": [f"Code generation failed: {str(e)}"],
            "generated_code": {}
        }


# ============================================
# Node 7.5: Deep Code Review Agent
# ============================================

async def code_review_agent_node(state: AutoGITState) -> Dict[str, Any]:
    """
    Node 7.5: Deep semantic code review with full build context.

    Runs AFTER code generation, BEFORE the test suite.
    Unlike Option 6 (fast cross-file API check), this node:
      - Knows WHAT is being built (idea / solution architecture)
      - Detects truncated files, missing __main__ guards, logic bugs
        like checking state after a mutating call, stub implementations,
        silent-success (main.py runs but produces no output)
      - Re-generates only the affected files with precise fix instructions
      - Iterates up to 2 rounds so fixes don't introduce new issues
    """
    logger.info("🔍 Code Review Agent: deep semantic review with build context")
    console = Console()
    console.print("\n[cyan]🔍 Code Review Agent running...[/cyan]")

    try:
        import json as _json_ra
        from ..utils.model_manager import get_fallback_llm

        generated_code = state.get("generated_code", {})
        files: dict = _flatten_file_keys(dict(generated_code.get("files", {})), "code_review_input")
        if not files:
            logger.warning("  No files to review — skipping")
            return {"current_stage": "code_reviewed", "generated_code": generated_code}

        # ── Load lessons from past runs for the reviewer ─────────────────
        _review_lessons = ""
        try:
            from ..utils.codegen_error_memory import get_error_memory as _gem_rv
            _review_lessons = _gem_rv().get_lessons_for_review(n=10)
            if _review_lessons:
                logger.info(f"  📚 Loaded historical bug patterns for reviewer")
        except Exception as _le:
            logger.debug(f"  Could not load review lessons: {_le}")

        # ── Build context about what we're building ──────────────────────────
        idea            = state.get("idea", "")
        problem         = state.get("selected_problem", "")
        final_solution  = state.get("final_solution", {})
        approach_name   = ""
        arch_summary    = ""
        if isinstance(final_solution, dict):
            approach_name = final_solution.get("approach_name", "")
            arch_summary  = final_solution.get("architecture_design", "") or \
                            final_solution.get("implementation_plan", "")
            if isinstance(arch_summary, list):
                arch_summary = "\n".join(str(x) for x in arch_summary)

        build_ctx = (
            f"PROJECT IDEA: {idea}\n"
            f"PROBLEM BEING SOLVED: {problem}\n"
            f"SOLUTION APPROACH: {approach_name}\n"
            f"ARCHITECTURE SUMMARY:\n{str(arch_summary)}"
        )

        py_files = {k: v for k, v in files.items() if k.endswith(".py") and v.strip()}
        if not py_files:
            logger.info("  No Python files to review")
            return {"current_stage": "code_reviewed", "generated_code": generated_code}

        review_llm = get_fallback_llm("powerful")
        fix_llm    = get_fallback_llm("balanced")
        total_issues_fixed = 0
        _review_parsed_ok = False  # Track whether at least one iteration parsed JSON successfully

        for _iteration in range(3):  # max 3 review→fix cycles
            # ── Build the review payload ─────────────────────────────────────
            # Truncate individual files if total is too large for model context
            _max_chars_per_file = 50000  # ~1250 lines — room for large files
            file_listing = "\n\n".join(
                f"=== {fn} ===\n{fc[:_max_chars_per_file]}" + 
                (f"\n... (truncated, {len(fc)} chars total)" if len(fc) > _max_chars_per_file else "")
                for fn, fc in py_files.items()
            )

            review_system = (
                "You are a senior Python engineer doing a DEEP code quality review.\n"
                "You have full context of what the project is supposed to build.\n\n"
                "Check every file for these issues (in priority order):\n"
                "1. TRUNCATED — file ends mid-function, mid-statement, or body \"cuts off\" before the function finishes\n"
                "2. MISSING_ENTRY_POINT — main.py exists but has no `if __name__ == '__main__':` block, so nothing executes\n"
                "3. SILENT_MAIN — main.py has an entry point but does not print any result / output, so user gets no feedback\n"
                "4. MISSING_OUTPUT_PROJECTION — an nn.Module subclass stores vocab_size or num_classes but forward() returns\n"
                "   raw hidden states (d_model dimensions) without a final nn.Linear(d_model, vocab_size) projection head.\n"
                "   This ALWAYS causes IndexError/RuntimeError when used with CrossEntropyLoss. Check that every model's\n"
                "   forward() output last dimension matches what the loss function expects.\n"
                "5. DEAD_LOGIC — checking a condition that is always True/False because a prior call already mutated the state \n"
                "   (e.g. calling .fire() after .step() when .step() already resets the membrane, so .fire() always returns False)\n"
                "6. STUB_BODY — function body is only `pass`, `...`, or `raise NotImplementedError` where real logic is needed\n"
                "7. WRONG_CALL — method called on an object but that method does not exist in the class\n"
                "8. MISSING_EXPORT — name imported from a file but not defined/exported in that file\n"
                "9. CIRCULAR_IMPORT — file A imports from file B which imports from file A\n"
                "10. SHAPE_MISMATCH — tensor shape incompatibility between producer and consumer:\n"
                "    e.g. model returns (B, S, d_model) but loss/caller expects (B, S, vocab_size),\n"
                "    or function returns scalar but caller indexes it as a tensor\n"
                "11. DUPLICATE_CLASS — the same class is fully re-implemented in main.py AND in a module file.\n"
                "    main.py should import from the module, not redefine it. Duplicate definitions drift apart and cause bugs.\n"
                "12. PLACEHOLDER_INIT — a variable is assigned a bare placeholder like `model = nn.Module()` or\n"
                "    `model = None  # placeholder`, or the REAL initialization is commented out while a placeholder is active.\n"
                "    The file imports the real class but never uses it. This ALWAYS causes RuntimeError (empty parameter list)\n"
                "    or AttributeError. The placeholder must be replaced with the actual class instantiation.\n"
                "13. API_MISMATCH — a caller file (e.g. main.py) calls methods like `obj.add_task()` on an object, but the actual\n"
                "    class defines DIFFERENT method names (e.g. `execute_command()`). Also covers RETURN TYPE mismatches:\n"
                "    if a db/storage method returns dicts, callers MUST use `row['key']` not `row.key`.\n"
                "    Also check main.py re-implementing dispatch when class already has `run()`.\n"
                "14. SELF_METHOD_MISSING — inside a class body, `self.some_method()` is called but the class does NOT define\n"
                "    `some_method`. For example, a method calls `self._save_metadata()` but the class only defines\n"
                "    `_write_metadata()`. Check EVERY `self.xxx()` call in each class against the actual method list.\n"
                "15. UNINITIALIZED_ATTR — a method accesses `self.attr` (read) but `__init__` never sets `self.attr = ...`.\n"
                "    The method is called from `__init__` or early in the lifecycle BEFORE `self.attr` is assigned.\n"
                "    For example, `__init__` calls `self._load()` which uses `self._metadata`, but `self._metadata` is not\n"
                "    initialized before the call. This causes AttributeError.\n"
                "16. RELATIVE_IMPORT — file uses `from .module import X` (relative import). This ALWAYS fails when running\n"
                "    `python main.py` because the project has no __init__.py. Must be `from module import X` (absolute).\n"
                "17. ATTR_MISMATCH — a variable refers to an object of a known class, and the code accesses an attribute\n"
                "    (e.g. `db_manager.db_path`) that does NOT exist on that class. Commonly the class defines a PRIVATE\n"
                "    attribute (e.g. `self._db_path`) but the caller uses the public name (without underscore), or vice versa.\n"
                "    Check every `obj.attr` access across files and verify the attribute actually exists in the class definition.\n"
                "18. ENCODING_ISSUE — file contains emoji or non-ASCII characters (e.g. ✅, ❌, ⚠️, 🔄) in print() calls\n"
                "    or string literals. On Windows, the default console encoding (cp1252) cannot represent these characters,\n"
                "    causing UnicodeEncodeError at runtime. Replace ALL emoji with ASCII equivalents (e.g. [OK], [FAIL], [!]).\n"
                "    This is a CRITICAL issue on Windows — it will crash the program.\n"
                "19. REDUNDANT_WRAPPING — a data structure already contains boundary/border/frame elements as part of its\n"
                "    representation (e.g. a maze grid where row 0 and row -1 are walls, or a table with built-in header\n"
                "    separators), but the renderer/display function ALSO adds its own border/frame on top. This causes\n"
                "    double borders, extra padding, or visual artifacts. The renderer should detect whether the data\n"
                "    already has boundaries and skip adding redundant ones. Check for: grid[0][*]=wall + add_border=True,\n"
                "    table has header separator + renderer adds another, frame inside frame, etc.\n"
                "20. DEMO_MODE_INPUT — main.py has a demo/interactive mode that calls `input()` when run without arguments.\n"
                "    This BLOCKS automated testing and causes timeouts. The program MUST work without user interaction\n"
                "    when given command-line arguments. If a demo mode exists, it should only activate explicitly\n"
                "    (e.g. `--demo` flag) and should NOT be the default behavior. The default should produce output and exit.\n\n"
                "CRITICAL RULE: For any nn.Module with a stored vocab_size/num_classes attribute, VERIFY that forward()\n"
                "includes a projection layer (nn.Linear) whose output dimension equals vocab_size/num_classes.\n"
                "If it doesn't, report MISSING_OUTPUT_PROJECTION as severity=critical.\n\n"
                "IMPORTANT: Only report issues that are genuinely present. Do NOT invent issues.\n"
                + (_review_lessons + "\n\n" if _review_lessons else "")
                + "Severity:\n"
                "  critical — will cause wrong output, crash, or silent failure when run\n"
                "  warning  — code smell but won't crash\n\n"
                "Output ONLY valid JSON, no prose:\n"
                '{"issues": [{\n'
                '  "file": "filename.py",\n'
                '  "type": "TRUNCATED|MISSING_ENTRY_POINT|SILENT_MAIN|MISSING_OUTPUT_PROJECTION|DEAD_LOGIC|STUB_BODY|WRONG_CALL|MISSING_EXPORT|CIRCULAR_IMPORT|SHAPE_MISMATCH|DUPLICATE_CLASS|PLACEHOLDER_INIT|API_MISMATCH|SELF_METHOD_MISSING|UNINITIALIZED_ATTR|ATTR_MISMATCH|ENCODING_ISSUE|RELATIVE_IMPORT|REDUNDANT_WRAPPING|DEMO_MODE_INPUT|SQLITE_NONDETERMINISTIC|SHADOW_FILE|MISSING_IMPORT|CLASS_SCOPE_NAME_ERROR|EMPTY_STUB_FILE|CROSS_FILE_IMPORT_MISMATCH|MISSING_CUSTOM_MODULE|MISSING_MAIN_GUARD|GENERATED_TEST_FAILURE",\n'
                '  "severity": "critical|warning",\n'
                '  "problem": "exact description with line numbers if possible",\n'
                '  "fix_instruction": "precise instruction for fixing it"\n'
                '}]}\n'
                'If no issues: {"issues": []}'
            )

            review_human = (
                f"{build_ctx}\n\n"
                f"Review these generated files for the project described above:\n\n"
                f"{file_listing}"
            )

            try:
                _rv_resp = await review_llm.ainvoke([
                    SystemMessage(content=review_system),
                    HumanMessage(content=review_human)
                ])
                _raw = _rv_resp.content.strip()
                # Handle thinking models
                if "<think>" in _raw:
                    _think_end = _raw.rfind("</think>")
                    if _think_end != -1:
                        _raw = _raw[_think_end + len("</think>"):].strip()
                # Strip markdown fences if present
                import re as _re_rv
                _raw = _re_rv.sub(r"^```[a-z]*\n?", "", _raw)
                _raw = _re_rv.sub(r"\n?```$", "", _raw.strip())
                # Extract JSON from response
                _fb = _raw.find("{")
                _lb = _raw.rfind("}")
                if _fb != -1 and _lb != -1 and _lb > _fb:
                    _raw = _raw[_fb:_lb + 1]
                try:
                    _rv_parsed = _json_ra.loads(_raw)
                except _json_ra.JSONDecodeError:
                    _cleaned = _re_rv.sub(r',\s*([}\]])', r'\1', _raw)
                    _rv_parsed = _json_ra.loads(_cleaned)
                _review_parsed_ok = True  # At least one successful parse
                issues = _rv_parsed.get("issues", [])
            except Exception as _pe:
                logger.warning(f"  ⚠️  Review parse error ({_pe}) — skipping iteration {_iteration + 1}")
                break

            critical = [i for i in issues if i.get("severity") == "critical"]
            warnings = [i for i in issues if i.get("severity") == "warning"]

            logger.info(f"  [Iteration {_iteration + 1}] Found {len(critical)} critical, {len(warnings)} warning issues")
            for iss in issues:
                sev = iss.get('severity', '?')
                icon = "❌" if sev == "critical" else "⚠️ "
                logger.info(f"    {icon} [{iss.get('file','?')}] {iss.get('type','?')}: {iss.get('problem','')[:120]}")
                console.print(f"    {icon} [{iss.get('file','?')}] {iss.get('type','?')}: [dim]{iss.get('problem','')[:100]}[/dim]")

            # ── Record review issues in codegen error memory ─────────────────
            if issues:
                try:
                    from ..utils.codegen_error_memory import get_error_memory as _gem_ra
                    _mem_ra = _gem_ra()
                    _idea_ra = state.get("idea", "")[:120]
                    _run_id_ra = state.get("run_id", "unknown")
                    _entries_ra = []
                    for iss in issues:
                        _entries_ra.append({
                            "run_id": _run_id_ra,
                            "idea_summary": _idea_ra,
                            "phase": "code_review",
                            "bug_type": iss.get("type", "UNKNOWN"),
                            "file": iss.get("file", "unknown"),
                            "description": iss.get("problem", "")[:300],
                            "fix_applied": iss.get("fix_instruction", "")[:300],
                            "fixed": True,  # review agent fixes them
                        })
                    if _entries_ra:
                        _mem_ra.record_batch(_entries_ra)
                        logger.info(f"  💾 Recorded {len(_entries_ra)} review issues to codegen memory")
                except Exception as _me_ra:
                    logger.debug(f"  Could not record review issues: {_me_ra}")

            if not critical:
                logger.info(f"  ✅ No critical issues in iteration {_iteration + 1}")
                if warnings:
                    logger.info(f"  ℹ️  {len(warnings)} minor warnings (not blocking)")
                break

            # ── Fix each file that has critical issues ───────────────────────
            by_file: dict = {}
            for iss in critical:
                fn = iss.get("file", "")
                if fn in py_files:
                    by_file.setdefault(fn, []).append(iss)

            # Fix all affected files concurrently
            async def _fix_one_file(fname: str, file_issues: list) -> tuple[str, str]:
                issue_text = "\n".join(
                    f"- [{i['type']}] {i['problem']} → FIX: {i['fix_instruction']}"
                    for i in file_issues
                )
                other_ctx = "\n\n".join(
                    f"=== {n} ===\n{c}" for n, c in py_files.items() if n != fname
                )
                fix_msgs = [
                    SystemMessage(content=(
                        "You are an expert Python developer.\n"
                        "Fix ALL reported issues in the given file.\n"
                        "NEVER use relative imports (from .module import X). Always use absolute imports (from module import X).\n"
                        "NEVER use dotted package imports for local files (from project.module import X). All files are FLAT in one directory — use `from module import X` directly.\n"
                        "Return ONLY the complete corrected Python source file.\n"
                        "No markdown fences, no explanation, just the code."
                    )),
                    HumanMessage(content=(
                        f"PROJECT CONTEXT:\n{build_ctx}\n\n"
                        f"Fix these issues in `{fname}`:\n{issue_text}\n\n"
                        f"Current `{fname}`:\n{py_files[fname]}\n\n"
                        f"Other project files (for API reference):\n{other_ctx[:12000]}"
                    ))
                ]
                try:
                    _fix_resp = await fix_llm.ainvoke(fix_msgs)
                    _fixed = _fix_resp.content
                    if "```python" in _fixed:
                        _fixed = _fixed.split("```python")[1].split("```")[0].strip()
                    elif "```" in _fixed:
                        _fixed = _fixed.split("```")[1].split("```")[0].strip()
                    if _fixed.strip():
                        return fname, _fixed.strip()
                except Exception as _fe:
                    logger.warning(f"  ⚠️  Could not fix {fname}: {_fe}")
                return fname, py_files[fname]  # return original if fix failed

            import asyncio as _asyncio_ra
            fix_results = await _asyncio_ra.gather(
                *[_fix_one_file(fn, issues_list) for fn, issues_list in by_file.items()],
                return_exceptions=True
            )
            for res in fix_results:
                if isinstance(res, Exception):
                    logger.warning(f"  ⚠️  Fix task exception: {res}")
                    continue
                fn, new_code = res
                py_files[fn] = new_code
                files[fn] = new_code
                total_issues_fixed += 1
                logger.info(f"  ✅ Fixed: {fn}")
                console.print(f"  [green]✓[/green] Fixed: {fn}")

        # ── Done ─────────────────────────────────────────────────────────────
        if not _review_parsed_ok:
            # Review LLM never returned parseable JSON — code was NOT reviewed
            console.print("\n[yellow]⚠️  Code Review Agent: LLM returned unparseable JSON — review SKIPPED[/yellow]")
            logger.warning("  ⚠️  Code review parse failed on all iterations — code NOT reviewed")
        elif total_issues_fixed > 0:
            console.print(f"\n[green]🔍 Code Review Agent: fixed {total_issues_fixed} file(s)[/green]")
        else:
            console.print("\n[green]🔍 Code Review Agent: code looks correct ✅[/green]")

        # ── Flatten file keys (strip directory prefixes) ─────────────────────
        files = _flatten_file_keys(files, "code_review_agent")

        # ── Strip relative imports after review fixes ────────────────────────
        _cr_module_names = {f[:-3] for f in files if f.endswith(".py")}
        _cr_rel_total = 0
        for _cr_fn, _cr_code in list(files.items()):
            if not _cr_fn.endswith(".py") or not _cr_code:
                continue
            _cr_out = []
            _cr_cnt = 0
            for _cr_line in _cr_code.splitlines():
                _cr_m = _re.match(r"^(\s*from\s+)\.(\w+)(\s+import\s+.*)$", _cr_line)
                if _cr_m:
                    _cr_mod = _cr_m.group(2)
                    if _cr_mod in _cr_module_names:
                        _cr_out.append(f"{_cr_m.group(1)}{_cr_m.group(2)}{_cr_m.group(3)}")
                    else:
                        _cr_out.append(f"# REMOVED phantom relative import: {_cr_line.strip()}")
                    _cr_cnt += 1
                else:
                    _cr_out.append(_cr_line)
            if _cr_cnt:
                files[_cr_fn] = "\n".join(_cr_out)
                _cr_rel_total += _cr_cnt
        if _cr_rel_total:
            logger.info(f"  🔧 Code review: converted {_cr_rel_total} relative import(s) → absolute")

        # ── Flatten dotted package imports after review fixes ────────────────
        _cr_dotted_fixes = _fix_dotted_local_imports(files, "code_review")
        if _cr_dotted_fixes:
            logger.info(f"  🔧 Code review: flattened {_cr_dotted_fixes} dotted package import(s)")

        gc.collect()
        return {
            "current_stage": "code_reviewed",
            "generated_code": {
                **generated_code,
                "files": files,
            }
        }

    except Exception as _e:
        logger.error(f"Code review agent failed: {_e}")
        # Non-fatal — let testing catch whatever it can, but mark failure
        # so downstream nodes know review didn't actually run.
        return {
            "current_stage": "code_review_failed",
            "generated_code": state.get("generated_code", {}),
            "errors": [f"Code review agent crashed: {str(_e)}"],
        }


# ============================================
# Node 8: Code Testing and Validation
# ============================================

async def code_testing_node(state: AutoGITState) -> Dict[str, Any]:
    """
    Node 8: Test generated code in isolated environment
    
    Creates virtual environment, installs dependencies,
    validates syntax, tests imports, and runs basic execution tests.
    ENHANCED: Now includes type checking, security scanning, and linting.
    """
    logger.info("🧪 Code Testing Node")
    
    try:
        from pathlib import Path
        from ..utils.code_executor import CodeExecutor
        from ..utils.enhanced_validator import EnhancedValidator
        import tempfile
        import shutil
        
        generated_code = state.get("generated_code", {})
        files = _flatten_file_keys(generated_code.get("files", {}), "code_testing_input")
        
        if not files:
            logger.warning("No files to test")
            return {
                "current_stage": "testing_skipped",
                "test_results": {"error": "No files generated"}
            }

        # ── FAST PATH: AST syntax pre-check (ms) before expensive venv setup (mins) ──
        # Test artifacts (feature_tests.py, test_main.py) are LLM-generated and
        # may have syntax errors.  Those should NOT block the entire pipeline —
        # only product code syntax errors are fatal.
        import ast as _ast
        _TEST_ARTIFACTS = {"feature_tests.py", "test_main.py"}
        syntax_errors = []
        test_artifact_warnings = []
        for fname, code in files.items():
            if not fname.endswith(".py"):
                continue
            try:
                _ast.parse(code)
            except SyntaxError as _se:
                _err_msg = (
                    f"Syntax error in {fname}: {_se.msg} (line {_se.lineno}): "
                    f"{(_se.text or '').strip()}"
                )
                if fname in _TEST_ARTIFACTS:
                    # Test artifact — warn but don't block pipeline
                    test_artifact_warnings.append(_err_msg)
                    logger.warning(f"  ⚠️  {_err_msg} (test artifact — non-blocking)")
                else:
                    syntax_errors.append(_err_msg)

        # Log test artifact warnings (non-blocking)
        if test_artifact_warnings:
            logger.warning(
                f"  ⚠️  {len(test_artifact_warnings)} test artifact(s) have syntax errors "
                f"(will be excluded from deployment)"
            )
            # Remove broken test artifacts from files so they don't get pushed
            for fname in list(files.keys()):
                if fname in _TEST_ARTIFACTS:
                    try:
                        _ast.parse(files[fname])
                    except SyntaxError:
                        logger.info(f"  🗑️  Removing broken test artifact: {fname}")
                        del files[fname]

        if syntax_errors:
            logger.error("\u274c Syntax errors detected (fast pre-check — skipping venv)")
            for err in syntax_errors:
                logger.error(f"  {err}")
            return {
                "current_stage": "testing_complete",
                "test_results": {
                    "environment_created": False,
                    "dependencies_installed": False,
                    "syntax_valid": False,
                    "import_successful": False,
                    "execution_errors": syntax_errors,
                    "warnings": test_artifact_warnings,
                },
                "tests_passed": False,
                "code_quality": 0,
            }
        
        # Create temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            test_dir = Path(temp_dir) / "test_project"
            test_dir.mkdir(parents=True, exist_ok=True)

            # Sanitize requirements.txt before writing — full stdlib/internal filtering
            def _sanitize_requirements(req_text: str) -> str:
                """Remove stdlib internals, underscore-prefixed modules, bad pins."""
                # Cross-reference against actual .py imports in this project
                py_srcs_for_req = {k: v for k, v in files.items() if k.endswith(".py")}
                # First pass: module-level cleaner strips stdlib + _internals + editable
                cleaned = _clean_requirements_txt(req_text, py_srcs_for_req)
                # Second pass: fix remaining bad version pins
                out = []
                for line in cleaned.splitlines():
                    s = line.strip()
                    if not s or s.startswith("#"):
                        out.append(line)
                        continue
                    # pytorch-lightning <2.0 → lightning>=2.3
                    if s.lower().startswith("pytorch-lightning") and "==" in s:
                        try:
                            major = int(s.split("==")[1].strip().split(".")[0])
                            if major < 2:
                                logger.info(f"  🔧 Auto-fixing bad pin: {s} → lightning>=2.3")
                                out.append("lightning>=2.3")
                                continue
                        except (ValueError, IndexError):
                            pass
                    # torch>=1.8.* invalid wildcard specifier
                    if "torch" in s.lower() and ".*" in s:
                        out.append(_re.sub(r">=(\d+\.\d+)\.\*", r">=\1", s))
                        continue
                    out.append(line)
                return "\n".join(out)

            # Write all files to test directory
            # Safety: flatten any directory-prefixed keys (e.g., "baby_dragon/model.py" → "model.py")
            import os as _os_test
            for filename, content in files.items():
                _flat_name = _os_test.path.basename(filename) if ('/' in filename or '\\' in filename) else filename
                if _flat_name != filename:
                    logger.warning(f"  ⚠️  Flattened test file key '{filename}' → '{_flat_name}'")
                if _flat_name == "requirements.txt":
                    content = _sanitize_requirements(content)
                file_path = test_dir / _flat_name
                file_path.parent.mkdir(parents=True, exist_ok=True)  # safety: ensure parent exists
                file_path.write_text(content, encoding="utf-8")
                logger.info(f"  📝 Wrote {_flat_name} for testing")
            
            # ENHANCED VALIDATION — Run all .py files in parallel
            # EnhancedValidator spawns subprocesses (mypy, bandit, ruff).
            # Running them concurrently via run_in_executor cuts this from
            # sum(per-file time) → max(per-file time).
            validation_results = {}
            quality_scores = []
            validator = EnhancedValidator()

            import asyncio as _asyncio_val
            _val_loop = _asyncio_val.get_event_loop()
            _py_files = [(fname, content, test_dir / fname)
                         for fname, content in files.items() if fname.endswith('.py')]

            logger.info(f"  ⚡ Validating {len(_py_files)} Python files in parallel...")
            _val_results = await _asyncio_val.gather(
                *[
                    _val_loop.run_in_executor(
                        None,
                        lambda c=content, p=str(fpath): validator.validate_all(c, p)
                    )
                    for _, content, fpath in _py_files
                ],
                return_exceptions=True
            )

            for (filename, _content, _fpath), validation in zip(_py_files, _val_results):
                if isinstance(validation, Exception):
                    logger.warning(f"  ⚠️  Validation failed for {filename}: {validation}")
                    validation = {'quality_score': 0, 'passed': False}
                validation_results[filename] = validation
                quality = validation.get('quality_score', 0)
                quality_scores.append(quality)
                logger.info(f"  📊 [{filename}] Quality={quality}/100")
                if validation.get('type_safe', False):
                    logger.info(f"  ✅ [{filename}] Types: Safe")
                security_score = validation.get('security_score', 0)
                if security_score < 70:
                    logger.warning(f"  🔒 [{filename}] Security: {security_score}/100")
                    for issue in validation.get('security_issues', [])[:3]:
                        logger.warning(f"    - {issue}")
                else:
                    logger.info(f"  🔒 [{filename}] Security: {security_score}/100")
                lint_score = validation.get('lint_score', 0)
                logger.info(f"  ✨ [{filename}] Lint: {lint_score}/100")
            
            # Calculate average quality
            avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0
            logger.info(f"📈 Average Code Quality: {avg_quality:.1f}/100")
            
            # Run test suite with hard 5-minute overall timeout (prevents subprocess deadlocks)
            logger.info(f"🔬 Testing code in: {test_dir}")
            executor = CodeExecutor(test_dir)
            import asyncio as _asyncio
            try:
                loop = _asyncio.get_event_loop()
                test_results = await _asyncio.wait_for(
                    loop.run_in_executor(None, lambda: executor.run_full_test_suite(cleanup_after=True)),
                    timeout=300  # 5-minute hard cap on entire test suite
                )
            except _asyncio.TimeoutError:
                logger.error("⏰ Test suite timed out after 5 minutes — skipping execution tests")
                executor.cleanup()
                test_results = {
                    "environment_created": False,
                    "dependencies_installed": False,
                    "syntax_valid": True,   # AST pre-check already verified syntax above
                    "import_successful": False,  # Fail-safe: imports were NOT tested
                    "execution_errors": ["Test suite timed out after 300s (pip install too slow for deps)"],
                    "warnings": ["Skipped: timeout"],
                    "test_outputs": []
                }
            
            # Merge validation results into test_results
            test_results['validation_results'] = validation_results
            test_results['average_quality'] = avg_quality
            
            # Analyze results - ENHANCED with quality thresholds + execution errors
            _exec_errs_list = test_results.get("execution_errors", [])
            _entry_exit = test_results.get("entry_exit_code", None)
            _has_runtime_errors = bool(_exec_errs_list) or (_entry_exit is not None and _entry_exit != 0)
            passed = (
                test_results.get("environment_created", False) and
                test_results.get("dependencies_installed", False) and
                test_results.get("syntax_valid", False) and      # Fail-safe: untested → not passed
                test_results.get("import_successful", False) and  # Fail-safe: untested → not passed
                avg_quality >= 50 and  # Minimum quality threshold
                not _has_runtime_errors  # CRITICAL: fail if main.py crashes or executor found errors
            )

            # ── Static shape/projection audit (runs when pip cannot install) ──
            # If pip failed, we can't run the code. Do a lightweight AST check
            # for nn.Module subclasses that store vocab_size but lack a matching
            # nn.Linear output projection — the #1 cause of runtime IndexError.
            _exec_errors = test_results.get("execution_errors", [])
            _pip_failed = (
                not test_results.get("dependencies_installed", True)
                or (len(_exec_errors) == 1 and "timed out" in str(_exec_errors[0]).lower())
            )
            if _pip_failed and files:
                import ast as _ast_ct
                for _fname, _fcode in files.items():
                    if not _fname.endswith(".py") or not _fcode.strip():
                        continue
                    try:
                        _tree = _ast_ct.parse(_fcode)
                    except SyntaxError:
                        continue
                    for _node in _ast_ct.walk(_tree):
                        if not isinstance(_node, _ast_ct.ClassDef):
                            continue
                        # Check if class stores vocab_size / num_classes
                        _has_vocab_attr = False
                        _has_projection = False
                        _has_ce_loss = False
                        for _child in _ast_ct.walk(_node):
                            # self.vocab_size = ... or self.num_classes = ...
                            if isinstance(_child, _ast_ct.Attribute) and isinstance(_child.value, _ast_ct.Name):
                                if _child.value.id == "self" and _child.attr in ("vocab_size", "num_classes", "output_size"):
                                    _has_vocab_attr = True
                            # nn.Linear(..., vocab_size) or nn.Linear(..., self.vocab_size)
                            if isinstance(_child, _ast_ct.Call):
                                _call_name = ""
                                if isinstance(_child.func, _ast_ct.Attribute):
                                    _call_name = _child.func.attr
                                elif isinstance(_child.func, _ast_ct.Name):
                                    _call_name = _child.func.id
                                if _call_name == "Linear" and len(_child.args) >= 2:
                                    _arg2 = _child.args[1]
                                    if isinstance(_arg2, _ast_ct.Attribute) and isinstance(_arg2.value, _ast_ct.Name):
                                        if _arg2.attr in ("vocab_size", "num_classes", "output_size"):
                                            _has_projection = True
                                    elif isinstance(_arg2, _ast_ct.Name) and _arg2.id in ("vocab_size", "num_classes", "output_size"):
                                        _has_projection = True
                                # Check for CrossEntropyLoss usage
                                if _call_name in ("CrossEntropyLoss", "cross_entropy"):
                                    _has_ce_loss = True
                        if _has_vocab_attr and not _has_projection:
                            _errmsg = (
                                f"STATIC CHECK: {_fname}::{_node.name} stores vocab_size/num_classes "
                                f"but has no nn.Linear(..., vocab_size) projection in __init__. "
                                f"forward() likely returns d_model dims → IndexError with CrossEntropyLoss."
                            )
                            logger.warning(f"  ⚠️  {_errmsg}")
                            _exec_errors.append(_errmsg)
                            test_results["execution_errors"] = _exec_errors

            # ── Static placeholder audit (catch `model = nn.Module()`) ───────
            # LLMs sometimes generate `model = nn.Module()  # placeholder`
            # with the real init commented out.  This always crashes at runtime
            # with "optimizer got an empty parameter list".
            if files:
                import ast as _ast_ph, re as _re_ph
                for _fname, _fcode in files.items():
                    if not _fname.endswith(".py") or not _fcode.strip():
                        continue
                    # Quick regex check for nn.Module() bare instantiation
                    for _lineno, _line in enumerate(str(_fcode).splitlines(), 1):
                        _stripped = _line.strip()
                        # Detect: `model = nn.Module()`, `variable = nn.Module()`
                        if _re_ph.match(r"^\w+\s*=\s*nn\.Module\(\s*\)", _stripped):
                            _errmsg = (
                                f"PLACEHOLDER_INIT: {_fname}:{_lineno} — `{_stripped}` "
                                f"uses bare nn.Module() instead of a real model class. "
                                f"This will crash with 'optimizer got an empty parameter list'. "
                                f"Replace with the actual model class imported from model.py."
                            )
                            logger.warning(f"  ⚠️  {_errmsg}")
                            _exec_errors = test_results.get("execution_errors", [])
                            _exec_errors.append(_errmsg)
                            test_results["execution_errors"] = _exec_errors
                            if test_results.get("tests_passed"):
                                test_results["tests_passed"] = False

            # ── Static method-call & attribute validator ──────────────────
            # (A) Cross-file: var.method() where var = ClassName() from another file
            # (B) Intra-class: self.method() where method doesn't exist in the class
            # (C) Uninitialized attrs: self.attr read before __init__ assigns it
            # (D) Cross-file: var.attr where attr doesn't exist on the class
            # (E) Windows encoding: non-ASCII chars that crash on cp1252
            if files:
                import ast as _ast_xm
                # Step 1: collect class → set of method names AND attribute names (across ALL files)
                _class_methods = {}   # {class_name: set of method names}
                _class_attrs = {}     # {class_name: set of attribute names set in __init__}
                _class_file = {}      # {class_name: filename}
                _class_nodes = {}     # {(filename, class_name): ClassDef node}
                for _xf, _xc in files.items():
                    if not _xf.endswith(".py") or not str(_xc).strip():
                        continue
                    try:
                        _tree = _ast_xm.parse(str(_xc))
                        for _node in _ast_xm.iter_child_nodes(_tree):
                            if isinstance(_node, _ast_xm.ClassDef):
                                _methods = set()
                                _attrs = set()
                                for _item in _node.body:
                                    if isinstance(_item, (_ast_xm.FunctionDef, _ast_xm.AsyncFunctionDef)):
                                        _methods.add(_item.name)
                                        # Collect attributes set by self.X = ... in __init__
                                        if _item.name == "__init__":
                                            for _stmt in _ast_xm.walk(_item):
                                                if isinstance(_stmt, _ast_xm.Assign):
                                                    for _tgt in _stmt.targets:
                                                        if (isinstance(_tgt, _ast_xm.Attribute) and
                                                            isinstance(_tgt.value, _ast_xm.Name) and _tgt.value.id == "self"):
                                                            _attrs.add(_tgt.attr)
                                                elif isinstance(_stmt, _ast_xm.AnnAssign) and _stmt.target:
                                                    _tgt = _stmt.target
                                                    if (isinstance(_tgt, _ast_xm.Attribute) and
                                                        isinstance(_tgt.value, _ast_xm.Name) and _tgt.value.id == "self"):
                                                        _attrs.add(_tgt.attr)
                                    # Also collect class-level attributes (X = ...)
                                    elif isinstance(_item, _ast_xm.Assign):
                                        for _tgt in _item.targets:
                                            if isinstance(_tgt, _ast_xm.Name):
                                                _attrs.add(_tgt.id)
                                # Properties count as both attrs and methods
                                for _item in _node.body:
                                    if isinstance(_item, (_ast_xm.FunctionDef, _ast_xm.AsyncFunctionDef)):
                                        for _dec in _item.decorator_list:
                                            if isinstance(_dec, _ast_xm.Name) and _dec.id == "property":
                                                _attrs.add(_item.name)
                                _class_methods[_node.name] = _methods
                                _class_attrs[_node.name] = _attrs
                                _class_file[_node.name] = _xf
                                _class_nodes[(_xf, _node.name)] = _node
                    except SyntaxError:
                        pass

                def _report_mismatch(_tag, _msg):
                    logger.warning(f"  ⚠️  {_msg}")
                    _el = test_results.get("execution_errors", [])
                    _el.append(_msg)
                    test_results["execution_errors"] = _el
                    if test_results.get("tests_passed"):
                        test_results["tests_passed"] = False

                # ── (B) Intra-class self.method() check ──────────────────
                for (_xf, _cname), _cls_node in _class_nodes.items():
                    _methods = _class_methods.get(_cname, set())
                    for _node in _ast_xm.walk(_cls_node):
                        if not isinstance(_node, _ast_xm.Call):
                            continue
                        _func = _node.func
                        if not isinstance(_func, _ast_xm.Attribute):
                            continue
                        # Check self.method() calls
                        if isinstance(_func.value, _ast_xm.Name) and _func.value.id == "self":
                            _mname = _func.attr
                            if _mname.startswith("__") and _mname.endswith("__"):
                                continue  # skip dunder methods
                            if _mname not in _methods:
                                _lineno = getattr(_node, "lineno", "?")
                                _avail = sorted(m for m in _methods if not (m.startswith("__") and m.endswith("__")))
                                _report_mismatch("SELF_METHOD",
                                    f"SELF_METHOD_MISSING: {_xf}:{_lineno} — class `{_cname}` calls "
                                    f"`self.{_mname}()` but no method `{_mname}` exists. "
                                    f"Available methods: {_avail}")

                # ── (C) Uninitialized self.attr detection ─────────────────
                for (_xf, _cname), _cls_node in _class_nodes.items():
                    # Find attrs set in __init__ (before any method call)
                    _init_attrs = set()
                    _init_node = None
                    for _item in _cls_node.body:
                        if isinstance(_item, (_ast_xm.FunctionDef, _ast_xm.AsyncFunctionDef)) and _item.name == "__init__":
                            _init_node = _item
                            break
                    if not _init_node:
                        continue
                    # Walk __init__ body line by line to find attrs set BEFORE first method call
                    _first_call_line = 99999
                    for _stmt in _ast_xm.walk(_init_node):
                        if isinstance(_stmt, _ast_xm.Call) and isinstance(getattr(_stmt, 'func', None), _ast_xm.Attribute):
                            _f = _stmt.func
                            if isinstance(_f.value, _ast_xm.Name) and _f.value.id == "self":
                                _ln = getattr(_stmt, "lineno", 99999)
                                if _ln < _first_call_line:
                                    _first_call_line = _ln
                    # Collect attrs assigned before the first self.method() call
                    for _stmt in _ast_xm.walk(_init_node):
                        if isinstance(_stmt, _ast_xm.Assign):
                            for _tgt in _stmt.targets:
                                if (isinstance(_tgt, _ast_xm.Attribute) and
                                    isinstance(_tgt.value, _ast_xm.Name) and _tgt.value.id == "self"):
                                    _assign_line = getattr(_stmt, "lineno", 0)
                                    if _assign_line < _first_call_line:
                                        _init_attrs.add(_tgt.attr)
                    # Now find all self.method() calls in __init__ and check what attrs those methods READ
                    _methods_in_class = _class_methods.get(_cname, set())
                    for _stmt in _ast_xm.walk(_init_node):
                        if isinstance(_stmt, _ast_xm.Call) and isinstance(getattr(_stmt, 'func', None), _ast_xm.Attribute):
                            _f = _stmt.func
                            if isinstance(_f.value, _ast_xm.Name) and _f.value.id == "self" and _f.attr in _methods_in_class:
                                # Find the method body and check what self.attrs it reads
                                for _m_item in _cls_node.body:
                                    if isinstance(_m_item, (_ast_xm.FunctionDef, _ast_xm.AsyncFunctionDef)) and _m_item.name == _f.attr:
                                        for _m_node in _ast_xm.walk(_m_item):
                                            if (isinstance(_m_node, _ast_xm.Attribute) and
                                                isinstance(_m_node.value, _ast_xm.Name) and _m_node.value.id == "self"):
                                                _attr = _m_node.attr
                                                # Only flag reads (not writes) — check if this is a load context
                                                if isinstance(getattr(_m_node, 'ctx', None), _ast_xm.Load):
                                                    if _attr not in _init_attrs and _attr not in _methods_in_class:
                                                        _lineno = getattr(_m_node, "lineno", "?")
                                                        _report_mismatch("UNINIT_ATTR",
                                                            f"UNINITIALIZED_ATTR: {_xf}:{_lineno} — class `{_cname}`: "
                                                            f"`self.{_attr}` is read inside `{_f.attr}()` which is called from `__init__`, "
                                                            f"but `self.{_attr}` is not initialized before the call. "
                                                            f"Add `self.{_attr} = ...` in `__init__` before `self.{_f.attr}()`.")
                                                        _init_attrs.add(_attr)  # avoid duplicate reports
                                        break

                # ── (A) Cross-file var.method() check ────────────────────
                for _xf, _xc in files.items():
                    if not _xf.endswith(".py") or not str(_xc).strip():
                        continue
                    try:
                        _tree = _ast_xm.parse(str(_xc))
                    except SyntaxError:
                        continue
                    _var_class = {}  # {var_name: class_name}
                    _var_ambiguous = set()  # var names assigned to multiple things
                    _var_any_assignment = set()  # ALL vars that are ever assigned via X(...)
                    for _node in _ast_xm.walk(_tree):
                        if isinstance(_node, _ast_xm.Assign) and len(_node.targets) == 1:
                            _tgt = _node.targets[0]
                            if isinstance(_tgt, _ast_xm.Name) and isinstance(_node.value, _ast_xm.Call):
                                _call_func = _node.value.func
                                _cname = None
                                if isinstance(_call_func, _ast_xm.Name):
                                    _cname = _call_func.id
                                elif isinstance(_call_func, _ast_xm.Attribute):
                                    _cname = _call_func.attr
                                if _cname and _cname in _class_methods:
                                    if _tgt.id in _var_class and _var_class[_tgt.id] != _cname:
                                        _var_ambiguous.add(_tgt.id)  # same var, different class
                                    # Also ambiguous if previously assigned to unknown
                                    if _tgt.id in _var_any_assignment and _tgt.id not in _var_class:
                                        _var_ambiguous.add(_tgt.id)
                                    _var_class[_tgt.id] = _cname
                                else:
                                    # Assigned to something NOT in our local classes
                                    # (e.g., argparse.ArgumentParser) — mark ambiguous
                                    # if it's also assigned to a known class anywhere
                                    if _tgt.id in _var_class:
                                        _var_ambiguous.add(_tgt.id)
                                _var_any_assignment.add(_tgt.id)
                            # Also: self.var = ClassName(...)
                            if (isinstance(_tgt, _ast_xm.Attribute) and
                                isinstance(_tgt.value, _ast_xm.Name) and _tgt.value.id == "self"):
                                if isinstance(_node.value, _ast_xm.Call):
                                    _call_func = _node.value.func
                                    _cname = None
                                    if isinstance(_call_func, _ast_xm.Name):
                                        _cname = _call_func.id
                                    elif isinstance(_call_func, _ast_xm.Attribute):
                                        _cname = _call_func.attr
                                    _sa = "self." + _tgt.attr
                                    if _cname and _cname in _class_methods:
                                        if _sa in _var_class and _var_class[_sa] != _cname:
                                            _var_ambiguous.add(_sa)
                                        if _sa in _var_any_assignment and _sa not in _var_class:
                                            _var_ambiguous.add(_sa)
                                        _var_class[_sa] = _cname
                                    else:
                                        if _sa in _var_class:
                                            _var_ambiguous.add(_sa)
                                    _var_any_assignment.add(_sa)
                    # Remove ambiguous variables — they could be stdlib types
                    for _amb in _var_ambiguous:
                        _var_class.pop(_amb, None)

                    for _node in _ast_xm.walk(_tree):
                        if not isinstance(_node, _ast_xm.Call):
                            continue
                        _func = _node.func
                        if not isinstance(_func, _ast_xm.Attribute):
                            continue
                        _method_name = _func.attr
                        if _method_name.startswith("__") and _method_name.endswith("__"):
                            continue  # skip dunder only
                        _obj = _func.value
                        _var_name = None
                        if isinstance(_obj, _ast_xm.Name):
                            _var_name = _obj.id
                        elif (isinstance(_obj, _ast_xm.Attribute) and
                              isinstance(_obj.value, _ast_xm.Name) and _obj.value.id == "self"):
                            _var_name = "self." + _obj.attr
                        if _var_name and _var_name in _var_class:
                            _cname = _var_class[_var_name]
                            _known_methods = _class_methods.get(_cname, set())
                            if _method_name not in _known_methods:
                                _lineno = getattr(_node, "lineno", "?")
                                _report_mismatch("API_MISMATCH",
                                    f"API_MISMATCH: {_xf}:{_lineno} — `{_var_name}.{_method_name}()` "
                                    f"called but class `{_cname}` (in {_class_file.get(_cname, '?')}) "
                                    f"has no method `{_method_name}`. "
                                    f"Available methods: {sorted(m for m in _known_methods if not m.startswith('_'))}")

                # ── (D) Cross-file attribute ACCESS check (non-call) ─────
                # Catches: db_manager.db_path when class has self._db_path
                # This is NOT about method calls — it's about reading attributes
                for _xf, _xc in files.items():
                    if not _xf.endswith(".py") or not str(_xc).strip():
                        continue
                    try:
                        _tree = _ast_xm.parse(str(_xc))
                    except SyntaxError:
                        continue
                    # Re-collect var→class mappings for this file (with ambiguity tracking)
                    _var_class_attr = {}
                    _var_attr_ambiguous = set()
                    _var_attr_any = set()  # all vars assigned via X(...)
                    for _node in _ast_xm.walk(_tree):
                        if isinstance(_node, _ast_xm.Assign) and len(_node.targets) == 1:
                            _tgt = _node.targets[0]
                            if isinstance(_tgt, _ast_xm.Name) and isinstance(_node.value, _ast_xm.Call):
                                _call_func = _node.value.func
                                _cname = None
                                if isinstance(_call_func, _ast_xm.Name):
                                    _cname = _call_func.id
                                elif isinstance(_call_func, _ast_xm.Attribute):
                                    _cname = _call_func.attr
                                if _cname and _cname in _class_attrs:
                                    if _tgt.id in _var_class_attr and _var_class_attr[_tgt.id] != _cname:
                                        _var_attr_ambiguous.add(_tgt.id)
                                    if _tgt.id in _var_attr_any and _tgt.id not in _var_class_attr:
                                        _var_attr_ambiguous.add(_tgt.id)
                                    _var_class_attr[_tgt.id] = _cname
                                else:
                                    if _tgt.id in _var_class_attr:
                                        _var_attr_ambiguous.add(_tgt.id)
                                _var_attr_any.add(_tgt.id)
                            if (isinstance(_tgt, _ast_xm.Attribute) and
                                isinstance(_tgt.value, _ast_xm.Name) and _tgt.value.id == "self"):
                                if isinstance(_node.value, _ast_xm.Call):
                                    _call_func = _node.value.func
                                    _cname = None
                                    if isinstance(_call_func, _ast_xm.Name):
                                        _cname = _call_func.id
                                    elif isinstance(_call_func, _ast_xm.Attribute):
                                        _cname = _call_func.attr
                                    _sa = "self." + _tgt.attr
                                    if _cname and _cname in _class_attrs:
                                        if _sa in _var_class_attr and _var_class_attr[_sa] != _cname:
                                            _var_attr_ambiguous.add(_sa)
                                        if _sa in _var_attr_any and _sa not in _var_class_attr:
                                            _var_attr_ambiguous.add(_sa)
                                        _var_class_attr[_sa] = _cname
                                    else:
                                        if _sa in _var_class_attr:
                                            _var_attr_ambiguous.add(_sa)
                                    _var_attr_any.add(_sa)
                    # Remove ambiguous variables
                    for _amb in _var_attr_ambiguous:
                        _var_class_attr.pop(_amb, None)

                    # Now find all var.attr accesses that are NOT method calls
                    for _node in _ast_xm.walk(_tree):
                        if isinstance(_node, _ast_xm.Attribute) and isinstance(getattr(_node, 'ctx', None), _ast_xm.Load):
                            # Skip if this is part of a Call (already checked by method validator)
                            _attr_name = _node.attr
                            # Determine variable name
                            _obj = _node.value
                            _var_name = None
                            if isinstance(_obj, _ast_xm.Name):
                                _var_name = _obj.id
                            elif (isinstance(_obj, _ast_xm.Attribute) and
                                  isinstance(_obj.value, _ast_xm.Name) and _obj.value.id == "self"):
                                _var_name = "self." + _obj.attr
                            if not _var_name or _var_name not in _var_class_attr:
                                continue
                            _cname = _var_class_attr[_var_name]
                            _known_attrs = _class_attrs.get(_cname, set())
                            _known_meths = _class_methods.get(_cname, set())
                            # Skip if attr is a known method (it's a method reference, not attr access)
                            if _attr_name in _known_meths:
                                continue
                            # Skip dunder attrs (always assumed to exist)
                            if _attr_name.startswith("__") and _attr_name.endswith("__"):
                                continue
                            if _attr_name not in _known_attrs:
                                _lineno = getattr(_node, "lineno", "?")
                                # Build a helpful suggestion — maybe they used public name but attr is private
                                _suggestion = ""
                                _private_name = "_" + _attr_name
                                _public_name = _attr_name.lstrip("_")
                                if _private_name in _known_attrs:
                                    _suggestion = f" Did you mean `{_var_name}.{_private_name}`?"
                                elif _public_name in _known_attrs and _public_name != _attr_name:
                                    _suggestion = f" Did you mean `{_var_name}.{_public_name}`?"
                                else:
                                    _similar = [a for a in _known_attrs if _attr_name.lower() in a.lower() or a.lower() in _attr_name.lower()]
                                    if _similar:
                                        _suggestion = f" Similar attributes: {sorted(_similar)}"
                                _report_mismatch("ATTR_MISMATCH",
                                    f"ATTR_MISMATCH: {_xf}:{_lineno} — `{_var_name}.{_attr_name}` "
                                    f"accessed but class `{_cname}` (in {_class_file.get(_cname, '?')}) "
                                    f"has no attribute `{_attr_name}`.{_suggestion} "
                                    f"Available attributes: {sorted(a for a in _known_attrs if not a.startswith('__'))}")

                # ── (E) Windows encoding check ───────────────────────────
                # Detect non-ASCII characters (emoji, unicode symbols) in code
                # that will crash on Windows cp1252 encoding if printed to stdout
                import sys as _sys_enc
                if _sys_enc.platform == "win32":
                    for _ef_name, _ef_code in files.items():
                        if not _ef_name.endswith(".py") or not str(_ef_code).strip():
                            continue
                        _non_ascii_lines = []
                        for _ln, _line in enumerate(str(_ef_code).splitlines(), 1):
                            try:
                                _line.encode("cp1252")
                            except (UnicodeEncodeError, UnicodeDecodeError):
                                _non_ascii_lines.append((_ln, _line.strip()[:60]))
                        if _non_ascii_lines:
                            _examples = _non_ascii_lines[:5]
                            _report_mismatch("ENCODING_ISSUE",
                                f"ENCODING_ISSUE: {_ef_name} has {len(_non_ascii_lines)} line(s) with "
                                f"non-ASCII characters (emoji/unicode) that will crash on Windows cp1252. "
                                f"Examples: {_examples}. "
                                f"FIX: Replace emoji/unicode symbols with ASCII equivalents "
                                f"(e.g., '[OK]' instead of '✅', '[FAIL]' instead of '❌', "
                                f"'[WARN]' instead of '⚠️'). Or wrap all print() calls in a helper "
                                f"that catches UnicodeEncodeError.")

            # ── (F) SQLite non-deterministic GENERATED column check ───────
            # SQLite forbids non-deterministic functions (date(), time(),
            # random(), datetime(), julianday(), strftime('%s','now'), etc.)
            # in GENERATED ALWAYS AS columns.  CREATE TABLE succeeds but
            # INSERT with a non-NULL value for the column used in the
            # expression crashes with:
            #   OperationalError: non-deterministic use of date() in a generated column
            # FIX: remove the GENERATED column and compute it in Python.
            if files:
                import re as _re_gen_col
                _NONDETERMINISTIC_FNS = r"(?:date|time|random|datetime|julianday|strftime)\s*\("
                for _gc_fname, _gc_code in files.items():
                    if not _gc_fname.endswith(".py") or not str(_gc_code).strip():
                        continue
                    _gc_str = str(_gc_code)
                    # Find GENERATED ALWAYS AS (...) blocks
                    for _gc_match in _re_gen_col.finditer(
                        r'GENERATED\s+ALWAYS\s+AS\s*\((.+?)\)\s*(?:STORED|VIRTUAL)',
                        _gc_str, _re_gen_col.IGNORECASE | _re_gen_col.DOTALL
                    ):
                        _gc_expr = _gc_match.group(1)
                        _gc_bad_fns = _re_gen_col.findall(_NONDETERMINISTIC_FNS, _gc_expr, _re_gen_col.IGNORECASE)
                        if _gc_bad_fns:
                            _gc_lineno = _gc_str[:_gc_match.start()].count("\n") + 1
                            _errmsg = (
                                f"SQLITE_NONDETERMINISTIC_GENERATED_COL: {_gc_fname}:{_gc_lineno} — "
                                f"GENERATED ALWAYS AS column uses non-deterministic function(s): "
                                f"{_gc_bad_fns}. SQLite forbids date()/time()/random()/datetime() "
                                f"in generated columns. FIX: Remove the GENERATED column entirely "
                                f"and compute this value in Python (e.g., as a @property on the "
                                f"model class). The column expression was: {_gc_expr[:120]}"
                            )
                            logger.warning(f"  ⚠️  {_errmsg}")
                            _exec_errors = test_results.get("execution_errors", [])
                            _exec_errors.append(_errmsg)
                            test_results["execution_errors"] = _exec_errors
                            if test_results.get("tests_passed"):
                                test_results["tests_passed"] = False
                            passed = False

            # ── (G) Shadow file name collision detector ───────────────────
            # LLMs sometimes create files named after stdlib/third-party
            # packages (e.g., numpy.py, torch.py, jwt.py) which shadow
            # the real package and cause ImportError with circular import.
            # This catches cases the code_generation shadow sanitizer missed.
            if files:
                _SHADOW_STEMS_CT = {
                    "torch", "numpy", "pandas", "scipy", "sklearn", "tensorflow",
                    "keras", "matplotlib", "seaborn", "cv2", "jwt", "bcrypt",
                    "websockets", "websocket", "cryptography", "yaml", "toml",
                    "transformers", "datasets", "tokenizers", "accelerate",
                    "requests", "httpx", "aiohttp", "pydantic", "sqlalchemy",
                    "redis", "celery", "click", "typer", "rich", "flask",
                    "django", "fastapi", "dotenv",
                    # stdlib
                    "os", "sys", "re", "io", "math", "time", "random", "copy",
                    "json", "csv", "logging", "pathlib", "typing", "collections",
                    "functools", "itertools", "asyncio", "subprocess", "socket",
                    "hashlib", "datetime", "string", "dataclasses", "warnings",
                    "sqlite3", "threading", "multiprocessing", "abc", "enum",
                    "inspect", "importlib", "ast", "struct", "array", "queue",
                    "http", "urllib", "email", "html", "xml", "ssl",
                    "secrets", "base64", "uuid", "decimal", "operator",
                    "calendar", "textwrap", "unittest", "contextlib",
                    "configparser", "glob", "fnmatch", "shutil", "tempfile",
                    "argparse", "signal", "heapq", "bisect",
                }
                for _sf_name in list(files.keys()):
                    if not _sf_name.endswith(".py"):
                        continue
                    _sf_stem = _sf_name.rsplit(".", 1)[0].lower()
                    if _sf_stem in _SHADOW_STEMS_CT:
                        _errmsg = (
                            f"SHADOW_FILE: {_sf_name} shadows the '{_sf_stem}' package/module. "
                            f"Any file that does `import {_sf_stem}` will import this local file "
                            f"instead of the real package, causing ImportError or circular import. "
                            f"FIX: Rename {_sf_name} to project_{_sf_stem}.py or {_sf_stem}_module.py "
                            f"and update all imports accordingly."
                        )
                        logger.warning(f"  ⚠️  {_errmsg}")
                        _exec_errors = test_results.get("execution_errors", [])
                        _exec_errors.append(_errmsg)
                        test_results["execution_errors"] = _exec_errors
                        if test_results.get("tests_passed"):
                            test_results["tests_passed"] = False
                        passed = False

            # ── (H) Colorama init() / missing import detector ─────────────
            # LLMs often call `init(autoreset=True)` at module level from
            # the `colorama` package but forget to import it, causing:
            #   NameError: name 'init' is not defined
            if files:
                import re as _re_colorama
                for _ci_fname, _ci_code in files.items():
                    if not _ci_fname.endswith(".py") or not str(_ci_code).strip():
                        continue
                    _ci_str = str(_ci_code)
                    # Check for bare init(autoreset=...) without colorama import
                    if _re_colorama.search(r'^\s*init\s*\(\s*autoreset\s*=', _ci_str, _re_colorama.MULTILINE):
                        has_colorama_import = bool(_re_colorama.search(
                            r'^\s*from\s+colorama\s+import\s+.*\binit\b', _ci_str, _re_colorama.MULTILINE
                        ))
                        if not has_colorama_import:
                            _errmsg = (
                                f"MISSING_COLORAMA_IMPORT: {_ci_fname} — calls `init(autoreset=True)` "
                                f"(colorama) at module level but never imports it. "
                                f"FIX: Add `from colorama import init` at the top, or wrap the "
                                f"init() call in a try/except, or remove it entirely if colorama "
                                f"is not actually needed."
                            )
                            logger.warning(f"  ⚠️  {_errmsg}")
                            _exec_errors = test_results.get("execution_errors", [])
                            _exec_errors.append(_errmsg)
                            test_results["execution_errors"] = _exec_errors
                            if test_results.get("tests_passed"):
                                test_results["tests_passed"] = False
                            passed = False

            # ── (I) Class-scope NameError detector ────────────────────────
            # LLMs put type annotations in class body that reference names
            # not yet imported or defined at class scope, e.g.:
            #   class Worker:
            #       def __init__(self, task_queue: TaskQueue, ...):
            # If TaskQueue is defined in another file but not imported,
            # Python raises NameError at class definition time (not at
            # instantiation).  Scan for type hints in method signatures
            # that reference names not available in the file's namespace.
            if files:
                import ast as _ast_cs
                for _cs_fname, _cs_code in files.items():
                    if not _cs_fname.endswith(".py") or not str(_cs_code).strip():
                        continue
                    try:
                        _cs_tree = _ast_cs.parse(str(_cs_code))
                    except SyntaxError:
                        continue
                    # Collect all top-level names: imports, classes, functions, assignments
                    _defined_names = set()
                    for _cs_node in _ast_cs.iter_child_nodes(_cs_tree):
                        if isinstance(_cs_node, _ast_cs.Import):
                            for alias in _cs_node.names:
                                _defined_names.add(alias.asname or alias.name.split(".")[0])
                        elif isinstance(_cs_node, _ast_cs.ImportFrom):
                            if _cs_node.names:
                                for alias in _cs_node.names:
                                    _defined_names.add(alias.asname or alias.name)
                        elif isinstance(_cs_node, _ast_cs.ClassDef):
                            _defined_names.add(_cs_node.name)
                        elif isinstance(_cs_node, (_ast_cs.FunctionDef, _ast_cs.AsyncFunctionDef)):
                            _defined_names.add(_cs_node.name)
                        elif isinstance(_cs_node, _ast_cs.Assign):
                            for _tgt in _cs_node.targets:
                                if isinstance(_tgt, _ast_cs.Name):
                                    _defined_names.add(_tgt.id)
                    # Add builtins
                    _defined_names.update({
                        "int", "str", "float", "bool", "list", "dict", "set", "tuple",
                        "bytes", "bytearray", "memoryview", "complex", "frozenset",
                        "type", "object", "None", "True", "False", "Ellipsis",
                        "range", "enumerate", "zip", "map", "filter", "sorted",
                        "reversed", "len", "min", "max", "sum", "abs", "round",
                        "print", "input", "open", "super", "property", "classmethod",
                        "staticmethod", "isinstance", "issubclass", "hasattr",
                        "getattr", "setattr", "delattr", "callable", "iter", "next",
                        "hash", "id", "repr", "format", "chr", "ord", "hex", "oct",
                        "bin", "pow", "divmod", "vars", "dir", "globals", "locals",
                        "any", "all", "breakpoint", "compile", "eval", "exec",
                        "Exception", "ValueError", "TypeError", "KeyError",
                        "IndexError", "AttributeError", "RuntimeError",
                        "FileNotFoundError", "OSError", "IOError", "ImportError",
                        "StopIteration", "GeneratorExit", "SystemExit",
                        "NotImplementedError", "OverflowError", "ZeroDivisionError",
                        "NameError", "SyntaxError", "UnicodeError", "ConnectionError",
                        # typing names
                        "Optional", "List", "Dict", "Tuple", "Set", "Any",
                        "Union", "Callable", "Iterator", "Generator", "Sequence",
                        "Mapping", "Iterable", "Type", "ClassVar",
                        # also add every class defined in other files in this project
                    })
                    # Add classes from other project files
                    for _other_fname, _other_code in files.items():
                        if _other_fname == _cs_fname or not _other_fname.endswith(".py"):
                            continue
                        try:
                            _other_tree = _ast_cs.parse(str(_other_code))
                            for _on in _ast_cs.iter_child_nodes(_other_tree):
                                if isinstance(_on, _ast_cs.ClassDef):
                                    _defined_names.add(_on.name)
                                elif isinstance(_on, (_ast_cs.FunctionDef, _ast_cs.AsyncFunctionDef)):
                                    _defined_names.add(_on.name)
                        except SyntaxError:
                            pass
                    # Now check class-level type annotations in method signatures
                    for _cs_node in _ast_cs.walk(_cs_tree):
                        if not isinstance(_cs_node, _ast_cs.ClassDef):
                            continue
                        for _method in _cs_node.body:
                            if not isinstance(_method, (_ast_cs.FunctionDef, _ast_cs.AsyncFunctionDef)):
                                continue
                            # Check argument annotations
                            for _arg in _method.args.args + _method.args.kwonlyargs:
                                if _arg.annotation and isinstance(_arg.annotation, _ast_cs.Name):
                                    _ann_name = _arg.annotation.id
                                    if _ann_name not in _defined_names:
                                        # Check if it looks like a class name (starts uppercase)
                                        if _ann_name[0].isupper():
                                            _errmsg = (
                                                f"CLASS_SCOPE_NAME_ERROR: {_cs_fname}:{_method.lineno} — "
                                                f"method `{_cs_node.name}.{_method.name}()` uses type hint "
                                                f"`{_ann_name}` which is not imported or defined in this file. "
                                                f"Python evaluates type annotations at class definition time, "
                                                f"so this will raise NameError when the class is loaded. "
                                                f"FIX: Add `from <module> import {_ann_name}` at the top of "
                                                f"the file, or use a string annotation: `'{_ann_name}'`."
                                            )
                                            logger.warning(f"  ⚠️  {_errmsg}")
                                            _exec_errors = test_results.get("execution_errors", [])
                                            _exec_errors.append(_errmsg)
                                            test_results["execution_errors"] = _exec_errors
                                            if test_results.get("tests_passed"):
                                                test_results["tests_passed"] = False
                                            passed = False

            # ── (J) Empty/stub file detector ──────────────────────────────
            # LLMs sometimes generate a file that's supposed to define key
            # classes but it's empty or just has a single-line syntax error.
            # e.g., numpy.py with `<no output>` → SyntaxError at line 1.
            if files:
                for _ef_fname, _ef_code in files.items():
                    if not _ef_fname.endswith(".py"):
                        continue
                    _ef_str = str(_ef_code).strip()
                    if not _ef_str or len(_ef_str) < 10:
                        # Check if any other file imports from this one
                        _ef_mod = _ef_fname.rsplit(".", 1)[0]
                        _is_imported = False
                        for _other_fn, _other_code in files.items():
                            if _other_fn == _ef_fname:
                                continue
                            if f"import {_ef_mod}" in str(_other_code) or f"from {_ef_mod}" in str(_other_code):
                                _is_imported = True
                                break
                        if _is_imported:
                            _errmsg = (
                                f"EMPTY_STUB_FILE: {_ef_fname} is empty or near-empty "
                                f"({len(_ef_str)} chars) but other files import from it. "
                                f"This will cause ImportError at runtime. "
                                f"FIX: Implement the required classes/functions in {_ef_fname}."
                            )
                            logger.warning(f"  ⚠️  {_errmsg}")
                            _exec_errors = test_results.get("execution_errors", [])
                            _exec_errors.append(_errmsg)
                            test_results["execution_errors"] = _exec_errors
                            if test_results.get("tests_passed"):
                                test_results["tests_passed"] = False
                            passed = False

            # ── (K) Cross-file import name mismatch detector ─────────────
            # LLMs generate `from module import ClassName` where ClassName
            # doesn't exist in that module (wrong name, different spelling,
            # or stub file).  This catches ImportError at runtime.
            if files:
                import ast as _ast_xfi
                # Build a map: module_stem → set of exported top-level names
                _module_exports: Dict[str, set] = {}
                for _xfi_fname, _xfi_code in files.items():
                    if not _xfi_fname.endswith(".py") or not str(_xfi_code).strip():
                        continue
                    _xfi_mod = _xfi_fname.rsplit(".", 1)[0]
                    _exports = set()
                    try:
                        _xfi_tree = _ast_xfi.parse(str(_xfi_code))
                        for _xfi_node in _ast_xfi.iter_child_nodes(_xfi_tree):
                            if isinstance(_xfi_node, _ast_xfi.ClassDef):
                                _exports.add(_xfi_node.name)
                            elif isinstance(_xfi_node, (_ast_xfi.FunctionDef, _ast_xfi.AsyncFunctionDef)):
                                _exports.add(_xfi_node.name)
                            elif isinstance(_xfi_node, _ast_xfi.Assign):
                                for _tgt in _xfi_node.targets:
                                    if isinstance(_tgt, _ast_xfi.Name):
                                        _exports.add(_tgt.id)
                            elif isinstance(_xfi_node, (_ast_xfi.Import, _ast_xfi.ImportFrom)):
                                # Re-exports count too
                                if isinstance(_xfi_node, _ast_xfi.ImportFrom) and _xfi_node.names:
                                    for _alias in _xfi_node.names:
                                        _exports.add(_alias.asname or _alias.name)
                                elif isinstance(_xfi_node, _ast_xfi.Import):
                                    for _alias in _xfi_node.names:
                                        _exports.add(_alias.asname or _alias.name.split(".")[0])
                    except SyntaxError:
                        pass
                    _module_exports[_xfi_mod] = _exports

                # Now check every `from <local_module> import <Name>` statement
                for _xfi_fname, _xfi_code in files.items():
                    if not _xfi_fname.endswith(".py") or not str(_xfi_code).strip():
                        continue
                    try:
                        _xfi_tree = _ast_xfi.parse(str(_xfi_code))
                    except SyntaxError:
                        continue
                    for _xfi_node in _ast_xfi.walk(_xfi_tree):
                        if not isinstance(_xfi_node, _ast_xfi.ImportFrom):
                            continue
                        _imp_mod = _xfi_node.module
                        if not _imp_mod or _imp_mod not in _module_exports:
                            continue  # External package or not a local file
                        _available = _module_exports[_imp_mod]
                        if not _available:
                            continue  # Empty module — handled by EMPTY_STUB_FILE
                        for _alias in (_xfi_node.names or []):
                            _imp_name = _alias.name
                            if _imp_name == "*":
                                continue  # Can't check star imports
                            if _imp_name not in _available:
                                _lineno = getattr(_xfi_node, "lineno", "?")
                                # Suggest closest match
                                import difflib as _dl_xfi
                                _close = _dl_xfi.get_close_matches(_imp_name, _available, n=1, cutoff=0.5)
                                _suggestion = f" Did you mean '{_close[0]}'?" if _close else ""
                                _errmsg = (
                                    f"CROSS_FILE_IMPORT_MISMATCH: {_xfi_fname}:{_lineno} — "
                                    f"`from {_imp_mod} import {_imp_name}` but {_imp_mod}.py "
                                    f"does not define '{_imp_name}'.{_suggestion} "
                                    f"Available names: {sorted(n for n in _available if not n.startswith('_'))[:15]}"
                                )
                                logger.warning(f"  ⚠️  {_errmsg}")
                                _exec_errors = test_results.get("execution_errors", [])
                                _exec_errors.append(_errmsg)
                                test_results["execution_errors"] = _exec_errors
                                if test_results.get("tests_passed"):
                                    test_results["tests_passed"] = False
                                passed = False

            # ── (L) Missing custom module detector ────────────────────────
            # LLMs sometimes import from a module that was never generated
            # and is not a stdlib/third-party package.  E.g.:
            #   from surprise_metric import compute_surprise
            # where surprise_metric.py was never created.
            if files:
                import ast as _ast_mm
                _generated_modules = {f.rsplit(".", 1)[0] for f in files if f.endswith(".py")}
                _STDLIB_AND_COMMON = {
                    # stdlib
                    "os", "sys", "re", "io", "abc", "gc", "math", "cmath", "time",
                    "random", "copy", "enum", "json", "csv", "logging", "pathlib",
                    "typing", "types", "collections", "functools", "itertools",
                    "operator", "threading", "asyncio", "concurrent", "multiprocessing",
                    "subprocess", "socket", "ssl", "http", "urllib", "email", "html",
                    "xml", "sqlite3", "hashlib", "hmac", "secrets", "base64",
                    "struct", "array", "queue", "heapq", "bisect", "datetime",
                    "calendar", "string", "textwrap", "dataclasses", "warnings",
                    "traceback", "inspect", "importlib", "ast", "dis",
                    "unittest", "doctest", "pdb", "profile", "timeit",
                    "contextlib", "configparser", "argparse", "shutil", "tempfile",
                    "glob", "fnmatch", "zipfile", "tarfile", "gzip", "bz2",
                    "signal", "ctypes", "uuid", "decimal", "fractions", "statistics",
                    "pprint", "textwrap", "locale", "gettext", "unicodedata",
                    "codecs", "mmap", "weakref", "atexit", "sched", "shelve",
                    "dbm", "pickle", "marshal", "copyreg",
                    # very common third-party (also in requirements.txt usually)
                    "torch", "numpy", "pandas", "scipy", "sklearn", "tensorflow",
                    "keras", "matplotlib", "seaborn", "plotly", "PIL", "cv2",
                    "transformers", "datasets", "tokenizers", "accelerate",
                    "requests", "httpx", "aiohttp", "pydantic", "sqlalchemy",
                    "redis", "celery", "click", "typer", "rich", "colorama",
                    "flask", "django", "fastapi", "uvicorn", "gunicorn",
                    "pytest", "hypothesis", "yaml", "toml", "dotenv",
                    "jwt", "bcrypt", "cryptography", "paramiko", "fabric",
                    "openai", "anthropic", "groq", "langchain",
                    "websockets", "websocket", "tqdm", "tabulate",
                }
                # Also add anything in requirements.txt
                _req_modules = set()
                _req_text = files.get("requirements.txt", "")
                if _req_text:
                    for _rl in str(_req_text).splitlines():
                        _rl_s = _rl.strip()
                        if _rl_s and not _rl_s.startswith("#"):
                            _pkg = _re.split(r"[>=<!\[\]]", _rl_s)[0].strip().replace("-", "_").lower()
                            _req_modules.add(_pkg)

                for _mm_fname, _mm_code in files.items():
                    if not _mm_fname.endswith(".py") or not str(_mm_code).strip():
                        continue
                    try:
                        _mm_tree = _ast_mm.parse(str(_mm_code))
                    except SyntaxError:
                        continue
                    for _mm_node in _ast_mm.walk(_mm_tree):
                        if isinstance(_mm_node, _ast_mm.ImportFrom) and _mm_node.module:
                            _mm_mod = _mm_node.module.split(".")[0]
                            if (_mm_mod not in _generated_modules and
                                _mm_mod not in _STDLIB_AND_COMMON and
                                _mm_mod.replace("-", "_").lower() not in _req_modules and
                                not _mm_mod.startswith("_")):
                                _lineno = getattr(_mm_node, "lineno", "?")
                                _errmsg = (
                                    f"MISSING_CUSTOM_MODULE: {_mm_fname}:{_lineno} — "
                                    f"`from {_mm_node.module} import ...` but module "
                                    f"'{_mm_mod}' is not a generated file, not in requirements.txt, "
                                    f"and not a known stdlib/third-party package. "
                                    f"FIX: Either create {_mm_mod}.py or add '{_mm_mod}' to "
                                    f"requirements.txt, or remove this import."
                                )
                                logger.warning(f"  ⚠️  {_errmsg}")
                                _exec_errors = test_results.get("execution_errors", [])
                                _exec_errors.append(_errmsg)
                                test_results["execution_errors"] = _exec_errors
                                if test_results.get("tests_passed"):
                                    test_results["tests_passed"] = False
                                passed = False
                        elif isinstance(_mm_node, _ast_mm.Import):
                            for _alias in (_mm_node.names or []):
                                _mm_mod = _alias.name.split(".")[0]
                                if (_mm_mod not in _generated_modules and
                                    _mm_mod not in _STDLIB_AND_COMMON and
                                    _mm_mod.replace("-", "_").lower() not in _req_modules and
                                    not _mm_mod.startswith("_")):
                                    _lineno = getattr(_mm_node, "lineno", "?")
                                    _errmsg = (
                                        f"MISSING_CUSTOM_MODULE: {_mm_fname}:{_lineno} — "
                                        f"`import {_alias.name}` but module '{_mm_mod}' is not "
                                        f"a generated file, not in requirements.txt, and not a "
                                        f"known package. FIX: Create {_mm_mod}.py or add to "
                                        f"requirements.txt."
                                    )
                                    logger.warning(f"  ⚠️  {_errmsg}")
                                    _exec_errors = test_results.get("execution_errors", [])
                                    _exec_errors.append(_errmsg)
                                    test_results["execution_errors"] = _exec_errors
                                    passed = False

            # ── (M) __main__ guard enforcement ────────────────────────────
            # main.py that runs logic at module level (without
            # `if __name__ == "__main__":`) causes side effects during
            # import tests and makes the code non-reusable.
            if files and "main.py" in files:
                _main_code = str(files["main.py"])
                if _main_code.strip() and "if __name__" not in _main_code:
                    # Check if there's substantial top-level code (not just imports/defs)
                    try:
                        _main_tree = _ast_xfi.parse(_main_code)
                        _toplevel_stmts = 0
                        for _node in _ast_xfi.iter_child_nodes(_main_tree):
                            if isinstance(_node, (_ast_xfi.Expr, _ast_xfi.Assign,
                                                  _ast_xfi.If, _ast_xfi.For,
                                                  _ast_xfi.While, _ast_xfi.Try)):
                                # Check it's not just a docstring
                                if isinstance(_node, _ast_xfi.Expr) and isinstance(_node.value, (_ast_xfi.Constant, _ast_xfi.Str)):
                                    continue
                                _toplevel_stmts += 1
                        if _toplevel_stmts >= 2:
                            _errmsg = (
                                f"MISSING_MAIN_GUARD: main.py has {_toplevel_stmts} executable "
                                f"top-level statements without `if __name__ == '__main__':` guard. "
                                f"This causes side effects when main.py is imported by other modules "
                                f"or test files. FIX: Wrap the entry-point code in "
                                f"`if __name__ == '__main__':` block."
                            )
                            logger.warning(f"  ⚠️  {_errmsg}")
                            _exec_errors = test_results.get("execution_errors", [])
                            _exec_errors.append(_errmsg)
                            test_results["execution_errors"] = _exec_errors
                            # Don't set passed = False — this is a quality issue, not a crash
                    except SyntaxError:
                        pass

            # ── Pip-timeout grace: if the ONLY failure is dependency install
            # timeout but all static analysis passed with high quality, treat
            # as "conditional pass" — code is likely correct, just can't pip
            # install large deps (torch, etc.) in 5 minutes.
            _only_pip_timeout = (
                not passed
                and len(_exec_errors) == 1
                and "timed out" in str(_exec_errors[0]).lower()
                and test_results.get("syntax_valid", False)
                and avg_quality >= 80
            )
            if _only_pip_timeout:
                logger.warning("⚠️ Pip-timeout grace: conditional pass (pip_timeout_grace)")
                # V12 FIX: Don't set passed=True — code was NEVER runtime-tested.
                # Instead, set a grace flag so downstream nodes know this is a
                # timeout-only failure with high static quality.
                test_results["pip_timeout_grace"] = True
                test_results["warnings"] = test_results.get("warnings", []) + [
                    "PIP_TIMEOUT_GRACE: Static analysis passed but runtime tests were NOT executed."
                ]
                # V11 FIX: Only clear the pip-timeout error, preserve any other errors
                test_results["execution_errors"] = [
                    e for e in test_results.get("execution_errors", [])
                    if "timed out" not in str(e).lower()
                ]
                # Conditionally pass — code MIGHT work, but wasn't verified
                passed = True
            
            if passed:
                logger.info("✅ All tests passed!")
            else:
                logger.warning("⚠️  Some tests failed")
                for error in test_results.get("execution_errors", []):
                    logger.error(f"  ❌ {error}")
                if avg_quality < 50:
                    logger.warning(f"  ❌ Quality too low: {avg_quality:.1f}/100 (need ≥50)")
            
            # Log warnings
            for warning in test_results.get("warnings", []):
                logger.warning(f"  ⚠️  {warning}")

            # ── Record errors in codegen error memory ────────────────────
            try:
                from ..utils.codegen_error_memory import get_error_memory as _gem_ct
                _mem = _gem_ct()
                _idea_s = state.get("idea", "")[:120]
                _run_id = state.get("run_id", "unknown")
                _errors_to_record = []
                for _err in test_results.get("execution_errors", []):
                    _err_s = str(_err)
                    # Try to extract bug type from error string
                    _bt = "RUNTIME_ERROR"
                    for _known in ["ATTR_MISMATCH", "API_MISMATCH", "ENCODING_ISSUE",
                                   "SELF_METHOD_MISSING", "UNINITIALIZED_ATTR",
                                   "PLACEHOLDER_INIT", "WRONG_CALL", "MISSING_EXPORT",
                                   "CIRCULAR_IMPORT", "SHAPE_MISMATCH", "TRUNCATED",
                                   "SQLITE_NONDETERMINISTIC", "SHADOW_FILE",
                                   "MISSING_COLORAMA", "CLASS_SCOPE_NAME_ERROR",
                                   "EMPTY_STUB_FILE", "CROSS_FILE_IMPORT_MISMATCH",
                                   "MISSING_CUSTOM_MODULE", "MISSING_MAIN_GUARD",
                                   "GENERATED_TEST_FAILURE",
                                   "ImportError", "ModuleNotFoundError", "AttributeError",
                                   "TypeError", "NameError", "SyntaxError"]:
                        if _known in _err_s:
                            _bt = _known
                            break
                    # Extract filename if present
                    _ef = "unknown"
                    import re as _re_mem
                    _fm = _re_mem.search(r'([\w_]+\.py)', _err_s)
                    if _fm:
                        _ef = _fm.group(1)
                    _errors_to_record.append({
                        "run_id": _run_id,
                        "idea_summary": _idea_s,
                        "phase": "static_check",
                        "bug_type": _bt,
                        "file": _ef,
                        "description": _err_s[:300],
                        "fixed": False,
                    })
                if _errors_to_record:
                    _mem.record_batch(_errors_to_record)
                    logger.info(f"  💾 Recorded {len(_errors_to_record)} errors to codegen memory")
            except Exception as _me:
                logger.debug(f"  Could not record to codegen memory: {_me}")

            # ── SOTA: LLM-as-Judge Output Validation ─────────────────────────
            # Inspired by MT-Bench (Zheng et al. 2023) — evaluate whether the
            # program's RUNTIME OUTPUT semantically matches the user's intent.
            # This catches "compiles fine, tests pass, but does nothing useful"
            # scenarios that fooled the validator in Runs #1-17.
            #
            # Only runs when:
            #   (a) tests passed (no point judging output of broken code)
            #   (b) entry_point_stdout was captured by CodeExecutor
            #   (c) idea is available for comparison
            if passed and state.get("idea"):
                _ep_stdout = test_results.get("entry_point_stdout", "")
                _ep_exit   = test_results.get("entry_point_exit_code", None)
                _idea_text = state.get("idea", "")

                # Only judge if we have actual output or a suspicious silence
                _should_judge = bool(_ep_stdout) or _ep_exit == 0
                if _should_judge:
                    try:
                        _judge_llm = get_fallback_llm("fast")
                        _judge_prompt = (
                            "You are a code output validator. A user asked for this:\n"
                            f"IDEA: {_idea_text}\n\n"
                            f"The generated main.py ran and produced this output:\n"
                            f"```\n{(_ep_stdout or '(no output — program was silent)')[:2000]}\n```\n\n"
                            "Score the output 1-10:\n"
                            "- 1-3: Output is empty, just an error, or completely unrelated to the idea\n"
                            "- 4-6: Output shows partial functionality but missing key features\n"
                            "- 7-10: Output demonstrates the core functionality the user asked for\n\n"
                            "Return ONLY valid JSON (no markdown fences):\n"
                            '{"output_score": 1-10, "assessment": "one sentence", '
                            '"is_functional": true/false, "missing": ["what is missing if any"]}'
                        )
                        _judge_resp = await _judge_llm.ainvoke([HumanMessage(content=_judge_prompt)])
                        import json as _jsj
                        _jr = _judge_resp.content.strip()
                        _jr = _re.sub(r"^```[a-z]*\n?", "", _jr)
                        _jr = _re.sub(r"\n?```$", "", _jr.strip())
                        if "<think>" in _jr:
                            _te = _jr.rfind("</think>")
                            if _te != -1:
                                _jr = _jr[_te + len("</think>"):].strip()
                        _judge_result = _jsj.loads(_jr)

                        _out_score = float(_judge_result.get("output_score", 5))
                        _is_func   = _judge_result.get("is_functional", True)
                        _assess    = _judge_result.get("assessment", "")
                        _missing   = _judge_result.get("missing", [])

                        test_results["output_validation"] = _judge_result
                        logger.info(f"  🧑‍⚖️ LLM-as-Judge: output_score={_out_score}/10, functional={_is_func}")
                        logger.info(f"     Assessment: {_assess}")

                        # If output score is very low, add it as an error so the fix loop
                        # can address it (e.g., silent main.py, wrong output format)
                        if _out_score <= 3 and not _is_func:
                            _ov_errors = test_results.get("execution_errors", [])
                            _ov_msg = (
                                f"OUTPUT_VALIDATION: main.py output scored {_out_score}/10. "
                                f"Assessment: {_assess}. "
                                f"Missing: {', '.join(_missing[:3]) if _missing else 'N/A'}"
                            )
                            _ov_errors.append(_ov_msg)
                            test_results["execution_errors"] = _ov_errors
                            passed = False  # Fail the test — output is not functional
                            logger.warning(f"  ❌ Output validation FAILED: {_ov_msg}")

                    except Exception as _je:
                        logger.debug(f"  LLM-as-Judge skipped (error: {_je})")
            # ── End LLM-as-Judge ─────────────────────────────────────────────

            # ── IMPROVEMENT #4: Docker Sandbox Verification ──────────────────
            # If Docker is available, re-run main.py inside a container for
            # extra safety verification. This catches issues that only appear
            # in a clean environment (e.g., missing system deps, implicit globals).
            try:
                try:
                    from ..utils.docker_executor import DockerSandboxExecutor, docker_is_available
                except ImportError:
                    from utils.docker_executor import DockerSandboxExecutor, docker_is_available  # type: ignore
                from rich.console import Console as _DockerConsole
                _d_console = _DockerConsole()
                
                if docker_is_available() and files and "main.py" in files:
                    logger.info("  🐳 Running Docker sandbox verification...")
                    _d_console.print("  [cyan]🐳 Docker sandbox verification...[/cyan]")
                    _docker_exec = DockerSandboxExecutor(test_dir, timeout=45)
                    _docker_result = _docker_exec.run_sandboxed("main.py", timeout=45, install_deps=True)
                    
                    test_results["docker_sandbox"] = {
                        "used": True,
                        "returncode": _docker_result.returncode,
                        "timed_out": _docker_result.timed_out,
                        "execution_time_ms": _docker_result.execution_time_ms,
                        "stdout_preview": _docker_result.stdout[:500] if _docker_result.stdout else "",
                    }
                    
                    if _docker_result.returncode == 0:
                        logger.info(f"  🐳 Docker sandbox: PASSED ({_docker_result.execution_time_ms}ms)")
                        _d_console.print(f"  [green]🐳 Docker sandbox: PASSED[/green]")
                    elif _docker_result.timed_out:
                        logger.info(f"  🐳 Docker sandbox: timed out (may be server/long-running)")
                    else:
                        _docker_err = _docker_result.stderr[:300] if _docker_result.stderr else ""
                        logger.warning(f"  🐳 Docker sandbox: FAILED (exit {_docker_result.returncode})")
                        if _docker_err:
                            logger.warning(f"    Docker stderr: {_docker_err}")
                        # Add as warning, not error (may be Docker-specific issue)
                        _dw = test_results.get("warnings", [])
                        _dw.append(f"Docker sandbox failed (exit {_docker_result.returncode}): {_docker_err[:200]}")
                        test_results["warnings"] = _dw
                else:
                    test_results["docker_sandbox"] = {"used": False, "reason": "Docker not available or no main.py"}
            except Exception as _de:
                logger.debug(f"  Docker sandbox skipped: {_de}")
                test_results["docker_sandbox"] = {"used": False, "reason": str(_de)[:100]}
            # ── End Docker Sandbox ───────────────────────────────────────────

            return {
                "current_stage": "testing_complete",
                "test_results": test_results,
                "tests_passed": passed,
                "code_quality": avg_quality
            }
    
    except Exception as e:
        logger.error(f"Code testing failed: {e}")
        return {
            "current_stage": "testing_failed",
            "errors": [f"Testing failed: {str(e)}"],
            "test_results": {
                "error": str(e),
                "execution_errors": [f"Testing infrastructure error: {str(e)}"],
            },
            "tests_passed": False
        }


# ============================================
# Node 8.3: Feature Verification (Runtime Sandbox)
# ============================================

async def feature_verification_node(state: AutoGITState) -> Dict[str, Any]:
    """
    Node 8.3: Runtime Feature Verification in Sandbox

    Unlike syntax/import checks or LLM-as-Judge (which reads code and guesses),
    this node ACTUALLY RUNS each feature in an isolated subprocess and checks
    whether it produces the expected behaviour.

    How it works:
    1. Takes the generated code files + structured requirements (key_features)
    2. Uses LLM to generate a feature_tests.py with one test function per feature
    3. Runs feature_tests.py in the project's venv via subprocess
    4. Parses structured JSON output to get per-feature PASS/FAIL/ERROR
    5. Injects failures into test_results so the fix loop can address them

    This catches the #1 class of bugs: "code generates, imports fine, but features
    don't actually work" (wrong dict keys, missing methods, broken wiring, etc.)
    """
    logger.info("🔍 Feature Verification Node — runtime testing each feature")

    from rich.console import Console as _RCFV
    from rich.table import Table as _FVTab
    _console = _RCFV()
    _console.print("\n[bold cyan]🔍 Feature Verification — testing each feature in sandbox...[/bold cyan]")

    try:
        from pathlib import Path
        from ..utils.feature_verifier import FeatureVerifier, create_feature_error_messages
        import tempfile
        import shutil

        generated_code = state.get("generated_code", {})
        files = _flatten_file_keys(
            generated_code.get("files", {}) if isinstance(generated_code, dict) else {},
            "feature_verification_input"
        )
        test_results = state.get("test_results", {}) if isinstance(state.get("test_results"), dict) else {}
        tests_passed = state.get("tests_passed", False)
        idea = state.get("idea", "")
        requirements = state.get("requirements") or {}

        # Only run feature verification if:
        # (a) We have files to test
        # (b) Basic tests passed (syntax, imports OK) — no point testing features of broken code
        # (c) We have requirements/idea to know WHAT to test
        if not files:
            logger.info("  No files — skipping feature verification")
            return {"current_stage": "feature_verification_skipped"}

        if not tests_passed:
            logger.info("  Basic tests failed — skipping feature verification (fix basic issues first)")
            _console.print("  [dim yellow]Skipping — basic tests haven't passed yet[/dim yellow]")
            return {"current_stage": "feature_verification_skipped"}

        if not idea and not requirements:
            logger.info("  No idea/requirements — skipping feature verification")
            return {"current_stage": "feature_verification_skipped"}

        # If requirements doesn't have key_features, build a minimal one from the idea
        if not requirements.get("key_features"):
            requirements = dict(requirements)
            requirements["key_features"] = [idea[:200]]  # Use the idea itself as the feature

        # Create or reuse a project-specific venv — REUSE venv from code_testing_node
        # instead of creating a duplicate (saves 2-6 minutes per run)
        with tempfile.TemporaryDirectory() as temp_dir:
            test_dir = Path(temp_dir) / "feature_test_project"
            test_dir.mkdir(parents=True, exist_ok=True)

            # Write all project files
            import os as _os_fv
            for filename, content in files.items():
                flat_name = _os_fv.path.basename(filename) if ('/' in filename or '\\' in filename) else filename
                fpath = test_dir / flat_name
                fpath.parent.mkdir(parents=True, exist_ok=True)
                fpath.write_text(content or "", encoding="utf-8")

            # Create venv with --system-site-packages so stdlib + already-installed
            # packages from the host are available without re-installing
            import subprocess as _sp_fv
            import sys as _sys_fv

            python_exe = _sys_fv.executable
            venv_dir = test_dir / ".venv"
            try:
                _sp_fv.run(
                    [python_exe, "-m", "venv", "--system-site-packages", str(venv_dir)],
                    check=True, capture_output=True, timeout=60
                )
                if _sys_fv.platform == "win32":
                    venv_python = venv_dir / "Scripts" / "python.exe"
                else:
                    venv_python = venv_dir / "bin" / "python"
                logger.info("  Created lightweight venv (system-site-packages) for feature testing")
            except Exception as e:
                logger.warning(f"  Venv creation failed ({e}) — using system Python")
                venv_python = Path(python_exe)

            # Only install requirements if the base doesn't have them
            # (quick check: try importing the first requirement)
            req_file = test_dir / "requirements.txt"
            if req_file.exists() and venv_python != Path(python_exe):
                try:
                    _sp_fv.run(
                        [str(venv_python), "-m", "pip", "install",
                         "--prefer-binary", "--no-build-isolation",
                         "-r", str(req_file), "-q"],
                        capture_output=True, timeout=120, check=False
                    )
                    logger.info("  Installed dependencies for feature testing")
                except Exception as e:
                    logger.warning(f"  Dep install failed ({e}) — continuing anyway")

            # Run feature verification
            verifier = FeatureVerifier(timeout=90)
            report = await verifier.verify_features(
                files=files,
                requirements=requirements,
                idea=idea,
                project_dir=test_dir,
                python_exe=venv_python,
                get_llm_func=get_fallback_llm,
            )

        # Display results in a nice table
        summary = report.get("summary", {})
        features = report.get("features", [])

        if features:
            table = _FVTab(title="Feature Verification Report", show_lines=True)
            table.add_column("Status", width=4, justify="center")
            table.add_column("Feature", min_width=25)
            table.add_column("Importance", width=12)
            table.add_column("Details", min_width=30)

            for feat in features:
                status = feat.get("status", "?")
                name = feat.get("feature", "?")
                importance = feat.get("importance", "?")
                error = feat.get("error", "")
                output = feat.get("output", "")

                if status == "PASS":
                    icon = "✅"
                    detail = (output[:60] + "...") if len(output) > 60 else output
                elif status == "FAIL":
                    icon = "❌"
                    detail = error[:80]
                else:
                    icon = "💥"
                    detail = error[:80]

                table.add_row(icon, name, importance, detail or "-")

            _console.print(table)

        total = summary.get("total", 0)
        passed_count = summary.get("passed", 0)
        failed_count = summary.get("failed", 0)
        error_count = summary.get("errors", 0)
        pass_rate = summary.get("pass_rate", 0)

        color = "green" if pass_rate >= 80 else ("yellow" if pass_rate >= 50 else "red")
        _console.print(
            f"\n  [bold]Features:[/bold] [{color}]{passed_count}/{total} passed ({pass_rate:.0f}%)[/{color}]"
            f"  |  ❌ {failed_count} failed  |  💥 {error_count} errors"
        )

        # Inject feature failures into test_results as execution_errors
        # so the strategy_reasoner + code_fixing loop can address them
        feature_errors = create_feature_error_messages(report)
        updated_tests = dict(test_results)
        updated_tests["feature_verification"] = report

        if feature_errors:
            existing_errors = updated_tests.get("execution_errors", [])
            existing_errors.extend(feature_errors)
            updated_tests["execution_errors"] = existing_errors

            # If critical features failed, mark tests as not passed
            critical_failures = [
                f for f in features
                if f.get("status") in ("FAIL", "ERROR")
                and f.get("importance") == "critical"
            ]
            if critical_failures:
                tests_passed = False
                _console.print(
                    f"\n  [red]❌ {len(critical_failures)} CRITICAL features failed — "
                    f"routing to fix loop[/red]"
                )
            elif pass_rate < 50:
                tests_passed = False
                _console.print(
                    f"\n  [red]❌ Less than 50% features working — routing to fix loop[/red]"
                )
            else:
                _console.print(
                    f"\n  [yellow]⚠️  Some features failed but core functionality works[/yellow]"
                )
        else:
            _console.print(f"\n  [green]✅ All features verified working![/green]")

        # Save feature_tests.py into the generated code for reference
        test_script = report.get("test_script", "")
        if test_script:
            updated_code = dict(generated_code)
            updated_files = dict(files)
            updated_files["feature_tests.py"] = test_script
            updated_code["files"] = updated_files
        else:
            updated_code = generated_code

        logger.info(f"  Feature verification: {passed_count}/{total} passed ({pass_rate:.0f}%)")

        return {
            "current_stage": "feature_verification_complete",
            "test_results": updated_tests,
            "tests_passed": tests_passed,
            "generated_code": updated_code,
        }

    except Exception as e:
        logger.error(f"Feature verification failed: {e}")
        _console.print(f"  [dim yellow]Feature verification failed ({e}) — continuing[/dim yellow]")
        return {
            "current_stage": "feature_verification_failed",
            "errors": [f"Feature verification crashed: {str(e)}"],
        }


# ============================================
# Node 8.4: Strategy Reasoner (Reasoning-in-the-Loop)
# ============================================

async def strategy_reasoner_node(state: AutoGITState) -> Dict[str, Any]:
    """
    Node 8.4: Strategic reasoning about WHY code failed and WHAT to do differently.

    This is the core "reasoning-in-the-loop" capability. Instead of mechanically
    injecting errors and asking the LLM to patch them (which produces the same
    bad code), this node:

    1. DIAGNOSES the root cause (not just symptoms) of each failure
    2. CLASSIFIES the failure type (architecture flaw, missing logic, wrong API,
       incomplete implementation, dependency issue, etc.)
    3. GENERATES a strategic fix plan with specific per-file instructions
    4. DECIDES which specific parts of which files to patch (NEVER regenerates from scratch)
    5. TRACKS what strategies were already tried and failed (no repeating)

    The output is a structured "fix_strategy" dict that code_fixing_node uses
    instead of blindly asking "fix this error".
    """
    logger.info("🧠 Strategy Reasoner Node — analyzing failure root causes")

    from rich.console import Console as _RCSR
    _console = _RCSR()
    _console.print("\n[bold magenta]🧠 Strategy Reasoner — thinking about WHY code failed...[/bold magenta]")

    try:
        test_results = state.get("test_results", {})
        generated_code = state.get("generated_code", {})
        files: Dict[str, str] = _flatten_file_keys(
            generated_code.get("files", {}) if isinstance(generated_code, dict) else {},
            "strategy_reasoner_input"
        )
        fix_attempts = state.get("fix_attempts", 0)
        idea = state.get("idea", "")
        selected_problem = state.get("selected_problem", "") or ""
        solution = state.get("final_solution") or {}

        execution_errors = test_results.get("execution_errors", []) if isinstance(test_results, dict) else []
        self_eval_fixes = test_results.get("self_eval_fixes", "") if isinstance(test_results, dict) else ""
        prev_strategies = state.get("_prev_fix_strategies", [])

        if not execution_errors and not self_eval_fixes:
            logger.info("  No errors to reason about — passing through")
            return {"current_stage": "strategy_pass_through"}

        # ── Load lessons from past runs for informed strategy (loaded ONCE) ──
        _strategy_lessons = ""
        try:
            from ..utils.codegen_error_memory import get_error_memory as _gem_sr
            _strategy_lessons = _gem_sr().get_top_lessons(n=10)
            if _strategy_lessons:
                logger.info(f"  📚 Loaded {_strategy_lessons.count(chr(10))} lessons for strategy reasoning")
        except Exception:
            pass

        # Build file overview for the reasoner
        file_overview = []
        for fname, fcode in files.items():
            if not fname.endswith(".py"):
                continue
            lines = fcode.splitlines() if isinstance(fcode, str) else []
            real_lines = [l for l in lines if l.strip() and not l.strip().startswith("#")]
            has_main_guard = "if __name__" in fcode if isinstance(fcode, str) else False
            has_stubs = any(p in (fcode or "") for p in (
                "# TODO", "raise NotImplementedError", "pass  #",
                "# Implement", "# implement", "# your code here",
            ))
            file_overview.append(
                f"  {fname}: {len(lines)} lines ({len(real_lines)} real), "
                f"main_guard={'yes' if has_main_guard else 'NO'}, "
                f"stubs={'YES' if has_stubs else 'no'}"
            )

        error_text = "\n".join(f"  - {e}" for e in execution_errors)
        file_text = "\n".join(file_overview)
        prev_text = "\n".join(f"  - Attempt {i+1}: {s}" for i, s in enumerate(prev_strategies[-3:]))

        llm = get_fallback_llm("reasoning")

        reasoning_prompt = (
            "You are a senior software architect debugging a failed code generation pipeline.\n\n"
            "Your job is NOT to write code. Your job is to THINK STRATEGICALLY about:\n"
            "1. What is the ROOT CAUSE of each failure (not just the symptom)?\n"
            "2. What CATEGORY of bug is this? (architecture_flaw, incomplete_impl, wrong_api, "
            "shadow_file, circular_import, missing_dep, stub_code, truncated, wrong_algorithm, "
            "attr_mismatch, encoding_issue, cross_file_import_mismatch, missing_custom_module)\n"
            "3. What is the BEST STRATEGY to fix it? (patch_file, fix_imports, fix_deps, add_missing_module)\n"
            "   IMPORTANT: NEVER regenerate entire files from scratch. Always do TARGETED PATCHES \n"
            "   that fix only the broken parts while preserving working code.\n"
            "4. What SPECIFIC INSTRUCTIONS should the code fixer follow for each file?\n\n"
            "NOTE: The following error types have DETERMINISTIC AUTO-FIXERS that run before\n"
            "your strategy reaches the LLM fixer. Focus your reasoning on errors NOT in this list:\n"
            "  - ENCODING_ISSUE (emoji/non-ASCII → ASCII replacement)\n"
            "  - shadow_file (auto-deleted: torch.py, numpy.py, etc.)\n"
            "  - Relative imports (from .X → from X)\n"
            "  - Missing stdlib imports (auto-added: os, sys, json, etc.)\n"
            "  - CLASS_SCOPE_NAME_ERROR (forward ref quoting)\n"
            "  - CROSS_FILE_IMPORT_MISMATCH (auto-renamed to closest match)\n"
            "  - EMPTY_STUB_FILE (auto-generates minimal stubs)\n"
            "  - MISSING_MAIN_GUARD (auto-wraps in if __name__ == '__main__')\n"
            "  - MISSING_COLORAMA (auto-adds colorama.init())\n"
            "  - SQLite GENERATED columns (auto-removed)\n"
            "If ALL errors are in the above list, confidence should be HIGH since fixers handle them.\n\n"
            f"PROJECT IDEA: {idea}\n"
            f"APPROACH: {solution.get('approach_name', 'N/A')}\n\n"
            f"FILES GENERATED:\n{file_text}\n\n"
            f"ERRORS:\n{error_text}\n\n"
        )

        # Inject lessons from past runs so strategy doesn't repeat known mistakes
        if _strategy_lessons:
            reasoning_prompt += f"LESSONS FROM PAST PIPELINE RUNS (avoid these mistakes):\n{_strategy_lessons}\n\n"

        if self_eval_fixes:
            reasoning_prompt += f"SELF-EVAL FEEDBACK:\n{self_eval_fixes}\n\n"

        if prev_text:
            reasoning_prompt += (
                f"PREVIOUSLY TRIED STRATEGIES (DO NOT REPEAT THESE):\n{prev_text}\n\n"
            )

        # Include code of each file so the reasoner can see the actual bugs.
        # For very large files (>300 lines), show first 200 + last 50 to save tokens.
        code_preview = []
        for fname, fcode in files.items():
            if not fname.endswith(".py"):
                continue
            lines = (fcode or "").splitlines()
            if len(lines) > 300:
                preview_lines = lines[:200] + [f"  ... ({len(lines) - 250} lines omitted) ..."] + lines[-50:]
            else:
                preview_lines = lines
            code_preview.append(f"=== {fname} ({len(lines)} lines) ===\n" + "\n".join(preview_lines))
        reasoning_prompt += "CODE:\n" + "\n\n".join(code_preview) + "\n\n"

        reasoning_prompt += (
            "Return ONLY valid JSON (no markdown fences):\n"
            "{\n"
            '  "root_cause_analysis": "One paragraph explaining the fundamental problem",\n'
            '  "failure_category": "architecture_flaw|incomplete_impl|wrong_api|shadow_file|'
            'circular_import|missing_dep|stub_code|truncated|wrong_algorithm|attr_mismatch|'
            'encoding_issue|sqlite_nondeterministic|missing_import|class_scope_name_error|empty_stub_file",\n'
            '  "overall_strategy": "patch_files|fix_imports|fix_deps",\n'
            '  "confidence": 0.0-1.0,\n'
            '  "file_instructions": {\n'
            '    "filename.py": {\n'
            '      "action": "patch|regenerate|delete|create",\n'
            '      "reason": "why this file needs this action",\n'
            '      "specific_instructions": "detailed fix instructions for the code fixer LLM"\n'
            "    }\n"
            "  },\n"
            '  "strategy_summary": "One-line summary of the fix plan"\n'
            "}\n"
        )

        messages = [HumanMessage(content=reasoning_prompt)]
        response = await llm.ainvoke(messages)

        import json as _jsr, re as _resr
        raw = response.content.strip()
        raw = _resr.sub(r"^```[a-z]*\n?", "", raw)
        raw = _resr.sub(r"\n?```$", "", raw.strip())
        # Handle thinking models that prefix with <think>...</think>
        if "<think>" in raw:
            think_end = raw.rfind("</think>")
            if think_end != -1:
                raw = raw[think_end + len("</think>"):].strip()
        strategy = _jsr.loads(raw)

        root_cause = strategy.get("root_cause_analysis", "Unknown")
        category = strategy.get("failure_category", "unknown")
        overall = strategy.get("overall_strategy", "patch_files")
        confidence = strategy.get("confidence", 0.5)
        file_instructions = strategy.get("file_instructions", {})
        summary = strategy.get("strategy_summary", "")

        # ── PROGRAMMATIC STRATEGY DEDUP ───────────────────────────────────
        # Hash the strategy summary + file instructions to prevent the LLM
        # from repeating the exact same approach.  Prompt-only "don't repeat"
        # was unreliable — LLMs would rephrase the same strategy.
        import hashlib as _hashlib_sd
        _strategy_key_parts = [summary.lower().strip()]
        for _fi_name in sorted(file_instructions.keys()):
            _fi = file_instructions[_fi_name]
            if isinstance(_fi, dict):
                _strategy_key_parts.append(f"{_fi_name}:{_fi.get('action', '')}:{_fi.get('specific_instructions', '')[:100]}")
        _strategy_hash = _hashlib_sd.md5("|".join(_strategy_key_parts).encode()).hexdigest()[:12]

        _prev_hashes = state.get("_prev_error_hashes", [])
        if _strategy_hash in _prev_hashes:
            logger.warning(f"  ⚠️  Strategy dedup: hash {_strategy_hash} already tried — escalating")
            _console.print(f"  [yellow]⚠️  Same strategy detected (hash {_strategy_hash}) — escalating to different approach[/yellow]")
            # Force a different approach by changing the strategy
            strategy["overall_strategy"] = "regenerate_targeted"
            strategy["strategy_summary"] = f"[ESCALATED from duplicate] {summary}"
            for _fi_name in file_instructions:
                if isinstance(file_instructions[_fi_name], dict):
                    file_instructions[_fi_name]["action"] = "regenerate"
                    file_instructions[_fi_name]["specific_instructions"] = (
                        "PREVIOUS FIX STRATEGY WAS IDENTICAL TO A PRIOR ATTEMPT. "
                        "You MUST take a FUNDAMENTALLY DIFFERENT approach. "
                        "Consider: rewriting the class hierarchy, changing the algorithm, "
                        "simplifying the implementation, or removing the problematic feature.\n\n"
                        + file_instructions[_fi_name].get("specific_instructions", "")
                    )
            _strategy_hash = _strategy_hash + "_esc"  # new hash for escalated version

        # Track this strategy's hash for future dedup
        _updated_hashes = list(_prev_hashes) + [_strategy_hash]

        # ── SOTA: Retrieval-Augmented Debugging (RAD) ─────────────────────
        # Inspired by SWE-Agent's retrieval loop — when the strategy reasoner
        # identifies a `wrong_api` or `missing_dep` bug, we do a targeted
        # web search to find the CORRECT API/usage before passing to the fixer.
        # This prevents the fix loop from blindly guessing API signatures.
        if category in ("wrong_api", "missing_dep", "wrong_algorithm"):
            try:
                from ..utils.web_search import MultiEngineSearcher
                _rad_searcher = MultiEngineSearcher(max_results=3, timeout=15)

                # Build targeted search queries from error context
                _rad_queries = []
                for _fi_name, _fi_instr in file_instructions.items():
                    _fi_reason = (_fi_instr.get("reason", "") if isinstance(_fi_instr, dict) else "")
                    if _fi_reason:
                        # Extract the API name or module causing the issue
                        _api_match = _re.search(r"(?:method|function|class|module|API)\s+[`'\"]?(\w+[\.\w]*)[`'\"]?", _fi_reason, _re.I)
                        if _api_match:
                            _rad_queries.append(f"python {_api_match.group(1)} correct usage example")
                        else:
                            _rad_queries.append(f"python {_fi_reason[:60]} fix example")

                if not _rad_queries:
                    # Fallback: search based on the root cause
                    _rad_queries.append(f"python {root_cause[:80]} solution")

                _rad_context_parts = []
                for _rq in _rad_queries[:2]:  # Max 2 searches to stay fast
                    _rad_results = _rad_searcher.search(_rq)
                    # Flatten all engine results
                    for _eng_name, _eng_results in _rad_results.items():
                        if isinstance(_eng_results, list):
                            for _rr in _eng_results[:2]:
                                _title = _rr.get("title", "")
                                _content = _rr.get("content", "")[:300]
                                if _title or _content:
                                    _rad_context_parts.append(f"[{_title}] {_content}")

                if _rad_context_parts:
                    _rad_context = "\n".join(_rad_context_parts[:4])
                    # Inject web search results into file instructions as extra context
                    for _fi_name in file_instructions:
                        if isinstance(file_instructions[_fi_name], dict):
                            _existing = file_instructions[_fi_name].get("specific_instructions", "")
                            file_instructions[_fi_name]["specific_instructions"] = (
                                _existing + f"\n\nWEB SEARCH RESULTS (correct API usage):\n{_rad_context}"
                            )
                    strategy["file_instructions"] = file_instructions
                    _console.print(f"  [cyan]🔍 RAD: Found {len(_rad_context_parts)} web results for API fix guidance[/cyan]")
                    logger.info(f"  RAD: Injected {len(_rad_context_parts)} web search results into fix instructions")

            except Exception as _rad_err:
                logger.debug(f"  RAD web search failed (non-critical): {_rad_err}")
        # ── End RAD ──────────────────────────────────────────────────────────

        # Display reasoning results
        conf_color = "green" if confidence >= 0.7 else ("yellow" if confidence >= 0.4 else "red")
        _console.print(f"\n  [bold]Root cause:[/bold] {root_cause[:200]}")
        _console.print(f"  [bold]Category:[/bold] {category}")
        _console.print(f"  [bold]Strategy:[/bold] {overall} (confidence [{conf_color}]{confidence:.0%}[/{conf_color}])")
        _console.print(f"  [bold]Plan:[/bold] {summary}")

        if file_instructions:
            for fname, instr in file_instructions.items():
                action = instr.get("action", "patch")
                reason = instr.get("reason", "")[:80]
                _console.print(f"    [{fname}] → {action}: {reason}")

        logger.info(f"  Strategy: {overall} | Category: {category} | Confidence: {confidence:.0%}")
        logger.info(f"  Summary: {summary}")

        # Track strategy history to avoid repeating
        updated_strategies = list(prev_strategies) + [summary]

        # Update test_results with strategy for code_fixing_node to use
        updated_tests = dict(test_results) if isinstance(test_results, dict) else {}
        updated_tests["fix_strategy"] = strategy

        return {
            "test_results": updated_tests,
            "_prev_fix_strategies": updated_strategies,
            "_prev_error_hashes": _updated_hashes,
            "current_stage": "strategy_ready",
        }

    except Exception as e:
        logger.warning(f"Strategy reasoner failed ({e}) — proceeding with default patch strategy")
        _console.print(f"  [dim yellow]Reasoning failed ({e}) — falling back to default patch strategy[/dim yellow]")
        # V17 FIX: Provide a default strategy so code_fixing has *some* guidance
        _fallback_strategy = {
            "overall_strategy": "patch_files",
            "confidence": 0.3,
            "file_instructions": {},
            "strategy_summary": f"Strategy reasoning failed ({type(e).__name__}) — using default patch approach",
        }
        _fb_tests = dict(test_results) if isinstance(test_results, dict) else {}
        _fb_tests["fix_strategy"] = _fallback_strategy
        return {"test_results": _fb_tests, "current_stage": "strategy_fallback"}


# ============================================
# Node 8.5: Code Fixing (Self-Healing)
# ============================================

async def code_fixing_node(state: AutoGITState) -> Dict[str, Any]:
    """
    Node 8.5: Automatically fix code issues based on test failures
    
    Analyzes test errors and generates fixes for:
    - Syntax errors
    - Import errors
    - Missing dependencies
    - Runtime errors
    """
    logger.info("🔧 Code Fixing Node: Auto-healing code issues")
    
    console = Console()
    console.print("\n[yellow]🔧 Analyzing test failures and generating fixes...[/yellow]")
    
    try:
        test_results = state.get("test_results", {})
        fix_attempts = state.get("fix_attempts", 0)
        
        # CRITICAL: Check max attempts with reduced limit to prevent OOM
        max_fix_attempts = state.get("max_fix_attempts", 3)  # 3 max — allow more fix iterations
        if fix_attempts >= max_fix_attempts:
            logger.error(f"Max fix attempts ({fix_attempts}) reached. Giving up.")
            console.print(f"\n[red]❌ Max fix attempts reached. Cannot auto-fix code.[/red]\n")
            return {
                "current_stage": "fixing_failed",
                "fix_attempts": fix_attempts,
                "errors": [f"Max fix attempts ({fix_attempts}) reached"],
                "tests_passed": False  # Ensure we don't loop back
            }
        
        # Get error details
        execution_errors = test_results.get("execution_errors", [])
        _original_errors = list(execution_errors)  # snapshot before deterministic fixers remove items
        warnings = test_results.get("warnings", [])

        # CRITICAL: If no errors, mark as complete to prevent loop
        if not execution_errors:
            logger.info("No errors to fix")
            return {
                "current_stage": "no_errors_to_fix",
                "fix_attempts": fix_attempts + 1,  # ALWAYS increment to prevent infinite loop
                "tests_passed": state.get("tests_passed", False),  # Don't override — keep what testing said
            }

        # ── Fast path: pip-install-only errors ─────────────────────────────
        # If every error is a pip install failure (bad package pin, wrong version,
        # python version mismatch, etc.) we can fix requirements.txt WITHOUT
        # calling an LLM — which avoids the 5-20 min Groq rate-limit hang.
        PIP_ERROR_KEYWORDS = (
            "failed to install dependencies",
            "no matching distribution",
            "could not find a version",
            "invalid metadata",
            "requires-python",
            "pytorch-lightning",
            "pip<",
            "error: no matching",
            "error: could not find",
            "invalid requirement",          # e.g. '_bisect' stdlib internal
            "expected package name at",     # pip: Expected package name at the start
            "expected package name",
            "dependency specifier",
            "expected semicolon",           # e.g. 'torch schedulers' multi-word
            "no version specifier",
        )

        def _is_pip_only_error(errors):
            return errors and all(
                any(kw in str(e).lower() for kw in PIP_ERROR_KEYWORDS)
                for e in errors
            )

        generated_code_state = state.get("generated_code", {})
        files_for_fix = _flatten_file_keys(generated_code_state.get("files", {}), "code_fixing_input")

        if _is_pip_only_error(execution_errors):
            logger.info("  ⚡ Pip-only errors detected — fixing requirements.txt without LLM")
            console.print("[cyan]  ⚡ Dependency pinning issue — auto-fixing requirements.txt...[/cyan]")

            py_srcs = {k: v for k, v in files_for_fix.items() if k.endswith(".py")}
            req_text = files_for_fix.get("requirements.txt", "")
            raw_lines = len([l for l in req_text.splitlines() if l.strip() and not l.startswith("#")])

            # Full clean: strip stdlib internals + filter to actual imports + fix bad pins
            new_req_text = _clean_requirements_txt(req_text, py_srcs)
            # Extra bad-pin fixes
            out = []
            for line in new_req_text.splitlines():
                s = line.strip()
                if _re.match(r"pytorch.lightning==1\.", s, _re.I):
                    out.append("lightning>=2.3")
                    logger.info(f"    Fixed: {s} → lightning>=2.3")
                elif "torch" in s.lower() and ".*" in s:
                    out.append(_re.sub(r">=(\d+\.\d+)\.\*", r">=\1", s))
                else:
                    out.append(line)
            new_req_text = "\n".join(out)

            clean_lines = len([l for l in new_req_text.splitlines() if l.strip() and not l.startswith("#")])
            logger.info(f"  ✅ requirements.txt: {raw_lines} → {clean_lines} packages (no LLM needed)")
            console.print(f"  [green]✓[/green] requirements.txt: {raw_lines} → {clean_lines} packages")

            updated_files = dict(files_for_fix)
            updated_files["requirements.txt"] = new_req_text
            return {
                "current_stage": "fixes_applied",
                "fix_attempts": fix_attempts + 1,
                "tests_passed": False,  # V5 FIX: Must re-test — deps were cleaned but code not retested
                "generated_code": {"files": _flatten_file_keys(updated_files, "code_fixing_pip")},
            }
        # ── End fast path ───────────────────────────────────────────────────

        max_display = state.get('max_fix_attempts', 3)
        console.print(f"\n[cyan]Found {len(execution_errors)} errors. Attempt {fix_attempts + 1}/{max_display}[/cyan]")

        # ── Strategy-aware fixing ─────────────────────────────────────────────
        # If strategy_reasoner_node ran first, use its guidance.
        fix_strategy = test_results.get("fix_strategy") if isinstance(test_results, dict) else None
        strategy_file_instructions = {}
        use_powerful_model = False
        if fix_strategy and isinstance(fix_strategy, dict):
            strategy_file_instructions = fix_strategy.get("file_instructions", {})
            overall_strategy = fix_strategy.get("overall_strategy", "patch_files")
            category = fix_strategy.get("failure_category", "unknown")
            console.print(f"  [magenta]🧠 Using strategy: {overall_strategy} (category: {category})[/magenta]")
            # For architecture flaws or incomplete implementations, use a more powerful model
            if category in ("architecture_flaw", "incomplete_impl", "wrong_algorithm"):
                use_powerful_model = True
            # NEVER regenerate_all — force targeted patching to preserve working code
            if overall_strategy in ("regenerate_all", "regenerate_worst"):
                logger.warning(f"  ⚠️  Strategy '{overall_strategy}' downgraded to 'patch_files' — never regenerate working code")
                console.print(f"  [yellow]⚠️  Downgraded '{overall_strategy}' → 'patch_files' (preserve working code)[/yellow]")
                overall_strategy = "patch_files"
                # Convert any 'regenerate' file actions to 'patch'
                for fname, finstr in strategy_file_instructions.items():
                    if isinstance(finstr, dict) and finstr.get("action") == "regenerate":
                        finstr["action"] = "patch"
                        finstr["specific_instructions"] = (
                            "Fix ONLY the broken parts of this file. Keep all working code intact. "
                            + finstr.get("specific_instructions", "")
                        )

        # ── Handle "delete" actions BEFORE any LLM fixing ─────────────────
        # Strategy reasoner may flag files for deletion (e.g. shadow files like
        # numpy.py, torch.py that shadow real packages).  Remove them from the
        # file set immediately — no LLM call needed.
        _SHADOW_PKG_STEMS_FIX = {
            "torch", "numpy", "pandas", "scipy", "sklearn", "tensorflow",
            "keras", "matplotlib", "seaborn", "plotly", "cv2",
            "transformers", "datasets", "tokenizers", "accelerate",
            "diffusers", "langchain", "openai", "anthropic", "groq",
            "fastapi", "flask", "django", "requests", "httpx", "aiohttp",
            "pydantic", "sqlalchemy", "redis", "celery", "pytest",
            "hypothesis", "click", "typer", "rich",
            "jwt", "bcrypt", "websockets", "websocket", "cryptography",
            "yaml", "toml", "dotenv", "paramiko", "fabric",
            "os", "sys", "re", "io", "abc", "gc", "math", "cmath",
            "time", "random", "copy", "enum", "json", "csv", "logging",
            "pathlib", "typing", "types", "collections", "functools",
            "itertools", "asyncio", "subprocess", "socket",
            "hashlib", "datetime", "string", "dataclasses", "warnings",
            "traceback", "inspect", "importlib", "ast",
        }
        deleted_files = []
        for fname, finstr in list(strategy_file_instructions.items()):
            action = finstr.get("action", "patch") if isinstance(finstr, dict) else "patch"
            if action == "delete":
                if fname in files_for_fix:
                    del files_for_fix[fname]
                    logger.info(f"  🗑️  Deleted '{fname}' per strategy reasoner (action=delete)")
                    console.print(f"  [red]🗑️  Deleted shadow/problematic file: {fname}[/red]")
                    deleted_files.append(fname)
                # Remove from files_with_errors tracking
                strategy_file_instructions.pop(fname, None)

        # Also proactively detect + remove shadow files even without strategy instruction
        for fname in list(files_for_fix.keys()):
            if not fname.endswith(".py"):
                continue
            stem = fname.rsplit(".", 1)[0].lower()
            if stem in _SHADOW_PKG_STEMS_FIX and fname not in deleted_files:
                del files_for_fix[fname]
                logger.info(f"  🗑️  Auto-deleted shadow file '{fname}' (shadows package '{stem}')")
                console.print(f"  [red]🗑️  Auto-deleted shadow file: {fname}[/red]")
                deleted_files.append(fname)

        if deleted_files:
            console.print(f"  [green]✓[/green] Removed {len(deleted_files)} shadow/problematic file(s): {deleted_files}")
            # If deleting files resolved all errors (shadow imports), return early
            remaining_errors = [
                e for e in execution_errors
                if not any(df.rsplit('.', 1)[0] in str(e) for df in deleted_files)
            ]
            if not remaining_errors:
                logger.info("  ✅ All errors were caused by shadow files — no LLM fixing needed")
                console.print("  [green]✅ Shadow file deletion resolved all errors![/green]")
                return {
                    "current_stage": "code_fixed",
                    "generated_code": {"files": _flatten_file_keys(files_for_fix, "code_fixing_shadow")},
                    "fix_attempts": fix_attempts + 1,
                    "tests_passed": False,  # re-test to confirm
                }

        # ── Deterministic Pre-Fix: Auto-add missing stdlib imports ──────────
        # LLMs repeatedly fail to add simple `import X` statements. This
        # deterministic step scans errors for "name 'X' is not defined" where
        # X is a known stdlib module, and prepends the import directly.
        # No LLM needed — 100% reliable.
        _KNOWN_STDLIB_IMPORTABLE = {
            "argparse", "os", "sys", "re", "io", "abc", "gc", "math", "cmath",
            "time", "random", "copy", "enum", "json", "csv", "logging",
            "pathlib", "typing", "types", "collections", "functools",
            "itertools", "asyncio", "subprocess", "socket", "hashlib",
            "datetime", "string", "dataclasses", "warnings", "traceback",
            "inspect", "importlib", "ast", "textwrap", "shutil", "tempfile",
            "sqlite3", "threading", "multiprocessing", "contextlib",
            "operator", "struct", "base64", "secrets", "uuid", "decimal",
            "fractions", "statistics", "heapq", "bisect", "array",
            "pprint", "reprlib", "unittest", "doctest", "configparser",
            "http", "urllib", "email", "html", "xml", "ctypes",
            "glob", "fnmatch", "zipfile", "tarfile", "gzip", "bz2",
            "queue", "sched", "signal", "select", "selectors",
        }
        import re as _re_fix_import
        _auto_fixed_imports = []
        for _err in execution_errors:
            _err_s = str(_err)
            # Match: "NameError: name 'argparse' is not defined"
            _nim = _re_fix_import.search(r"NameError: name '(\w+)' is not defined", _err_s)
            if _nim:
                _missing_name = _nim.group(1)
                if _missing_name in _KNOWN_STDLIB_IMPORTABLE:
                    # Find which file has the error
                    _fix_file = None
                    _fm_file = _re_fix_import.search(r'([\w_]+\.py)', _err_s)
                    if _fm_file:
                        _fix_file = _fm_file.group(1)
                    # If file not found in error, scan all .py files for usage
                    if not _fix_file:
                        for _fn, _fc in files_for_fix.items():
                            if _fn.endswith(".py") and _missing_name in str(_fc):
                                _fix_file = _fn
                                break
                    if _fix_file and _fix_file in files_for_fix:
                        _existing_code = str(files_for_fix[_fix_file])
                        # Check if import is genuinely missing
                        _import_pattern = _re_fix_import.compile(
                            rf'^(?:import\s+{_missing_name}|from\s+{_missing_name}\s+import)',
                            _re_fix_import.MULTILINE
                        )
                        if not _import_pattern.search(_existing_code):
                            # Prepend the import
                            files_for_fix[_fix_file] = f"import {_missing_name}\n" + _existing_code
                            _auto_fixed_imports.append((_fix_file, _missing_name))
                            logger.info(f"  🔧 Auto-added: import {_missing_name} → {_fix_file}")
        if _auto_fixed_imports:
            console.print(f"  [green]✓ Auto-fixed {len(_auto_fixed_imports)} missing stdlib import(s):[/green]")
            for _afi_file, _afi_mod in _auto_fixed_imports:
                console.print(f"    [green]import {_afi_mod}[/green] → {_afi_file}")
            # Remove the now-fixed errors from execution_errors so the LLM
            # doesn't waste time on them
            _fixed_names = {n for _, n in _auto_fixed_imports}
            execution_errors = [
                e for e in execution_errors
                if not any(f"name '{n}' is not defined" in str(e) for n in _fixed_names)
            ]

        # ── Deterministic Pre-Fix: Auto-sanitize encoding issues ──────────
        # Uses shared _EMOJI_TO_ASCII map for consistency.
        _has_encoding_errors = any(
            ("ENCODING_ISSUE" in str(e) or "UnicodeEncodeError" in str(e)
             or "UnicodeDecodeError" in str(e) or "charmap" in str(e))
            for e in execution_errors
        )
        _encoding_fixed = []
        if _has_encoding_errors:
            # Blanket sanitize ALL .py files — safer than trying to parse filenames
            _enc_count = _sanitize_emoji(files_for_fix, "encoding-prefix")
            if _enc_count:
                _encoding_fixed = [f for f in files_for_fix if f.endswith(".py")]  # track all .py as potentially fixed
        if _encoding_fixed:
            console.print(f"  [green]✓ Auto-sanitized Unicode in {len(_encoding_fixed)} file(s): {_encoding_fixed}[/green]")
            # Remove encoding errors from the list
            execution_errors = [
                e for e in execution_errors
                if not any(k in str(e) for k in ("ENCODING_ISSUE", "UnicodeEncodeError",
                                                   "UnicodeDecodeError", "charmap"))
            ]
        # ── Deterministic Pre-Fix: Fuzzy method rename ────────────────────
        # When SELF_METHOD_MISSING or API_MISMATCH says "calls self.X() but
        # no method X, available methods: [Y, Z]" and one of the available
        # methods is a close match (e.g. get_budget_vs_actual vs
        # generate_budget_vs_actual), auto-rename the call site.
        import difflib as _difflib_fix
        _method_renames = []
        for _mr_err in list(execution_errors):
            _mr_s = str(_mr_err)
            # Match: "calls `self.get_budget_vs_actual()` but no method `get_budget_vs_actual` exists"
            # OR: "`parser.add_subparsers()` called but class `CSVParser` has no method `add_subparsers`"
            _mr_match = _re_fix_import.search(
                r'(?:calls\s+`(?:self|[\w.]+)\.(\w+)\(\)`\s+but\s+no\s+method\s+`\w+`|'
                r'`[\w.]+\.(\w+)\(\)`\s+called\s+but\s+class\s+`\w+`.*?has\s+no\s+method\s+`\w+`)',
                _mr_s
            )
            if not _mr_match:
                continue
            _wrong_method = _mr_match.group(1) or _mr_match.group(2)
            if not _wrong_method:
                continue
            # Extract available methods
            _avail_match = _re_fix_import.search(r'Available methods:\s*\[([^\]]+)\]', _mr_s)
            if not _avail_match:
                continue
            _avail_methods = [m.strip().strip("'\"") for m in _avail_match.group(1).split(",")]
            # Find closest match
            _close = _difflib_fix.get_close_matches(_wrong_method, _avail_methods, n=1, cutoff=0.5)
            if not _close:
                # Try substring matching: if wrong_method is a substring or vice versa
                for _am in _avail_methods:
                    if _wrong_method in _am or _am in _wrong_method:
                        _close = [_am]
                        break
            if not _close:
                continue
            _correct_method = _close[0]
            # Find which file has the error
            _mr_file_match = _re_fix_import.search(r'([\w_]+\.py):\d+', _mr_s)
            if not _mr_file_match:
                continue
            _mr_file = _mr_file_match.group(1)
            if _mr_file not in files_for_fix:
                continue
            # Replace the wrong method call with the correct one
            _mr_code = str(files_for_fix[_mr_file])
            # Replace .wrong_method( with .correct_method( — be precise
            _mr_pattern = r'\.{}\s*\('.format(_re_fix_import.escape(_wrong_method))
            _mr_new = '.{}('.format(_correct_method)
            _mr_new_code = _re_fix_import.sub(_mr_pattern, _mr_new, _mr_code)
            if _mr_new_code != _mr_code:
                files_for_fix[_mr_file] = _mr_new_code
                _method_renames.append((_mr_file, _wrong_method, _correct_method))
                logger.info(f"  🔧 Auto-renamed: .{_wrong_method}() → .{_correct_method}() in {_mr_file}")
        if _method_renames:
            console.print(f"  [green]✓ Auto-renamed {len(_method_renames)} method call(s):[/green]")
            for _mrf, _old, _new in _method_renames:
                console.print(f"    [green].{_old}() → .{_new}()[/green] in {_mrf}")
            _renamed_methods = {old for _, old, _ in _method_renames}
            execution_errors = [
                e for e in execution_errors
                if not any(f".{m}()" in str(e) or f"`{m}`" in str(e) for m in _renamed_methods)
            ]

        # ── Deterministic Pre-Fix: SQLite non-deterministic GENERATED columns ──
        # date(), time(), random(), datetime() are forbidden in GENERATED
        # ALWAYS AS columns.  Remove the GENERATED clause entirely —
        # the Python model already computes this as a @property / method.
        import re as _re_fix_gen
        _gen_col_fixes = []
        for _gc_fname, _gc_code in list(files_for_fix.items()):
            if not _gc_fname.endswith(".py"):
                continue
            _gc_str = str(_gc_code)
            _gc_new = _gc_str
            _NONDETERMINISTIC_FNS = r"(?:date|time|random|datetime|julianday|strftime)\s*\("
            # Pattern: full column definition with GENERATED ALWAYS AS (...) VIRTUAL/STORED
            # We need to handle multi-line expressions
            _gen_col_pattern = _re_fix_gen.compile(
                r',?\s*\n?\s*(\w+)\s+(?:\w+\s+)?GENERATED\s+ALWAYS\s+AS\s*\((.+?)\)\s*(?:STORED|VIRTUAL)',
                _re_fix_gen.IGNORECASE | _re_fix_gen.DOTALL
            )
            _removed_cols = []
            for _gc_m in reversed(list(_gen_col_pattern.finditer(_gc_new))):
                _gc_expr = _gc_m.group(2)
                _gc_col_name = _gc_m.group(1)
                if _re_fix_gen.search(_NONDETERMINISTIC_FNS, _gc_expr, _re_fix_gen.IGNORECASE):
                    _gc_new = _gc_new[:_gc_m.start()] + _gc_new[_gc_m.end():]
                    _removed_cols.append(_gc_col_name)
                    logger.info(f"  🔧 Auto-removed non-deterministic GENERATED column `{_gc_col_name}` from {_gc_fname}")

            # Also remove indexes on removed columns
            for _rc in _removed_cols:
                _gc_new = _re_fix_gen.sub(
                    rf'^\s*"?CREATE\s+INDEX\s+.*\b{_re_fix_gen.escape(_rc)}\b.*"?\s*,?\s*\n?',
                    '', _gc_new, flags=_re_fix_gen.MULTILINE | _re_fix_gen.IGNORECASE
                )

            # Also handle ALTER TABLE ... ADD COLUMN ... GENERATED ALWAYS AS
            _alter_gen_pattern = _re_fix_gen.compile(
                r'(self\.connection\.execute\s*\(\s*"""[^"]*?'
                r'ALTER\s+TABLE\s+\w+\s*\n?\s*ADD\s+COLUMN\s+\w+\s+\w+\s*\n?\s*'
                r'GENERATED\s+ALWAYS\s+AS\s*\(.+?\)\s*(?:STORED|VIRTUAL)'
                r'[^"]*?"""\s*\))',
                _re_fix_gen.IGNORECASE | _re_fix_gen.DOTALL
            )
            for _alt_m in reversed(list(_alter_gen_pattern.finditer(_gc_new))):
                _alt_expr = _alt_m.group(0)
                if _re_fix_gen.search(_NONDETERMINISTIC_FNS, _alt_expr, _re_fix_gen.IGNORECASE):
                    _gc_new = _gc_new[:_alt_m.start()] + "pass  # Removed: non-deterministic GENERATED column" + _gc_new[_alt_m.end():]
                    logger.info(f"  🔧 Auto-removed ALTER TABLE with non-deterministic GENERATED column from {_gc_fname}")

            if _gc_new != _gc_str:
                files_for_fix[_gc_fname] = _gc_new
                _gen_col_fixes.append((_gc_fname, _removed_cols))
        if _gen_col_fixes:
            console.print(f"  [green]✓ Auto-removed non-deterministic GENERATED columns:[/green]")
            for _gcf_file, _gcf_cols in _gen_col_fixes:
                console.print(f"    [green]{_gcf_file}[/green]: removed {_gcf_cols}")
            # Remove now-fixed errors
            execution_errors = [
                e for e in execution_errors
                if "SQLITE_NONDETERMINISTIC" not in str(e) and "non-deterministic" not in str(e).lower()
            ]

        # ── Deterministic Pre-Fix: Colorama init() missing import ──────────
        # LLMs call `init(autoreset=True)` at module level without importing
        # from colorama.  Fix by adding the import or wrapping in try/except.
        _colorama_fixes = []
        for _ci_fname, _ci_code in list(files_for_fix.items()):
            if not _ci_fname.endswith(".py"):
                continue
            _ci_str = str(_ci_code)
            if _re_fix_import.search(r'^\s*init\s*\(\s*autoreset\s*=', _ci_str, _re_fix_import.MULTILINE):
                has_colorama_import = bool(_re_fix_import.search(
                    r'^\s*from\s+colorama\s+import\s+.*\binit\b', _ci_str, _re_fix_import.MULTILINE
                ))
                if not has_colorama_import:
                    # Wrap the init() call in try/except so it doesn't crash
                    # if colorama isn't installed
                    _ci_new = _re_fix_import.sub(
                        r'^(\s*)(init\s*\(\s*autoreset\s*=[^)]*\))',
                        r'\1try:\n\1    from colorama import init\n\1    \2\n\1except ImportError:\n\1    pass  # colorama not installed',
                        _ci_str, flags=_re_fix_import.MULTILINE
                    )
                    if _ci_new != _ci_str:
                        files_for_fix[_ci_fname] = _ci_new
                        _colorama_fixes.append(_ci_fname)
                        logger.info(f"  🔧 Auto-fixed colorama init() import in {_ci_fname}")
        if _colorama_fixes:
            console.print(f"  [green]✓ Auto-fixed colorama init() in {len(_colorama_fixes)} file(s)[/green]")
            execution_errors = [
                e for e in execution_errors
                if "MISSING_COLORAMA" not in str(e) and "init' is not defined" not in str(e)
            ]

        # ── Deterministic Pre-Fix: Relative imports → absolute ─────────────
        # LLMs produce `from .module import X` despite prompt rules.
        # Fix deterministically: `from .module import X` → `from module import X`
        _rel_import_fixes = []
        for _ri_fname, _ri_code in list(files_for_fix.items()):
            if not _ri_fname.endswith(".py"):
                continue
            _ri_str = str(_ri_code)
            # Match `from .module import ...` or `from . import ...`
            _ri_new = _re_fix_import.sub(
                r'^(\s*)from\s+\.(\w+)\s+import\s+',
                r'\1from \2 import ',
                _ri_str, flags=_re_fix_import.MULTILINE
            )
            # Also fix `from . import module`
            _ri_new = _re_fix_import.sub(
                r'^(\s*)from\s+\.\s+import\s+',
                r'\1import ',
                _ri_new, flags=_re_fix_import.MULTILINE
            )
            if _ri_new != _ri_str:
                files_for_fix[_ri_fname] = _ri_new
                _ri_count = _ri_str.count("from .") - _ri_new.count("from .")
                _rel_import_fixes.append((_ri_fname, _ri_count))
                logger.info(f"  🔧 Auto-fixed {_ri_count} relative import(s) in {_ri_fname}")
        if _rel_import_fixes:
            console.print(f"  [green]✓ Fixed relative → absolute imports in {len(_rel_import_fixes)} file(s)[/green]")
            execution_errors = [
                e for e in execution_errors
                if "relative import" not in str(e).lower()
            ]

        # ── Deterministic Pre-Fix: CLASS_SCOPE_NAME_ERROR (string annotation) ─
        # When a type annotation references a name not defined in the file,
        # wrap it in quotes to make it a forward reference (PEP 563).
        # e.g. `def __init__(self, queue: TaskQueue)` → `def __init__(self, queue: 'TaskQueue')`
        _class_scope_fixes = []
        for _csf_err in list(execution_errors):
            _csf_s = str(_csf_err)
            if "CLASS_SCOPE_NAME_ERROR" not in _csf_s:
                continue
            # Extract the undefined name: "uses type hint `TaskQueue`"
            _csf_match = _re_fix_import.search(r"uses type hint `(\w+)` which is not imported", _csf_s)
            if not _csf_match:
                continue
            _undef_name = _csf_match.group(1)
            # Extract filename
            _csf_file_match = _re_fix_import.search(r'([\w_]+\.py):\d+', _csf_s)
            if not _csf_file_match:
                continue
            _csf_file = _csf_file_match.group(1)
            if _csf_file not in files_for_fix:
                continue
            _csf_code = str(files_for_fix[_csf_file])
            # Replace bare type annotations with quoted versions
            # Match: `name: TypeName` in function args and `-> TypeName`
            _csf_new = _re_fix_import.sub(
                r':\s*' + _re_fix_import.escape(_undef_name) + r'(?=\s*[,=)\]])',
                f": '{_undef_name}'",
                _csf_code
            )
            # Also fix return type annotations: `-> TypeName:`
            _csf_new = _re_fix_import.sub(
                r'->\s*' + _re_fix_import.escape(_undef_name) + r'(?=\s*:)',
                f"-> '{_undef_name}'",
                _csf_new
            )
            if _csf_new != _csf_code:
                files_for_fix[_csf_file] = _csf_new
                _class_scope_fixes.append((_csf_file, _undef_name))
                logger.info(f"  🔧 Auto-quoted forward ref '{_undef_name}' in {_csf_file}")
        if _class_scope_fixes:
            console.print(f"  [green]✓ Fixed {len(_class_scope_fixes)} class-scope name error(s) (PEP 563 forward refs)[/green]")
            _fixed_names = {n for _, n in _class_scope_fixes}
            execution_errors = [
                e for e in execution_errors
                if not ("CLASS_SCOPE_NAME_ERROR" in str(e) and any(n in str(e) for n in _fixed_names))
            ]

        # ── Deterministic Pre-Fix: Cross-file import name fix ──────────────
        # When `from module import WrongName` but module has `CorrectName`,
        # auto-fix the import statement to use the closest match.
        _xf_import_fixes = []
        for _xf_err in list(execution_errors):
            _xf_s = str(_xf_err)
            if "CROSS_FILE_IMPORT_MISMATCH" not in _xf_s:
                continue
            # Extract: "from module import WrongName ... Did you mean 'CorrectName'?"
            _xf_imp_match = _re_fix_import.search(
                r'`from (\w+) import (\w+)`.+?Did you mean \'(\w+)\'', _xf_s
            )
            if not _xf_imp_match:
                continue
            _xf_mod, _xf_wrong, _xf_correct = _xf_imp_match.groups()
            # Find which file has this import
            _xf_file_match = _re_fix_import.search(r'([\w_]+\.py):\d+', _xf_s)
            if not _xf_file_match:
                continue
            _xf_file = _xf_file_match.group(1)
            if _xf_file not in files_for_fix:
                continue
            _xf_code = str(files_for_fix[_xf_file])
            # Replace the wrong import name
            _xf_new = _re_fix_import.sub(
                rf'(from\s+{_re_fix_import.escape(_xf_mod)}\s+import\s+.*?)\b{_re_fix_import.escape(_xf_wrong)}\b',
                rf'\g<1>{_xf_correct}',
                _xf_code
            )
            # Also update all identifier usages (word-boundary safe — V3 FIX)
            if _xf_new != _xf_code:
                _xf_new = _re_fix_import.sub(r'\b' + _re_fix_import.escape(_xf_wrong) + r'\b', _xf_correct, _xf_new)
                files_for_fix[_xf_file] = _xf_new
                _xf_import_fixes.append((_xf_file, _xf_wrong, _xf_correct))
                logger.info(f"  🔧 Auto-fixed import: {_xf_wrong} → {_xf_correct} in {_xf_file}")
        if _xf_import_fixes:
            console.print(f"  [green]✓ Fixed {len(_xf_import_fixes)} cross-file import mismatch(es)[/green]")
            _fixed_imports = {w for _, w, _ in _xf_import_fixes}
            execution_errors = [
                e for e in execution_errors
                if not ("CROSS_FILE_IMPORT_MISMATCH" in str(e) and any(n in str(e) for n in _fixed_imports))
            ]

        # ── Deterministic Pre-Fix: Empty stub file generator ──────────────
        # When a file is empty/near-empty but other files import from it,
        # generate minimal stub classes/functions based on what's imported.
        _stub_fixes = []
        for _sf_err in list(execution_errors):
            _sf_s = str(_sf_err)
            if "EMPTY_STUB_FILE" not in _sf_s:
                continue
            _sf_file_match = _re_fix_import.search(r'EMPTY_STUB_FILE:\s*([\w_]+\.py)', _sf_s)
            if not _sf_file_match:
                continue
            _sf_file = _sf_file_match.group(1)
            if _sf_file not in files_for_fix:
                continue
            _sf_mod = _sf_file.rsplit(".", 1)[0]
            # Find what names other files import from this module
            import ast as _ast_stub
            _needed_names = set()
            for _other_fn, _other_code in files_for_fix.items():
                if _other_fn == _sf_file or not _other_fn.endswith(".py"):
                    continue
                try:
                    _other_tree = _ast_stub.parse(str(_other_code))
                    for _sn in _ast_stub.walk(_other_tree):
                        if isinstance(_sn, _ast_stub.ImportFrom) and _sn.module == _sf_mod:
                            for _alias in (_sn.names or []):
                                if _alias.name != "*":
                                    _needed_names.add(_alias.name)
                except SyntaxError:
                    pass
            if _needed_names:
                # Generate minimal stubs
                _stub_lines = [f'"""Auto-generated stubs for {_sf_file}"""\n']
                for _name in sorted(_needed_names):
                    if _name[0].isupper():
                        # Likely a class
                        _stub_lines.append(f'class {_name}:\n    """Stub for {_name}."""\n    pass\n')
                    else:
                        # Likely a function or constant
                        _stub_lines.append(f'def {_name}(*args, **kwargs):\n    """Stub for {_name}."""\n    pass\n')
                files_for_fix[_sf_file] = "\n".join(_stub_lines)
                _stub_fixes.append((_sf_file, sorted(_needed_names)))
                logger.info(f"  🔧 Auto-generated stubs in {_sf_file}: {sorted(_needed_names)}")
        if _stub_fixes:
            console.print(f"  [green]✓ Generated stub implementations for {len(_stub_fixes)} empty file(s)[/green]")
            execution_errors = [
                e for e in execution_errors
                if "EMPTY_STUB_FILE" not in str(e)
            ]

        # ── Deterministic Pre-Fix: __main__ guard wrapper ──────────────────
        # Wrap top-level executable code in main.py with if __name__ guard
        _main_guard_fixed = False
        for _mg_err in list(execution_errors):
            if "MISSING_MAIN_GUARD" not in str(_mg_err):
                continue
            if "main.py" in files_for_fix:
                _mg_code = str(files_for_fix["main.py"])
                if "if __name__" not in _mg_code:
                    try:
                        import ast as _ast_mg
                        _mg_tree = _ast_mg.parse(_mg_code)
                        _mg_lines = _mg_code.splitlines(True)
                        # Find the first non-import, non-def, non-class top-level statement
                        _first_exec_line = None
                        for _mg_node in _ast_mg.iter_child_nodes(_mg_tree):
                            if isinstance(_mg_node, (_ast_mg.Import, _ast_mg.ImportFrom,
                                                     _ast_mg.ClassDef, _ast_mg.FunctionDef,
                                                     _ast_mg.AsyncFunctionDef)):
                                continue
                            if isinstance(_mg_node, _ast_mg.Expr) and isinstance(_mg_node.value, (_ast_mg.Constant, _ast_mg.Str)):
                                continue  # docstring
                            _first_exec_line = getattr(_mg_node, "lineno", None)
                            if _first_exec_line:
                                break
                        if _first_exec_line and _first_exec_line > 1:
                            # Split: everything before exec line stays, everything after gets wrapped
                            _before = "".join(_mg_lines[:_first_exec_line - 1])
                            _after = "".join(_mg_lines[_first_exec_line - 1:])
                            # Indent the after part
                            _indented = "\n".join("    " + l if l.strip() else l for l in _after.splitlines())
                            _mg_new = _before + '\n\nif __name__ == "__main__":\n' + _indented + "\n"
                            files_for_fix["main.py"] = _mg_new
                            _main_guard_fixed = True
                            logger.info("  🔧 Auto-wrapped main.py code in __main__ guard")
                    except (SyntaxError, Exception) as _mge:
                        logger.debug(f"  Could not auto-add __main__ guard: {_mge}")
        if _main_guard_fixed:
            console.print("  [green]✓ Wrapped main.py top-level code in __main__ guard[/green]")
            execution_errors = [e for e in execution_errors if "MISSING_MAIN_GUARD" not in str(e)]

        # ── End Deterministic Pre-Fix ─────────────────────────────────────

        # ── Track auto-fixed errors for tracer ────────────────────────────
        # Compare original errors vs remaining: the difference = auto-fixed.
        _auto_fixed_this_round = [e for e in _original_errors if e not in execution_errors]
        if _auto_fixed_this_round:
            logger.info(f"  🔧 Deterministic fixers resolved {len(_auto_fixed_this_round)} error(s)")
        # ── End auto-fix tracking ─────────────────────────────────────────

        # ── Error Dedup across Fix Iterations (Item #17) ──────────────────
        # Hash each remaining error.  If the same error appeared in a prior
        # fix iteration, annotate it so the LLM knows it's persistent and
        # should try a fundamentally different approach.
        import hashlib as _hashlib_dedup
        _prev_hashes = list(state.get("_prev_error_hashes", []))
        _current_hashes = []
        _persistent_errors = []
        for _err in execution_errors:
            # Normalize: strip whitespace, line numbers, paths for consistent hashing
            _err_str = str(_err).strip()
            _err_norm = _re.sub(r'line \d+', 'line N', _err_str)
            _err_norm = _re.sub(r'File "[^"]*"', 'File "X"', _err_norm)
            _ehash = _hashlib_dedup.md5(_err_norm.encode()).hexdigest()[:12]
            _current_hashes.append(_ehash)
            if _ehash in _prev_hashes:
                _count = _prev_hashes.count(_ehash) + 1
                _persistent_errors.append((_err_str, _count))

        if _persistent_errors:
            logger.warning(f"  ⚠️  {len(_persistent_errors)} error(s) persisted across fix iterations")
            console.print(f"  [yellow]⚠️  {len(_persistent_errors)} error(s) are recurring — escalating to LLM[/yellow]")
        # Build combined hash list for next iteration
        _all_hashes = _prev_hashes + _current_hashes
        # ── End Error Dedup ───────────────────────────────────────────────

        # ── IMPROVEMENT #2: Traceback Parser — structured error extraction ──
        # Parse raw error text into structured ParsedError objects with
        # file, line, function, error type. Then build per-file error
        # summaries with ±10 lines of code context around each error.
        _parsed_errors = []
        _smart_error_context: dict = {}
        try:
            try:
                from ..utils.traceback_parser import parse_python_traceback, build_smart_fix_context
            except ImportError:
                from utils.traceback_parser import parse_python_traceback, build_smart_fix_context  # type: ignore
            _all_error_text = "\n".join(str(e) for e in execution_errors)
            _parsed_errors = parse_python_traceback(_all_error_text)
            if _parsed_errors:
                _smart_error_context = build_smart_fix_context(
                    _parsed_errors, {k: str(v) for k, v in files_for_fix.items()}, context_lines=10
                )
                logger.info(f"  🔍 Parsed {len(_parsed_errors)} structured errors from tracebacks")
                for _pe in _parsed_errors[:5]:
                    logger.info(f"    {_pe.error_type}: {_pe.error_message[:80]} ({_pe.file}:{_pe.line})")
        except Exception as _tp_err:
            logger.debug(f"  Traceback parser failed: {_tp_err}")
        # ── End Traceback Parser ──────────────────────────────────────────

        # ── IMPROVEMENT #3: Error Pattern DB — instant auto-fixes ─────────
        # Try deterministic regex-based fixes for common patterns BEFORE
        # sending anything to the LLM. Saves time and tokens.
        _pattern_auto_fixed = 0
        try:
            try:
                from ..utils.error_pattern_db import get_pattern_db
            except ImportError:
                from utils.error_pattern_db import get_pattern_db  # type: ignore
            _pattern_db = get_pattern_db()
            for _pe in _parsed_errors:
                if _pe.file and _pe.file in files_for_fix:
                    _auto_fixed = _pattern_db.try_auto_fix(
                        str(files_for_fix[_pe.file]),
                        _pe.error_type,
                        _pe.error_message,
                        {k: str(v) for k, v in files_for_fix.items()},
                    )
                    if _auto_fixed:
                        files_for_fix[_pe.file] = _auto_fixed
                        _pattern_auto_fixed += 1
                        logger.info(f"  🎯 Pattern auto-fix applied to {_pe.file}: {_pe.error_type}")
            if _pattern_auto_fixed:
                console.print(f"  [green]✓ Error Pattern DB auto-fixed {_pattern_auto_fixed} error(s) without LLM[/green]")
                # Remove auto-fixed errors from the list so LLM doesn't re-fix them
                _remaining_parsed = [e for e in _parsed_errors if not (
                    e.file and e.file in files_for_fix
                )]
                # Rebuild execution_errors minus the auto-fixed ones
                _auto_fixed_types = {(e.file, e.error_type) for e in _parsed_errors if e.file in files_for_fix}
                execution_errors = [
                    e for e in execution_errors
                    if not any(f"{ft[0]}" in str(e) and ft[1] in str(e) for ft in _auto_fixed_types)
                ] or execution_errors  # keep original if filtering removed everything
        except Exception as _epdb_err:
            logger.debug(f"  Error Pattern DB failed: {_epdb_err}")
        # ── End Error Pattern DB ──────────────────────────────────────────

        # Use powerful model for complex fixes, fast for simple patches
        llm = get_llm("powerful") if use_powerful_model else get_llm("fast")

        # ── SOTA: Reflexion-style Snapshot ────────────────────────────────
        # Save a deep copy of all files BEFORE any LLM fixing.
        # After fixing, we compare syntax error counts.  If the "fix"
        # introduced MORE syntax errors than the original, we ROLLBACK
        # to the pre-fix state.  (Inspired by Reflexion — Shinn et al. 2023)
        import copy as _copy_fix
        _snapshot_files = _copy_fix.deepcopy(files_for_fix)
        _snapshot_syntax_errors = 0
        for _sf_name, _sf_code in _snapshot_files.items():
            if _sf_name.endswith(".py") and _sf_code.strip():
                try:
                    compile(_sf_code, _sf_name, "exec")
                except SyntaxError:
                    _snapshot_syntax_errors += 1
        logger.info(f"  📸 Snapshot: {len(_snapshot_files)} files, {_snapshot_syntax_errors} syntax errors (pre-fix)")
        # ── End Snapshot ──────────────────────────────────────────────────

        # Build error context — with persistence annotations
        _error_lines = []
        for _err in execution_errors:
            _err_str = str(_err)
            _persistent_info = ""
            for _pe, _pc in _persistent_errors:
                if _pe == _err_str.strip():
                    _persistent_info = f" [⚠️  PERSISTENT: failed {_pc}x — previous fix approaches did NOT work. Try a FUNDAMENTALLY DIFFERENT approach.]"
                    break
            _error_lines.append(f"- {_err_str}{_persistent_info}")
        error_summary = "\n".join(_error_lines)

        system_prompt = """You are an expert Python debugger. Fix code issues based on test errors.

Your job:
1. Analyze the error messages
2. Identify the root cause — fix ONLY the broken parts
3. Generate fixed code — keep ALL working code exactly as-is
4. Ensure all imports and dependencies are correct

CRITICAL: Do NOT rewrite entire files from scratch. Make MINIMAL, TARGETED changes.
Keep all working functions, classes, and logic intact. Only modify the specific
lines/functions that are causing errors.

CRITICAL IMPORT RULES:
- NEVER use relative imports (from .module import X). Always use absolute imports (from module import X).
- NEVER use dotted package imports for local files (from project_name.module import X). All project files are in a FLAT directory — use `from module import X` directly.
- The project is NOT a Python package — there is no __init__.py, no subdirectories.
- Only import from: Python stdlib, pip packages in requirements.txt, or other project files.

SPECIAL ERROR TYPES — handle these specifically:

- ATTR_MISMATCH: A caller accesses `obj.some_attr` but the class defines it with a different name
  (e.g. `db_manager.db_path` but class has `self._db_path`). Fix by changing the CALLER to use
  the correct attribute name as defined in the class. Do NOT rename the class attribute.
  The error message will tell you the correct attribute name — use it exactly.

- ENCODING_ISSUE: File contains emoji or non-ASCII characters (✅, ❌, ⚠️, 🔄, etc.) in print()
  calls or strings. Replace ALL emoji/unicode symbols with ASCII equivalents:
  ✅ → [OK]  ❌ → [FAIL]  ⚠️ → [!]  🔄 → [...]  ✓ → [v]  ✗ → [x]  📊 → [stats]
  Do a thorough scan — replace EVERY non-ASCII character in the file.

- API_MISMATCH: Caller uses `obj.method()` but class defines a different method name.
  Fix the caller to use the correct method name from the class definition.

Return ONLY valid Python code for each file, no explanations."""

        fixed_files = {}

        # Determine which files actually have errors (don't waste LLM calls on clean files)
        # If strategy provided file_instructions, use those files instead
        files_with_errors = set()
        if strategy_file_instructions:
            files_with_errors = {f for f in strategy_file_instructions if f in files_for_fix}
        if not files_with_errors:
            for err in execution_errors:
                for filename in files_for_fix:
                    if filename in str(err):
                        files_with_errors.add(filename)
        # Fallback: if we can't identify specific files, fix all .py files
        if not files_with_errors:
            files_with_errors = {f for f in files_for_fix if f.endswith('.py')}

        logger.info(f"  Files needing fixes: {sorted(files_with_errors)}")

        # ── Build per-file error summaries (only relevant errors per file) ──
        # Use smart traceback-parsed context if available, otherwise fallback
        _per_file_errors: dict = {}
        if _smart_error_context:
            # Use structured traceback-parsed context (IMPROVEMENT #2)
            _per_file_errors = dict(_smart_error_context)
            logger.info(f"  🔍 Using smart traceback context for {len(_per_file_errors)} file(s)")
        # Also add raw error matching as fallback for files not in parsed context
        for _fname_err in files_with_errors:
            if _fname_err not in _per_file_errors:
                _relevant = [e for e in execution_errors if _fname_err in str(e)]
                if _relevant:
                    _per_file_errors[_fname_err] = "\n".join(str(e) for e in _relevant)

        _FIX_TYPO = {'\u202f':' ','\u2011':'-','\u2013':'-','\u2014':'--','\u2015':'--',
                     '\u2018':"'",'\u2019':"'",'\u201a':"'",'\u201c':'"','\u201d':'"',
                     '\u201e':'"','\u00a0':' ','\u2026':'...','\u2212':'-','\ufeff':''}

        _fix_semaphore = _asyncio_fix.Semaphore(4)  # max 4 concurrent LLM calls

        async def _fix_one_file(_fname: str, _content: str) -> tuple:
            """Fix a single file via LLM. Returns (filename, fixed_code_or_None)."""
            file_strategy = strategy_file_instructions.get(_fname, {})
            strategy_instr = file_strategy.get("specific_instructions", "")
            strategy_action = file_strategy.get("action", "patch")

            console.print(f"  [dim]Fixing {_fname} (action: {strategy_action})...[/dim]")

            strategy_section = ""
            if strategy_instr:
                strategy_section = (
                    f"\n\nSTRATEGY GUIDANCE (from reasoning analysis):\n"
                    f"Action: {strategy_action}\n"
                    f"Instructions: {strategy_instr}\n"
                )

            file_error_summary = _per_file_errors.get(_fname, error_summary)

            # ── Build cross-file context so LLM sees the full project ────
            # Include OTHER project files (truncated) so the LLM can fix
            # cross-file import errors, method signature mismatches, etc.
            _context_lines = []
            _context_budget = 4000  # chars of OTHER file context
            for _cf_name, _cf_code in sorted(files_for_fix.items()):
                if _cf_name == _fname or not _cf_name.endswith(".py"):
                    continue
                _cf_snippet = str(_cf_code)[:_context_budget // max(1, len(files_for_fix) - 1)]
                _context_lines.append(f"# === {_cf_name} ===\n{_cf_snippet}")
            _cross_file_ctx = ""
            if _context_lines:
                _cross_file_ctx = (
                    "\n\nOTHER PROJECT FILES (for cross-file reference — do NOT return these):\n"
                    + "\n\n".join(_context_lines)
                )

            user_prompt = f"""Fix this Python file based on the test errors:

Errors:
{file_error_summary}
{strategy_section}
{_cross_file_ctx}

File to fix: {_fname}
```python
{_content}
```

Return the FIXED code for {_fname}. Fix ONLY:
- The specific functions/methods causing errors
- Syntax errors
- Import errors
- Missing dependencies
- Type errors
- Runtime errors

CRITICAL: Make MINIMAL changes. Keep every function that is NOT mentioned in the
errors EXACTLY as-is. Do NOT rewrite working code. Do NOT rename variables or
restructure code that already works. Only touch the broken parts.

Return ONLY the complete file with targeted fixes applied, no explanations."""

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]

            async with _fix_semaphore:
                try:
                    # Per-file timeout: 3 minutes max to prevent one slow call
                    # from blocking the entire parallel batch
                    response = await _asyncio_fix.wait_for(
                        llm.ainvoke(messages),
                        timeout=180  # 3 minutes per file
                    )
                except _asyncio_fix.TimeoutError:
                    logger.warning(f"  ⏰ LLM fix timed out for {_fname} (180s) — keeping original")
                    return (_fname, None)
                _max_retries = 2  # Try same model once more before giving up
                response = None
                for _retry in range(_max_retries):
                    try:
                        # Per-file timeout: 3 minutes max to prevent one slow call
                        # from blocking the entire parallel batch
                        response = await _asyncio_fix.wait_for(
                            llm.ainvoke(messages),
                            timeout=180  # 3 minutes per file
                        )
                        break  # Success — exit retry loop
                    except _asyncio_fix.TimeoutError:
                        if _retry < _max_retries - 1:
                            logger.warning(f"  ⏰ LLM fix timed out for {_fname} (180s) — retrying ({_retry + 1}/{_max_retries})")
                            continue
                        logger.warning(f"  ⏰ LLM fix timed out for {_fname} (180s) — exhausted retries, keeping original")
                        return (_fname, None)
                    except Exception as _fix_err:
                        if _retry < _max_retries - 1:
                            logger.warning(f"  ⚠️ LLM call failed for {_fname}: {_fix_err} — retrying ({_retry + 1}/{_max_retries})")
                            continue
                        logger.warning(f"  ⚠️ LLM call failed for {_fname}: {_fix_err} — exhausted retries")
                        return (_fname, None)

                if response is None:
                    return (_fname, None)

            fixed_code = response.content
            if "```python" in fixed_code:
                fixed_code = fixed_code.split("```python")[1].split("```")[0].strip()
            elif "```" in fixed_code:
                fixed_code = fixed_code.split("```")[1].split("```")[0].strip()

            # Strip LLM artifacts inline (</function>, ``` etc.)
            for _art_pat, _art_rep in _LLM_ARTIFACT_PATTERNS:
                fixed_code = _art_pat.sub(_art_rep, fixed_code)
            import re as _re_artifact_fix
            fixed_code = _re_artifact_fix.sub(r'\n{3,}', '\n\n', fixed_code
                try:
                    compile(fixed_code, _fname, "exec")
                except SyntaxError as _se:
                    _is_garbage = True
                    logger.warning(f"  ⚠️ Fixed {_fname} has syntax error ({_se.msg} line {_se.lineno}) — keeping original")

            if _is_garbage:
                console.print(f"  [yellow]⚠[/yellow] Kept original {_fname} (bad LLM response)")
                return (_fname, None)

            # Sanitize typographic unicode
            fixed_code = fixed_code.translate(str.maketrans(_FIX_TYPO))
            console.print(f"  [green]✓[/green] Fixed {_fname}")
            return (_fname, fixed_code)

        # Copy unchanged files first
        for filename, content in files_for_fix.items():
            if not filename.endswith('.py') or filename not in files_with_errors:
                fixed_files[filename] = content

        # Fire all LLM fix calls in parallel
        _fix_tasks = [
            _fix_one_file(fn, str(files_for_fix[fn]))
            for fn in sorted(files_with_errors)
            if fn in files_for_fix
        ]
        if _fix_tasks:
            console.print(f"  [cyan]⚡ Fixing {len(_fix_tasks)} files in parallel...[/cyan]")
            _fix_results = await _asyncio_fix.gather(*_fix_tasks, return_exceptions=True)
            for _res in _fix_results:
                if isinstance(_res, Exception):
                    logger.warning(f"  ⚠️ Parallel fix exception: {_res}")
                    continue
                _fname, _fixed = _res
                if _fixed is not None:
                    fixed_files[_fname] = _fixed
                else:
                    # Keep original on failure
                    if _fname in files_for_fix:
                        fixed_files[_fname] = files_for_fix[_fname]
        # ── End Parallel LLM fixing ────────────────────────────────────────

        # ── Post-LLM emoji sanitization (uses shared _EMOJI_TO_ASCII) ──
        import sys as _sys_fix_enc
        if _sys_fix_enc.platform == "win32":
            _pf_count = _sanitize_emoji(fixed_files, "post-LLM-fix")
            if _pf_count:
                logger.info(f"  🧹 Post-LLM emoji cleanup: {_pf_count} file(s)")
        # ── End Post-LLM emoji sanitization ──────────────────────────────

        # ── Post-LLM artifact stripping (XML/markdown leftovers) ─────────
        _pf_art_count = _sanitize_llm_artifacts(fixed_files, "post-LLM-fix")
        if _pf_art_count:
            logger.info(f"  🧹 Post-LLM artifact cleanup: {_pf_art_count} file(s)")
            console.print(f"  [green]✓[/green] Post-LLM artifact cleanup: {_pf_art_count} file(s)")
        # ── End Post-LLM artifact stripping ──────────────────────────────
        
        # Update requirements.txt if there are import errors
        if any("import" in str(e).lower() or "modulenotfound" in str(e).lower() for e in execution_errors):
            console.print(f"  [dim]Updating requirements.txt...[/dim]")
            
            # Extract missing modules from errors
            missing_pip_modules = []
            for error in execution_errors:
                if "No module named" in str(error):
                    # Extract module name from "No module named 'xxx'"
                    match = _re.search(r"No module named ['\"]([^'\"]+)['\"]", str(error))
                    if match:
                        # Take only the top-level module (e.g. 'numpy' not 'numpy.core._multiarray_umath')
                        raw_mod = match.group(1).split(".")[0]
                        # Skip private/internal modules (e.g. _bisect, _thread)
                        if raw_mod.startswith("_"):
                            continue
                        # Skip stdlib modules
                        if raw_mod.lower() in _STDLIB_MODULES:
                            continue
                        # Determine if this is a LOCAL project module (not a pip package)
                        # A module is local if it's NOT a known third-party package AND
                        # its name is a simple snake_case identifier (typical local file name)
                        is_known_pip = raw_mod in _IMPORT_TO_PKG or raw_mod in _IMPORT_TO_PKG.values()
                        # Hard guard: NEVER create stubs for well-known third-party packages
                        _NEVER_STUB = {
                            "flask", "django", "fastapi", "uvicorn", "starlette",
                            "pytest", "requests", "httpx", "aiohttp", "redis",
                            "celery", "sqlalchemy", "pydantic", "click", "typer",
                            "rich", "colorama", "tqdm", "numpy", "pandas", "scipy",
                            "torch", "tensorflow", "transformers", "boto3", "paramiko",
                            "jinja2", "websockets", "cryptography", "jwt", "pyjwt",
                            "kombu", "dramatiq", "rq", "gunicorn", "marshmallow",
                            "alembic", "pymongo", "psycopg2", "matplotlib", "seaborn",
                            "PIL", "cv2", "sklearn", "yaml", "bs4",
                        }
                        if raw_mod.lower() in _NEVER_STUB:
                            is_known_pip = True
                        # Also check if module file already exists (or should exist) in project
                        local_file_key = raw_mod + ".py"
                        is_local = not is_known_pip and local_file_key not in fixed_files
                        if is_local:
                            # Generate a stub .py file for the missing local module
                            stub_lines = [f'"""Auto-generated stub module: {raw_mod}"""\n']
                            # Scan all source files to find what symbols are imported from this module
                            imported_symbols: list = []
                            for _code_content in fixed_files.values():
                                for _m in _re.finditer(
                                    rf"from\s+{_re.escape(raw_mod)}\s+import\s+([^\n]+)",
                                    _code_content
                                ):
                                    for sym in _m.group(1).split(","):
                                        sym = sym.strip().split(" as ")[0].strip()
                                        if sym and sym != "*" and sym not in imported_symbols:
                                            imported_symbols.append(sym)
                            if imported_symbols:
                                stub_lines.append("")
                                for sym in imported_symbols:
                                    # V15 FIX: Generate callable stubs, not None
                                    if sym and sym[0].isupper():
                                        stub_lines.append(f"class {sym}:\n    pass  # TODO: implement")
                                    else:
                                        stub_lines.append(f"def {sym}(*args, **kwargs):\n    pass  # TODO: implement")
                            else:
                                stub_lines.append("# TODO: add module contents")
                            fixed_files[local_file_key] = "\n".join(stub_lines) + "\n"
                            console.print(f"  [yellow]⚠️[/yellow]  Created stub {local_file_key} (local module, not a pip package)")
                        else:
                            # It's a known third-party pip package
                            pkg = _IMPORT_TO_PKG.get(raw_mod, raw_mod)
                            missing_pip_modules.append(pkg)
            
            if missing_pip_modules:
                current_reqs = fixed_files.get("requirements.txt", "")
                new_reqs = current_reqs.strip()
                for module in missing_pip_modules:
                    if module not in new_reqs:
                        new_reqs += f"\n{module}"
                fixed_files["requirements.txt"] = new_reqs.strip()
                console.print(f"  [green]✓[/green] Added missing pip dependencies: {', '.join(missing_pip_modules)}")
        
        logger.info(f"✅ Fixed {len(fixed_files)} files")

        # ── AST-based cross-file import repair (same as in code_generation) ──
        # After LLM fixes, imports may be wrong again.  Deterministically verify.
        import ast as _ast_fix
        _py_fixed = {k: v for k, v in fixed_files.items() if k.endswith(".py") and v.strip()}
        _fix_stems = {fn.rsplit(".", 1)[0] for fn in _py_fixed}
        if len(_py_fixed) >= 2 and len(_fix_stems) >= 2:
            # Build export map
            _fx_exports: dict = {}
            for _fxn, _fxc in _py_fixed.items():
                _fxs = _fxn.rsplit(".", 1)[0]
                try:
                    _fxt = _ast_fix.parse(_fxc)
                    _fxnames = set()
                    for _nd in _ast_fix.iter_child_nodes(_fxt):
                        if isinstance(_nd, (_ast_fix.ClassDef, _ast_fix.FunctionDef, _ast_fix.AsyncFunctionDef)):
                            _fxnames.add(_nd.name)
                        elif isinstance(_nd, _ast_fix.Assign):
                            for _tg in _nd.targets:
                                if isinstance(_tg, _ast_fix.Name):
                                    _fxnames.add(_tg.id)
                        elif isinstance(_nd, _ast_fix.AnnAssign) and isinstance(getattr(_nd, 'target', None), _ast_fix.Name):
                            _fxnames.add(_nd.target.id)
                    _fx_exports[_fxs] = _fxnames
                except SyntaxError:
                    _fx_exports[_fxs] = set()
            # Scan and fix mismatched cross-file imports
            # Also catch imports from non-existent local modules
            _STDLIB_FIX = {
                "os", "sys", "json", "math", "re", "io", "abc", "copy", "time",
                "datetime", "logging", "warnings", "enum", "typing", "pathlib",
                "functools", "collections", "itertools", "dataclasses", "random",
                "argparse", "textwrap", "string", "struct", "hashlib", "base64",
                "unittest", "pytest", "torch", "numpy", "scipy", "sklearn",
                "matplotlib", "pandas", "tqdm", "rich", "requests", "flask",
                "fastapi", "pydantic", "transformers", "datasets", "PIL",
                "cv2", "tensorflow", "jax", "einops", "wandb", "hydra",
                "omegaconf", "yaml", "toml", "dotenv", "click", "typer",
                "__future__", "ast", "inspect", "importlib", "contextlib",
                "concurrent", "multiprocessing", "threading", "asyncio",
                "subprocess", "signal", "atexit", "gc", "traceback",
            }
            _fix_import_count = 0
            for _fxn, _fxc in list(_py_fixed.items()):
                _fxs = _fxn.rsplit(".", 1)[0]
                _fxlines = _fxc.split("\n")
                _fxchanged = False
                for _fli, _fl in enumerate(_fxlines):
                    _fm = _re.match(r"^(\s*from\s+)\.?(\w+)(\s+import\s+)(.+?)(\s*#.*)?$", _fl)
                    if not _fm:
                        continue
                    _fprefix, _fsrc, _fkw, _fnames, _fcomm = _fm.group(1), _fm.group(2), _fm.group(3), _fm.group(4), _fm.group(5) or ""
                    _fprefix = _re.sub(r"from\s+\.\s*", "from ", _fprefix)
                    if _fsrc == _fxs:
                        continue  # self-import

                    # Case A: module exists as generated file
                    if _fsrc in _fix_stems:
                        _fsrc_exports = _fx_exports.get(_fsrc, set())
                        _fimported = [n.strip().split(" as ")[0].strip() for n in _fnames.split(",")]
                        _fmissing = [n for n in _fimported if n and n not in _fsrc_exports]
                        if not _fmissing:
                            continue
                    # Case B: module does NOT exist as a generated file (and not stdlib)
                    elif _fsrc not in _STDLIB_FIX:
                        _fimported = [n.strip().split(" as ")[0].strip() for n in _fnames.split(",")]
                        _fmissing = list(_fimported)
                        logger.warning(f"  ⚠️  Post-fix: {_fxn} imports from non-existent '{_fsrc}' — fixing")
                    else:
                        continue
                    for _fmn in _fmissing:
                        _factual = None
                        for _fcs, _fce in _fx_exports.items():
                            if _fmn in _fce and _fcs != _fxs:
                                _factual = _fcs
                                break
                        if _factual and _factual != _fsrc:
                            if len(_fimported) == 1:
                                _fxlines[_fli] = f"{_fprefix}{_factual}{_fkw}{_fnames}{_fcomm}"
                            else:
                                _frem = [n for n in _fnames.split(",") if _fmn not in n]
                                _fxlines[_fli] = f"{_fprefix}{_fsrc}{_fkw}{', '.join(n.strip() for n in _frem)}{_fcomm}"
                                _fxlines.insert(_fli + 1, f"{_fprefix}{_factual}{_fkw}{_fmn}")
                            _fxchanged = True
                            _fix_import_count += 1
                            logger.info(f"  🔧 Post-fix import repair: {_fxn}: '{_fmn}' → import from {_factual}.py")
                        elif _factual is None:
                            _fxlines[_fli] = f"# REMOVED ('{_fmn}' not in any project file): {_fl.strip()}"
                            _fxchanged = True
                            _fix_import_count += 1
                if _fxchanged:
                    fixed_files[_fxn] = "\n".join(_fxlines)
            if _fix_import_count:
                logger.info(f"  ✅ Post-fix import validator: {_fix_import_count} cross-file import fix(es)")
                console.print(f"  [green]✓[/green] Import validator: {_fix_import_count} cross-file import fix(es)")
        # ──────────────────────────────────────────────────────────────────────

        # ── Strip ALL remaining relative imports in fixed files ───────────────
        # LLM fixes often re-introduce `from .module import X` which fails
        # when running `python main.py` (project is NOT a Python package).
        _py_module_names_fix = {f[:-3] for f in fixed_files if f.endswith(".py")}
        _rel_total = 0
        for _rf_name, _rf_code in list(fixed_files.items()):
            if not _rf_name.endswith(".py"):
                continue
            _rf_lines = []
            _rf_count = 0
            for _rf_line in _rf_code.splitlines():
                _rf_m = _re.match(r"^(\s*from\s+)\.(\w+)(\s+import\s+.*)$", _rf_line)
                if _rf_m:
                    _rf_mod = _rf_m.group(2)
                    if _rf_mod in _py_module_names_fix:
                        _rf_lines.append(f"{_rf_m.group(1)}{_rf_m.group(2)}{_rf_m.group(3)}")
                    else:
                        _rf_lines.append(f"# REMOVED phantom relative import: {_rf_line.strip()}")
                    _rf_count += 1
                else:
                    _rf_lines.append(_rf_line)
            if _rf_count:
                fixed_files[_rf_name] = "\n".join(_rf_lines)
                _rel_total += _rf_count
        if _rel_total:
            logger.info(f"  🔧 Converted {_rel_total} relative import(s) → absolute in fixed files")
            console.print(f"  [green]✓[/green] Converted {_rel_total} relative import(s) → absolute")

        # ── Flatten dotted package imports in fixed files ─────────────────────
        _fix_dotted_total = _fix_dotted_local_imports(fixed_files, "code_fix")
        if _fix_dotted_total:
            logger.info(f"  🔧 Flattened {_fix_dotted_total} dotted package import(s) in fixed files")
            console.print(f"  [green]✓[/green] Flattened {_fix_dotted_total} dotted package import(s)")
        # ──────────────────────────────────────────────────────────────────────

        console.print(f"\n[green]✅ Code fixes generated. Re-testing...[/green]\n")
        
        # ── SOTA: Reflexion Rollback Check ────────────────────────────────
        # Count syntax errors in the fixed files. If we introduced MORE
        # syntax errors than before, rollback to the snapshot.
        _post_fix_syntax_errors = 0
        for _pf_name, _pf_code in fixed_files.items():
            if _pf_name.endswith(".py") and _pf_code.strip():
                try:
                    compile(_pf_code, _pf_name, "exec")
                except SyntaxError:
                    _post_fix_syntax_errors += 1

        if _post_fix_syntax_errors > _snapshot_syntax_errors:
            logger.warning(
                f"  ⚠️  ROLLBACK: Fix introduced {_post_fix_syntax_errors} syntax errors "
                f"(was {_snapshot_syntax_errors}). Reverting to pre-fix snapshot."
            )
            console.print(
                f"  [red]⚠️  Rollback: fix worsened code "
                f"({_snapshot_syntax_errors} → {_post_fix_syntax_errors} syntax errors) "
                f"— reverting[/red]"
            )
            fixed_files = _snapshot_files  # Revert!
        elif _post_fix_syntax_errors < _snapshot_syntax_errors:
            logger.info(
                f"  ✅ Fix improved: {_snapshot_syntax_errors} → {_post_fix_syntax_errors} syntax errors"
            )

        # ── Post-fix dangling reference check ────────────────────────────
        # When the fix loop comments out an import (e.g. `from colorama import init`)
        # but leaves calls to the imported name (e.g. `init(autoreset=True)`),
        # the code will NameError at runtime. Detect and remove these orphans.
        import re as _re_dr
        _dr_fix_count = 0
        for _dr_fname, _dr_code in list(fixed_files.items()):
            if not _dr_fname.endswith(".py") or not _dr_code:
                continue
            _dr_lines = _dr_code.splitlines()
            # Find names that were commented-out imports (our specific pattern)
            _commented_names = set()
            for _dl in _dr_lines:
                _cm = _re_dr.match(r'^# REMOVED \(.*?\):\s*from\s+\S+\s+import\s+(.+)', _dl)
                if _cm:
                    for _name in _cm.group(1).split(','):
                        _name = _name.strip().split(' as ')[-1].strip()
                        if _name and _name.isidentifier():
                            _commented_names.add(_name)
            if not _commented_names:
                continue
            # Check if any of those names are still used (not in comments/strings)
            _new_lines = []
            _changed = False
            for _dl in _dr_lines:
                _stripped = _dl.strip()
                if _stripped.startswith('#'):
                    _new_lines.append(_dl)
                    continue
                _has_orphan = False
                for _cn in _commented_names:
                    # Match bare calls like `init(...)` or assignments like `x = init(...)`
                    if _re_dr.search(rf'\b{_re_dr.escape(_cn)}\s*\(', _stripped):
                        _has_orphan = True
                        break
                if _has_orphan:
                    _new_lines.append(f'# REMOVED (dangling after import removal): {_dl.strip()}')
                    _changed = True
                    _dr_fix_count += 1
                else:
                    _new_lines.append(_dl)
            if _changed:
                fixed_files[_dr_fname] = '\n'.join(_new_lines)
        if _dr_fix_count:
            logger.info(f"  ✅ Dangling reference cleanup: {_dr_fix_count} orphaned call(s) commented out")
            console.print(f"  [green]✓[/green] Dangling reference cleanup: {_dr_fix_count} orphaned call(s)")
        # ── End Rollback + Dangling Ref Check ────────────────────────────

        # ── Post-LLM: Encoding Sanitizer (uses shared _EMOJI_TO_ASCII) ──
        _post_count = _sanitize_emoji(fixed_files, "post-LLM-final")
        if _post_count:
            logger.info(f"  ✅ Post-LLM encoding sanitizer: cleaned {_post_count} file(s)")
            console.print(f"  [green]✓[/green] Post-LLM encoding sanitizer: {_post_count} file(s) cleaned")
        # ── End Post-LLM Encoding Sanitizer ──────────────────────────────

        # ── Post-LLM: Final Artifact Stripper ────────────────────────────
        _post_art = _sanitize_llm_artifacts(fixed_files, "post-LLM-final")
        if _post_art:
            logger.info(f"  ✅ Post-LLM artifact stripper: cleaned {_post_art} file(s)")
            console.print(f"  [green]✓[/green] Post-LLM artifact stripper: {_post_art} file(s) cleaned")
        # ── End Post-LLM Final Artifact Stripper ─────────────────────────

        return {
            "current_stage": "code_fixed",
            "generated_code": {"files": _flatten_file_keys(fixed_files, "code_fixing")},
            "fix_attempts": fix_attempts + 1,
            "_prev_error_hashes": _all_hashes,
            "_auto_fixed_errors": list(state.get("_auto_fixed_errors", [])) + _auto_fixed_this_round,
        }
    
    except Exception as e:
        logger.error(f"Code fixing failed: {e}")
        console.print(f"\n[red]❌ Fixing failed: {e}[/red]\n")
        return {
            "current_stage": "fixing_error",
            "errors": [f"Fixing failed: {str(e)}"],
            "fix_attempts": state.get("fix_attempts", 0) + 1
        }


# ============================================
# Node 9: Git Publishing
# ============================================

async def pipeline_self_eval_node(state: AutoGITState) -> Dict[str, Any]:
    """
    Node 9.5: Pipeline Self-Evaluation

    After code passes tests, holistically evaluate whether the generated solution
    actually fulfils the original idea / requirements.

    Scores 0-10 across:
      Completeness  — every planned file exists with real code (no stubs / TODOs)
      Correctness   — main.py runtime result, known errors from test_results
      Alignment     — code addresses the stated idea / selected problem
      Code quality  — no magic strings, error handling present, entry-point guard

    If overall score < 6 and self_eval_attempts < MAX_SELF_EVAL → route back to
    code_fixing with targeted improvement instructions injected into test_results.
    Otherwise → approve for git publishing.
    """
    logger.info("🔬 Pipeline Self-Eval Node")

    MAX_SELF_EVAL = 3  # Maximum self-eval reruns
    MAX_FIX_ATTEMPTS_CAP = 8  # Hard ceiling — no node may push max_fix_attempts above this
    self_eval_attempts: int = state.get("self_eval_attempts", 0)  # type: ignore[assignment]

    idea             = state.get("idea", "")
    selected_problem = state.get("selected_problem", "") or ""
    solution         = state.get("final_solution") or {}
    generated_code   = state.get("generated_code") or {}
    files: Dict[str, str] = generated_code.get("files", {}) if isinstance(generated_code, dict) else {}
    existing_tests   = state.get("test_results") or {}

    from rich.console import Console as _RCSE
    _console = _RCSE()
    _console.print(f"\n  [bold cyan]🔬 Self-Evaluation Pass {self_eval_attempts + 1}/{MAX_SELF_EVAL}[/bold cyan]")

    if not files:
        logger.warning("Self-eval: no files — approving immediately")
        _console.print("  [dim yellow]No files found — skipping eval, routing to publish[/dim yellow]")
        return {"current_stage": "self_eval_approved", "self_eval_score": 0.0,
                "self_eval_attempts": self_eval_attempts + 1}

    # ── Build compact code summary for the LLM evaluator ─────────────────────
    # Send full files for short files, truncate only if very large
    MAX_LINES_PER_FILE = 500   # generous — need to see full implementations
    file_summaries: List[str] = []
    for fname, fcode in files.items():
        code_str = fcode if isinstance(fcode, str) else ""
        lines = code_str.splitlines()
        preview = "\n".join(lines[:MAX_LINES_PER_FILE])
        if len(lines) > MAX_LINES_PER_FILE:
            preview += f"\n... [{len(lines) - MAX_LINES_PER_FILE} more lines] ..."
        file_summaries.append(f"=== {fname} ({len(lines)} lines) ===\n{preview}")
    code_summary = "\n\n".join(file_summaries)

    # ── Summarise what the test run found ─────────────────────────────────────
    runtime_context = ""
    if isinstance(existing_tests, dict):
        exec_errors = existing_tests.get("execution_errors", [])
        if exec_errors:
            runtime_context = "Known runtime errors from testing:\n" + "\n".join(
                f"  - {e}" for e in exec_errors
            )
        elif existing_tests.get("tests_passed") or state.get("tests_passed"):
            runtime_context = "Test suite passed (all automated checks OK)."
        else:
            runtime_context = "Test suite result: mixed (some checks failed)."

    try:
        llm = get_fallback_llm("powerful")

        eval_prompt = (
            "You are a senior code reviewer evaluating automatically generated code.\n\n"
            f"ORIGINAL IDEA:\n{idea}\n\n"
            f"PROBLEM BEING SOLVED:\n{selected_problem}\n\n"
            f"CHOSEN APPROACH: {solution.get('approach_name', 'N/A')}\n"
            f"KEY INNOVATION:  {solution.get('key_innovation', 'N/A')}\n\n"
            f"GENERATED FILES (first {MAX_LINES_PER_FILE} lines each):\n{code_summary}\n\n"
            f"RUNTIME STATUS:\n{runtime_context or 'Unknown'}\n\n"
            "Score the output 0-10 on each dimension and return ONLY valid JSON:\n"
            "{\n"
            '  "completeness":  {"score": 0-10, "issues": ["..."]},\n'
            '  "correctness":   {"score": 0-10, "issues": ["..."]},\n'
            '  "alignment":     {"score": 0-10, "issues": ["..."]},\n'
            '  "code_quality":  {"score": 0-10, "issues": ["..."]},\n'
            '  "overall_score": 0-10,\n'
            '  "verdict":       "approved" or "needs_work",\n'
            '  "priority_fixes": ["top-3 most impactful fixes if needs_work, else []"]\n'
            "}\n"
            'verdict must be "needs_work" if overall_score < 6.'
        )

        messages = [HumanMessage(content=eval_prompt)]
        response = await llm.ainvoke(messages)

        import json as _jse, re as _rese
        raw = response.content.strip()
        raw = _rese.sub(r"^```[a-z]*\n?", "", raw)
        raw = _rese.sub(r"\n?```$", "", raw.strip())
        eval_result = _jse.loads(raw)

        overall_score: float = float(eval_result.get("overall_score", 5))
        verdict: str         = eval_result.get("verdict", "approved")
        priority_fixes: List[str] = eval_result.get("priority_fixes", [])

        # ── Display scorecard ─────────────────────────────────────────────────
        s_color = "green" if overall_score >= 7 else ("yellow" if overall_score >= 5 else "red")
        _console.print(f"  [bold]Overall score:[/bold] [{s_color}]{overall_score:.1f}/10[/{s_color}]  "
                       f"verdict=[bold]{verdict}[/bold]")
        for dim in ("completeness", "correctness", "alignment", "code_quality"):
            d = eval_result.get(dim, {})
            s = d.get("score", "?")
            issues = d.get("issues", [])
            issue_str = f"  ⚠ {issues[0]}" if issues else ""
            d_color = "green" if isinstance(s, (int, float)) and s >= 7 else (
                      "yellow" if isinstance(s, (int, float)) and s >= 5 else "red")
            _console.print(f"    {dim:<16} [{d_color}]{s}/10[/{d_color}]{issue_str}")

        logger.info(f"  Self-eval: {overall_score}/10  verdict={verdict}  "
                    f"attempt={self_eval_attempts + 1}/{MAX_SELF_EVAL}")

        # ── Route decision ────────────────────────────────────────────────────
        # Re-loop if score is below acceptable (< 6) AND we haven't exhausted attempts
        if verdict == "needs_work" and overall_score < 6 and (self_eval_attempts + 1) < MAX_SELF_EVAL:
            fix_guidance = (
                "SELF-EVAL FEEDBACK — address these before re-testing:\n"
                + "\n".join(f"  {i}. {fix}" for i, fix in enumerate(priority_fixes, 1))
            )
            if runtime_context and "error" in runtime_context.lower():
                fix_guidance += f"\n\nRUNTIME ERRORS:\n{runtime_context}"

            # Inject guidance so code_fixing_node can act on it
            updated_tests = dict(existing_tests) if isinstance(existing_tests, dict) else {}
            updated_tests["self_eval_fixes"] = fix_guidance
            updated_tests["self_eval_score"] = overall_score
            _existing_se_errors = updated_tests.get("execution_errors", [])
            _existing_se_errors.extend([f"[SELF-EVAL] {fix}" for fix in priority_fixes])
            updated_tests["execution_errors"] = _existing_se_errors

            _console.print(f"\n  [yellow]⟳  Score {overall_score:.1f} < 6 — routing back for targeted fixes "
                           f"(pass {self_eval_attempts + 1}/{MAX_SELF_EVAL})[/yellow]")
            if priority_fixes:
                _console.print("  [dim]Priority fixes: " + "; ".join(priority_fixes[:3]) + "[/dim]")

            return {
                "current_stage": "self_eval_needs_regen",
                "self_eval_score": overall_score,
                "self_eval_attempts": self_eval_attempts + 1,
                "test_results": updated_tests,
                "tests_passed": False,  # force re-test after fixing
                # Grant exactly ONE more fix attempt by raising the cap.
                # Old: fix_attempts - 1 → could reset to 0 creating infinite loop.
                # New: bump max_fix_attempts by 1, hard-capped at MAX_FIX_ATTEMPTS_CAP.
                "max_fix_attempts": min(state.get("max_fix_attempts", 3) + 1, MAX_FIX_ATTEMPTS_CAP),
            }

        _console.print(f"\n  [green]✅ Approved for publishing (score {overall_score:.1f}/10)[/green]")
        return {
            "current_stage": "self_eval_approved",
            "self_eval_score": overall_score,
            "self_eval_attempts": self_eval_attempts + 1,
        }

    except Exception as e:
        logger.error(f"Self-eval LLM failed ({e}) — marking as needs_work (not silently approving)")
        _console.print(f"  [red]⚠️ Self-eval error ({e}) — flagging for review[/red]")
        # On first eval failure, route back for one more try rather than
        # silently approving potentially broken code.
        if (self_eval_attempts + 1) < MAX_SELF_EVAL:
            return {
                "current_stage": "self_eval_needs_regen",
                "self_eval_score": 0.0,
                "self_eval_attempts": self_eval_attempts + 1,
                "tests_passed": False,
                "max_fix_attempts": min(state.get("max_fix_attempts", 3) + 1, MAX_FIX_ATTEMPTS_CAP),
            }
        # Exhausted retries — approve but BLOCK publishing (fail-safe)
        logger.warning(
            "\u26a0\ufe0f  UNVERIFIED APPROVAL: Self-eval exhausted all retries due to LLM errors. "
            "Blocking auto-publish. Code quality is UNKNOWN."
        )
        return {
            "current_stage": "self_eval_approved",
            "self_eval_score": 0.0,
            "self_eval_attempts": self_eval_attempts + 1,
            "tests_passed": False,  # Fail-safe: don't publish unverified code
            "warnings": [f"UNVERIFIED_APPROVAL: Self-eval LLM failed {MAX_SELF_EVAL} times ({e})."],
        }


# ============================================
# Node 9.9: Goal Achievement Evaluation
# ============================================

async def goal_achievement_eval_node(state: AutoGITState) -> Dict[str, Any]:
    """
    Node 9.9: Goal Achievement Evaluation

    Compares the user's original idea against the generated code on a
    requirement-by-requirement basis.  Unlike pipeline_self_eval (Node 9.5)
    which looks at generic quality, this node answers:

        "Did we actually build what the user asked for?"

    For each discrete requirement extracted from the user's prompt it produces:
        ✅ IMPLEMENTED  — feature present with real logic
        ⚠️  PARTIAL      — feature mentioned but stub / incomplete
        ❌ MISSING       — not found in the code at all

    Decision logic (MAX 2 regen loops):
        • If ≥80% requirements are IMPLEMENTED → approved, publish
        • Otherwise → inject unmet requirements as focused fix targets and
          loop back to code_fixing (up to goal_eval_attempts < 2)
    """
    logger.info("🎯 Goal Achievement Evaluation Node")

    MAX_GOAL_EVAL = 3
    MAX_FIX_ATTEMPTS_CAP = 8  # Hard ceiling — mirrors self_eval cap
    goal_eval_attempts: int = state.get("goal_eval_attempts", 0)  # type: ignore[assignment]

    idea              = state.get("idea", "")
    user_requirements = state.get("user_requirements", "") or ""
    requirements      = state.get("requirements") or {}
    generated_code    = state.get("generated_code") or {}
    files: Dict[str, str] = generated_code.get("files", {}) if isinstance(generated_code, dict) else {}

    from rich.console import Console as _GCon
    from rich.table import Table as _GTab
    _console = _GCon()
    _console.print(f"\n  [bold magenta]🎯 Goal Achievement Eval — Pass {goal_eval_attempts + 1}/{MAX_GOAL_EVAL}[/bold magenta]")

    if not files:
        logger.warning("Goal eval: no files — skipping")
        return {"current_stage": "goal_eval_approved", "goal_eval_attempts": goal_eval_attempts + 1}

    # ── Build full code context ──────────────────────────────────────────────
    MAX_LINES = 500
    code_blocks: List[str] = []
    for fname, fcode in files.items():
        code_str = fcode if isinstance(fcode, str) else ""
        lines = code_str.splitlines()
        preview = "\n".join(lines[:MAX_LINES])
        if len(lines) > MAX_LINES:
            preview += f"\n... [{len(lines) - MAX_LINES} more lines] ..."
        code_blocks.append(f"=== {fname} ({len(lines)} lines) ===\n{preview}")
    code_context = "\n\n".join(code_blocks)

    # ── Build requirements context ───────────────────────────────────────────
    req_context = f"USER IDEA:\n{idea}\n"
    if user_requirements:
        req_context += f"\nADDITIONAL REQUIREMENTS:\n{user_requirements}\n"
    if requirements:
        import json as _gjson_req
        req_context += f"\nSTRUCTURED REQUIREMENTS:\n{_gjson_req.dumps(requirements, indent=2, default=str)}\n"

    try:
        llm = get_fallback_llm("powerful")

        eval_prompt = (
            "You are a meticulous QA engineer. Your job is to verify whether the "
            "generated code ACTUALLY implements every feature the user asked for.\n\n"
            f"{req_context}\n"
            f"GENERATED CODE:\n{code_context}\n\n"
            "INSTRUCTIONS:\n"
            "1. Extract every discrete requirement/feature from the user's idea.\n"
            "   Be thorough — if they said 'retry with exponential backoff', that's\n"
            "   one requirement, 'dead letter queue' is another, etc.\n"
            "2. For EACH requirement, check the actual code (not just comments/docstrings)\n"
            "   and classify as:\n"
            '   - "implemented" — real working logic exists\n'
            '   - "partial" — mentioned but stub/TODO/incomplete\n'
            '   - "missing" — not found anywhere\n'
            "3. Check if main.py provides a runnable demo that shows each feature working.\n"
            "4. Check if main.py produces visible terminal output when run.\n\n"
            "Return ONLY valid JSON (no markdown fences):\n"
            "{\n"
            '  "requirements": [\n'
            '    {"name": "short requirement name", "status": "implemented|partial|missing",\n'
            '     "evidence": "which file/function implements it, or why missing",\n'
            '     "importance": "critical|important|nice-to-have"}\n'
            "  ],\n"
            '  "demo_runnable": true/false,\n'
            '  "demo_has_output": true/false,\n'
            '  "overall_pct_implemented": 0-100,\n'
            '  "summary": "1-2 sentence summary of what was built vs what was asked"\n'
            "}\n"
        )

        messages = [HumanMessage(content=eval_prompt)]
        response = await llm.ainvoke(messages)

        import re as _gre
        import json as _gjson
        raw = response.content.strip()
        raw = _gre.sub(r"^```[a-z]*\n?", "", raw)
        raw = _gre.sub(r"\n?```$", "", raw.strip())
        # Handle trailing commas in JSON (LLM quirk)
        raw = _gre.sub(r",\s*([}\]])", r"\1", raw)
        eval_result = _gjson.loads(raw)

        reqs = eval_result.get("requirements", [])
        pct = float(eval_result.get("overall_pct_implemented", 0))
        demo_ok = eval_result.get("demo_runnable", False)
        demo_output = eval_result.get("demo_has_output", False)
        summary = eval_result.get("summary", "")

        # ── Display requirement checklist ────────────────────────────────────
        table = _GTab(title="Goal Achievement Report", show_lines=True)
        table.add_column("Status", width=4, justify="center")
        table.add_column("Requirement", min_width=25)
        table.add_column("Evidence", min_width=30)
        table.add_column("Priority", width=12)

        implemented = partial = missing = 0
        unmet_requirements: List[str] = []

        for req in reqs:
            status = req.get("status", "missing")
            name = req.get("name", "?")
            evidence = req.get("evidence", "")
            importance = req.get("importance", "important")

            if status == "implemented":
                icon = "✅"
                implemented += 1
            elif status == "partial":
                icon = "⚠️"
                partial += 1
                unmet_requirements.append(f"[PARTIAL] {name}: {evidence}")
            else:
                icon = "❌"
                missing += 1
                unmet_requirements.append(f"[MISSING] {name}: {evidence}")

            table.add_row(icon, name, evidence[:60], importance)

        _console.print(table)

        total = max(implemented + partial + missing, 1)
        impl_pct = (implemented / total) * 100

        color = "green" if impl_pct >= 80 else ("yellow" if impl_pct >= 50 else "red")
        _console.print(f"\n  [bold]Requirements:[/bold] [{color}]{implemented}/{total} implemented ({impl_pct:.0f}%)[/{color}]"
                       f"  |  ⚠️ {partial} partial  |  ❌ {missing} missing")
        _console.print(f"  [bold]Demo runnable:[/bold] {'✅' if demo_ok else '❌'}   "
                       f"[bold]Has output:[/bold] {'✅' if demo_output else '❌'}")
        _console.print(f"  [dim]{summary}[/dim]")

        logger.info(f"  Goal eval: {implemented}/{total} implemented ({impl_pct:.0f}%), "
                    f"demo={'ok' if demo_ok else 'no'}, attempt={goal_eval_attempts + 1}/{MAX_GOAL_EVAL}")

        # ── Build GOAL_REPORT for the output directory ───────────────────────
        report_lines = [
            "# 🎯 Goal Achievement Report\n",
            f"**User Idea:** {idea}\n",
            f"**Implementation Rate:** {implemented}/{total} ({impl_pct:.0f}%)\n",
            f"**Demo Runnable:** {'Yes' if demo_ok else 'No'}\n",
            f"**Demo Has Output:** {'Yes' if demo_output else 'No'}\n",
            f"\n## Requirements Checklist\n",
        ]
        for req in reqs:
            s = req.get("status", "missing")
            icon = "✅" if s == "implemented" else ("⚠️" if s == "partial" else "❌")
            report_lines.append(f"- {icon} **{req.get('name', '?')}** ({s}) — {req.get('evidence', '')}")
        report_lines.append(f"\n## Summary\n{summary}\n")
        goal_report_md = "\n".join(report_lines)

        # Inject GOAL_REPORT.md into generated files
        updated_code = dict(generated_code)
        updated_files = dict(files)
        updated_files["GOAL_REPORT.md"] = goal_report_md
        updated_code["files"] = updated_files

        # ── Route decision ───────────────────────────────────────────────────
        # Approve if ≥80% implemented OR exhausted attempts
        if impl_pct >= 80 or (goal_eval_attempts + 1) >= MAX_GOAL_EVAL:
            if impl_pct >= 80:
                _console.print(f"\n  [green]✅ Goal achieved — {impl_pct:.0f}% requirements implemented[/green]")
            else:
                _console.print(f"\n  [yellow]⚠️  Max goal-eval attempts reached ({MAX_GOAL_EVAL}) — "
                               f"publishing with {impl_pct:.0f}% coverage[/yellow]")
            return {
                "current_stage": "goal_eval_approved",
                "goal_eval_attempts": goal_eval_attempts + 1,
                "goal_eval_report": eval_result,
                "generated_code": updated_code,
            }

        # ── Not enough requirements met — loop back with focused targets ─────
        fix_guidance = (
            "GOAL ACHIEVEMENT EVAL FAILED — the following requirements are NOT properly implemented.\n"
            "Your #1 priority is to implement these MISSING/PARTIAL features with real working code.\n"
            "Do NOT just add comments or TODOs — write the actual implementation.\n\n"
            "UNMET REQUIREMENTS:\n"
            + "\n".join(f"  {i+1}. {r}" for i, r in enumerate(unmet_requirements))
            + "\n\nAlso ensure main.py demonstrates ALL features with visible terminal output."
        )

        updated_tests = dict(state.get("test_results") or {})
        updated_tests["goal_eval_fixes"] = fix_guidance
        _existing_ge_errors = updated_tests.get("execution_errors", [])
        _existing_ge_errors.extend([f"[GOAL-EVAL] {r}" for r in unmet_requirements[:10]])
        updated_tests["execution_errors"] = _existing_ge_errors

        _console.print(f"\n  [yellow]⟳  Only {impl_pct:.0f}% implemented — routing back to fix "
                       f"{len(unmet_requirements)} unmet requirements "
                       f"(pass {goal_eval_attempts + 1}/{MAX_GOAL_EVAL})[/yellow]")

        return {
            "current_stage": "goal_eval_needs_work",
            "goal_eval_attempts": goal_eval_attempts + 1,
            "goal_eval_report": eval_result,
            "generated_code": updated_code,
            "test_results": updated_tests,
            "tests_passed": False,
            # Grant one more fix attempt by raising the cap (hard-capped)
            "max_fix_attempts": min(state.get("max_fix_attempts", 3) + 1, MAX_FIX_ATTEMPTS_CAP),
        }

    except Exception as e:
        logger.error(f"Goal eval LLM failed ({e}) — marking as needs_work (not silently approving)")
        _console.print(f"  [red]⚠️ Goal eval error ({e}) — flagging for review[/red]")
        # On first eval failure, route back for one more try
        if (goal_eval_attempts + 1) < MAX_GOAL_EVAL:
            return {
                "current_stage": "goal_eval_needs_work",
                "goal_eval_attempts": goal_eval_attempts + 1,
                "tests_passed": False,
                "max_fix_attempts": min(state.get("max_fix_attempts", 3) + 1, MAX_FIX_ATTEMPTS_CAP),
            }
        # Exhausted retries — BLOCK publishing (fail-safe, don't publish unverified code)
        logger.warning(
            "⚠️  UNVERIFIED: Goal eval exhausted all retries due to LLM errors. "
            "Blocking auto-publish. Code quality is UNKNOWN."
        )
        _console.print(
            "\n  [bold red]⚠️  UNVERIFIED: Goal eval could not complete — blocking publish (fail-safe)[/bold red]"
        )
        return {
            "current_stage": "goal_eval_approved",
            "goal_eval_attempts": goal_eval_attempts + 1,
            "tests_passed": False,  # Fail-safe: don't publish unverified code
            "warnings": [
                f"UNVERIFIED_APPROVAL: Goal eval LLM failed {MAX_GOAL_EVAL} times ({e}). "
                "Code saved locally — NOT published to GitHub."
            ],
        }


async def _post_save_smoke_test(project_dir) -> Dict[str, Any]:
    """
    Post-save smoke test: install requirements.txt (if exists) and run main.py
    in a subprocess. Returns a dict with pass/fail status and output.
    
    Uses a PROJECT-SPECIFIC venv (not the host Auto-GIT Python) to avoid
    polluting Auto-GIT's environment with project dependencies.
    """
    import subprocess
    from pathlib import Path

    console = Console()
    console.print("\n[cyan]🔬 Post-save smoke test...[/cyan]")
    result = {"passed": False, "steps": []}

    proj = Path(project_dir).resolve()  # Always use absolute path

    # Create or reuse a project-specific venv
    _smoke_venv = proj / ".smoke_venv"
    if sys.platform == "win32":
        _smoke_python = _smoke_venv / "Scripts" / "python.exe"
    else:
        _smoke_python = _smoke_venv / "bin" / "python"

    if not _smoke_venv.exists():
        try:
            subprocess.run(
                [sys.executable, "-m", "venv", str(_smoke_venv)],
                check=True, capture_output=True, timeout=60,
            )
            console.print("  ✅ Created smoke test venv")
        except Exception as e:
            console.print(f"  ⚠️  Venv creation failed: {e} — using host Python (fallback)")
            _smoke_python = Path(sys.executable)

    # Build a sanitized env (no API keys leak) — V10 FIX: comprehensive pattern matching
    _SENSITIVE_NAMES = {"GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
                        "GITHUB_TOKEN", "GH_TOKEN", "OPENAI_ORG", "AWS_ACCESS_KEY_ID",
                        "AWS_SECRET_ACCESS_KEY", "AZURE_OPENAI_KEY", "HF_TOKEN",
                        "HUGGINGFACE_TOKEN", "COHERE_API_KEY", "TOGETHER_API_KEY"}
    _SENSITIVE_PATS = ("API_KEY", "SECRET", "_TOKEN", "PASSWORD", "CREDENTIAL", "_KEY")
    _smoke_env = {}
    for k, v in __import__('os').environ.items():
        if k in _SENSITIVE_NAMES:
            continue
        k_upper = k.upper()
        if any(pat in k_upper for pat in _SENSITIVE_PATS):
            continue
        _smoke_env[k] = v
    _smoke_env["PYTHONIOENCODING"] = "utf-8"

    # Step 1: install requirements.txt if present (into project venv, NOT host)
    req_path = proj / "requirements.txt"
    if req_path.exists():
        try:
            proc = subprocess.run(
                [str(_smoke_python), "-m", "pip", "install", "-r", str(req_path), "--quiet"],
                capture_output=True, text=True, timeout=120,
                cwd=str(proj),
                env=_smoke_env,
            )
            ok = proc.returncode == 0
            result["steps"].append({"step": "pip install -r requirements.txt", "passed": ok,
                                    "stderr": proc.stderr.strip()[-200:] if not ok else ""})
            status = "✅" if ok else "⚠️"
            console.print(f"  {status} pip install -r requirements.txt")
        except Exception as e:
            result["steps"].append({"step": "pip install", "passed": False, "error": str(e)})
            console.print(f"  ⚠️  pip install failed: {e}")
    else:
        result["steps"].append({"step": "requirements.txt", "passed": True, "note": "not found (OK)"})

    # Step 2: find main entry point
    main_file = None
    for candidate in ["main.py", "app.py", "run.py"]:
        if (proj / candidate).exists():
            main_file = candidate
            break
    if not main_file:
        # Pick first .py file
        py_files = sorted(proj.glob("*.py"))
        if py_files:
            main_file = py_files[0].name

    # Step 3: run the entry point (in project venv, NOT host)
    if main_file:
        try:
            main_path = str(proj / main_file)
            proc = subprocess.run(
                [str(_smoke_python), main_path],
                capture_output=True, text=True, timeout=30,
                cwd=str(proj),
                env=_smoke_env,
            )
            ok = proc.returncode == 0
            stdout_preview = proc.stdout.strip()[:300] if proc.stdout else ""
            stderr_preview = proc.stderr.strip()[-300:] if not ok and proc.stderr else ""
            result["steps"].append({
                "step": f"python {main_file}",
                "passed": ok,
                "exit_code": proc.returncode,
                "stdout_preview": stdout_preview,
                "stderr_preview": stderr_preview,
            })
            if ok:
                console.print(f"  ✅ python {main_file} — exit 0")
                if stdout_preview:
                    for line in stdout_preview.split("\n")[:3]:
                        console.print(f"     {line}")
            else:
                console.print(f"  ❌ python {main_file} — exit {proc.returncode}")
                for line in stderr_preview.split("\n")[-3:]:
                    console.print(f"     {line}")
        except subprocess.TimeoutExpired:
            result["steps"].append({"step": f"python {main_file}", "passed": True,
                                    "note": "timeout (likely a server — OK)"})
            console.print(f"  ⏱️  python {main_file} — timeout (server/loop, OK)")
        except Exception as e:
            result["steps"].append({"step": f"python {main_file}", "passed": False, "error": str(e)})
            console.print(f"  ⚠️  Could not run {main_file}: {e}")
    else:
        result["steps"].append({"step": "find entry point", "passed": False, "note": "no .py files"})
        console.print("  ⚠️  No Python entry point found")

    # Step 4: run tests if test_main.py exists (in project venv)
    test_file = proj / "test_main.py"
    if test_file.exists():
        try:
            proc = subprocess.run(
                [str(_smoke_python), "-m", "pytest", str(test_file), "-v", "--tb=short"],
                capture_output=True, text=True, timeout=60,
                cwd=str(proj),
                env=_smoke_env,
            )
            ok = proc.returncode == 0
            result["steps"].append({"step": "pytest test_main.py", "passed": ok,
                                    "exit_code": proc.returncode})
            status = "✅" if ok else "❌"
            console.print(f"  {status} pytest test_main.py — exit {proc.returncode}")
        except Exception as e:
            result["steps"].append({"step": "pytest", "passed": False, "error": str(e)})

    # Cleanup smoke venv (don't leave garbage in output dir)
    try:
        import shutil
        if _smoke_venv.exists():
            shutil.rmtree(_smoke_venv, ignore_errors=True)
    except Exception:
        pass

    result["passed"] = all(s.get("passed", False) for s in result["steps"])
    overall = "✅ PASSED" if result["passed"] else "⚠️ ISSUES"
    console.print(f"\n  [{'green' if result['passed'] else 'yellow'}]Smoke test: {overall}[/{'green' if result['passed'] else 'yellow'}]\n")

    return result


async def git_publishing_node(state: AutoGITState) -> Dict[str, Any]:
    """
    Node 9: Publish generated code to GitHub
    
    Creates a new repository and pushes all generated code.
    Only publishes if tests passed (or if testing was skipped).
    """
    logger.info("📤 Git Publishing Node")
    
    # Check test results before publishing
    test_results = state.get("test_results", {})
    tests_passed = state.get("tests_passed", False)  # Fail-safe: default to False (never publish untested code)
    
    console = Console()
    
    if not tests_passed:
        logger.warning("⚠️  Tests failed! Skipping GitHub publishing.")
        console.print("\n[yellow]⚠️  Tests failed! Code will be saved locally only (not published to GitHub).[/yellow]")
        
        # Force local save when tests fail
        try:
            from pathlib import Path
            from datetime import datetime
            
            output_dir = Path(state.get("output_dir", "output"))
            solution = state.get("final_solution") or {}
            repo_name = _re.sub(r"[^a-z0-9-]", "", solution.get("approach_name", "auto-git-project").replace(" ", "-").lower()).strip("-") or "auto-git-project"
            project_dir = output_dir / repo_name / datetime.now().strftime("%Y%m%d_%H%M%S")
            project_dir.mkdir(parents=True, exist_ok=True)
            
            generated_code = state.get("generated_code") or {}
            files = generated_code.get("files", {})
            
            if files:
                # ── Final safety net: strip any remaining LLM artifacts ──
                _final_art = _sanitize_llm_artifacts(files, "pre-save")
                if _final_art:
                    logger.info(f"  🧹 Pre-save artifact cleanup: {_final_art} file(s)")
                    console.print(f"  [green]✓[/green] Pre-save artifact cleanup: {_final_art} file(s)")

                # Filter out shadow files (e.g. numpy.py, torch.py) that shadow real packages
                _SHADOW_SAVE = {"numpy", "torch", "scipy", "pandas", "sklearn", "tensorflow",
                                "requests", "flask", "django", "fastapi", "setuptools", "pip",
                                "pytest", "unittest", "typing", "collections", "abc"}
                for filename, content in files.items():
                    _stem = filename.rsplit(".", 1)[0] if "." in filename else filename
                    if _stem in _SHADOW_SAVE:
                        logger.warning(f"  🗑️  Skipping shadow file: {filename}")
                        continue
                    file_path = project_dir / filename
                    file_path.write_text(content, encoding="utf-8")
                    logger.info(f"  ✅ Saved {filename}")
                
                console.print(f"\n[green]✅ Code saved to:[/green] [bold cyan]{project_dir}[/bold cyan]\n")
                console.print(f"[dim]Review the code, fix any issues, then use the publish script to upload to GitHub.[/dim]\n")
                
                smoke_result = await _post_save_smoke_test(project_dir)
                
                return {
                    "current_stage": "saved_locally_tests_failed",
                    "output_path": str(project_dir),
                    "github_url": None,
                    "tests_passed": False,
                    "smoke_test": smoke_result,
                }
            else:
                logger.error("No files to save")
                return {
                    "current_stage": "no_files",
                    "errors": ["No generated files to save"]
                }
        except Exception as e:
            logger.error(f"Failed to save locally: {e}")
            return {
                "current_stage": "save_failed",
                "errors": [f"Local save failed: {str(e)}"]
            }
    
    try:
        import os
        from pathlib import Path
        from github import Github
        from datetime import datetime
        
        # Check if auto-publish is enabled
        if not state.get("auto_publish", False):
            logger.info("Auto-publish disabled, saving locally only")
            
            # Save files locally
            output_dir = Path(state.get("output_dir", "output"))
            solution = state.get("final_solution") or {}
            repo_name = _re.sub(r"[^a-z0-9-]", "", solution.get("approach_name", "auto-git-project").replace(" ", "-").lower()).strip("-") or "auto-git-project"
            project_dir = output_dir / repo_name / datetime.now().strftime("%Y%m%d_%H%M%S")
            project_dir.mkdir(parents=True, exist_ok=True)
            
            generated_code = state.get("generated_code") or {}
            files = generated_code.get("files", {})
            
            # ── Final safety net: strip any remaining LLM artifacts ──
            _final_art2 = _sanitize_llm_artifacts(files, "pre-save-local")
            if _final_art2:
                logger.info(f"  🧹 Pre-save artifact cleanup: {_final_art2} file(s)")

            # V9 FIX: Filter shadow files before saving
            _SHADOW_LOCAL = {"numpy", "torch", "scipy", "pandas", "sklearn", "tensorflow",
                            "requests", "flask", "django", "fastapi", "setuptools", "pip",
                            "pytest", "unittest", "typing", "collections", "abc"}
            for filename, content in files.items():
                _stem_l = filename.rsplit(".", 1)[0] if "." in filename else filename
                if _stem_l in _SHADOW_LOCAL:
                    logger.warning(f"  🗑️  Skipping shadow file: {filename}")
                    continue
                file_path = project_dir / filename
                file_path.write_text(content, encoding="utf-8")
                logger.info(f"  ✅ Saved {filename}")
            
            logger.info(f"✅ Code saved to: {project_dir}")
            
            # ── Post-save smoke test ─────────────────────────────────────────
            smoke_result = await _post_save_smoke_test(project_dir)
            
            return {
                "current_stage": "saved_locally",
                "output_path": str(project_dir),
                "github_url": None,
                "smoke_test": smoke_result,
            }
        
        # GitHub publishing
        github_token = os.getenv("GITHUB_TOKEN")
        if not github_token:
            logger.error("GITHUB_TOKEN not found in environment")
            return {
                "current_stage": "publishing_failed",
                "errors": ["GITHUB_TOKEN not set. Use: export GITHUB_TOKEN=your_token"]
            }
        
        solution = state.get("final_solution") or {}
        generated_code = state.get("generated_code") or {}
        files = generated_code.get("files", {})
        
        if not files:
            logger.warning("No files to publish")
            return {
                "current_stage": "no_files",
                "errors": ["No generated files to publish"]
            }
        
        # Create GitHub client
        g = Github(github_token)
        user = g.get_user()
        
        # Create repository name
        repo_name = _re.sub(r"[^a-z0-9-]", "", solution.get("approach_name", "auto-git-project").replace(" ", "-").lower()).strip("-") or "auto-git-project"
        repo_name = f"autogit-{repo_name}-{datetime.now().strftime('%Y%m%d')}"
        
        logger.info(f"  Creating repository: {repo_name}")
        
        # Create repository
        repo = user.create_repo(
            name=repo_name,
            description=f"Auto-generated implementation: {solution.get('approach_name', 'N/A')}",
            private=False,
            auto_init=False
        )
        
        logger.info(f"  ✅ Repository created: {repo.html_url}")
        
        # Create files — V9 FIX: filter shadow files
        _SHADOW_GH = {"numpy", "torch", "scipy", "pandas", "sklearn", "tensorflow",
                      "requests", "flask", "django", "fastapi", "setuptools", "pip",
                      "pytest", "unittest", "typing", "collections", "abc"}
        for filename, content in files.items():
            _stem_gh = filename.rsplit(".", 1)[0] if "." in filename else filename
            if _stem_gh in _SHADOW_GH:
                logger.warning(f"  🗑️  Skipping shadow file: {filename}")
                continue
            logger.info(f"  📤 Uploading {filename}...")
            repo.create_file(
                path=filename,
                message=f"Add {filename}",
                content=content
            )
        
        logger.info(f"✅ Published to GitHub: {repo.html_url}")
        
        return {
            "current_stage": "published",
            "github_url": repo.html_url,
            "repo_name": repo_name
        }
        
    except Exception as e:
        logger.error(f"Git publishing failed: {e}")
        
        # Fallback: save locally
        try:
            output_dir = Path(state.get("output_dir", "output"))
            solution = state.get("final_solution") or {}
            repo_name = _re.sub(r"[^a-z0-9-]", "", solution.get("approach_name", "auto-git-project").replace(" ", "-").lower()).strip("-") or "auto-git-project"
            project_dir = output_dir / repo_name / datetime.now().strftime("%Y%m%d_%H%M%S")
            project_dir.mkdir(parents=True, exist_ok=True)
            
            generated_code = state.get("generated_code") or {}
            files = generated_code.get("files", {})
            
            for filename, content in files.items():
                file_path = project_dir / filename
                file_path.write_text(content, encoding="utf-8")
            
            logger.info(f"✅ Saved locally to: {project_dir} (GitHub push failed)")
            
            return {
                "current_stage": "saved_locally_after_error",
                "output_path": str(project_dir),
                "errors": [f"GitHub publishing failed: {str(e)}"]
            }
        except Exception as save_error:
            logger.error(f"Failed to save locally: {save_error}")
            return {
                "current_stage": "publishing_failed",
                "errors": [f"Publishing failed: {str(e)}", f"Local save failed: {str(save_error)}"]
            }

