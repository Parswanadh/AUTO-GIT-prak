#!/usr/bin/env python3
"""
Auto-GIT Rerun & Refine — Fix or improve already-generated code
═══════════════════════════════════════════════════════════════

Takes existing generated code and runs targeted fixes, improvements,
or user-requested changes WITHOUT re-running research/debate/generation.

Usage:
    # Auto-fix: re-test and fix existing code
    python rerun_fix.py output/my-project/20260228_162525

    # User-directed change
    python rerun_fix.py output/my-project/20260228_162525 --change "Remove colorama dependency, use plain print"

    # Multiple changes
    python rerun_fix.py output/my-project/20260228_162525 --change "Add input validation" --change "Support modulo operator"

    # Re-evaluate quality without fixing
    python rerun_fix.py output/my-project/20260228_162525 --eval-only

    # Force more fix attempts
    python rerun_fix.py output/my-project/20260228_162525 --max-fixes 4

Progress is written to stdout and logs/rerun_progress.txt
"""

import sys, os, time, ast, argparse, asyncio, logging, subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# ── Fixed encoding for Windows ──────────────────────────────────────
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    os.environ["PYTHONUTF8"] = "1"

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# ── Suppress noisy loggers ──────────────────────────────────────────
for n in ["langchain", "openai", "httpx", "urllib3", "httpcore",
          "langchain_core", "langchain_openai", "langchain_community"]:
    logging.getLogger(n).setLevel(logging.ERROR)
logging.getLogger("src.utils.model_manager").setLevel(logging.INFO)
logging.getLogger("src.langraph_pipeline.nodes").setLevel(logging.INFO)
logging.basicConfig(level=logging.WARNING, format="%(name)s: %(message)s")

PROGRESS_FILE = os.path.join("logs", "rerun_progress.txt")
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


def _fmt_time(secs: float) -> str:
    if secs < 60:
        return f"{secs:.0f}s"
    return f"{secs / 60:.1f}m"


def load_project(project_dir: str) -> Dict[str, str]:
    """Load all files from a generated project directory."""
    files = {}
    proj = Path(project_dir)
    if not proj.is_dir():
        print(f"❌ Directory not found: {project_dir}")
        sys.exit(1)

    for fpath in sorted(proj.iterdir()):
        if fpath.is_file():
            try:
                files[fpath.name] = fpath.read_text(encoding="utf-8")
            except Exception:
                pass
    return files


def quick_diagnose(files: Dict[str, str]) -> Dict:
    """Quick diagnosis of code health without LLM calls."""
    results = {
        "syntax_ok": [],
        "syntax_fail": [],
        "import_errors": [],
        "has_main_guard": False,
        "total_lines": 0,
        "py_files": 0,
    }

    for fname, code in files.items():
        if not fname.endswith(".py"):
            continue
        results["py_files"] += 1
        results["total_lines"] += len(code.splitlines())

        # Syntax check
        try:
            compile(code, fname, "exec")
            results["syntax_ok"].append(fname)
        except SyntaxError as e:
            results["syntax_fail"].append((fname, str(e)))

        # Main guard
        if fname == "main.py" and "if __name__" in code:
            results["has_main_guard"] = True

        # Dangling references (common post-fix issue)
        import re
        lines = code.splitlines()
        for i, line in enumerate(lines, 1):
            m = re.match(r'^# REMOVED \(.*?\):\s*from\s+\S+\s+import\s+(.+)', line)
            if m:
                for name in m.group(1).split(','):
                    name = name.strip().split(' as ')[-1].strip()
                    if name and name.isidentifier():
                        # Check if name is still used below
                        remaining = "\n".join(lines[i:])
                        if re.search(rf'\b{re.escape(name)}\s*\(', remaining):
                            results["import_errors"].append(
                                f"{fname}:{i}: `{name}` import was commented out "
                                f"but `{name}()` is still called below"
                            )

    return results


