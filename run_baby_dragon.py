"""Run pipeline: Baby Dragon Hatching — New AI Architecture"""
import sys, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ["PYTHONUTF8"] = "1"

import asyncio, logging
from dotenv import load_dotenv
load_dotenv("d:/Projects/auto-git/.env")

for n in ["langchain", "openai", "httpx", "urllib3", "httpcore"]:
    logging.getLogger(n).setLevel(logging.ERROR)
logging.getLogger("src.utils.model_manager").setLevel(logging.INFO)
logging.getLogger("src.langraph_pipeline.nodes").setLevel(logging.INFO)
logging.basicConfig(level=logging.WARNING, format="%(name)s: %(message)s")


IDEA = (
    "Baby Dragon Hatching: design a radically new AI architecture inspired by the biological "
    "process of a dragon hatching — a system that starts as a minimal seed (compressed latent "
    "world-model) and progressively 'hatches' / self-expands its own architecture at inference "
    "time based on task complexity. Core ideas: dynamic depth/width growth via learned gating, "
    "a meta-learning shell that wraps a small core model and spawns specialist sub-networks "
    "on-demand, progressive self-distillation so the hatched model compresses what it learned "
    "back into the seed for the next run. Should outperform static transformers on few-shot "
    "tasks while using fewer total FLOPs for simple inputs."
)

async def main():
    print("=" * 70)
    print("AUTO-GIT PIPELINE — Baby Dragon Hatching: New AI Architecture")
    print("  compound-beta research | expert debate | full codegen | self-eval")
    print("=" * 70)

    from src.langraph_pipeline.workflow_enhanced import run_auto_git_pipeline

    state = await run_auto_git_pipeline(
        idea=IDEA,
        use_web_search=True,
        max_debate_rounds=2,
        min_consensus_score=0.35,
        auto_publish=False,
        output_dir="output/baby_dragon",
        thread_id="baby_dragon_001",
        interactive=False,
        resume=False,   # fresh run
    )

    stage    = state.get("current_stage", "unknown")
    gen      = state.get("generated_code") or {}
    files    = gen.get("files", {})
    sol      = state.get("final_solution") or {}
    errs     = state.get("errors", [])
    se_score = state.get("self_eval_score", -1)

    print(f"\n{'='*70}")
    print(f"Stage        : {stage}")
    print(f"Approach     : {sol.get('approach_name', 'N/A')}")
    print(f"Innovation   : {sol.get('key_innovation', 'N/A')}")
    print(f"Self-Eval    : {se_score:.1f}/10" if se_score >= 0 else "Self-Eval    : skipped")
    print(f"Files        : {list(files.keys())}")
    for fname, code in files.items():
        lines = code.splitlines() if isinstance(code, str) else []
        print(f"  {fname:<30} {len(lines)} lines")
    if errs:
        print(f"\nErrors ({len(errs)}):")
        for e in errs[-5:]:
            print(f"  - {e}")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
