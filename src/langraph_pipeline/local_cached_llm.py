"""
Local Cache Wrapper (No Docker Required)
=========================================

Simple in-memory + disk cache that doesn't need Redis/Docker.
Perfect for local development.
"""

from langchain_ollama import ChatOllama
from typing import Any, Dict, List, Optional
import hashlib
import json
import logging
from pathlib import Path
import time

logger = logging.getLogger(__name__)


# Patch ollama AsyncClient to remove 'think' parameter
try:
    from ollama import AsyncClient as OllamaAsyncClient
    
    _original_ac_chat = OllamaAsyncClient.chat
    
    async def _patched_ac_chat(self, *args, **kwargs):
        """Remove 'think' and 'reasoning' params that cause issues"""
        # Filter at the lowest level possible
        filtered_kwargs = {k: v for k, v in kwargs.items() if k not in ['think', 'reasoning']}
        # Also filter in options dict if present
        if 'options' in filtered_kwargs and isinstance(filtered_kwargs['options'], dict):
            filtered_kwargs['options'] = {
                k: v for k, v in filtered_kwargs['options'].items() 
                if k not in ['think', 'reasoning']
            }
        return await _original_ac_chat(self, *args, **filtered_kwargs)
    
    OllamaAsyncClient.chat = _patched_ac_chat
    logger.info("✅ Patched Ollama AsyncClient to filter 'think' parameter")
except Exception as e:
    logger.warning(f"⚠️  Could not patch Ollama AsyncClient: {e}")


