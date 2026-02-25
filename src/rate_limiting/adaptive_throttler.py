"""
Adaptive Throttler

Dynamically adjusts rate limits based on success/failure rates using AIMD
(Additive Increase Multiplicative Decrease) algorithm.
"""

import asyncio
import time
from typing import Dict, Any, Optional
from collections import deque
from dataclasses import dataclass

from .token_bucket import TokenBucket


@dataclass
class AdaptiveThrottlerStats:
    """Statistics for adaptive throttler"""
    current_rate: float
    min_rate: float
    max_rate: float
    success_rate: float
    total_requests: int
    successful_requests: int
    failed_requests: int
    rate_adjustments: int
    last_adjustment_time: Optional[float]


class AdaptiveThrottler:
    """
    Adaptive rate limiter using AIMD algorithm
    
    Automatically adjusts rate limits based on success/failure rates:
    - High success rate (>90%) → Additive increase (rate += step)
    - Low success rate (<70%) → Multiplicative decrease (rate *= factor)
    - Medium success rate → No change
    
    This allows the system to find optimal rate limits dynamically and
    back off when hitting rate limits or experiencing failures.
    
    Example:
        throttler = AdaptiveThrottler(
            initial_rate=10.0,
            min_rate=5.0,
            max_rate=20.0
        )
        
        # Acquire permission
        await throttler.acquire()
        
        # Make request
        try:
            result = await make_api_call()
            throttler.record_success()
        except Exception:
            throttler.record_failure()
    """
    
    def __init__(
        self,
        initial_rate: float,
        min_rate: float,
        max_rate: float,
        increase_step: float = 1.0,
        decrease_factor: float = 0.5,
        adjustment_window: int = 10,
        success_threshold: float = 0.9,
        failure_threshold: float = 0.7
    ):
        """
        Initialize adaptive throttler
        
        Args:
            initial_rate: Starting rate (requests per second)
            min_rate: Minimum allowed rate
            max_rate: Maximum allowed rate
            increase_step: Amount to increase rate on success (additive)
            decrease_factor: Factor to decrease rate on failure (multiplicative)
            adjustment_window: Number of recent requests to consider
            success_threshold: Success rate to trigger increase (0.0-1.0)
            failure_threshold: Success rate to trigger decrease (0.0-1.0)
        """
        if not (min_rate <= initial_rate <= max_rate):
            raise ValueError("initial_rate must be between min_rate and max_rate")
        if increase_step <= 0:
            raise ValueError("increase_step must be positive")
        if not (0 < decrease_factor < 1):
            raise ValueError("decrease_factor must be between 0 and 1")
        if adjustment_window <= 0:
            raise ValueError("adjustment_window must be positive")
        
        self.current_rate = initial_rate
        self.min_rate = min_rate
        self.max_rate = max_rate
        self.increase_step = increase_step
        self.decrease_factor = decrease_factor
        self.adjustment_window = adjustment_window
        self.success_threshold = success_threshold
        self.failure_threshold = failure_threshold
        
        # Recent results (True=success, False=failure)
        self.recent_results: deque = deque(maxlen=adjustment_window)
        
        # Token bucket for actual rate limiting
        self._bucket = TokenBucket(
            rate=initial_rate,
            capacity=int(initial_rate * 2)
        )
        
        # Statistics
        self._total_requests = 0
        self._successful_requests = 0
        self._failed_requests = 0
        self._rate_adjustments = 0
        self._last_adjustment_time: Optional[float] = None
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
    
    async def acquire(
        self,
        tokens: int = 1,
        timeout: Optional[float] = None
    ) -> bool:
        """
        Acquire permission to proceed
        
        Args:
            tokens: Number of tokens to acquire
            timeout: Maximum time to wait
            
        Returns:
            True if acquired, False if timeout
        """
        return await self._bucket.acquire(tokens, timeout)
    
    def record_success(self) -> None:
        """Record a successful request"""
        self._total_requests += 1
        self._successful_requests += 1
        self.recent_results.append(True)
        self._maybe_adjust_rate()
    
    def record_failure(self) -> None:
        """Record a failed request"""
        self._total_requests += 1
        self._failed_requests += 1
        self.recent_results.append(False)
        self._maybe_adjust_rate()
    
    def _maybe_adjust_rate(self) -> None:
        """Adjust rate if conditions are met"""
        # Need enough samples
        if len(self.recent_results) < self.adjustment_window:
            return
        
        # Calculate success rate
        success_count = sum(1 for r in self.recent_results if r)
        success_rate = success_count / len(self.recent_results)
        
        new_rate = None
        
        if success_rate >= self.success_threshold:
            # Additive increase
            new_rate = min(
                self.max_rate,
                self.current_rate + self.increase_step
            )
        
        elif success_rate < self.failure_threshold:
            # Multiplicative decrease
            new_rate = max(
                self.min_rate,
                self.current_rate * self.decrease_factor
            )
        
        # Apply rate change if needed
        if new_rate is not None and new_rate != self.current_rate:
            self._apply_rate_change(new_rate)
    
    def _apply_rate_change(self, new_rate: float) -> None:
        """Apply a rate change"""
        old_rate = self.current_rate
        self.current_rate = new_rate
        self._rate_adjustments += 1
        self._last_adjustment_time = time.time()
        
        # Create new token bucket with new rate
        self._bucket = TokenBucket(
            rate=new_rate,
            capacity=int(new_rate * 2),
            initial_tokens=int(new_rate)  # Start with some tokens
        )
    
    def force_rate_change(self, new_rate: float) -> None:
        """
        Manually set a new rate
        
        Args:
            new_rate: New rate to set
        """
        if not (self.min_rate <= new_rate <= self.max_rate):
            raise ValueError(f"Rate must be between {self.min_rate} and {self.max_rate}")
        
        self._apply_rate_change(new_rate)
    
    def reset(self) -> None:
        """Reset to initial state"""
        self.current_rate = self.min_rate
        self.recent_results.clear()
        self._bucket.reset()
        self._rate_adjustments = 0
        self._last_adjustment_time = None
    
    def get_statistics(self) -> AdaptiveThrottlerStats:
        """Get statistics about throttler"""
        success_rate = 0.0
        if self._total_requests > 0:
            success_rate = self._successful_requests / self._total_requests
        
        return AdaptiveThrottlerStats(
            current_rate=self.current_rate,
            min_rate=self.min_rate,
            max_rate=self.max_rate,
            success_rate=success_rate,
            total_requests=self._total_requests,
            successful_requests=self._successful_requests,
            failed_requests=self._failed_requests,
            rate_adjustments=self._rate_adjustments,
            last_adjustment_time=self._last_adjustment_time
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        stats = self.get_statistics()
        bucket_stats = self._bucket.to_dict()
        
        return {
            "current_rate": stats.current_rate,
            "min_rate": stats.min_rate,
            "max_rate": stats.max_rate,
            "success_rate": stats.success_rate,
            "total_requests": stats.total_requests,
            "successful_requests": stats.successful_requests,
            "failed_requests": stats.failed_requests,
            "rate_adjustments": stats.rate_adjustments,
            "last_adjustment_ago": (
                time.time() - stats.last_adjustment_time
                if stats.last_adjustment_time else None
            ),
            "bucket": bucket_stats
        }
    
    @property
    def available_tokens(self) -> int:
        """Get number of available tokens"""
        return self._bucket.available_tokens()
