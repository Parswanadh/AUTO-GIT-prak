"""
rerun_fix_on_output.py

Loads an already-generated output folder and runs it through:
  1. code_review_agent  (Node 7.5 — semantic review with full build context)
  2. code_testing       (Node 8   — venv, imports, run main.py)
  3. code_fixing loop   (Node 8.5 — LLM fixes, up to 3 passes)

Then saves the final fixed files back into the same folder (overwriting),
so you can re-run `python main.py` and verify it works.

Usage:
    python rerun_fix_on_output.py [output_folder]

If no folder given, uses the most recent subfolder under output/.
"""

import sys, os, asyncio, logging
from pathlib import Path

# UTF-8 console on Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ["PYTHONUTF8"] = "1"

from dotenv import load_dotenv
load_dotenv("d:/Projects/auto-git/.env")

# Quiet noisy loggers, show pipeline detail
for n in ["langchain", "openai", "httpx", "urllib3", "httpcore"]:
    logging.getLogger(n).setLevel(logging.ERROR)
logging.getLogger("src.langraph_pipeline.nodes").setLevel(logging.INFO)
logging.getLogger("src.utils.model_manager").setLevel(logging.INFO)
logging.basicConfig(level=logging.WARNING, format="%(name)s: %(message)s")

# ── Resolve target folder ─────────────────────────────────────────────────────