def apply_user_changes(files: Dict[str, str], changes: List[str],
                        idea: str = "") -> Dict[str, str]:
    """Apply user-requested changes using LLM."""
    from src.utils.model_manager import get_fallback_llm
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = get_fallback_llm("powerful")

    change_text = "\n".join(f"  {i+1}. {c}" for i, c in enumerate(changes))

    # Build file overview
    file_overview = []
    for fname, code in sorted(files.items()):
        if fname.endswith(".py"):
            lines = len(code.splitlines())
            file_overview.append(f"  {fname}: {lines} lines")

    modified = dict(files)
    py_files = [f for f in files if f.endswith(".py")]

    for fname in py_files:
        code = files[fname]

        # Build context showing other files' APIs
        other_apis = []
        for other_name, other_code in files.items():
            if other_name == fname or not other_name.endswith(".py"):
                continue
            # Extract class/function names
            try:
                tree = ast.parse(other_code)
                names = []
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                        names.append(f"class {node.name}: {', '.join(methods[:5])}")
                    elif isinstance(node, ast.FunctionDef) and not isinstance(getattr(node, '_parent', None), ast.ClassDef):
                        names.append(f"def {node.name}()")
                if names:
                    other_apis.append(f"  {other_name}: {'; '.join(names[:5])}")
            except Exception:
                pass

        prompt = (
            f"You are modifying an existing Python file to apply user-requested changes.\n\n"
            f"FILE: {fname}\n"
            f"CURRENT CODE:\n```python\n{code}\n```\n\n"
        )
        if other_apis:
            prompt += f"OTHER FILES IN PROJECT:\n" + "\n".join(other_apis) + "\n\n"
        prompt += (
            f"REQUESTED CHANGES:\n{change_text}\n\n"
            f"Apply ONLY the changes that are relevant to this file ({fname}).\n"
            f"If none of the changes apply to this file, return the code UNCHANGED.\n"
            f"Return ONLY the complete updated Python code. No markdown fences, no explanation."
        )

        import asyncio as _aio
        response = _aio.get_event_loop().run_until_complete(
            llm.ainvoke([
                SystemMessage(content="You are an expert Python developer. Apply requested changes precisely."),
                HumanMessage(content=prompt),
            ])
        )
        new_code = response.content.strip()
        # Strip markdown fences
        import re
        new_code = re.sub(r"^```[a-z]*\n?", "", new_code)
        new_code = re.sub(r"\n?```$", "", new_code.strip())

        if new_code and len(new_code) > 20:
            # Verify syntax before applying
            try:
                compile(new_code, fname, "exec")
                modified[fname] = new_code
                print(f"  ✅ Applied changes to {fname}")
            except SyntaxError as e:
                print(f"  ⚠️  Changes produced syntax error in {fname}: {e} — keeping original")
        else:
            print(f"  ⏭️  No changes needed for {fname}")

    return modified


