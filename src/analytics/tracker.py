"""Analytics Tracker - SQLite-based metrics storage"""

import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class PipelineRun:
    """Individual pipeline run record"""
    run_id: str
    timestamp: str
    idea: str
    model_used: str
    stage: str
    success: bool
    tokens_used: int
    latency_seconds: float
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ModelMetrics:
    """Model performance metrics"""
    model_name: str
    total_runs: int
    successful_runs: int
    failed_runs: int
    avg_tokens: float
    avg_latency: float
    success_rate: float
    total_cost_estimate: float  # Estimated cost in USD


class AnalyticsTracker:
    """
    SQLite-based analytics tracker for pipeline metrics
    
    Tracks:
    - Individual pipeline runs
    - Model performance
    - Token usage
    - Success/failure rates
    - Cost estimates
    """
    
    def __init__(self, db_path: str = "data/analytics/pipeline_analytics.db"):
        """Initialize tracker with SQLite database"""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
        logger.info(f"Analytics tracker initialized: {self.db_path}")
    
    def _init_database(self):
        """Create tables if they don't exist"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Pipeline runs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pipeline_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    idea TEXT NOT NULL,
                    model_used TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    tokens_used INTEGER NOT NULL,
                    latency_seconds REAL NOT NULL,
                    error TEXT,
                    metadata TEXT,
                    UNIQUE(run_id, stage)
                )
            """)
            
            # Model performance table (aggregated)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS model_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_name TEXT NOT NULL,
                    date TEXT NOT NULL,
                    total_runs INTEGER DEFAULT 0,
                    successful_runs INTEGER DEFAULT 0,
                    failed_runs INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    total_latency REAL DEFAULT 0,
                    UNIQUE(model_name, date)
                )
            """)
            
            # Cost tracking table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cost_tracking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_name TEXT NOT NULL,
                    backend TEXT NOT NULL,
                    date TEXT NOT NULL,
                    tokens_used INTEGER NOT NULL,
                    estimated_cost REAL NOT NULL
                )
            """)
            
            conn.commit()
            logger.info("Database tables initialized")
    
    def record_run(
        self,
        run_id: str,
        idea: str,
        model: str,
        stage: str,
        success: bool,
        tokens: int,
        latency: float,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Record a single pipeline run"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO pipeline_runs 
                    (run_id, timestamp, idea, model_used, stage, success, 
                     tokens_used, latency_seconds, error, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    run_id,
                    datetime.now().isoformat(),
                    idea,
                    model,
                    stage,
                    1 if success else 0,
                    tokens,
                    latency,
                    error,
                    json.dumps(metadata) if metadata else None
                ))
                
                conn.commit()
                logger.debug(f"Recorded run: {run_id}/{stage} - {model}")
                
                # Update aggregated model performance
                self._update_model_performance(model, success, tokens, latency)
                
        except Exception as e:
            logger.error(f"Failed to record run: {e}")
    
    def _update_model_performance(
        self,
        model: str,
        success: bool,
        tokens: int,
        latency: float
    ):
        """Update aggregated model performance"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get existing record
            cursor.execute("""
                SELECT total_runs, successful_runs, failed_runs, 
                       total_tokens, total_latency
                FROM model_performance
                WHERE model_name = ? AND date = ?
            """, (model, today))
            
            row = cursor.fetchone()
            
            if row:
                total, success_count, fail_count, total_tok, total_lat = row
                cursor.execute("""
                    UPDATE model_performance
                    SET total_runs = ?,
                        successful_runs = ?,
                        failed_runs = ?,
                        total_tokens = ?,
                        total_latency = ?
                    WHERE model_name = ? AND date = ?
                """, (
                    total + 1,
                    success_count + (1 if success else 0),
                    fail_count + (0 if success else 1),
                    total_tok + tokens,
                    total_lat + latency,
                    model,
                    today
                ))
            else:
                cursor.execute("""
                    INSERT INTO model_performance
                    (model_name, date, total_runs, successful_runs, failed_runs,
                     total_tokens, total_latency)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    model,
                    today,
                    1,
                    1 if success else 0,
                    0 if success else 1,
                    tokens,
                    latency
                ))
            
            conn.commit()
    
    def record_cost(
        self,
        model: str,
        backend: str,
        tokens: int,
        estimated_cost: float
    ):
        """Record cost for a model invocation"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO cost_tracking
                    (model_name, backend, date, tokens_used, estimated_cost)
                    VALUES (?, ?, ?, ?, ?)
                """, (model, backend, today, tokens, estimated_cost))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to record cost: {e}")
    
    def get_model_metrics(self, model: str, days: int = 7) -> Optional[ModelMetrics]:
        """Get aggregated metrics for a model over last N days"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT 
                        SUM(total_runs) as total,
                        SUM(successful_runs) as success,
                        SUM(failed_runs) as failed,
                        AVG(total_tokens * 1.0 / total_runs) as avg_tokens,
                        AVG(total_latency * 1.0 / total_runs) as avg_latency
                    FROM model_performance
                    WHERE model_name = ?
                    AND date >= date('now', ?)
                    GROUP BY model_name
                """, (model, f'-{days} days'))
                
                row = cursor.fetchone()
                
                if not row or not row[0]:
                    return None
                
                total, success, failed, avg_tok, avg_lat = row
                success_rate = success / total if total > 0 else 0.0
                
                # Estimate cost (very rough: $0.0001 per 1K tokens)
                total_cost = (total * avg_tok / 1000) * 0.0001
                
                return ModelMetrics(
                    model_name=model,
                    total_runs=int(total),
                    successful_runs=int(success),
                    failed_runs=int(failed),
                    avg_tokens=float(avg_tok),
                    avg_latency=float(avg_lat),
                    success_rate=success_rate,
                    total_cost_estimate=total_cost
                )
                
        except Exception as e:
            logger.error(f"Failed to get model metrics: {e}")
            return None
    
    def get_recent_runs(self, limit: int = 10) -> List[PipelineRun]:
        """Get recent pipeline runs"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT run_id, timestamp, idea, model_used, stage,
                           success, tokens_used, latency_seconds, error, metadata
                    FROM pipeline_runs
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,))
                
                runs = []
                for row in cursor.fetchall():
                    metadata = json.loads(row[9]) if row[9] else None
                    runs.append(PipelineRun(
                        run_id=row[0],
                        timestamp=row[1],
                        idea=row[2],
                        model_used=row[3],
                        stage=row[4],
                        success=bool(row[5]),
                        tokens_used=row[6],
                        latency_seconds=row[7],
                        error=row[8],
                        metadata=metadata
                    ))
                
                return runs
                
        except Exception as e:
            logger.error(f"Failed to get recent runs: {e}")
            return []
    
    def get_stage_statistics(self, stage: str, days: int = 7) -> Dict[str, Any]:
        """Get statistics for a specific stage"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes,
                        AVG(tokens_used) as avg_tokens,
                        AVG(latency_seconds) as avg_latency,
                        MIN(latency_seconds) as min_latency,
                        MAX(latency_seconds) as max_latency
                    FROM pipeline_runs
                    WHERE stage = ?
                    AND date(timestamp) >= date('now', ?)
                """, (stage, f'-{days} days'))
                
                row = cursor.fetchone()
                
                if not row or not row[0]:
                    return {}
                
                total, successes, avg_tok, avg_lat, min_lat, max_lat = row
                
                return {
                    "stage": stage,
                    "total_runs": total,
                    "successful_runs": successes,
                    "success_rate": successes / total if total > 0 else 0.0,
                    "avg_tokens": float(avg_tok) if avg_tok else 0.0,
                    "avg_latency_seconds": float(avg_lat) if avg_lat else 0.0,
                    "min_latency_seconds": float(min_lat) if min_lat else 0.0,
                    "max_latency_seconds": float(max_lat) if max_lat else 0.0,
                }
                
        except Exception as e:
            logger.error(f"Failed to get stage statistics: {e}")
            return {}
    
    def get_total_cost_estimate(self, days: int = 30) -> float:
        """Get total estimated cost over last N days"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT SUM(estimated_cost)
                    FROM cost_tracking
                    WHERE date >= date('now', ?)
                """, (f'-{days} days',))
                
                row = cursor.fetchone()
                return float(row[0]) if row and row[0] else 0.0
                
        except Exception as e:
            logger.error(f"Failed to get total cost: {e}")
            return 0.0
