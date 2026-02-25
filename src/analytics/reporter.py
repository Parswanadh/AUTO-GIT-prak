"""Analytics Reporter - Generate reports and visualizations"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from .tracker import AnalyticsTracker, ModelMetrics

logger = logging.getLogger(__name__)


class AnalyticsReporter:
    """
    Generate analytics reports and summaries
    
    Features:
    - Text-based reports
    - Trend analysis
    - Comparison reports
    - Export capabilities
    """
    
    def __init__(self, tracker: AnalyticsTracker):
        """Initialize reporter with tracker"""
        self.tracker = tracker
    
    def generate_summary_report(self, days: int = 7) -> str:
        """
        Generate human-readable summary report
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Formatted report string
        """
        report_lines = []
        report_lines.append("=" * 60)
        report_lines.append(f"PIPELINE ANALYTICS REPORT ({days}-day period)")
        report_lines.append("=" * 60)
        report_lines.append("")
        
        # Recent runs section
        report_lines.append("📊 RECENT RUNS (Last 10)")
        report_lines.append("-" * 60)
        
        recent_runs = self.tracker.get_recent_runs(limit=10)
        for run in recent_runs:
            status = "✅" if run.success else "❌"
            timestamp = datetime.fromisoformat(run.timestamp).strftime("%Y-%m-%d %H:%M")
            report_lines.append(
                f"{status} {timestamp} | {run.stage:20} | "
                f"{run.model_used:20} | {run.tokens_used:6} tokens"
            )
        
        report_lines.append("")
        
        # Model performance section
        report_lines.append("🤖 MODEL PERFORMANCE")
        report_lines.append("-" * 60)
        
        models = [
            "qwen2.5-coder:7b",
            "deepseek-r1:8b",
            "phi4-mini:3.8b",
            "qwen3:8b",
            "qwen3:4b"
        ]
        
        for model in models:
            metrics = self.tracker.get_model_metrics(model, days=days)
            if metrics:
                report_lines.append(f"\n{model}:")
                report_lines.append(f"  Total Runs:    {metrics.total_runs}")
                report_lines.append(f"  Success Rate:  {metrics.success_rate:.1%}")
                report_lines.append(f"  Avg Tokens:    {metrics.avg_tokens:.0f}")
                report_lines.append(f"  Avg Latency:   {metrics.avg_latency:.2f}s")
                report_lines.append(f"  Est. Cost:     ${metrics.total_cost_estimate:.4f}")
        
        report_lines.append("")
        
        # Stage statistics section
        report_lines.append("📈 STAGE STATISTICS")
        report_lines.append("-" * 60)
        
        stages = [
            "research",
            "problem_extraction",
            "solution_generation",
            "critique",
            "solution_selection",
            "code_generation"
        ]
        
        for stage in stages:
            stats = self.tracker.get_stage_statistics(stage, days=days)
            if stats and stats.get("total_runs", 0) > 0:
                report_lines.append(f"\n{stage}:")
                report_lines.append(f"  Total Runs:    {stats['total_runs']}")
                report_lines.append(f"  Success Rate:  {stats['success_rate']:.1%}")
                report_lines.append(f"  Avg Latency:   {stats['avg_latency_seconds']:.2f}s")
                report_lines.append(f"  Latency Range: {stats['min_latency_seconds']:.2f}s - {stats['max_latency_seconds']:.2f}s")
        
        report_lines.append("")
        
        # Cost summary
        total_cost = self.tracker.get_total_cost_estimate(days=days)
        report_lines.append("💰 COST SUMMARY")
        report_lines.append("-" * 60)
        report_lines.append(f"Total Estimated Cost ({days} days): ${total_cost:.4f}")
        
        report_lines.append("")
        report_lines.append("=" * 60)
        
        return "\n".join(report_lines)
    
    def generate_comparison_report(
        self,
        model1: str,
        model2: str,
        days: int = 7
    ) -> str:
        """
        Generate comparison report between two models
        
        Args:
            model1: First model name
            model2: Second model name
            days: Number of days to analyze
            
        Returns:
            Formatted comparison report
        """
        metrics1 = self.tracker.get_model_metrics(model1, days=days)
        metrics2 = self.tracker.get_model_metrics(model2, days=days)
        
        if not metrics1 or not metrics2:
            return f"Insufficient data for comparison between {model1} and {model2}"
        
        report_lines = []
        report_lines.append("=" * 60)
        report_lines.append(f"MODEL COMPARISON: {model1} vs {model2}")
        report_lines.append("=" * 60)
        report_lines.append("")
        
        # Success rate
        report_lines.append("📊 SUCCESS RATE")
        report_lines.append(f"  {model1}: {metrics1.success_rate:.1%}")
        report_lines.append(f"  {model2}: {metrics2.success_rate:.1%}")
        if metrics1.success_rate > metrics2.success_rate:
            diff = (metrics1.success_rate - metrics2.success_rate) * 100
            report_lines.append(f"  Winner: {model1} (+{diff:.1f}%)")
        else:
            diff = (metrics2.success_rate - metrics1.success_rate) * 100
            report_lines.append(f"  Winner: {model2} (+{diff:.1f}%)")
        report_lines.append("")
        
        # Latency
        report_lines.append("⚡ LATENCY")
        report_lines.append(f"  {model1}: {metrics1.avg_latency:.2f}s")
        report_lines.append(f"  {model2}: {metrics2.avg_latency:.2f}s")
        if metrics1.avg_latency < metrics2.avg_latency:
            diff = metrics2.avg_latency - metrics1.avg_latency
            speedup = metrics2.avg_latency / metrics1.avg_latency
            report_lines.append(f"  Winner: {model1} (-{diff:.2f}s, {speedup:.1f}x faster)")
        else:
            diff = metrics1.avg_latency - metrics2.avg_latency
            speedup = metrics1.avg_latency / metrics2.avg_latency
            report_lines.append(f"  Winner: {model2} (-{diff:.2f}s, {speedup:.1f}x faster)")
        report_lines.append("")
        
        # Tokens
        report_lines.append("🔢 TOKEN USAGE")
        report_lines.append(f"  {model1}: {metrics1.avg_tokens:.0f} tokens/run")
        report_lines.append(f"  {model2}: {metrics2.avg_tokens:.0f} tokens/run")
        report_lines.append("")
        
        # Cost
        report_lines.append("💰 COST")
        report_lines.append(f"  {model1}: ${metrics1.total_cost_estimate:.4f}")
        report_lines.append(f"  {model2}: ${metrics2.total_cost_estimate:.4f}")
        report_lines.append("")
        
        # Recommendation
        report_lines.append("🎯 RECOMMENDATION")
        
        # Calculate scores
        score1 = (
            metrics1.success_rate * 0.5 +  # 50% weight on success
            (1.0 / metrics1.avg_latency) * 0.3 +  # 30% weight on speed
            (1.0 / (metrics1.total_cost_estimate + 0.0001)) * 0.2  # 20% weight on cost
        )
        score2 = (
            metrics2.success_rate * 0.5 +
            (1.0 / metrics2.avg_latency) * 0.3 +
            (1.0 / (metrics2.total_cost_estimate + 0.0001)) * 0.2
        )
        
        if score1 > score2:
            report_lines.append(f"  Use {model1} for better overall performance")
        else:
            report_lines.append(f"  Use {model2} for better overall performance")
        
        report_lines.append("")
        report_lines.append("=" * 60)
        
        return "\n".join(report_lines)
    
    def generate_trend_report(self, model: str, days: int = 30) -> str:
        """
        Generate trend analysis for a model
        
        Args:
            model: Model name
            days: Number of days to analyze
            
        Returns:
            Formatted trend report
        """
        # Get metrics for different time periods
        week1 = self.tracker.get_model_metrics(model, days=7)
        week2 = self.tracker.get_model_metrics(model, days=14)
        month = self.tracker.get_model_metrics(model, days=30)
        
        if not week1:
            return f"Insufficient data for trend analysis of {model}"
        
        report_lines = []
        report_lines.append("=" * 60)
        report_lines.append(f"TREND ANALYSIS: {model}")
        report_lines.append("=" * 60)
        report_lines.append("")
        
        # Success rate trend
        report_lines.append("📈 SUCCESS RATE TREND")
        if week1:
            report_lines.append(f"  Last 7 days:  {week1.success_rate:.1%} ({week1.total_runs} runs)")
        if week2:
            report_lines.append(f"  Last 14 days: {week2.success_rate:.1%} ({week2.total_runs} runs)")
        if month:
            report_lines.append(f"  Last 30 days: {month.success_rate:.1%} ({month.total_runs} runs)")
        
        # Determine trend
        if week2 and week1.success_rate > week2.success_rate:
            report_lines.append("  Trend: 📈 IMPROVING")
        elif week2 and week1.success_rate < week2.success_rate:
            report_lines.append("  Trend: 📉 DECLINING")
        else:
            report_lines.append("  Trend: ➡️ STABLE")
        
        report_lines.append("")
        
        # Latency trend
        report_lines.append("⚡ LATENCY TREND")
        if week1:
            report_lines.append(f"  Last 7 days:  {week1.avg_latency:.2f}s")
        if week2:
            report_lines.append(f"  Last 14 days: {week2.avg_latency:.2f}s")
        if month:
            report_lines.append(f"  Last 30 days: {month.avg_latency:.2f}s")
        
        if week2 and week1.avg_latency < week2.avg_latency:
            report_lines.append("  Trend: ⚡ FASTER")
        elif week2 and week1.avg_latency > week2.avg_latency:
            report_lines.append("  Trend: 🐌 SLOWER")
        else:
            report_lines.append("  Trend: ➡️ STABLE")
        
        report_lines.append("")
        report_lines.append("=" * 60)
        
        return "\n".join(report_lines)
    
    def export_to_json(self, days: int = 7) -> Dict[str, any]:
        """
        Export analytics data to JSON format
        
        Args:
            days: Number of days to export
            
        Returns:
            Analytics data as dict
        """
        data = {
            "generated_at": datetime.now().isoformat(),
            "period_days": days,
            "recent_runs": [],
            "model_metrics": {},
            "stage_statistics": {},
            "total_cost": self.tracker.get_total_cost_estimate(days=days)
        }
        
        # Recent runs
        recent_runs = self.tracker.get_recent_runs(limit=50)
        for run in recent_runs:
            data["recent_runs"].append({
                "run_id": run.run_id,
                "timestamp": run.timestamp,
                "idea": run.idea[:100],  # Truncate for JSON
                "model": run.model_used,
                "stage": run.stage,
                "success": run.success,
                "tokens": run.tokens_used,
                "latency": run.latency_seconds,
                "error": run.error
            })
        
        # Model metrics
        models = ["qwen2.5-coder:7b", "deepseek-r1:8b", "phi4-mini:3.8b", "qwen3:8b"]
        for model in models:
            metrics = self.tracker.get_model_metrics(model, days=days)
            if metrics:
                data["model_metrics"][model] = {
                    "total_runs": metrics.total_runs,
                    "successful_runs": metrics.successful_runs,
                    "failed_runs": metrics.failed_runs,
                    "success_rate": metrics.success_rate,
                    "avg_tokens": metrics.avg_tokens,
                    "avg_latency": metrics.avg_latency,
                    "total_cost_estimate": metrics.total_cost_estimate
                }
        
        # Stage statistics
        stages = ["research", "problem_extraction", "solution_generation",
                  "critique", "solution_selection", "code_generation"]
        for stage in stages:
            stats = self.tracker.get_stage_statistics(stage, days=days)
            if stats:
                data["stage_statistics"][stage] = stats
        
        return data
    
    def print_quick_summary(self, days: int = 1):
        """
        Print quick summary to console
        
        Args:
            days: Number of days to summarize
        """
        print(f"\n{'='*50}")
        print(f"QUICK ANALYTICS SUMMARY (Last {days} day{'s' if days > 1 else ''})")
        print(f"{'='*50}\n")
        
        # Recent activity
        recent_runs = self.tracker.get_recent_runs(limit=5)
        if recent_runs:
            print(f"📊 Last 5 Runs:")
            for run in recent_runs:
                status = "✅" if run.success else "❌"
                print(f"  {status} {run.stage:20} | {run.model_used:20}")
        else:
            print("  No recent activity")
        
        print(f"\n{'='*50}\n")
