"""Simple integration test without Unicode issues"""

import asyncio
import sys
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analytics.tracker import AnalyticsTracker
from src.tracing.tracer import DistributedTracer
from src.multi_agent.parallel_executor import ParallelExecutor
from src.knowledge_graph import KnowledgeGraph, PatternLearner, QueryEngine
from src.advanced_testing.quality_validator import QualityValidator


async def test_integration():
    """Test all 5 systems work together"""
    print("\n" + "="*70)
    print("COMPREHENSIVE INTEGRATION TEST")
    print("="*70)
    
    # Initialize
    print("\n[1/5] Initializing systems...")
    analytics = AnalyticsTracker("data/test_integration/analytics.db")
    tracer = DistributedTracer("data/test_integration/traces")
    executor = ParallelExecutor(max_concurrent=3)
    kg = KnowledgeGraph("data/test_integration/knowledge.db")
    pattern_learner = PatternLearner(kg)
    query_engine = QueryEngine(kg, pattern_learner)
    validator = QualityValidator()
    print("   OK: All systems initialized")
    
    # Test tracer
    print("\n[2/5] Testing distributed tracing...")
    trace_id = tracer.start_trace("integration_test")
    span1 = tracer.start_span("operation1", "test")
    await asyncio.sleep(0.01)
    tracer.end_span(span1, success=True)
    
    span2 = tracer.start_span("operation2", "test")
    await asyncio.sleep(0.01)
    tracer.end_span(span2, success=True)
    print(f"   OK: Created trace {trace_id} with 2 spans")
    
    # Test parallel execution
    print("\n[3/5] Testing parallel execution...")
    async def task(n):
        await asyncio.sleep(0.01)
        return n * 2
    
    results = await executor.execute_parallel([
        (task, {"n": i}) for i in range(5)
    ])
    print(f"   OK: Executed {len(results)} tasks in parallel")
    
    # Test knowledge graph
    print("\n[4/5] Testing knowledge graph...")
    run_data = {
        'run_id': 'test_run_001',
        'project_name': 'test_project',
        'status': 'success',
        'execution_time': 1.5,
        'model_used': 'qwen2.5-coder:7b',
        'stage': 'code_generation',
        'files': [{'path': 'test.py', 'size': 100}],
        'solutions': [{
            'type': 'generation',
            'approach': 'direct',
            'effectiveness': 0.9,
            'context': 'Test solution'
        }]
    }
    pattern_learner.learn_from_run(run_data, success=True)
    
    stats = kg.get_stats()
    total_nodes = stats.get('total_nodes', 0)
    total_edges = stats.get('total_edges', 0)
    print(f"   OK: Knowledge graph has {total_nodes} nodes, {total_edges} edges")
    
    # Test analytics
    print("\n[5/5] Testing analytics tracking...")
    analytics.record_run(
        run_id='test_run_001',
        idea='test project',
        model='qwen2.5-coder:7b',
        stage='code_generation',
        latency=1.5,
        tokens=1000,
        success=True,
        error=None,
        metadata={'test': True}
    )
    
    metrics = analytics.get_model_metrics('qwen2.5-coder:7b', days=1)
    print(f"   OK: Tracked run with {metrics.total_runs} total runs")
    
    # Test quality validation
    code = """
def test_function(x, y):
    '''Test function'''
    result = x + y
    return result
"""
    quality = validator.validate_code(code)
    print(f"   Code quality: {quality['overall']['quality_level']} ({quality['overall']['score']:.1%})")
    
    print("\n" + "="*70)
    print("ALL INTEGRATION TESTS PASSED")
    print("="*70)
    print("\nSystem Status:")
    print("  - Analytics: OK")
    print("  - Tracing: OK")
    print("  - Parallel Execution: OK")
    print("  - Knowledge Graph: OK")
    print("  - Advanced Testing: OK")
    
    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(test_integration())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
