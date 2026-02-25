"""
Error Recovery Manager - Integration #16

Provides centralized retry orchestration with exponential backoff,
jitter, and configurable retry policies.
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional, Dict
from enum import Enum

logger = logging.getLogger(__name__)


@dataclass
class RetryPolicy:
    """Configuration for retry behavior"""
    
    max_attempts: int = 3
    base_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    exponential_base: float = 2.0
    jitter: bool = True  # Add randomness to prevent thundering herd
    timeout: Optional[float] = None  # Per-attempt timeout


class RetryableError(Exception):
    """Base class for errors that should trigger retry"""
    pass


class NonRetryableError(Exception):
    """Base class for errors that should NOT trigger retry"""
    pass


class ErrorRecoveryManager:
    """
    Centralized retry orchestration with intelligent backoff.
    
    Features:
    - Exponential backoff with jitter
    - Configurable retry policies per operation type
    - Timeout management
    - Fallback support
    - Telemetry and logging
    
    Example:
        manager = ErrorRecoveryManager()
        
        policy = RetryPolicy(
            max_attempts=5,
            base_delay=2.0,
            jitter=True
        )
        
        result = await manager.execute_with_retry(
            my_operation,
            policy=policy,
            fallback=my_fallback_operation
        )
    """
    
    def __init__(self):
        self.policies: Dict[str, RetryPolicy] = {}
        self.stats = {
            "total_attempts": 0,
            "successful_retries": 0,
            "failed_retries": 0,
            "fallback_used": 0,
        }
    
    def register_policy(self, operation_type: str, policy: RetryPolicy):
        """
        Register a retry policy for a specific operation type.
        
        Args:
            operation_type: Name/type of operation (e.g., "llm_generate")
            policy: RetryPolicy configuration
        """
        self.policies[operation_type] = policy
        logger.info(f"Registered retry policy for {operation_type}: {policy}")
    
    def get_policy(self, operation_type: str) -> RetryPolicy:
        """
        Get retry policy for operation type, or default.
        
        Args:
            operation_type: Name/type of operation
            
        Returns:
            RetryPolicy for this operation
        """
        return self.policies.get(operation_type, RetryPolicy())
    
    async def execute_with_retry(
        self,
        operation: Callable,
        policy: Optional[RetryPolicy] = None,
        fallback: Optional[Callable] = None,
        operation_type: Optional[str] = None,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute operation with retry logic and optional fallback.
        
        Args:
            operation: Async function to execute
            policy: Retry policy (uses default if None)
            fallback: Optional fallback function if all retries fail
            operation_type: Type of operation for policy lookup
            *args: Arguments to pass to operation
            **kwargs: Keyword arguments to pass to operation
            
        Returns:
            Result from operation or fallback
            
        Raises:
            Exception: If all retries fail and no fallback provided
        """
        if policy is None:
            if operation_type:
                policy = self.get_policy(operation_type)
            else:
                policy = RetryPolicy()
        
        attempts = 0
        last_error = None
        
        while attempts < policy.max_attempts:
            attempts += 1
            self.stats["total_attempts"] += 1
            
            try:
                logger.debug(
                    f"Attempting operation (attempt {attempts}/{policy.max_attempts})"
                )
                
                # Execute with timeout if specified
                if policy.timeout:
                    result = await asyncio.wait_for(
                        operation(*args, **kwargs),
                        timeout=policy.timeout
                    )
                else:
                    result = await operation(*args, **kwargs)
                
                # Success!
                if attempts > 1:
                    self.stats["successful_retries"] += 1
                    logger.info(
                        f"✅ Operation succeeded after {attempts} attempts"
                    )
                
                return result
            
            except NonRetryableError as e:
                # Don't retry these errors
                logger.error(f"❌ Non-retryable error: {e}")
                last_error = e
                break
            
            except asyncio.TimeoutError as e:
                logger.warning(
                    f"⏱️  Operation timed out (attempt {attempts}/{policy.max_attempts})"
                )
                last_error = e
            
            except Exception as e:
                logger.warning(
                    f"⚠️  Operation failed (attempt {attempts}/{policy.max_attempts}): {e}"
                )
                last_error = e
            
            # Check if we should retry
            if attempts < policy.max_attempts:
                delay = self._calculate_delay(policy, attempts)
                logger.debug(f"💤 Waiting {delay:.2f}s before retry...")
                await asyncio.sleep(delay)
        
        # All retries failed
        self.stats["failed_retries"] += 1
        logger.error(
            f"❌ Operation failed after {attempts} attempts"
        )
        
        # Try fallback if provided
        if fallback:
            self.stats["fallback_used"] += 1
            logger.info("🔄 Executing fallback operation...")
            
            try:
                result = await fallback(*args, **kwargs)
                logger.info("✅ Fallback succeeded")
                return result
            except Exception as e:
                logger.error(f"❌ Fallback also failed: {e}")
                raise Exception(
                    f"Operation and fallback both failed. Last error: {last_error}"
                ) from e
        
        # No fallback, raise the last error
        raise last_error
    
    def _calculate_delay(self, policy: RetryPolicy, attempt: int) -> float:
        """
        Calculate delay for next retry using exponential backoff with jitter.
        
        Formula:
            delay = base_delay * (exponential_base ^ (attempt - 1))
            delay = min(delay, max_delay)
            if jitter: delay *= random(0.5, 1.5)
        
        Args:
            policy: Retry policy configuration
            attempt: Current attempt number (1-indexed)
            
        Returns:
            Delay in seconds
        """
        # Exponential backoff
        delay = policy.base_delay * (policy.exponential_base ** (attempt - 1))
        
        # Cap at max delay
        delay = min(delay, policy.max_delay)
        
        # Add jitter to prevent thundering herd
        if policy.jitter:
            jitter_factor = random.uniform(0.5, 1.5)
            delay *= jitter_factor
        
        return delay
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get retry statistics.
        
        Returns:
            Dictionary with retry stats
        """
        return {
            **self.stats,
            "success_rate": (
                self.stats["successful_retries"] / self.stats["total_attempts"]
                if self.stats["total_attempts"] > 0 else 0.0
            ),
            "registered_policies": len(self.policies),
        }
    
    def reset_statistics(self):
        """Reset all statistics counters"""
        self.stats = {
            "total_attempts": 0,
            "successful_retries": 0,
            "failed_retries": 0,
            "fallback_used": 0,
        }


# Global instance for convenience
_global_manager = None


def get_error_recovery_manager() -> ErrorRecoveryManager:
    """Get global ErrorRecoveryManager instance"""
    global _global_manager
    if _global_manager is None:
        _global_manager = ErrorRecoveryManager()
    return _global_manager


if __name__ == "__main__":
    # Quick test
    async def test():
        manager = ErrorRecoveryManager()
        
        # Test successful operation
        async def succeeds():
            return "success"
        
        result = await manager.execute_with_retry(succeeds)
        print(f"✅ Success test: {result}")
        
        # Test with retries
        attempt_count = 0
        async def fails_twice():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise Exception(f"Attempt {attempt_count} failed")
            return "success after retries"
        
        result = await manager.execute_with_retry(fails_twice)
        print(f"✅ Retry test: {result}")
        
        # Test with fallback
        async def always_fails():
            raise Exception("Always fails")
        
        async def fallback_fn():
            return "fallback success"
        
        result = await manager.execute_with_retry(
            always_fails,
            fallback=fallback_fn
        )
        print(f"✅ Fallback test: {result}")
        
        # Print stats
        print(f"\n📊 Stats: {manager.get_statistics()}")
    
    asyncio.run(test())
