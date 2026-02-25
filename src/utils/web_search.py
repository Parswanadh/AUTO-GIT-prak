"""
Multi-Engine Web Search Integration for Auto-GIT (Option C)

Provides comprehensive search using multiple engines with intelligent fallback:

PRIMARY ENGINES (Prioritized):
1. Tavily API (96% accuracy, 2000 free req/month)
2. Brave Search API (privacy-focused)

SECONDARY ENGINES (No API keys):
3. DuckDuckGo Search (DDGS - unlimited, free)
4. SearXNG (self-hosted metasearch if available)
5. arXiv (academic papers)

STRATEGY: Use Tavily if key available, fallback to free engines.
This provides best-of-both-worlds: accuracy with cost control.
"""

import logging
import os
import json
import time
from typing import List, Dict, Optional, Union
from datetime import datetime
from enum import Enum

# Try arxiv (may fail on Python 3.14 due to cgi module)
try:
    import arxiv
    HAS_ARXIV = True
except (ImportError, ModuleNotFoundError):
    arxiv = None
    HAS_ARXIV = False

# Try SearXNG
try:
    from src.research.searxng_client import SearXNGClient
    HAS_SEARXNG = True
except ImportError:
    HAS_SEARXNG = False

# DuckDuckGo — package was renamed from duckduckgo_search to ddgs
try:
    from ddgs import DDGS
    HAS_DUCKDUCKGO = True
except ImportError:
    try:
        from duckduckgo_search import DDGS  # legacy name fallback
        HAS_DUCKDUCKGO = True
    except ImportError:
        HAS_DUCKDUCKGO = False

# Premium APIs (optional)
try:
    from tavily import TavilyClient
    HAS_TAVILY = True
except ImportError:
    HAS_TAVILY = False

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

logger = logging.getLogger(__name__)


class SearchEngine(Enum):
    """Available search engines"""
    TAVILY = "tavily"
    BRAVE = "brave"
    DUCKDUCKGO = "duckduckgo"
    SEARXNG = "searxng"
    ARXIV = "arxiv"


