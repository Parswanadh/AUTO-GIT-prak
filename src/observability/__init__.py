"""
Observability Module
====================

Automatic distributed tracing, metrics collection, and monitoring.

Key Features:
- One-line Logfire setup for automatic LLM tracing
- Metrics collection and aggregation
- Performance monitoring
- Error tracking

Quick Start:
    ```python
    from src.observability import configure_logfire, get_metrics_collector
    
    # Enable automatic tracing
    configure_logfire()  # ← One line, all agents traced!
    
    # Track custom metrics
    collector = get_metrics_collector()
    collector.record_agent_call(
        agent_name="CodeGenerator",
        model="qwen2.5-coder:7b",
        latency_ms=1234,
        tokens_used=500,
        success=True
    )
    
    # Get performance summary
    summary = collector.get_summary()
    print(f"Total calls: {summary['system']['total_calls']}")
    print(f"Cache hit rate: {summary['cache']['hit_rate_percent']}%")
    ```

Logfire Setup:
    1. Get token from https://logfire.pydantic.dev
    2. Set environment variable: export LOGFIRE_TOKEN="your-token"
    3. Call configure_logfire() once at startup
    4. All Pydantic AI agents automatically traced!
"""

from .logfire_config import (
    configure_logfire,
    configure_logfire_offline,
    get_current_trace_id
)

from .metrics_collector import (
    MetricsCollector,
    get_metrics_collector
)

__all__ = [
    # Logfire configuration
    "configure_logfire",
    "configure_logfire_offline",
    "get_current_trace_id",
    
    # Metrics collection
    "MetricsCollector",
    "get_metrics_collector",
]
