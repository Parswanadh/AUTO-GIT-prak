"""
Recovery Orchestrator

Coordinates automatic recovery across components with strategies, backoff, and dependency handling.
"""

import asyncio
import time
from enum import Enum
from typing import Callable, Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import deque


class RecoveryStrategy(Enum):
    """Recovery strategies"""
    RESTART = "restart"
    RECONNECT = "reconnect"
    RESET = "reset"
    FAILOVER = "failover"
    MANUAL = "manual"


@dataclass
class RecoveryAttempt:
    """Record of a recovery attempt"""
    component: str
    strategy: RecoveryStrategy
    timestamp: float
    success: bool
    duration: float
    reason: Optional[str] = None
    error: Optional[str] = None


@dataclass
class RecoveryConfig:
    """Configuration for recovery of a component"""
    strategy: RecoveryStrategy
    recovery_func: Callable
    max_attempts: int = 3
    base_delay: float = 1.0
    timeout: float = 60.0
    dependencies: List[str] = field(default_factory=list)


class RecoveryOrchestrator:
    """
    Automatic recovery orchestration
    
    Coordinates recovery across components with:
    - Multiple recovery strategies (restart, reconnect, reset, failover)
    - Exponential backoff between attempts
    - Dependency-aware recovery ordering
    - Recovery attempt tracking and history
    - Circuit breaker to prevent infinite recovery loops
    
    Example:
        orchestrator = RecoveryOrchestrator()
        
        # Register recovery strategy
        async def restart_database():
            await database.stop()
            await asyncio.sleep(1.0)
            await database.start()
            return database.is_healthy()
        
        orchestrator.register_strategy(
            "database",
            RecoveryStrategy.RESTART,
            restart_database
        )
        
        # Attempt recovery
        success = await orchestrator.attempt_recovery("database")
    """
    
    def __init__(
        self,
        max_recovery_attempts: int = 3,
        recovery_timeout: float = 60.0,
        backoff_multiplier: float = 2.0,
        history_size: int = 100
    ):
        """
        Initialize recovery orchestrator
        
        Args:
            max_recovery_attempts: Default max attempts per component
            recovery_timeout: Default timeout for recovery operations
            backoff_multiplier: Multiplier for exponential backoff
            history_size: Number of historical attempts to keep
        """
        if max_recovery_attempts < 1:
            raise ValueError("max_recovery_attempts must be at least 1")
        if recovery_timeout <= 0:
            raise ValueError("recovery_timeout must be positive")
        if backoff_multiplier < 1.0:
            raise ValueError("backoff_multiplier must be >= 1.0")
        
        self.max_recovery_attempts = max_recovery_attempts
        self.recovery_timeout = recovery_timeout
        self.backoff_multiplier = backoff_multiplier
        self.history_size = history_size
        
        # Recovery configurations
        self.strategies: Dict[str, RecoveryConfig] = {}
        
        # Recovery attempt tracking
        self.attempt_counts: Dict[str, int] = {}
        self.last_attempt_time: Dict[str, float] = {}
        
        # Recovery history
        self.history: deque = deque(maxlen=history_size)
        
        # Currently recovering components
        self.recovery_in_progress: set = set()
    
    def register_strategy(
        self,
        component: str,
        strategy: RecoveryStrategy,
        recovery_func: Callable,
        max_attempts: Optional[int] = None,
        base_delay: float = 1.0,
        timeout: Optional[float] = None,
        dependencies: Optional[List[str]] = None
    ) -> None:
        """
        Register recovery strategy for component
        
        Args:
            component: Component name
            strategy: Recovery strategy to use
            recovery_func: Async function that performs recovery
            max_attempts: Max recovery attempts (overrides default)
            base_delay: Base delay between attempts in seconds
            timeout: Recovery timeout (overrides default)
            dependencies: Components that must be healthy first
        """
        self.strategies[component] = RecoveryConfig(
            strategy=strategy,
            recovery_func=recovery_func,
            max_attempts=max_attempts or self.max_recovery_attempts,
            base_delay=base_delay,
            timeout=timeout or self.recovery_timeout,
            dependencies=dependencies or []
        )
        
        self.attempt_counts[component] = 0
    
    async def attempt_recovery(
        self,
        component: str,
        reason: Optional[str] = None,
        force: bool = False
    ) -> bool:
        """
        Attempt to recover component
        
        Args:
            component: Component name
            reason: Reason for recovery attempt
            force: Force recovery even if max attempts exceeded
            
        Returns:
            True if recovery successful, False otherwise
        """
        if component not in self.strategies:
            return False
        
        # Check if already recovering
        if component in self.recovery_in_progress:
            return False
        
        config = self.strategies[component]
        attempts = self.attempt_counts[component]
        
        # Check attempt limit
        if not force and attempts >= config.max_attempts:
            return False
        
        self.recovery_in_progress.add(component)
        start_time = time.time()
        
        try:
            # Calculate backoff delay
            if attempts > 0:
                backoff = config.base_delay * (self.backoff_multiplier ** (attempts - 1))
                
                # Check if we need to wait
                last_attempt = self.last_attempt_time.get(component, 0)
                elapsed = time.time() - last_attempt
                
                if elapsed < backoff:
                    await asyncio.sleep(backoff - elapsed)
            
            # Attempt recovery
            recovery_func = config.recovery_func
            
            success = await asyncio.wait_for(
                recovery_func(),
                timeout=config.timeout
            )
            
            duration = time.time() - start_time
            
            # Record attempt
            attempt = RecoveryAttempt(
                component=component,
                strategy=config.strategy,
                timestamp=time.time(),
                success=success,
                duration=duration,
                reason=reason
            )
            
            self.history.append(attempt)
            self.last_attempt_time[component] = time.time()
            
            if success:
                # Reset attempt count on success
                self.attempt_counts[component] = 0
                return True
            else:
                # Increment attempt count
                self.attempt_counts[component] = attempts + 1
                return False
            
        except asyncio.TimeoutError:
            duration = time.time() - start_time
            
            # Record timeout
            attempt = RecoveryAttempt(
                component=component,
                strategy=config.strategy,
                timestamp=time.time(),
                success=False,
                duration=duration,
                reason=reason,
                error="Recovery timeout"
            )
            
            self.history.append(attempt)
            self.last_attempt_time[component] = time.time()
            self.attempt_counts[component] = attempts + 1
            
            return False
            
        except Exception as e:
            duration = time.time() - start_time
            
            # Record error
            attempt = RecoveryAttempt(
                component=component,
                strategy=config.strategy,
                timestamp=time.time(),
                success=False,
                duration=duration,
                reason=reason,
                error=str(e)
            )
            
            self.history.append(attempt)
            self.last_attempt_time[component] = time.time()
            self.attempt_counts[component] = attempts + 1
            
            return False
            
        finally:
            self.recovery_in_progress.discard(component)
    
    async def recover_dependencies(
        self,
        component: str,
        reason: Optional[str] = None
    ) -> Dict[str, bool]:
        """
        Recover component and all its dependencies
        
        Args:
            component: Component name
            reason: Reason for recovery
            
        Returns:
            Dictionary mapping component names to recovery success
        """
        if component not in self.strategies:
            return {component: False}
        
        config = self.strategies[component]
        results = {}
        
        # Recover dependencies first
        for dep in config.dependencies:
            if dep in self.strategies:
                success = await self.attempt_recovery(dep, f"Dependency of {component}")
                results[dep] = success
                
                # If critical dependency fails, don't recover component
                if not success:
                    results[component] = False
                    return results
        
        # Recover the component itself
        success = await self.attempt_recovery(component, reason)
        results[component] = success
        
        return results
    
    def reset_attempts(self, component: Optional[str] = None) -> None:
        """
        Reset recovery attempt counts
        
        Args:
            component: Specific component to reset (None for all)
        """
        if component is not None:
            if component in self.attempt_counts:
                self.attempt_counts[component] = 0
        else:
            self.attempt_counts = {k: 0 for k in self.attempt_counts}
    
    def get_recovery_status(self, component: str) -> Dict[str, Any]:
        """
        Get recovery status for component
        
        Args:
            component: Component name
            
        Returns:
            Dictionary with recovery status
        """
        if component not in self.strategies:
            return {"registered": False}
        
        config = self.strategies[component]
        attempts = self.attempt_counts[component]
        
        # Get recent attempts
        recent_attempts = [
            a for a in self.history
            if a.component == component
        ][-5:]  # Last 5 attempts
        
        # Calculate success rate
        if recent_attempts:
            success_count = sum(1 for a in recent_attempts if a.success)
            success_rate = success_count / len(recent_attempts)
        else:
            success_rate = 0.0
        
        return {
            "registered": True,
            "strategy": config.strategy.value,
            "attempts": attempts,
            "max_attempts": config.max_attempts,
            "can_retry": attempts < config.max_attempts,
            "recovering": component in self.recovery_in_progress,
            "recent_attempts": len(recent_attempts),
            "success_rate": success_rate,
            "last_attempt": (
                time.time() - self.last_attempt_time[component]
                if component in self.last_attempt_time else None
            )
        }
    
    def get_recent_recoveries(self, limit: int = 10) -> List[RecoveryAttempt]:
        """
        Get recent recovery attempts
        
        Args:
            limit: Maximum number of attempts to return
            
        Returns:
            List of recent recovery attempts
        """
        return list(self.history)[-limit:]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "registered_components": list(self.strategies.keys()),
            "recovery_in_progress": list(self.recovery_in_progress),
            "total_attempts": sum(self.attempt_counts.values()),
            "components": {
                component: self.get_recovery_status(component)
                for component in self.strategies.keys()
            },
            "recent_recoveries": [
                {
                    "component": a.component,
                    "strategy": a.strategy.value,
                    "success": a.success,
                    "duration": a.duration,
                    "ago_seconds": time.time() - a.timestamp,
                    "reason": a.reason,
                    "error": a.error
                }
                for a in list(self.history)[-10:]
            ]
        }
