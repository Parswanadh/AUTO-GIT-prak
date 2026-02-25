"""
Semantic Caching System for LLM Responses

This module provides intelligent caching of LLM responses based on semantic similarity
of prompts. Uses embedding models to find similar past queries and return cached responses.

Features:
- Semantic similarity matching (not just exact string match)
- Configurable similarity threshold
- TTL (time-to-live) support
- Backend-specific caching
- Cache invalidation
- Statistics tracking

Architecture:
- EmbeddingCache: Stores embeddings and responses
- SemanticMatcher: Finds similar queries
- CacheManager: Orchestrates caching logic

Benefits:
- Reduces API calls (saves on rate limits)
- Faster responses (no LLM call needed)
- Cost savings (even on free tier, respects rate limits)
- Consistent responses for similar queries
"""

import json
import hashlib
import time
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
import numpy as np

from src.utils.logger import get_logger

logger = get_logger("semantic_cache")


@dataclass
class CachedResponse:
    """A cached LLM response with metadata."""
    query: str
    query_embedding: List[float]
    response: str
    backend: str
    model: str
    tokens: int
    timestamp: float
    ttl_seconds: int = 3600  # 1 hour default
    hit_count: int = 0
    
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        return time.time() - self.timestamp > self.ttl_seconds
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON storage."""
        return {
            "query": self.query,
            "query_embedding": self.query_embedding,
            "response": self.response,
            "backend": self.backend,
            "model": self.model,
            "tokens": self.tokens,
            "timestamp": self.timestamp,
            "ttl_seconds": self.ttl_seconds,
            "hit_count": self.hit_count
        }
    
    @staticmethod
    def from_dict(data: Dict) -> 'CachedResponse':
        """Create from dictionary."""
        return CachedResponse(**data)


@dataclass
class CacheStats:
    """Statistics about cache performance."""
    total_queries: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    api_calls_saved: int = 0
    tokens_saved: int = 0
    avg_similarity_on_hit: float = 0.0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        if self.total_queries == 0:
            return 0.0
        return self.cache_hits / self.total_queries
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "total_queries": self.total_queries,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": self.hit_rate,
            "api_calls_saved": self.api_calls_saved,
            "tokens_saved": self.tokens_saved,
            "avg_similarity_on_hit": self.avg_similarity_on_hit
        }


class SemanticCache:
    """
    Semantic cache for LLM responses using embedding-based similarity matching.
    
    Instead of exact string matching, this cache finds semantically similar
    queries and returns cached responses if similarity is above threshold.
    
    Uses a simple embedding model (all-minilm) that's fast and lightweight.
    """
    
    def __init__(
        self,
        cache_dir: str = "./data/semantic_cache",
        similarity_threshold: float = 0.85,
        default_ttl: int = 3600,
        embedding_model: str = "all-minilm",
        max_cache_size: int = 10000
    ):
        """
        Initialize semantic cache.
        
        Args:
            cache_dir: Directory to store cache data
            similarity_threshold: Minimum cosine similarity for cache hit (0-1)
            default_ttl: Default time-to-live in seconds
            embedding_model: Model to use for embeddings (small & fast)
            max_cache_size: Maximum number of cached entries
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.similarity_threshold = similarity_threshold
        self.default_ttl = default_ttl
        self.embedding_model = embedding_model
        self.max_cache_size = max_cache_size
        
        # In-memory cache
        self.cache: Dict[str, CachedResponse] = {}
        
        # Statistics
        self.stats = CacheStats()
        
        # Load from disk
        self._load_cache()
        
        logger.info(f"SemanticCache initialized: {len(self.cache)} entries, threshold={similarity_threshold}")
    
    def _generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text using Ollama's embedding model.
        
        Falls back to simple hash-based embedding if Ollama not available.
        """
        try:
            import requests
            
            response = requests.post(
                "http://localhost:11434/api/embeddings",
                json={
                    "model": self.embedding_model,
                    "prompt": text
                },
                timeout=5
            )
            
            if response.status_code == 200:
                embedding = response.json().get("embedding", [])
                if embedding:
                    return embedding
        except Exception as e:
            logger.debug(f"Embedding generation failed: {e}, using fallback")
        
        # Fallback: simple hash-based embedding (not semantic, but better than nothing)
        hash_value = hashlib.md5(text.encode()).hexdigest()
        # Convert hex to normalized float vector
        embedding = [int(hash_value[i:i+2], 16) / 255.0 for i in range(0, len(hash_value), 2)]
        return embedding
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(a) != len(b):
            return 0.0
        
        a_array = np.array(a)
        b_array = np.array(b)
        
        dot_product = np.dot(a_array, b_array)
        norm_a = np.linalg.norm(a_array)
        norm_b = np.linalg.norm(b_array)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot_product / (norm_a * norm_b)
    
    def _find_similar(self, query_embedding: List[float]) -> Optional[Tuple[str, float]]:
        """
        Find most similar cached query.
        
        Returns:
            Tuple of (cache_key, similarity_score) or None
        """
        best_match = None
        best_similarity = 0.0
        
        for key, cached in self.cache.items():
            if cached.is_expired():
                continue
            
            similarity = self._cosine_similarity(query_embedding, cached.query_embedding)
            
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = key
        
        if best_similarity >= self.similarity_threshold:
            return (best_match, best_similarity)
        
        return None
    
    def get(self, query: str, backend: str = None) -> Optional[Tuple[str, Dict]]:
        """
        Get cached response for query if similar enough.
        
        Args:
            query: Query text
            backend: Optional backend filter
            
        Returns:
            Tuple of (response_text, metadata) or None if cache miss
        """
        self.stats.total_queries += 1
        
        # Generate embedding
        query_embedding = self._generate_embedding(query)
        
        # Find similar query
        match = self._find_similar(query_embedding)
        
        if match:
            key, similarity = match
            cached = self.cache[key]
            
            # Check backend filter
            if backend and cached.backend != backend:
                self.stats.cache_misses += 1
                return None
            
            # Cache hit!
            cached.hit_count += 1
            self.stats.cache_hits += 1
            self.stats.api_calls_saved += 1
            self.stats.tokens_saved += cached.tokens
            
            # Update running average of similarity
            n = self.stats.cache_hits
            self.stats.avg_similarity_on_hit = (
                (self.stats.avg_similarity_on_hit * (n - 1) + similarity) / n
            )
            
            logger.info(f"✅ Cache HIT (similarity={similarity:.3f}): {query[:50]}...")
            
            metadata = {
                "cached": True,
                "similarity": similarity,
                "original_query": cached.query,
                "backend": cached.backend,
                "model": cached.model,
                "tokens": cached.tokens,
                "hit_count": cached.hit_count
            }
            
            return (cached.response, metadata)
        
        # Cache miss
        self.stats.cache_misses += 1
        logger.debug(f"❌ Cache MISS: {query[:50]}...")
        return None
    
    def put(
        self,
        query: str,
        response: str,
        backend: str,
        model: str,
        tokens: int,
        ttl_seconds: Optional[int] = None
    ):
        """
        Store response in cache.
        
        Args:
            query: Query text
            response: LLM response
            backend: Backend used (groq, openrouter, local)
            model: Model used
            tokens: Number of tokens in response
            ttl_seconds: Optional TTL override
        """
        # Generate embedding
        query_embedding = self._generate_embedding(query)
        
        # Create cache key (hash of query)
        key = hashlib.md5(query.encode()).hexdigest()
        
        # Create cached response
        cached = CachedResponse(
            query=query,
            query_embedding=query_embedding,
            response=response,
            backend=backend,
            model=model,
            tokens=tokens,
            timestamp=time.time(),
            ttl_seconds=ttl_seconds or self.default_ttl
        )
        
        # Store in cache
        self.cache[key] = cached
        
        # Evict old entries if cache too large
        if len(self.cache) > self.max_cache_size:
            self._evict_oldest()
        
        logger.debug(f"💾 Cached response: {query[:50]}... (key={key[:8]})")
    
    def _evict_oldest(self):
        """Evict oldest cache entries to maintain max size."""
        # Sort by timestamp and remove oldest 10%
        sorted_items = sorted(
            self.cache.items(),
            key=lambda x: x[1].timestamp
        )
        
        evict_count = len(self.cache) // 10
        for i in range(evict_count):
            key, _ = sorted_items[i]
            del self.cache[key]
        
        logger.info(f"♻️  Evicted {evict_count} old cache entries")
    
    def clear_expired(self):
        """Remove all expired cache entries."""
        expired_keys = [
            key for key, cached in self.cache.items()
            if cached.is_expired()
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            logger.info(f"♻️  Cleared {len(expired_keys)} expired cache entries")
    
    def clear_all(self):
        """Clear entire cache."""
        self.cache.clear()
        self.stats = CacheStats()
        logger.info("🗑️  Cleared all cache entries")
    
    def _load_cache(self):
        """Load cache from disk."""
        cache_file = self.cache_dir / "cache.json"
        stats_file = self.cache_dir / "stats.json"
        
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                
                for key, cached_dict in data.items():
                    self.cache[key] = CachedResponse.from_dict(cached_dict)
                
                logger.info(f"📂 Loaded {len(self.cache)} cache entries from disk")
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")
        
        if stats_file.exists():
            try:
                with open(stats_file, 'r') as f:
                    stats_dict = json.load(f)
                
                # Remove computed properties that aren't in __init__
                stats_dict.pop('hit_rate', None)
                
                self.stats = CacheStats(**stats_dict)
            except Exception as e:
                logger.warning(f"Failed to load stats: {e}")
    
    def save(self):
        """Save cache to disk."""
        cache_file = self.cache_dir / "cache.json"
        stats_file = self.cache_dir / "stats.json"
        
        try:
            # Save cache
            cache_dict = {
                key: cached.to_dict()
                for key, cached in self.cache.items()
            }
            
            with open(cache_file, 'w') as f:
                json.dump(cache_dict, f, indent=2)
            
            # Save stats
            with open(stats_file, 'w') as f:
                json.dump(self.stats.to_dict(), f, indent=2)
            
            logger.info(f"💾 Saved {len(self.cache)} cache entries to disk")
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")
    
    def get_stats(self) -> Dict:
        """Get cache statistics."""
        return self.stats.to_dict()
    
    def print_stats(self):
        """Print cache statistics to console."""
        stats = self.stats
        
        print("="*60)
        print("📊 SEMANTIC CACHE STATISTICS")
        print("="*60)
        print(f"Total Queries: {stats.total_queries}")
        print(f"Cache Hits: {stats.cache_hits}")
        print(f"Cache Misses: {stats.cache_misses}")
        print(f"Hit Rate: {stats.hit_rate:.1%}")
        print(f"API Calls Saved: {stats.api_calls_saved}")
        print(f"Tokens Saved: {stats.tokens_saved:,}")
        print(f"Avg Similarity on Hit: {stats.avg_similarity_on_hit:.3f}")
        print(f"Cache Size: {len(self.cache)} entries")
        print("="*60)


# Singleton instance
_cache_instance: Optional[SemanticCache] = None


def get_semantic_cache() -> SemanticCache:
    """Get or create global semantic cache instance."""
    global _cache_instance
    
    if _cache_instance is None:
        _cache_instance = SemanticCache()
    
    return _cache_instance
