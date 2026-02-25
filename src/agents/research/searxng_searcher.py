"""SearXNG metasearch engine integration - MANDATORY for latest information."""

import aiohttp
import logging
from typing import List, Optional, Dict, Any
from urllib.parse import urlencode
from .web_searcher import WebSearcher, SearchResult

logger = logging.getLogger(__name__)


class SearXNGSearcher(WebSearcher):
    """
    SearXNG metasearch engine integration.
    
    SearXNG aggregates results from multiple search engines:
    - Google, Bing, DuckDuckGo, Qwant, etc.
    - Reddit, StackOverflow, GitHub
    - arXiv, Google Scholar, Semantic Scholar
    
    This gives us the BEST coverage for:
    - Latest world events and news
    - Current best practices
    - New techniques and approaches
    - Community discussions
    - Code examples
    
    Can be self-hosted or use public instances.
    """
    
    def __init__(
        self,
        base_url: str = "https://search.sapti.me",  # More reliable instance
        categories: Optional[List[str]] = None,
        engines: Optional[List[str]] = None,
        language: str = "en",
        time_range: Optional[str] = None,
        safesearch: int = 0,
        timeout: int = 30
    ):
        """
        Initialize SearXNG searcher.
        
        Args:
            base_url: SearXNG instance URL
                     Popular public instances:
                     - https://searx.be
                     - https://searx.work
                     - https://search.sapti.me
                     - https://searx.tiekoetter.com
                     Or self-host: https://github.com/searxng/searxng
                     
            categories: Search categories to use
                       Options: "general", "science", "it", "news", "files"
                       Default: ["general", "science", "it"]
                       
            engines: Specific engines to use (optional)
                    Examples: "google", "bing", "duckduckgo", "github", 
                             "stackoverflow", "reddit", "arxiv", "wikipedia"
                    Default: None (uses all available)
                    
            language: Result language (default: "en")
            
            time_range: Time filter (optional)
                       Options: "day", "week", "month", "year"
                       
            safesearch: Safe search level (0=off, 1=moderate, 2=strict)
            
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.categories = categories or ["general", "science", "it"]
        self.engines = engines
        self.language = language
        self.time_range = time_range
        self.safesearch = safesearch
        self.timeout = timeout
        
        logger.info(
            f"Initialized SearXNG searcher: {self.base_url}, "
            f"categories={self.categories}, engines={self.engines}"
        )
    
    async def search(
        self,
        query: str,
        max_results: int = 10,
        **kwargs
    ) -> List[SearchResult]:
        """
        Search using SearXNG.
        
        Args:
            query: Search query
            max_results: Maximum results to return
            **kwargs: Override instance settings
                     - categories: List[str]
                     - engines: List[str]
                     - time_range: str
                     
        Returns:
            List of SearchResult objects
        """
        # Build query parameters
        params = {
            "q": query,
            "format": "json",
            "language": kwargs.get("language", self.language),
            "safesearch": kwargs.get("safesearch", self.safesearch),
            "categories": ",".join(kwargs.get("categories", self.categories))
        }
        
        # Add optional parameters
        if kwargs.get("engines") or self.engines:
            engines_list = kwargs.get("engines", self.engines)
            params["engines"] = ",".join(engines_list)
        
        if kwargs.get("time_range") or self.time_range:
            params["time_range"] = kwargs.get("time_range", self.time_range)
        
        url = f"{self.base_url}/search?{urlencode(params)}"
        
        # Headers to avoid bot detection
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": self.base_url
        }
        
        try:
            logger.info(f"Searching SearXNG: {query} (max={max_results})")
            
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status != 200:
                        logger.error(
                            f"SearXNG returned status {response.status}: "
                            f"{await response.text()}"
                        )
                        return []
                    
                    data = await response.json()
                    results = self._parse_results(data, max_results)
                    
                    logger.info(f"SearXNG returned {len(results)} results")
                    return results
                    
        except aiohttp.ClientError as e:
            logger.error(f"SearXNG request failed: {e}")
            return []
        except Exception as e:
            logger.error(f"SearXNG error: {e}", exc_info=True)
            return []
    
    def _parse_results(
        self,
        data: Dict[str, Any],
        max_results: int
    ) -> List[SearchResult]:
        """Parse SearXNG JSON response into SearchResult objects."""
        results = []
        
        for item in data.get("results", [])[:max_results]:
            # Extract fields with safe defaults
            url = item.get("url", "")
            title = item.get("title", "Untitled")
            content = item.get("content", "")
            
            # SearXNG provides engine info
            engine = item.get("engine", "unknown")
            
            # Published date (if available)
            published_date = item.get("publishedDate")
            if published_date:
                published_date = str(published_date)
            
            # Score (if available)
            score = item.get("score")
            
            # Additional metadata
            metadata = {
                "engine": engine,
                "category": item.get("category", "general"),
                "parsed_url": item.get("parsed_url", {}),
                "engines": item.get("engines", []),
                "positions": item.get("positions", [])
            }
            
            # Add optional fields
            if "thumbnail" in item:
                metadata["thumbnail"] = item["thumbnail"]
            if "author" in item:
                metadata["author"] = item["author"]
            if "iframe_src" in item:
                metadata["iframe_src"] = item["iframe_src"]
            
            results.append(SearchResult(
                url=url,
                title=title,
                content=content,
                source=f"searxng/{engine}",
                published_date=published_date,
                relevance_score=score,
                metadata=metadata
            ))
        
        return results
    
    def get_source_name(self) -> str:
        """Return source identifier."""
        return "searxng"
    
    def get_priority(self) -> int:
        """SearXNG gets highest priority (0) - it's our main source."""
        return 0
    
    def is_available(self) -> bool:
        """Check if SearXNG instance is available."""
        import requests
        try:
            response = requests.head(self.base_url, timeout=5)
            return response.status_code == 200
        except:
            return False
    
    @classmethod
    def get_public_instances(cls) -> List[str]:
        """
        Get list of known public SearXNG instances.
        
        Returns:
            List of public instance URLs
        """
        return [
            "https://searx.be",
            "https://searx.work", 
            "https://search.sapti.me",
            "https://searx.tiekoetter.com",
            "https://search.bus-hit.me",
            "https://searx.be",
            "https://search.mdosch.de",
            "https://searx.ninja",
            "https://search.privacyguides.net"
        ]
    
    @classmethod
    async def find_working_instance(cls) -> Optional[str]:
        """
        Find a working public SearXNG instance.
        
        Returns:
            URL of working instance or None
        """
        import aiohttp
        
        instances = cls.get_public_instances()
        
        async with aiohttp.ClientSession() as session:
            for instance in instances:
                try:
                    async with session.head(
                        instance,
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as response:
                        if response.status == 200:
                            logger.info(f"Found working SearXNG instance: {instance}")
                            return instance
                except:
                    continue
        
        logger.warning("No working SearXNG instance found")
        return None


# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def test_searxng():
        """Test SearXNG searcher."""
        searcher = SearXNGSearcher()
        
        # Test 1: General search
        print("\\n=== Test 1: General Search ===")
        results = await searcher.search(
            "large language models code generation best practices",
            max_results=5
        )
        for r in results:
            print(f"- {r.title}")
            print(f"  {r.url}")
            print(f"  Engine: {r.metadata.get('engine')}")
            print()
        
        # Test 2: Recent search (last week)
        print("\\n=== Test 2: Recent Search (Last Week) ===")
        results = await searcher.search(
            "AI code generation breakthroughs",
            max_results=5,
            time_range="week"
        )
        for r in results:
            print(f"- {r.title}")
            print(f"  Date: {r.published_date}")
            print()
        
        # Test 3: GitHub search
        print("\\n=== Test 3: GitHub Code Search ===")
        results = await searcher.search(
            "langchain research coordinator",
            max_results=5,
            engines=["github"]
        )
        for r in results:
            print(f"- {r.title}")
            print(f"  {r.url}")
            print()
    
    asyncio.run(test_searxng())
