"""
Comprehensive retry decorator with exponential backoff for external calls.

Features:
- Error-aware retry (only retry TRANSIENT errors)
- Exponential backoff with jitter
- Circuit breaker integration
- Detailed logging of retry attempts
- Configurable max attempts and timeouts
"""

import asyncio
import functools
import random
import time
from typing import Callable, TypeVar, ParamSpec, Any
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception_type,
    before_sleep_log,
    after_log,
)

from src.utils.error_types import (
    PipelineError,
    ErrorCategory,
    NetworkError,
    OllamaConnectionError,
    RateLimitError,
    PersonaGenerationError,
    ParsingError,
)
from src.utils.logger import get_logger

logger = get_logger("retry")


T = TypeVar("T")
P = ParamSpec("P")


def is_retryable_error(exception: Exception) -> bool:
    """
    Check if exception is retryable based on error category.

    Args:
        exception: The exception to check

    Returns:
        True if error should be retried
    """
    if isinstance(exception, PipelineError):
        return exception.is_retryable()

    # Standard library exceptions that are retryable
    return isinstance(exception, (ConnectionError, TimeoutError))


class RetryConfig:
    """
    Configuration for retry behavior.

    Attributes:
        max_attempts: Maximum number of retry attempts
        min_wait: Minimum wait time between retries (seconds)
        max_wait: Maximum wait time between retries (seconds)
        exponential_base: Base for exponential backoff
        jitter: Add random jitter to wait times
    """

    def __init__(
        self,
        max_attempts: int = 3,
        min_wait: float = 1.0,
        max_wait: float = 60.0,
        exponential_base: int = 2,
        jitter: bool = True,
    ):
        self.max_attempts = max_attempts
        self.min_wait = min_wait
        self.max_wait = max_wait
        self.exponential_base = exponential_base
        self.jitter = jitter


