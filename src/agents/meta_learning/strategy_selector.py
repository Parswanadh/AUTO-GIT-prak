"""
Meta-Learning System for Strategy Selection.

Tracks which strategies work best for different problem types and contexts,
enabling the system to learn from past experiences and continuously improve
decision-making.

Key Features:
1. Performance tracking per strategy
2. Context-aware strategy selection
3. Multi-armed bandit optimization (Thompson Sampling)
4. Historical pattern learning
5. Adaptive exploration/exploitation

This integrates with:
- Integration #4: Multi-Critic Consensus (strategy selection)
- Integration #6: LangGraph Checkpointing (persistent storage)
- Integration #7: Quality Assessment (performance metrics)
"""

import json
import logging
import time
import random
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict
import math

logger = logging.getLogger(__name__)


@dataclass
class StrategyPerformance:
    """Performance metrics for a strategy."""
    strategy_name: str
    total_attempts: int = 0
    successful_attempts: int = 0
    total_quality_score: float = 0.0
    total_latency: float = 0.0
    total_tokens: int = 0
    
    # Thompson Sampling parameters (Beta distribution)
    alpha: float = 1.0  # Successes + 1 (prior)
    beta: float = 1.0   # Failures + 1 (prior)
    
    # Context-specific performance
    context_performance: Dict[str, Dict[str, float]] = field(default_factory=dict)
    
    # Last updated
    last_used: float = 0.0
    
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_attempts == 0:
            return 0.0
        return self.successful_attempts / self.total_attempts
    
    def avg_quality(self) -> float:
        """Calculate average quality score."""
        if self.successful_attempts == 0:
            return 0.0
        return self.total_quality_score / self.successful_attempts
    
    def avg_latency(self) -> float:
        """Calculate average latency."""
        if self.total_attempts == 0:
            return 0.0
        return self.total_latency / self.total_attempts
    
    def avg_tokens_per_attempt(self) -> float:
        """Calculate average tokens per attempt."""
        if self.total_attempts == 0:
            return 0.0
        return self.total_tokens / self.total_attempts


@dataclass
class StrategyRecommendation:
    """Strategy selection recommendation."""
    strategy_name: str
    confidence: float  # 0-1
    expected_quality: float  # 0-10
    expected_latency: float  # seconds
    reasoning: str
    
    # Alternative strategies
    alternatives: List[Tuple[str, float]] = field(default_factory=list)


@dataclass
class ProblemContext:
    """Context for problem classification."""
    domain: str
    complexity: str  # "simple", "medium", "complex"
    task_type: str  # "code_generation", "research", "analysis"
    requires_creativity: bool = False
    requires_accuracy: bool = False
    time_sensitive: bool = False