def _find_latest_output() -> Path:
    """Walk output/ and return the most recently modified leaf folder."""
    root = Path("output")
    if not root.exists():
        raise FileNotFoundError("No output/ directory found. Run a pipeline first.")
    candidates = sorted(
        (p for p in root.rglob("main.py")),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError("No main.py found anywhere under output/")
    return candidates[0].parent


if len(sys.argv) > 1:
    target_dir = Path(sys.argv[1])
else:
    target_dir = _find_latest_output()

if not target_dir.exists():
    print(f"ERROR: folder not found: {target_dir}")
    sys.exit(1)

print("=" * 70)
print(f"TARGET FOLDER : {target_dir}")
print("=" * 70)

# ── Read all source files ─────────────────────────────────────────────────────

def _load_files(folder: Path) -> dict:
    exts = {".py", ".txt", ".md", ".yaml", ".yml", ".toml", ".cfg", ".json"}
    out = {}
    for f in sorted(folder.iterdir()):
        if f.is_file() and f.suffix.lower() in exts:
            try:
                out[f.name] = f.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                print(f"  WARN: could not read {f.name}: {e}")
    return out

files = _load_files(target_dir)
print(f"\nLoaded {len(files)} files:")
for name, content in files.items():
    lines = content.count("\n") + 1
    print(f"  {name:35s}  {lines:4d} lines  ({len(content):6d} bytes)")

# ── Extract build context from RESEARCH_REPORT.md (if present) ───────────────

idea = ""
solution_approach = ""
arch_summary = ""

rr = files.get("RESEARCH_REPORT.md", "")
if rr:
    # First line of RESEARCH_REPORT is usually "# Research Report: <idea>"
    for line in rr.splitlines():
        if line.startswith("# Research Report:"):
            idea = line.replace("# Research Report:", "").strip()
            break
    # Look for a "Solution" or "Approach" section
    import re
    m = re.search(r"(?:##.*[Ss]olution|##.*[Aa]pproach)(.*?)(?=\n##|\Z)", rr, re.S)
    if m:
        arch_summary = m.group(1).strip()[:1200]

if not idea:
    # Fall back to folder name
    idea = target_dir.parent.name.replace("-", " ")

print(f"\nIdea (from report): {idea[:120]}")

# ── Build a minimal AutoGITState ─────────────────────────────────────────────

minimal_state = {
    "idea": idea,
    "selected_problem": idea,          # best approximation
    "final_solution": {
        "approach_name": solution_approach or target_dir.parent.name,
        "architecture_design": arch_summary,
    },
    "generated_code": {
        "files": dict(files),
        "approach": solution_approach or target_dir.parent.name,
        "total_files": len(files),
    },
    "current_stage": "code_generated",
    "test_results": {},
    "tests_passed": False,
    "fix_attempts": 0,
    "max_fix_attempts": 3,
    "errors": [],
}

# ── Run the three nodes ───────────────────────────────────────────────────────

async def main():
    from src.langraph_pipeline.nodes import (
        code_review_agent_node,
        code_testing_node,
        code_fixing_node,
    )

    state = dict(minimal_state)

    # ── Step 1: Code Review Agent (Node 7.5) ──────────────────────────────────
    print("\n" + "="*70)
    print("STEP 1 / 3 — Code Review Agent (semantic review with build context)")
    print("="*70)
    review_update = await code_review_agent_node(state)
    state.update(review_update)
    reviewed_files = state.get("generated_code", {}).get("files", {})
    print(f"\nAfter review: {len(reviewed_files)} files in state")

    # ── Step 2 + 3: Test → Fix loop ───────────────────────────────────────────
    MAX_LOOPS = 3
    for _loop in range(MAX_LOOPS):
        print(f"\n{'='*70}")
        print(f"STEP 2 / 3 — Code Testing (pass {_loop + 1}/{MAX_LOOPS})")
        print("="*70)
        test_update = await code_testing_node(state)
        state.update(test_update)

        passed      = state.get("tests_passed", False)
        fix_attempts = state.get("fix_attempts", 0)
        stage        = state.get("current_stage", "")

        print(f"\n  tests_passed={passed}  fix_attempts={fix_attempts}  stage={stage}")
        errs = state.get("test_results", {}).get("execution_errors", [])
        if errs:
            print("  Errors:")
            for e in errs[:5]:
                print(f"    ✗ {str(e)[:130]}")

        if passed or stage in ("testing_skipped", "no_errors_to_fix", "fixing_failed"):
            print(f"\n  ✅ Tests passed (or nothing to fix) — done.")
            break

        print(f"\n{'='*70}")
        print(f"STEP 3 / 3 — Code Fixing (pass {_loop + 1}/{MAX_LOOPS})")
        print("="*70)
        fix_update = await code_fixing_node(state)
        state.update(fix_update)
        fix_stage = state.get("current_stage", "")
        print(f"\n  stage after fix: {fix_stage}")
        if fix_stage in ("fixing_failed",):
            print("  Max fix attempts reached — stopping loop.")
            break

    # ── Save fixed files back to the same folder ──────────────────────────────
    final_files = state.get("generated_code", {}).get("files", {})
    saved = 0
    print(f"\n{'='*70}")
    print("SAVING FIXED FILES")
    print("="*70)
    for fname, content in final_files.items():
        dest = target_dir / fname
        if not content or not content.strip():
            print(f"  SKIP (empty): {fname}")
            continue
        dest.write_text(content, encoding="utf-8")
        lines = content.count("\n") + 1
        print(f"  ✅ {fname:35s}  {lines:4d} lines  ({len(content):6d} bytes)")
        saved += 1
    print(f"\nSaved {saved} files to: {target_dir}")

    # ── Quick smoke-test: run main.py ─────────────────────────────────────────
    main_py = target_dir / "main.py"
    if main_py.exists():
        import subprocess
        print(f"\n{'='*70}")
        print("SMOKE TEST — python main.py")
        print("="*70)
        result = subprocess.run(
            [sys.executable, "main.py"],
            capture_output=True, timeout=20, cwd=str(target_dir)
        )
        stdout = result.stdout.decode(errors="replace").strip()
        stderr = result.stderr.decode(errors="replace").strip()
        if result.returncode == 0 and stdout:
            print(f"  ✅ EXIT 0 — output:\n{stdout[:800]}")
        elif result.returncode == 0 and not stdout:
            print("  ⚠️  EXIT 0 but NO OUTPUT — SILENT_MAIN may still be present")
        else:
            print(f"  ❌ EXIT {result.returncode}")
            if stderr:
                print(f"  stderr: {stderr[-600:]}")

asyncio.run(main())
