"""Base classes for web search functionality."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import time
import hashlib
import json


@dataclass
class SearchResult:
    """Standardized search result across all sources."""
    
    url: str
    title: str
    content: str
    source: str  # "searxng", "arxiv", "github", etc.
    published_date: Optional[str] = None
    relevance_score: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "url": self.url,
            "title": self.title,
            "content": self.content,
            "source": self.source,
            "published_date": self.published_date,
            "relevance_score": self.relevance_score,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SearchResult":
        """Create from dictionary."""
        return cls(**data)


class SearchCache:
    """Cache for search results to avoid redundant API calls."""
    
    def __init__(self, ttl_seconds: int = 3600):
        """
        Initialize cache.
        
        Args:
            ttl_seconds: Time-to-live for cached results (default: 1 hour)
        """
        self.cache: Dict[str, tuple[List[SearchResult], float]] = {}
        self.ttl = ttl_seconds
    
    def _normalize_query(self, query: str) -> str:
        """Normalize query for consistent caching."""
        return query.lower().strip()
    
    def _get_cache_key(self, source: str, query: str) -> str:
        """Generate cache key from source and query."""
        normalized = self._normalize_query(query)
        combined = f"{source}:{normalized}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    def get(self, source: str, query: str) -> Optional[List[SearchResult]]:
        """
        Get cached results if available and not expired.
        
        Args:
            source: Source identifier (e.g., "searxng", "arxiv")
            query: Search query
            
        Returns:
            Cached results if available, None otherwise
        """
        cache_key = self._get_cache_key(source, query)
        
        if cache_key in self.cache:
            results, timestamp = self.cache[cache_key]
            
            # Check if expired
            if time.time() - timestamp < self.ttl:
                return results
            else:
                # Remove expired entry
                del self.cache[cache_key]
        
        return None
    
    def set(self, source: str, query: str, results: List[SearchResult]) -> None:
        """
        Cache search results.
        
        Args:
            source: Source identifier
            query: Search query
            results: Search results to cache
        """
        cache_key = self._get_cache_key(source, query)
        self.cache[cache_key] = (results, time.time())
    
    def clear(self) -> None:
        """Clear all cached results."""
        self.cache.clear()
    
    def clear_expired(self) -> int:
        """
        Remove expired entries from cache.
        
        Returns:
            Number of entries removed
        """
        current_time = time.time()
        expired_keys = [
            key for key, (_, timestamp) in self.cache.items()
            if current_time - timestamp >= self.ttl
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = len(self.cache)
        current_time = time.time()
        
        valid = sum(
            1 for _, timestamp in self.cache.values()
            if current_time - timestamp < self.ttl
        )
        
        return {
            "total_entries": total,
            "valid_entries": valid,
            "expired_entries": total - valid,
            "ttl_seconds": self.ttl
        }


class WebSearcher(ABC):
    """Abstract base class for all web search sources."""
    
    @abstractmethod
    async def search(
        self, 
        query: str, 
        max_results: int = 5,
        **kwargs
    ) -> List[SearchResult]:
        """
        Execute search and return standardized results.
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return
            **kwargs: Additional source-specific parameters
            
        Returns:
            List of SearchResult objects
        """
        pass
    
    @abstractmethod
    def get_source_name(self) -> str:
        """
        Return source identifier.
        
        Returns:
            Source name (e.g., "searxng", "arxiv")
        """
        pass
    
    def is_available(self) -> bool:
        """
        Check if this search source is available.
        
        Returns:
            True if source can be used, False otherwise
        """
        return True
    
    def get_priority(self) -> int:
        """
        Get priority order for this source (lower = higher priority).
        
        Returns:
            Priority value (0-100)
        """
        return 50  # Default medium priority
