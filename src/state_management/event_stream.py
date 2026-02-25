"""
Event Stream
============

Redis-based pub/sub system for real-time analytics and agent communication.
"""

import json
from typing import Optional, Callable, Any, Dict
from datetime import datetime
from .redis_client import RedisClient, get_redis_client
import asyncio
import logging

logger = logging.getLogger(__name__)


class EventStream:
    """
    Real-time event streaming system using Redis pub/sub.
    
    Use cases:
    - Agent-to-agent communication
    - Real-time analytics tracking
    - System monitoring
    - Event-driven workflows
    
    Example:
        ```python
        stream = EventStream()
        await stream.initialize()
        
        # Publish event
        await stream.publish_agent_event(
            agent_name="CodeGenerator",
            event_type="code_generated",
            data={"lines": 50, "language": "python"}
        )
        
        # Subscribe to events
        async def handle_event(event):
            print(f"Received: {event}")
        
        await stream.subscribe("agent.events", handle_event)
        ```
    """
    
    def __init__(self, redis_client: Optional[RedisClient] = None):
        """
        Initialize event stream.
        
        Args:
            redis_client: Redis client instance
        """
        self.redis_client = redis_client
        self._subscribers: Dict[str, list] = {}  # channel -> [callbacks]
    
    async def initialize(self) -> None:
        """Initialize event stream (connect to Redis)"""
        if self.redis_client is None:
            self.redis_client = await get_redis_client()
        
        logger.info("Event stream initialized")
    
    async def publish(
        self,
        channel: str,
        event_type: str,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Publish event to channel.
        
        Args:
            channel: Channel name (e.g., "agent.events", "system.metrics")
            event_type: Event type (e.g., "code_generated", "error_occurred")
            data: Event data
            metadata: Optional metadata (timestamps, user_id, etc.)
        
        Returns:
            Number of subscribers that received the event
        """
        if self.redis_client is None:
            raise RuntimeError("Event stream not initialized")
        
        event = {
            "type": event_type,
            "data": data,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat(),
            "channel": channel
        }
        
        event_json = json.dumps(event)
        
        try:
            subscribers = await self.redis_client.publish(channel, event_json)
            logger.debug(f"Published {event_type} to {channel} ({subscribers} subscribers)")
            return subscribers
        
        except Exception as e:
            logger.error(f"Failed to publish event: {e}")
            return 0
    
    async def subscribe(
        self,
        channel: str,
        callback: Callable[[Dict], Any]
    ) -> None:
        """
        Subscribe to channel and handle events with callback.
        
        Args:
            channel: Channel to subscribe to
            callback: Async function to handle events
        
        Example:
            ```python
            async def handle_agent_event(event):
                agent = event["data"]["agent_name"]
                event_type = event["type"]
                print(f"{agent}: {event_type}")
            
            await stream.subscribe("agent.events", handle_agent_event)
            ```
        """
        if self.redis_client is None:
            raise RuntimeError("Event stream not initialized")
        
        # Store callback
        if channel not in self._subscribers:
            self._subscribers[channel] = []
        
        self._subscribers[channel].append(callback)
        
        # Start listening in background
        asyncio.create_task(self._listen(channel))
        
        logger.info(f"Subscribed to channel: {channel}")
    
    async def _listen(self, channel: str) -> None:
        """Background task that listens to channel and calls callbacks"""
        try:
            pubsub = await self.redis_client.subscribe(channel)
            
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        event = json.loads(message["data"])
                        
                        # Call all callbacks for this channel
                        for callback in self._subscribers.get(channel, []):
                            try:
                                if asyncio.iscoroutinefunction(callback):
                                    await callback(event)
                                else:
                                    callback(event)
                            except Exception as e:
                                logger.error(f"Error in event callback: {e}")
                    
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON in message: {message['data']}")
        
        except Exception as e:
            logger.error(f"Error listening to channel {channel}: {e}")
    
    # Convenience methods for common event types
    
    async def publish_agent_event(
        self,
        agent_name: str,
        event_type: str,
        data: Dict[str, Any]
    ) -> int:
        """
        Publish agent-related event.
        
        Example:
            ```python
            await stream.publish_agent_event(
                agent_name="CodeGenerator",
                event_type="code_generated",
                data={"lines": 50, "tokens": 1200}
            )
            ```
        """
        return await self.publish(
            channel="agent.events",
            event_type=event_type,
            data={
                "agent_name": agent_name,
                **data
            }
        )
    
    async def publish_metric(
        self,
        metric_name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None
    ) -> int:
        """
        Publish performance metric.
        
        Example:
            ```python
            await stream.publish_metric(
                metric_name="llm.latency_ms",
                value=1234.5,
                tags={"model": "qwen2.5-coder:7b", "agent": "CodeGenerator"}
            )
            ```
        """
        return await self.publish(
            channel="system.metrics",
            event_type="metric",
            data={
                "name": metric_name,
                "value": value,
                "tags": tags or {}
            }
        )
    
    async def publish_error(
        self,
        error_type: str,
        error_message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Publish error event.
        
        Example:
            ```python
            await stream.publish_error(
                error_type="LLMTimeout",
                error_message="Model took too long to respond",
                context={"model": "deepseek-r1:8b", "timeout": 30}
            )
            ```
        """
        return await self.publish(
            channel="system.errors",
            event_type="error",
            data={
                "error_type": error_type,
                "message": error_message,
                "context": context or {}
            }
        )
    
    async def publish_workflow_event(
        self,
        workflow_name: str,
        stage: str,
        status: str,  # started/completed/failed
        data: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Publish workflow status event.
        
        Example:
            ```python
            await stream.publish_workflow_event(
                workflow_name="code_generation",
                stage="validation",
                status="completed",
                data={"validation_score": 0.95}
            )
            ```
        """
        return await self.publish(
            channel="workflow.events",
            event_type="workflow_status",
            data={
                "workflow_name": workflow_name,
                "stage": stage,
                "status": status,
                **(data or {})
            }
        )


# Global event stream instance
_event_stream: Optional[EventStream] = None


async def get_event_stream() -> EventStream:
    """
    Get singleton event stream instance.
    
    Example:
        ```python
        from src.state_management import get_event_stream
        
        stream = await get_event_stream()
        
        await stream.publish_agent_event(
            agent_name="CodeReviewer",
            event_type="review_completed",
            data={"score": 8.5}
        )
        ```
    """
    global _event_stream
    
    if _event_stream is None:
        _event_stream = EventStream()
        await _event_stream.initialize()
    
    return _event_stream
