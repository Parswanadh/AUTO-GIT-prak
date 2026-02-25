"""
Health Checker

Monitors component health with periodic checks, retries, and status tracking.
"""

import asyncio
import time
from enum import Enum
from typing import Callable, Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import deque


class HealthStatus(Enum):
    """Component health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class HealthCheckError(Exception):
    """Raised when health check fails"""
    pass


@dataclass
class HealthResult:
    """Result of a health check"""
    component: str
    status: HealthStatus
    message: str
    latency: float
    timestamp: float
    details: Dict[str, Any] = field(default_factory=dict)
    check_type: str = "ping"


@dataclass
class ComponentHealth:
    """Health information for a component"""
    name: str
    status: HealthStatus
    last_check: Optional[HealthResult]
    consecutive_failures: int
    total_checks: int
    successful_checks: int
    average_latency: float
    uptime: float


class HealthChecker:
    """
    Component health checker with periodic monitoring
    
    Monitors registered components with configurable health checks:
    - Periodic checks at configured intervals
    - Automatic retries on transient failures
    - Health status tracking (HEALTHY, DEGRADED, UNHEALTHY, UNKNOWN)
    - Latency and uptime tracking
    - Dependency awareness
    
    Example:
        checker = HealthChecker(check_interval=30.0)
        
        # Register component
        async def check_database():
            # Perform health check
            if database.is_connected():
                return {"status": "ok", "connections": 10}
            raise HealthCheckError("Not connected")
        
        checker.register_component("database", check_database)
        
        # Check health
        result = await checker.check_health("database")
        if result.status == HealthStatus.HEALTHY:
            print("Database is healthy!")
    """
    
    def __init__(
        self,
        check_interval: float = 30.0,
        timeout: float = 5.0,
        max_retries: int = 3,
        history_size: int = 100
    ):
        """
        Initialize health checker
        
        Args:
            check_interval: Seconds between checks
            timeout: Timeout for each check
            max_retries: Max retry attempts on failure
            history_size: Number of historical results to keep
        """
        if check_interval <= 0:
            raise ValueError("check_interval must be positive")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        
        self.check_interval = check_interval
        self.timeout = timeout
        self.max_retries = max_retries
        self.history_size = history_size
        
        # Component registry
        self.components: Dict[str, Dict[str, Any]] = {}
        
        # Latest results
        self.last_results: Dict[str, HealthResult] = {}
        
        # Historical results
        self.history: Dict[str, deque] = {}
        
        # Background monitoring
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
    
    def register_component(
        self,
        name: str,
        check_func: Callable,
        check_type: str = "ping",
        dependencies: Optional[List[str]] = None,
        critical: bool = True
    ) -> None:
        """
        Register component for health monitoring
        
        Args:
            name: Component name
            check_func: Async function that performs health check
            check_type: Type of check (ping, functional, deep)
            dependencies: List of component names this depends on
            critical: Whether this is a critical component
        """
        self.components[name] = {
            "check_func": check_func,
            "check_type": check_type,
            "dependencies": dependencies or [],
            "critical": critical,
            "consecutive_failures": 0,
            "total_checks": 0,
            "successful_checks": 0,
            "total_latency": 0.0,
            "last_check_time": None
        }
        
        self.history[name] = deque(maxlen=self.history_size)
    
    async def check_health(self, component: str) -> HealthResult:
        """
        Check health of specific component
        
        Args:
            component: Component name
            
        Returns:
            HealthResult with status and details
        """
        if component not in self.components:
            return HealthResult(
                component=component,
                status=HealthStatus.UNKNOWN,
                message="Component not registered",
                latency=0.0,
                timestamp=time.time(),
                details={},
                check_type="unknown"
            )
        
        comp = self.components[component]
        check_func = comp["check_func"]
        check_type = comp["check_type"]
        
        comp["total_checks"] += 1
        
        # Try with retries
        last_error = None
        for attempt in range(self.max_retries + 1):
            start = time.time()
            
            try:
                # Run check with timeout
                result = await asyncio.wait_for(
                    check_func(),
                    timeout=self.timeout
                )
                
                latency = time.time() - start
                
                # Success
                comp["consecutive_failures"] = 0
                comp["successful_checks"] += 1
                comp["total_latency"] += latency
                comp["last_check_time"] = time.time()
                
                health_result = HealthResult(
                    component=component,
                    status=HealthStatus.HEALTHY,
                    message="Check passed",
                    latency=latency,
                    timestamp=time.time(),
                    details=result if isinstance(result, dict) else {},
                    check_type=check_type
                )
                
                self.last_results[component] = health_result
                self.history[component].append(health_result)
                
                return health_result
                
            except asyncio.TimeoutError:
                last_error = "Timeout"
                latency = time.time() - start
                
                if attempt < self.max_retries:
                    await asyncio.sleep(0.1 * (attempt + 1))
                    continue
                
            except Exception as e:
                last_error = str(e)
                latency = time.time() - start
                
                if attempt < self.max_retries:
                    await asyncio.sleep(0.1 * (attempt + 1))
                    continue
        
        # All retries failed
        comp["consecutive_failures"] += 1
        comp["last_check_time"] = time.time()
        
        health_result = HealthResult(
            component=component,
            status=HealthStatus.UNHEALTHY,
            message=f"Check failed after {self.max_retries + 1} attempts: {last_error}",
            latency=latency,
            timestamp=time.time(),
            details={
                "error": last_error,
                "consecutive_failures": comp["consecutive_failures"],
                "attempts": self.max_retries + 1
            },
            check_type=check_type
        )
        
        self.last_results[component] = health_result
        self.history[component].append(health_result)
        
        return health_result
    
    async def check_all(self) -> Dict[str, HealthResult]:
        """
        Check health of all registered components
        
        Returns:
            Dictionary mapping component names to health results
        """
        if not self.components:
            return {}
        
        # Check all components concurrently
        tasks = {
            name: self.check_health(name)
            for name in self.components.keys()
        }
        
        results = await asyncio.gather(*tasks.values())
        
        return {
            name: result
            for name, result in zip(tasks.keys(), results)
        }
    
    def get_status(self, component: str) -> HealthStatus:
        """
        Get current health status of component
        
        Args:
            component: Component name
            
        Returns:
            Current HealthStatus
        """
        if component not in self.last_results:
            return HealthStatus.UNKNOWN
        
        return self.last_results[component].status
    
    def get_component_health(self, component: str) -> ComponentHealth:
        """
        Get detailed health information for component
        
        Args:
            component: Component name
            
        Returns:
            ComponentHealth with detailed stats
        """
        if component not in self.components:
            return ComponentHealth(
                name=component,
                status=HealthStatus.UNKNOWN,
                last_check=None,
                consecutive_failures=0,
                total_checks=0,
                successful_checks=0,
                average_latency=0.0,
                uptime=0.0
            )
        
        comp = self.components[component]
        last_check = self.last_results.get(component)
        
        avg_latency = 0.0
        if comp["successful_checks"] > 0:
            avg_latency = comp["total_latency"] / comp["successful_checks"]
        
        uptime = 0.0
        if comp["total_checks"] > 0:
            uptime = comp["successful_checks"] / comp["total_checks"]
        
        return ComponentHealth(
            name=component,
            status=last_check.status if last_check else HealthStatus.UNKNOWN,
            last_check=last_check,
            consecutive_failures=comp["consecutive_failures"],
            total_checks=comp["total_checks"],
            successful_checks=comp["successful_checks"],
            average_latency=avg_latency,
            uptime=uptime
        )
    
    def get_all_component_health(self) -> Dict[str, ComponentHealth]:
        """Get health info for all components"""
        return {
            name: self.get_component_health(name)
            for name in self.components.keys()
        }
    
    async def start_monitoring(self) -> None:
        """Start background health monitoring"""
        if self._running:
            return
        
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
    
    async def stop_monitoring(self) -> None:
        """Stop background health monitoring"""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
    
    async def _monitor_loop(self) -> None:
        """Background monitoring loop"""
        while self._running:
            try:
                await self.check_all()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception:
                # Continue monitoring even on errors
                await asyncio.sleep(self.check_interval)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "components": {
                name: {
                    "status": health.status.value,
                    "consecutive_failures": health.consecutive_failures,
                    "total_checks": health.total_checks,
                    "successful_checks": health.successful_checks,
                    "uptime": health.uptime,
                    "average_latency_ms": health.average_latency * 1000,
                    "last_check_ago_seconds": (
                        time.time() - health.last_check.timestamp
                        if health.last_check else None
                    )
                }
                for name, health in self.get_all_component_health().items()
            },
            "monitoring_active": self._running
        }