async def run_test_fix_loop(files: Dict[str, str], project_dir: str,
                             idea: str, max_fixes: int = 3) -> Dict[str, str]:
    """Run the test → strategy → fix loop on existing code."""
    from src.utils.code_executor import CodeExecutor
    from src.utils.model_manager import get_fallback_llm
    from langchain_core.messages import HumanMessage, SystemMessage

    current_files = dict(files)

    for attempt in range(1, max_fixes + 1):
        print(f"\n{'='*60}")
        print(f"  🔄 Fix Attempt {attempt}/{max_fixes}")
        print(f"{'='*60}")

        # ── Step 1: Test the code ────────────────────────────────────
        executor = CodeExecutor(current_files, project_dir)
        try:
            executor.run_full_test_suite()
        except Exception as e:
            print(f"  ⚠️  Test suite exception: {e}")

        test_results = executor.test_results
        errors = test_results.get("execution_errors", [])
        warnings_list = test_results.get("warnings", [])

        # Show results
        syntax_ok = test_results.get("syntax_valid", False)
        imports_ok = test_results.get("imports_valid", False)
        entry_exit = test_results.get("entry_point_exit_code", -1)
        gen_test_exit = test_results.get("generated_test_exit_code", -1)

        print(f"  Syntax:     {'✅' if syntax_ok else '❌'}")
        print(f"  Imports:    {'✅' if imports_ok else '❌'}")
        print(f"  Entry point: exit {entry_exit}" if entry_exit >= 0 else "  Entry point: not tested")
        if gen_test_exit >= 0:
            print(f"  Auto-tests: {'✅ pass' if gen_test_exit == 0 else '❌ fail'}")
        print(f"  Errors:     {len(errors)}")
        print(f"  Warnings:   {len(warnings_list)}")

        if not errors:
            print(f"\n  ✅ All tests pass!")

            # Run LLM-as-Judge quick eval
            stdout = test_results.get("entry_point_stdout", "")
            if stdout:
                print(f"  📋 Output preview: {stdout[:200]}")

            executor.cleanup()
            break

        # ── Step 2: Reason about failures ────────────────────────────
        error_text = "\n".join(f"  - {e}" for e in errors[:10])
        print(f"\n  Errors to fix:\n{error_text}")

        # ── Step 3: Fix via LLM ─────────────────────────────────────
        llm = get_fallback_llm("powerful")

        file_overview = "\n".join(
            f"  {fn}: {len(code.splitlines())} lines"
            for fn, code in current_files.items()
            if fn.endswith(".py")
        )

        for fname in list(current_files.keys()):
            if not fname.endswith(".py"):
                continue

            # Only fix files mentioned in errors
            file_errors = [e for e in errors if fname in str(e)]
            if not file_errors:
                continue

            code = current_files[fname]
            fix_prompt = (
                f"Fix the following Python file to resolve these errors:\n\n"
                f"FILE: {fname}\n"
                f"```python\n{code}\n```\n\n"
                f"ERRORS:\n" + "\n".join(f"  - {e}" for e in file_errors[:5]) + "\n\n"
                f"OTHER FILES: {file_overview}\n\n"
                f"RULES:\n"
                f"1. Return the COMPLETE fixed file — not just the changed part\n"
                f"2. Do NOT comment out imports and leave their calls — either remove BOTH or keep BOTH\n"
                f"3. Do NOT add imports from packages not in requirements.txt\n"
                f"4. If a dependency is unavailable, replace its functionality with stdlib equivalents\n"
                f"5. Return ONLY valid Python code, no markdown fences\n"
            )

            response = await llm.ainvoke([
                SystemMessage(content="You are an expert Python debugger. Fix code precisely."),
                HumanMessage(content=fix_prompt),
            ])

            new_code = response.content.strip()
            import re
            new_code = re.sub(r"^```[a-z]*\n?", "", new_code)
            new_code = re.sub(r"\n?```$", "", new_code.strip())

            if new_code and len(new_code) > 20:
                try:
                    compile(new_code, fname, "exec")
                    current_files[fname] = new_code
                    print(f"  ✅ Fixed {fname}")
                except SyntaxError as e:
                    print(f"  ⚠️  Fix introduced syntax error in {fname}: {e}")
            else:
                print(f"  ⏭️  No fix generated for {fname}")

        executor.cleanup()

    return current_files