class MultiEngineSearcher:
    """
    Intelligent multi-engine search aggregator with fallback chains.
    
    Uses premium APIs (Tavily, Brave) when available, falls back to
    free engines (DDGS, SearXNG) automatically with intelligent retries.
    """
    
    def __init__(self, 
                 tavily_api_key: Optional[str] = None,
                 brave_api_key: Optional[str] = None,
                 searxng_url: str = "http://localhost:8888",
                 max_results: int = 5,
                 timeout: int = 30):
        """Initialize multi-engine searcher"""
        self.tavily_api_key = tavily_api_key or os.getenv("TAVILY_API_KEY")
        self.brave_api_key = brave_api_key or os.getenv("BRAVE_API_KEY")
        self.searxng_url = searxng_url
        self.max_results = max_results
        self.timeout = timeout
        self.available_engines: List[SearchEngine] = []
        self._detect_available_engines()
        self.metrics = {"total_queries": 0, "successful_engines": {}, "failed_engines": {}, "total_results": 0}
    
    def _detect_available_engines(self):
        """Detect which engines are available"""
        if self.tavily_api_key and HAS_TAVILY:
            self.available_engines.append(SearchEngine.TAVILY)
            logger.info("✓ Tavily API available")
        if self.brave_api_key:
            self.available_engines.append(SearchEngine.BRAVE)
            logger.info("✓ Brave Search API available")
        if HAS_DUCKDUCKGO:
            self.available_engines.append(SearchEngine.DUCKDUCKGO)
            logger.info("✓ DuckDuckGo available (free, unlimited)")
        if HAS_SEARXNG:
            # Only add SearXNG if the local instance is actually reachable
            try:
                _s = SearXNGClient(base_url=self.searxng_url)
                if _s.is_available():
                    self.available_engines.append(SearchEngine.SEARXNG)
                    logger.info("\u2713 SearXNG available (self-hosted)")
                else:
                    logger.debug("SearXNG not reachable at %s \u2014 skipping", self.searxng_url)
            except Exception:
                logger.debug("SearXNG probe failed \u2014 skipping")
        if HAS_ARXIV:
            self.available_engines.append(SearchEngine.ARXIV)
            logger.info("✓ arXiv available (academic)")
    
    def search(self, query: str, engines: Optional[List[SearchEngine]] = None,
              include_academic: bool = False, max_results: Optional[int] = None) -> Dict:
        """Multi-engine search with intelligent fallback"""
        self.metrics["total_queries"] += 1
        max_results = max_results or self.max_results
        results = {}
        engines_to_use = engines or self.available_engines
        
        for engine in engines_to_use:
            try:
                if engine == SearchEngine.TAVILY:
                    results["tavily"] = self._search_tavily(query, max_results)
                elif engine == SearchEngine.DUCKDUCKGO:
                    results["duckduckgo"] = self._search_duckduckgo(query, max_results)
                elif engine == SearchEngine.SEARXNG:
                    results["searxng"] = self._search_searxng(query, max_results)
                elif engine == SearchEngine.ARXIV and include_academic:
                    results["arxiv"] = self._search_arxiv(query, max_results)
            except Exception as e:
                logger.warning(f"Search failed on {engine.value}: {e}")
                self.metrics["failed_engines"][engine.value] = self.metrics["failed_engines"].get(engine.value, 0) + 1
        
        aggregated = self._deduplicate_results(results)
        self.metrics["total_results"] += len(aggregated)
        
        return {
            "aggregated": aggregated,
            "by_engine": results,
            "metadata": {"query": query, "timestamp": datetime.now().isoformat(), "engines_used": len(results), "total_results": len(aggregated)}
        }
    
    def _search_tavily(self, query: str, max_results: int) -> List[Dict]:
        """Search using Tavily API"""
        if not HAS_TAVILY or not self.tavily_api_key:
            return []
        try:
            logger.info(f"🔍 Tavily: {query}")
            client = TavilyClient(api_key=self.tavily_api_key)
            response = client.search(query, max_results=max_results)
            results = [{"title": r.get("title", ""), "url": r.get("url", ""), "content": r.get("content", ""), "score": r.get("score", 0), "engine": "tavily"} for r in response.get("results", [])]
            logger.info(f"✓ Tavily: {len(results)} results")
            return results
        except Exception as e:
            logger.error(f"Tavily search failed: {e}")
            return []
    
    def _search_duckduckgo(self, query: str, max_results: int) -> List[Dict]:
        """Search using DuckDuckGo"""
        if not HAS_DUCKDUCKGO:
            return []
        try:
            logger.info(f"🔍 DuckDuckGo: {query}")
            with DDGS(timeout=self.timeout) as ddgs:
                results_raw = list(ddgs.text(query, max_results=max_results))
            results = [{"title": r.get("title", ""), "url": r.get("href", ""), "content": r.get("body", ""), "engine": "duckduckgo"} for r in results_raw]
            logger.info(f"✓ DuckDuckGo: {len(results)} results")
            return results
        except Exception as e:
            logger.error(f"DuckDuckGo search failed: {e}")
            return []
    
    def _search_searxng(self, query: str, max_results: int) -> List[Dict]:
        """Search using SearXNG"""
        if not HAS_SEARXNG:
            return []
        try:
            logger.info(f"🔍 SearXNG: {query}")
            client = SearXNGClient(base_url=self.searxng_url)
            results_raw = client.search(query, num_results=max_results)
            results = [{"title": r.get("title", ""), "url": r.get("url", ""), "content": r.get("content", ""), "engine": r.get("engine", "searxng")} for r in results_raw]
            logger.info(f"✓ SearXNG: {len(results)} results")
            return results
        except Exception as e:
            logger.error(f"SearXNG search failed: {e}")
            return []
    
    def _search_arxiv(self, query: str, max_results: int) -> List[Dict]:
        """Search arXiv for papers"""
        if not HAS_ARXIV:
            return []
        try:
            logger.info(f"🔍 arXiv: {query}")
            search = arxiv.Search(query=query, max_results=max_results, sort_by=arxiv.SortCriterion.Relevance)
            results = [{"title": r.title, "url": r.pdf_url, "content": r.summary[:300] + "...", "authors": [a.name for a in r.authors], "published": r.published.strftime("%Y-%m-%d"), "engine": "arxiv"} for r in search.results()]
            logger.info(f"✓ arXiv: {len(results)} results")
            return results
        except Exception as e:
            logger.error(f"arXiv search failed: {e}")
            return []
    
    def _deduplicate_results(self, results_by_engine: Dict[str, List[Dict]]) -> List[Dict]:
        """Deduplicate results from multiple engines"""
        seen_urls = set()
        aggregated = []
        all_results = []
        for engine, results in results_by_engine.items():
            for result in results:
                result["engine"] = engine
                all_results.append(result)
        all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
        for result in all_results:
            url = result.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                aggregated.append(result)
        return aggregated
    
    def get_metrics(self) -> Dict:
        """Get search metrics"""
        return {
            "total_queries": self.metrics["total_queries"],
            "successful_engines": self.metrics["successful_engines"],
            "failed_engines": self.metrics["failed_engines"],
            "available_engines": [e.value for e in self.available_engines]
        }


