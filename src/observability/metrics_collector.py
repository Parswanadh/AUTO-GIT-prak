"""
Metrics Collector
=================

Aggregates performance metrics from agents, cache, and system.

Provides:
- Real-time metrics collection
- Aggregation and statistical analysis
- Export to monitoring systems
- Dashboard data
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict
import statistics
import json
import asyncio
import logging

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Collects and aggregates metrics from various system components.
    
    Metrics tracked:
    - Agent performance (latency, success rate)
    - Token usage (per agent, per model)
    - Cache performance (hit rate, savings)
    - Error rates
    - System health
    
    Example:
        ```python
        collector = MetricsCollector()
        
        # Record agent call
        collector.record_agent_call(
            agent_name="CodeGenerator",
            model="qwen2.5-coder:7b",
            latency_ms=1234,
            tokens_used=500,
            success=True
        )
        
        # Get summary
        summary = collector.get_summary()
        print(summary)
        ```
    """
    
    def __init__(self):
        """Initialize metrics collector"""
        # Agent metrics
        self.agent_calls: List[Dict] = []
        self.agent_stats: Dict[str, Dict] = defaultdict(lambda: {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "total_latency_ms": 0,
            "total_tokens": 0,
            "errors": []
        })
        
        # Cache metrics
        self.cache_hits = 0
        self.cache_misses = 0
        self.cache_savings_tokens = 0
        
        # Model usage
        self.model_usage: Dict[str, Dict] = defaultdict(lambda: {
            "calls": 0,
            "tokens": 0,
            "latency_ms": []
        })
        
        # System metrics
        self.start_time = datetime.now()
        self.total_errors = 0
    
    def record_agent_call(
        self,
        agent_name: str,
        model: str,
        latency_ms: float,
        tokens_used: int,
        success: bool = True,
        error: Optional[str] = None
    ) -> None:
        """
        Record an agent call.
        
        Args:
            agent_name: Name of the agent
            model: Model used
            latency_ms: Response latency in milliseconds
            tokens_used: Number of tokens consumed
            success: Whether call succeeded
            error: Error message if failed
        """
        # Record call details
        call_record = {
            "agent_name": agent_name,
            "model": model,
            "latency_ms": latency_ms,
            "tokens_used": tokens_used,
            "success": success,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }
        self.agent_calls.append(call_record)
        
        # Update agent stats
        stats = self.agent_stats[agent_name]
        stats["total_calls"] += 1
        stats["total_latency_ms"] += latency_ms
        stats["total_tokens"] += tokens_used
        
        if success:
            stats["successful_calls"] += 1
        else:
            stats["failed_calls"] += 1
            if error:
                stats["errors"].append({
                    "error": error,
                    "timestamp": datetime.now().isoformat()
                })
            self.total_errors += 1
        
        # Update model usage
        model_stats = self.model_usage[model]
        model_stats["calls"] += 1
        model_stats["tokens"] += tokens_used
        model_stats["latency_ms"].append(latency_ms)
        
        logger.debug(
            f"Recorded {agent_name} call: {latency_ms:.0f}ms, "
            f"{tokens_used} tokens, {'✅' if success else '❌'}"
        )
    
    def record_cache_hit(self, tokens_saved: int = 500) -> None:
        """
        Record a cache hit.
        
        Args:
            tokens_saved: Estimated tokens saved by cache hit
        """
        self.cache_hits += 1
        self.cache_savings_tokens += tokens_saved
    
    def record_cache_miss(self) -> None:
        """Record a cache miss"""
        self.cache_misses += 1
    
    def get_agent_summary(self, agent_name: str) -> Dict[str, Any]:
        """
        Get summary for specific agent.
        
        Args:
            agent_name: Agent to summarize
        
        Returns:
            Dict with agent statistics
        """
        if agent_name not in self.agent_stats:
            return {"error": f"No data for agent: {agent_name}"}
        
        stats = self.agent_stats[agent_name]
        total_calls = stats["total_calls"]
        
        if total_calls == 0:
            return {"error": "No calls recorded"}
        
        return {
            "agent_name": agent_name,
            "total_calls": total_calls,
            "successful_calls": stats["successful_calls"],
            "failed_calls": stats["failed_calls"],
            "success_rate_percent": round(stats["successful_calls"] / total_calls * 100, 2),
            "avg_latency_ms": round(stats["total_latency_ms"] / total_calls, 2),
            "total_tokens": stats["total_tokens"],
            "avg_tokens_per_call": round(stats["total_tokens"] / total_calls, 2),
            "recent_errors": stats["errors"][-5:]  # Last 5 errors
        }
    
    def get_model_summary(self, model: str) -> Dict[str, Any]:
        """
        Get summary for specific model.
        
        Args:
            model: Model to summarize
        
        Returns:
            Dict with model statistics
        """
        if model not in self.model_usage:
            return {"error": f"No data for model: {model}"}
        
        usage = self.model_usage[model]
        latencies = usage["latency_ms"]
        
        if not latencies:
            return {"error": "No data"}
        
        return {
            "model": model,
            "total_calls": usage["calls"],
            "total_tokens": usage["tokens"],
            "avg_tokens_per_call": round(usage["tokens"] / usage["calls"], 2),
            "avg_latency_ms": round(statistics.mean(latencies), 2),
            "median_latency_ms": round(statistics.median(latencies), 2),
            "p95_latency_ms": round(statistics.quantiles(latencies, n=20)[18], 2) if len(latencies) >= 20 else None,
            "min_latency_ms": round(min(latencies), 2),
            "max_latency_ms": round(max(latencies), 2)
        }
    
    def get_cache_summary(self) -> Dict[str, Any]:
        """
        Get cache performance summary.
        
        Returns:
            Dict with cache statistics
        """
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total_requests * 100) if total_requests > 0 else 0.0
        
        # Estimate cost savings (rough approximation)
        estimated_cost_usd = self.cache_savings_tokens * 0.00002  # ~$0.02 per 1k tokens
        
        return {
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "total_requests": total_requests,
            "hit_rate_percent": round(hit_rate, 2),
            "tokens_saved": self.cache_savings_tokens,
            "estimated_cost_savings_usd": round(estimated_cost_usd, 4)
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive system summary.
        
        Returns:
            Dict with all metrics
        """
        uptime_seconds = (datetime.now() - self.start_time).total_seconds()
        total_calls = sum(s["total_calls"] for s in self.agent_stats.values())
        total_tokens = sum(s["total_tokens"] for s in self.agent_stats.values())
        
        # Agent summaries
        agent_summaries = {
            name: self.get_agent_summary(name)
            for name in self.agent_stats.keys()
        }
        
        # Model summaries
        model_summaries = {
            model: self.get_model_summary(model)
            for model in self.model_usage.keys()
        }
        
        return {
            "system": {
                "uptime_seconds": round(uptime_seconds, 2),
                "uptime_hours": round(uptime_seconds / 3600, 2),
                "total_calls": total_calls,
                "total_tokens": total_tokens,
                "total_errors": self.total_errors,
                "error_rate_percent": round(self.total_errors / total_calls * 100, 2) if total_calls > 0 else 0.0
            },
            "agents": agent_summaries,
            "models": model_summaries,
            "cache": self.get_cache_summary()
        }
    
    def export_json(self, filepath: str) -> None:
        """
        Export metrics to JSON file.
        
        Args:
            filepath: Path to save JSON file
        """
        summary = self.get_summary()
        
        with open(filepath, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"Metrics exported to {filepath}")
    
    def reset(self) -> None:
        """Reset all metrics (useful for testing)"""
        self.agent_calls.clear()
        self.agent_stats.clear()
        self.cache_hits = 0
        self.cache_misses = 0
        self.cache_savings_tokens = 0
        self.model_usage.clear()
        self.start_time = datetime.now()
        self.total_errors = 0
        
        logger.info("Metrics reset")


# Global metrics collector
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """
    Get singleton metrics collector instance.
    
    Example:
        ```python
        from src.observability import get_metrics_collector
        
        collector = get_metrics_collector()
        collector.record_agent_call(...)
        
        summary = collector.get_summary()
        ```
    """
    global _metrics_collector
    
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    
    return _metrics_collector
