"""
Metrics Collector - Integration #14

Collects and aggregates system metrics from all integrations:
- Performance metrics (latency, throughput)
- Quality metrics (scores, trends)
- Reliability metrics (errors, retries)
- Cost metrics (tokens, API usage)
- Integration-specific metrics
"""

import time
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
from collections import defaultdict
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class GenerationMetric:
    """Metric for a single generation event."""
    timestamp: float
    integration: str
    backend: str
    model: str
    latency_ms: float
    success: bool
    tokens_used: int
    quality_score: Optional[float] = None
    error_type: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class MetricsCollector:
    """
    Collect and aggregate system metrics.
    
    Tracks:
    - Generation events (latency, success, backend)
    - Quality assessments
    - Errors and failures
    - Cost tracking (tokens)
    - Integration-specific metrics
    """
    
    def __init__(self, storage_path: str = "data/metrics/metrics.db"):
        """
        Initialize metrics collector.
        
        Args:
            storage_path: Path to SQLite database
        """
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # In-memory aggregations (for fast queries)
        self.recent_generations: List[GenerationMetric] = []
        self.error_counts = defaultdict(int)
        self.backend_stats = defaultdict(lambda: {"count": 0, "total_latency": 0.0})
        self.integration_stats = defaultdict(lambda: {"count": 0, "success": 0})
        
        # Initialize database
        self._init_db()
        
        logger.info(f"MetricsCollector initialized: {storage_path}")
    
    def _init_db(self):
        """Initialize SQLite database schema."""
        conn = sqlite3.connect(str(self.storage_path))
        cursor = conn.cursor()
        
        # Generation events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS generation_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                integration TEXT NOT NULL,
                backend TEXT NOT NULL,
                model TEXT NOT NULL,
                latency_ms REAL NOT NULL,
                success INTEGER NOT NULL,
                tokens_used INTEGER NOT NULL,
                quality_score REAL,
                error_type TEXT,
                metadata TEXT
            )
        """)
        
        # Quality metrics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quality_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                integration TEXT NOT NULL,
                score REAL NOT NULL,
                criteria TEXT,
                metadata TEXT
            )
        """)
        
        # Error events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS error_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                error_type TEXT NOT NULL,
                integration TEXT,
                backend TEXT,
                message TEXT,
                metadata TEXT
            )
        """)
        
        # Create indexes for common queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON generation_events(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_integration ON generation_events(integration)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_backend ON generation_events(backend)")
        
        conn.commit()
        conn.close()
        
        logger.info("Database schema initialized")
    
    def record_generation(self, 
                         integration: str,
                         backend: str,
                         model: str,
                         latency_ms: float,
                         success: bool,
                         tokens_used: int = 0,
                         quality_score: Optional[float] = None,
                         error_type: Optional[str] = None,
                         metadata: Optional[Dict[str, Any]] = None):
        """
        Record a generation event.
        
        Args:
            integration: Integration name (e.g., "parallel_generation")
            backend: Backend used (e.g., "groq", "openrouter")
            model: Model name
            latency_ms: Generation latency in milliseconds
            success: Whether generation succeeded
            tokens_used: Number of tokens used
            quality_score: Optional quality score (0.0-1.0)
            error_type: Optional error type if failed
            metadata: Optional additional metadata
        """
        timestamp = time.time()
        
        # Create metric object
        metric = GenerationMetric(
            timestamp=timestamp,
            integration=integration,
            backend=backend,
            model=model,
            latency_ms=latency_ms,
            success=success,
            tokens_used=tokens_used,
            quality_score=quality_score,
            error_type=error_type,
            metadata=metadata
        )
        
        # Update in-memory aggregations
        self.recent_generations.append(metric)
        if len(self.recent_generations) > 1000:
            self.recent_generations = self.recent_generations[-1000:]
        
        self.backend_stats[backend]["count"] += 1
        self.backend_stats[backend]["total_latency"] += latency_ms
        
        self.integration_stats[integration]["count"] += 1
        if success:
            self.integration_stats[integration]["success"] += 1
        
        if error_type:
            self.error_counts[error_type] += 1
        
        # Persist to database
        conn = sqlite3.connect(str(self.storage_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO generation_events 
            (timestamp, integration, backend, model, latency_ms, success, 
             tokens_used, quality_score, error_type, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp,
            integration,
            backend,
            model,
            latency_ms,
            1 if success else 0,
            tokens_used,
            quality_score,
            error_type,
            json.dumps(metadata) if metadata else None
        ))
        
        conn.commit()
        conn.close()
        
        logger.debug(f"Recorded generation: {integration}/{backend}/{model} - {latency_ms:.0f}ms")
    
    def record_quality(self,
                      integration: str,
                      score: float,
                      criteria: Optional[Dict[str, float]] = None,
                      metadata: Optional[Dict[str, Any]] = None):
        """
        Record a quality assessment.
        
        Args:
            integration: Integration name
            score: Overall quality score (0.0-1.0)
            criteria: Optional breakdown of quality criteria scores
            metadata: Optional additional metadata
        """
        timestamp = time.time()
        
        conn = sqlite3.connect(str(self.storage_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO quality_metrics 
            (timestamp, integration, score, criteria, metadata)
            VALUES (?, ?, ?, ?, ?)
        """, (
            timestamp,
            integration,
            score,
            json.dumps(criteria) if criteria else None,
            json.dumps(metadata) if metadata else None
        ))
        
        conn.commit()
        conn.close()
        
        logger.debug(f"Recorded quality: {integration} - {score:.3f}")
    
    def record_error(self,
                    error_type: str,
                    integration: Optional[str] = None,
                    backend: Optional[str] = None,
                    message: Optional[str] = None,
                    metadata: Optional[Dict[str, Any]] = None):
        """
        Record an error event.
        
        Args:
            error_type: Type of error (e.g., "timeout", "rate_limit", "api_error")
            integration: Optional integration where error occurred
            backend: Optional backend where error occurred
            message: Optional error message
            metadata: Optional additional metadata
        """
        timestamp = time.time()
        
        self.error_counts[error_type] += 1
        
        conn = sqlite3.connect(str(self.storage_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO error_events 
            (timestamp, error_type, integration, backend, message, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            timestamp,
            error_type,
            integration,
            backend,
            message,
            json.dumps(metadata) if metadata else None
        ))
        
        conn.commit()
        conn.close()
        
        logger.warning(f"Recorded error: {error_type} - {integration}/{backend}")
    
    def get_metrics(self, time_window: str = "1h") -> Dict[str, Any]:
        """
        Get aggregated metrics for a time window.
        
        Args:
            time_window: Time window ("1h", "24h", "7d")
            
        Returns:
            Dictionary of aggregated metrics
        """
        # Parse time window
        if time_window == "1h":
            start_time = time.time() - 3600
        elif time_window == "24h":
            start_time = time.time() - 86400
        elif time_window == "7d":
            start_time = time.time() - 604800
        else:
            start_time = 0
        
        conn = sqlite3.connect(str(self.storage_path))
        cursor = conn.cursor()
        
        # Get generation metrics
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful,
                AVG(latency_ms) as avg_latency,
                SUM(tokens_used) as total_tokens,
                AVG(quality_score) as avg_quality
            FROM generation_events
            WHERE timestamp >= ?
        """, (start_time,))
        
        row = cursor.fetchone()
        total, successful, avg_latency, total_tokens, avg_quality = row
        
        # Get backend stats
        cursor.execute("""
            SELECT backend, COUNT(*) as count, AVG(latency_ms) as avg_latency
            FROM generation_events
            WHERE timestamp >= ?
            GROUP BY backend
        """, (start_time,))
        
        backend_stats = {row[0]: {"count": row[1], "avg_latency": row[2]} 
                        for row in cursor.fetchall()}
        
        # Get integration stats
        cursor.execute("""
            SELECT 
                integration,
                COUNT(*) as total,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful
            FROM generation_events
            WHERE timestamp >= ?
            GROUP BY integration
        """, (start_time,))
        
        integration_stats = {row[0]: {"total": row[1], "successful": row[2]}
                            for row in cursor.fetchall()}
        
        # Get error stats
        cursor.execute("""
            SELECT error_type, COUNT(*) as count
            FROM error_events
            WHERE timestamp >= ?
            GROUP BY error_type
        """, (start_time,))
        
        error_stats = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Get quality trend (last 10 data points)
        cursor.execute("""
            SELECT timestamp, score
            FROM quality_metrics
            WHERE timestamp >= ?
            ORDER BY timestamp DESC
            LIMIT 10
        """, (start_time,))
        
        quality_trend = [(row[0], row[1]) for row in cursor.fetchall()]
        quality_trend.reverse()
        
        conn.close()
        
        # Calculate derived metrics
        success_rate = (successful / total) if total > 0 else 0.0
        error_rate = 1.0 - success_rate
        
        metrics = {
            "time_window": time_window,
            "timestamp": time.time(),
            "performance": {
                "total_requests": total or 0,
                "successful_requests": successful or 0,
                "success_rate": success_rate,
                "error_rate": error_rate,
                "avg_latency_ms": avg_latency or 0.0,
                "total_tokens": total_tokens or 0
            },
            "quality": {
                "avg_score": avg_quality or 0.0,
                "trend": [score for _, score in quality_trend]
            },
            "backends": backend_stats,
            "integrations": integration_stats,
            "errors": error_stats
        }
        
        return metrics
    
    def get_recent_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent generation events.
        
        Args:
            limit: Maximum number of events to return
            
        Returns:
            List of event dictionaries
        """
        conn = sqlite3.connect(str(self.storage_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT timestamp, integration, backend, model, 
                   latency_ms, success, quality_score, error_type
            FROM generation_events
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        
        events = []
        for row in cursor.fetchall():
            events.append({
                "timestamp": row[0],
                "integration": row[1],
                "backend": row[2],
                "model": row[3],
                "latency_ms": row[4],
                "success": bool(row[5]),
                "quality_score": row[6],
                "error_type": row[7]
            })
        
        conn.close()
        
        return events
    
    def clear_old_data(self, days: int = 30):
        """
        Clear data older than specified days.
        
        Args:
            days: Number of days to keep
        """
        cutoff_time = time.time() - (days * 86400)
        
        conn = sqlite3.connect(str(self.storage_path))
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM generation_events WHERE timestamp < ?", (cutoff_time,))
        cursor.execute("DELETE FROM quality_metrics WHERE timestamp < ?", (cutoff_time,))
        cursor.execute("DELETE FROM error_events WHERE timestamp < ?", (cutoff_time,))
        
        deleted_gen = cursor.rowcount
        conn.commit()
        conn.close()
        
        logger.info(f"Cleared {deleted_gen} old records (older than {days} days)")


if __name__ == "__main__":
    # Test metrics collector
    print("Testing MetricsCollector...")
    
    collector = MetricsCollector("data/metrics/test_metrics.db")
    
    # Record some test events
    collector.record_generation(
        integration="parallel_generation",
        backend="groq",
        model="llama-3.1-8b-instant",
        latency_ms=2450.0,
        success=True,
        tokens_used=1500,
        quality_score=0.85
    )
    
    collector.record_generation(
        integration="multi_critic",
        backend="openrouter",
        model="qwen/qwen3-coder:free",
        latency_ms=3200.0,
        success=True,
        tokens_used=2000,
        quality_score=0.79
    )
    
    collector.record_error(
        error_type="timeout",
        integration="reflection",
        backend="openrouter",
        message="Request timed out after 30s"
    )
    
    # Get metrics
    metrics = collector.get_metrics("1h")
    print("\nMetrics:")
    print(f"Total requests: {metrics['performance']['total_requests']}")
    print(f"Success rate: {metrics['performance']['success_rate']:.1%}")
    print(f"Avg latency: {metrics['performance']['avg_latency_ms']:.0f}ms")
    print(f"Avg quality: {metrics['quality']['avg_score']:.3f}")
    print(f"Errors: {metrics['errors']}")
    
    print("\n✅ MetricsCollector test complete!")
