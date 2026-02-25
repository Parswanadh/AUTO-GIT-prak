"""
Degradation Detector

Detects performance degradation by tracking metrics and comparing to baselines.
"""

import time
from typing import Dict, Optional, List, Any
from dataclasses import dataclass
from collections import deque
import statistics


@dataclass
class DegradationAlert:
    """Alert for detected degradation"""
    component: str
    metric: str
    current_value: float
    baseline_value: float
    degradation_percent: float
    severity: str  # "warning", "critical"
    timestamp: float
    details: Dict[str, Any]


class DegradationDetector:
    """
    Performance degradation detector
    
    Monitors performance metrics and detects degradation by:
    - Maintaining baseline performance metrics
    - Comparing current performance to baseline
    - Detecting statistically significant degradation
    - Generating alerts for degradation
    - Tracking degradation trends
    
    Example:
        detector = DegradationDetector(
            baseline_window=100,
            degradation_threshold=0.3  # 30% degradation
        )
        
        # Record metrics during normal operation
        for _ in range(100):
            detector.record_metric("api", "latency", 100.0)
        
        # Detect degradation
        detector.record_metric("api", "latency", 150.0)
        alert = detector.check_degradation("api", "latency")
        
        if alert:
            print(f"Degradation detected: {alert.degradation_percent:.1f}%")
    """
    
    def __init__(
        self,
        baseline_window: int = 100,
        current_window: int = 10,
        degradation_threshold: float = 0.3,
        critical_threshold: float = 0.5
    ):
        """
        Initialize degradation detector
        
        Args:
            baseline_window: Number of samples for baseline
            current_window: Number of recent samples to compare
            degradation_threshold: Threshold for warning (0.0-1.0)
            critical_threshold: Threshold for critical (0.0-1.0)
        """
        if baseline_window <= 0:
            raise ValueError("baseline_window must be positive")
        if current_window <= 0:
            raise ValueError("current_window must be positive")
        if not (0 < degradation_threshold < 1):
            raise ValueError("degradation_threshold must be between 0 and 1")
        if not (0 < critical_threshold < 1):
            raise ValueError("critical_threshold must be between 0 and 1")
        
        self.baseline_window = baseline_window
        self.current_window = current_window
        self.degradation_threshold = degradation_threshold
        self.critical_threshold = critical_threshold
        
        # Metric storage: {component: {metric: deque}}
        self.metrics: Dict[str, Dict[str, deque]] = {}
        
        # Baselines: {component: {metric: value}}
        self.baselines: Dict[str, Dict[str, float]] = {}
        
        # Baseline established: {component: {metric: bool}}
        self.baseline_established: Dict[str, Dict[str, bool]] = {}
        
        # Active alerts
        self.active_alerts: List[DegradationAlert] = []
    
    def record_metric(
        self,
        component: str,
        metric_name: str,
        value: float
    ) -> None:
        """
        Record a performance metric
        
        Args:
            component: Component name
            metric_name: Metric name (e.g., "latency", "error_rate")
            value: Metric value
        """
        # Initialize component if needed
        if component not in self.metrics:
            self.metrics[component] = {}
            self.baselines[component] = {}
            self.baseline_established[component] = {}
        
        # Initialize metric if needed
        if metric_name not in self.metrics[component]:
            self.metrics[component][metric_name] = deque(
                maxlen=self.baseline_window + self.current_window
            )
            self.baseline_established[component][metric_name] = False
        
        # Record value
        self.metrics[component][metric_name].append(value)
        
        # Update baseline if not established or periodically
        if not self.baseline_established[component][metric_name]:
            if len(self.metrics[component][metric_name]) >= self.baseline_window:
                self._update_baseline(component, metric_name)
                self.baseline_established[component][metric_name] = True
    
    def _update_baseline(self, component: str, metric_name: str) -> None:
        """Update baseline for metric"""
        values = list(self.metrics[component][metric_name])
        
        if not values:
            return
        
        # Use median for robustness
        if len(values) >= self.baseline_window:
            # Use first baseline_window samples
            baseline_samples = values[:self.baseline_window]
            self.baselines[component][metric_name] = statistics.median(baseline_samples)
        else:
            self.baselines[component][metric_name] = statistics.median(values)
    
    def check_degradation(
        self,
        component: str,
        metric_name: str
    ) -> Optional[DegradationAlert]:
        """
        Check for performance degradation
        
        Args:
            component: Component name
            metric_name: Metric name
            
        Returns:
            DegradationAlert if degradation detected, None otherwise
        """
        # Check if metric exists
        if (component not in self.metrics or
            metric_name not in self.metrics[component]):
            return None
        
        # Check if baseline established
        if not self.baseline_established.get(component, {}).get(metric_name, False):
            return None
        
        values = self.metrics[component][metric_name]
        
        # Need enough recent samples
        if len(values) < self.baseline_window + self.current_window:
            return None
        
        # Get recent samples
        recent_samples = list(values)[-self.current_window:]
        current_value = statistics.median(recent_samples)
        
        # Get baseline
        baseline_value = self.baselines[component][metric_name]
        
        if baseline_value == 0:
            return None
        
        # Calculate degradation (assuming higher is worse)
        degradation = (current_value - baseline_value) / baseline_value
        
        # Check thresholds
        if degradation >= self.critical_threshold:
            severity = "critical"
        elif degradation >= self.degradation_threshold:
            severity = "warning"
        else:
            return None
        
        # Create alert
        alert = DegradationAlert(
            component=component,
            metric=metric_name,
            current_value=current_value,
            baseline_value=baseline_value,
            degradation_percent=degradation * 100,
            severity=severity,
            timestamp=time.time(),
            details={
                "recent_samples": len(recent_samples),
                "baseline_samples": self.baseline_window,
                "threshold": (
                    self.critical_threshold if severity == "critical"
                    else self.degradation_threshold
                )
            }
        )
        
        # Add to active alerts
        self.active_alerts.append(alert)
        
        return alert
    
    def check_all(self, component: str) -> List[DegradationAlert]:
        """
        Check all metrics for a component
        
        Args:
            component: Component name
            
        Returns:
            List of degradation alerts
        """
        if component not in self.metrics:
            return []
        
        alerts = []
        for metric_name in self.metrics[component].keys():
            alert = self.check_degradation(component, metric_name)
            if alert:
                alerts.append(alert)
        
        return alerts
    
    def get_baseline(
        self,
        component: str,
        metric_name: str
    ) -> Optional[float]:
        """
        Get baseline value for metric
        
        Args:
            component: Component name
            metric_name: Metric name
            
        Returns:
            Baseline value or None
        """
        if (component not in self.baselines or
            metric_name not in self.baselines[component]):
            return None
        
        return self.baselines[component][metric_name]
    
    def reset_baseline(
        self,
        component: str,
        metric_name: Optional[str] = None
    ) -> None:
        """
        Reset baseline for component/metric
        
        Args:
            component: Component name
            metric_name: Specific metric (None for all)
        """
        if component not in self.baseline_established:
            return
        
        if metric_name is not None:
            if metric_name in self.baseline_established[component]:
                self.baseline_established[component][metric_name] = False
        else:
            for metric in self.baseline_established[component].keys():
                self.baseline_established[component][metric] = False
    
    def clear_alerts(self, component: Optional[str] = None) -> None:
        """
        Clear active alerts
        
        Args:
            component: Specific component (None for all)
        """
        if component is not None:
            self.active_alerts = [
                a for a in self.active_alerts
                if a.component != component
            ]
        else:
            self.active_alerts.clear()
    
    def get_active_alerts(
        self,
        component: Optional[str] = None
    ) -> List[DegradationAlert]:
        """
        Get active degradation alerts
        
        Args:
            component: Filter by component (None for all)
            
        Returns:
            List of active alerts
        """
        if component is not None:
            return [a for a in self.active_alerts if a.component == component]
        return list(self.active_alerts)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "monitored_components": list(self.metrics.keys()),
            "total_metrics": sum(
                len(metrics) for metrics in self.metrics.values()
            ),
            "baselines_established": sum(
                sum(1 for established in comp.values() if established)
                for comp in self.baseline_established.values()
            ),
            "active_alerts": len(self.active_alerts),
            "alerts": [
                {
                    "component": alert.component,
                    "metric": alert.metric,
                    "current_value": alert.current_value,
                    "baseline_value": alert.baseline_value,
                    "degradation_percent": alert.degradation_percent,
                    "severity": alert.severity,
                    "ago_seconds": time.time() - alert.timestamp
                }
                for alert in self.active_alerts[-10:]  # Last 10 alerts
            ]
        }
