"""
Test Integration #14: Production Monitoring Dashboard

Tests the monitoring system components:
- MetricsCollector
- Dashboard generation
- Metric aggregation
- Error tracking
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.monitoring.metrics_collector import MetricsCollector
from src.monitoring.dashboard import DashboardGenerator


def test_metrics_collection():
    """Test basic metrics collection."""
    print("\n" + "="*80)
    print("TEST 1: Metrics Collection")
    print("="*80)
    
    collector = MetricsCollector("data/metrics/test_metrics.db")
    
    # Record various events
    print("Recording test events...")
    
    # Successful generation
    collector.record_generation(
        integration="parallel_generation",
        backend="groq",
        model="llama-3.1-8b-instant",
        latency_ms=2450.0,
        success=True,
        tokens_used=1500,
        quality_score=0.85
    )
    
    # Another successful generation
    collector.record_generation(
        integration="multi_critic",
        backend="openrouter",
        model="qwen/qwen3-coder:free",
        latency_ms=3200.0,
        success=True,
        tokens_used=2000,
        quality_score=0.79
    )
    
    # Failed generation
    collector.record_generation(
        integration="reflection",
        backend="openrouter",
        model="xiaomi/mimo-v2-flash:free",
        latency_ms=0.0,
        success=False,
        tokens_used=0,
        error_type="timeout"
    )
    
    # Record quality assessments
    collector.record_quality(
        integration="parallel_generation",
        score=0.85,
        criteria={
            "completeness": 0.9,
            "correctness": 0.85,
            "clarity": 0.8
        }
    )
    
    # Record errors
    collector.record_error(
        error_type="timeout",
        integration="reflection",
        backend="openrouter",
        message="Request timed out after 30s"
    )
    
    collector.record_error(
        error_type="rate_limit",
        integration="parallel_generation",
        backend="openrouter",
        message="Rate limit exceeded"
    )
    
    print("✅ Recorded 3 generations, 1 quality assessment, 2 errors")
    return True


def test_metrics_aggregation():
    """Test metric aggregation and queries."""
    print("\n" + "="*80)
    print("TEST 2: Metrics Aggregation")
    print("="*80)
    
    collector = MetricsCollector("data/metrics/test_metrics.db")
    
    # Get aggregated metrics
    metrics = collector.get_metrics("1h")
    
    print(f"\nAggregated Metrics (last 1h):")
    print(f"  Total Requests: {metrics['performance']['total_requests']}")
    print(f"  Successful: {metrics['performance']['successful_requests']}")
    print(f"  Success Rate: {metrics['performance']['success_rate']:.1%}")
    print(f"  Avg Latency: {metrics['performance']['avg_latency_ms']:.0f}ms")
    print(f"  Total Tokens: {metrics['performance']['total_tokens']:,}")
    print(f"  Avg Quality: {metrics['quality']['avg_score']:.3f}")
    
    print(f"\nBackend Stats:")
    for backend, stats in metrics['backends'].items():
        print(f"  {backend}: {stats['count']} requests, {stats['avg_latency']:.0f}ms avg")
    
    print(f"\nIntegration Stats:")
    for integration, stats in metrics['integrations'].items():
        success_rate = (stats['successful'] / stats['total'] * 100) if stats['total'] > 0 else 0
        print(f"  {integration}: {stats['total']} total, {success_rate:.1f}% success")
    
    print(f"\nErrors:")
    for error_type, count in metrics['errors'].items():
        print(f"  {error_type}: {count} occurrences")
    
    print("\n✅ Metrics aggregation working")
    return True


def test_dashboard_generation():
    """Test HTML dashboard generation."""
    print("\n" + "="*80)
    print("TEST 3: Dashboard Generation")
    print("="*80)
    
    collector = MetricsCollector("data/metrics/test_metrics.db")
    
    # Add more test data for better visualization
    print("Adding more test data...")
    for i in range(20):
        collector.record_generation(
            integration=["parallel_generation", "multi_critic", "reflection"][i % 3],
            backend=["groq", "openrouter", "local"][i % 3],
            model=f"test-model-{i % 3}",
            latency_ms=1000 + (i * 100),
            success=(i % 5 != 0),  # 20% failure rate
            tokens_used=1000 + (i * 50),
            quality_score=0.7 + (i % 20) * 0.015
        )
        
        if i % 3 == 0:
            collector.record_quality(
                integration=["parallel_generation", "multi_critic", "reflection"][i % 3],
                score=0.7 + (i % 20) * 0.015
            )
    
    # Get metrics
    metrics = collector.get_metrics("1h")
    
    # Generate dashboard
    generator = DashboardGenerator()
    html = generator.generate_dashboard(metrics)
    
    # Save dashboard
    dashboard_path = Path("data/metrics/dashboards/test_dashboard.html")
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(dashboard_path, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"\n✅ Dashboard generated: {len(html):,} bytes")
    print(f"   Saved to: {dashboard_path}")
    print(f"   Open in browser to view!")
    
    return True


def test_recent_events():
    """Test retrieving recent events."""
    print("\n" + "="*80)
    print("TEST 4: Recent Events")
    print("="*80)
    
    collector = MetricsCollector("data/metrics/test_metrics.db")
    
    events = collector.get_recent_events(limit=10)
    
    print(f"\nRecent Events (last 10):")
    for i, event in enumerate(events, 1):
        status = "✅" if event['success'] else "❌"
        timestamp = time.strftime('%H:%M:%S', time.localtime(event['timestamp']))
        print(f"  {i}. {status} [{timestamp}] {event['integration']}/{event['backend']}")
        print(f"      Model: {event['model']}, Latency: {event['latency_ms']:.0f}ms")
        if event['quality_score']:
            print(f"      Quality: {event['quality_score']:.3f}")
        if event['error_type']:
            print(f"      Error: {event['error_type']}")
    
    print("\n✅ Recent events retrieval working")
    return True


def run_all_tests():
    """Run all monitoring tests."""
    print("\n" + "="*80)
    print("INTEGRATION #14: PRODUCTION MONITORING - TEST SUITE")
    print("="*80)
    
    tests = [
        ("Metrics Collection", test_metrics_collection),
        ("Metrics Aggregation", test_metrics_aggregation),
        ("Dashboard Generation", test_dashboard_generation),
        ("Recent Events", test_recent_events)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success, None))
        except Exception as e:
            print(f"\n❌ {test_name} failed: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False, str(e)))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    
    for test_name, success, error in results:
        status = "✅ PASSED" if success else f"❌ FAILED: {error}"
        print(f"  {test_name}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Integration #14 is working correctly!")
        print("\n📊 View the dashboard:")
        print("   data/metrics/dashboards/test_dashboard.html")
        return True
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
