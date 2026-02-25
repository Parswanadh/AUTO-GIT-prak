"""Trace Span - Represents a single operation in the trace"""

import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class SpanContext:
    """Span context for propagating trace information"""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for serialization"""
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SpanContext":
        """Create from dict"""
        return cls(**data)


@dataclass
class TraceSpan:
    """
    Represents a single operation (span) in a distributed trace
    
    Tracks:
    - Start/end timestamps
    - Duration
    - Status (success/error)
    - Metadata
    - Parent-child relationships
    """
    
    # Identifiers
    trace_id: str
    span_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    parent_span_id: Optional[str] = None
    
    # Operation details
    operation: str = "unknown"
    component: str = "pipeline"
    
    # Timing
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration_seconds: Optional[float] = None
    
    # Status
    status: str = "in_progress"  # in_progress, success, error
    error: Optional[str] = None
    error_type: Optional[str] = None
    
    # Metadata
    tags: Dict[str, Any] = field(default_factory=dict)
    logs: List[Dict[str, Any]] = field(default_factory=list)
    
    # Resource usage
    tokens_used: int = 0
    model_used: Optional[str] = None
    backend: Optional[str] = None
    
    def __enter__(self):
        """Context manager entry"""
        self.start_time = time.time()
        self.status = "in_progress"
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if exc_type is not None:
            self.record_error(exc_val, exc_type.__name__)
        else:
            self.end(success=True)
        return False  # Don't suppress exceptions
    
    def end(self, success: bool = True):
        """Mark span as complete"""
        self.end_time = time.time()
        self.duration_seconds = self.end_time - self.start_time
        self.status = "success" if success else "error"
    
    def record_error(self, error: Exception, error_type: Optional[str] = None):
        """Record error in span"""
        self.status = "error"
        self.error = str(error)
        self.error_type = error_type or type(error).__name__
        self.end()
    
    def set_tag(self, key: str, value: Any):
        """Set a tag on the span"""
        self.tags[key] = value
    
    def log_event(self, event: str, **kwargs):
        """Log an event within the span"""
        self.logs.append({
            "timestamp": time.time(),
            "event": event,
            **kwargs
        })
    
    def set_resource_usage(
        self,
        tokens: int,
        model: Optional[str] = None,
        backend: Optional[str] = None
    ):
        """Record resource usage"""
        self.tokens_used = tokens
        self.model_used = model
        self.backend = backend
    
    def get_context(self) -> SpanContext:
        """Get span context for propagation"""
        return SpanContext(
            trace_id=self.trace_id,
            span_id=self.span_id,
            parent_span_id=self.parent_span_id
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for serialization"""
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "operation": self.operation,
            "component": self.component,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": self.duration_seconds,
            "status": self.status,
            "error": self.error,
            "error_type": self.error_type,
            "tags": self.tags,
            "logs": self.logs,
            "tokens_used": self.tokens_used,
            "model_used": self.model_used,
            "backend": self.backend,
            "timestamp_iso": datetime.fromtimestamp(self.start_time).isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TraceSpan":
        """Create from dict"""
        # Remove timestamp_iso if present (it's computed)
        data = {k: v for k, v in data.items() if k != "timestamp_iso"}
        return cls(**data)
    
    def is_finished(self) -> bool:
        """Check if span is finished"""
        return self.end_time is not None
    
    def is_successful(self) -> bool:
        """Check if span completed successfully"""
        return self.status == "success"
    
    def has_error(self) -> bool:
        """Check if span has error"""
        return self.status == "error"
    
    def __repr__(self) -> str:
        """String representation"""
        duration_str = f"{self.duration_seconds:.3f}s" if self.duration_seconds else "in_progress"
        return (
            f"TraceSpan(operation={self.operation}, "
            f"span_id={self.span_id[:6]}, "
            f"status={self.status}, "
            f"duration={duration_str})"
        )
