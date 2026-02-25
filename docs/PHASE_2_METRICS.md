# AUTO-GIT Phase 2: Metrics Guide

**Version**: 2.0
**Date**: January 6, 2026

---

## Table of Contents

1. [Overview](#overview)
2. [Metrics Collected](#metrics-collected)
3. [Accessing Metrics](#accessing-metrics)
4. [Dashboards](#dashboards)
5. [Performance Analysis](#performance-analysis)
6. [Custom Metrics](#custom-metrics)

---

## Overview

AUTO-GIT automatically collects metrics during pipeline execution:

- **Per-paper metrics**: Individual paper processing stats
- **Aggregate metrics**: Stats across multiple papers
- **Stage timings**: How long each pipeline stage takes
- **Error tracking**: Error frequencies and types
- **Resource usage**: Tokens, retries, cache hits

### Storage

Metrics are stored in:
- **File**: `./data/metrics/papers.jsonl` - Per-paper metrics
- **File**: `./data/metrics/metrics.jsonl` - Raw metric events
- **Reports**: `./data/metrics/reports/` - Daily summaries

---

## Metrics Collected

### Per-Paper Metrics

```python
@dataclass
class PaperMetrics:
    paper_id: str
    start_time: float
    end_time: Optional[float]
    total_duration_ms: Optional[float]
    success: bool
    stage_durations: dict[str, float]
    llm_tokens_used: int
    llm_calls: int
    retry_attempts: int
    validation_score: Optional[float]
    error_type: Optional[str]
    error_message: Optional[str]
```

### Example

```json
{
  "paper_id": "2401.12345",
  "start_time": 1704555231.123,
  "end_time": 1704555674.456,
  "total_duration_ms": 443333.0,
  "success": true,
  "stage_durations": {
    "discovering": 12000.0,
    "extracting": 65000.0,
    "generating_personas": 45000.0,
    "debating": 195000.0,
    "generating_code": 95000.0,
    "validating": 8000.0,
    "publishing": 13000.0
  },
  "llm_tokens_used": 145230,
  "llm_calls": 15,
  "retry_attempts": 2,
  "validation_score": 8.5,
  "error_type": null,
  "error_message": null
}
```

### Aggregate Metrics

```python
@dataclass
class AggregateMetrics:
    start_date: str
    end_date: str
    papers_processed: int
    papers_completed: int
    papers_failed: int
    total_duration_ms: float
    avg_duration_per_paper_ms: float
    success_rate: float
    bottleneck_stage: Optional[str]
    most_common_errors: dict[str, int]
```

---

## Accessing Metrics

### Programmatically

```python
from src.utils.metrics import get_metrics_collector

mc = get_metrics_collector()

# Get metrics for current paper
current = mc.get_current_paper_metrics()

# Get metrics for specific paper
paper = mc.get_paper_metrics("2401.12345")

# Get aggregate metrics (last 24 hours)
aggregate = mc.get_aggregate_metrics(hours=24)

print(f"Success rate: {aggregate.success_rate:.1f}%")
print(f"Bottleneck: {aggregate.bottleneck_stage}")
```

### Command Line

```bash
# Generate daily summary
python -m src.utils.metrics --summary

# View recent metrics
cat ./data/metrics/papers.jsonl | jq . | tail -20

# Calculate success rate
cat ./data/metrics/papers.jsonl | \
  jq '[.success] | add / length * 100'
```

### API Endpoints (Future)

```bash
# Get metrics for paper
curl http://localhost:8000/metrics/papers/2401.12345

# Get aggregate metrics
curl http://localhost:8000/metrics/aggregate?hours=24

# Health check
curl http://localhost:8000/health
```

---

## Dashboards

### Daily Summary Report

```bash
python -m src.utils.metrics --report
```

Generates `./data/metrics/reports/summary_YYYYMMDD.md`:

```markdown
# AUTO-GIT Metrics Summary - 2026-01-06

## Overview
- Papers Processed: 47
- Success Rate: 89.4% (42/47)
- Failures: 5
- Total Time: 6.5h
- Avg Time/Paper: 8.3m

## Performance
- Bottleneck Stage: debating (195s avg)

## Top Errors
- JSONDecodeError: 3 occurrences
- TimeoutError: 2 occurrences
```

### Real-Time Monitoring (Future)

```bash
# Start metrics server
python -m src.utils.metrics_server --port 8000

# View dashboard
open http://localhost:8000/dashboard
```

---

## Performance Analysis

### Identify Bottlenecks

```python
from src.utils.metrics import get_metrics_collector

mc = get_metrics_collector()
aggregate = mc.get_aggregate_metrics(hours=24)

print("Stage durations:")
for stage, stats in aggregate.stage_durations.items():
    print(f"  {stage}: {stats['avg_ms']/1000:.1f}s avg")

print(f"\nBottleneck: {aggregate.bottleneck_stage}")
```

### Analyze Errors

```python
from src.utils.structured_logging import ErrorAggregator

aggregator = ErrorAggregator("./logs/structured")
analysis = aggregator.analyze_errors(limit=100)

print("Errors by type:")
for error_type, count in analysis["errors_by_type"].items():
    print(f"  {error_type}: {count}")
```

### Track Success Rate Over Time

```python
import json
from collections import defaultdict

# Read all paper metrics
metrics_by_day = defaultdict(lambda: {"completed": 0, "failed": 0})

with open("./data/metrics/papers.jsonl") as f:
    for line in f:
        paper = json.loads(line)
        date = paper["start_time"].split("T")[0]
        if paper["success"]:
            metrics_by_day[date]["completed"] += 1
        else:
            metrics_by_day[date]["failed"] += 1

# Calculate success rate by day
for date, counts in sorted(metrics_by_day.items()):
    total = counts["completed"] + counts["failed"]
    rate = counts["completed"] / total * 100 if total > 0 else 0
    print(f"{date}: {rate:.1f}% ({counts['completed']}/{total})")
```

---

## Custom Metrics

### Track Custom Operation

```python
from src.utils.metrics import get_metrics_collector

mc = get_metrics_collector()

# Track custom operation
with mc.track_operation("my_custom_operation"):
    result = do_something()

# Or use decorator
from src.utils.metrics import track_operation

@track_operation("expensive_computation")
def compute_something(data):
    # This will be tracked automatically
    return expensive_function(data)
```

### Record Custom Metric

```python
# Increment counter
mc.increment_counter("custom_events", value=1)

# Set gauge
mc.set_gauge("queue_size", value=42)

# Record histogram value
mc._histograms["processing_time_ms"].append(1234.5)
```

### Track Stage Duration

```python
from src.utils.metrics import get_metrics_collector

mc = get_metrics_collector()

# Track stage
with mc.track_stage("custom_stage"):
    do_stage_work()
```

---

## Performance Tuning

### Optimize Based on Metrics

1. **Identify bottleneck stage**
   ```python
   aggregate = mc.get_aggregate_metrics()
   print(aggregate.bottleneck_stage)  # e.g., "debating"
   ```

2. **Check if caching helps**
   ```python
   # Cache hit rate
   cache_stats = get_all_cache_stats()
   print(cache_stats["paper_metadata"]["hit_rate"])
   # If low, increase TTL or enable more caching
   ```

3. **Reduce retry attempts for fast-fail**
   ```yaml
   # config.yaml
   retry:
     max_attempts: 2  # Was 3
   ```

4. **Enable parallel processing**
   ```yaml
   # config.yaml
   parallel:
     max_concurrent_critiques: 10  # Was 5
   ```

### Metrics-Based Alerts (Future)

```python
# Alert if success rate drops below 80%
aggregate = mc.get_aggregate_metrics(hours=1)
if aggregate.success_rate < 80:
    send_alert(f"Success rate dropped to {aggregate.success_rate}%")
```

---

## Metrics Reference

### Counters

- `papers_started` - Papers processed
- `papers_completed` - Papers succeeded
- `papers_failed` - Papers failed
- `llm_calls` - LLM API calls
- `llm_tokens_used` - Total tokens
- `retry_attempts` - Retry attempts
- `fallback_succeeded` - Fallbacks used
- `failures` - Total failures

### Gauges

- Current paper ID
- Current stage
- Memory usage
- Disk usage
- Queue size

### Histograms

- Stage durations (per stage)
- Operation durations (per operation)
- LLM call durations
- Retry wait times
- Validation scores

### Timers

- Total paper processing time
- Stage times
- Operation times
- LLM generation times

---

For more information:
- [Error Handling Guide](PHASE_2_ERROR_HANDLING_GUIDE.md)
- [Troubleshooting](PHASE_2_TROUBLESHOOTING.md)
- [Configuration Reference](PHASE_2_CONFIGURATION.md)
