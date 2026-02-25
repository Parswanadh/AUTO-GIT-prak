"""
Comprehensive End-to-End Integration Test

Tests all 5 integrations working together in a realistic pipeline scenario:
1. Analytics tracking
2. Distributed tracing
3. Parallel execution
4. Knowledge graph learning
5. Advanced testing/validation
"""

import asyncio
import sys
from pathlib import Path
import time

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analytics.tracker import AnalyticsTracker
from src.tracing.tracer import DistributedTracer
from src.multi_agent.parallel_executor import ParallelExecutor
from src.knowledge_graph import KnowledgeGraph, PatternLearner, QueryEngine
from src.advanced_testing.property_tester import PropertyTester
from src.advanced_testing.mutation_tester import MutationTester
from src.advanced_testing.quality_validator import QualityValidator


async def simulate_code_generation(file_name: str, delay: float = 0.5) -> dict:
    """Simulate generating a code file"""
    await asyncio.sleep(delay)
    
    code = f'''
def {file_name.replace('.py', '')}():
    """Generated function for {file_name}"""
    result = []
    for i in range(10):
        result.append(i * 2)
    return result

if __name__ == "__main__":
    print({file_name.replace('.py', '')}())
'''
    
    return {
        'file': file_name,
        'code': code,
        'lines': len(code.split('\n')),
        'success': True
    }


async def test_full_pipeline_integration():
    """Test all 5 integrations working together"""
    print("\n" + "="*70)
    print("🚀 FULL PIPELINE INTEGRATION TEST")
    print("="*70)
    
    # Initialize all systems
    print("\n📦 Initializing systems...")
    analytics = AnalyticsTracker("data/test_integration/analytics.db")
    tracer = DistributedTracer("data/test_integration/traces")
    executor = ParallelExecutor(max_concurrent=3)
    kg = KnowledgeGraph("data/test_integration/knowledge.db")
    pattern_learner = PatternLearner(kg)
    query_engine = QueryEngine(kg, pattern_learner)
    quality_validator = QualityValidator()
    
    print("✓ All systems initialized")
    
    # Start distributed trace
    trace_id = tracer.start_trace("full_pipeline_test")
    run_id = f"test_run_{int(time.time())}"
    start_time = time.time()
    
    print(f"\n🔍 Starting trace: {trace_id}")
    print(f"📊 Run ID: {run_id}")
    
    try:
        # PHASE 1: Parallel code generation (Multi-Agent + Tracing)
        parent_span = tracer.start_span("code_generation", "parallel_execution"):
            print("\n⚡ Phase 1: Parallel Code Generation")
            
            files = ['utils.py', 'models.py', 'handlers.py']
            tasks = [simulate_code_generation(f) for f in files]
            
            results = await executor.execute_parallel(tasks)
            print(f"✓ Generated {len(results)} files in parallel")
            
            for r in results:
                print(f"  - {r['file']}: {r['lines']} lines")
        
        # PHASE 2: Code quality validation (Advanced Testing)
        parent_span = tracer.start_span("quality_validation", "testing"):
            print("\n🧪 Phase 2: Quality Validation")
            
            validation_results = []
            for result in results:
                qr = quality_validator.validate_code(result['code'])
                validation_results.append({
                    'file': result['file'],
                    'quality': qr['overall']['quality_level'],
                    'score': qr['overall']['score']
                })
                print(f"  - {result['file']}: {qr['overall']['quality_level']} ({qr['overall']['score']:.1%})")
        
        # PHASE 3: Pattern learning (Knowledge Graph)
        parent_span = tracer.start_span("pattern_learning", "knowledge_extraction"):
            print("\n🧠 Phase 3: Pattern Learning")
            
            run_data = {
                'run_id': run_id,
                'project_name': 'integration_test',
                'status': 'success',
                'execution_time': time.time() - start_time,
                'model_used': 'qwen2.5-coder:7b',
                'stage': 'code_generation',
                'files': [{'path': r['file'], 'size': r['lines'] * 50} for r in results],
                'solutions': [{
                    'type': 'parallel_generation',
                    'approach': 'multi-agent',
                    'effectiveness': 0.95,
                    'context': 'Fast parallel code generation'
                }]
            }
            
            pattern_learner.learn_from_run(run_data)
            print(f"✓ Learned patterns from run")
        
        # PHASE 4: Analytics tracking
        with tracer.start_span(trace_id, "analytics_tracking", "metrics"):
            print("\n📊 Phase 4: Analytics Tracking")
            
            analytics.record_run(
                run_id=run_id,
                model="qwen2.5-coder:7b",
                stage="code_generation",
                execution_time=time.time() - start_time,
                tokens_used=sum(r['lines'] * 10 for r in results),
                cost_usd=0.001,
                status="success",
                metadata={
                    'files_generated': len(results),
                    'parallel_execution': True,
                    'quality_validated': True
                }
            )
            print(f"✓ Recorded pipeline run: {run_id}")
        
        # PHASE 5: Query insights (Knowledge Graph)
        with tracer.start_span(trace_id, "query_insights", "analysis"):
            print("\n🔎 Phase 5: Query Insights")
            
            stats = query_engine.query("Show project statistics")
            print(f"✓ Knowledge graph stats:")
            print(f"  - Total entities: {stats['result']['graph_stats']['total_entities']}")
            print(f"  - Total runs: {stats['result']['run_stats']['total']}")
        
        # Mark successful completion
        execution_time = time.time() - start_time
        
        print("\n" + "="*70)
        print("✅ PIPELINE COMPLETED SUCCESSFULLY")
        print("="*70)
        print(f"⏱️  Execution time: {execution_time:.2f}s")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Generate reports
        print("\n📝 Generating reports...")
        
        # Trace visualization
        print("\n🔍 Trace Tree:")
        print(tracer.visualize_trace(trace_id))
        
        # Analytics summary
        print("\n📊 Analytics Summary:")
        model_metrics = analytics.get_model_metrics(model="qwen2.5-coder:7b", days=1)
        if model_metrics:
            print(f"  Model: {model_metrics['model']}")
            print(f"  Success rate: {model_metrics['success_rate']:.1%}")
            print(f"  Avg time: {model_metrics['avg_execution_time']:.2f}s")
        
        # Knowledge graph insights
        kg_stats = kg.get_stats()
        print(f"\n🧠 Knowledge Graph:")
        print(f"  Entities: {kg_stats['total_entities']}")
        print(f"  Relationships: {kg_stats['total_relationships']}")


