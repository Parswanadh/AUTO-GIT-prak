"""
Metrics collection and reporting for AUTO-GIT pipeline.

Features:
- Runtime metrics collection (timing, tokens, success rates)
- Per-paper and aggregate metrics
- Health check functionality
- Daily summary reports
- Performance trend tracking
"""

import json
import time
from collections import defaultdict
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Callable
from contextlib import contextmanager
from functools import wraps

from src.utils.logger import get_logger

logger = get_logger("metrics")


class MetricType(Enum):
    """Types of metrics."""
    COUNTER = "counter"  # Incrementing value (e.g., requests made)
    GAUGE = "gauge"  # Current value (e.g., memory usage)
    HISTOGRAM = "histogram"  # Distribution (e.g., timing)
    TIMER = "timer"  # Duration measurement


@dataclass
class MetricValue:
    """A single metric measurement."""
    name: str
    value: float
    timestamp: float
    labels: dict[str, str] = field(default_factory=dict)
    metric_type: MetricType = MetricType.GAUGE

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class PaperMetrics:
    """
    Metrics collected for a single paper processing run.

    Attributes:
        paper_id: Paper identifier
        start_time: Processing start timestamp
        end_time: Processing end timestamp
        total_duration_ms: Total processing duration
        success: Whether processing succeeded
        stage_durations: Duration per pipeline stage
        llm_tokens_used: Total LLM tokens consumed
        llm_calls: Number of LLM calls made
        retry_attempts: Number of retry attempts
        validation_score: Code validation score
        error_type: Type of error if failed
        error_message: Error message if failed
    """
    paper_id: str
    start_time: float
    end_time: Optional[float] = None
    total_duration_ms: Optional[float] = None
    success: bool = False
    stage_durations: dict[str, float] = field(default_factory=dict)
    llm_tokens_used: int = 0
    llm_calls: int = 0
    retry_attempts: int = 0
    validation_score: Optional[float] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    def mark_completed(self, success: bool = True):
        """Mark paper as completed."""
        self.end_time = time.time()
        self.total_duration_ms = (self.end_time - self.start_time) * 1000
        self.success = success


