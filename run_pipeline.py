#!/usr/bin/env python3
"""
Auto-GIT Pipeline Runner — Clean agentic output
═══════════════════════════════════════════════

Usage:
    python run_pipeline.py                           # Use default idea
    python run_pipeline.py "Your idea here"          # Custom idea
    python run_pipeline.py --fresh                   # Force fresh run (ignore checkpoint)
    python run_pipeline.py --fresh "Your idea here"  # Both

Progress is written live to stdout AND logs/pipeline_progress.txt
"""

import sys, os, time, ast, atexit, argparse

# ── Fixed encoding for Windows ──────────────────────────────────────
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    os.environ["PYTHONUTF8"] = "1"

import asyncio, logging
from datetime import datetime
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# ── Suppress noisy loggers ──────────────────────────────────────────
for n in ["langchain", "openai", "httpx", "urllib3", "httpcore",
          "langchain_core", "langchain_openai", "langchain_community"]:
    logging.getLogger(n).setLevel(logging.ERROR)
logging.getLogger("src.utils.model_manager").setLevel(logging.INFO)
logging.getLogger("src.langraph_pipeline.nodes").setLevel(logging.INFO)
logging.basicConfig(level=logging.WARNING, format="%(name)s: %(message)s")

# ── Progress / heartbeat ────────────────────────────────────────────
PROGRESS_FILE = os.path.join("logs", "pipeline_progress.txt")
_start_wall = time.time()
os.makedirs("logs", exist_ok=True)

