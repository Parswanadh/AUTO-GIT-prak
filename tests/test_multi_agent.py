"""Test Multi-Agent Parallel Execution"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.multi_agent import MultiAgentCoordinator, ParallelExecutor, TaskDistributor
from src.multi_agent.task_distributor import TaskPriority


# Mock async functions for testing
async def mock_generate_file(filename: str, prompt: str) -> str:
    """Mock file generation"""
    await asyncio.sleep(0.1)  # Simulate work
    return f"# {filename}\n# Generated from: {prompt[:50]}"


async def mock_critique(solution: str, perspective: str) -> str:
    """Mock critique"""
    await asyncio.sleep(0.05)
    return f"Critique from {perspective}: {solution[:30]}"


async def mock_search(query: str) -> list:
    """Mock search"""
    await asyncio.sleep(0.08)
    return [f"Result for: {query}"]


async def mock_slow_task(**kwargs) -> str:
    """Mock slow task"""
    await asyncio.sleep(0.5)
    return "slow result"


async def mock_fast_task(**kwargs) -> str:
    """Mock fast task"""
    await asyncio.sleep(0.05)
    return "fast result"


async def test_parallel_executor():
    """Test 1: Basic Parallel Executor"""
    print("\n" + "="*60)
    print("TEST 1: Parallel Executor")
    print("="*60)
    
    executor = ParallelExecutor(max_concurrent=3)
    
    # Create test tasks
    tasks = [
        (mock_fast_task, {}),
        (mock_fast_task, {}),
        (mock_fast_task, {}),
    ]
    
    print("\n⏱️  Executing 3 tasks in parallel...")
    start = time.time()
    results = await executor.execute_parallel(tasks)
    elapsed = time.time() - start
    
    print(f"✅ Completed in {elapsed:.2f}s")
    print(f"   Expected: ~0.05s (parallel)")
    print(f"   Sequential would be: ~0.15s")
    
    # Verify results
    successful = sum(1 for r in results if r.get("success"))
    assert successful == 3, "All tasks should succeed"
    assert elapsed < 0.2, "Should be much faster than sequential"
    
    # Get stats
    stats = executor.get_stats(results)
    print(f"\n📊 Stats:")
    print(f"   Success rate: {stats['success_rate']:.0%}")
    print(f"   Avg time: {stats['avg_elapsed']:.3f}s")
    
    print("\n✅ Test 1 PASSED")
    return True


async def test_task_distributor():
    """Test 2: Task Distributor with Dependencies"""
    print("\n" + "="*60)
    print("TEST 2: Task Distributor")
    print("="*60)
    
    distributor = TaskDistributor()
    
    # Add tasks with dependencies
    distributor.add_task(
        "research",
        "Research",
        mock_search,
        {"query": "test"},
        priority=TaskPriority.HIGH,
        estimated_duration=10.0
    )
    
    distributor.add_task(
        "generate_1",
        "Generate File 1",
        mock_generate_file,
        {"filename": "file1.py", "prompt": "test"},
        dependencies=["research"],
        estimated_duration=15.0
    )
    
    distributor.add_task(
        "generate_2",
        "Generate File 2",
        mock_generate_file,
        {"filename": "file2.py", "prompt": "test"},
        dependencies=["research"],
        estimated_duration=12.0
    )
    
    distributor.add_task(
        "test",
        "Test Code",
        mock_fast_task,
        {},
        dependencies=["generate_1", "generate_2"],
        priority=TaskPriority.CRITICAL,
        estimated_duration=5.0
    )
    
    print("\n🌳 Task Dependency Tree:")
    print(distributor.visualize_dependencies())
    
    # Get ready tasks (should be only 'research')
    ready = distributor.get_ready_tasks()
    assert len(ready) == 1
    assert ready[0].task_id == "research"
    print(f"\n✅ Ready tasks: {[t.task_id for t in ready]}")
    
    # Mark research complete
    distributor.mark_completed("research")
    
    # Now generate tasks should be ready
    ready = distributor.get_ready_tasks()
    assert len(ready) == 2
    ready_ids = {t.task_id for t in ready}
    assert ready_ids == {"generate_1", "generate_2"}
    print(f"✅ After research: {[t.task_id for t in ready]}")
    
    # Estimate total time
    total_time = distributor.estimate_total_time(max_concurrent=2)
    print(f"\n⏱️  Estimated total time: {total_time:.1f}s")
    
    # Get critical path
    critical = distributor.get_critical_path()
    print(f"🔴 Critical path: {[t.operation for t in critical]}")
    
    print("\n✅ Test 2 PASSED")
    return True


async def test_file_generation():
    """Test 3: Parallel File Generation"""
    print("\n" + "="*60)
    print("TEST 3: Parallel File Generation")
    print("="*60)
    
    coordinator = MultiAgentCoordinator(max_concurrent=3)
    
    file_specs = [
        {"filename": "model.py", "prompt": "Create a PyTorch model"},
        {"filename": "train.py", "prompt": "Create training loop"},
        {"filename": "utils.py", "prompt": "Create utility functions"},
    ]
    
    print(f"\n📝 Generating {len(file_specs)} files...")
    start = time.time()
    results = await coordinator.generate_files_parallel(
        file_specs,
        mock_generate_file,
        timeout=5.0
    )
    elapsed = time.time() - start
    
    print(f"✅ Generated in {elapsed:.2f}s")
    
    # Verify all succeeded
    for result in results:
        print(f"   {result['filename']}: {'✅' if result['success'] else '❌'}")
        assert result['success'], f"File generation failed: {result.get('error')}"
    
    print("\n✅ Test 3 PASSED")
    return True


async def test_parallel_critique():
    """Test 4: Parallel Critique"""
    print("\n" + "="*60)
    print("TEST 4: Parallel Critique")
    print("="*60)
    
    coordinator = MultiAgentCoordinator(max_concurrent=4)
    
    solution = "Implement a transformer model with attention mechanism"
    perspectives = [
        "ML Researcher",
        "Systems Engineer",
        "Applied Scientist",
        "Software Architect"
    ]
    
    print(f"\n🔍 Running {len(perspectives)} parallel critiques...")
    results = await coordinator.critique_parallel(
        solution,
        perspectives,
        mock_critique,
        timeout=5.0
    )
    
    # Verify all succeeded
    for result in results:
        print(f"   {result['perspective']}: {'✅' if result['success'] else '❌'}")
        assert result['success']
    
    print("\n✅ Test 4 PASSED")
    return True


async def test_dependency_execution():
    """Test 5: Execution with Dependencies"""
    print("\n" + "="*60)
    print("TEST 5: Dependency-Based Execution")
    print("="*60)
    
    coordinator = MultiAgentCoordinator(max_concurrent=3)
    
    task_configs = [
        {
            "task_id": "init",
            "operation": "Initialize",
            "func": mock_fast_task,
            "kwargs": {},
            "priority": TaskPriority.HIGH,
            "estimated_duration": 5.0
        },
        {
            "task_id": "process_1",
            "operation": "Process Data 1",
            "func": mock_fast_task,
            "kwargs": {},
            "dependencies": ["init"],
            "estimated_duration": 10.0
        },
        {
            "task_id": "process_2",
            "operation": "Process Data 2",
            "func": mock_fast_task,
            "kwargs": {},
            "dependencies": ["init"],
            "estimated_duration": 10.0
        },
        {
            "task_id": "aggregate",
            "operation": "Aggregate Results",
            "func": mock_fast_task,
            "kwargs": {},
            "dependencies": ["process_1", "process_2"],
            "priority": TaskPriority.CRITICAL,
            "estimated_duration": 5.0
        }
    ]
    
    print("\n🚀 Executing tasks with dependencies...")
    results = await coordinator.execute_with_dependencies(task_configs)
    
    # Verify all succeeded
    successful = sum(1 for r in results if r.get("success"))
    print(f"\n📊 Results: {successful}/{len(results)} succeeded")
    assert successful == len(results)
    
    print("\n✅ Test 5 PASSED")
    return True


async def test_batch_processing():
    """Test 6: Batch Processing"""
    print("\n" + "="*60)
    print("TEST 6: Batch Processing")
    print("="*60)
    
    coordinator = MultiAgentCoordinator(max_concurrent=2)
    
    items = [f"item_{i}" for i in range(6)]
    
    print(f"\n📦 Processing {len(items)} items in batches...")
    results = await coordinator.batch_process(
        items,
        lambda item: mock_fast_task(),
        batch_size=2,
        timeout=5.0
    )
    
    successful = sum(1 for r in results if r.get("success"))
    print(f"✅ Processed: {successful}/{len(items)}")
    assert successful == len(items)
    
    # Get stats
    stats = coordinator.get_performance_stats(results)
    print(f"\n📊 Performance:")
    print(f"   Success rate: {stats['success_rate']:.0%}")
    print(f"   Total time: {stats['total_elapsed']:.2f}s")
    
    print("\n✅ Test 6 PASSED")
    return True


async def test_race_condition():
    """Test 7: Task Racing (First Wins)"""
    print("\n" + "="*60)
    print("TEST 7: Task Racing")
    print("="*60)
    
    executor = ParallelExecutor()
    
    tasks = [
        (mock_slow_task, {}),
        (mock_fast_task, {}),
        (mock_slow_task, {}),
    ]
    
    print("\n🏁 Racing 3 tasks (1 fast, 2 slow)...")
    start = time.time()
    result = await executor.race(tasks, timeout=10.0)
    elapsed = time.time() - start
    
    print(f"✅ Winner in {elapsed:.2f}s")
    print(f"   Expected: ~0.05s (fast task wins)")
    assert result.get("success")
    assert elapsed < 0.2, "Fast task should win"
    
    print("\n✅ Test 7 PASSED")
    return True


async def main():
    """Run all tests"""
    print("\n🧪 MULTI-AGENT PARALLEL EXECUTION TESTS")
    print("="*60)
    
    tests = [
        ("Parallel Executor", test_parallel_executor),
        ("Task Distributor", test_task_distributor),
        ("File Generation", test_file_generation),
        ("Parallel Critique", test_parallel_critique),
        ("Dependency Execution", test_dependency_execution),
        ("Batch Processing", test_batch_processing),
        ("Task Racing", test_race_condition),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = await test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ {name} FAILED: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Final summary
    print("\n" + "="*60)
    print("FINAL SUMMARY")
    print("="*60)
    
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {name:30} {status}")
    
    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\n📊 Results: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED - Multi-Agent Integration Complete!")
        return True
    else:
        print(f"\n⚠️ {total - passed} test(s) failed")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
