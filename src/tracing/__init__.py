"""Distributed Tracing Module (Integration #19)

JSON-based tracing for tracking:
- Pipeline execution flows
- Node-to-node transitions
- Timing and performance
- Error propagation
"""

from .tracer import DistributedTracer
from .span import TraceSpan, SpanContext

__all__ = [
    "DistributedTracer",
    "TraceSpan",
    "SpanContext",
]
