"""
Free Tier Optimizer - Ensure 100% Free Operation

Tracks API usage and enforces free-tier-only operation.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class FreeTierOptimizer:
    """
    Optimize for 100% free operation.
    
    Features:
    - Track daily API usage
    - Enforce free-tier limits
    - Alert before approaching limits
    - Automatic fallback to local if limits reached
    """
    
    def __init__(self, usage_file: str = "./data/api_usage.json"):
        self.usage_file = Path(usage_file)
        self.usage_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Free tier limits (per day)
        self.limits = {
            "groq": {
                "requests_per_day": 14400,
                "models": ["llama-3.1-8b-instant", "llama-3.1-70b", "llama-3.1-405b"]
            },
            "openrouter_free": {
                "requests_per_day": 10000,  # Rate-limited but high
                "models": [
                    "qwen/qwen3-coder:free",
                    "meta-llama/llama-3.1-70b:free",
                    "google/gemini-2.0-flash:free",
                    "xiaomi/mimo-v2-flash:free",
                    "mistralai/devstral-2512:free"
                ]
            },
            "local": {
                "requests_per_day": float('inf'),  # Unlimited
                "cost_per_request": 0.0
            }
        }
        
        # Load usage data
        self.usage = self._load_usage()
        
        logger.info("FreeTierOptimizer initialized - 100% free operation mode")
    
    def _load_usage(self) -> Dict:
        """Load usage data from disk"""
        if self.usage_file.exists():
            with open(self.usage_file, 'r') as f:
                return json.load(f)
        
        return self._create_new_usage()
    
    def _create_new_usage(self) -> Dict:
        """Create new usage tracking structure"""
        return {
            "current_date": datetime.now().strftime("%Y-%m-%d"),
            "groq": {"requests": 0, "cost": 0.0},
            "openrouter_free": {"requests": 0, "cost": 0.0},
            "local": {"requests": 0, "cost": 0.0},
            "history": []
        }
    
    def _save_usage(self):
        """Save usage data to disk"""
        with open(self.usage_file, 'w') as f:
            json.dump(self.usage, f, indent=2)
    
    def _check_date_rollover(self):
        """Check if we need to reset daily counters"""
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        if self.usage["current_date"] != current_date:
            # Archive previous day
            self.usage["history"].append({
                "date": self.usage["current_date"],
                "groq": self.usage["groq"].copy(),
                "openrouter_free": self.usage["openrouter_free"].copy(),
                "local": self.usage["local"].copy()
            })
            
            # Reset counters
            self.usage["current_date"] = current_date
            self.usage["groq"] = {"requests": 0, "cost": 0.0}
            self.usage["openrouter_free"] = {"requests": 0, "cost": 0.0}
            self.usage["local"] = {"requests": 0, "cost": 0.0}
            
            self._save_usage()
            logger.info(f"Daily counters reset for {current_date}")
    
    def can_use_backend(self, backend: str) -> bool:
        """
        Check if backend is available under free tier limits.
        
        Args:
            backend: "groq", "openrouter_free", or "local"
        
        Returns:
            True if can use, False if limit reached
        """
        self._check_date_rollover()
        
        if backend not in self.limits:
            logger.warning(f"Unknown backend: {backend}")
            return False
        
        current_usage = self.usage.get(backend, {}).get("requests", 0)
        limit = self.limits[backend]["requests_per_day"]
        
        if current_usage >= limit:
            logger.warning(f"Free tier limit reached for {backend}: {current_usage}/{limit}")
            return False
        
        # Alert at 80% usage
        if current_usage >= limit * 0.8:
            logger.warning(f"Approaching free tier limit for {backend}: {current_usage}/{limit} (80%+)")
        
        return True
    
    def record_usage(self, backend: str, model: str, tokens: int = 0):
        """
        Record API usage.
        
        Args:
            backend: Backend name
            model: Model used
            tokens: Tokens generated (optional)
        """
        self._check_date_rollover()
        
        if backend not in self.usage:
            self.usage[backend] = {"requests": 0, "cost": 0.0}
        
        self.usage[backend]["requests"] += 1
        self.usage[backend]["cost"] = 0.0  # Always $0 in free tier
        
        self._save_usage()
        
        # Log usage stats
        current = self.usage[backend]["requests"]
        limit = self.limits.get(backend, {}).get("requests_per_day", 0)
        percentage = (current / limit * 100) if limit > 0 else 0
        
        logger.debug(f"API usage: {backend} {current}/{limit} ({percentage:.1f}%)")
    
    def get_usage_stats(self) -> Dict:
        """Get current usage statistics"""
        self._check_date_rollover()
        
        stats = {
            "date": self.usage["current_date"],
            "backends": {}
        }
        
        for backend, limits in self.limits.items():
            current = self.usage.get(backend, {}).get("requests", 0)
            limit = limits["requests_per_day"]
            
            stats["backends"][backend] = {
                "requests": current,
                "limit": limit,
                "percentage": (current / limit * 100) if limit < float('inf') else 0,
                "cost": 0.0  # Always $0
            }
        
        return stats
    
    def get_optimal_backend(
        self, 
        task_type: str,
        prefer_speed: bool = False
    ) -> str:
        """
        Get optimal backend for task while staying free.
        
        Args:
            task_type: Type of task (code_generation, reasoning, etc.)
            prefer_speed: Prefer fastest option
        
        Returns:
            Backend name to use
        """
        self._check_date_rollover()
        
        # Preference order for speed
        if prefer_speed:
            # Groq is fastest (300+ tok/sec)
            if self.can_use_backend("groq"):
                return "groq"
            # OpenRouter free tier next
            elif self.can_use_backend("openrouter_free"):
                return "openrouter_free"
            # Local fallback
            else:
                return "local"
        
        # Preference order for quality
        else:
            # For complex tasks, prefer Groq 70B
            if task_type in ["reasoning", "critique", "architecture"]:
                if self.can_use_backend("groq"):
                    return "groq"
            
            # For code generation, OpenRouter Qwen Coder is excellent
            if task_type == "code_generation":
                if self.can_use_backend("openrouter_free"):
                    return "openrouter_free"
            
            # Local as fallback or for simple tasks
            return "local"
    
    def print_usage_report(self):
        """Print usage report to console"""
        stats = self.get_usage_stats()
        
        print("\n" + "="*60)
        print("📊 FREE TIER USAGE REPORT")
        print("="*60)
        print(f"Date: {stats['date']}")
        print()
        
        total_requests = 0
        total_cost = 0.0
        
        for backend, data in stats["backends"].items():
            print(f"{backend.upper()}:")
            print(f"  Requests: {data['requests']:,} / {data['limit']:,}")
            
            if data['limit'] < float('inf'):
                print(f"  Usage: {data['percentage']:.1f}%")
            
            print(f"  Cost: ${data['cost']:.2f}")
            print()
            
            total_requests += data['requests']
            total_cost += data['cost']
        
        print(f"TOTAL:")
        print(f"  Requests: {total_requests:,}")
        print(f"  Cost: ${total_cost:.2f} ✅ FREE!")
        print("="*60 + "\n")


# Global instance
_optimizer_instance = None


def get_free_tier_optimizer() -> FreeTierOptimizer:
    """Get global FreeTierOptimizer instance"""
    global _optimizer_instance
    if _optimizer_instance is None:
        _optimizer_instance = FreeTierOptimizer()
    return _optimizer_instance


def ensure_free_operation():
    """
    Decorator to ensure function uses only free-tier resources.
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            optimizer = get_free_tier_optimizer()
            
            # Check if we can proceed
            backend = kwargs.get('backend', 'groq')
            if not optimizer.can_use_backend(backend):
                logger.warning(f"Free tier limit reached for {backend}, falling back to local")
                kwargs['backend'] = 'local'
            
            result = await func(*args, **kwargs)
            
            # Record usage
            if 'backend' in kwargs:
                optimizer.record_usage(
                    kwargs['backend'],
                    kwargs.get('model', 'unknown')
                )
            
            return result
        
        return wrapper
    return decorator
