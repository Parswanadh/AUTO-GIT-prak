"""
Cost Tracker

Tracks and limits spending per component with rolling time windows and budget enforcement.
"""

import time
from typing import Dict, Any, Optional, Tuple
from collections import deque
from dataclasses import dataclass


class BudgetExceededError(Exception):
    """Raised when budget is exceeded"""
    pass


@dataclass
class ComponentBudget:
    """Budget information for a component"""
    name: str
    budget: float
    spent: float
    remaining: float
    spending_rate: float  # Per hour
    projected_24h: float
    alert_threshold: float
    is_over_budget: bool
    is_near_limit: bool


@dataclass
class CostStats:
    """Overall cost statistics"""
    total_budget: float
    total_spent: float
    total_remaining: float
    component_count: int
    over_budget_count: int
    near_limit_count: int
    total_transactions: int


class CostTracker:
    """
    Cost tracker with per-component budgets
    
    Tracks spending per component with:
    - Rolling time window for budget periods
    - Per-component budget limits
    - Alert thresholds for approaching limits
    - Automatic cleanup of old costs
    - Spending rate calculation
    
    Example:
        tracker = CostTracker(
            default_budget=10.0,  # $10 per day
            time_window=86400.0   # 24 hours
        )
        
        # Record cost
        if tracker.record_cost("llm_generation", 0.05):
            # Cost recorded, under budget
            pass
        else:
            # Budget exceeded
            raise BudgetExceededError()
        
        # Check remaining
        remaining = tracker.remaining_budget("llm_generation")
    """
    
    def __init__(
        self,
        default_budget: float,
        time_window: float = 86400.0,  # 24 hours
        alert_threshold: float = 0.8,  # 80%
        auto_cleanup: bool = True
    ):
        """
        Initialize cost tracker
        
        Args:
            default_budget: Default budget per component (USD)
            time_window: Time window in seconds (default: 24 hours)
            alert_threshold: Alert when usage exceeds this fraction (0.0-1.0)
            auto_cleanup: Automatically clean up old costs
        """
        if default_budget <= 0:
            raise ValueError("default_budget must be positive")
        if time_window <= 0:
            raise ValueError("time_window must be positive")
        if not (0 < alert_threshold <= 1):
            raise ValueError("alert_threshold must be between 0 and 1")
        
        self.default_budget = default_budget
        self.time_window = time_window
        self.alert_threshold = alert_threshold
        self.auto_cleanup = auto_cleanup
        
        # Per-component costs: {component: deque[(timestamp, cost, metadata)]}
        self.costs: Dict[str, deque] = {}
        
        # Per-component budgets (can override default)
        self.budgets: Dict[str, float] = {}
        
        # Statistics
        self._total_transactions = 0
        self._last_cleanup: Dict[str, float] = {}
    
    def _cleanup(self, component: str) -> None:
        """Remove costs outside the time window"""
        if component not in self.costs:
            return
        
        now = time.time()
        cutoff = now - self.time_window
        
        # Remove old costs
        while self.costs[component] and self.costs[component][0][0] < cutoff:
            self.costs[component].popleft()
        
        self._last_cleanup[component] = now
    
    def _maybe_cleanup(self, component: str) -> None:
        """Cleanup if auto_cleanup enabled and time has passed"""
        if not self.auto_cleanup:
            return
        
        # Cleanup every minute max
        last = self._last_cleanup.get(component, 0)
        if time.time() - last > 60.0:
            self._cleanup(component)
    
    def _get_spending(self, component: str) -> float:
        """Get total spending for component in current window"""
        if component not in self.costs:
            return 0.0
        
        return sum(cost for _, cost, _ in self.costs[component])
    
    def record_cost(
        self,
        component: str,
        cost: float,
        metadata: Optional[Dict[str, Any]] = None,
        enforce_budget: bool = True
    ) -> bool:
        """
        Record a cost
        
        Args:
            component: Component name
            cost: Cost in USD
            metadata: Optional metadata (e.g., model, tokens, etc.)
            enforce_budget: If True, reject if over budget
            
        Returns:
            True if recorded, False if budget exceeded (when enforce_budget=True)
        """
        if cost < 0:
            raise ValueError("Cost cannot be negative")
        
        # Initialize component if needed
        if component not in self.costs:
            self.costs[component] = deque()
            self.budgets[component] = self.default_budget
        
        # Cleanup old costs
        self._maybe_cleanup(component)
        
        # Check budget
        current_spending = self._get_spending(component)
        budget = self.budgets[component]
        
        if enforce_budget and current_spending + cost > budget:
            return False
        
        # Record cost
        self.costs[component].append((
            time.time(),
            cost,
            metadata or {}
        ))
        
        self._total_transactions += 1
        return True
    
    def remaining_budget(self, component: str) -> float:
        """
        Get remaining budget for component
        
        Args:
            component: Component name
            
        Returns:
            Remaining budget in USD
        """
        if component not in self.costs:
            return self.budgets.get(component, self.default_budget)
        
        self._maybe_cleanup(component)
        spending = self._get_spending(component)
        budget = self.budgets.get(component, self.default_budget)
        
        return max(0.0, budget - spending)
    
    def set_budget(self, component: str, budget: float) -> None:
        """
        Set custom budget for component
        
        Args:
            component: Component name
            budget: Budget in USD
        """
        if budget <= 0:
            raise ValueError("Budget must be positive")
        
        self.budgets[component] = budget
    
    def get_component_status(self, component: str) -> ComponentBudget:
        """
        Get detailed status for component
        
        Args:
            component: Component name
            
        Returns:
            ComponentBudget with detailed information
        """
        if component not in self.costs:
            budget = self.budgets.get(component, self.default_budget)
            return ComponentBudget(
                name=component,
                budget=budget,
                spent=0.0,
                remaining=budget,
                spending_rate=0.0,
                projected_24h=0.0,
                alert_threshold=self.alert_threshold,
                is_over_budget=False,
                is_near_limit=False
            )
        
        self._maybe_cleanup(component)
        
        spent = self._get_spending(component)
        budget = self.budgets.get(component, self.default_budget)
        remaining = max(0.0, budget - spent)
        
        # Calculate spending rate (per hour)
        spending_rate = 0.0
        if self.costs[component]:
            oldest_time = self.costs[component][0][0]
            time_span = time.time() - oldest_time
            if time_span > 0:
                spending_rate = (spent / time_span) * 3600  # Per hour
        
        # Project 24h spending
        projected_24h = spending_rate * 24
        
        # Check thresholds
        usage_ratio = spent / budget if budget > 0 else 0.0
        is_over_budget = spent > budget
        is_near_limit = usage_ratio >= self.alert_threshold
        
        return ComponentBudget(
            name=component,
            budget=budget,
            spent=spent,
            remaining=remaining,
            spending_rate=spending_rate,
            projected_24h=projected_24h,
            alert_threshold=self.alert_threshold,
            is_over_budget=is_over_budget,
            is_near_limit=is_near_limit
        )
    
    def get_all_components(self) -> Dict[str, ComponentBudget]:
        """Get status for all components"""
        components = {}
        
        # Get all component names
        all_names = set(self.costs.keys()) | set(self.budgets.keys())
        
        for component in all_names:
            components[component] = self.get_component_status(component)
        
        return components
    
    def get_overall_stats(self) -> CostStats:
        """Get overall statistics"""
        all_components = self.get_all_components()
        
        total_budget = sum(c.budget for c in all_components.values())
        total_spent = sum(c.spent for c in all_components.values())
        total_remaining = sum(c.remaining for c in all_components.values())
        over_budget_count = sum(1 for c in all_components.values() if c.is_over_budget)
        near_limit_count = sum(1 for c in all_components.values() if c.is_near_limit)
        
        return CostStats(
            total_budget=total_budget,
            total_spent=total_spent,
            total_remaining=total_remaining,
            component_count=len(all_components),
            over_budget_count=over_budget_count,
            near_limit_count=near_limit_count,
            total_transactions=self._total_transactions
        )
    
    def reset(self, component: Optional[str] = None) -> None:
        """
        Reset cost tracking
        
        Args:
            component: Specific component to reset (None for all)
        """
        if component is not None:
            if component in self.costs:
                self.costs[component].clear()
        else:
            self.costs.clear()
    
    def force_cleanup_all(self) -> int:
        """
        Force cleanup of all components
        
        Returns:
            Number of costs removed
        """
        removed = 0
        
        for component in list(self.costs.keys()):
            before = len(self.costs[component])
            self._cleanup(component)
            after = len(self.costs[component])
            removed += (before - after)
        
        return removed
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        overall = self.get_overall_stats()
        components = self.get_all_components()
        
        return {
            "overall": {
                "total_budget": overall.total_budget,
                "total_spent": overall.total_spent,
                "total_remaining": overall.total_remaining,
                "component_count": overall.component_count,
                "over_budget_count": overall.over_budget_count,
                "near_limit_count": overall.near_limit_count,
                "total_transactions": overall.total_transactions
            },
            "components": {
                name: {
                    "budget": comp.budget,
                    "spent": comp.spent,
                    "remaining": comp.remaining,
                    "spending_rate_per_hour": comp.spending_rate,
                    "projected_24h": comp.projected_24h,
                    "is_over_budget": comp.is_over_budget,
                    "is_near_limit": comp.is_near_limit,
                    "usage_percentage": (comp.spent / comp.budget * 100) if comp.budget > 0 else 0.0
                }
                for name, comp in components.items()
            }
        }
