"""arXiv paper search integration - for academic papers."""

import logging
from typing import List, Optional
from datetime import datetime

try:
    import arxiv
    ARXIV_AVAILABLE = True
except ImportError:
    ARXIV_AVAILABLE = False
    logging.warning("arxiv package not installed. Run: pip install arxiv")

from .web_searcher import WebSearcher, SearchResult

logger = logging.getLogger(__name__)


class ArxivSearcher(WebSearcher):
    """
    arXiv paper search integration.
    
    arXiv is the primary source for academic papers in:
    - Computer Science
    - AI/ML
    - Mathematics
    - Physics
    
    Free, no API key required.
    """
    
    def __init__(
        self,
        max_results_per_query: int = 10,
        sort_by: str = "submittedDate",
        sort_order: str = "descending"
    ):
        """
        Initialize arXiv searcher.
        
        Args:
            max_results_per_query: Max results per query
            sort_by: Sort criterion
                    Options: "relevance", "lastUpdatedDate", "submittedDate"
            sort_order: Sort order ("ascending" or "descending")
        """
        if not ARXIV_AVAILABLE:
            raise ImportError(
                "arxiv package required. Install: pip install arxiv"
            )
        
        self.max_results_per_query = max_results_per_query
        self.sort_by = sort_by
        self.sort_order = sort_order
        self.client = arxiv.Client()
        
        logger.info(
            f"Initialized arXiv searcher: sort_by={sort_by}, "
            f"order={sort_order}"
        )
    
    async def search(
        self,
        query: str,
        max_results: int = 5,
        **kwargs
    ) -> List[SearchResult]:
        """
        Search arXiv papers.
        
        Args:
            query: Search query
            max_results: Maximum results to return
            **kwargs: Override instance settings
                     - sort_by: str
                     - sort_order: str
                     - categories: List[str] (e.g., ["cs.AI", "cs.LG"])
                     
        Returns:
            List of SearchResult objects
        """
        # Determine sort criterion
        sort_by = kwargs.get("sort_by", self.sort_by)
        sort_criterion = {
            "relevance": arxiv.SortCriterion.Relevance,
            "lastUpdatedDate": arxiv.SortCriterion.LastUpdatedDate,
            "submittedDate": arxiv.SortCriterion.SubmittedDate
        }.get(sort_by, arxiv.SortCriterion.SubmittedDate)
        
        # Determine sort order
        sort_order = kwargs.get("sort_order", self.sort_order)
        sort_order_obj = {
            "ascending": arxiv.SortOrder.Ascending,
            "descending": arxiv.SortOrder.Descending
        }.get(sort_order, arxiv.SortOrder.Descending)
        
        # Add category filter if specified
        categories = kwargs.get("categories")
        if categories:
            category_filter = " OR ".join([f"cat:{cat}" for cat in categories])
            query = f"({query}) AND ({category_filter})"
        
        try:
            logger.info(f"Searching arXiv: {query} (max={max_results})")
            
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=sort_criterion,
                sort_order=sort_order_obj
            )
            
            results = []
            for paper in self.client.results(search):
                results.append(self._parse_paper(paper))
            
            logger.info(f"arXiv returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"arXiv search failed: {e}", exc_info=True)
            return []
    
    def _parse_paper(self, paper: "arxiv.Result") -> SearchResult:
        """Convert arxiv.Result to SearchResult."""
        # Format authors
        authors = [author.name for author in paper.authors]
        author_str = ", ".join(authors[:3])
        if len(authors) > 3:
            author_str += f" et al. ({len(authors)} authors)"
        
        # Build content from abstract
        content = paper.summary.replace("\n", " ").strip()
        
        # Published date
        published_date = paper.published.isoformat()
        
        # Metadata
        metadata = {
            "authors": authors,
            "categories": paper.categories,
            "primary_category": paper.primary_category,
            "pdf_url": paper.pdf_url,
            "doi": paper.doi,
            "journal_ref": paper.journal_ref,
            "comment": paper.comment,
            "updated": paper.updated.isoformat() if paper.updated else None,
            "author_str": author_str
        }
        
        return SearchResult(
            url=paper.entry_id,
            title=paper.title,
            content=content,
            source="arxiv",
            published_date=published_date,
            relevance_score=None,  # arXiv doesn't provide scores
            metadata=metadata
        )
    
    def get_source_name(self) -> str:
        """Return source identifier."""
        return "arxiv"
    
    def get_priority(self) -> int:
        """arXiv gets priority 1 (after SearXNG)."""
        return 1
    
    def is_available(self) -> bool:
        """Check if arxiv package is available."""
        return ARXIV_AVAILABLE


# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def test_arxiv():
        """Test arXiv searcher."""
        searcher = ArxivSearcher()
        
        # Test 1: General search
        print("\\n=== Test 1: General Search ===")
        results = await searcher.search(
            "large language models code generation",
            max_results=5
        )
        for r in results:
            print(f"- {r.title}")
            print(f"  Authors: {r.metadata['author_str']}")
            print(f"  Date: {r.published_date[:10]}")
            print(f"  Categories: {', '.join(r.metadata['categories'])}")
            print(f"  {r.url}")
            print()
        
        # Test 2: Category-filtered search
        print("\\n=== Test 2: CS.AI Category ===")
        results = await searcher.search(
            "transformer architecture",
            max_results=3,
            categories=["cs.AI", "cs.LG"]
        )
        for r in results:
            print(f"- {r.title}")
            print(f"  {r.url}")
            print()
    
    asyncio.run(test_arxiv())
