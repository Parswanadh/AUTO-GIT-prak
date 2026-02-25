"""Minimal test to find where pipeline hangs"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

print("=" * 80)
print("MINIMAL TEST - Finding the hang")
print("=" * 80)

# Test 1: Import
print("\n1. Testing imports...")
try:
    from src.langraph_pipeline.workflow_enhanced import create_autogit_workflow
    from src.langraph_pipeline.state import AutoGITState
    print("   ✅ Imports OK")
except Exception as e:
    print(f"   ❌ Import failed: {e}")
    sys.exit(1)

# Test 2: Create workflow
print("\n2. Creating workflow...")
try:
    workflow = create_autogit_workflow(
        use_web_search=False,
        max_debate_rounds=1,
        max_fix_attempts=1
    )
    print("   ✅ Workflow created")
except Exception as e:
    print(f"   ❌ Workflow creation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Compile workflow  
print("\n3. Compiling workflow...")
try:
    app = workflow.compile(
        checkpointer=None,  # No checkpointer for simple test
    )
    print("   ✅ Workflow compiled")
except Exception as e:
    print(f"   ❌ Compilation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Create minimal state
print("\n4. Creating initial state...")
try:
    initial_state: AutoGITState = {
        "idea": "Test idea for debugging",
        "perspectives": ["ML Researcher"],
        "use_web_search": False,
        "current_stage": "start",
        "current_round": 0,
        "errors": [],
        "warnings": []
    }
    print("   ✅ State created")
except Exception as e:
    print(f"   ❌ State creation failed: {e}")
    sys.exit(1)

print("\n5. Invoking pipeline...")
print("   (This is where it might hang)")
import asyncio

async def run_test():
    try:
        print("   Starting invoke...")
        result = await app.ainvoke(initial_state)
        print(f"   ✅ Pipeline completed! Stage: {result.get('current_stage')}")
        return result
    except Exception as e:
        print(f"   ❌ Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        return None

print("\nRunning async test...")
result = asyncio.run(run_test())

if result:
    print("\n✅ TEST PASSED")
else:
    print("\n❌ TEST FAILED")