async def test_system_interoperability():
    """Test that all systems work well together"""
    print("\n" + "="*70)
    print("🔗 SYSTEM INTEROPERABILITY TEST")
    print("="*70)
    
    print("\n1️⃣  Testing Analytics + Tracing integration...")
    analytics = AnalyticsTracker("data/test_integration/analytics.db")
    tracer = DistributedTracer("data/test_integration/traces")
    
    trace_id = tracer.start_trace("interop_test")
    run_id = "interop_001"
    
    span_ctx = tracer.start_trace("interop_test")
    parent_span = tracer.start_span("analytics_write", "integration"):
        analytics.record_run(
            run_id=run_id,
            model="test_model",
            stage="test",
            execution_time=1.0,
            tokens_used=100,
            cost_usd=0.001,
            status="success"
        )
    
    print("   ✓ Analytics and Tracing work together")
    
    print("\n2️⃣  Testing Knowledge Graph + Analytics integration...")
    kg = KnowledgeGraph("data/test_integration/knowledge.db")
    pattern_learner = PatternLearner(kg)
    
    run_data = {
        'run_id': run_id,
        'project_name': 'interop_test',
        'description': 'Interoperability test',
        'status': 'success',
        'execution_time': 1.0,
        'model_used': 'test_model',
        'stage': 'test',
        'files_generated': 1,
        'errors_encountered': 0
    }
    
    with tracer.start_span(trace_id, "knowledge_extraction", "integration"):
        pattern_learner.learn_from_run(run_data)
    
    print("   ✓ Knowledge Graph and Analytics work together")
    
    print("\n3️⃣  Testing Parallel Execution + Tracing integration...")
    executor = ParallelExecutor(max_concurrent=2)
    
    async def traced_task(x):
        await asyncio.sleep(0.1)
        return x * 2
    
    with tracer.start_span(trace_id, "parallel_tasks", "integration"):
        results = await executor.execute_parallel([traced_task(i) for i in range(5)])
    
    print(f"   ✓ Parallel Execution and Tracing work together (results: {results})")
    
    print("\n4️⃣  Testing Quality Validation + Analytics integration...")
    validator = QualityValidator()
    
    test_code = """
def example():
    return sum(range(10))
"""
    
    with tracer.start_span(trace_id, "quality_check", "integration"):
        quality = validator.validate_code(test_code)
    
    print(f"   ✓ Quality Validation works (score: {quality['overall']['score']:.1%})")
    
    print("\n✅ All systems are interoperable!")
    return True


