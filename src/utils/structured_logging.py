"""
Structured JSON logging for AUTO-GIT pipeline.

Features:
- JSON format for machine-parseable logs
- Per-paper log separation
- Context tracking (paper_id, stage, agent, etc.)
- Performance metrics tracking
- Error aggregation and reporting
"""

import json
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Callable
from functools import wraps

from src.utils.logger import get_logger

logger = get_logger("structured_logging")


class LogLevel(Enum):
    """Log levels for structured logging."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class PipelineStage(Enum):
    """Pipeline stages for tracking."""
    QUEUED = "queued"
    DISCOVERING = "discovering"
    EXTRACTING = "extracting"
    GENERATING_PERSONAS = "generating_personas"
    DEBATING = "debating"
    GENERATING_CODE = "generating_code"
    VALIDATING = "validating"
    PUBLISHING = "publishing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class LogEntry:
    """
    Structured log entry with full context.

    Attributes:
        timestamp: ISO format timestamp
        level: Log level
        stage: Current pipeline stage
        paper_id: Paper identifier
        agent: Agent/function name
        message: Human-readable message
        duration_ms: Operation duration in milliseconds
        error_type: Type of error if applicable
        error_message: Error message if applicable
        retry_attempt: Retry attempt number if applicable
        will_retry: Whether operation will be retried
        extra: Additional context data
    """
    timestamp: str
    level: str
    stage: Optional[str] = None
    paper_id: Optional[str] = None
    agent: Optional[str] = None
    message: str = ""
    duration_ms: Optional[float] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    retry_attempt: Optional[int] = None
    will_retry: Optional[bool] = None
    extra: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False)


class StructuredLogger:
    """
    Structured JSON logger with context tracking.

    Maintains separate log files per paper and provides
    performance tracking and error aggregation.
    """

    def __init__(
        self,
        log_dir: str = "./logs/structured",
        paper_id: Optional[str] = None,
    ):
        """
        Initialize structured logger.

        Args:
            log_dir: Base directory for structured logs
            paper_id: Paper ID for per-paper logging
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.paper_id = paper_id
        self._current_stage = PipelineStage.QUEUED
        self._stage_start_time = None
        self._paper_start_time = None

        # Per-paper log file
        if paper_id:
            self.log_file = self.log_dir / f"paper_{paper_id}.jsonl"
        else:
            self.log_file = self.log_dir / f"pipeline_{datetime.now().strftime('%Y%m%d')}.jsonl"

        # Error log
        self.error_log = self.log_dir / "errors.jsonl"

    def _write_log(self, entry: LogEntry):
        """Write log entry to file."""
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(entry.to_json() + "\n")
        except Exception as e:
            logger.error(f"Failed to write structured log: {e}")

    def _write_error(self, entry: LogEntry):
        """Write error to error log."""
        try:
            with open(self.error_log, "a", encoding="utf-8") as f:
                f.write(entry.to_json() + "\n")
        except Exception as e:
            logger.error(f"Failed to write error log: {e}")

    def log(
        self,
        level: LogLevel,
        message: str,
        stage: Optional[PipelineStage] = None,
        agent: Optional[str] = None,
        paper_id: Optional[str] = None,
        duration_ms: Optional[float] = None,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        retry_attempt: Optional[int] = None,
        will_retry: Optional[bool] = None,
        extra: Optional[dict[str, Any]] = None,
    ):
        """
        Write a structured log entry.

        Args:
            level: Log level
            message: Human-readable message
            stage: Current pipeline stage
            agent: Agent/function name
            paper_id: Paper ID
            duration_ms: Operation duration
            error_type: Type of error
            error_message: Error message
            retry_attempt: Retry attempt number
            will_retry: Whether operation will be retried
            extra: Additional context
        """
        entry = LogEntry(
            timestamp=datetime.utcnow().isoformat() + "Z",
            level=level.value,
            stage=(stage or self._current_stage).value,
            paper_id=paper_id or self.paper_id,
            agent=agent,
            message=message,
            duration_ms=duration_ms,
            error_type=error_type,
            error_message=error_message,
            retry_attempt=retry_attempt,
            will_retry=will_retry,
            extra=extra,
        )

        self._write_log(entry)

        # Also write to error log if it's an error or critical
        if level in (LogLevel.ERROR, LogLevel.CRITICAL):
            self._write_error(entry)

    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self.log(LogLevel.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs):
        """Log info message."""
        self.log(LogLevel.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self.log(LogLevel.WARNING, message, **kwargs)

    def error(
        self,
        message: str,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        **kwargs
    ):
        """Log error message."""
        self.log(
            LogLevel.ERROR,
            message,
            error_type=error_type,
            error_message=error_message,
            **kwargs
        )

    def critical(self, message: str, **kwargs):
        """Log critical message."""
        self.log(LogLevel.CRITICAL, message, **kwargs)

    def set_stage(self, stage: PipelineStage):
        """Set current pipeline stage."""
        self._current_stage = stage
        self._stage_start_time = time.time()
        self.info(f"Entered stage: {stage.value}", stage=stage)

    def start_paper(self, paper_id: str):
        """Start processing a new paper."""
        self.paper_id = paper_id
        self._paper_start_time = time.time()
        self.info(f"Started processing paper: {paper_id}", paper_id=paper_id)

    def complete_paper(self, success: bool = True):
        """Mark paper as completed."""
        duration_ms = None
        if self._paper_start_time:
            duration_ms = (time.time() - self._paper_start_time) * 1000

        self.info(
            f"Completed processing paper: {self.paper_id}",
            stage=PipelineStage.COMPLETED if success else PipelineStage.FAILED,
            duration_ms=duration_ms,
        )

    @contextmanager
    def track_stage(self, stage: PipelineStage):
        """
        Context manager for tracking a pipeline stage.

        Usage:
            with structured_logger.track_stage(PipelineStage.EXTRACTING):
                # Do extraction work
                ...
        """
        start_time = time.time()
        self.set_stage(stage)

        try:
            yield
            duration_ms = (time.time() - start_time) * 1000
            self.info(
                f"Completed stage: {stage.value}",
                stage=stage,
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self.error(
                f"Failed stage: {stage.value}",
                stage=stage,
                error_type=type(e).__name__,
                error_message=str(e),
                duration_ms=duration_ms,
            )
            raise

    @contextmanager
    def track_operation(self, operation_name: str, **context):
        """
        Context manager for tracking an operation.

        Usage:
            with structured_logger.track_operation("llm_generation", agent="SolutionGenerator"):
                result = await generate_solution()
        """
        start_time = time.time()

        try:
            yield
            duration_ms = (time.time() - start_time) * 1000
            self.info(
                f"Completed operation: {operation_name}",
                agent=operation_name,
                duration_ms=duration_ms,
                extra=context,
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self.error(
                f"Failed operation: {operation_name}",
                agent=operation_name,
                error_type=type(e).__name__,
                error_message=str(e)[:500],
                duration_ms=duration_ms,
                extra=context,
            )
            raise


# Global structured logger instance
_structured_logger: Optional[StructuredLogger] = None


def get_structured_logger(paper_id: Optional[str] = None) -> StructuredLogger:
    """
    Get global structured logger instance.

    Args:
        paper_id: Paper ID for per-paper logging

    Returns:
        StructuredLogger instance
    """
    global _structured_logger

    if _structured_logger is None or (paper_id and _structured_logger.paper_id != paper_id):
        _structured_logger = StructuredLogger(paper_id=paper_id)

    return _structured_logger


def track_operation(operation_name: str, **context):
    """
    Decorator for tracking function execution.

    Usage:
        @track_operation("persona_generation", stage=PipelineStage.GENERATING_PERSONAS)
        async def generate_personas(domain: str):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            slog = get_structured_logger()
            start_time = time.time()

            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                slog.info(
                    f"✅ {operation_name} completed",
                    agent=operation_name,
                    duration_ms=duration_ms,
                    extra=context,
                )
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                slog.error(
                    f"❌ {operation_name} failed",
                    agent=operation_name,
                    error_type=type(e).__name__,
                    error_message=str(e)[:500],
                    duration_ms=duration_ms,
                    extra=context,
                )
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            slog = get_structured_logger()
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                slog.info(
                    f"✅ {operation_name} completed",
                    agent=operation_name,
                    duration_ms=duration_ms,
                    extra=context,
                )
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                slog.error(
                    f"❌ {operation_name} failed",
                    agent=operation_name,
                    error_type=type(e).__name__,
                    error_message=str(e)[:500],
                    duration_ms=duration_ms,
                    extra=context,
                )
                raise

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


class ErrorAggregator:
    """
    Aggregates errors for analysis and reporting.

    Tracks error frequencies, patterns, and provides summaries.
    """

    def __init__(self, log_dir: str = "./logs/structured"):
        """
        Initialize error aggregator.

        Args:
            log_dir: Directory containing structured logs
        """
        self.log_dir = Path(log_dir)
        self.error_log = self.log_dir / "errors.jsonl"

    def analyze_errors(self, limit: int = 100) -> dict[str, Any]:
        """
        Analyze recent errors and generate summary.

        Args:
            limit: Maximum number of errors to analyze

        Returns:
            Dictionary with error statistics
        """
        if not self.error_log.exists():
            return {"total_errors": 0}

        errors_by_type: dict[str, int] = {}
        errors_by_stage: dict[str, int] = {}
        errors_by_paper: dict[str, int] = {}
        recent_errors = []

        with open(self.error_log, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= limit:
                    break

                try:
                    entry = json.loads(line.strip())
                    error_type = entry.get("error_type", "Unknown")
                    stage = entry.get("stage", "unknown")
                    paper_id = entry.get("paper_id", "unknown")

                    errors_by_type[error_type] = errors_by_type.get(error_type, 0) + 1
                    errors_by_stage[stage] = errors_by_stage.get(stage, 0) + 1
                    errors_by_paper[paper_id] = errors_by_paper.get(paper_id, 0) + 1

                    recent_errors.append(entry)
                except json.JSONDecodeError:
                    continue

        return {
            "total_errors": len(recent_errors),
            "errors_by_type": dict(sorted(
                errors_by_type.items(),
                key=lambda x: x[1],
                reverse=True
            )),
            "errors_by_stage": dict(sorted(
                errors_by_stage.items(),
                key=lambda x: x[1],
                reverse=True
            )),
            "papers_with_most_errors": dict(sorted(
                errors_by_paper.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]),
            "recent_errors": recent_errors[-10:],
        }

    def generate_report(self, output_path: Optional[str] = None) -> str:
        """
        Generate human-readable error report.

        Args:
            output_path: Optional file path to save report

        Returns:
            Markdown report as string
        """
        analysis = self.analyze_errors()

        lines = [
            "# Error Report",
            f"Generated: {datetime.now().isoformat()}",
            "",
            f"## Overview",
            f"- Total Errors: {analysis['total_errors']}",
            "",
        ]

        if analysis.get("errors_by_type"):
            lines.extend([
                "## Top Error Types",
                "",
            ])
            for error_type, count in list(analysis["errors_by_type"].items())[:10]:
                lines.append(f"- **{error_type}**: {count} occurrences")
            lines.append("")

        if analysis.get("errors_by_stage"):
            lines.extend([
                "## Errors by Pipeline Stage",
                "",
            ])
            for stage, count in list(analysis["errors_by_stage"].items())[:10]:
                lines.append(f"- **{stage}**: {count} errors")
            lines.append("")

        if analysis.get("papers_with_most_errors"):
            lines.extend([
                "## Papers with Most Errors",
                "",
            ])
            for paper_id, count in analysis["papers_with_most_errors"].items():
                lines.append(f"- **{paper_id}**: {count} errors")
            lines.append("")

        report = "\n".join(lines)

        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(report)

        return report


def generate_summary_report(
    log_dir: str = "./logs/structured",
    output_dir: Optional[str] = None,
) -> dict[str, Any]:
    """
    Generate daily summary report from structured logs.

    Args:
        log_dir: Directory containing structured logs
        output_dir: Optional directory to save reports

    Returns:
        Dictionary with summary statistics
    """
    log_path = Path(log_dir)
    output_path = Path(output_dir or log_dir / "reports")
    output_path.mkdir(parents=True, exist_ok=True)

    aggregator = ErrorAggregator(log_dir)
    error_report = aggregator.generate_report(
        output_path / f"error_report_{datetime.now().strftime('%Y%m%d')}.md"
    )

    # Parse all paper logs for summary statistics
    papers_completed = 0
    papers_failed = 0
    total_duration_ms = 0
    stage_durations: dict[str, list[float]] = {}

    for log_file in log_path.glob("paper_*.jsonl"):
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    entry = json.loads(line.strip())
                    stage = entry.get("stage")
                    duration = entry.get("duration_ms")

                    if duration:
                        total_duration_ms += duration
                        if stage and stage not in stage_durations:
                            stage_durations[stage] = []
                        if stage:
                            stage_durations[stage].append(duration)

                    if stage == "completed":
                        papers_completed += 1
                    elif stage == "failed":
                        papers_failed += 1
        except (json.JSONDecodeError, IOError):
            continue

    avg_duration_per_paper = (
        total_duration_ms / max(papers_completed + papers_failed, 1) / 1000
    )

    summary = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "papers_processed": papers_completed + papers_failed,
        "papers_completed": papers_completed,
        "papers_failed": papers_failed,
        "success_rate": papers_completed / max(papers_completed + papers_failed, 1) * 100,
        "total_time_seconds": total_duration_ms / 1000,
        "avg_time_per_paper_seconds": avg_duration_per_paper,
        "stage_durations": {
            stage: {
                "avg_ms": sum(durations) / len(durations),
                "count": len(durations),
            }
            for stage, durations in stage_durations.items()
        },
    }

    # Save summary JSON
    summary_file = output_path / f"summary_{datetime.now().strftime('%Y%m%d')}.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Generate human-readable summary
    summary_lines = [
        f"# AUTO-GIT Daily Summary - {summary['date']}",
        "",
        "## Overview",
        f"- Papers Processed: {summary['papers_processed']}",
        f"- Success Rate: {summary['success_rate']:.1f}% ({summary['papers_completed']}/{summary['papers_processed']})",
        f"- Failures: {summary['papers_failed']}",
        f"- Total Time: {summary['total_time_seconds'] / 3600:.1f}h",
        f"- Avg Time/Paper: {summary['avg_time_per_paper_seconds'] / 60:.1f}m",
        "",
        "## Stage Durations",
        "",
    ]

    for stage, stats in sorted(
        summary["stage_durations"].items(),
        key=lambda x: x[1]["avg_ms"],
        reverse=True
    ):
        summary_lines.append(
            f"- **{stage}**: {stats['avg_ms'] / 1000:.1f}s avg ({stats['count']} operations)"
        )

    summary_report = "\n".join(summary_lines)

    summary_md_file = output_path / f"summary_{datetime.now().strftime('%Y%m%d')}.md"
    with open(summary_md_file, "w", encoding="utf-8") as f:
        f.write(summary_report)

    return summary
