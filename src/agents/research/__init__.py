"""Research coordination agents for web search and information gathering."""

from .web_searcher import WebSearcher, SearchResult, SearchCache
from .searxng_searcher import SearXNGSearcher
from .arxiv_searcher import ArxivSearcher
from .duckduckgo_searcher import DuckDuckGoSearcher
from .research_coordinator import ResearchCoordinator, ResearchReport, ResearchConfig

__all__ = [
    "WebSearcher",
    "SearchResult", 
    "SearchCache",
    "SearXNGSearcher",
    "ArxivSearcher",
    "DuckDuckGoSearcher",
    "ResearchCoordinator",
    "ResearchReport",
    "ResearchConfig"
]
