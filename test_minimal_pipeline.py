"""
Minimal Pipeline Test - Bypasses Import Issues
"""
import os
os.environ["PYTHONIOENCODING"] = "utf-8"

# Monkey patch platform.system() before any imports
import platform
_original_system = platform.system

def _fast_system():
    """Fast system detection without WMI"""
    return "Windows"

platform.system = _fast_system

import sys
sys.path.insert(0, "d:/Projects/auto-git")
sys.stdout.reconfigure(encoding='utf-8')

print("=" * 80)
print("MINIMAL PIPELINE TEST (No WMI Hang)")
print("=" * 80)

# Now safe to import
from src.langraph_pipeline.workflow_enhanced import create_workflow
from src.langraph_pipeline.state import create_initial_state

async def main():
    print("\n1. Creating workflow...")
    workflow = create_workflow(use_web_search=False, max_debate_rounds=1, max_fix_attempts=1)
    
    print("2. Compiling workflow...")
    app = workflow.compile()
    
    print("3. Creating initial state...")
    idea = """Tiny Recursive Models by Samsung

Implement compact recursive neural networks for mobile deployment."""
    
    state = create_initial_state(
        idea=idea,
        perspectives=["ML Researcher"],  # Just 1 for speed
        use_web_search=False
    )
    
    print("4. Running pipeline...")
    config = {"recursion_limit": 50, "configurable": {"thread_id": "test-1"}}
    
    async for event in app.astream(state, config=config):
        for node_name, node_output in event.items():
            stage = node_output.get("current_stage", "unknown")
            print(f"\n✓ {node_name}: {stage}")
            
            if "errors" in node_output:
                print(f"  ⚠️  Errors: {node_output['errors']}")
    
    print("\n" + "=" * 80)
    print("PIPELINE COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
