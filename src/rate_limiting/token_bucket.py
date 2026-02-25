"""
Token Bucket Rate Limiter

Classic token bucket algorithm for rate limiting with configurable rate and burst capacity.
"""

import asyncio
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class TokenBucketStats:
    """Statistics for token bucket"""
    rate: float
    capacity: int
    available_tokens: float
    total_acquisitions: int
    successful_acquisitions: int
    failed_acquisitions: int
    total_wait_time: float
    utilization: float


class TokenBucket:
    """
    Token bucket rate limiter
    
    Implements the token bucket algorithm for rate limiting:
    - Tokens are added to the bucket at a fixed rate
    - Bucket has a maximum capacity (burst size)
    - Requests consume tokens
    - If no tokens available, request waits or fails
    
    Example:
        # 10 requests per second, burst of 20
        bucket = TokenBucket(rate=10.0, capacity=20)
        
        # Acquire 1 token (waits if needed)
        if await bucket.acquire():
            # Make API call
            pass
        
        # Try to acquire without waiting
        if bucket.try_acquire():
            # Make API call
            pass
    """
    
    def __init__(
        self,
        rate: float,
        capacity: int,
        initial_tokens: Optional[int] = None
    ):
        """
        Initialize token bucket
        
        Args:
            rate: Number of tokens added per second
            capacity: Maximum number of tokens in bucket (burst size)
            initial_tokens: Initial token count (defaults to capacity)
        """
        if rate <= 0:
            raise ValueError("Rate must be positive")
        if capacity <= 0:
            raise ValueError("Capacity must be positive")
        
        self.rate = rate
        self.capacity = capacity
        self.tokens = float(initial_tokens if initial_tokens is not None else capacity)
        self.last_update = time.time()
        self._lock = asyncio.Lock()
        
        # Statistics
        self._total_acquisitions = 0
        self._successful_acquisitions = 0
        self._failed_acquisitions = 0
        self._total_wait_time = 0.0
    
    def _refill(self) -> None:
        """Refill tokens based on elapsed time"""
        now = time.time()
        elapsed = now - self.last_update
        
        # Add tokens based on elapsed time
        new_tokens = elapsed * self.rate
        self.tokens = min(self.capacity, self.tokens + new_tokens)
        self.last_update = now
    
    async def acquire(
        self,
        tokens: int = 1,
        timeout: Optional[float] = None
    ) -> bool:
        """
        Acquire tokens, waiting if necessary
        
        Args:
            tokens: Number of tokens to acquire
            timeout: Maximum time to wait (None = wait forever)
            
        Returns:
            True if tokens acquired, False if timeout
        """
        if tokens <= 0:
            raise ValueError("Tokens must be positive")
        if tokens > self.capacity:
            raise ValueError(f"Cannot acquire {tokens} tokens (capacity: {self.capacity})")
        
        start = time.time()
        self._total_acquisitions += 1
        
        while True:
            async with self._lock:
                self._refill()
                
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    self._successful_acquisitions += 1
                    self._total_wait_time += time.time() - start
                    return True
            
            # Check timeout
            if timeout is not None:
                elapsed = time.time() - start
                if elapsed >= timeout:
                    self._failed_acquisitions += 1
                    return False
            
            # Calculate wait time until enough tokens
            tokens_needed = tokens - self.tokens
            wait_time = tokens_needed / self.rate
            
            # Wait a bit before retry (but not more than needed)
            await asyncio.sleep(min(0.01, wait_time))
    
    def try_acquire(self, tokens: int = 1) -> bool:
        """
        Try to acquire tokens without waiting
        
        Args:
            tokens: Number of tokens to acquire
            
        Returns:
            True if tokens acquired, False otherwise
        """
        if tokens <= 0:
            raise ValueError("Tokens must be positive")
        if tokens > self.capacity:
            return False
        
        self._refill()
        self._total_acquisitions += 1
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            self._successful_acquisitions += 1
            return True
        
        self._failed_acquisitions += 1
        return False
    
    def available_tokens(self) -> int:
        """Get number of currently available tokens"""
        self._refill()
        return int(self.tokens)
    
    def time_until_tokens(self, tokens: int) -> float:
        """
        Get time in seconds until specified tokens available
        
        Args:
            tokens: Number of tokens needed
            
        Returns:
            Time in seconds (0 if already available)
        """
        self._refill()
        
        if self.tokens >= tokens:
            return 0.0
        
        tokens_needed = tokens - self.tokens
        return tokens_needed / self.rate
    
    def reset(self, tokens: Optional[int] = None) -> None:
        """
        Reset bucket to initial state
        
        Args:
            tokens: Token count to reset to (defaults to capacity)
        """
        self.tokens = float(tokens if tokens is not None else self.capacity)
        self.last_update = time.time()
    
    def get_statistics(self) -> TokenBucketStats:
        """Get statistics about token bucket usage"""
        self._refill()
        
        utilization = 0.0
        if self._successful_acquisitions > 0:
            avg_tokens = self.capacity / 2  # Approximate average
            utilization = 1.0 - (self.tokens / self.capacity)
        
        return TokenBucketStats(
            rate=self.rate,
            capacity=self.capacity,
            available_tokens=self.tokens,
            total_acquisitions=self._total_acquisitions,
            successful_acquisitions=self._successful_acquisitions,
            failed_acquisitions=self._failed_acquisitions,
            total_wait_time=self._total_wait_time,
            utilization=utilization
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        stats = self.get_statistics()
        return {
            "rate": stats.rate,
            "capacity": stats.capacity,
            "available_tokens": int(stats.available_tokens),
            "total_acquisitions": stats.total_acquisitions,
            "successful_acquisitions": stats.successful_acquisitions,
            "failed_acquisitions": stats.failed_acquisitions,
            "avg_wait_time": (
                stats.total_wait_time / stats.successful_acquisitions
                if stats.successful_acquisitions > 0 else 0.0
            ),
            "utilization": stats.utilization
        }
