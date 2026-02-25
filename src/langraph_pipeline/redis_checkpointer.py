"""
Redis-based checkpointer for LangGraph.

Replaces in-memory MemorySaver with Redis persistence.
Survives restarts and enables distributed workflows.
"""

from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint
from typing import Optional, Iterator, Tuple
import pickle
import logging

logger = logging.getLogger(__name__)


class RedisCheckpointSaver(BaseCheckpointSaver):
    """
    Checkpoint saver that persists to Redis.
    
    Survives restarts, enables distributed workflows.
    
    Usage:
        checkpointer = RedisCheckpointSaver()
        app = workflow.compile(checkpointer=checkpointer)
    """
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        ttl: int = 86400  # 24 hours
    ):
        self.redis_url = redis_url
        self.ttl = ttl
        self._redis = None
        self._initialize_redis()
    
    def _initialize_redis(self):
        """Initialize Redis connection"""
        try:
            import redis
            self._redis = redis.from_url(self.redis_url, decode_responses=False)
            self._redis.ping()
            logger.info("✅ Redis checkpointer connected")
        except Exception as e:
            logger.warning(f"⚠️  Redis checkpointer unavailable: {e}")
            logger.warning("   Checkpoints will not persist across restarts")
            self._redis = None
    
    def put(self, config: dict, checkpoint: Checkpoint, metadata: dict) -> dict:
        """Save checkpoint to Redis"""
        if self._redis is None:
            return {"configurable": {"thread_id": config.get("configurable", {}).get("thread_id", "default")}}
        
        try:
            thread_id = config.get("configurable", {}).get("thread_id", "default")
            key = f"checkpoint:{thread_id}"
            
            # Serialize checkpoint and metadata
            data = pickle.dumps({
                "checkpoint": checkpoint,
                "metadata": metadata
            })
            
            # Store with TTL
            self._redis.setex(key, self.ttl, data)
            logger.debug(f"💾 Saved checkpoint for thread {thread_id}")
            
            return {"configurable": {"thread_id": thread_id}}
        
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
            return {"configurable": {"thread_id": config.get("configurable", {}).get("thread_id", "default")}}
    
    def get_tuple(self, config: dict) -> Optional[Tuple]:
        """Load checkpoint from Redis"""
        if self._redis is None:
            return None
        
        try:
            thread_id = config.get("configurable", {}).get("thread_id", "default")
            key = f"checkpoint:{thread_id}"
            
            data = self._redis.get(key)
            if data:
                loaded = pickle.loads(data)
                logger.debug(f"📂 Loaded checkpoint for thread {thread_id}")
                return (config, loaded["checkpoint"], loaded["metadata"])
            
            return None
        
        except Exception as e:
            logger.debug(f"Checkpoint load error: {e}")
            return None
    
    def list(self, config: dict) -> Iterator[Tuple]:
        """List all checkpoints (for debugging)"""
        if self._redis is None:
            return
        
        try:
            thread_id = config.get("configurable", {}).get("thread_id", "default")
            pattern = f"checkpoint:{thread_id}*"
            
            for key in self._redis.scan_iter(pattern):
                data = self._redis.get(key)
                if data:
                    loaded = pickle.loads(data)
                    yield (config, loaded["checkpoint"], loaded["metadata"])
        
        except Exception as e:
            logger.error(f"Checkpoint list error: {e}")
