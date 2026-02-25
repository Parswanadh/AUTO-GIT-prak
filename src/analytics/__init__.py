"""Analytics and Optimization Module (Integration #20)

SQLite-based analytics for tracking:
- Model performance metrics
- Token usage across runs
- Success/failure rates
- Cost analysis
- Performance trends
"""

from .tracker import AnalyticsTracker
from .optimizer import PerformanceOptimizer
from .reporter import AnalyticsReporter

__all__ = [
    "AnalyticsTracker",
    "PerformanceOptimizer",
    "AnalyticsReporter",
]
