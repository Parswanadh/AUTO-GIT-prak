"""DuckDuckGo web search integration - reliable fallback."""

import logging
from typing import List, Optional
from datetime import datetime

try:
    from ddgs import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False
    logging.warning("ddgs not installed. Run: pip install ddgs")

from .web_searcher import WebSearcher, SearchResult

logger = logging.getLogger(__name__)


class DuckDuckGoSearcher(WebSearcher):
    """
    DuckDuckGo web search integration.
    
    Advantages:
    - Free, no API key required
    - No rate limits (reasonable use)
    - Privacy-focused
    - Good for general web searches
    
    Perfect fallback when SearXNG isn't available.
    """
    
    def __init__(
        self,
        region: str = "wt-wt",  # "wt-wt" = worldwide
        safesearch: str = "moderate",  # "on", "moderate", "off"
        timeout: int = 30
    ):
        """
        Initialize DuckDuckGo searcher.
        
        Args:
            region: Region code (e.g., "us-en", "uk-en", "wt-wt")
            safesearch: Safe search level ("on", "moderate", "off")
            timeout: Request timeout in seconds
        """
        if not DDGS_AVAILABLE:
            raise ImportError(
                "ddgs required. Install: pip install ddgs"
            )
        
        self.region = region
        self.safesearch = safesearch
        self.timeout = timeout
        
        logger.info(
            f"Initialized DuckDuckGo searcher: region={region}, "
            f"safesearch={safesearch}"
        )
    
    async def search(
        self,
        query: str,
        max_results: int = 10,
        **kwargs
    ) -> List[SearchResult]:
        """
        Search using DuckDuckGo.
        
        Args:
            query: Search query
            max_results: Maximum results to return
            **kwargs: Override settings
                     - region: str
                     - safesearch: str
                     - time_range: str ("d", "w", "m", "y")
                     
        Returns:
            List of SearchResult objects
        """
        region = kwargs.get("region", self.region)
        safesearch = kwargs.get("safesearch", self.safesearch)
        time_range = kwargs.get("time_range")
        
        try:
            logger.info(f"Searching DuckDuckGo: {query} (max={max_results})")
            
            # DuckDuckGo search is synchronous, but we wrap it for consistency
            with DDGS() as ddgs:
                results_iter = ddgs.text(
                    query,
                    region=region,
                    safesearch=safesearch,
                    timelimit=time_range,
                    max_results=max_results
                )
                
                results = []
                for result in results_iter:
                    results.append(self._parse_result(result))
                
                logger.info(f"DuckDuckGo returned {len(results)} results")
                return results
                
        except Exception as e:
            logger.error(f"DuckDuckGo search failed: {e}", exc_info=True)
            return []
    
    def _parse_result(self, result: dict) -> SearchResult:
        """Convert DDG result to SearchResult."""
        return SearchResult(
            url=result.get("href", ""),
            title=result.get("title", "Untitled"),
            content=result.get("body", ""),
            source="duckduckgo",
            published_date=None,  # DDG doesn't provide dates
            relevance_score=None,
            metadata={}
        )
    
    def get_source_name(self) -> str:
        """Return source identifier."""
        return "duckduckgo"
    
    def get_priority(self) -> int:
        """DuckDuckGo gets medium priority (10)."""
        return 10
    
    def is_available(self) -> bool:
        """Check if duckduckgo-search is available."""
        return DDGS_AVAILABLE


# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def test_ddg():
        """Test DuckDuckGo searcher."""
        searcher = DuckDuckGoSearcher()
        
        # Test 1: General search
        print("\\n=== Test 1: General Search ===")
        results = await searcher.search(
            "large language models code generation best practices",
            max_results=5
        )
        for r in results:
            print(f"- {r.title}")
            print(f"  {r.url}")
            print(f"  {r.content[:100]}...")
            print()
        
        # Test 2: Recent search (last week)
        print("\\n=== Test 2: Recent Search (Last Week) ===")
        results = await searcher.search(
            "AI breakthroughs",
            max_results=3,
            time_range="w"  # Last week
        )
        for r in results:
            print(f"- {r.title}")
            print(f"  {r.url}")
            print()
    
    asyncio.run(test_ddg())