class LocalCachedLLM(ChatOllama):
    """
    ChatOllama with local file-based caching.
    
    No Redis, no Docker, just files on disk.
    
    Drop-in replacement:
        llm = ChatOllama(model="qwen2.5-coder:7b")
    Becomes:
        llm = LocalCachedLLM(model="qwen2.5-coder:7b")
    """
    
    class Config:
        """Allow extra fields for our cache parameters"""
        arbitrary_types_allowed = True
        extra = "allow"
    
    def __init__(
        self,
        *args,
        cache_dir: str = ".cache/llm",
        cache_ttl: int = 3600,
        similarity_threshold: float = 0.85,
        enable_cache: bool = True,
        **kwargs
    ):
        # Filter out deepseek-r1 specific parameters that other models don't support
        filtered_kwargs = {k: v for k, v in kwargs.items() if k not in ['think']}
        
        # Explicitly disable reasoning/think mode for non-deepseek models
        if 'reasoning' not in filtered_kwargs:
            filtered_kwargs['reasoning'] = False
        
        super().__init__(*args, **filtered_kwargs)
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.cache_ttl = cache_ttl
        self.similarity_threshold = similarity_threshold
        self.enable_cache = enable_cache
        
        # In-memory cache for speed
        self._memory_cache: Dict[str, tuple] = {}  # hash -> (response, timestamp, embedding)
        
        # Load embedding model lazily
        self._embedder = None
        
        # Metrics
        self.cache_hits = 0
        self.cache_misses = 0
        self.tokens_saved = 0
        
        # Remove 'think' from model_kwargs if present (deepseek-r1 specific)
        if hasattr(self, 'model_kwargs') and self.model_kwargs:
            self.model_kwargs = {k: v for k, v in self.model_kwargs.items() if k != 'think'}
        
        # Force reasoning=False to prevent think parameter
        if hasattr(self, 'reasoning'):
            object.__setattr__(self, 'reasoning', False)
        
        logger.info(f"✅ Local cache initialized at {self.cache_dir}")
    
    def _filter_kwargs(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Filter out unsupported parameters like 'think' (deepseek-r1 specific)"""
        unsupported = ['think', 'reasoning']  # deepseek-r1 specific params
        filtered = {k: v for k, v in kwargs.items() if k not in unsupported}
        # Also check nested dicts
        if 'options' in filtered and isinstance(filtered['options'], dict):
            filtered['options'] = {k: v for k, v in filtered['options'].items() if k not in unsupported}
        return filtered
    
    def bind(self, **kwargs):
        """Override bind to filter unsupported params"""
        filtered = self._filter_kwargs(kwargs)
        return super().bind(**filtered)
    
    def _prepare_request(self, **kwargs):
        """Override to filter all request params"""
        filtered = self._filter_kwargs(kwargs)
        if hasattr(super(), '_prepare_request'):
            return super()._prepare_request(**filtered)
        return filtered
    
    def _get_embedder(self):
        """Get or create embedding model"""
        if self._embedder is None and self.enable_cache:
            try:
                # Try to load sentence-transformers
                from sentence_transformers import SentenceTransformer
                logger.info("Loading embedding model...")
                self._embedder = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
                logger.info("✅ Embedding model loaded")
            except ImportError as e:
                # Python 3.14 compatibility issue - use text matching instead
                logger.info(f"⚠️  Sentence-transformers not available ({e}). Using text-based matching.")
                self._embedder = "text-only"
            except Exception as e:
                logger.warning(f"⚠️  Could not load embeddings: {e}. Using fuzzy text matching instead.")
                self._embedder = "text-only"
        
        return self._embedder
    
    def _create_cache_key(self, messages: Any) -> tuple:
        """Create cache key and embedding from messages"""
        try:
            # Convert messages to string
            if isinstance(messages, list):
                text = "\n".join(str(msg.content if hasattr(msg, 'content') else msg) for msg in messages)
            else:
                text = str(messages)
            
            # Create hash
            cache_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
            
            # Generate embedding for semantic matching
            embedder = self._get_embedder()
            if embedder and embedder != "text-only":
                embedding = embedder.encode(text).tolist()
            elif embedder == "text-only":
                # Use text itself as "embedding" for fuzzy matching
                embedding = text
            else:
                embedding = None
            
            return cache_hash, embedding
        except Exception as e:
            logger.debug(f"Cache key creation failed: {e}")
            return None, None
    
    def _compute_similarity(self, emb1, emb2) -> float:
        """Compute similarity (cosine for vectors, text match for strings)"""
        try:
            # Text-based fuzzy matching
            if isinstance(emb1, str) and isinstance(emb2, str):
                from difflib import SequenceMatcher
                return SequenceMatcher(None, emb1.lower(), emb2.lower()).ratio()
            
            # Vector-based cosine similarity
            import numpy as np
            arr1 = np.array(emb1)
            arr2 = np.array(emb2)
            return float(np.dot(arr1, arr2) / (np.linalg.norm(arr1) * np.linalg.norm(arr2)))
        except Exception:
            return 0.0
    
    def _is_cache_valid(self, timestamp: float) -> bool:
        """Check if cache entry is still valid (TTL)"""
        return (time.time() - timestamp) < self.cache_ttl
    
    def _check_memory_cache(self, query_embedding: Optional[List[float]]) -> Optional[Any]:
        """Check in-memory cache first (fast)"""
        if not self.enable_cache or not query_embedding:
            return None
        
        best_match = None
        best_similarity = 0.0
        
        for cache_hash, (response, timestamp, embedding) in self._memory_cache.items():
            # Check TTL
            if not self._is_cache_valid(timestamp):
                continue
            
            # Check similarity
            if embedding:
                similarity = self._compute_similarity(query_embedding, embedding)
                if similarity > best_similarity and similarity >= self.similarity_threshold:
                    best_similarity = similarity
                    best_match = response
        
        if best_match:
            self.cache_hits += 1
            self.tokens_saved += 500
            logger.info(f"⚡ Memory cache HIT (similarity: {best_similarity:.1%})")
            return best_match
        
        return None
    
    def _check_disk_cache(self, query_embedding: Optional[List[float]]) -> Optional[Any]:
        """Check disk cache (slower but persistent)"""
        if not self.enable_cache or not query_embedding:
            return None
        
        try:
            best_match = None
            best_similarity = 0.0
            
            # Search all cache files
            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                    
                    # Check TTL
                    if not self._is_cache_valid(cache_data['timestamp']):
                        cache_file.unlink()  # Delete expired
                        continue
                    
                    # Check similarity
                    if cache_data.get('embedding'):
                        similarity = self._compute_similarity(
                            query_embedding,
                            cache_data['embedding']
                        )
                        
                        if similarity > best_similarity and similarity >= self.similarity_threshold:
                            best_similarity = similarity
                            best_match = cache_data['response']
                            
                            # Load into memory cache for next time
                            cache_hash = cache_file.stem
                            self._memory_cache[cache_hash] = (
                                cache_data['response'],
                                cache_data['timestamp'],
                                cache_data['embedding']
                            )
                
                except Exception as e:
                    logger.debug(f"Error reading cache file {cache_file}: {e}")
                    continue
            
            if best_match:
                self.cache_hits += 1
                self.tokens_saved += 500
                logger.info(f"⚡ Disk cache HIT (similarity: {best_similarity:.1%})")
                return best_match
            
        except Exception as e:
            logger.debug(f"Disk cache check error: {e}")
        
        return None
    
    def _store_cache(self, messages: Any, response: Any) -> None:
        """Store in both memory and disk cache"""
        if not self.enable_cache:
            return
        
        try:
            cache_hash, embedding = self._create_cache_key(messages)
            if not cache_hash:
                return
            
            response_content = response.content if hasattr(response, 'content') else str(response)
            timestamp = time.time()
            
            # Store in memory
            self._memory_cache[cache_hash] = (response_content, timestamp, embedding)
            
            # Store on disk
            cache_file = self.cache_dir / f"{cache_hash}.json"
            cache_data = {
                'response': response_content,
                'timestamp': timestamp,
                'embedding': embedding
            }
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f)
            
            logger.debug(f"💾 Cached to {cache_file.name}")
        
        except Exception as e:
            logger.debug(f"Cache store error: {e}")
    
    async def ainvoke(self, messages: Any, **kwargs) -> Any:
        """Async invoke with caching"""
        if not self.enable_cache:
            return await super().ainvoke(messages, **kwargs)
        
        # Create embedding for query
        _, query_embedding = self._create_cache_key(messages)
        
        # Check memory cache first (fast)
        cached_response = self._check_memory_cache(query_embedding)
        if cached_response:
            from langchain_core.messages import AIMessage
            return AIMessage(content=cached_response)
        
        # Check disk cache (persistent)
        cached_response = self._check_disk_cache(query_embedding)
        if cached_response:
            from langchain_core.messages import AIMessage
            return AIMessage(content=cached_response)
        
        # Cache miss - call real LLM
        self.cache_misses += 1
        logger.debug(f"Cache MISS - calling LLM")
        
        # Filter out unsupported params
        filtered_kwargs = self._filter_kwargs(kwargs)
        
        response = await super().ainvoke(messages, **filtered_kwargs)
        
        # Store in cache
        self._store_cache(messages, response)
        
        return response
    
    def invoke(self, messages: Any, **kwargs) -> Any:
        """Sync invoke"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import nest_asyncio
                nest_asyncio.apply()
        except RuntimeError:
            pass
        
        return asyncio.run(self.ainvoke(messages, **kwargs))
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        total = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total * 100) if total > 0 else 0.0
        
        # Count disk cache files
        cache_files = len(list(self.cache_dir.glob("*.json")))
        
        return {
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "total_requests": total,
            "hit_rate_percent": round(hit_rate, 2),
            "tokens_saved": self.tokens_saved,
            "estimated_savings_usd": round(self.tokens_saved * 0.00002, 4),
            "memory_cache_size": len(self._memory_cache),
            "disk_cache_files": cache_files
        }
    
    def clear_cache(self) -> None:
        """Clear all cache (memory + disk)"""
        self._memory_cache.clear()
        
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()
        
        logger.info("🗑️  Cache cleared")
