"""
State Management Module
=======================

Redis-based state management, caching, and event streaming for distributed systems.

Key Features:
- Redis connection pooling with health checks
- Semantic caching (30%+ token cost reduction)
- Real-time event streaming (pub/sub)
- Analytics and metrics collection

Quick Start:
    ```python
    from src.state_management import (
        get_redis_client,
        get_semantic_cache,
        get_event_stream
    )
    
    # Get Redis client
    client = await get_redis_client()
    await client.set("key", "value", ttl=3600)
    
    # Use semantic cache
    cache = await get_semantic_cache()
    response = await cache.get("query")
    if response is None:
        response = await call_llm("query")
        await cache.set("query", response)
    
    # Publish events
    stream = await get_event_stream()
    await stream.publish_agent_event(
        agent_name="CodeGenerator",
        event_type="code_generated",
        data={"lines": 50}
    )
    ```
"""

from .redis_client import (
    RedisClient,
    get_redis_client,
    close_redis_client
)

from .cache_manager import (
    SemanticCache,
    get_semantic_cache
)

from .event_stream import (
    EventStream,
    get_event_stream
)

__all__ = [
    # Redis client
    "RedisClient",
    "get_redis_client",
    "close_redis_client",
    
    # Semantic caching
    "SemanticCache",
    "get_semantic_cache",
    
    # Event streaming
    "EventStream",
    "get_event_stream",
]