def with_retry(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 60.0,
    on_failure: str = "raise",  # "raise", "return_default", "return_none"
    default_value: Any = None,
    operation_name: str = "operation",
):
    """
    Decorator for retrying operations with exponential backoff.

    Only retries TRANSIENT errors. PERMANENT and CRITICAL errors are raised immediately.

    Args:
        max_attempts: Maximum number of attempts (including first attempt)
        min_wait: Minimum wait time between retries (seconds)
        max_wait: Maximum wait time between retries (seconds)
        on_failure: What to do after max attempts exhausted
        default_value: Value to return if on_failure="return_default"
        operation_name: Name of operation for logging

    Example:
        @with_retry(max_attempts=3, operation_name="fetch_paper")
        async def fetch_arxiv_paper(paper_id: str):
            ...
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_error = None

            for attempt in range(1, max_attempts + 1):
                try:
                    if attempt > 1:
                        logger.info(
                            f"Retry attempt {attempt}/{max_attempts} for {operation_name}"
                        )

                    result = await func(*args, **kwargs)
                    if attempt > 1:
                        logger.info(
                            f"✅ {operation_name} succeeded on attempt {attempt}"
                        )
                    return result

                except Exception as e:
                    last_error = e

                    # Check if error is retryable
                    pipeline_error = (
                        e if isinstance(e, PipelineError)
                        else PipelineError(str(e), category=ErrorCategory.TRANSIENT)
                    )

                    if not pipeline_error.is_retryable():
                        logger.error(
                            f"❌ {operation_name} failed with non-retryable error: "
                            f"{pipeline_error.to_dict()}"
                        )
                        raise

                    # Log retry attempt
                    wait_time = min(
                        min_wait * (2 ** (attempt - 1)),
                        max_wait
                    )
                    if random.random() < 0.5:
                        wait_time = max(wait_time * 0.5, min_wait)

                    logger.warning(
                        f"⚠️ {operation_name} attempt {attempt}/{max_attempts} failed: "
                        f"{type(e).__name__}: {str(e)[:100]}. "
                        f"Retrying in {wait_time:.1f}s..."
                    )

                    if attempt < max_attempts:
                        await asyncio.sleep(wait_time)

            # All attempts exhausted
            logger.error(
                f"❌ {operation_name} failed after {max_attempts} attempts. "
                f"Last error: {type(last_error).__name__}: {str(last_error)[:200]}"
            )

            if on_failure == "return_none":
                return None  # type: ignore
            elif on_failure == "return_default":
                return default_value  # type: ignore
            else:
                raise last_error

        @functools.wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_error = None

            for attempt in range(1, max_attempts + 1):
                try:
                    if attempt > 1:
                        logger.info(
                            f"Retry attempt {attempt}/{max_attempts} for {operation_name}"
                        )

                    result = func(*args, **kwargs)
                    if attempt > 1:
                        logger.info(
                            f"✅ {operation_name} succeeded on attempt {attempt}"
                        )
                    return result

                except Exception as e:
                    last_error = e

                    # Check if error is retryable
                    pipeline_error = (
                        e if isinstance(e, PipelineError)
                        else PipelineError(str(e), category=ErrorCategory.TRANSIENT)
                    )

                    if not pipeline_error.is_retryable():
                        logger.error(
                            f"❌ {operation_name} failed with non-retryable error: "
                            f"{pipeline_error.to_dict()}"
                        )
                        raise

                    # Log retry attempt
                    wait_time = min(
                        min_wait * (2 ** (attempt - 1)),
                        max_wait
                    )
                    if random.random() < 0.5:
                        wait_time = max(wait_time * 0.5, min_wait)

                    logger.warning(
                        f"⚠️ {operation_name} attempt {attempt}/{max_attempts} failed: "
                        f"{type(e).__name__}: {str(e)[:100]}. "
                        f"Retrying in {wait_time:.1f}s..."
                    )

                    if attempt < max_attempts:
                        time.sleep(wait_time)

            # All attempts exhausted
            logger.error(
                f"❌ {operation_name} failed after {max_attempts} attempts. "
                f"Last error: {type(last_error).__name__}: {str(last_error)[:200]}"
            )

            if on_failure == "return_none":
                return None  # type: ignore
            elif on_failure == "return_default":
                return default_value  # type: ignore
            else:
                raise last_error

        # Return appropriate wrapper based on whether function is async
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore

    return decorator


# Tenacity-based retry decorator (alternative approach)
def tenacity_retry(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 60.0,
    operation_name: str = "operation",
):
    """
    Tenacity-based retry decorator with more advanced features.

    Uses tenacity library for robust retry logic with:
    - Exponential backoff with jitter
    - Retry condition checking
    - Before/after hooks for logging

    Args:
        max_attempts: Maximum number of retry attempts
        min_wait: Minimum wait time in seconds
        max_wait: Maximum wait time in seconds
        operation_name: Name for logging

    Example:
        @tenacity_retry(max_attempts=3, operation_name="llm_call")
        async def generate_with_llm(prompt: str):
            ...
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        return retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential_jitter(
                exponential_base=2,
                min=min_wait,
                max=max_wait,
                jitter=True,  # Add randomness to prevent thundering herd
            ),
            retry=retry_if_exception_type(PipelineError) & is_retryable_error,
            before_sleep=before_sleep_log(logger, logger.level),
            after=after_log(logger, logger.level),
            reraise=True,
        )(func)

    return decorator


