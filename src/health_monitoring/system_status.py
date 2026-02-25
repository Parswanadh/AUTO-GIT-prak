"""
System Status Monitor

Aggregates health status across all components and provides system-wide health metrics.
"""

import time
from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


class SystemStatus(Enum):
    """Overall system status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ComponentStatus:
    """Status of a single component"""
    name: str
    status: str
    latency_ms: float
    uptime: float
    last_check_ago: Optional[float]
    consecutive_failures: int
    is_critical: bool


@dataclass
class SystemHealth:
    """Overall system health information"""
    overall_status: SystemStatus
    health_score: float
    total_components: int
    healthy_components: int
    degraded_components: int
    unhealthy_components: int
    critical_failures: int
    timestamp: float


class SystemStatusMonitor:
    """
    System-wide status monitoring
    
    Aggregates health status from all components and provides:
    - Overall system status (HEALTHY, DEGRADED, UNHEALTHY)
    - System health score (0.0-1.0)
    - Component-level status
    - Critical component tracking
    - Status change alerts
    
    Example:
        monitor = SystemStatusMonitor()
        monitor.set_health_checker(health_checker)
        monitor.set_recovery_orchestrator(recovery_orchestrator)
        
        # Get system health
        health = monitor.get_system_health()
        print(f"System is {health.overall_status.value}")
        print(f"Health score: {health.health_score:.2f}")
    """
    
    def __init__(self):
        """Initialize system status monitor"""
        self.health_checker = None
        self.recovery_orchestrator = None
        self._last_status: Optional[SystemStatus] = None
        self._status_change_callbacks: List = []
    
    def set_health_checker(self, health_checker) -> None:
        """Set health checker instance"""
        self.health_checker = health_checker
    
    def set_recovery_orchestrator(self, recovery_orchestrator) -> None:
        """Set recovery orchestrator instance"""
        self.recovery_orchestrator = recovery_orchestrator
    
    def register_status_change_callback(self, callback) -> None:
        """
        Register callback for status changes
        
        Args:
            callback: Function called when system status changes
        """
        self._status_change_callbacks.append(callback)
    
    def get_component_statuses(self) -> Dict[str, ComponentStatus]:
        """
        Get status for all components
        
        Returns:
            Dictionary mapping component names to status
        """
        if not self.health_checker:
            return {}
        
        statuses = {}
        
        for name, health in self.health_checker.get_all_component_health().items():
            comp_config = self.health_checker.components.get(name, {})
            
            statuses[name] = ComponentStatus(
                name=name,
                status=health.status.value,
                latency_ms=health.average_latency * 1000,
                uptime=health.uptime,
                last_check_ago=(
                    time.time() - health.last_check.timestamp
                    if health.last_check else None
                ),
                consecutive_failures=health.consecutive_failures,
                is_critical=comp_config.get("critical", True)
            )
        
        return statuses
    
    def get_system_health(self) -> SystemHealth:
        """
        Get overall system health
        
        Returns:
            SystemHealth with aggregated metrics
        """
        if not self.health_checker:
            return SystemHealth(
                overall_status=SystemStatus.UNKNOWN,
                health_score=0.0,
                total_components=0,
                healthy_components=0,
                degraded_components=0,
                unhealthy_components=0,
                critical_failures=0,
                timestamp=time.time()
            )
        
        statuses = self.get_component_statuses()
        
        if not statuses:
            return SystemHealth(
                overall_status=SystemStatus.UNKNOWN,
                health_score=0.0,
                total_components=0,
                healthy_components=0,
                degraded_components=0,
                unhealthy_components=0,
                critical_failures=0,
                timestamp=time.time()
            )
        
        # Count component statuses
        healthy = sum(1 for s in statuses.values() if s.status == "healthy")
        degraded = sum(1 for s in statuses.values() if s.status == "degraded")
        unhealthy = sum(1 for s in statuses.values() if s.status == "unhealthy")
        
        # Count critical failures
        critical_failures = sum(
            1 for s in statuses.values()
            if s.status == "unhealthy" and s.is_critical
        )
        
        # Calculate health score
        total = len(statuses)
        health_score = healthy / total if total > 0 else 0.0
        
        # Adjust for degraded (50% weight)
        health_score += (degraded * 0.5) / total if total > 0 else 0.0
        
        # Determine overall status
        if critical_failures > 0:
            overall_status = SystemStatus.UNHEALTHY
        elif unhealthy > 0:
            overall_status = SystemStatus.UNHEALTHY
        elif degraded > 0:
            overall_status = SystemStatus.DEGRADED
        elif healthy == total:
            overall_status = SystemStatus.HEALTHY
        else:
            overall_status = SystemStatus.UNKNOWN
        
        # Check for status change
        if self._last_status != overall_status:
            self._notify_status_change(self._last_status, overall_status)
            self._last_status = overall_status
        
        return SystemHealth(
            overall_status=overall_status,
            health_score=health_score,
            total_components=total,
            healthy_components=healthy,
            degraded_components=degraded,
            unhealthy_components=unhealthy,
            critical_failures=critical_failures,
            timestamp=time.time()
        )
    
    def _notify_status_change(
        self,
        old_status: Optional[SystemStatus],
        new_status: SystemStatus
    ) -> None:
        """Notify callbacks of status change"""
        for callback in self._status_change_callbacks:
            try:
                callback(old_status, new_status)
            except Exception:
                # Don't let callback errors affect monitoring
                pass
    
    def get_health_score(self) -> float:
        """
        Get system health score (0.0-1.0)
        
        Returns:
            Health score between 0.0 (unhealthy) and 1.0 (healthy)
        """
        return self.get_system_health().health_score
    
    def is_healthy(self) -> bool:
        """Check if system is healthy"""
        health = self.get_system_health()
        return health.overall_status == SystemStatus.HEALTHY
    
    def has_critical_failures(self) -> bool:
        """Check if there are critical component failures"""
        health = self.get_system_health()
        return health.critical_failures > 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        health = self.get_system_health()
        statuses = self.get_component_statuses()
        
        return {
            "system_health": {
                "overall_status": health.overall_status.value,
                "health_score": health.health_score,
                "total_components": health.total_components,
                "healthy_components": health.healthy_components,
                "degraded_components": health.degraded_components,
                "unhealthy_components": health.unhealthy_components,
                "critical_failures": health.critical_failures,
                "timestamp": health.timestamp
            },
            "components": {
                name: {
                    "status": status.status,
                    "latency_ms": status.latency_ms,
                    "uptime": status.uptime,
                    "last_check_ago_seconds": status.last_check_ago,
                    "consecutive_failures": status.consecutive_failures,
                    "is_critical": status.is_critical
                }
                for name, status in statuses.items()
            }
        }
