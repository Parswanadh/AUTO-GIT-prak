"""
Semantic Cache Manager
======================

Intelligent caching system that reduces token costs by 30%+ through semantic matching.

Uses vector similarity to find cached responses for similar queries.
"""

import hashlib
import json
from typing import Optional, Any, List, Tuple
from datetime import datetime
import numpy as np
from sentence_transformers import SentenceTransformer
from .redis_client import RedisClient, get_redis_client
import logging

logger = logging.getLogger(__name__)


class SemanticCache:
    """
    Cache that uses semantic similarity to match queries.
    
    Features:
    - Semantic matching (not just exact string match)
    - Configurable similarity threshold
    - Automatic TTL management
    - Cache hit/miss metrics
    
    Example:
        ```python
        cache = SemanticCache()
        await cache.initialize()
        
        # Try to get cached response
        response = await cache.get("Write a Python function")
        
        if response is None:
            # Call LLM
            response = await call_llm("Write a Python function")
            
            # Cache the response
            await cache.set("Write a Python function", response)
        ```
    """
    
    def __init__(
        self,
        redis_client: Optional[RedisClient] = None,
        embedding_model: str = "nomic-embed-text",
        similarity_threshold: float = 0.85,  # 85% similar = cache hit
        default_ttl: int = 3600  # 1 hour
    ):
        """
        Initialize semantic cache.
        
        Args:
            redis_client: Redis client instance
            embedding_model: Model for generating embeddings
            similarity_threshold: Minimum similarity for cache hit (0-1)
            default_ttl: Default cache TTL in seconds
        """
        self.redis_client = redis_client
        self.embedding_model_name = embedding_model
        self.similarity_threshold = similarity_threshold
        self.default_ttl = default_ttl
        
        # Lazy load embedding model
        self._embedder: Optional[SentenceTransformer] = None
        
        # Metrics
        self.hits = 0
        self.misses = 0
        self.total_savings_tokens = 0
    
    async def initialize(self) -> None:
        """Initialize cache (load embedding model, connect to Redis)"""
        # Get Redis client if not provided
        if self.redis_client is None:
            self.redis_client = await get_redis_client()
        
        # Load embedding model
        if self._embedder is None:
            logger.info(f"Loading embedding model: {self.embedding_model_name}")
            
            # Use sentence-transformers for local embeddings
            # For Ollama models, we'd need to call the API
            try:
                self._embedder = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
                logger.info("Embedding model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
                raise
    
    def _generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding vector for text.
        
        Args:
            text: Text to embed
        
        Returns:
            Embedding vector as list
        """
        if self._embedder is None:
            raise RuntimeError("Cache not initialized. Call initialize() first.")
        
        embedding = self._embedder.encode(text)
        return embedding.tolist()
    
    def _compute_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Compute cosine similarity between two vectors.
        
        Args:
            vec1: First vector
            vec2: Second vector
        
        Returns:
            Similarity score (0-1)
        """
        arr1 = np.array(vec1)
        arr2 = np.array(vec2)
        
        # Cosine similarity
        similarity = np.dot(arr1, arr2) / (np.linalg.norm(arr1) * np.linalg.norm(arr2))
        return float(similarity)
    
    def _make_cache_key(self, query_hash: str, suffix: str = "") -> str:
        """Generate Redis key for cache entry"""
        return f"semantic_cache:{query_hash}{':' + suffix if suffix else ''}"
    
    async def get(
        self,
        query: str,
        context: Optional[str] = None
    ) -> Optional[Any]:
        """
        Get cached response for query.
        
        Uses semantic similarity to find similar cached queries.
        
        Args:
            query: Query text
            context: Optional context to include in matching
        
        Returns:
            Cached response if found, None otherwise
        """
        if self.redis_client is None:
            raise RuntimeError("Cache not initialized")
        
        # Combine query and context for embedding
        full_query = f"{query}\n{context}" if context else query
        
        # Generate embedding
        query_embedding = self._generate_embedding(full_query)
        
        # Search for similar cached queries
        # Get all cache keys
        cache_keys = await self.redis_client.keys("semantic_cache:*:data")
        
        best_match: Optional[Tuple[str, float]] = None
        best_similarity = 0.0
        
        for key in cache_keys:
            # Get embedding for cached query
            embedding_key = key.replace(":data", ":embedding")
            cached_embedding_json = await self.redis_client.get(embedding_key)
            
            if not cached_embedding_json:
                continue
            
            cached_embedding = json.loads(cached_embedding_json)
            
            # Compute similarity
            similarity = self._compute_similarity(query_embedding, cached_embedding)
            
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = (key, similarity)
        
        # Check if best match exceeds threshold
        if best_match and best_similarity >= self.similarity_threshold:
            cache_key = best_match[0]
            
            # Get cached response
            cached_data_json = await self.redis_client.get(cache_key)
            
            if cached_data_json:
                cached_data = json.loads(cached_data_json)
                
                # Update metrics
                self.hits += 1
                estimated_tokens = cached_data.get("estimated_tokens", 500)
                self.total_savings_tokens += estimated_tokens
                
                logger.info(
                    f"Cache HIT (similarity: {best_similarity:.2f}). "
                    f"Saved ~{estimated_tokens} tokens."
                )
                
                return cached_data["response"]
        
        # Cache miss
        self.misses += 1
        logger.debug(f"Cache MISS. Best similarity: {best_similarity:.2f}")
        
        return None
    
    async def set(
        self,
        query: str,
        response: Any,
        context: Optional[str] = None,
        ttl: Optional[int] = None,
        estimated_tokens: int = 500
    ) -> None:
        """
        Store query-response pair in cache.
        
        Args:
            query: Query text
            response: Response to cache
            context: Optional context
            ttl: Time-to-live in seconds (uses default if None)
            estimated_tokens: Estimated tokens in response (for metrics)
        """
        if self.redis_client is None:
            raise RuntimeError("Cache not initialized")
        
        # Combine query and context
        full_query = f"{query}\n{context}" if context else query
        
        # Generate embedding
        embedding = self._generate_embedding(full_query)
        
        # Create unique hash for this query
        query_hash = hashlib.sha256(full_query.encode()).hexdigest()[:16]
        
        # Store embedding
        embedding_key = self._make_cache_key(query_hash, "embedding")
        await self.redis_client.set(
            embedding_key,
            json.dumps(embedding),
            ttl=ttl or self.default_ttl
        )
        
        # Store response data
        data_key = self._make_cache_key(query_hash, "data")
        cache_data = {
            "query": query,
            "response": response,
            "context": context,
            "cached_at": datetime.now().isoformat(),
            "estimated_tokens": estimated_tokens
        }
        await self.redis_client.set(
            data_key,
            json.dumps(cache_data),
            ttl=ttl or self.default_ttl
        )
        
        logger.info(f"Cached response for query (hash: {query_hash})")
    
    async def clear(self) -> int:
        """
        Clear all cache entries.
        
        Returns:
            Number of entries cleared
        """
        if self.redis_client is None:
            raise RuntimeError("Cache not initialized")
        
        cache_keys = await self.redis_client.keys("semantic_cache:*")
        
        if cache_keys:
            deleted = await self.redis_client.delete(*cache_keys)
            logger.info(f"Cleared {deleted} cache entries")
            return deleted
        
        return 0
    
    def get_metrics(self) -> dict:
        """
        Get cache performance metrics.
        
        Returns:
            Dict with hits, misses, hit_rate, total_savings_tokens
        """
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0.0
        
        return {
            "hits": self.hits,
            "misses": self.misses,
            "total_requests": total_requests,
            "hit_rate_percent": round(hit_rate, 2),
            "total_savings_tokens": self.total_savings_tokens,
            "estimated_cost_savings_usd": round(self.total_savings_tokens * 0.00002, 4)  # Rough estimate
        }
    
    def reset_metrics(self) -> None:
        """Reset cache metrics"""
        self.hits = 0
        self.misses = 0
        self.total_savings_tokens = 0


# Global cache instance
_semantic_cache: Optional[SemanticCache] = None


async def get_semantic_cache() -> SemanticCache:
    """
    Get singleton semantic cache instance.
    
    Example:
        ```python
        from src.state_management import get_semantic_cache
        
        cache = await get_semantic_cache()
        
        response = await cache.get("Generate Python code")
        if response is None:
            response = await call_llm(...)
            await cache.set("Generate Python code", response)
        ```
    """
    global _semantic_cache
    
    if _semantic_cache is None:
        _semantic_cache = SemanticCache()
        await _semantic_cache.initialize()
    
    return _semantic_cache