class CircuitBreaker:
    """
    Circuit breaker to prevent repeated calls to failing services.

    After threshold failures, circuit opens and refuses calls for cooldown period.
    """

    def __init__(
        self,
        service_name: str,
        failure_threshold: int = 5,
        cooldown_seconds: int = 300,
    ):
        """
        Initialize circuit breaker.

        Args:
            service_name: Name of service being protected
            failure_threshold: Number of failures before opening circuit
            cooldown_seconds: How long to keep circuit open
        """
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.failure_count = 0
        self.last_failure_time = 0
        self.is_open = False

    def record_success(self):
        """Record a successful call."""
        self.failure_count = 0
        self.is_open = False
        logger.debug(f"Circuit breaker closed for {self.service_name}")

    def record_failure(self):
        """Record a failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.is_open = True
            logger.error(
                f"⚡ Circuit breaker OPENED for {self.service_name} "
                f"after {self.failure_count} failures"
            )

    def allow_request(self) -> bool:
        """
        Check if request should be allowed.

        Returns:
            True if request can proceed, False if circuit is open
        """
        if not self.is_open:
            return True

        # Check if cooldown period has elapsed
        time_since_failure = time.time() - self.last_failure_time
        if time_since_failure > self.cooldown_seconds:
            logger.info(
                f"Circuit breaker cooldown elapsed for {self.service_name}, "
                f"allowing trial request"
            )
            self.is_open = False
            self.failure_count = 0
            return True

        logger.warning(
            f"Circuit breaker blocking request to {self.service_name} "
            f"({self.cooldown_seconds - time_since_failure:.0f}s remaining)"
        )
        return False

    def raise_if_open(self):
        """Raise exception if circuit is open."""
        if self.is_open:
            raise CircuitBreakerOpen(
                service_name=self.service_name,
                failure_count=self.failure_count,
            )


# Global circuit breakers for common services
_circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    service_name: str,
    failure_threshold: int = 5,
    cooldown_seconds: int = 300,
) -> CircuitBreaker:
    """
    Get or create circuit breaker for a service.

    Args:
        service_name: Name of service
        failure_threshold: Failures before opening circuit
        cooldown_seconds: Cooldown period in seconds

    Returns:
        CircuitBreaker instance
    """
    if service_name not in _circuit_breakers:
        _circuit_breakers[service_name] = CircuitBreaker(
            service_name=service_name,
            failure_threshold=failure_threshold,
            cooldown_seconds=cooldown_seconds,
        )
    return _circuit_breakers[service_name]


def with_circuit_breaker(
    service_name: str,
    failure_threshold: int = 5,
    cooldown_seconds: int = 300,
):
    """
    Decorator that wraps function with circuit breaker protection.

    Args:
        service_name: Name of service for circuit breaker
        failure_threshold: Failures before opening circuit
        cooldown_seconds: Cooldown period

    Example:
        @with_circuit_breaker("arxiv_api", failure_threshold=5, cooldown_seconds=300)
        async def fetch_arxiv_paper(paper_id: str):
            ...
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        breaker = get_circuit_breaker(service_name, failure_threshold, cooldown_seconds)

        @functools.wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            breaker.raise_if_open()

            try:
                result = await func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure()
                raise

        @functools.wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            breaker.raise_if_open()

            try:
                result = func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure()
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore

    return decorator


# Combined decorator: retry + circuit breaker
def with_resilience(
    service_name: str,
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 60.0,
    failure_threshold: int = 5,
    cooldown_seconds: int = 300,
):
    """
    Combined decorator with both retry logic and circuit breaker.

    This provides maximum resilience for external service calls.

    Args:
        service_name: Name of service for circuit breaker
        max_attempts: Maximum retry attempts
        min_wait: Minimum wait between retries
        max_wait: Maximum wait between retries
        failure_threshold: Failures before opening circuit
        cooldown_seconds: Circuit breaker cooldown period

    Example:
        @with_resilience("github_api", max_attempts=3)
        async def create_github_repo(repo_name: str):
            ...
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        # Apply circuit breaker first, then retry
        return with_circuit_breaker(
            service_name, failure_threshold, cooldown_seconds
        )(
            with_retry(
                max_attempts=max_attempts,
                min_wait=min_wait,
                max_wait=max_wait,
                operation_name=service_name,
            )(func)
        )

    return decorator
