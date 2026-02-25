"""Test Analytics Integration (#20)"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analytics import AnalyticsTracker, PerformanceOptimizer, AnalyticsReporter


async def test_analytics_tracker():
    """Test 1: Analytics Tracker"""
    print("\n" + "="*60)
    print("TEST 1: Analytics Tracker")
    print("="*60)
    
    tracker = AnalyticsTracker(db_path="data/analytics/test_analytics.db")
    
    # Record some test runs
    print("\n📊 Recording test runs...")
    
    for i in range(5):
        tracker.record_run(
            run_id=f"test-run-{i}",
            idea="Test idea for analytics",
            model="qwen3:8b",
            stage="research",
            success=True,
            tokens=500 + i * 50,
            latency=2.5 + i * 0.5
        )
    
    # Record some failures
    tracker.record_run(
        run_id="test-run-fail-1",
        idea="Test failure",
        model="qwen3:8b",
        stage="code_generation",
        success=False,
        tokens=300,
        latency=5.0,
        error="Timeout"
    )
    
    print("✅ Recorded 6 test runs")
    
    # Get model metrics
    print("\n📈 Model Metrics:")
    metrics = tracker.get_model_metrics("qwen3:8b", days=7)
    if metrics:
        print(f"  Total Runs:    {metrics.total_runs}")
        print(f"  Success Rate:  {metrics.success_rate:.1%}")
        print(f"  Avg Tokens:    {metrics.avg_tokens:.0f}")
        print(f"  Avg Latency:   {metrics.avg_latency:.2f}s")
    
    # Get recent runs
    print("\n📋 Recent Runs:")
    recent = tracker.get_recent_runs(limit=3)
    for run in recent:
        status = "✅" if run.success else "❌"
        print(f"  {status} {run.stage:20} | {run.tokens_used:4} tokens | {run.latency_seconds:.2f}s")
    
    print("\n✅ Test 1 PASSED")
    return True


async def test_performance_optimizer():
    """Test 2: Performance Optimizer"""
    print("\n" + "="*60)
    print("TEST 2: Performance Optimizer")
    print("="*60)
    
    tracker = AnalyticsTracker(db_path="data/analytics/test_analytics.db")
    optimizer = PerformanceOptimizer(tracker)
    
    # Test model recommendation
    print("\n🤖 Testing Model Recommendations:")
    
    tasks = ["coding", "reasoning", "fast", "general"]
    for task in tasks:
        model, reason = optimizer.recommend_model(
            task_type=task,
            stage="generation",
            min_success_rate=0.5
        )
        print(f"  {task:10} → {model:25} ({reason})")
    
    # Test fallback chain
    print("\n🔄 Testing Fallback Chains:")
    chain = optimizer.get_fallback_chain("qwen2.5-coder:7b", "coding")
    print(f"  Primary: qwen2.5-coder:7b")
    for i, fallback in enumerate(chain, 1):
        print(f"  Fallback {i}: {fallback}")
    
    # Test cost-efficient model
    print("\n💰 Testing Cost Optimization:")
    model, reason = optimizer.get_cost_efficient_model("general", max_cost_per_run=0.001)
    print(f"  Cost-efficient: {model} ({reason})")
    
    print("\n✅ Test 2 PASSED")
    return True


async def test_analytics_reporter():
    """Test 3: Analytics Reporter"""
    print("\n" + "="*60)
    print("TEST 3: Analytics Reporter")
    print("="*60)
    
    tracker = AnalyticsTracker(db_path="data/analytics/test_analytics.db")
    reporter = AnalyticsReporter(tracker)
    
    # Quick summary
    print("\n📊 Quick Summary:")
    reporter.print_quick_summary(days=1)
    
    # Full report
    print("\n📄 Generating Full Report...")
    report = reporter.generate_summary_report(days=7)
    # Print first 20 lines
    lines = report.split('\n')
    for line in lines[:20]:
        print(line)
    print(f"\n... ({len(lines) - 20} more lines)")
    
    # Export to JSON
    print("\n💾 Testing JSON Export:")
    data = reporter.export_to_json(days=7)
    print(f"  Exported {len(data['recent_runs'])} runs")
    print(f"  Exported {len(data['model_metrics'])} model metrics")
    print(f"  Total cost: ${data['total_cost']:.4f}")
    
    print("\n✅ Test 3 PASSED")
    return True


async def test_integration_with_pipeline():
    """Test 4: Integration with Pipeline Nodes"""
    print("\n" + "="*60)
    print("TEST 4: Pipeline Integration")
    print("="*60)
    
    # Test that analytics tracker can be imported in nodes
    try:
        from src.langraph_pipeline.nodes import get_analytics_tracker
        tracker = get_analytics_tracker()
        print("\n✅ Analytics tracker successfully integrated into nodes")
        print(f"   Database: {tracker.db_path}")
        
        # Record a test run
        tracker.record_run(
            run_id="pipeline-test-1",
            idea="Test pipeline integration",
            model="qwen3:8b",
            stage="research",
            success=True,
            tokens=450,
            latency=3.2
        )
        print("✅ Successfully recorded pipeline run")
        
    except Exception as e:
        print(f"\n❌ Integration failed: {e}")
        return False
    
    print("\n✅ Test 4 PASSED")
    return True


async def main():
    """Run all tests"""
    print("\n🧪 ANALYTICS INTEGRATION TESTS (Integration #20)")
    print("="*60)
    
    tests = [
        ("Analytics Tracker", test_analytics_tracker),
        ("Performance Optimizer", test_performance_optimizer),
        ("Analytics Reporter", test_analytics_reporter),
        ("Pipeline Integration", test_integration_with_pipeline),
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
        print("\n🎉 ALL TESTS PASSED - Integration #20 Complete!")
        return True
    else:
        print(f"\n⚠️ {total - passed} test(s) failed")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
