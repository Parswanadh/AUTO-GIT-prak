# AUTO-GIT Phase 2: Configuration Reference

**Version**: 2.0
**Date**: January 6, 2026

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Configuration File](#configuration-file)
3. [Environment Variables](#environment-variables)
4. [Options Reference](#options-reference)
5. [Examples](#examples)

---

## Quick Start

### Create Default Config

```bash
python -m src.utils.config_manager
```

This creates `config.yaml` with all default values.

### Load Config in Code

```python
from src.utils.config_manager import get_config

config = get_config()

# Access configuration
print(config.retry.max_attempts)  # 3
print(config.logging.level)  # INFO
print(config.validation.min_score)  # 8.0
```

---

## Configuration File

### Default Location

- **File**: `./config.yaml`
- **Environment Variable**: `AUTO_GIT_CONFIG`

```bash
export AUTO_GIT_CONFIG=/path/to/custom/config.yaml
```

### File Structure

```yaml
# LLM Settings
llm_provider: ollama
execution_mode: local

# Retry Configuration
retry:
  max_attempts: 3
  min_wait_seconds: 1.0
  max_wait_seconds: 60.0

# Circuit Breaker Configuration
circuit_breaker:
  failure_threshold: 5
  cooldown_seconds: 300

# ... (see full reference below)
```

---

## Environment Variables

Environment variables override config file values.

### Priority

1. Environment variable (highest)
2. Config file
3. Default value (lowest)

### Available Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `AUTO_GIT_CONFIG` | Path to config file | `/etc/auto-git/config.yaml` |
| `AUTO_GIT_LLM_PROVIDER` | LLM provider | `ollama`, `claude` |
| `AUTO_GIT_EXECUTION_MODE` | Execution mode | `local`, `cloud` |
| `AUTO_GIT_MAX_RETRIES` | Max retry attempts | `5` |
| `AUTO_GIT_TIMEOUT` | Max wait time (seconds) | `120` |
| `AUTO_GIT_LOG_LEVEL` | Logging level | `DEBUG` |
| `AUTO_GIT_LOG_DIR` | Log directory | `./logs` |
| `AUTO_GIT_CACHE_ENABLED` | Enable caching | `true`, `false` |
| `AUTO_GIT_METRICS_ENABLED` | Enable metrics | `true`, `false` |
| `AUTO_GIT_VALIDATION_ENABLED` | Enable validation | `true`, `false` |
| `AUTO_GIT_GITHUB_TOKEN` | GitHub API token | `ghp_xxxx` |
| `AUTO_GIT_MAX_PARALLEL` | Max parallel critiques | `5` |

### Example Usage

```bash
export AUTO_GIT_LOG_LEVEL=DEBUG
export AUTO_GIT_MAX_RETRIES=5
export AUTO_GIT_GITHUB_TOKEN=ghp_xxxxxxxxxxxx
python run.py
```

---

## Options Reference

### LLM Settings

```yaml
# LLM provider: ollama, glm, claude, openai
llm_provider: ollama

# Execution mode: local, cloud, parallel, fallback
execution_mode: local

# Ollama-specific settings (if using Ollama)
ollama:
  base_url: http://localhost:11434
  timeout: 120
  default_model: qwen3:8b
  fallback_model: gemma2:2b
```

### Retry Configuration

```yaml
retry:
  # Maximum number of retry attempts
  max_attempts: 3

  # Minimum wait time between retries (seconds)
  min_wait_seconds: 1.0

  # Maximum wait time between retries (seconds)
  max_wait_seconds: 60.0

  # Exponential backoff base
  exponential_base: 2
```

**Behavior**:
- Attempt 1: Execute immediately
- Attempt 2: Wait 1 second (2^0 * 1.0)
- Attempt 3: Wait 2 seconds (2^1 * 1.0)
- Attempt 4: Wait 4 seconds (2^2 * 1.0)
- ...

### Circuit Breaker Configuration

```yaml
circuit_breaker:
  # Number of failures before opening circuit
  failure_threshold: 5

  # How long to keep circuit open (seconds)
  cooldown_seconds: 300
```

**Behavior**:
- After 5 consecutive failures, circuit opens
- All requests fail immediately while open
- After 5 minutes, one trial request allowed
- If trial succeeds, circuit closes

### Validation Configuration

```yaml
validation:
  # Enable/disable validation entirely
  enabled: true

  # Minimum score to pass (0-10)
  min_score: 8.0

  # Individual validation layers
  enable_syntax_check: true
  enable_type_check: true
  enable_security_scan: true
  enable_quality_check: true
  enable_import_validation: true

  # Tool-specific settings
  mypy_enabled: true
  pylint_enabled: true
  bandit_enabled: true
```

**Score Calculation**:
- Each layer contributes 0-10 points
- Final score = average of all enabled layers
- Below threshold = mark as "needs review"

### Cache Configuration

```yaml
cache:
  # Enable/disable caching
  enabled: true

  # TTL for different cache types (seconds)
  paper_ttl_seconds: 86400      # 24 hours
  problem_ttl_seconds: 604800    # 7 days
  persona_ttl_seconds: 2592000   # 30 days
  template_ttl_seconds: 2592000  # 30 days

  # Database path
  db_path: ./data/cache.db

  # In-memory cache limits
  max_memory_mb: 100
```

**What Gets Cached**:
- Paper metadata (arXiv API results)
- Extracted problems
- Generated personas
- Code templates

### Metrics Configuration

```yaml
metrics:
  # Enable/disable metrics collection
  enabled: true

  # Metrics storage directory
  metrics_dir: ./data/metrics

  # Aggregation window (hours)
  aggregate_window_hours: 24

  # What to track
  track_llm_tokens: true
  track_timing: true
  track_errors: true
  track_cache_hits: true
```

**Metrics Collected**:
- Per-paper metrics (duration, tokens, retries)
- Aggregate metrics (success rate, bottleneck stage)
- Stage timings
- Error frequencies

### Logging Configuration

```yaml
logging:
  # Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
  level: INFO

  # Log directory
  log_dir: ./logs

  # Enable structured JSON logging
  structured_logging: true

  # Enable per-paper log files
  per_paper_logs: true

  # Enable console output
  console_output: true
```

**Log Files**:
- `./logs/pipeline_YYYY-MM-DD.log` - Rich console logs
- `./logs/structured/paper_ID.jsonl` - Per-paper JSON logs
- `./logs/structured/errors.jsonl` - Error aggregation
- `./logs/structured/pipeline_YYYYMMDD.jsonl` - Daily logs

### Parallel Execution Configuration

```yaml
parallel:
  # Maximum concurrent critique generations
  max_concurrent_critiques: 5

  # Timeout per critique (seconds)
  critique_timeout_seconds: 120

  # Continue if one critique fails
  continue_on_error: true
```

**Behavior**:
- All 5 personas run concurrently
- If one times out/fails, others continue
- Results aggregated after all complete

### GitHub Configuration

```yaml
github:
  # GitHub API token (or set GITHUB_TOKEN env var)
  token: null

  # Default organization
  default_org: null

  # Pause when rate limit hit
  rate_limit_pause: true
```

**Getting a Token**:
1. Go to GitHub Settings → Developer settings → Personal access tokens
2. Generate new token (classic)
3. Select scopes: `repo`, `public_repo`
4. Set as `GITHUB_TOKEN` environment variable

### Pipeline Configuration

```yaml
# Maximum papers to process in one batch
max_papers_per_batch: 100

# Checkpoint save interval (seconds)
checkpoint_interval_seconds: 300

# Automatically publish to GitHub
enable_auto_publish: true
```

---

## Examples

### Minimal Config (Development)

```yaml
# Minimal development config
logging:
  level: DEBUG

validation:
  enabled: false  # Skip validation for speed

cache:
  enabled: true

retry:
  max_attempts: 2  # Faster failure
```

### Production Config

```yaml
# Production config
logging:
  level: INFO
  structured_logging: true
  per_paper_logs: true

validation:
  enabled: true
  min_score: 8.0
  enable_security_scan: true

cache:
  enabled: true
  paper_ttl_seconds: 86400

retry:
  max_attempts: 3
  max_wait_seconds: 60

circuit_breaker:
  failure_threshold: 5
  cooldown_seconds: 300

metrics:
  enabled: true
```

### High-Throughput Config

```yaml
# For processing many papers quickly
logging:
  level: WARNING  # Less logging

validation:
  enabled: true
  min_score: 6.0  # Lower threshold
  enable_type_check: false  # Skip slow checks
  enable_quality_check: false

parallel:
  max_concurrent_critiques: 10  # More parallelism

retry:
  max_attempts: 2  # Fewer retries
```

### Resource-Constrained Config

```yaml
# For systems with limited resources
cache:
  enabled: true
  max_memory_mb: 50  # Less memory

parallel:
  max_concurrent_critiques: 2  # Less parallelism

validation:
  enable_type_check: false
  enable_quality_check: false  # Skip CPU-intensive checks
```

---

## Validation

Config is validated on load. Common errors:

### Invalid Log Level

```
ConfigurationError: Invalid log level: VERBOSE
```

**Fix**: Use valid level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

### Invalid Retry Attempts

```
ConfigurationError: Invalid max_attempts: 0
```

**Fix**: Must be >= 1

### Invalid Validation Score

```
ConfigurationError: Invalid validation min_score: 15
```

**Fix**: Must be between 0 and 10

---

## Hot Reload

To reload config without restarting:

```python
from src.utils.config_manager import reload_config

config = reload_config()
```

Or restart with `--reload-config` flag:

```bash
python run.py --reload-config
```

---

For more information:
- [Error Handling Guide](PHASE_2_ERROR_HANDLING_GUIDE.md)
- [Troubleshooting](PHASE_2_TROUBLESHOOTING.md)
- [Metrics Guide](PHASE_2_METRICS.md)