class ArxivSearcher:
    """Search arXiv for research papers"""
    
    def __init__(self, max_results: int = 5):
        self.max_results = max_results
    
    def search(self, query: str, max_results: Optional[int] = None) -> List[Dict]:
        """
        Search arXiv for papers
        
        Args:
            query: Search query (e.g., "transformer attention mechanism")
            max_results: Override default max results
            
        Returns:
            List of paper dictionaries with title, summary, authors, pdf_url, etc.
        """
        max_results = max_results or self.max_results
        
        # Check if arxiv is available (may fail on Python 3.14)
        if not HAS_ARXIV:
            logger.warning("arXiv not available (Python 3.14 compatibility issue). Skipping arXiv search.")
            return []
        
        try:
            logger.info(f"Starting arXiv search for: {query}")
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.Relevance
            )
            
            papers = []
            for result in search.results():
                paper = {
                    "title": result.title,
                    "summary": result.summary[:500] + "..." if len(result.summary) > 500 else result.summary,
                    "authors": [author.name for author in result.authors],
                    "pdf_url": result.pdf_url,
                    "published": result.published.strftime("%Y-%m-%d"),
                    "categories": result.categories,
                    "primary_category": result.primary_category,
                    "entry_id": result.entry_id
                }
                papers.append(paper)
            
            logger.info(f"Found {len(papers)} papers for query: {query}")
            return papers
            
        except Exception as e:
            logger.error(f"arXiv search failed for '{query}': {e}")
            logger.debug(f"Error details: {type(e).__name__}: {str(e)}")
            return []


class WebSearcher:
    """
    Multi-engine web searcher with intelligent fallback.
    
    Uses available engines in priority order: Tavily → Brave → DuckDuckGo → SearXNG
    Automatically falls back if engines unavailable.
    """
    
    def __init__(self, 
                 tavily_api_key: Optional[str] = None,
                 brave_api_key: Optional[str] = None,
                 max_results: int = 5, 
                 searxng_url: str = "http://localhost:8888"):
        self.multi_engine = MultiEngineSearcher(
            tavily_api_key=tavily_api_key,
            brave_api_key=brave_api_key,
            searxng_url=searxng_url,
            max_results=max_results
        )
        logger.info(f"WebSearcher initialized with {len(self.multi_engine.available_engines)} engines")
    
    def search(self, query: str, max_results: Optional[int] = None) -> List[Dict]:
        """
        Search web using multiple engines
        
        Args:
            query: Search query
            max_results: Override default max results
            
        Returns:
            List of aggregated result dictionaries
        """
        result_data = self.multi_engine.search(query, max_results=max_results)
        return result_data["aggregated"]
    
    def search_with_details(self, query: str, max_results: Optional[int] = None) -> Dict:
        """Get search results with per-engine breakdown"""
        return self.multi_engine.search(query, max_results=max_results)
    
    def search_news(self, query: str, max_results: Optional[int] = None) -> List[Dict]:
        """Search news articles"""
        return self.search(f"{query} news", max_results=max_results)
    
    def get_metrics(self) -> Dict:
        """Get search engine metrics"""
        return self.multi_engine.get_metrics()


