"""Test Distributed Tracing Integration (#19)"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tracing import DistributedTracer, TraceSpan, SpanContext


async def test_basic_span():
    """Test 1: Basic span creation and completion"""
    print("\n" + "="*60)
    print("TEST 1: Basic Span Operations")
    print("="*60)
    
    tracer = DistributedTracer(trace_dir="data/traces/test")
    
    # Start a trace
    trace_id = tracer.start_trace("test_pipeline")
    print(f"\n✅ Started trace: {trace_id}")
    
    # Create a span
    span = tracer.start_span(
        operation="research",
        component="pipeline_node",
        tags={"model": "qwen3:8b", "stage": "research"}
    )
    print(f"✅ Started span: {span.span_id[:6]}")
    
    # Simulate work
    time.sleep(0.1)
    span.log_event("data_loaded", records=100)
    span.set_resource_usage(tokens=450, model="qwen3:8b", backend="ollama")
    
    # End span
    tracer.end_span(span, success=True)
    print(f"✅ Ended span: {span.duration_seconds:.3f}s")
    
    print("\n✅ Test 1 PASSED")
    return True


async def test_hierarchical_spans():
    """Test 2: Parent-child span relationships"""
    print("\n" + "="*60)
    print("TEST 2: Hierarchical Spans")
    print("="*60)
    
    tracer = DistributedTracer(trace_dir="data/traces/test")
    
    # Start trace and root span
    trace_id = tracer.start_trace("hierarchical_test")
    root_span = tracer.start_span("pipeline", component="root")
    
    print(f"\n✅ Root span: {root_span.operation}")
    
    # Create child spans
    child1_context = root_span.get_context()
    child1 = tracer.start_span(
        "research",
        component="node",
        parent_context=child1_context
    )
    time.sleep(0.05)
    tracer.end_span(child1, success=True)
    print(f"  ├── Child 1: {child1.operation} ({child1.duration_seconds:.3f}s)")
    
    child2 = tracer.start_span(
        "problem_extraction",
        component="node",
        parent_context=child1_context
    )
    
    # Create grandchild
    child2_context = child2.get_context()
    grandchild = tracer.start_span(
        "llm_call",
        component="llm",
        parent_context=child2_context
    )
    time.sleep(0.03)
    tracer.end_span(grandchild, success=True)
    print(f"  │   └── Grandchild: {grandchild.operation} ({grandchild.duration_seconds:.3f}s)")
    
    time.sleep(0.05)
    tracer.end_span(child2, success=True)
    print(f"  ├── Child 2: {child2.operation} ({child2.duration_seconds:.3f}s)")
    
    # End root
    tracer.end_span(root_span, success=True)
    print(f"✅ Root complete: {root_span.duration_seconds:.3f}s")
    
    print("\n✅ Test 2 PASSED")
    return True


async def test_error_tracking():
    """Test 3: Error tracking in spans"""
    print("\n" + "="*60)
    print("TEST 3: Error Tracking")
    print("="*60)
    
    tracer = DistributedTracer(trace_dir="data/traces/test")
    
    trace_id = tracer.start_trace("error_test")
    
    # Successful span
    success_span = tracer.start_span("success_operation", component="test")
    time.sleep(0.05)
    tracer.end_span(success_span, success=True)
    print(f"\n✅ Successful span: {success_span.status}")
    
    # Error span
    error_span = tracer.start_span("failing_operation", component="test")
    time.sleep(0.02)
    try:
        raise ValueError("Simulated error")
    except Exception as e:
        tracer.record_error(error_span, e)
    
    print(f"❌ Error span: {error_span.status}")
    print(f"   Error: {error_span.error}")
    print(f"   Type:  {error_span.error_type}")
    
    print("\n✅ Test 3 PASSED")
    return True


async def test_trace_loading():
    """Test 4: Loading and analyzing traces"""
    print("\n" + "="*60)
    print("TEST 4: Trace Loading & Analysis")
    print("="*60)
    
    tracer = DistributedTracer(trace_dir="data/traces/test")
    
    # Create a complete trace
    trace_id = tracer.start_trace("analysis_test")
    root = tracer.start_span("root", component="pipeline")
    
    for i in range(3):
        child = tracer.start_span(
            f"operation_{i}",
            component="node",
            parent_context=root.get_context(),
            tags={"iteration": i}
        )
        child.set_resource_usage(tokens=100 + i * 50, model="qwen3:8b")
        time.sleep(0.02)
        tracer.end_span(child, success=True)
    
    tracer.end_span(root, success=True)
    
    print(f"\n✅ Created trace: {trace_id}")
    
    # Load the trace
    spans = tracer.get_trace(trace_id)
    print(f"✅ Loaded {len(spans)} spans")
    
    # Get summary
    summary = tracer.get_trace_summary(trace_id)
    print(f"\n📊 Trace Summary:")
    print(f"  Total Spans:    {summary['total_spans']}")
    print(f"  Successful:     {summary['successful_spans']}")
    print(f"  Errors:         {summary['error_spans']}")
    print(f"  Total Duration: {summary['total_duration_seconds']:.3f}s")
    print(f"  Total Tokens:   {summary['total_tokens']}")
    
    print("\n✅ Test 4 PASSED")
    return True


async def test_trace_visualization():
    """Test 5: ASCII tree visualization"""
    print("\n" + "="*60)
    print("TEST 5: Trace Visualization")
    print("="*60)
    
    tracer = DistributedTracer(trace_dir="data/traces/test")
    
    # Create complex trace
    trace_id = tracer.start_trace("viz_test")
    root = tracer.start_span("pipeline", component="root")
    root.set_resource_usage(tokens=1000, model="qwen3:8b")
    
    # Level 1 children
    research = tracer.start_span(
        "research",
        component="node",
        parent_context=root.get_context()
    )
    research.set_resource_usage(tokens=300, model="qwen3:8b")
    time.sleep(0.02)
    tracer.end_span(research, success=True)
    
    generation = tracer.start_span(
        "code_generation",
        component="node",
        parent_context=root.get_context()
    )
    
    # Level 2 children
    gen_child1 = tracer.start_span(
        "generate_file_1",
        component="generator",
        parent_context=generation.get_context()
    )
    gen_child1.set_resource_usage(tokens=200, model="deepseek-coder")
    time.sleep(0.01)
    tracer.end_span(gen_child1, success=True)
    
    gen_child2 = tracer.start_span(
        "generate_file_2",
        component="generator",
        parent_context=generation.get_context()
    )
    gen_child2.set_resource_usage(tokens=250, model="deepseek-coder")
    time.sleep(0.01)
    tracer.end_span(gen_child2, success=True)
    
    time.sleep(0.02)
    generation.set_resource_usage(tokens=500, model="deepseek-coder")
    tracer.end_span(generation, success=True)
    
    tracer.end_span(root, success=True)
    
    # Visualize
    print(f"\n🌳 Trace Visualization:")
    print(tracer.visualize_trace(trace_id))
    
    print("\n✅ Test 5 PASSED")
    return True


async def test_context_propagation():
    """Test 6: Span context propagation"""
    print("\n" + "="*60)
    print("TEST 6: Context Propagation")
    print("="*60)
    
    tracer = DistributedTracer(trace_dir="data/traces/test")
    
    # Start trace
    trace_id = tracer.start_trace("context_test")
    parent_span = tracer.start_span("parent", component="test")
    
    # Get context
    context = tracer.create_span_context(parent_span)
    print(f"\n✅ Created context:")
    print(f"   Trace ID: {context.trace_id}")
    print(f"   Span ID:  {context.span_id}")
    
    # Propagate to child
    child_span = tracer.start_span(
        "child",
        component="test",
        parent_context=context
    )
    
    print(f"\n✅ Child span:")
    print(f"   Trace ID: {child_span.trace_id}")
    print(f"   Parent:   {child_span.parent_span_id}")
    
    # Verify relationship
    assert child_span.trace_id == context.trace_id
    assert child_span.parent_span_id == context.span_id
    
    tracer.end_span(child_span, success=True)
    tracer.end_span(parent_span, success=True)
    
    print("\n✅ Test 6 PASSED")
    return True


async def test_context_manager():
    """Test 7: Context manager support"""
    print("\n" + "="*60)
    print("TEST 7: Context Manager")
    print("="*60)
    
    tracer = DistributedTracer(trace_dir="data/traces/test")
    trace_id = tracer.start_trace("context_mgr_test")
    
    # Test successful span with context manager
    span = tracer.start_span("success_op", component="test")
    with span:
        time.sleep(0.05)
        span.log_event("processing", items=100)
    tracer.end_span(span, success=True)
    
    print(f"\n✅ Span auto-completed: {span.status}")
    assert span.is_finished()
    assert span.is_successful()
    
    # Test error handling with context manager
    error_span = tracer.start_span("error_op", component="test")
    try:
        with error_span:
            time.sleep(0.02)
            raise RuntimeError("Test error")
    except RuntimeError:
        pass
    
    print(f"\n🔍 Debug: error_span.status={error_span.status}, error={error_span.error}")
    print(f"❌ Error span handled: {error_span.status}")
    
    # Don't call end_span if already errored
    if error_span.status != "error":
        tracer.end_span(error_span, success=False)
    else:
        tracer._write_span_to_json(error_span)
    
    assert error_span.has_error(), f"Expected error status but got {error_span.status}"
    
    print("\n✅ Test 7 PASSED")
    return True


async def main():
    """Run all tests"""
    print("\n🧪 DISTRIBUTED TRACING TESTS (Integration #19)")
    print("="*60)
    
    tests = [
        ("Basic Span Operations", test_basic_span),
        ("Hierarchical Spans", test_hierarchical_spans),
        ("Error Tracking", test_error_tracking),
        ("Trace Loading & Analysis", test_trace_loading),
        ("Trace Visualization", test_trace_visualization),
        ("Context Propagation", test_context_propagation),
        ("Context Manager", test_context_manager),
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
        print("\n🎉 ALL TESTS PASSED - Integration #19 Complete!")
        return True
    else:
        print(f"\n⚠️ {total - passed} test(s) failed")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
