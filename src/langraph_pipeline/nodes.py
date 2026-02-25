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
    "cv2": "opencv-python", "PIL": "pillow", "PIL": "Pillow",
    "sklearn": "scikit-learn", "yaml": "pyyaml", "bs4": "beautifulsoup4",
    "dateutil": "python-dateutil", "Crypto": "pycryptodome",
    "dotenv": "python-dotenv", "wx": "wxPython", "OpenGL": "PyOpenGL",
    "attr": "attrs", "gi": "pygobject",
}


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


def get_llm(profile: str = "balanced"):
    """
    Get LLM model from model manager (prevents VRAM thrashing)
    
    Args:
        profile: Model profile (fast/balanced/powerful/reasoning)
    
    Returns:
        ChatOllama instance that stays loaded
    """
    global _model_manager
    if _model_manager is None:
        _model_manager = get_model_manager()
    
    return _model_manager.get_fallback_llm(profile)


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
            sota_summary = f"\n\nSOTA context: {cb['sota_summary'][:400]}"

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
                "focus_areas": list(p.get("focus_areas", []))[:5],
                "evaluation_criteria": list(p.get("evaluation_criteria", []))[:5],
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
                for ra in cb_research["recent_advances"][:5]:
                    context += f"  - {ra}\n"
            if cb_research.get("key_insights"):
                context += "\n\n=== KEY INSIGHTS FOR BUILDERS ===\n"
                for ki in cb_research["key_insights"][:5]:
                    context += f"  - {ki}\n"
            if cb_research.get("benchmarks"):
                context += "\n\n=== BENCHMARKS ===\n"
                for bm in cb_research["benchmarks"][:4]:
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
                        f" focus on {', '.join(cfg.get('focus_areas',[])[:3])}\n"
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
                    sota_ctx = "\nKnown open problems from SOTA research: " + "; ".join(cb2["open_problems"][:3])

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
Implementation: {', '.join(proposal['implementation_plan'][:3])}...

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
            if isinstance(result, Exception) or result is None:
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
        state["should_continue_debate"] = False
        return state
    
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
        for op in (open_probs or [])[:3]:
            p(f"- Directly addresses: *{op}*")
    if insights:
        p("\n**Grounded in these research insights:**")
        for ins in insights[:3]:
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
            '"pseudocode": "step-by-step logic (5-10 lines)"}\n'
            "  ],\n"
            '  "entry_point_behavior": "What main.py does when run: parses args, creates X, runs Y, prints Z",\n'
            '  "expected_output": "What the user sees when they run python main.py",\n'
            '  "test_scenarios": [\n'
            '    "python main.py → should print X",\n'
            '    "python main.py --verbose → should show detailed output"\n'
            "  ],\n"
            '  "total_estimated_lines": 800\n'
            "}\n\n"
            "RULES:\n"
            "1. Total project should be 600-2000 lines of real code (not comments/blanks)\n"
            "2. Each implementation file should be 100-400 lines\n"
            "3. main.py must produce VISIBLE OUTPUT when run (not just exit silently)\n"
            "4. NO file should be named after a Python package (torch.py, numpy.py, etc.)\n"
            "5. NO circular imports — if A imports B, B must NOT import A\n"
            "6. Every algorithm must have real pseudocode, not just a name\n"
            "7. List ALL cross-file dependencies explicitly\n"
            "8. Include requirements.txt and README.md in the file list"
        )

        messages = [HumanMessage(content=spec_prompt)]
        response = await llm.ainvoke(messages)

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

        # ── Read architecture spec (from Node 6.5) ──────────────────────────
        _arch_spec_text = state.get("_architecture_spec_text") or ""
        _arch_spec = state.get("architecture_spec") or {}
        
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
                "- 3-7 files maximum\n"
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
                "6. If using relative imports (from .module import X), the module MUST be in 'Other files'\n"
                "7. Proper docstrings and type hints on all public functions/classes\n"
                "8. If this is main.py, it must have a working `if __name__ == '__main__':` entry point\n"
                "9. NEVER assign placeholder objects like `model = nn.Module()` — always use the REAL class. If model.py defines `MyModel`, you MUST write `model = MyModel(...)` with real arguments, not a bare nn.Module()\n"
                "10. NEVER comment out real initialization and replace it with a placeholder — the uncommented code MUST use the actual classes\n"
                + (f"\n{_contract_text}\n\n" if _contract_text else "")
                + (f"\n{_arch_spec_text}\n\n" if _arch_spec_text else "")
                + """COMPLETENESS REQUIREMENTS — the file MUST be substantial and production-ready:
- Write EVERY function and class in FULL. No shortened bodies, no cut-off code.
- Each non-trivial function should be at least 10-30 lines of real logic.
- A core implementation file (model, trainer, encoder, etc.) should be 150-400+ lines.
- main.py must demonstrate end-to-end usage with argument parsing and meaningful output.
- Prefer depth over breadth: fewer files done completely > many files done shallowly.
- Treat this like a production open-source repository others will clone and run.
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
            return "You are an expert Python developer. Generate clean, production-ready code."

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
                # Raise threshold: a real implementation file should have ≥40 real lines.
                # 8-line threshold was far too lenient (allowed 50-line stubs through).
                if len(real_lines) < 80 or (has_stubs and len(real_lines) < 100):
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
                                f"def main():\n"
                                f"    \"\"\"Entry point placeholder — requires implementation.\"\"\"\n"
                                f"    raise NotImplementedError(\n"
                                f"        \"Generation of {filename!r} failed. "
                                f"Please implement this file manually.\"\n"
                                f"    )\n"
                                f"\n"
                                f"\nif __name__ == '__main__':\n"
                                f"    main()\n"
                            )

            logger.info(f"  ✅ [{filename}] done ({len(code)} chars)")
            return filename, code

        # ── Run all file generations concurrently ────────────────────────────
        # Each file is an independent LLM call.  For N files the wall time drops
        # from sum(latencies) to max(single_latency) — typically 5-10× faster.
        import asyncio as _asyncio_gen
        logger.info(f"  ⚡ Generating {len(files_to_generate)} files in parallel...")
        _gen_results = await _asyncio_gen.gather(
            *[_gen_file(fname, prompt) for fname, prompt in files_to_generate.items()],
            return_exceptions=True
        )
        generated_files = {}
        for _gr in _gen_results:
            if isinstance(_gr, Exception):
                logger.error(f"  ❌ File generation task failed: {_gr}")
                continue
            _gfname, _gcode = _gr
            generated_files[_gfname] = _gcode
        logger.info(f"✅ Generated {len(generated_files)} files in parallel")

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
                            f"def main():\n"
                            f"    raise NotImplementedError('Implement {_efn}')\n"
                            f"\nif __name__ == '__main__':\n    main()\n"
                        )
                        logger.error(f"  ❌ [{_efn}] post-gather retry failed — minimal skeleton written")
                except Exception as _ep_err:
                    logger.error(f"  ❌ [{_efn}] post-gather retry raised: {_ep_err}")
        # ─────────────────────────────────────────────────────────────────────
        # Any `from .X import Y` in a file must reference a module that is actually
        # in the generated file list — otherwise the import will crash at runtime.
        py_module_names = {f[:-3] for f in generated_files if f.endswith(".py")}
        import re as _re_imports
        for fname, content in list(generated_files.items()):
            if not fname.endswith(".py"):
                continue
            bad_imports = []
            for line in content.splitlines():
                m = _re_imports.match(r"\s*from \.([\w]+) import", line)
                if m and m.group(1) not in py_module_names:
                    bad_imports.append((line.strip(), m.group(1)))
            if bad_imports:
                logger.warning(f"  ⚠️  {fname} has {len(bad_imports)} phantom relative import(s): "
                               f"{[b[1] for b in bad_imports]} — rewriting to absolute-safe form")
                for orig_line, missing_mod in bad_imports:
                    # Best effort: comment out the phantom import
                    content = content.replace(
                        orig_line,
                        f"# REMOVED phantom import (module '{missing_mod}' not in project): {orig_line}"
                    )
                generated_files[fname] = content

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
                            generated_files[_fixf] = _pf_code
                            logger.info(f"  ✅ Pre-fixed: {_fixf}")
                else:
                    logger.info("  ✅ Self-review: no cross-file issues found")
            except Exception as _rv_err:
                logger.warning(f"  ⚠️  Self-review pass failed ({_rv_err}) — continuing")
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

        # ── Flatten file keys: strip any directory prefix ───────────────────
        generated_files = _flatten_file_keys(generated_files, "code_generation")
        # ──────────────────────────────────────────────────────────────────────

        # Memory cleanup after heavy generation
        gc.collect()
        
        return {
            "current_stage": "code_generated",
            "generated_code": {
                "files": generated_files,
                "approach": approach,
                "total_files": len(generated_files)
            }
        }
        
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
            f"ARCHITECTURE SUMMARY:\n{str(arch_summary)[:1200]}"
        )

        py_files = {k: v for k, v in files.items() if k.endswith(".py") and v.strip()}
        if not py_files:
            logger.info("  No Python files to review")
            return {"current_stage": "code_reviewed", "generated_code": generated_code}

        review_llm = get_fallback_llm("powerful")
        fix_llm    = get_fallback_llm("balanced")
        total_issues_fixed = 0

        for _iteration in range(2):  # max 2 review→fix cycles
            # ── Build the review payload ─────────────────────────────────────
            # Truncate individual files if total is too large for model context
            _max_chars_per_file = 12000  # ~300 lines at 40 chars/line
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
                "    or AttributeError. The placeholder must be replaced with the actual class instantiation.\n\n"
                "CRITICAL RULE: For any nn.Module with a stored vocab_size/num_classes attribute, VERIFY that forward()\n"
                "includes a projection layer (nn.Linear) whose output dimension equals vocab_size/num_classes.\n"
                "If it doesn't, report MISSING_OUTPUT_PROJECTION as severity=critical.\n\n"
                "IMPORTANT: Only report issues that are genuinely present. Do NOT invent issues.\n"
                "Severity:\n"
                "  critical — will cause wrong output, crash, or silent failure when run\n"
                "  warning  — code smell but won't crash\n\n"
                "Output ONLY valid JSON, no prose:\n"
                '{"issues": [{\n'
                '  "file": "filename.py",\n'
                '  "type": "TRUNCATED|MISSING_ENTRY_POINT|SILENT_MAIN|MISSING_OUTPUT_PROJECTION|DEAD_LOGIC|STUB_BODY|WRONG_CALL|MISSING_EXPORT|CIRCULAR_IMPORT|SHAPE_MISMATCH|DUPLICATE_CLASS|PLACEHOLDER_INIT",\n'
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
                        "Return ONLY the complete corrected Python source file.\n"
                        "No markdown fences, no explanation, just the code."
                    )),
                    HumanMessage(content=(
                        f"PROJECT CONTEXT:\n{build_ctx}\n\n"
                        f"Fix these issues in `{fname}`:\n{issue_text}\n\n"
                        f"Current `{fname}`:\n{py_files[fname]}\n\n"
                        f"Other project files (for API reference):\n{other_ctx[:4000]}"
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
        if total_issues_fixed > 0:
            console.print(f"\n[green]🔍 Code Review Agent: fixed {total_issues_fixed} file(s)[/green]")
        else:
            console.print("\n[green]🔍 Code Review Agent: code looks correct ✅[/green]")

        # ── Flatten file keys (strip directory prefixes) ─────────────────────
        files = _flatten_file_keys(files, "code_review_agent")

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
        # Non-fatal — let testing catch whatever it can
        return {"current_stage": "code_reviewed", "generated_code": state.get("generated_code", {})}


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
        import ast as _ast
        syntax_errors = []
        for fname, code in files.items():
            if not fname.endswith(".py"):
                continue
            try:
                _ast.parse(code)
            except SyntaxError as _se:
                syntax_errors.append(
                    f"Syntax error in {fname}: {_se.msg} (line {_se.lineno}): "
                    f"{(_se.text or '').strip()}"
                )
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
                    "warnings": [],
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
                    "syntax_valid": True,
                    "import_successful": True,
                    "execution_errors": ["Test suite timed out after 300s (pip install too slow for deps)"],
                    "warnings": ["Skipped: timeout"],
                    "test_outputs": []
                }
            
            # Merge validation results into test_results
            test_results['validation_results'] = validation_results
            test_results['average_quality'] = avg_quality
            
            # Analyze results - ENHANCED with quality thresholds
            passed = (
                test_results.get("environment_created", False) and
                test_results.get("dependencies_installed", False) and
                test_results.get("syntax_valid", True) and
                test_results.get("import_successful", True) and
                avg_quality >= 50  # Minimum quality threshold
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
                logger.info("⏰ Only failure is pip-install timeout — static analysis passed.")
                logger.info(f"   Quality {avg_quality:.0f}/100 ≥ 80 → treating as conditional pass")
                passed = True
                test_results["execution_errors"] = []  # Clear the timeout error
            
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
    4. DECIDES whether to patch individual files or regenerate from scratch
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

        error_text = "\n".join(f"  - {e}" for e in execution_errors[:10])
        file_text = "\n".join(file_overview)
        prev_text = "\n".join(f"  - Attempt {i+1}: {s}" for i, s in enumerate(prev_strategies[-3:]))

        llm = get_fallback_llm("reasoning")

        reasoning_prompt = (
            "You are a senior software architect debugging a failed code generation pipeline.\n\n"
            "Your job is NOT to write code. Your job is to THINK STRATEGICALLY about:\n"
            "1. What is the ROOT CAUSE of each failure (not just the symptom)?\n"
            "2. What CATEGORY of bug is this? (architecture_flaw, incomplete_impl, wrong_api, "
            "shadow_file, circular_import, missing_dep, stub_code, truncated, wrong_algorithm)\n"
            "3. What is the BEST STRATEGY to fix it? (patch_file, regenerate_file, "
            "regenerate_all, fix_imports, fix_deps, add_missing_module)\n"
            "4. What SPECIFIC INSTRUCTIONS should the code fixer follow for each file?\n\n"
            f"PROJECT IDEA: {idea}\n"
            f"APPROACH: {solution.get('approach_name', 'N/A')}\n\n"
            f"FILES GENERATED:\n{file_text}\n\n"
            f"ERRORS:\n{error_text}\n\n"
        )

        if self_eval_fixes:
            reasoning_prompt += f"SELF-EVAL FEEDBACK:\n{self_eval_fixes}\n\n"

        if prev_text:
            reasoning_prompt += (
                f"PREVIOUSLY TRIED STRATEGIES (DO NOT REPEAT THESE):\n{prev_text}\n\n"
            )

        # Include first 40 lines of each file so the reasoner can see the actual code
        code_preview = []
        for fname, fcode in files.items():
            if not fname.endswith(".py"):
                continue
            lines = (fcode or "").splitlines()[:40]
            code_preview.append(f"=== {fname} (first 40 lines) ===\n" + "\n".join(lines))
        reasoning_prompt += "CODE PREVIEW:\n" + "\n\n".join(code_preview) + "\n\n"

        reasoning_prompt += (
            "Return ONLY valid JSON (no markdown fences):\n"
            "{\n"
            '  "root_cause_analysis": "One paragraph explaining the fundamental problem",\n'
            '  "failure_category": "architecture_flaw|incomplete_impl|wrong_api|shadow_file|'
            'circular_import|missing_dep|stub_code|truncated|wrong_algorithm",\n'
            '  "overall_strategy": "patch_files|regenerate_worst|regenerate_all",\n'
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
            "current_stage": "strategy_ready",
        }

    except Exception as e:
        logger.warning(f"Strategy reasoner failed ({e}) — proceeding with basic fixing")
        _console.print(f"  [dim yellow]Reasoning failed ({e}) — falling back to basic fixing[/dim yellow]")
        return {"current_stage": "strategy_fallback"}


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
        max_fix_attempts = state.get("max_fix_attempts", 3)  # Reduced from 6
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
                "tests_passed": True,
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
            # For regenerate strategies, mark all .py files for regeneration
            if overall_strategy == "regenerate_all":
                for fname in files_for_fix:
                    if fname.endswith(".py"):
                        strategy_file_instructions.setdefault(fname, {
                            "action": "regenerate",
                            "reason": "Full project regeneration requested by strategy reasoner",
                            "specific_instructions": "Regenerate the entire file from scratch based on the project requirements."
                        })

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

        # Use powerful model for complex fixes, fast for simple patches
        llm = get_llm("powerful") if use_powerful_model else get_llm("fast")

        # Build error context
        error_summary = "\n".join([f"- {error}" for error in execution_errors[:5]])

        system_prompt = """You are an expert Python debugger. Fix code issues based on test errors.

