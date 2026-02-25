# AUTO-GIT Phase 2: Error Handling Guide

**Version**: 2.0
**Date**: January 6, 2026
**Status**: Production Ready

---

## Table of Contents

1. [Error Categories](#error-categories)
2. [Exception Types](#exception-types)
3. [Retry Strategy](#retry-strategy)
4. [Fallback Mechanisms](#fallback-mechanisms)
5. [Error Recovery](#error-recovery)
6. [Best Practices](#best-practices)

---

## Error Categories

AUTO-GIT classifies errors into three categories that determine how they're handled:

### TRANSIENT Errors
**Definition**: Temporary failures that can be resolved by retrying.

**Examples**:
- Network timeouts
- API rate limits
- Temporary service unavailability
- LLM generation timeouts

**Handling Strategy**: Retry with exponential backoff (1s, 2s, 4s, ... up to 60s)

**Maximum Retries**: 3 attempts by default (configurable)

```python
from src.utils.error_types import NetworkError, ErrorCategory

error = NetworkError(
    message="Connection timeout",
    url="https://api.example.com"
)
# error.category == ErrorCategory.TRANSIENT
# error.is_retryable() == True
```

### PERMANENT Errors
**Definition**: Failures that won't be resolved by retrying.

**Examples**:
- 404 Not Found (paper doesn't exist)
- Invalid JSON schema
- Authentication failures
- Malformed data

**Handling Strategy**: Skip operation, continue pipeline, log error

```python
from src.utils.error_types import ValidationError

error = ValidationError(
    message="Invalid JSON structure",
    validation_type="json_schema"
)
# error.category == ErrorCategory.PERMANENT
# error.is_retryable() == False
```

### CRITICAL Errors
**Definition**: System-level failures that require human intervention.

**Examples**:
- Disk full
- Out of memory
- Database corruption
- Configuration errors

**Handling Strategy**: Stop pipeline, alert operator, save checkpoint

```python
from src.utils.error_types import ResourceExhaustedError

error = ResourceExhaustedError(
    message="No space left on device",
    resource_type="disk"
)
# error.category == ErrorCategory.CRITICAL
# error.is_critical() == True
```

---

## Exception Types

### Base Exception

```python
class PipelineError(Exception):
    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.TRANSIENT,
        details: Optional[dict] = None,
        original_error: Optional[Exception] = None
    )
```

### Common Exceptions

| Exception Type | Category | When to Use |
|----------------|----------|-------------|
| `NetworkError` | TRANSIENT | API calls, network operations |
| `RateLimitError` | TRANSIENT | API rate limits exceeded |
| `OllamaConnectionError` | TRANSIENT | Ollama server unreachable |
| `ParsingError` | TRANSIENT/PERMANENT | JSON parsing failures |
| `ValidationError` | PERMANENT | Code validation failures |
| `ConfigurationError` | PERMANENT | Invalid configuration |
| `ResourceExhaustedError` | CRITICAL | Disk/memory exhausted |
| `CircuitBreakerOpen` | TRANSIENT | Too many repeated failures |

### Auto-Classification

Standard Python exceptions are automatically classified:

```python
from src.utils.error_types import classify_exception

try:
    # Some operation that might fail
    result = parse_json(data)
except Exception as e:
    pipeline_error = classify_exception(e, context="json_parsing")
    # Returns appropriately categorized PipelineError
```

---

## Retry Strategy

### Basic Retry Decorator

```python
from src.utils.retry import with_retry

@with_retry(
    max_attempts=3,
    min_wait=1.0,
    max_wait=60.0,
    operation_name="fetch_paper"
)
async def fetch_arxiv_paper(paper_id: str):
    # This will be retried up to 3 times if it fails
    ...
```

### Retry with Circuit Breaker

```python
from src.utils.retry import with_resilience

@with_resilience(
    service_name="github_api",
    max_attempts=3,
    failure_threshold=5,
    cooldown_seconds=300
)
async def create_github_repo(repo_name: str):
    # Protected by retry + circuit breaker
    ...
```

### Retry Behavior

1. **First Attempt**: Execute operation normally
2. **On Failure**:
   - Check if error is retryable (`is_retryable()`)
   - If not retryable: raise immediately
   - If retryable: calculate wait time and retry
3. **Wait Time**: `min(min_wait * 2^(attempt-1), max_wait)` with jitter
4. **After Max Attempts**: Raise last error or return default

### Example Retry Timeline

```
Attempt 1: Fail → Wait 1.0s
Attempt 2: Fail → Wait 2.0s
Attempt 3: Fail → Wait 4.0s
Attempt 4: Fail → Raise error (if max_attempts=3)
```

---

## Fallback Mechanisms

### Persona Generation Fallback Chain

```
Level 1: Dynamic LLM generation
    ↓ (fail)
Level 2: Cached personas for domain
    ↓ (miss)
Level 3: Hardcoded domain-specific personas
    ↓ (no match)
Level 4: Base 3 personas (always succeeds)
```

### Search Fallback Chain

```
Level 1: arxiv Python library
    ↓ (fail)
Level 2: Cached search results
    ↓ (miss)
Level 3: ChromaDB local search
    ↓ (fail)
Level 4: Empty results (graceful degradation)
```

### Using Fallbacks

```python
from src.utils.fallback import get_personas_with_fallback

personas_result = await get_personas_with_fallback(
    domain="machine learning"
)
# Returns: {"personas": [...], "source": "cache|hardcoded|base"}
```

---

## Error Recovery

### Circuit Breaker

When a service fails repeatedly, the circuit breaker opens:

1. **Closed State**: Normal operation, requests pass through
2. **Open State**: Requests fail immediately, no retries
3. **Half-Open**: After cooldown, one trial request allowed
4. **Recovery**: If trial succeeds, circuit closes

```python
from src.utils.retry import get_circuit_breaker

breaker = get_circuit_breaker("arxiv_api", failure_threshold=5)

# Circuit opens after 5 failures
# Remains open for 5 minutes (cooldown)
# Then allows one trial request
```

### Checkpoint Recovery

Pipeline state is saved periodically:

```python
# Automatic checkpointing (every 5 minutes)
# Manual checkpoint on critical stages
# Resume from last checkpoint on restart
```

### Graceful Degradation

System continues with reduced functionality:

- Persona generation fails → Use base personas
- One critique fails → Continue with remaining critiques
- Validation fails → Mark as "needs review", don't crash
- Cache fails → Operate without caching

---

## Best Practices

### DO ✅

1. **Always categorize errors**
   ```python
   raise NetworkError("Timeout", category=ErrorCategory.TRANSIENT)
   ```

2. **Include context in error details**
   ```python
   raise ValidationError(
       "Code validation failed",
       validation_type="security",
       details={"file": "model.py", "issues": [...]}
   )
   ```

3. **Use retry decorators for external calls**
   ```python
   @with_retry(max_attempts=3, operation_name="api_call")
   async def external_api_call():
       ...
   ```

4. **Log errors with structured logging**
   ```python
   slog.error(
       "LLM generation failed",
       error_type="TimeoutError",
       error_message=str(e),
       paper_id=paper_id
   )
   ```

5. **Let errors propagate to appropriate handler**
   ```python
   # Don't silently catch exceptions
   try:
       result = await operation()
   except PipelineError:
       # Handle pipeline errors appropriately
       raise  # or provide fallback
   ```

### DON'T ❌

1. **Don't catch all exceptions silently**
   ```python
   # BAD
   try:
       result = do_something()
   except:
       return []  # Hides real errors
   ```

2. **Don't retry non-retryable errors**
   ```python
   # Don't retry 404s, authentication errors, etc.
   ```

3. **Don't ignore CRITICAL errors**
   ```python
   # Don't continue if disk is full
   ```

4. **Don't use empty exception handlers**
   ```python
   # BAD
   except Exception:
       pass
   ```

5. **Don't raise generic exceptions**
   ```python
   # BAD
   raise Exception("Something went wrong")

   # GOOD
   raise ValidationError("Invalid JSON", validation_type="json")
   ```

---

## Troubleshooting

### Common Error Patterns

#### "Circuit breaker open for X"
- **Cause**: Service failed 5+ times in a row
- **Solution**: Wait for cooldown (default 5 minutes) or reset circuit breaker
- **Prevention**: Fix underlying service issue

#### "All fallback levels failed"
- **Cause**: Primary + all fallbacks failed
- **Solution**: Check service availability, verify configuration
- **Prevention**: Ensure at least one fallback is always available

#### "Validation failed: score below threshold"
- **Cause**: Generated code has too many issues
- **Solution**: Review validation report, fix issues
- **Prevention**: Improve code generation quality

### Debugging Tips

1. **Check structured logs**
   ```bash
   cat ./logs/structured/paper_2401.12345.jsonl | jq .
   ```

2. **Review error aggregation**
   ```python
   from src.utils.structured_logging import ErrorAggregator
   aggregator = ErrorAggregator()
   report = aggregator.analyze_errors()
   ```

3. **Examine circuit breaker state**
   ```python
   from src.utils.retry import get_circuit_breaker
   breaker = get_circuit_breaker("service_name")
   print(f"Open: {breaker.is_open}")
   print(f"Failures: {breaker.failure_count}")
   ```

---

## Configuration

All retry and error handling is configurable via `config.yaml`:

```yaml
retry:
  max_attempts: 3
  min_wait_seconds: 1.0
  max_wait_seconds: 60.0

circuit_breaker:
  failure_threshold: 5
  cooldown_seconds: 300
```

Or via environment variables:
```bash
export AUTO_GIT_MAX_RETRIES=5
export AUTO_GIT_TIMEOUT=120
```

---

For more information, see:
- [Troubleshooting Guide](TROUBLESHOOTING.md)
- [Configuration Reference](CONFIGURATION.md)
- [Metrics Guide](METRICS.md)