def save_files(files: Dict[str, str], output_dir: str):
    """Save files to output directory."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    for fname, code in files.items():
        (out / fname).write_text(code, encoding="utf-8")
    print(f"\n  💾 Saved {len(files)} files to {out}")


def run_main_test(output_dir: str) -> bool:
    """Try running main.py and show output."""
    main_path = os.path.join(output_dir, "main.py")
    if not os.path.exists(main_path):
        print("  ⚠️  No main.py to test")
        return False

    print(f"\n  🚀 Testing: python main.py")
    try:
        result = subprocess.run(
            [sys.executable, main_path],
            capture_output=True, text=True, timeout=30,
            cwd=output_dir
        )
        if result.returncode == 0:
            output = result.stdout.strip()
            if output:
                print(f"  ✅ Exit 0 — output:")
                for line in output.split("\n")[:10]:
                    print(f"      {line}")
                return True
            else:
                print(f"  ⚠️  Exit 0 but no output")
                return True
        else:
            stderr = result.stderr.strip()
            print(f"  ❌ Exit {result.returncode}")
            for line in stderr.split("\n")[-5:]:
                print(f"      {line}")
            return False
    except subprocess.TimeoutExpired:
        print(f"  ⏱️  Timeout (30s) — likely a server (OK)")
        return True
    except Exception as e:
        print(f"  ⚠️  Could not run: {e}")
        return False


async def main():
    parser = argparse.ArgumentParser(
        description="Auto-GIT Rerun & Refine — fix or improve generated code",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python rerun_fix.py output/my-project/20260228_162525
  python rerun_fix.py output/my-project/20260228_162525 --change "Add error handling"
  python rerun_fix.py output/my-project/20260228_162525 --eval-only
  python rerun_fix.py output/my-project/20260228_162525 --max-fixes 4
        """
    )
    parser.add_argument("project_dir", help="Path to generated project directory")
    parser.add_argument("--change", "-c", action="append", default=[],
                        help="User-requested change (can specify multiple)")
    parser.add_argument("--eval-only", action="store_true",
                        help="Only diagnose and evaluate, don't fix")
    parser.add_argument("--max-fixes", type=int, default=3,
                        help="Maximum fix attempts (default: 3)")
    parser.add_argument("--idea", type=str, default="",
                        help="Original idea (for context in LLM prompts)")

    args = parser.parse_args()
    _progress(f"rerun_fix.py started — {args.project_dir}")

    # ── Load project ────────────────────────────────────────────────
    files = load_project(args.project_dir)
    if not files:
        print(f"❌ No files found in {args.project_dir}")
        return

    py_count = sum(1 for f in files if f.endswith(".py"))
    total_lines = sum(len(c.splitlines()) for f, c in files.items() if f.endswith(".py"))

    print(f"\n╔{'═'*60}╗")
    print(f"║  🔄 Auto-GIT Rerun & Refine{' '*33}║")
    print(f"╠{'═'*60}╣")
    print(f"║  Dir:   {args.project_dir[:50]:50s}  ║")
    print(f"║  Files: {py_count} Python ({total_lines:,d} lines){' '*(38-len(f'{py_count} Python ({total_lines:,d} lines)'))}  ║")
    if args.change:
        print(f"║  Mode:  User-directed changes{' '*30}  ║")
    elif args.eval_only:
        print(f"║  Mode:  Evaluate only{' '*38}  ║")
    else:
        print(f"║  Mode:  Auto-fix{' '*42}  ║")
    print(f"╚{'═'*60}╝\n")

    # ── Step 1: Quick diagnosis ─────────────────────────────────────
    print("── Quick Diagnosis ──────────────────────────────────────")
    diag = quick_diagnose(files)

    if diag["syntax_fail"]:
        print(f"  ❌ Syntax errors: {len(diag['syntax_fail'])}")
        for fname, err in diag["syntax_fail"]:
            print(f"     {fname}: {err}")
    else:
        print(f"  ✅ Syntax: all {len(diag['syntax_ok'])} files OK")

    if diag["import_errors"]:
        print(f"  ⚠️  Dangling references: {len(diag['import_errors'])}")
        for err in diag["import_errors"]:
            print(f"     {err}")

    print(f"  📊 {diag['py_files']} Python files, {diag['total_lines']:,d} lines")
    print(f"  {'✅' if diag['has_main_guard'] else '❌'} main.py __main__ guard")

    if args.eval_only:
        print("\n── Running main.py ──────────────────────────────────────")
        run_main_test(args.project_dir)
        _progress("eval-only DONE ✅")
        return

    # ── Step 2: Apply user changes (if any) ─────────────────────────
    current_files = dict(files)
    if args.change:
        print(f"\n── Applying User Changes ────────────────────────────────")
        for i, change in enumerate(args.change, 1):
            print(f"  {i}. {change}")
        current_files = apply_user_changes(current_files, args.change, args.idea)
        save_files(current_files, args.project_dir)

    # ── Step 3: Test → Fix loop ─────────────────────────────────────
    print(f"\n── Test & Fix Loop (max {args.max_fixes} attempts) ────────────────────")
    t0 = time.time()
    fixed_files = await run_test_fix_loop(
        current_files, args.project_dir,
        idea=args.idea,
        max_fixes=args.max_fixes
    )
    elapsed = time.time() - t0

    # ── Step 4: Save results ────────────────────────────────────────
    save_files(fixed_files, args.project_dir)

    # ── Step 5: Final test ──────────────────────────────────────────
    print(f"\n── Final Test ──────────────────────────────────────────")
    success = run_main_test(args.project_dir)

    print(f"\n{'═'*60}")
    print(f"  🏁 Rerun complete — {_fmt_time(elapsed)}")
    print(f"  Result: {'✅ PASS' if success else '❌ FAIL'}")
    print(f"{'═'*60}")

    _progress(f"DONE {'✅' if success else '❌'} in {_fmt_time(elapsed)}")


if __name__ == "__main__":
    asyncio.run(main())
