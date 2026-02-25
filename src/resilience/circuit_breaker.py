"""
Circuit Breaker - Integration #16

Implements the circuit breaker pattern to prevent repeated calls
to failing services, allowing them time to recover.
"""

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Callable, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation, requests pass through
    OPEN = "open"          # Service failing, requests fail fast
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open"""
    pass


@dataclass
class CircuitBreakerStats:
    """Circuit breaker statistics"""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0  # Calls rejected due to open circuit
    state_transitions: int = 0


class CircuitBreaker:
    """
    Circuit breaker implementation to prevent cascade failures.
    
    States:
    - CLOSED: Normal operation, all requests pass through
    - OPEN: Failure threshold reached, all requests fail fast
    - HALF_OPEN: Testing recovery, limited requests allowed
    
    Transitions:
    - CLOSED → OPEN: After N consecutive failures
    - OPEN → HALF_OPEN: After timeout period
    - HALF_OPEN → CLOSED: After successful test request
    - HALF_OPEN → OPEN: If test request fails
    
    Example:
        breaker = CircuitBreaker(
            failure_threshold=5,
            timeout=60.0
        )
        
        try:
            result = await breaker.call(my_operation, arg1, arg2)
        except CircuitBreakerOpenError:
            # Circuit is open, use fallback
            result = await fallback_operation(arg1, arg2)
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: float = 60.0,
        half_open_max_calls: int = 1,
        name: str = "unnamed"
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            timeout: Seconds to wait before trying HALF_OPEN
            half_open_max_calls: Max concurrent calls in HALF_OPEN state
            name: Name for logging/identification
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.half_open_max_calls = half_open_max_calls
        
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._stats = CircuitBreakerStats()
        
        logger.info(
            f"Circuit breaker '{name}' initialized: "
            f"threshold={failure_threshold}, timeout={timeout}s"
        )
    
    @property
    def state(self) -> CircuitBreakerState:
        """Get current state"""
        return self._state
    
    @property
    def stats(self) -> CircuitBreakerStats:
        """Get statistics"""
        return self._stats
    
    async def call(self, operation: Callable, *args, **kwargs) -> Any:
        """
        Execute operation through circuit breaker.
        
        Args:
            operation: Async function to execute
            *args: Arguments to pass to operation
            **kwargs: Keyword arguments to pass to operation
            
        Returns:
            Result from operation
            
        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: Any exception from operation
        """
        # Check if we should transition from OPEN to HALF_OPEN
        if self._state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self._transition_to_half_open()
            else:
                self._stats.rejected_calls += 1
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is OPEN "
                    f"(will retry in {self._time_until_retry():.1f}s)"
                )
        
        # Check if HALF_OPEN allows more calls
        if self._state == CircuitBreakerState.HALF_OPEN:
            if self._half_open_calls >= self.half_open_max_calls:
                self._stats.rejected_calls += 1
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is HALF_OPEN "
                    f"(testing in progress, max calls reached)"
                )
            self._half_open_calls += 1
        
        # Execute operation
        self._stats.total_calls += 1
        
        try:
            result = await operation(*args, **kwargs)
            self.record_success()
            return result
        
        except Exception as e:
            self.record_failure()
            raise
    
    def record_success(self):
        """Record successful operation"""
        self._stats.successful_calls += 1
        
        if self._state == CircuitBreakerState.HALF_OPEN:
            # Success in HALF_OPEN → close circuit
            logger.info(
                f"✅ Circuit breaker '{self.name}' HALF_OPEN test succeeded, "
                f"transitioning to CLOSED"
            )
            self._transition_to_closed()
        
        # Reset failure count on success
        self._failure_count = 0
    
    def record_failure(self):
        """Record failed operation"""
        self._stats.failed_calls += 1
        self._failure_count += 1
        self._last_failure_time = time.time()
        
        if self._state == CircuitBreakerState.HALF_OPEN:
            # Failure in HALF_OPEN → reopen circuit
            logger.warning(
                f"❌ Circuit breaker '{self.name}' HALF_OPEN test failed, "
                f"transitioning back to OPEN"
            )
            self._transition_to_open()
        
        elif self._state == CircuitBreakerState.CLOSED:
            # Check if we should open circuit
            if self._failure_count >= self.failure_threshold:
                logger.error(
                    f"🚨 Circuit breaker '{self.name}' threshold reached "
                    f"({self._failure_count} failures), transitioning to OPEN"
                )
                self._transition_to_open()
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if self._last_failure_time is None:
            return True
        
        return (time.time() - self._last_failure_time) >= self.timeout
    
    def _time_until_retry(self) -> float:
        """Calculate seconds until next retry attempt"""
        if self._last_failure_time is None:
            return 0.0
        
        elapsed = time.time() - self._last_failure_time
        remaining = self.timeout - elapsed
        return max(0.0, remaining)
    
    def _transition_to_open(self):
        """Transition to OPEN state"""
        self._state = CircuitBreakerState.OPEN
        self._half_open_calls = 0
        self._stats.state_transitions += 1
    
    def _transition_to_half_open(self):
        """Transition to HALF_OPEN state"""
        self._state = CircuitBreakerState.HALF_OPEN
        self._half_open_calls = 0
        self._stats.state_transitions += 1
        logger.info(
            f"🔄 Circuit breaker '{self.name}' transitioning to HALF_OPEN "
            f"(testing recovery)"
        )
    
    def _transition_to_closed(self):
        """Transition to CLOSED state"""
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._half_open_calls = 0
        self._stats.state_transitions += 1
    
    def reset(self):
        """Manually reset circuit breaker to CLOSED state"""
        logger.info(f"🔧 Manually resetting circuit breaker '{self.name}'")
        self._transition_to_closed()
    
    def get_status(self) -> dict:
        """Get detailed status information"""
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "timeout": self.timeout,
            "time_until_retry": self._time_until_retry(),
            "stats": {
                "total_calls": self._stats.total_calls,
                "successful_calls": self._stats.successful_calls,
                "failed_calls": self._stats.failed_calls,
                "rejected_calls": self._stats.rejected_calls,
                "state_transitions": self._stats.state_transitions,
                "success_rate": (
                    self._stats.successful_calls / self._stats.total_calls
                    if self._stats.total_calls > 0 else 0.0
                ),
            },
        }