def _progress(msg: str):
    elapsed = time.time() - _start_wall
    line = f"[{datetime.now().strftime('%H:%M:%S')} +{elapsed:5.0f}s] {msg}"
    print(line, flush=True)
    try:
        with open(PROGRESS_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

atexit.register(lambda: _progress("PROCESS EXIT"))

# ── Default idea ────────────────────────────────────────────────────
DEFAULT_IDEA = (
    "Baby Dragon: a new AI architecture that hatches like a dragon egg — starts small, "
    "self-evolves by consuming compute, and grows richer internal representations over time. "
    "Design the full architecture: a seed model (tiny transformer) that bootstraps itself "
    "via recursive self-distillation, dynamic layer addition, and an internal reward signal "
    "based on prediction surprise. Implement training loop, self-evolution scheduler, "
    "layer-growth controller, surprise metric, and a demo that shows the dragon grow from "
    "1-layer to 6-layer while training on a toy sequence task."
)

def _fmt_time(s):
    if s < 60: return f"{s:.0f}s"
    return f"{s/60:.1f}m"


def _validate_output(files: dict, output_dir: str):
    """Quick local validation of generated code — like Claude Code would do."""
    print("\n" + "─" * 60)
    print("  📋 Output Validation")
    print("─" * 60)

    py_files = {k: v for k, v in files.items() if k.endswith(".py")}
    total_lines = 0
    all_pass = True

    for fname, code in sorted(py_files.items()):
        code_str = str(code)
        lines = code_str.split("\n")
        total_lines += len(lines)

        # Syntax check
        try:
            tree = ast.parse(code_str)
            classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
            funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
            print(f"  ✅ {fname:30s} {len(lines):4d} lines | {len(classes)} classes, {len(funcs)} funcs")
        except SyntaxError as e:
            print(f"  ❌ {fname:30s} {len(lines):4d} lines | SYNTAX ERROR: {e.msg} line {e.lineno}")
            all_pass = False

    # Check cross-file imports
    export_map = {}
    for fname, code in py_files.items():
        stem = fname.rsplit(".", 1)[0]
        try:
            tree = ast.parse(str(code))
            names = set()
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                    names.add(node.name)
                elif isinstance(node, ast.Assign):
                    for t in node.targets:
                        if isinstance(t, ast.Name):
                            names.add(t.id)
            export_map[stem] = names
        except SyntaxError:
            export_map[stem] = set()

    import_issues = []
    import re
    for fname, code in py_files.items():
        stem = fname.rsplit(".", 1)[0]
        for line in str(code).split("\n"):
            m = re.match(r"\s*from\s+\.?(\w+)\s+import\s+(.+?)(?:\s*#.*)?$", line)
            if not m:
                continue
            src_mod = m.group(1)
            if src_mod in export_map and src_mod != stem:
                imported = [n.strip().split(" as ")[0].strip() for n in m.group(2).split(",")]
                missing = [n for n in imported if n and n not in export_map[src_mod]]
                if missing:
                    import_issues.append(f"{fname}: '{', '.join(missing)}' not in {src_mod}.py")
            elif src_mod not in export_map:
                # Check if it's a local-looking module (not stdlib)
                stdlib = {"os","sys","json","math","re","typing","torch","numpy","pathlib",
                          "datetime","logging","argparse","collections","dataclasses","random",
                          "functools","abc","copy","time","warnings","enum","io","itertools",
                          "__future__","ast","inspect","contextlib","textwrap","unittest","pytest"}
                if src_mod not in stdlib:
                    import_issues.append(f"{fname}: imports from '{src_mod}' which doesn't exist")

    if import_issues:
        print(f"\n  ⚠️  Cross-file import issues:")
        for issue in import_issues[:5]:
            print(f"      • {issue}")
        all_pass = False
    else:
        print(f"\n  ✅ Cross-file imports: all valid")

    # Non-python files
    for fname, code in sorted(files.items()):
        if not fname.endswith(".py"):
            size = len(str(code))
            print(f"  📄 {fname:30s} {size:,d} bytes")

    print(f"\n  📊 Total: {len(py_files)} Python files, {total_lines:,d} lines")
    print("─" * 60)

    # Try running main.py
    main_file = None
    for f in py_files:
        if "main" in f.lower():
            main_file = f
            break
    if not main_file:
        main_file = next(iter(py_files), None)

    if main_file and output_dir:
        main_path = os.path.join(output_dir, os.path.basename(main_file))
        if os.path.exists(main_path):
            print(f"\n  🚀 Testing: python {main_file}")
            import subprocess
            try:
                result = subprocess.run(
                    [sys.executable, main_path],
                    capture_output=True, text=True, timeout=30,
                    cwd=output_dir
                )
                if result.returncode == 0:
                    output = result.stdout.strip()
                    if output:
                        print(f"  ✅ Exit 0 — output ({len(output)} chars):")
                        for line in output.split("\n")[:10]:
                            print(f"      {line}")
                        if output.count("\n") > 10:
                            print(f"      ... ({output.count(chr(10)) - 10} more lines)")
                    else:
                        print(f"  ⚠️  Exit 0 but no output")
                else:
                    stderr = result.stderr.strip()
                    print(f"  ❌ Exit {result.returncode}")
                    for line in stderr.split("\n")[-5:]:
                        print(f"      {line}")
            except subprocess.TimeoutExpired:
                print(f"  ⏱️  Timeout (30s) — likely a server/training loop (OK)")
            except Exception as e:
                print(f"  ⚠️  Could not run: {e}")

    return all_pass


async def main(idea: str, resume: bool):
    _progress(f"PIPELINE STARTING")

    # ── Pretty banner ───────────────────────────────────────────────
    print()
    print("╔" + "═" * 62 + "╗")
    print("║  🐉 AUTO-GIT Pipeline                                         ║")
    print("╠" + "═" * 62 + "╣")
    print(f"║  Idea: {idea[:53]:53s}  ║")
    if len(idea) > 53:
        print(f"║        {idea[53:106]:53s}  ║")
    print(f"║  Mode: {'Resume' if resume else 'Fresh':53s}  ║")
    print("╚" + "═" * 62 + "╝")
    print()

    from src.langraph_pipeline.workflow_enhanced import run_auto_git_pipeline

    slug = idea.split(":")[0].lower().replace(" ", "_")[:30] if ":" in idea else "project"
    thread_id = f"{slug}_001"

    _progress(f"Starting pipeline (thread={thread_id})...")
    t0 = time.time()

    try:
        state = await run_auto_git_pipeline(
            idea=idea,
            use_web_search=True,
            max_debate_rounds=2,
            min_consensus_score=0.35,
            auto_publish=False,
            output_dir=f"output/{slug}",
            thread_id=thread_id,
            interactive=False,
            resume=resume,
        )
    except Exception as exc:
        _progress(f"PIPELINE FAILED: {type(exc).__name__}: {exc}")
        print(f"\n❌ Pipeline failed after {_fmt_time(time.time()-t0)}: {exc}")
        raise

    elapsed = time.time() - t0

    if state is None:
        _progress("PIPELINE RETURNED None — completed checkpoint exists. Use --fresh to re-run.")
        print(f"\n⚠️  Pipeline already completed for this idea. Use --fresh to start over.")
        return

    # ── Results ─────────────────────────────────────────────────────
    stage = state.get("current_stage", "unknown")
    _progress(f"PIPELINE FINISHED — stage={stage} in {_fmt_time(elapsed)}")

    gen = state.get("generated_code") or {}
    files = gen.get("files", {})
    sol = state.get("final_solution") or {}
    se_score = state.get("self_eval_score", -1)

    # If no files in state, try reading from output_path saved by pipeline
    output_path = state.get("output_path", "")
    if not files and output_path and os.path.isdir(output_path):
        for fname in os.listdir(output_path):
            fpath = os.path.join(output_path, fname)
            if os.path.isfile(fpath):
                try:
                    files[fname] = open(fpath, "r", encoding="utf-8").read()
                except Exception:
                    pass

    print()
    print("═" * 60)
    print(f"  🏁 Pipeline Complete — {_fmt_time(elapsed)}")
    print("═" * 60)
    print(f"  Stage    : {stage}")
    print(f"  Solution : {sol.get('approach_name', sol.get('title', 'N/A'))}")
    print(f"  Self-eval: {se_score:.1f}/10" if se_score >= 0 else "  Self-eval: skipped")
    print(f"  Files    : {len(files)}")

    if not files:
        print("\n⚠️  No files generated.")
        return

    # Save files (use pipeline's output path if available)
    out = output_path if output_path and os.path.isdir(output_path) else f"output/{slug}/generated"
    os.makedirs(out, exist_ok=True)
    for fname, code in files.items():
        path = os.path.join(out, fname)
        if not os.path.exists(path):  # Don't overwrite pipeline's saved files
            with open(path, "w", encoding="utf-8") as f:
                f.write(str(code))
    print(f"\n  💾 Saved to: {out}/")

    # Validate output
    _validate_output(files, out)

    _progress("DONE ✅")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto-GIT Pipeline Runner")
    parser.add_argument("idea", nargs="?", default=DEFAULT_IDEA, help="Your idea (default: Baby Dragon)")
    parser.add_argument("--fresh", action="store_true", help="Force fresh run, ignore checkpoint")
    args = parser.parse_args()

    _progress("run_pipeline.py started")
    asyncio.run(main(args.idea, resume=not args.fresh))
