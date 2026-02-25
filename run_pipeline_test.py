"""Quick pipeline smoke test - run with: conda run -n auto-git python run_pipeline_test.py

Progress is written to  logs/pipeline_progress.txt  so you can poll:
    Get-Content logs/pipeline_progress.txt -Tail 5
"""
import sys, os, time, json, atexit, signal
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ["PYTHONUTF8"] = "1"

import asyncio, logging
from datetime import datetime
from dotenv import load_dotenv
load_dotenv("d:/Projects/auto-git/.env")

for n in ["langchain", "openai", "httpx", "urllib3", "httpcore"]:
    logging.getLogger(n).setLevel(logging.ERROR)
logging.getLogger("src.utils.model_manager").setLevel(logging.INFO)
logging.getLogger("src.langraph_pipeline.nodes").setLevel(logging.INFO)
logging.basicConfig(level=logging.WARNING, format="%(name)s: %(message)s")

# ── Progress / heartbeat file ───────────────────────────────────────
PROGRESS_FILE = os.path.join("logs", "pipeline_progress.txt")
_start_wall = time.time()
os.makedirs("logs", exist_ok=True)


def _progress(msg: str):
    """Append a timestamped line to the progress file AND stdout."""
    elapsed = time.time() - _start_wall
    line = f"[{datetime.now().strftime('%H:%M:%S')} +{elapsed:6.0f}s] {msg}"
    print(line, flush=True)
    with open(PROGRESS_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _on_exit():
    _progress("PROCESS EXIT")


atexit.register(_on_exit)
_progress("pipeline_test.py started")


IDEA = (
    "Baby Dragon: a new AI architecture that hatches like a dragon egg — starts small, "
    "self-evolves by consuming compute, and grows richer internal representations over time. "
    "Design the full architecture: a seed model (tiny transformer) that bootstraps itself "
    "via recursive self-distillation, dynamic layer addition, and an internal reward signal "
    "based on prediction surprise. Implement training loop, self-evolution scheduler, "
    "layer-growth controller, surprise metric, and a demo that shows the dragon grow from "
    "1-layer to 6-layer while training on a toy sequence task."
)

async def main():
    _progress("PIPELINE STARTING — Baby Dragon")
    print("=" * 70)
    print("AUTO-GIT PIPELINE — Baby Dragon: Self-Evolving AI Architecture")
    print("  compound-beta deep research | 3-round expert debate | full pipeline")
    print("=" * 70)

    from src.langraph_pipeline.workflow_enhanced import run_auto_git_pipeline

    _progress("workflow imported, calling run_auto_git_pipeline …")
    try:
        state = await run_auto_git_pipeline(
            idea=IDEA,
            use_web_search=True,
            max_debate_rounds=3,
            min_consensus_score=0.35,
            auto_publish=False,
            output_dir="output/baby_dragon",
            thread_id="baby_dragon_001",
            interactive=False,
            resume=True,          # ♻️  auto-resume if pipeline was interrupted
        )
    except Exception as exc:
        _progress(f"PIPELINE FAILED: {type(exc).__name__}: {exc}")
        raise

    if state is None:
        _progress("PIPELINE RETURNED None — possibly resumed from completed checkpoint. Delete logs/pipeline_checkpoints.db to force fresh run.")
        return

    stage = state.get("current_stage", "unknown")
    _progress(f"PIPELINE FINISHED — stage={stage}")
    problems = state.get("problems", [])
    gen = state.get("generated_code") or {}
    files = gen.get("files", {})
    sol = state.get("final_solution") or {}
    errs = state.get("errors", [])
    persp_cfgs = state.get("dynamic_perspective_configs") or []
    rc = state.get("research_context") or {}
    cb = rc.get("compound_beta_research") or {}

    print(f"\n{'='*70}")
    print(f"Idea     : {IDEA[:100]}...")
    print(f"Stage    : {stage}")

    if cb.get("sota_summary"):
        print(f"\nSOTA Summary:")
        print(f"  {cb['sota_summary'][:300]}")

    if persp_cfgs:
        print(f"\nDomain Experts Generated ({len(persp_cfgs)}):")
        for p in persp_cfgs:
            print(f"  • {p.get('name','?')}: {p.get('role','')[:70]}")

    if problems:
        print(f"\nProblems Extracted ({len(problems)}):")
        for i, p in enumerate(problems[:5]):
            print(f"  {i+1}. {str(p)[:100]}")

    print(f"\nSelected: {state.get('selected_problem', 'N/A')[:120] if state.get('selected_problem') else 'N/A'}")
    print(f"Solution : {sol.get('approach_name', sol.get('title', 'N/A'))}")
    print(f"Files    : {list(files.keys())}")
    if errs:
        print("\nErrors:")
        for e in errs[:3]:
            print(f"  - {str(e)[:120]}")
    print("=" * 70)

    # Save generated files to disk
    out = "output/baby_dragon/generated"
    os.makedirs(out, exist_ok=True)
    for fname, code in files.items():
        path = os.path.join(out, fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(str(code))
    if files:
        print(f"\n✅ Saved {len(files)} files to {out}/")
        for fname, code in files.items():
            lines = str(code).split("\n")
            print(f"  {fname:30s} {len(lines):4d} lines")
        # Print first .py file preview
        main_file = next(
            (f for f in files if f.endswith(".py") and "main" in f.lower()),
            next((f for f in files if f.endswith(".py")), None),
        )
        if main_file:
            print(f"\n--- {main_file} (first 40 lines) ---")
            print("\n".join(str(files[main_file]).split("\n")[:40]))


asyncio.run(main())

