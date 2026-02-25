"""
Request Queue with Priority

Priority-based request queuing with fair scheduling and timeout support.
"""

import asyncio
import time
from enum import IntEnum
from typing import Callable, Any, Optional, Dict, List
from collections import deque
from dataclasses import dataclass


class Priority(IntEnum):
    """Request priority levels (lower number = higher priority)"""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


class QueueFullError(Exception):
    """Raised when queue is full"""
    pass


class RequestTimeoutError(Exception):
    """Raised when request times out in queue"""
    pass


@dataclass
class QueueStats:
    """Statistics for request queue"""
    total_size: int
    by_priority: Dict[Priority, int]
    total_enqueued: int
    total_processed: int
    total_timeouts: int
    total_errors: int
    avg_wait_time: float
    current_processing: bool


class RequestQueue:
    """
    Priority-based request queue
    
    Provides priority-based queuing with:
    - Multiple priority levels (CRITICAL, HIGH, NORMAL, LOW)
    - Fair scheduling within same priority
    - Timeout support for queued requests
    - Backpressure when queue is full
    
    Example:
        queue = RequestQueue(max_size=1000)
        
        # Enqueue high-priority request
        result = await queue.enqueue(
            lambda: expensive_operation(),
            priority=Priority.HIGH,
            timeout=30.0
        )
        
        # Process requests (typically in background task)
        while True:
            processed = await queue.process_next()
            if not processed:
                await asyncio.sleep(0.1)
    """
    
    def __init__(
        self,
        max_size: int = 1000,
        enable_fair_scheduling: bool = True
    ):
        """
        Initialize request queue
        
        Args:
            max_size: Maximum total queue size across all priorities
            enable_fair_scheduling: If True, round-robin within priority levels
        """
        if max_size <= 0:
            raise ValueError("max_size must be positive")
        
        self.max_size = max_size
        self.enable_fair_scheduling = enable_fair_scheduling
        
        # Separate queue for each priority
        self.queues: Dict[Priority, deque] = {
            priority: deque()
            for priority in Priority
        }
        
        # Statistics
        self._total_enqueued = 0
        self._total_processed = 0
        self._total_timeouts = 0
        self._total_errors = 0
        self._total_wait_time = 0.0
        self._processing = False
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
    
    def _total_size(self) -> int:
        """Get total size across all priority queues"""
        return sum(len(q) for q in self.queues.values())
    
    async def enqueue(
        self,
        request: Callable,
        priority: Priority = Priority.NORMAL,
        timeout: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Enqueue a request and wait for execution
        
        Args:
            request: Callable to execute
            priority: Request priority
            timeout: Maximum time to wait for execution
            metadata: Optional metadata for tracking
            
        Returns:
            Result of the request callable
            
        Raises:
            QueueFullError: If queue is full
            RequestTimeoutError: If timeout exceeded
        """
        async with self._lock:
            if self._total_size() >= self.max_size:
                raise QueueFullError(
                    f"Request queue full (size: {self.max_size})"
                )
            
            # Create future for result
            future = asyncio.Future()
            enqueue_time = time.time()
            
            # Add to appropriate priority queue
            self.queues[priority].append({
                "request": request,
                "future": future,
                "enqueue_time": enqueue_time,
                "timeout": timeout,
                "metadata": metadata or {}
            })
            
            self._total_enqueued += 1
        
        # Wait for execution
        try:
            if timeout:
                result = await asyncio.wait_for(future, timeout)
            else:
                result = await future
            
            # Update wait time stats
            wait_time = time.time() - enqueue_time
            self._total_wait_time += wait_time
            
            return result
            
        except asyncio.TimeoutError:
            self._total_timeouts += 1
            raise RequestTimeoutError(
                f"Request timed out after {timeout}s"
            )
    
    async def process_next(self) -> bool:
        """
        Process next request from highest priority queue
        
        Returns:
            True if a request was processed, False if no requests
        """
        async with self._lock:
            self._processing = True
            
            # Find highest priority queue with items
            for priority in sorted(Priority):
                queue = self.queues[priority]
                
                if queue:
                    # Get next item
                    item = queue.popleft()
                    break
            else:
                # No requests
                self._processing = False
                return False
        
        # Process outside lock to allow concurrent enqueuing
        request = item["request"]
        future = item["future"]
        timeout = item["timeout"]
        
        # Check if already timed out
        if timeout:
            elapsed = time.time() - item["enqueue_time"]
            if elapsed >= timeout:
                if not future.done():
                    future.set_exception(RequestTimeoutError(
                        f"Request timed out after {timeout}s"
                    ))
                self._total_timeouts += 1
                self._processing = False
                return True
        
        # Execute request
        try:
            result = await request()
            
            if not future.done():
                future.set_result(result)
            
            self._total_processed += 1
            
        except Exception as e:
            if not future.done():
                future.set_exception(e)
            
            self._total_errors += 1
        
        finally:
            self._processing = False
        
        return True
    
    async def process_all(self, max_concurrent: int = 1) -> int:
        """
        Process all queued requests
        
        Args:
            max_concurrent: Maximum concurrent requests to process
            
        Returns:
            Number of requests processed
        """
        processed = 0
        
        while self._total_size() > 0:
            # Process up to max_concurrent requests
            tasks = []
            for _ in range(min(max_concurrent, self._total_size())):
                tasks.append(self.process_next())
            
            results = await asyncio.gather(*tasks)
            processed += sum(1 for r in results if r)
            
            if not any(results):
                break
        
        return processed
    
    def size(self, priority: Optional[Priority] = None) -> int:
        """
        Get queue size
        
        Args:
            priority: Specific priority queue (None for total)
            
        Returns:
            Queue size
        """
        if priority is not None:
            return len(self.queues[priority])
        return self._total_size()
    
    def is_empty(self) -> bool:
        """Check if queue is empty"""
        return self._total_size() == 0
    
    def is_full(self) -> bool:
        """Check if queue is full"""
        return self._total_size() >= self.max_size
    
    def clear(self, priority: Optional[Priority] = None) -> int:
        """
        Clear queue
        
        Args:
            priority: Specific priority to clear (None for all)
            
        Returns:
            Number of items cleared
        """
        cleared = 0
        
        if priority is not None:
            cleared = len(self.queues[priority])
            self.queues[priority].clear()
        else:
            for queue in self.queues.values():
                cleared += len(queue)
                queue.clear()
        
        return cleared
    
    def get_statistics(self) -> QueueStats:
        """Get queue statistics"""
        by_priority = {
            priority: len(queue)
            for priority, queue in self.queues.items()
        }
        
        avg_wait_time = 0.0
        if self._total_processed > 0:
            avg_wait_time = self._total_wait_time / self._total_processed
        
        return QueueStats(
            total_size=self._total_size(),
            by_priority=by_priority,
            total_enqueued=self._total_enqueued,
            total_processed=self._total_processed,
            total_timeouts=self._total_timeouts,
            total_errors=self._total_errors,
            avg_wait_time=avg_wait_time,
            current_processing=self._processing
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        stats = self.get_statistics()
        
        return {
            "total_size": stats.total_size,
            "by_priority": {
                priority.name: count
                for priority, count in stats.by_priority.items()
            },
            "total_enqueued": stats.total_enqueued,
            "total_processed": stats.total_processed,
            "total_timeouts": stats.total_timeouts,
            "total_errors": stats.total_errors,
            "avg_wait_time": stats.avg_wait_time,
            "success_rate": (
                stats.total_processed / stats.total_enqueued
                if stats.total_enqueued > 0 else 0.0
            ),
            "currently_processing": stats.current_processing
        }