class MetaLearningStrategySelector:
    """
    Meta-learning system for adaptive strategy selection.
    
    Uses multi-armed bandit optimization (Thompson Sampling) to balance
    exploration of new strategies with exploitation of proven ones.
    
    Learns from:
    - Success/failure rates
    - Quality scores
    - Latency patterns
    - Context-specific performance
    
    Usage:
        selector = MetaLearningStrategySelector()
        
        # Get recommendation
        context = ProblemContext(domain="ML", complexity="medium")
        rec = selector.recommend_strategy(context, available_strategies)
        
        # Record outcome
        selector.record_outcome(
            strategy="multi_critic",
            context=context,
            success=True,
            quality_score=8.5,
            latency=15.2,
            tokens=2000
        )
        
        # Learn over time
        await selector.learn_from_history()
    """
    
    def __init__(
        self,
        storage_path: str = "./data/meta_learning",
        exploration_rate: float = 0.1,  # 10% exploration
        min_attempts_per_strategy: int = 5,  # Minimum trials before exploitation
        enable_context_learning: bool = True
    ):
        """
        Initialize meta-learning selector.
        
        Args:
            storage_path: Path to store performance data
            exploration_rate: Probability of random exploration (0-1)
            min_attempts_per_strategy: Min trials before trusting statistics
            enable_context_learning: Learn context-specific patterns
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.exploration_rate = exploration_rate
        self.min_attempts_per_strategy = min_attempts_per_strategy
        self.enable_context_learning = enable_context_learning
        
        # Strategy performance tracking
        self.strategies: Dict[str, StrategyPerformance] = {}
        
        # Global statistics
        self.total_selections = 0
        self.total_successes = 0
        
        # Load existing data
        self._load_performance_data()
        
        logger.info(
            f"MetaLearningStrategySelector initialized "
            f"({len(self.strategies)} strategies tracked, "
            f"exploration={exploration_rate:.1%})"
        )
    
    def recommend_strategy(
        self,
        context: ProblemContext,
        available_strategies: List[str],
        force_exploration: bool = False
    ) -> StrategyRecommendation:
        """
        Recommend best strategy for given context.
        
        Uses Thompson Sampling for exploration/exploitation balance.
        
        Args:
            context: Problem context
            available_strategies: List of strategy names to choose from
            force_exploration: Force random exploration
        
        Returns:
            StrategyRecommendation with selected strategy and reasoning
        """
        self.total_selections += 1
        
        # Ensure all strategies are tracked
        for strategy in available_strategies:
            if strategy not in self.strategies:
                self.strategies[strategy] = StrategyPerformance(
                    strategy_name=strategy,
                    last_used=time.time()
                )
        
        # 1. Random exploration (ε-greedy)
        if force_exploration or random.random() < self.exploration_rate:
            strategy = random.choice(available_strategies)
            return StrategyRecommendation(
                strategy_name=strategy,
                confidence=0.5,
                expected_quality=6.0,  # Neutral
                expected_latency=10.0,  # Average
                reasoning=f"Random exploration ({self.exploration_rate:.1%} rate)"
            )
        
        # 2. Thompson Sampling for exploitation
        strategy_scores = {}
        
        for strategy in available_strategies:
            perf = self.strategies[strategy]
            
            # Sample from Beta distribution
            sampled_success_rate = random.betavariate(perf.alpha, perf.beta)
            
            # Adjust for context if learning enabled
            context_boost = 0.0
            if self.enable_context_learning:
                context_boost = self._get_context_boost(strategy, context)
            
            # Calculate score (success rate + context boost)
            score = sampled_success_rate + context_boost
            
            strategy_scores[strategy] = score
        
        # Select best strategy
        best_strategy = max(strategy_scores, key=strategy_scores.get)
        best_perf = self.strategies[best_strategy]
        
        # Calculate confidence
        confidence = self._calculate_confidence(best_perf)
        
        # Get alternatives
        sorted_strategies = sorted(
            strategy_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        alternatives = [(s, score) for s, score in sorted_strategies[1:4]]
        
        # Build reasoning
        reasoning = self._build_reasoning(best_strategy, context, confidence)
        
        return StrategyRecommendation(
            strategy_name=best_strategy,
            confidence=confidence,
            expected_quality=best_perf.avg_quality() or 6.0,
            expected_latency=best_perf.avg_latency() or 10.0,
            reasoning=reasoning,
            alternatives=alternatives
        )
    
    def record_outcome(
        self,
        strategy: str,
        context: ProblemContext,
        success: bool,
        quality_score: float = 0.0,
        latency: float = 0.0,
        tokens: int = 0
    ) -> None:
        """
        Record outcome of strategy execution.
        
        Args:
            strategy: Strategy name
            context: Problem context
            success: Whether strategy succeeded
            quality_score: Quality score (0-10, if successful)
            latency: Execution time in seconds
            tokens: Tokens used
        """
        if strategy not in self.strategies:
            self.strategies[strategy] = StrategyPerformance(strategy_name=strategy)
        
        perf = self.strategies[strategy]
        
        # Update global statistics
        perf.total_attempts += 1
        perf.last_used = time.time()
        perf.total_latency += latency
        perf.total_tokens += tokens
        
        if success:
            perf.successful_attempts += 1
            perf.total_quality_score += quality_score
            self.total_successes += 1
            
            # Update Thompson Sampling parameters
            perf.alpha += 1.0  # Increment successes
        else:
            # Update Thompson Sampling parameters
            perf.beta += 1.0  # Increment failures
        
        # Update context-specific performance
        if self.enable_context_learning:
            self._update_context_performance(strategy, context, success, quality_score)
        
        # Periodic save
        if self.total_selections % 10 == 0:
            self._save_performance_data()
        
        logger.info(
            f"Recorded outcome: {strategy} "
            f"({'✓' if success else '✗'}, "
            f"quality={quality_score:.1f}, "
            f"success_rate={perf.success_rate():.1%})"
        )
    
    def _get_context_boost(
        self,
        strategy: str,
        context: ProblemContext
    ) -> float:
        """
        Calculate context-specific performance boost.
        
        Args:
            strategy: Strategy name
            context: Problem context
        
        Returns:
            Boost value (0-0.2)
        """
        perf = self.strategies[strategy]
        
        # Build context key
        context_key = f"{context.domain}_{context.complexity}_{context.task_type}"
        
        if context_key not in perf.context_performance:
            return 0.0
        
        context_perf = perf.context_performance[context_key]
        success_rate = context_perf.get('success_rate', 0.0)
        attempts = context_perf.get('attempts', 0)
        
        # Only trust context boost if sufficient data
        if attempts < 3:
            return 0.0
        
        # Boost: up to +0.2 for perfect context success rate
        return min(0.2, success_rate * 0.2)
    
    def _update_context_performance(
        self,
        strategy: str,
        context: ProblemContext,
        success: bool,
        quality_score: float
    ) -> None:
        """Update context-specific performance tracking."""
        perf = self.strategies[strategy]
        
        context_key = f"{context.domain}_{context.complexity}_{context.task_type}"
        
        if context_key not in perf.context_performance:
            perf.context_performance[context_key] = {
                'attempts': 0,
                'successes': 0,
                'success_rate': 0.0,
                'avg_quality': 0.0,
                'total_quality': 0.0
            }
        
        ctx = perf.context_performance[context_key]
        ctx['attempts'] += 1
        
        if success:
            ctx['successes'] += 1
            ctx['total_quality'] += quality_score
        
        ctx['success_rate'] = ctx['successes'] / ctx['attempts']
        ctx['avg_quality'] = ctx['total_quality'] / max(1, ctx['successes'])
    
    def _calculate_confidence(self, perf: StrategyPerformance) -> float:
        """
        Calculate confidence in strategy selection.
        
        Based on:
        - Number of attempts (more data = higher confidence)
        - Success rate (higher = higher confidence)
        - Variance (lower = higher confidence)
        
        Args:
            perf: Strategy performance data
        
        Returns:
            Confidence score 0-1
        """
        if perf.total_attempts < self.min_attempts_per_strategy:
            # Low confidence if insufficient data
            return 0.3 + (perf.total_attempts / self.min_attempts_per_strategy) * 0.2
        
        # Base confidence from success rate
        base_confidence = perf.success_rate()
        
        # Boost confidence with more data (diminishing returns)
        data_boost = min(0.2, math.log10(perf.total_attempts) * 0.1)
        
        return min(1.0, base_confidence + data_boost)
    
    def _build_reasoning(
        self,
        strategy: str,
        context: ProblemContext,
        confidence: float
    ) -> str:
        """Build human-readable reasoning for selection."""
        perf = self.strategies[strategy]
        
        if perf.total_attempts < self.min_attempts_per_strategy:
            return (
                f"Selected '{strategy}' based on limited data "
                f"({perf.total_attempts} attempts). Building confidence."
            )
        
        reasoning_parts = [
            f"Selected '{strategy}' with {confidence:.0%} confidence"
        ]
        
        # Add success rate
        if perf.total_attempts > 0:
            reasoning_parts.append(
                f"Success rate: {perf.success_rate():.1%} ({perf.successful_attempts}/{perf.total_attempts})"
            )
        
        # Add quality info
        if perf.successful_attempts > 0:
            reasoning_parts.append(f"Avg quality: {perf.avg_quality():.1f}/10")
        
        # Add context info
        context_key = f"{context.domain}_{context.complexity}_{context.task_type}"
        if context_key in perf.context_performance:
            ctx = perf.context_performance[context_key]
            if ctx['attempts'] >= 3:
                reasoning_parts.append(
                    f"Good fit for {context.domain}/{context.complexity} "
                    f"({ctx['success_rate']:.1%} success)"
                )
        
        return ". ".join(reasoning_parts)
    
    async def learn_from_history(
        self,
        history_data: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Analyze historical performance and extract patterns.
        
        Args:
            history_data: Optional historical data to learn from
        
        Returns:
            Learning summary with insights
        """
        logger.info("🧠 Analyzing historical performance patterns...")
        
        insights = {
            "total_strategies": len(self.strategies),
            "total_attempts": self.total_selections,
            "global_success_rate": self.total_successes / max(1, self.total_selections),
            "best_strategies": [],
            "worst_strategies": [],
            "context_patterns": [],
            "recommendations": []
        }
        
        # Find best strategies
        sorted_strategies = sorted(
            self.strategies.values(),
            key=lambda p: (p.success_rate(), p.total_attempts),
            reverse=True
        )
        
        insights["best_strategies"] = [
            {
                "name": p.strategy_name,
                "success_rate": p.success_rate(),
                "avg_quality": p.avg_quality(),
                "attempts": p.total_attempts
            }
            for p in sorted_strategies[:3]
            if p.total_attempts >= self.min_attempts_per_strategy
        ]
        
        # Find worst strategies (need improvement)
        insights["worst_strategies"] = [
            {
                "name": p.strategy_name,
                "success_rate": p.success_rate(),
                "attempts": p.total_attempts
            }
            for p in sorted_strategies[-3:]
            if p.total_attempts >= self.min_attempts_per_strategy
        ]
        
        # Analyze context patterns
        context_patterns = defaultdict(lambda: defaultdict(int))
        
        for strategy, perf in self.strategies.items():
            for context_key, ctx_perf in perf.context_performance.items():
                if ctx_perf['attempts'] >= 3:
                    context_patterns[context_key][strategy] = ctx_perf['success_rate']
        
        # Find strong context-strategy associations
        for context_key, strategy_rates in context_patterns.items():
            if strategy_rates:
                best_strategy = max(strategy_rates, key=strategy_rates.get)
                best_rate = strategy_rates[best_strategy]
                
                if best_rate >= 0.8:  # 80%+ success
                    insights["context_patterns"].append({
                        "context": context_key,
                        "best_strategy": best_strategy,
                        "success_rate": best_rate
                    })
        
        # Generate recommendations
        if insights["global_success_rate"] < 0.6:
            insights["recommendations"].append(
                "Overall success rate is low. Consider reviewing strategy implementations."
            )
        
        if len(insights["context_patterns"]) < 3:
            insights["recommendations"].append(
                "Not enough context-specific patterns learned. Increase exploration rate."
            )
        
        # Check for underexplored strategies
        underexplored = [
            s.strategy_name for s in self.strategies.values()
            if s.total_attempts < self.min_attempts_per_strategy
        ]
        
        if underexplored:
            insights["recommendations"].append(
                f"Explore: {', '.join(underexplored)} (insufficient data)"
            )
        
        logger.info(
            f"✅ Learning complete: {insights['total_strategies']} strategies analyzed, "
            f"{len(insights['best_strategies'])} high performers identified"
        )
        
        return insights
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get current statistics."""
        return {
            "total_selections": self.total_selections,
            "total_successes": self.total_successes,
            "global_success_rate": self.total_successes / max(1, self.total_selections),
            "strategies_tracked": len(self.strategies),
            "exploration_rate": self.exploration_rate,
            "strategy_performance": {
                name: {
                    "attempts": perf.total_attempts,
                    "successes": perf.successful_attempts,
                    "success_rate": perf.success_rate(),
                    "avg_quality": perf.avg_quality(),
                    "avg_latency": perf.avg_latency()
                }
                for name, perf in self.strategies.items()
            }
        }
    
    def _save_performance_data(self) -> None:
        """Save performance data to disk."""
        try:
            data = {
                "total_selections": self.total_selections,
                "total_successes": self.total_successes,
                "exploration_rate": self.exploration_rate,
                "strategies": {}
            }
            
            for name, perf in self.strategies.items():
                data["strategies"][name] = {
                    "total_attempts": perf.total_attempts,
                    "successful_attempts": perf.successful_attempts,
                    "total_quality_score": perf.total_quality_score,
                    "total_latency": perf.total_latency,
                    "total_tokens": perf.total_tokens,
                    "alpha": perf.alpha,
                    "beta": perf.beta,
                    "context_performance": perf.context_performance,
                    "last_used": perf.last_used
                }
            
            filepath = self.storage_path / "performance_data.json"
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.debug(f"Saved performance data: {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to save performance data: {e}")
    
    def _load_performance_data(self) -> None:
        """Load performance data from disk."""
        try:
            filepath = self.storage_path / "performance_data.json"
            
            if not filepath.exists():
                logger.info("No existing performance data found (fresh start)")
                return
            
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            self.total_selections = data.get("total_selections", 0)
            self.total_successes = data.get("total_successes", 0)
            
            for name, perf_data in data.get("strategies", {}).items():
                self.strategies[name] = StrategyPerformance(
                    strategy_name=name,
                    total_attempts=perf_data["total_attempts"],
                    successful_attempts=perf_data["successful_attempts"],
                    total_quality_score=perf_data["total_quality_score"],
                    total_latency=perf_data["total_latency"],
                    total_tokens=perf_data["total_tokens"],
                    alpha=perf_data.get("alpha", 1.0),
                    beta=perf_data.get("beta", 1.0),
                    context_performance=perf_data.get("context_performance", {}),
                    last_used=perf_data.get("last_used", 0.0)
                )
            
            logger.info(
                f"Loaded performance data: {len(self.strategies)} strategies, "
                f"{self.total_selections} total selections"
            )
            
        except Exception as e:
            logger.error(f"Failed to load performance data: {e}")


# Convenience function
def get_strategy_selector(
    storage_path: str = "./data/meta_learning"
) -> MetaLearningStrategySelector:
    """Get or create meta-learning strategy selector."""
    return MetaLearningStrategySelector(storage_path=storage_path)
