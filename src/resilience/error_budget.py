"""
Error Budget - Integration #16

Implements error budget tracking to prevent infinite retry loops
and provide rate limiting on errors per component.
"""

import asyncio
import logging
import time
from collections import deque
from typing import Dict, Deque, Optional, Any

logger = logging.getLogger(__name__)


class ErrorBudgetExhaustedError(Exception):
    """Raised when error budget is exhausted"""
    pass


class ErrorBudget:
    """
    Error budget tracker with rolling time windows.
    
    Tracks error rates per component and prevents excessive errors
    within a time window. Useful for:
    - Preventing infinite retry loops
    - Rate limiting errors
    - Alerting on error spikes
    
    Example:
        budget = ErrorBudget(
            max_errors=100,
            time_window=3600.0  # 1 hour
        )
        
        if budget.consume("llm_generation"):
            # Proceed with operation
            pass
        else:
            # Budget exhausted, use fallback
            logger.error("Error budget exhausted!")
    """
    
    def __init__(
        self,
        max_errors: int = 100,
        time_window: float = 3600.0,  # 1 hour in seconds
        alert_threshold: float = 0.8  # Alert at 80%
    ):
        """
        Initialize error budget tracker.
        
        Args:
            max_errors: Maximum errors allowed in time window
            time_window: Time window in seconds for rolling count
            alert_threshold: Fraction of budget that triggers alert (0-1)
        """
        self.max_errors = max_errors
        self.time_window = time_window
        self.alert_threshold = alert_threshold
        
        # Track errors per component with timestamps
        self.errors: Dict[str, Deque[float]] = {}
        
        # Track statistics
        self.stats = {
            "total_consumed": 0,
            "total_exhaustions": 0,
            "alerts_triggered": 0,
        }
        
        logger.info(
            f"Error budget initialized: max={max_errors}, window={time_window}s"
        )
    
    def consume(
        self,
        component: str,
        error_cost: int = 1,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Consume error budget for a component.
        
        Args:
            component: Component name (e.g., "llm_generation")
            error_cost: How much budget to consume (default=1)
            metadata: Optional metadata about the error
            
        Returns:
            True if budget consumed successfully, False if exhausted
        """
        # Initialize component if needed
        if component not in self.errors:
            self.errors[component] = deque()
        
        now = time.time()
        
        # Clean up old errors outside time window
        self._cleanup(component, now)
        
        # Check if budget available
        current_errors = len(self.errors[component])
        
        if current_errors + error_cost > self.max_errors:
            self.stats["total_exhaustions"] += 1
            logger.error(
                f"❌ Error budget exhausted for '{component}': "
                f"{current_errors}/{self.max_errors} errors in last "
                f"{self.time_window}s"
            )
            return False
        
        # Consume budget
        for _ in range(error_cost):
            self.errors[component].append(now)
        
        self.stats["total_consumed"] += error_cost
        
        # Check if alert threshold reached
        new_error_count = len(self.errors[component])
        usage_rate = new_error_count / self.max_errors
        
        if usage_rate >= self.alert_threshold:
            self.stats["alerts_triggered"] += 1
            logger.warning(
                f"⚠️  Error budget alert for '{component}': "
                f"{new_error_count}/{self.max_errors} "
                f"({usage_rate*100:.1f}% used)"
            )
        
        return True
    
    def remaining(self, component: str) -> int:
        """
        Get remaining error budget for component.
        
        Args:
            component: Component name
            
        Returns:
            Number of errors remaining in budget
        """
        if component not in self.errors:
            return self.max_errors
        
        now = time.time()
        self._cleanup(component, now)
        
        current_errors = len(self.errors[component])
        return max(0, self.max_errors - current_errors)
    
    def usage_rate(self, component: str) -> float:
        """
        Get error budget usage rate for component.
        
        Args:
            component: Component name
            
        Returns:
            Usage rate from 0.0 to 1.0
        """
        if component not in self.errors:
            return 0.0
        
        now = time.time()
        self._cleanup(component, now)
        
        current_errors = len(self.errors[component])
        return current_errors / self.max_errors
    
    def reset(self, component: Optional[str] = None):
        """
        Reset error budget.
        
        Args:
            component: If provided, reset only this component.
                      If None, reset all components.
        """
        if component:
            if component in self.errors:
                self.errors[component].clear()
                logger.info(f"Reset error budget for '{component}'")
        else:
            self.errors.clear()
            logger.info("Reset all error budgets")
    
    def _cleanup(self, component: str, now: float):
        """
        Remove errors outside the time window.
        
        Args:
            component: Component name
            now: Current timestamp
        """
        if component not in self.errors:
            return
        
        cutoff = now - self.time_window
        errors = self.errors[component]
        
        # Remove old errors
        while errors and errors[0] < cutoff:
            errors.popleft()
    
    def get_status(self, component: Optional[str] = None) -> Dict[str, Any]:
        """
        Get error budget status.
        
        Args:
            component: If provided, get status for this component only.
                      If None, get status for all components.
            
        Returns:
            Dictionary with budget status
        """
        now = time.time()
        
        if component:
            self._cleanup(component, now)
            
            return {
                "component": component,
                "current_errors": len(self.errors.get(component, [])),
                "max_errors": self.max_errors,
                "remaining": self.remaining(component),
                "usage_rate": self.usage_rate(component),
                "is_exhausted": self.remaining(component) == 0,
            }
        else:
            # Status for all components
            components = {}
            for comp in self.errors:
                self._cleanup(comp, now)
                components[comp] = {
                    "current_errors": len(self.errors[comp]),
                    "remaining": self.remaining(comp),
                    "usage_rate": self.usage_rate(comp),
                }
            
            return {
                "max_errors": self.max_errors,
                "time_window": self.time_window,
                "alert_threshold": self.alert_threshold,
                "components": components,
                "total_consumed": self.stats["total_consumed"],
                "total_exhaustions": self.stats["total_exhaustions"],
                "alerts_triggered": self.stats["alerts_triggered"],
            }


if __name__ == "__main__":
    # Quick test
    async def test():
        print("Testing Error Budget\n")
        
        # Test 1: Normal consumption
        print("Test 1: Normal budget consumption")
        budget = ErrorBudget(max_errors=5, time_window=10.0)
        
        for i in range(5):
            consumed = budget.consume("test_component")
            print(f"  Consume {i+1}: {consumed}, remaining={budget.remaining('test_component')}")
        
        # Test 2: Exhaustion
        print("\nTest 2: Budget exhaustion")
        consumed = budget.consume("test_component")
        print(f"  Consume 6: {consumed} (should be False)")
        
        # Test 3: Time window expiration
        print("\nTest 3: Time window expiration")
        print(f"  Waiting {budget.time_window + 1}s for window to expire...")
        await asyncio.sleep(budget.time_window + 1)
        
        consumed = budget.consume("test_component")
        print(f"  Consume after wait: {consumed}, remaining={budget.remaining('test_component')}")
        
        # Test 4: Multiple components
        print("\nTest 4: Multiple components")
        budget2 = ErrorBudget(max_errors=10, time_window=60.0)
        
        budget2.consume("component_a", error_cost=3)
        budget2.consume("component_b", error_cost=5)
        budget2.consume("component_a", error_cost=2)
        
        print(f"  Component A: {budget2.remaining('component_a')} remaining")
        print(f"  Component B: {budget2.remaining('component_b')} remaining")
        
        # Test 5: Alert threshold
        print("\nTest 5: Alert threshold")
        budget3 = ErrorBudget(max_errors=10, time_window=60.0, alert_threshold=0.7)
        
        for i in range(8):
            budget3.consume("alert_test")
            print(f"  Consumed {i+1}, usage={budget3.usage_rate('alert_test')*100:.0f}%")
        
        # Print final status
        print("\n📊 Final Status:")
        status = budget3.get_status()
        print(f"  Total consumed: {status['total_consumed']}")
        print(f"  Total exhaustions: {status['total_exhaustions']}")
        print(f"  Alerts triggered: {status['alerts_triggered']}")
        print(f"  Components: {list(status['components'].keys())}")
    
    asyncio.run(test())
