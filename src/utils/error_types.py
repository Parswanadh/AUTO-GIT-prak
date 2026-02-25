"""
Custom exception types for error handling in the pipeline.

Error Categories:
- TRANSIENT: Temporary failures (network timeouts, rate limits) → retry
- PERMANENT: Permanent failures (404, invalid data) → skip, don't retry
- CRITICAL: System-level failures (disk full) → stop pipeline
"""

from enum import Enum
from typing import Optional, Any


class ErrorCategory(Enum):
    """Error classification for handling strategy"""
    TRANSIENT = "TRANSIENT"  # Retry with backoff
    PERMANENT = "PERMANENT"  # Skip, don't retry
    CRITICAL = "CRITICAL"    # Stop pipeline


class PipelineError(Exception):
    """
    Base exception for all pipeline errors with error classification.
    """
    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.TRANSIENT,
        details: Optional[dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        self.category = category
        self.details = details or {}
        self.original_error = original_error
        super().__init__(message)

    def is_retryable(self) -> bool:
        """Check if error is retryable"""
        return self.category == ErrorCategory.TRANSIENT

    def is_critical(self) -> bool:
        """Check if error should stop the pipeline"""
        return self.category == ErrorCategory.CRITICAL

    def to_dict(self) -> dict[str, Any]:
        """Convert error to dictionary for logging"""
        return {
            "error_type": self.__class__.__name__,
            "message": str(self),
            "category": self.category.value,
            "details": self.details,
            "original_error": str(self.original_error) if self.original_error else None
        }


class OllamaConnectionError(PipelineError):
    """
    Ollama server connection failed - TRANSIENT by default.
    Retry with exponential backoff.
    """
    def __init__(
        self,
        message: str,
        details: Optional[dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        super().__init__(
            message,
            category=ErrorCategory.TRANSIENT,
            details=details,
            original_error=original_error
        )


class TokenLimitExceeded(PipelineError):
    """
    Token usage exceeded limits - PERMANENT (reduce input size).
    """
    def __init__(
        self,
        message: str,
        details: Optional[dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        super().__init__(
            message,
            category=ErrorCategory.PERMANENT,
            details=details,
            original_error=original_error
        )


class AgentExecutionError(PipelineError):
    """
    Agent execution failed - TRANSIENT by default (retryable).
    """
    def __init__(
        self,
        agent_name: str,
        message: str,
        category: ErrorCategory = ErrorCategory.TRANSIENT,
        details: Optional[dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        self.agent_name = agent_name
        details = details or {}
        details["agent_name"] = agent_name
        super().__init__(
            f"Agent '{agent_name}' failed: {message}",
            category=category,
            details=details,
            original_error=original_error
        )


class ValidationError(PipelineError):
    """
    Validation check failed - PERMANENT (data is invalid).
    """
    def __init__(
        self,
        message: str,
        validation_type: str = "unknown",
        details: Optional[dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        details = details or {}
        details["validation_type"] = validation_type
        super().__init__(
            message,
            category=ErrorCategory.PERMANENT,
            details=details,
            original_error=original_error
        )


class ResourceExhaustedError(PipelineError):
    """
    System resources exhausted (memory, disk, etc.) - CRITICAL.
    Stop the pipeline.
    """
    def __init__(
        self,
        message: str,
        resource_type: str = "unknown",
        details: Optional[dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        details = details or {}
        details["resource_type"] = resource_type
        super().__init__(
            message,
            category=ErrorCategory.CRITICAL,
            details=details,
            original_error=original_error
        )


class CircuitBreakerOpen(PipelineError):
    """
    Circuit breaker activated due to repeated failures - TRANSIENT.
    Wait before retrying.
    """
    def __init__(
        self,
        service_name: str,
        failure_count: int,
        message: str = "",
        details: Optional[dict[str, Any]] = None
    ):
        details = details or {}
        details.update({
            "service_name": service_name,
            "failure_count": failure_count
        })
        msg = message or f"Circuit breaker open for {service_name} after {failure_count} failures"
        super().__init__(
            msg,
            category=ErrorCategory.TRANSIENT,
            details=details
        )


class CheckpointError(PipelineError):
    """
    Error saving or loading checkpoint - PERMANENT (can't recover).
    """
    def __init__(
        self,
        message: str,
        checkpoint_path: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        details = details or {}
        if checkpoint_path:
            details["checkpoint_path"] = checkpoint_path
        super().__init__(
            message,
            category=ErrorCategory.PERMANENT,
            details=details,
            original_error=original_error
        )


class ConfigurationError(PipelineError):
    """
    Invalid configuration - PERMANENT (fix config before retry).
    """
    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        details: Optional[dict[str, Any]] = None
    ):
        details = details or {}
        if config_key:
            details["config_key"] = config_key
        super().__init__(
            message,
            category=ErrorCategory.PERMANENT,
            details=details
        )


class NetworkError(PipelineError):
    """
    Network operation failed - TRANSIENT (retry with backoff).
    """
    def __init__(
        self,
        message: str,
        url: Optional[str] = None,
        status_code: Optional[int] = None,
        details: Optional[dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        details = details or {}
        if url:
            details["url"] = url
        if status_code:
            details["status_code"] = status_code
        super().__init__(
            message,
            category=ErrorCategory.TRANSIENT,
            details=details,
            original_error=original_error
        )


class RateLimitError(NetworkError):
    """
    API rate limit exceeded - TRANSIENT (wait and retry).
    """
    def __init__(
        self,
        message: str,
        service: str,
        retry_after: Optional[int] = None,
        details: Optional[dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        details = details or {}
        details["service"] = service
        if retry_after:
            details["retry_after_seconds"] = retry_after
        super().__init__(
            message,
            details=details,
            original_error=original_error
        )


class ParsingError(PipelineError):
    """
    Failed to parse response/data - PERMANENT (data is malformed).
    Can be TRANSIENT if it's a JSON parsing issue from LLM (might retry).
    """
    def __init__(
        self,
        message: str,
        content_type: str = "unknown",
        is_retryable: bool = False,
        details: Optional[dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        category = ErrorCategory.TRANSIENT if is_retryable else ErrorCategory.PERMANENT
        details = details or {}
        details["content_type"] = content_type
        super().__init__(
            message,
            category=category,
            details=details,
            original_error=original_error
        )


class PersonaGenerationError(PipelineError):
    """
    Failed to generate dynamic personas - TRANSIENT (can fall back to base personas).
    """
    def __init__(
        self,
        message: str,
        domain: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        details = details or {}
        if domain:
            details["domain"] = domain
        super().__init__(
            message,
            category=ErrorCategory.TRANSIENT,
            details=details,
            original_error=original_error
        )


# Helper function to classify standard Python exceptions
def classify_exception(error: Exception, context: str = "") -> PipelineError:
    """
    Convert standard Python exceptions to categorized PipelineErrors.

    Args:
        error: The original exception
        context: Additional context about where error occurred

    Returns:
        Categorized PipelineError
    """
    error_type = type(error).__name__
    error_msg = str(error)

    # Network/Connection errors
    if isinstance(error, (ConnectionError, TimeoutError)):
        return NetworkError(
            message=f"Network error in {context}: {error_msg}",
            original_error=error
        )

    # JSON parsing errors (often from LLM responses)
    if isinstance(error, (SyntaxError, ValueError)) and "JSON" in error_msg:
        return ParsingError(
            message=f"JSON parsing error in {context}: {error_msg}",
            content_type="json",
            is_retryable=True,  # LLM might generate valid JSON on retry
            original_error=error
        )

    # File/OS errors
    if isinstance(error, (FileNotFoundError, PermissionError)):
        return ResourceExhaustedError(
            message=f"File system error in {context}: {error_msg}",
            resource_type="filesystem",
            original_error=error
        )

    if isinstance(error, OSError) and "No space left" in error_msg:
        return ResourceExhaustedError(
            message=f"Disk full in {context}: {error_msg}",
            resource_type="disk",
            original_error=error
        )

    # Memory errors
    if isinstance(error, MemoryError):
        return ResourceExhaustedError(
            message=f"Memory error in {context}: {error_msg}",
            resource_type="memory",
            original_error=error
        )

    # Default: treat as transient agent error
    return AgentExecutionError(
        agent_name=context or "unknown",
        message=f"{error_type}: {error_msg}",
        category=ErrorCategory.TRANSIENT,
        original_error=error
    )
