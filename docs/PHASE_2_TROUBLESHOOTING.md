# AUTO-GIT Phase 2: Troubleshooting Guide

**Version**: 2.0
**Date**: January 6, 2026

---

## Table of Contents

1. [Quick Diagnosis](#quick-diagnosis)
2. [Common Issues](#common-issues)
3. [Debug Mode](#debug-mode)
4. [Log Analysis](#log-analysis)
5. [Recovery Procedures](#recovery-procedures)
6. [Performance Issues](#performance-issues)

---

## Quick Diagnosis

### Health Check

Run the health check script to identify issues:

```bash
python -m src.utils.health_check
```

Output:
```json
{
  "timestamp": "2026-01-06T14:32:11Z",
  "status": "healthy",
  "checks": {
    "ollama": {"status": "healthy", "message": "Connected"},
    "github": {"status": "healthy", "message": "Token configured"},
    "disk": {"status": "warning", "message": "15GB free (15%)"},
    "chromadb": {"status": "healthy", "message": "Accessible"}
  }
}
```

### Status Commands

```bash
# Check recent errors
tail -n 50 ./logs/structured/errors.jsonl | jq .

# View metrics summary
cat ./data/metrics/reports/metrics_summary_*.json | jq .

# Check cache statistics
python -c "from src.utils.cache import get_all_cache_stats; import json; print(json.dumps(get_all_cache_stats(), indent=2))"
```

---

## Common Issues

### Issue: Ollama Connection Failed

**Symptoms**:
```
OllamaConnectionError: Failed to connect to Ollama server
```

**Diagnosis**:
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Check Ollama logs
ollama logs
```

**Solutions**:
1. Start Ollama: `ollama serve`
2. Verify model is downloaded: `ollama list`
3. Download model if needed: `ollama pull qwen3:8b`
4. Check firewall settings

**Prevention**:
- Add Ollama to system startup
- Use `@with_retry` decorator for all Ollama calls
- Configure health check pings

---

### Issue: GitHub Rate Limit

**Symptoms**:
```
RateLimitError: GitHub API rate limit exceeded
```

**Diagnosis**:
```bash
# Check rate limit status
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/rate_limit
```

**Solutions**:
1. Wait for rate limit reset (typically 1 hour)
2. Use authenticated requests (increases limit to 5000/hr)
3. Enable caching to reduce API calls
4. Batch operations where possible

**Prevention**:
```yaml
# config.yaml
github:
  rate_limit_pause: true
  token: your_github_token_here

cache:
  enabled: true
  paper_ttl_seconds: 86400  # Cache for 24 hours
```

---

### Issue: Persona Generation JSON Parse Error

**Symptoms**:
```
ParsingError: Expecting value: line 1 column 1 (json)
```

**Diagnosis**:
```bash
# Check persona generation logs
grep "persona_generation" ./logs/structured/*.jsonl | jq 'select(.error_type == "JSONDecodeError")'
```

**Solutions**:
1. LLM generated invalid JSON → retry with modified prompt
2. Fallback to cached personas
3. Fallback to base 3 personas

**Prevention**:
```python
# System automatically retries with fallback
from src.utils.fallback import get_personas_with_fallback

personas = await get_personas_with_fallback(domain="ml")
# Automatically tries: dynamic → cache → hardcoded → base
```

---

### Issue: Disk Space Exhausted

**Symptoms**:
```
ResourceExhaustedError: No space left on device
```

**Diagnosis**:
```bash
# Check disk usage
df -h

# Find large files
du -sh ./data/* | sort -rh | head -20
```

**Solutions**:
1. Clean old logs: `rm ./logs/pipeline_*.log`
2. Clear cache: `python -c "from src.utils.cache import clear_all_caches; clear_all_caches()"`
3. Archive old papers: `mv ./output/old_papers /archive/`
4. Clean vector DB: Remove old embeddings

**Prevention**:
```yaml
# config.yaml
cache:
  max_memory_mb: 100

# Enable automatic cleanup
metrics:
  cleanup_old_data: true
  retention_days: 30
```

---

### Issue: Circuit Breaker Open

**Symptoms**:
```
CircuitBreakerOpen: Circuit breaker open for arxiv_api after 5 failures
```

**Diagnosis**:
```python
from src.utils.retry import get_circuit_breaker

breaker = get_circuit_breaker("arxiv_api")
print(f"Failures: {breaker.failure_count}")
print(f"Open: {breaker.is_open}")
```

**Solutions**:
1. Wait for cooldown period (default 5 minutes)
2. Fix underlying service issue
3. Manually reset circuit breaker:
   ```python
   breaker.is_open = False
   breaker.failure_count = 0
   ```

**Prevention**:
```yaml
# config.yaml
circuit_breaker:
  failure_threshold: 10  # Increase threshold
  cooldown_seconds: 600  # Longer cooldown
```

---

### Issue: Validation Score Too Low

**Symptoms**:
```
ValidationError: Code validation score 5.2 below threshold 8.0
```

**Diagnosis**:
```bash
# View validation report
cat ./output/<paper>/validation_report.md
```

**Solutions**:
1. Review specific validation issues
2. Adjust threshold if too strict
3. Fix common issues (imports, type hints)

**Prevention**:
```yaml
# config.yaml
validation:
  min_score: 7.0  # Lower threshold
  enable_syntax_check: true
  enable_type_check: false  # Disable if too strict
```

---

## Debug Mode

### Enable Debug Logging

```bash
# Via environment variable
export AUTO_GIT_LOG_LEVEL=DEBUG
python run.py

# Via config.yaml
logging:
  level: DEBUG
```

### Enable Trace Logging

```python
import logging
logging.getLogger("auto_git").setLevel(logging.TRACE)
```

### Run with Verbose Output

```bash
python run.py --verbose --debug --trace
```

---

## Log Analysis

### Structured Log Query

```bash
# All errors in last hour
jq 'select(.level == "ERROR" and .timestamp > "2026-01-06T13:00:00Z")' \
  ./logs/structured/errors.jsonl

# Errors by stage
jq 'group_by(.stage) | map({stage: .[0].stage, count: length})' \
  ./logs/structured/errors.jsonl

# Slowest operations
jq 'select(.duration_ms > 10000) | {operation: .agent, duration: .duration_ms}' \
  ./logs/structured/*.jsonl | sort -rn -k2
```

### Performance Analysis

```python
from src.utils.structured_logging import generate_summary_report

# Generate daily summary
summary = generate_summary_report(
    log_dir="./logs/structured",
    output_dir="./logs/reports"
)
print(summary)
```

### Error Patterns

```python
from src.utils.structured_logging import ErrorAggregator

aggregator = ErrorAggregator("./logs/structured")
analysis = aggregator.analyze_errors(limit=100)

print("Top errors:")
for error_type, count in analysis["errors_by_type"].items():
    print(f"  {error_type}: {count}")
```

---

## Recovery Procedures

### Resume from Checkpoint

```bash
# Pipeline automatically resumes from last checkpoint
python run.py --resume

# Or specify checkpoint file
python run.py --checkpoint ./data/checkpoints/checkpoint_20260106_143211.json
```

### Retry Failed Papers

```bash
# Retry only failed papers
python run.py --filter failed

# Retry specific paper
python run.py --paper 2401.12345
```

### Clear Cache and Restart

```bash
# Clear all caches
python -c "from src.utils.cache import clear_all_caches; clear_all_caches()"

# Clear specific cache
python -c "from src.utils.cache import get_paper_cache; get_paper_cache().clear()"

# Restart pipeline
python run.py
```

### Reset Circuit Breakers

```python
from src.utils.retry import _circuit_breakers

for breaker in _circuit_breakers.values():
    breaker.is_open = False
    breaker.failure_count = 0
    print(f"Reset {breaker.service_name}")
```

---

## Performance Issues

### Pipeline Running Slowly

**Diagnosis**:
```python
from src.utils.metrics import get_metrics_collector

mc = get_metrics_collector()
aggregate = mc.get_aggregate_metrics(hours=24)

print("Bottleneck stage:", aggregate.bottleneck_stage)
print("Stage durations:", aggregate.stage_durations)
```

**Common Bottlenecks**:

1. **LLM Generation** (expected: 1-2 min per call)
   - Solution: Use smaller model for simple tasks
   - Enable caching for repeated prompts

2. **Critique Generation** (5 personas sequential)
   - Solution: Enable parallel critiques
   - Reduce number of personas

3. **Code Validation** (mypy, pylint slow)
   - Solution: Disable some validation layers
   - Run validation asynchronously

### Optimization Tips

```yaml
# config.yaml
parallel:
  max_concurrent_critiques: 5  # Run critiques in parallel

cache:
  enabled: true  # Enable all caches

validation:
  enable_type_check: false  # Disable slow checks
  enable_quality_check: false
```

### Memory Issues

**Symptoms**:
```
MemoryError: Unable to allocate memory
```

**Solutions**:
1. Reduce batch size: `max_papers_per_batch: 10`
2. Clear cache periodically
3. Use smaller LLM models
4. Increase system swap

---

## Getting Help

### Collect Diagnostic Information

```bash
# Create diagnostic bundle
python -m src.utils.diagnostics --output ./diagnostics.zip

# Includes:
# - Config file
# - Recent logs
# - Metrics summary
# - Error report
# - Health check
```

### Log an Issue

When reporting issues, include:
1. Diagnostic bundle
2. Full error message
3. Steps to reproduce
4. System information (OS, Python version)
5. Configuration file

---

## Prevention Checklist

- [ ] Configure GITHUB_TOKEN
- [ ] Enable all caches
- [ ] Set appropriate retry limits
- [ ] Configure circuit breaker thresholds
- [ ] Enable structured logging
- [ ] Set up log rotation
- [ ] Configure validation thresholds
- [ ] Test with small batch first
- [ ] Monitor disk space
- [ ] Set up alerts for critical errors

---

For more information:
- [Error Handling Guide](PHASE_2_ERROR_HANDLING_GUIDE.md)
- [Configuration Reference](PHASE_2_CONFIGURATION.md)
- [Metrics Guide](PHASE_2_METRICS.md)
