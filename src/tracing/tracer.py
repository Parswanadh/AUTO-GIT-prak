"""Distributed Tracer - JSON-based tracing system"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid

from .span import TraceSpan, SpanContext

logger = logging.getLogger(__name__)


class DistributedTracer:
    """
    JSON-based distributed tracing system
    
    Features:
    - Hierarchical span tracking
    - JSON log output
    - Parent-child relationships
    - Performance analysis
    - Error tracking
    """
    
    def __init__(self, trace_dir: str = "data/traces"):
        """Initialize tracer with trace directory"""
        self.trace_dir = Path(trace_dir)
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        
        # Active spans (in memory)
        self.active_spans: Dict[str, TraceSpan] = {}
        
        # Current trace context
        self.current_trace_id: Optional[str] = None
        
        logger.info(f"Distributed tracer initialized: {self.trace_dir}")
    
    def start_trace(self, operation: str = "pipeline") -> str:
        """
        Start a new trace (root span)
        
        Args:
            operation: Name of the root operation
            
        Returns:
            Trace ID
        """
        trace_id = str(uuid.uuid4())[:12]
        self.current_trace_id = trace_id
        
        # Create root span
        root_span = TraceSpan(
            trace_id=trace_id,
            operation=operation,
            component="root"
        )
        
        self.active_spans[root_span.span_id] = root_span
        
        logger.info(f"Started trace: {trace_id} ({operation})")
        return trace_id
    
    def start_span(
        self,
        operation: str,
        component: str = "pipeline",
        parent_context: Optional[SpanContext] = None,
        tags: Optional[Dict[str, Any]] = None
    ) -> TraceSpan:
        """
        Start a new span
        
        Args:
            operation: Operation name
            component: Component name (node, agent, etc.)
            parent_context: Parent span context for hierarchy
            tags: Initial tags
            
        Returns:
            TraceSpan object
        """
        # Use current trace or create new one
        trace_id = (
            parent_context.trace_id 
            if parent_context 
            else self.current_trace_id or self.start_trace()
        )
        
        # Create span
        span = TraceSpan(
            trace_id=trace_id,
            operation=operation,
            component=component,
            parent_span_id=parent_context.span_id if parent_context else None,
            tags=tags or {}
        )
        
        self.active_spans[span.span_id] = span
        
        logger.debug(f"Started span: {operation} ({span.span_id[:6]})")
        return span
    
    def end_span(
        self,
        span: TraceSpan,
        success: bool = True,
        tags: Optional[Dict[str, Any]] = None
    ):
        """
        End a span and write to JSON
        
        Args:
            span: Span to end
            success: Whether operation succeeded (ignored if span already has error)
            tags: Additional tags to add
        """
        # Update final tags
        if tags:
            for key, value in tags.items():
                span.set_tag(key, value)
        
        # Mark as complete (only if not already errored)
        if span.status != "error":
            span.end(success=success)
        
        # Write to JSON file
        self._write_span_to_json(span)
        
        # Remove from active spans
        if span.span_id in self.active_spans:
            del self.active_spans[span.span_id]
        
        logger.debug(f"Ended span: {span.operation} ({span.duration_seconds:.3f}s)")
    
    def record_error(
        self,
        span: TraceSpan,
        error: Exception,
        error_type: Optional[str] = None
    ):
        """Record error in span and end it"""
        span.record_error(error, error_type)
        self._write_span_to_json(span)
        
        if span.span_id in self.active_spans:
            del self.active_spans[span.span_id]
    
    def _write_span_to_json(self, span: TraceSpan):
        """Write span to JSON file"""
        try:
            # Create trace-specific file
            trace_file = self.trace_dir / f"trace_{span.trace_id}.jsonl"
            
            # Append span as JSON line
            with open(trace_file, 'a') as f:
                json.dump(span.to_dict(), f)
                f.write('\n')
            
        except Exception as e:
            logger.error(f"Failed to write span to JSON: {e}")
    
    def get_trace(self, trace_id: str) -> List[TraceSpan]:
        """
        Load all spans for a trace from JSON
        
        Args:
            trace_id: Trace ID to load
            
        Returns:
            List of spans
        """
        trace_file = self.trace_dir / f"trace_{trace_id}.jsonl"
        
        if not trace_file.exists():
            return []
        
        spans = []
        try:
            with open(trace_file, 'r') as f:
                for line in f:
                    if line.strip():
                        span_data = json.loads(line)
                        span = TraceSpan.from_dict(span_data)
                        spans.append(span)
        except Exception as e:
            logger.error(f"Failed to load trace {trace_id}: {e}")
        
        return spans
    
    def get_trace_summary(self, trace_id: str) -> Dict[str, Any]:
        """
        Get summary statistics for a trace
        
        Args:
            trace_id: Trace ID
            
        Returns:
            Summary dict
        """
        spans = self.get_trace(trace_id)
        
        if not spans:
            return {}
        
        total_duration = sum(
            s.duration_seconds for s in spans 
            if s.duration_seconds is not None
        )
        
        successful_spans = [s for s in spans if s.is_successful()]
        error_spans = [s for s in spans if s.has_error()]
        
        total_tokens = sum(s.tokens_used for s in spans)
        
        # Find root span
        root_span = next(
            (s for s in spans if s.parent_span_id is None),
            None
        )
        
        return {
            "trace_id": trace_id,
            "total_spans": len(spans),
            "successful_spans": len(successful_spans),
            "error_spans": len(error_spans),
            "total_duration_seconds": total_duration,
            "total_tokens": total_tokens,
            "root_operation": root_span.operation if root_span else "unknown",
            "start_time": root_span.start_time if root_span else None,
            "end_time": max(
                (s.end_time for s in spans if s.end_time),
                default=None
            ),
            "models_used": list(set(
                s.model_used for s in spans 
                if s.model_used
            )),
            "error_summary": [
                {
                    "operation": s.operation,
                    "error": s.error,
                    "error_type": s.error_type
                }
                for s in error_spans
            ]
        }
    
    def list_traces(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        List recent traces
        
        Args:
            limit: Maximum number of traces to return
            
        Returns:
            List of trace summaries
        """
        trace_files = sorted(
            self.trace_dir.glob("trace_*.jsonl"),
            key=lambda f: f.stat().st_mtime,
            reverse=True
        )[:limit]
        
        summaries = []
        for trace_file in trace_files:
            # Extract trace ID from filename
            trace_id = trace_file.stem.replace("trace_", "")
            summary = self.get_trace_summary(trace_id)
            if summary:
                summaries.append(summary)
        
        return summaries
    
    def visualize_trace(self, trace_id: str) -> str:
        """
        Create ASCII visualization of trace hierarchy
        
        Args:
            trace_id: Trace ID
            
        Returns:
            ASCII tree string
        """
        spans = self.get_trace(trace_id)
        
        if not spans:
            return f"No spans found for trace {trace_id}"
        
        # Build tree structure
        span_map = {s.span_id: s for s in spans}
        root_spans = [s for s in spans if s.parent_span_id is None]
        
        lines = []
        lines.append(f"Trace: {trace_id}")
        lines.append("="*60)
        
        def render_span(span: TraceSpan, prefix: str = "", is_last: bool = True):
            """Recursively render span tree"""
            # Status indicator
            if span.is_successful():
                status = "✅"
            elif span.has_error():
                status = "❌"
            else:
                status = "⏳"
            
            # Duration
            duration = f"{span.duration_seconds:.3f}s" if span.duration_seconds else "---"
            
            # Model info
            model_info = f" [{span.model_used}]" if span.model_used else ""
            
            # Line
            connector = "└── " if is_last else "├── "
            lines.append(
                f"{prefix}{connector}{status} {span.operation} ({duration}){model_info}"
            )
            
            # Find children
            children = [s for s in spans if s.parent_span_id == span.span_id]
            
            # Render children
            child_prefix = prefix + ("    " if is_last else "│   ")
            for i, child in enumerate(children):
                render_span(child, child_prefix, i == len(children) - 1)
        
        # Render from roots
        for i, root in enumerate(root_spans):
            render_span(root, "", i == len(root_spans) - 1)
        
        return "\n".join(lines)
    
    def create_span_context(self, span: TraceSpan) -> SpanContext:
        """Create propagation context from span"""
        return span.get_context()
    
    def flush(self):
        """Flush any pending spans"""
        for span in list(self.active_spans.values()):
            if span.is_finished():
                self._write_span_to_json(span)
                del self.active_spans[span.span_id]
        
        logger.info(f"Flushed tracer, {len(self.active_spans)} spans still active")