@dataclass
class AggregateMetrics:
    """
    Aggregate metrics across multiple paper runs.

    Attributes:
        start_date: Start of collection period
        end_date: End of collection period
        papers_processed: Total papers processed
        papers_completed: Papers completed successfully
        papers_failed: Papers that failed
        total_duration_ms: Total processing time
        avg_duration_per_paper_ms: Average duration per paper
        success_rate: Success rate percentage
        bottleneck_stage: Slowest stage on average
        most_common_errors: Most frequent error types
    """
    start_date: str
    end_date: str
    papers_processed: int = 0
    papers_completed: int = 0
    papers_failed: int = 0
    total_duration_ms: float = 0
    avg_duration_per_paper_ms: float = 0
    success_rate: float = 0
    bottleneck_stage: Optional[str] = None
    most_common_errors: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class MetricsCollector:
    """
    Collects and manages metrics for the pipeline.

    Provides:
    - Per-paper metrics tracking
    - Aggregate metrics calculation
    - Metric persistence to JSONL
    - Health monitoring
    """

    def __init__(
        self,
        metrics_dir: str = "./data/metrics",
        aggregate_window_hours: int = 24,
    ):
        """
        Initialize metrics collector.

        Args:
            metrics_dir: Directory to store metrics
            aggregate_window_hours: Window for aggregate metrics
        """
        self.metrics_dir = Path(metrics_dir)
        self.metrics_dir.mkdir(parents=True, exist_ok=True)

        self.metrics_file = self.metrics_dir / "metrics.jsonl"
        self.papers_file = self.metrics_dir / "papers.jsonl"

        self.aggregate_window_hours = aggregate_window_hours

        # Current paper metrics
        self._current_paper: Optional[PaperMetrics] = None

        # In-memory counters
        self._counters: defaultdict[str, int] = defaultdict(int)
        self._gauges: defaultdict[str, float] = defaultdict(float)
        self._histograms: defaultdict[str, list[float]] = defaultdict(list)

    def start_paper(self, paper_id: str) -> PaperMetrics:
        """
        Start tracking metrics for a paper.

        Args:
            paper_id: Paper identifier

        Returns:
            PaperMetrics instance for tracking
        """
        self._current_paper = PaperMetrics(
            paper_id=paper_id,
            start_time=time.time(),
        )
        self._counters["papers_started"] += 1
        return self._current_paper

    def record_stage_duration(self, stage: str, duration_ms: float):
        """
        Record duration of a pipeline stage.

        Args:
            stage: Stage name
            duration_ms: Duration in milliseconds
        """
        if self._current_paper:
            self._current_paper.stage_durations[stage] = duration_ms

        self._histograms[f"stage_{stage}_duration_ms"].append(duration_ms)

    def record_llm_call(self, tokens_used: int):
        """
        Record an LLM call.

        Args:
            tokens_used: Number of tokens consumed
        """
        if self._current_paper:
            self._current_paper.llm_calls += 1
            self._current_paper.llm_tokens_used += tokens_used

        self._counters["llm_calls"] += 1
        self._counters["llm_tokens_used"] += tokens_used

    def record_retry_attempt(self):
        """Record a retry attempt."""
        if self._current_paper:
            self._current_paper.retry_attempts += 1
        self._counters["retry_attempts"] += 1

    def record_validation_score(self, score: float):
        """
        Record validation score.

        Args:
            score: Validation score (0-10)
        """
        if self._current_paper:
            self._current_paper.validation_score = score
        self._histograms["validation_score"].append(score)

    def record_failure(self, error_type: str, error_message: str):
        """
        Record a failure.

        Args:
            error_type: Type of error
            error_message: Error message
        """
        if self._current_paper:
            self._current_paper.error_type = error_type
            self._current_paper.error_message = error_message

        self._counters["failures"] += 1
        self._counters[f"failure_{error_type}"] += 1

    def complete_paper(self, success: bool = True):
        """
        Complete tracking for current paper.

        Args:
            success: Whether processing succeeded
        """
        if not self._current_paper:
            return

        self._current_paper.mark_completed(success)

        # Save to file
        self._save_paper_metrics(self._current_paper)

        # Update counters
        if success:
            self._counters["papers_completed"] += 1
        else:
            self._counters["papers_failed"] += 1

        self._current_paper = None

    def _save_paper_metrics(self, metrics: PaperMetrics):
        """Save paper metrics to file."""
        try:
            with open(self.papers_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(metrics.to_dict()) + "\n")
        except Exception as e:
            logger.error(f"Failed to save paper metrics: {e}")

    def get_paper_metrics(self, paper_id: str) -> Optional[PaperMetrics]:
        """
        Retrieve metrics for a specific paper.

        Args:
            paper_id: Paper identifier

        Returns:
            PaperMetrics if found, None otherwise
        """
        if not self.papers_file.exists():
            return None

        try:
            with open(self.papers_file, "r", encoding="utf-8") as f:
                for line in f:
                    data = json.loads(line.strip())
                    if data.get("paper_id") == paper_id:
                        return PaperMetrics(**data)
        except (json.JSONDecodeError, IOError):
            pass

        return None

    def get_aggregate_metrics(
        self,
        hours: Optional[int] = None,
    ) -> AggregateMetrics:
        """
        Calculate aggregate metrics over time window.

        Args:
            hours: Time window in hours (default: from config)

        Returns:
            AggregateMetrics instance
        """
        hours = hours or self.aggregate_window_hours
        cutoff_time = time.time() - (hours * 3600)

        papers = []
        stage_durations: defaultdict[str, list[float]] = defaultdict(list)
        errors: defaultdict[str, int] = defaultdict(int)

        if self.papers_file.exists():
            with open(self.papers_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        if data.get("start_time", 0) >= cutoff_time:
                            papers.append(data)

                            # Collect stage durations
                            for stage, duration in data.get("stage_durations", {}).items():
                                stage_durations[stage].append(duration)

                            # Collect errors
                            if error_type := data.get("error_type"):
                                errors[error_type] += 1
                    except (json.JSONDecodeError, ValueError):
                        continue

        # Calculate statistics
        total_papers = len(papers)
        completed = sum(1 for p in papers if p.get("success", False))
        failed = total_papers - completed
        total_duration = sum(p.get("total_duration_ms", 0) for p in papers)

        # Find bottleneck stage
        bottleneck = None
        max_avg_duration = 0
        for stage, durations in stage_durations.items():
            avg_duration = sum(durations) / len(durations)
            if avg_duration > max_avg_duration:
                max_avg_duration = avg_duration
                bottleneck = stage

        return AggregateMetrics(
            start_date=datetime.fromtimestamp(cutoff_time).isoformat(),
            end_date=datetime.now().isoformat(),
            papers_processed=total_papers,
            papers_completed=completed,
            papers_failed=failed,
            total_duration_ms=total_duration,
            avg_duration_per_paper_ms=total_duration / max(total_papers, 1),
            success_rate=(completed / max(total_papers, 1)) * 100,
            bottleneck_stage=bottleneck,
            most_common_errors=dict(sorted(errors.items(), key=lambda x: x[1], reverse=True)[:5]),
        )

    def get_current_paper_metrics(self) -> Optional[PaperMetrics]:
        """Get metrics for currently processing paper."""
        return self._current_paper

    def get_counter(self, name: str) -> int:
        """Get counter value."""
        return self._counters.get(name, 0)

    def get_gauge(self, name: str) -> float:
        """Get gauge value."""
        return self._gauges.get(name, 0.0)

    def increment_counter(self, name: str, value: int = 1):
        """Increment counter."""
        self._counters[name] += value

    def set_gauge(self, name: str, value: float):
        """Set gauge value."""
        self._gauges[name] = value

    @contextmanager
    def track_operation(self, operation_name: str):
        """
        Context manager for tracking operation duration.

        Usage:
            with metrics_collector.track_operation("llm_generation"):
                result = await generate()
        """
        start_time = time.time()
        operation_start = time.time()

        try:
            yield
        finally:
            duration_ms = (time.time() - operation_start) * 1000
            self._histograms[f"operation_{operation_name}_duration_ms"].append(duration_ms)
            logger.debug(f"Operation {operation_name} took {duration_ms:.1f}ms")

    @contextmanager
    def track_stage(self, stage_name: str):
        """
        Context manager for tracking pipeline stage duration.

        Usage:
            with metrics_collector.track_stage("extracting"):
                # Do extraction
                ...
        """
        start_time = time.time()

        try:
            yield
        finally:
            duration_ms = (time.time() - start_time) * 1000
            self.record_stage_duration(stage_name, duration_ms)
            logger.debug(f"Stage {stage_name} took {duration_ms:.1f}ms")


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get global metrics collector instance."""
    global _metrics_collector

    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()

    return _metrics_collector


def track_operation(operation_name: str):
    """
    Decorator for tracking function execution time.

    Usage:
        @track_operation("persona_generation")
        async def generate_personas(domain: str):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            mc = get_metrics_collector()
            start_time = time.time()

            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                mc._histograms[f"operation_{operation_name}_duration_ms"].append(duration_ms)
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                mc._histograms[f"operation_{operation_name}_duration_ms"].append(duration_ms)
                mc.record_failure(type(e).__name__, str(e)[:200])
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            mc = get_metrics_collector()
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                mc._histograms[f"operation_{operation_name}_duration_ms"].append(duration_ms)
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                mc._histograms[f"operation_{operation_name}_duration_ms"].append(duration_ms)
                mc.record_failure(type(e).__name__, str(e)[:200])
                raise

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


async def health_check() -> dict[str, Any]:
    """
    Perform system health check.

    Checks:
    - Ollama connectivity
    - GitHub token validity
    - Disk space availability
    - ChromaDB accessibility

    Returns:
        Dictionary with health status for each component
    """
    health = {
        "timestamp": datetime.now().isoformat(),
        "status": "healthy",
        "checks": {},
    }

    # Check Ollama
    try:
        from src.utils.ollama_client import test_ollama_connection
        ollama_healthy = await test_ollama_connection()
        health["checks"]["ollama"] = {
            "status": "healthy" if ollama_healthy else "unhealthy",
            "message": "Connected" if ollama_healthy else "Failed to connect",
        }
        if not ollama_healthy:
            health["status"] = "degraded"
    except Exception as e:
        health["checks"]["ollama"] = {
            "status": "unhealthy",
            "message": str(e),
        }
        health["status"] = "degraded"

    # Check GitHub token
    try:
        import os
        github_token = os.getenv("GITHUB_TOKEN")
        if github_token:
            health["checks"]["github"] = {
                "status": "healthy",
                "message": "Token configured",
            }
        else:
            health["checks"]["github"] = {
                "status": "warning",
                "message": "No GITHUB_TOKEN configured",
            }
            health["status"] = "degraded"
    except Exception as e:
        health["checks"]["github"] = {
            "status": "unhealthy",
            "message": str(e),
        }
        health["status"] = "degraded"

    # Check disk space
    try:
        import shutil
        disk_usage = shutil.disk_usage(".")
        free_gb = disk_usage.free / (1024 ** 3)
        total_gb = disk_usage.total / (1024 ** 3)
        free_percent = (disk_usage.free / disk_usage.total) * 100

        if free_percent < 5:
            health["checks"]["disk"] = {
                "status": "critical",
                "message": f"Only {free_gb:.1f}GB free ({free_percent:.1f}%)",
            }
            health["status"] = "critical"
        elif free_percent < 10:
            health["checks"]["disk"] = {
                "status": "warning",
                "message": f"{free_gb:.1f}GB free ({free_percent:.1f}%)",
            }
            if health["status"] == "healthy":
                health["status"] = "degraded"
        else:
            health["checks"]["disk"] = {
                "status": "healthy",
                "message": f"{free_gb:.1f}GB free ({free_percent:.1f}%)",
            }
    except Exception as e:
        health["checks"]["disk"] = {
            "status": "unknown",
            "message": str(e),
        }

    # Check ChromaDB
    try:
        import chromadb
        client = chromadb.PersistentClient(path="./data/vector_db")
        health["checks"]["chromadb"] = {
            "status": "healthy",
            "message": "Accessible",
        }
    except Exception as e:
        health["checks"]["chromadb"] = {
            "status": "unhealthy",
            "message": str(e),
        }
        if health["status"] == "healthy":
            health["status"] = "degraded"

    return health


def generate_daily_summary(
    metrics_dir: str = "./data/metrics",
    output_dir: Optional[str] = None,
) -> dict[str, Any]:
    """
    Generate daily summary report from metrics.

    Args:
        metrics_dir: Directory containing metrics
        output_dir: Optional directory to save reports

    Returns:
        Dictionary with summary statistics
    """
    mc = MetricsCollector(metrics_dir=metrics_dir)
    aggregate = mc.get_aggregate_metrics(hours=24)

    output_path = Path(output_dir or metrics_dir / "reports")
    output_path.mkdir(parents=True, exist_ok=True)

    # Save JSON summary
    summary_file = output_path / f"metrics_summary_{datetime.now().strftime('%Y%m%d')}.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(aggregate.to_dict(), f, indent=2)

    # Generate markdown report
    lines = [
        f"# AUTO-GIT Metrics Summary - {datetime.now().strftime('%Y-%m-%d')}",
        "",
        "## Overview",
        f"- Papers Processed: {aggregate.papers_processed}",
        f"- Success Rate: {aggregate.success_rate:.1f}% ({aggregate.papers_completed}/{aggregate.papers_processed})",
        f"- Failures: {aggregate.papers_failed}",
        f"- Total Time: {aggregate.total_duration_ms / 3600000:.1f}h",
        f"- Avg Time/Paper: {aggregate.avg_duration_per_paper_ms / 60000:.1f}m",
        "",
    ]

    if aggregate.bottleneck_stage:
        lines.extend([
            f"## Performance",
            f"- Bottleneck Stage: **{aggregate.bottleneck_stage}**",
            "",
        ])

    if aggregate.most_common_errors:
        lines.extend([
            "## Top Errors",
            "",
        ])
        for error_type, count in list(aggregate.most_common_errors.items())[:5]:
            lines.append(f"- **{error_type}**: {count} occurrences")
        lines.append("")

    report = "\n".join(lines)

    summary_md_file = output_path / f"metrics_summary_{datetime.now().strftime('%Y%m%d')}.md"
    with open(summary_md_file, "w", encoding="utf-8") as f:
        f.write(report)

    return aggregate.to_dict()
