"""
Full pipeline smoke test with Groq fallback
Idea: Build a simple in-memory cache with TTL expiry
"""
import asyncio
import os
import sys
import logging

# Set parent dir on path
sys.path.insert(0, 'd:/Projects/auto-git')

from dotenv import load_dotenv
load_dotenv('d:/Projects/auto-git/.env')

# Show only important logs
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
for name in ["src", "langchain", "openai", "httpx"]:
    logging.getLogger(name).setLevel(logging.WARNING)

async def main():
    print("\n" + "=" * 65)
    print("AUTO-GIT PIPELINE TEST")
    print("=" * 65)
    print("Idea: Build a Python in-memory cache with TTL expiry and LRU eviction")
    print("Mode: No web search | 1 debate round | Save locally")
    print("=" * 65 + "\n")

    from src.langraph_pipeline.workflow_enhanced import run_auto_git_pipeline

    state = await run_auto_git_pipeline(
        idea="Build a Python in-memory cache with TTL expiry and LRU eviction",
        use_web_search=False,           # Skip SearXNG
        max_debate_rounds=1,            # Fast: 1 round
        min_consensus_score=0.3,        # Easy consensus
        auto_publish=False,             # Save locally
        output_dir="output/test_run",
        thread_id="smoke_test_001"
    )

    print("\n" + "=" * 65)
    print("PIPELINE RESULTS")
    print("=" * 65)
    print(f"Stage reached    : {state.get('current_stage', 'unknown')}")
    print(f"Problems found   : {len(state.get('problems', []))}")
    print(f"Selected problem : {str(state.get('selected_problem', 'N/A'))[:80]}")
    print(f"Debate rounds    : {len(state.get('debate_rounds', []))}")
    print(f"Final solution   : {str(state.get('final_solution', {}).get('approach_name', 'N/A'))[:60]}")

    gen = state.get('generated_code') or {}
    files = gen.get('files', {})
    print(f"Generated files  : {list(files.keys())}")
    for fname, content in files.items():
        lines = len(content.split('\n')) if content else 0
        print(f"  {fname}: {lines} lines")

    output_path = state.get('output_path', 'N/A')
    print(f"Output saved to  : {output_path}")

    errors = state.get('errors', [])
    if errors:
        print(f"Errors           : {errors[:2]}")
    else:
        print("Errors           : None")

    print("\n" + "=" * 65)
    if state.get('current_stage') in ('published', 'saved_locally', 'saved_locally_after_error'):
        print("[OK] PIPELINE COMPLETED SUCCESSFULLY!")
    elif files:
        print("[OK] CODE GENERATED - pipeline ran to code stage!")
    else:
        print(f"[PARTIAL] Stopped at stage: {state.get('current_stage')}")
    print("=" * 65 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