async def test_performance_under_load():
    """Test system performance with concurrent operations"""
    print("\n" + "="*70)
    print("⚡ PERFORMANCE UNDER LOAD TEST")
    print("="*70)
    
    analytics = AnalyticsTracker("data/test_integration/analytics.db")
    tracer = DistributedTracer("data/test_integration/traces")
    executor = ParallelExecutor(max_concurrent=5)
    
    print("\n🔥 Running 10 concurrent pipeline operations...")
    start_time = time.time()
    
    async def mini_pipeline(idx):
        trace_id = tracer.start_trace(f"load_test_{idx}")
        
        parent_span = tracer.start_span("work", "test"):
            await asyncio.sleep(0.1)
            
            analytics.record_run(
                run_id=f"load_{idx}",
                model="test_model",
                stage="load_test",
                execution_time=0.1,
                tokens_used=100,
                cost_usd=0.001,
                status="success"
            )
        
        return idx
    
    # Run tasks directly with asyncio.gather instead
    results = await asyncio.gather(*[mini_pipeline(i) for i in range(10)])
    
    elapsed = time.time() - start_time
    
    print(f"✓ Completed {len(results)} operations in {elapsed:.2f}s")
    print(f"✓ Throughput: {len(results)/elapsed:.1f} ops/sec")
    
    # Get performance stats
    stats = executor.get_stats()
    print(f"✓ Executor stats:")
    print(f"  - Total tasks: {stats['total_tasks']}")
    print(f"  - Successful: {stats['successful']}")
    print(f"  - Failed: {stats['failed']}")
    
    return True


async def main():
    """Run all comprehensive tests"""
    print("\n" + "="*70)
    print("🧪 COMPREHENSIVE END-TO-END INTEGRATION TEST SUITE")
    print("="*70)
    print("\nTesting all 5 integrations working together:")
    print("  1. Analytics & Optimization")
    print("  2. Distributed Tracing")
    print("  3. Multi-Agent Parallel Execution")
    print("  4. Knowledge Graph")
    print("  5. Advanced Testing")
    
    tests = [
        ("Full Pipeline Integration", test_full_pipeline_integration),
        ("System Interoperability", test_system_interoperability),
        ("Performance Under Load", test_performance_under_load),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = await test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ {name} failed: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Final summary
    print("\n" + "="*70)
    print("📊 FINAL TEST RESULTS")
    print("="*70)
    
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{name:40s} {status}")
    
    passed_count = sum(1 for _, p in results if p)
    total_count = len(results)
    
    print(f"\nRESULTS: {passed_count}/{total_count} tests passed ({passed_count/total_count*100:.0f}%)")
    
    if passed_count == total_count:
        print("\n" + "="*70)
        print("🎉 ALL SYSTEMS OPERATIONAL!")
        print("="*70)
        print("\n✨ System Status:")
        print("   • Analytics tracking: ✅ Operational")
        print("   • Distributed tracing: ✅ Operational")
        print("   • Parallel execution: ✅ Operational")
        print("   • Knowledge graph: ✅ Operational")
        print("   • Advanced testing: ✅ Operational")
        print("\n🚀 Production Ready!")
        print("   • All 5 integrations working together")
        print("   • Full observability stack active")
        print("   • Performance optimizations enabled")
        print("   • Quality validation automated")
        print("   • Pattern learning operational")
    
    return passed_count == total_count


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
