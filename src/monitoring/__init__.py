"""
Production Monitoring System - Integration #14

Provides comprehensive observability for the auto-git system:
- Real-time metrics collection
- Time series storage
- Dashboard generation
- Alert evaluation
"""

from .metrics_collector import MetricsCollector
from .dashboard import DashboardGenerator

__all__ = ['MetricsCollector', 'DashboardGenerator']
