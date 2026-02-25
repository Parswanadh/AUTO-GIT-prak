"""
Resilience Package - Integration #16

Provides production-grade error recovery, circuit breakers,
and resilience patterns for the Auto-Git system.

Components:
- error_recovery: Retry logic with exponential backoff
- circuit_breaker: Prevent cascade failures
- fallback_chain: Graceful degradation
- error_budget: Rate limiting on errors
- recovery_coordinator: Cross-component recovery orchestration
"""

from .error_recovery import ErrorRecoveryManager, RetryPolicy
from .circuit_breaker import CircuitBreaker, CircuitBreakerState, CircuitBreakerOpenError
from .fallback_chain import FallbackChain, FallbackExhaustedError
from .error_budget import ErrorBudget, ErrorBudgetExhaustedError

__all__ = [
    "ErrorRecoveryManager",
    "RetryPolicy",
    "CircuitBreaker",
    "CircuitBreakerState",
    "CircuitBreakerOpenError",
    "FallbackChain",
    "FallbackExhaustedError",
    "ErrorBudget",
    "ErrorBudgetExhaustedError",
]