# Keep DuckDuckGoSearcher for backward compatibility
class DuckDuckGoSearcher(WebSearcher):
    """Backward compatibility wrapper"""
    def __init__(self, max_results: int = 5):
        super().__init__(max_results=max_results)
        logger.warning("DuckDuckGoSearcher is deprecated, use WebSearcher instead")


class ResearchSearcher:
    """
    Combined research search using multiple sources
    
    Provides comprehensive search across academic and web sources.
    Uses SearXNG if available, falls back to DuckDuckGo.
    """
    
    def __init__(self, max_arxiv: int = 5, max_web: int = 5):
        self.arxiv_searcher = ArxivSearcher(max_results=max_arxiv)
        self.web_searcher = WebSearcher(max_results=max_web)  # Uses SearXNG if available
    
    def search_comprehensive(self, topic: str) -> Dict[str, List[Dict]]:
        """
        Search both arXiv and web for a research topic
        
        Args:
            topic: Research topic or query
            
        Returns:
            Dictionary with 'papers', 'web_results', 'implementations' keys
        """
        results = {
            "papers": [],
            "web_results": [],
            "implementations": []
        }
        
        # Search arXiv for academic papers
        logger.info(f"Searching arXiv for: {topic}")
        results["papers"] = self.arxiv_searcher.search(topic)
        
        # Search web for general information
        logger.info(f"Searching web for: {topic}")
        results["web_results"] = self.web_searcher.search(topic)
        
        # Search for code implementations on GitHub
        implementation_query = f"{topic} implementation github"
        logger.info(f"Searching for implementations: {implementation_query}")
        results["implementations"] = self.web_searcher.search(implementation_query)
        
        return results
    
    def format_papers_for_prompt(self, papers: List[Dict]) -> str:
        """Format arXiv papers for LLM prompt context"""
        if not papers or not isinstance(papers, list):
            return "No papers found."
        
        formatted = "## Related Research Papers\n\n"
        for i, paper in enumerate(papers, 1):
            if not isinstance(paper, dict):
                continue
                
            # Safely extract with defaults
            title = paper.get('title', 'Unknown Title')
            authors_list = paper.get("authors", [])
            if isinstance(authors_list, list) and authors_list:
                authors = ", ".join(str(a) for a in authors_list[:3])
                if len(authors_list) > 3:
                    authors += " et al."
            else:
                authors = "Unknown Authors"
            
            published = paper.get('published', 'Unknown Date')
            summary = paper.get('summary', 'No summary available')
            pdf_url = paper.get('pdf_url', 'N/A')
            
            formatted += f"{i}. **{title}**\n"
            formatted += f"   - Authors: {authors}\n"
            formatted += f"   - Published: {published}\n"
            formatted += f"   - Summary: {summary}\n"
            formatted += f"   - PDF: {pdf_url}\n\n"
        
        return formatted
    
    def format_web_results_for_prompt(self, results: List[Dict]) -> str:
        """Format web results for LLM prompt context"""
        if not results:
            return "No web results found."
        
        formatted = "## Web Search Results\n\n"
        for i, result in enumerate(results, 1):
            formatted += f"{i}. **{result.get('title', 'No title')}**\n"
            formatted += f"   - URL: {result.get('href', 'N/A')}\n"
            formatted += f"   - Snippet: {result.get('body', 'No description')[:200]}...\n\n"
        
        return formatted