if __name__ == "__main__":
    # Quick test
    async def test():
        print("Testing Circuit Breaker\n")
        
        breaker = CircuitBreaker(
            failure_threshold=3,
            timeout=5.0,
            name="test_breaker"
        )
        
        # Test 1: Successful calls
        print("Test 1: Successful operations")
        async def succeeds():
            return "success"
        
        for i in range(3):
            result = await breaker.call(succeeds)
            print(f"  Call {i+1}: {result}, state={breaker.state.value}")
        
        # Test 2: Failures to open circuit
        print("\nTest 2: Failures to open circuit")
        async def fails():
            raise Exception("Operation failed")
        
        for i in range(3):
            try:
                await breaker.call(fails)
            except Exception:
                print(f"  Call {i+1}: Failed, state={breaker.state.value}")
        
        # Test 3: Circuit is open
        print("\nTest 3: Circuit open - fast fail")
        try:
            await breaker.call(succeeds)
        except CircuitBreakerOpenError as e:
            print(f"  ✅ Correctly rejected: {e}")
        
        # Test 4: Wait for HALF_OPEN
        print("\nTest 4: Wait for HALF_OPEN transition")
        print(f"  Waiting {breaker.timeout}s...")
        await asyncio.sleep(breaker.timeout + 1)
        
        # Test 5: HALF_OPEN test succeeds
        print("\nTest 5: HALF_OPEN test succeeds")
        result = await breaker.call(succeeds)
        print(f"  Call succeeded: {result}, state={breaker.state.value}")
        
        # Print final status
        print("\n📊 Final Status:")
        status = breaker.get_status()
        for key, value in status.items():
            if key != "stats":
                print(f"  {key}: {value}")
            else:
                print(f"  stats:")
                for stat_key, stat_value in value.items():
                    print(f"    {stat_key}: {stat_value}")
    
    asyncio.run(test())
