"""Performance Optimizer - Model selection based on analytics"""

import logging
from typing import Dict, List, Optional, Tuple
from .tracker import AnalyticsTracker, ModelMetrics

logger = logging.getLogger(__name__)


class PerformanceOptimizer:
    """
    Optimize model selection based on historical performance
    
    Features:
    - Automatic model selection by stage
    - Fallback recommendations
    - Performance-based routing
    - Cost optimization
    """
    
    def __init__(self, tracker: AnalyticsTracker):
        """Initialize optimizer with analytics tracker"""
        self.tracker = tracker
        
        # Default model preferences by task type
        self.task_defaults = {
            "coding": ["qwen2.5-coder:7b", "deepseek-coder-v2:16b", "qwen3:8b"],
            "reasoning": ["deepseek-r1:8b", "qwen3:8b", "qwen3:4b"],
            "fast": ["phi4-mini:3.8b", "qwen3:4b", "qwen3:0.6b"],
            "general": ["qwen3:8b", "qwen3:4b"],
        }
    
    def recommend_model(
        self,
        task_type: str,
        stage: str,
        max_latency: Optional[float] = None,
        min_success_rate: float = 0.7
    ) -> Tuple[str, str]:
        """
        Recommend best model for a task
        
        Args:
            task_type: Type of task (coding, reasoning, fast, general)
            stage: Pipeline stage name
            max_latency: Maximum acceptable latency in seconds
            min_success_rate: Minimum success rate threshold
            
        Returns:
            Tuple of (recommended_model, reason)
        """
        candidates = self.task_defaults.get(task_type, self.task_defaults["general"])
        
        # Get metrics for each candidate
        metrics_list: List[Tuple[str, Optional[ModelMetrics]]] = []
        for model in candidates:
            metrics = self.tracker.get_model_metrics(model, days=7)
            metrics_list.append((model, metrics))
        
        # Filter by success rate
        valid_models = [
            (model, metrics) 
            for model, metrics in metrics_list 
            if metrics and metrics.success_rate >= min_success_rate
        ]
        
        # Filter by latency if specified
        if max_latency:
            valid_models = [
                (model, metrics)
                for model, metrics in valid_models
                if metrics.avg_latency <= max_latency
            ]
        
        # No valid models with metrics, use defaults
        if not valid_models:
            default_model = candidates[0]
            return default_model, f"Default for {task_type} (no historical data)"
        
        # Sort by success rate, then by speed
        valid_models.sort(
            key=lambda x: (-x[1].success_rate, x[1].avg_latency)
        )
        
        best_model, best_metrics = valid_models[0]
        reason = f"{best_metrics.success_rate:.1%} success, {best_metrics.avg_latency:.1f}s avg"
        
        return best_model, reason
    
    def get_fallback_chain(self, primary_model: str, task_type: str) -> List[str]:
        """
        Get fallback model chain for reliability
        
        Args:
            primary_model: Primary model choice
            task_type: Task type for fallback selection
            
        Returns:
            List of fallback models in order
        """
        candidates = self.task_defaults.get(task_type, self.task_defaults["general"])
        
        # Remove primary model and return rest
        fallbacks = [m for m in candidates if m != primary_model]
        
        # Add final safety fallback
        if "qwen3:0.6b" not in fallbacks:
            fallbacks.append("qwen3:0.6b")
        
        return fallbacks[:3]  # Limit to 3 fallbacks
    
    def get_cost_efficient_model(
        self,
        task_type: str,
        max_cost_per_run: float = 0.001
    ) -> Tuple[str, str]:
        """
        Get most cost-efficient model for task
        
        Args:
            task_type: Type of task
            max_cost_per_run: Maximum acceptable cost per run
            
        Returns:
            Tuple of (model, reason)
        """
        candidates = self.task_defaults.get(task_type, self.task_defaults["general"])
        
        # Get metrics and calculate cost per run
        cost_metrics: List[Tuple[str, float, float]] = []
        for model in candidates:
            metrics = self.tracker.get_model_metrics(model, days=7)
            if metrics and metrics.total_runs > 0:
                cost_per_run = metrics.total_cost_estimate / metrics.total_runs
                if cost_per_run <= max_cost_per_run:
                    cost_metrics.append((
                        model,
                        cost_per_run,
                        metrics.success_rate
                    ))
        
        if not cost_metrics:
            # Use smallest model as fallback
            return "qwen3:0.6b", "Ultra-low cost fallback"
        
        # Sort by cost, then by success rate
        cost_metrics.sort(key=lambda x: (x[1], -x[2]))
        
        best_model, cost, success_rate = cost_metrics[0]
        reason = f"${cost:.6f}/run, {success_rate:.1%} success"
        
        return best_model, reason
    
    def analyze_bottlenecks(self, days: int = 7) -> Dict[str, Dict[str, any]]:
        """
        Identify performance bottlenecks in pipeline
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dict of stage -> bottleneck analysis
        """
        stages = [
            "research",
            "problem_extraction",
            "solution_generation",
            "critique",
            "consensus_check",
            "solution_selection",
            "code_generation",
            "code_testing"
        ]
        
        bottlenecks = {}
        
        for stage in stages:
            stats = self.tracker.get_stage_statistics(stage, days=days)
            
            if not stats or stats.get("total_runs", 0) == 0:
                continue
            
            # Identify issues
            issues = []
            
            success_rate = stats.get("success_rate", 0.0)
            if success_rate < 0.8:
                issues.append(f"Low success rate: {success_rate:.1%}")
            
            avg_latency = stats.get("avg_latency_seconds", 0.0)
            if avg_latency > 30.0:
                issues.append(f"High latency: {avg_latency:.1f}s")
            
            max_latency = stats.get("max_latency_seconds", 0.0)
            if max_latency > 120.0:
                issues.append(f"Timeout risk: {max_latency:.1f}s max")
            
            if issues:
                bottlenecks[stage] = {
                    "statistics": stats,
                    "issues": issues,
                    "recommendations": self._get_recommendations(stage, stats)
                }
        
        return bottlenecks
    
    def _get_recommendations(
        self,
        stage: str,
        stats: Dict[str, any]
    ) -> List[str]:
        """Generate recommendations for improving stage performance"""
        recommendations = []
        
        success_rate = stats.get("success_rate", 0.0)
        avg_latency = stats.get("avg_latency_seconds", 0.0)
        
        # Success rate recommendations
        if success_rate < 0.5:
            recommendations.append("Critical: Consider changing model or prompt strategy")
        elif success_rate < 0.8:
            recommendations.append("Try different model or add retry logic")
        
        # Latency recommendations
        if avg_latency > 60.0:
            recommendations.append("High latency: Consider faster model (phi4-mini, qwen3:4b)")
        elif avg_latency > 30.0:
            recommendations.append("Optimize prompt length or use streaming")
        
        # Stage-specific recommendations
        if stage == "code_generation" and avg_latency > 45.0:
            recommendations.append("Consider generating files in parallel")
        
        if stage == "critique" and avg_latency > 20.0:
            recommendations.append("Reduce number of critique perspectives")
        
        return recommendations
    
    def get_performance_report(self, days: int = 7) -> Dict[str, any]:
        """
        Generate comprehensive performance report
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Performance report dict
        """
        # Get all model metrics
        models = ["qwen2.5-coder:7b", "deepseek-r1:8b", "phi4-mini:3.8b", "qwen3:8b"]
        model_reports = {}
        
        for model in models:
            metrics = self.tracker.get_model_metrics(model, days=days)
            if metrics:
                model_reports[model] = {
                    "success_rate": f"{metrics.success_rate:.1%}",
                    "avg_tokens": int(metrics.avg_tokens),
                    "avg_latency": f"{metrics.avg_latency:.2f}s",
                    "total_runs": metrics.total_runs,
                    "cost_estimate": f"${metrics.total_cost_estimate:.4f}"
                }
        
        # Get bottlenecks
        bottlenecks = self.analyze_bottlenecks(days=days)
        
        # Get total cost
        total_cost = self.tracker.get_total_cost_estimate(days=days)
        
        return {
            "period_days": days,
            "model_performance": model_reports,
            "bottlenecks": bottlenecks,
            "total_cost_estimate": f"${total_cost:.4f}",
            "recommendations": self._get_global_recommendations(model_reports, bottlenecks)
        }
    
    def _get_global_recommendations(
        self,
        model_reports: Dict[str, Dict],
        bottlenecks: Dict[str, Dict]
    ) -> List[str]:
        """Generate global optimization recommendations"""
        recommendations = []
        
        # Check if any model is underperforming
        for model, report in model_reports.items():
            if "success_rate" in report:
                success_str = report["success_rate"].rstrip("%")
                success_rate = float(success_str) / 100
                if success_rate < 0.7:
                    recommendations.append(
                        f"Replace {model} - low success rate ({report['success_rate']})"
                    )
        
        # Check for systemic bottlenecks
        if len(bottlenecks) >= 3:
            recommendations.append(
                "Multiple bottlenecks detected - consider pipeline redesign"
            )
        
        # Cost optimization
        if len(model_reports) > 0:
            recommendations.append(
                "Consider using faster models (phi4-mini:3.8b) for non-critical stages"
            )
        
        return recommendations