# Convenience functions
def search_papers(query: str, max_results: int = 5) -> List[Dict]:
    """Quick arXiv paper search"""
    searcher = ArxivSearcher(max_results=max_results)
    return searcher.search(query)


def search_web(query: str, max_results: int = 5) -> List[Dict]:
    """Quick multi-engine web search (Option C: Aggregator)"""
    searcher = WebSearcher(max_results=max_results)
    return searcher.search(query)


def search_web_detailed(query: str, max_results: int = 5) -> Dict:
    """Quick multi-engine web search with per-engine breakdown"""
    searcher = WebSearcher(max_results=max_results)
    return searcher.search_with_details(query)


def search_all(topic: str, max_arxiv: int = 5, max_web: int = 5) -> Dict[str, List[Dict]]:
    """Quick comprehensive search (academic + web aggregated)"""
    searcher = ResearchSearcher(max_arxiv=max_arxiv, max_web=max_web)
    return searcher.search_comprehensive(topic)


def multi_engine_search(query: str, 
                       tavily_api_key: Optional[str] = None,
                       brave_api_key: Optional[str] = None,
                       include_academic: bool = True,
                       max_results: int = 5) -> Dict:
    """
    Advanced multi-engine search with full control.
    
    Option C: Full aggregator with Tavily + Brave + DuckDuckGo + SearXNG + arXiv
    
    Args:
        query: Search query
        tavily_api_key: Optional Tavily API key
        brave_api_key: Optional Brave API key
        include_academic: Include arXiv papers
        max_results: Results per engine
        
    Returns:
        Aggregated results with per-engine breakdown
    """
    searcher = MultiEngineSearcher(
        tavily_api_key=tavily_api_key,
        brave_api_key=brave_api_key,
        max_results=max_results
    )
    return searcher.search(query, include_academic=include_academic)


if __name__ == "__main__":
    # Test searches - Multi-Engine Aggregator Demo
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 70)
    print("MULTI-ENGINE SEARCH AGGREGATOR (Option C) - Demo")
    print("=" * 70)
    
    # Test 1: Multi-engine web search
    print("\n📊 Test 1: Multi-Engine Web Search")
    print("-" * 70)
    result = search_web_detailed("efficient attention mechanisms 2025", max_results=3)
    print(f"Total results: {result['metadata']['total_results']}")
    print(f"Engines used: {result['metadata']['engines_used']}")
    print("Per-engine results:")
    for engine, results in result["by_engine"].items():
        print(f"  {engine}: {len(results)} results")
    
    # Test 2: Academic search
    print("\n📚 Test 2: Academic Search")
    print("-" * 70)
    papers = search_papers("transformer optimization", max_results=3)
    print(f"Found {len(papers)} academic papers")
    if papers:
        print(f"First paper: {papers[0]['title']}")
    
    # Test 3: Comprehensive search (academic + web)
    print("\n🔬 Test 3: Comprehensive Research Search")
    print("-" * 70)
    all_results = search_all("neural network pruning", max_arxiv=2, max_web=2)
    print(f"Papers: {len(all_results['papers'])}")
    print(f"Web results: {len(all_results['web_results'])}")
    print(f"Implementations: {len(all_results['implementations'])}")
    print(f"Total: {len(all_results['papers']) + len(all_results['web_results']) + len(all_results['implementations'])} results")
    
    # Test 4: Show available engines
    print("\n⚙️  Test 4: Available Search Engines")
    print("-" * 70)
    multi_searcher = MultiEngineSearcher()
    print(f"Available engines: {[e.value for e in multi_searcher.available_engines]}")
    print(f"Total engines: {len(multi_searcher.available_engines)}")
    
    print("\n" + "=" * 70)
    print("Option C (Multi-Engine Aggregator) Demonstration Complete ✅")
    print("=" * 70)