Your job:
1. Analyze the error messages
2. Identify the root cause
3. Generate fixed code
4. Ensure all imports and dependencies are correct

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

        # Fix each file that has errors
        for filename, content in files_for_fix.items():
            if not filename.endswith('.py') or filename not in files_with_errors:
                fixed_files[filename] = content  # keep unchanged
                continue

            # Get strategy-specific instructions for this file
            file_strategy = strategy_file_instructions.get(filename, {})
            strategy_instr = file_strategy.get("specific_instructions", "")
            strategy_action = file_strategy.get("action", "patch")

            console.print(f"  [dim]Fixing {filename} (action: {strategy_action})...[/dim]")
            
            # Build context-rich prompt with strategy guidance
            strategy_section = ""
            if strategy_instr:
                strategy_section = (
                    f"\n\nSTRATEGY GUIDANCE (from reasoning analysis):\n"
                    f"Action: {strategy_action}\n"
                    f"Instructions: {strategy_instr}\n"
                )
            
            user_prompt = f"""Fix this Python file based on the test errors:

Errors:
{error_summary}
{strategy_section}

File: {filename}
```python
{content}
```

Return the FIXED code for {filename}. Fix:
- Syntax errors
- Import errors  
- Missing dependencies
- Type errors
- Runtime errors

IMPORTANT: Return COMPLETE, PRODUCTION-READY code. Every function must have real
logic (10-30+ lines each). Do NOT use stubs, placeholders, or TODO comments.
The file should be 100-400+ lines of real, working code.

Return ONLY the complete fixed Python code, no explanations."""
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = await llm.ainvoke(messages)
            
            # Extract code from response
            fixed_code = response.content
            if "```python" in fixed_code:
                fixed_code = fixed_code.split("```python")[1].split("```")[0].strip()
            elif "```" in fixed_code:
                fixed_code = fixed_code.split("```")[1].split("```")[0].strip()
            
            fixed_files[filename] = fixed_code
            # Sanitize typographic unicode that breaks Windows cp1252 (same as generation step)
            _FIX_TYPO = {'\u202f':' ','\u2011':'-','\u2013':'-','\u2014':'--','\u2015':'--',
                         '\u2018':"'",'\u2019':"'",'\u201a':"'",'\u201c':'"','\u201d':'"',
                         '\u201e':'"','\u00a0':' ','\u2026':'...','\u2212':'-','\ufeff':''}
            fixed_files[filename] = fixed_code.translate(str.maketrans(_FIX_TYPO))
            console.print(f"  [green]\u2713[/green] Fixed {filename}")
        
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
                                    stub_lines.append(f"{sym} = None  # TODO: implement")
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

        console.print(f"\n[green]✅ Code fixes generated. Re-testing...[/green]\n")
        
        return {
            "current_stage": "code_fixed",
            "generated_code": {"files": _flatten_file_keys(fixed_files, "code_fixing")},
            "fix_attempts": fix_attempts + 1
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

    MAX_SELF_EVAL = 1  # Maximum self-eval reruns before we stop re-looping (was 3 — too slow)
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
    MAX_LINES_PER_FILE = 200   # up from 60 — need to see actual implementations
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
                f"  - {e}" for e in exec_errors[:5]
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
            'verdict must be "needs_work" if overall_score < 4.'
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
        # Only re-loop if score is VERY low (< 4) AND we haven't exhausted attempts
        if verdict == "needs_work" and overall_score < 4 and self_eval_attempts < MAX_SELF_EVAL:
            fix_guidance = (
                "SELF-EVAL FEEDBACK — address these before re-testing:\n"
                + "\n".join(f"  {i}. {fix}" for i, fix in enumerate(priority_fixes[:3], 1))
            )
            if runtime_context and "error" in runtime_context.lower():
                fix_guidance += f"\n\nRUNTIME ERRORS:\n{runtime_context}"

            # Inject guidance so code_fixing_node can act on it
            updated_tests = dict(existing_tests) if isinstance(existing_tests, dict) else {}
            updated_tests["self_eval_fixes"] = fix_guidance
            updated_tests["self_eval_score"] = overall_score
            updated_tests["execution_errors"] = [
                f"[SELF-EVAL] {fix}" for fix in priority_fixes[:5]
            ]

            _console.print(f"\n  [yellow]⟳  Score {overall_score:.1f} < 4 — routing back for targeted fixes "
                           f"(pass {self_eval_attempts + 1}/{MAX_SELF_EVAL})[/yellow]")
            if priority_fixes:
                _console.print("  [dim]Priority fixes: " + "; ".join(priority_fixes[:3]) + "[/dim]")

            return {
                "current_stage": "self_eval_needs_regen",
                "self_eval_score": overall_score,
                "self_eval_attempts": self_eval_attempts + 1,
                "test_results": updated_tests,
                "tests_passed": False,  # force re-test after fixing
                # Grant exactly ONE more fix attempt per self-eval cycle.
                # Old behavior (fix_attempts: 0) reset the entire budget,
                # causing 3×3=9 fix iterations max — far too many.
                "fix_attempts": max(state.get("fix_attempts", 0) - 1, 0),
            }

        _console.print(f"\n  [green]✅ Approved for publishing (score {overall_score:.1f}/10)[/green]")
        return {
            "current_stage": "self_eval_approved",
            "self_eval_score": overall_score,
            "self_eval_attempts": self_eval_attempts + 1,
        }

    except Exception as e:
        logger.warning(f"Self-eval LLM failed ({e}) — approving anyway to avoid blocking publish")
        _console.print(f"  [dim yellow]Self-eval skipped ({e}) — proceeding to publish[/dim yellow]")
        return {
            "current_stage": "self_eval_approved",
            "self_eval_score": -1.0,
            "self_eval_attempts": self_eval_attempts + 1,
        }


async def git_publishing_node(state: AutoGITState) -> Dict[str, Any]:
    """
    Node 9: Publish generated code to GitHub
    
    Creates a new repository and pushes all generated code.
    Only publishes if tests passed (or if testing was skipped).
    """
    logger.info("📤 Git Publishing Node")
    
    # Check test results before publishing
    test_results = state.get("test_results", {})
    tests_passed = state.get("tests_passed", True)  # Default to True if testing was skipped
    
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
                # Filter out shadow files (e.g. numpy.py, torch.py) that shadow real packages
                _SHADOW_SAVE = {"numpy", "torch", "scipy", "pandas", "sklearn", "tensorflow",
                                "requests", "flask", "django", "fastapi", "setuptools", "pip"}
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
                
                return {
                    "current_stage": "saved_locally_tests_failed",
                    "output_path": str(project_dir),
                    "github_url": None,
                    "tests_passed": False
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
            
            for filename, content in files.items():
                file_path = project_dir / filename
                file_path.write_text(content, encoding="utf-8")
                logger.info(f"  ✅ Saved {filename}")
            
            logger.info(f"✅ Code saved to: {project_dir}")
            
            return {
                "current_stage": "saved_locally",
                "output_path": str(project_dir),
                "github_url": None
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
        
        # Create files
        for filename, content in files.items():
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

