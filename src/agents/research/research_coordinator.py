"""Research coordination - orchestrates multi-source iterative research."""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from difflib import SequenceMatcher

from .web_searcher import WebSearcher, SearchResult, SearchCache
from .duckduckgo_searcher import DuckDuckGoSearcher
from .arxiv_searcher import ArxivSearcher

logger = logging.getLogger(__name__)


@dataclass
class ResearchConfig:
    """Configuration for research coordinator."""
    
    max_iterations: int = 3
    max_results_per_source: int = 5
    min_total_results: int = 10
    cache_ttl_seconds: int = 3600
    enable_duckduckgo: bool = True
    enable_arxiv: bool = True
    enable_query_refinement: bool = True
    
    # DuckDuckGo settings
    ddg_region: str = "wt-wt"
    ddg_safesearch: str = "moderate"
    
    # arXiv settings
    arxiv_sort_by: str = "relevance"  # "relevance", "submittedDate", "lastUpdatedDate"
    arxiv_sort_order: str = "descending"


@dataclass
class ResearchReport:
    """Compiled research results."""
    
    query: str
    refined_queries: List[str]
    results: List[SearchResult]
    summary: str
    related_papers: List[str] = field(default_factory=list)
    web_resources: List[str] = field(default_factory=list)
    iterations: int = 0
    sources_used: List[str] = field(default_factory=list)
    total_results: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "query": self.query,
            "refined_queries": self.refined_queries,
            "results": [r.to_dict() for r in self.results],
            "summary": self.summary,
            "related_papers": self.related_papers,
            "web_resources": self.web_resources,
            "iterations": self.iterations,
            "sources_used": self.sources_used,
            "total_results": self.total_results
        }


class ResearchCoordinator:
    """
    Orchestrates multi-source iterative research.
    
    Strategy:
    1. DuckDuckGo first - latest info, best practices, community discussions
    2. arXiv second - academic papers
    3. Iterative refinement - refine queries based on results
    4. Quality validation - filter spam and low-quality results
    5. Deduplication - remove duplicate results
    """
    
    def __init__(self, config: Optional[ResearchConfig] = None):
        """
        Initialize research coordinator.
        
        Args:
            config: Research configuration (uses defaults if None)
        """
        self.config = config or ResearchConfig()
        self.cache = SearchCache(ttl_seconds=self.config.cache_ttl_seconds)
        
        # Initialize sources
        self.sources: List[WebSearcher] = []
        
        if self.config.enable_duckduckgo:
            ddg = DuckDuckGoSearcher(
                region=self.config.ddg_region,
                safesearch=self.config.ddg_safesearch
            )
            self.sources.append(ddg)
            logger.info("Enabled DuckDuckGo searcher")
        
        if self.config.enable_arxiv:
            arxiv = ArxivSearcher(
                sort_by=self.config.arxiv_sort_by,
                sort_order=self.config.arxiv_sort_order
            )
            self.sources.append(arxiv)
            logger.info("Enabled arXiv searcher")
        
        # Sort sources by priority (lower = higher priority)
        self.sources.sort(key=lambda s: s.get_priority())
        
        logger.info(
            f"Initialized ResearchCoordinator with {len(self.sources)} sources: "
            f"{[s.get_source_name() for s in self.sources]}"
        )
    
    async def research(
        self,
        query: str,
        max_iterations: Optional[int] = None,
        max_results_per_source: Optional[int] = None
    ) -> ResearchReport:
        """
        Execute multi-iteration research.
        
        Args:
            query: Research query
            max_iterations: Override config max iterations
            max_results_per_source: Override config max results
            
        Returns:
            ResearchReport with all findings
        """
        max_iterations = max_iterations or self.config.max_iterations
        max_results_per_source = max_results_per_source or self.config.max_results_per_source
        
        logger.info(f"Starting research: '{query}'")
        logger.info(f"Config: max_iterations={max_iterations}, max_results={max_results_per_source}")
        
        all_results = []
        refined_queries = [query]
        sources_used = set()
        
        for iteration in range(max_iterations):
            logger.info(f"\n{'='*60}")
            logger.info(f"Research Iteration {iteration + 1}/{max_iterations}")
            logger.info(f"{'='*60}")
            logger.info(f"Query: {refined_queries[-1]}")
            
            iteration_results = []
            
            # Try each source in priority order
            for source in self.sources:
                source_name = source.get_source_name()
                
                try:
                    # Check cache first
                    cached = self.cache.get(source_name, refined_queries[-1])
                    
                    if cached:
                        logger.info(f"✓ Using cached results from {source_name} ({len(cached)} results)")
                        batch = cached
                    else:
                        logger.info(f"→ Searching {source_name}...")
                        batch = await source.search(
                            refined_queries[-1],
                            max_results=max_results_per_source
                        )
                        
                        if batch:
                            self.cache.set(source_name, refined_queries[-1], batch)
                            logger.info(f"✓ {source_name} returned {len(batch)} results")
                        else:
                            logger.warning(f"✗ {source_name} returned no results")
                    
                    # Validate results
                    validated = [r for r in batch if self._validate_result(r, refined_queries[-1])]
                    
                    if len(validated) < len(batch):
                        logger.info(f"  Filtered out {len(batch) - len(validated)} low-quality results")
                    
                    iteration_results.extend(validated)
                    sources_used.add(source_name)
                    
                except Exception as e:
                    logger.error(f"✗ Source {source_name} failed: {e}", exc_info=True)
                    continue
            
            all_results.extend(iteration_results)
            
            # Log iteration summary
            logger.info(f"\nIteration {iteration + 1} Summary:")
            logger.info(f"  - Results this iteration: {len(iteration_results)}")
            logger.info(f"  - Total results so far: {len(all_results)}")
            logger.info(f"  - Sources used: {list(sources_used)}")
            
            # Check if we have enough high-quality results
            if len(all_results) >= self.config.min_total_results:
                logger.info(f"\n✓ Sufficient results found ({len(all_results)} >= {self.config.min_total_results})")
                break
            
            # Refine query for next iteration if needed
            if iteration < max_iterations - 1 and self.config.enable_query_refinement:
                refined_query = self._refine_query(
                    original=query,
                    current=refined_queries[-1],
                    results=iteration_results,
                    iteration=iteration
                )
                
                if refined_query != refined_queries[-1]:
                    refined_queries.append(refined_query)
                    logger.info(f"\n→ Refined query for next iteration: '{refined_query}'")
                else:
                    logger.info("\n→ No refinement needed, stopping")
                    break
        
        # Deduplicate results
        unique_results = self._deduplicate_results(all_results)
        logger.info(f"\n✓ Deduplication: {len(all_results)} → {len(unique_results)} unique results")
        
        # Generate summary
        summary = self._generate_summary(query, unique_results)
        
        # Extract papers and web resources
        related_papers = self._extract_papers(unique_results)
        web_resources = self._extract_web_resources(unique_results)
        
        report = ResearchReport(
            query=query,
            refined_queries=refined_queries,
            results=unique_results,
            summary=summary,
            related_papers=related_papers,
            web_resources=web_resources,
            iterations=len(refined_queries),
            sources_used=list(sources_used),
            total_results=len(unique_results)
        )
        
        logger.info(f"\n{'='*60}")
        logger.info("Research Complete!")
        logger.info(f"{'='*60}")
        logger.info(f"Total iterations: {report.iterations}")
        logger.info(f"Total unique results: {report.total_results}")
        logger.info(f"Sources used: {report.sources_used}")
        logger.info(f"Related papers: {len(report.related_papers)}")
        logger.info(f"Web resources: {len(report.web_resources)}")
        
        return report
    
    def _validate_result(self, result: SearchResult, query: str) -> bool:
        """
        Validate result quality.
        
        Args:
            result: Search result to validate
            query: Original query
            
        Returns:
            True if result passes validation
        """
        # Check 1: Has sufficient content
        if len(result.content) < 50:
            return False
        
        # Check 2: Title and URL not empty
        if not result.title or not result.url:
            return False
        
        # Check 3: Basic relevance (keyword matching)
        query_terms = set(query.lower().split())
        result_text = (result.title + " " + result.content).lower()
        
        matches = sum(1 for term in query_terms if term in result_text)
        if matches / len(query_terms) < 0.3:  # At least 30% keyword match
            return False
        
        # Check 4: Not spam
        spam_indicators = ["click here", "buy now", "limited time", "act now"]
        content_lower = result.content.lower()
        if any(indicator in content_lower for indicator in spam_indicators):
            return False
        
        return True
    
    def _refine_query(
        self,
        original: str,
        current: str,
        results: List[SearchResult],
        iteration: int
    ) -> str:
        """
        Refine search query based on results.
        
        Simple heuristic-based refinement:
        - If too few results: broaden query (remove specific terms)
        - If results poor quality: add specific technical terms
        - If results off-topic: add context terms
        
        Args:
            original: Original query
            current: Current query
            results: Results from current query
            iteration: Current iteration number
            
        Returns:
            Refined query
        """
        # Too few results - broaden
        if len(results) < 3:
            # Remove least common words
            words = current.split()
            if len(words) > 3:
                # Keep first 3-4 most important words
                refined = " ".join(words[:4])
                logger.info(f"  Refinement strategy: Broaden (too few results)")
                return refined
        
        # Good number of results - add specificity
        if len(results) >= 3:
            # Add year for recency
            if "2025" not in current and "2024" not in current:
                refined = f"{current} 2025 2024"
                logger.info(f"  Refinement strategy: Add recency filter")
                return refined
            
            # Add "best practices" if not present
            if "best practices" not in current.lower() and "best" not in current.lower():
                refined = f"{current} best practices"
                logger.info(f"  Refinement strategy: Add 'best practices'")
                return refined
        
        # No refinement
        return current
    
    def _deduplicate_results(self, results: List[SearchResult]) -> List[SearchResult]:
        """
        Remove duplicate results based on URL and title similarity.
        
        Args:
            results: List of search results
            
        Returns:
            Deduplicated list
        """
        seen_urls = set()
        seen_titles = set()
        unique = []
        
        for result in results:
            # Check URL
            if result.url in seen_urls:
                continue
            
            # Check title similarity (fuzzy matching)
            title_norm = result.title.lower().strip()
            if any(self._is_similar(title_norm, seen) for seen in seen_titles):
                continue
            
            seen_urls.add(result.url)
            seen_titles.add(title_norm)
            unique.append(result)
        
        return unique
    
    def _is_similar(self, s1: str, s2: str, threshold: float = 0.9) -> bool:
        """Check if two strings are similar using difflib."""
        return SequenceMatcher(None, s1, s2).ratio() > threshold
    
    def _generate_summary(self, query: str, results: List[SearchResult]) -> str:
        """
        Generate summary of research findings.
        
        Args:
            query: Original query
            results: All research results
            
        Returns:
            Summary text
        """
        if not results:
            return "No results found."
        
        # Sort by relevance if available
        sorted_results = sorted(
            results,
            key=lambda r: r.relevance_score or 0.0,
            reverse=True
        )
        
        # Build summary
        lines = [
            f"Research query: {query}",
            f"Found {len(results)} relevant results from {len(set(r.source for r in results))} sources.",
            "",
            "Top findings:"
        ]
        
        for i, result in enumerate(sorted_results[:5], 1):
            lines.append(f"{i}. {result.title}")
            lines.append(f"   Source: {result.source}")
            if result.published_date:
                lines.append(f"   Date: {result.published_date[:10]}")
        
        return "\n".join(lines)
    
    def _extract_papers(self, results: List[SearchResult]) -> List[str]:
        """Extract academic paper citations."""
        papers = []
        
        for result in results:
            if result.source == "arxiv":
                # Format: "Title (FirstAuthor et al., Year)"
                metadata = result.metadata
                year = result.published_date[:4] if result.published_date else "Unknown"
                author = metadata.get("author_str", "Unknown")
                
                citation = f"{result.title} ({author}, {year})"
                papers.append(citation)
        
        return papers[:10]  # Top 10
    
    def _extract_web_resources(self, results: List[SearchResult]) -> List[str]:
        """Extract web resource URLs."""
        resources = []
        
        for result in results:
            if result.source.startswith("duckduckgo") or result.source.startswith("searxng"):
                resources.append(result.url)
        
        return resources[:10]  # Top 10


# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def test_research():
        """Test research coordinator."""
        # Initialize coordinator
        config = ResearchConfig(
            max_iterations=2,
            max_results_per_source=5,
            min_total_results=8
        )
        coordinator = ResearchCoordinator(config)
        
        # Test query
        query = "large language models code generation best practices"
        
        print(f"\n{'='*60}")
        print(f"Research Query: {query}")
        print(f"{'='*60}\n")
        
        # Execute research
        report = await coordinator.research(query)
        
        # Display report
        print("\n" + "="*60)
        print("RESEARCH REPORT")
        print("="*60)
        print(f"\nQuery: {report.query}")
        print(f"Iterations: {report.iterations}")
        print(f"Refined queries: {report.refined_queries}")
        print(f"Total results: {report.total_results}")
        print(f"Sources used: {report.sources_used}")
        
        print(f"\n{report.summary}")
        
        if report.related_papers:
            print(f"\nRelated Papers ({len(report.related_papers)}):")
            for paper in report.related_papers[:3]:
                print(f"  - {paper}")
        
        if report.web_resources:
            print(f"\nWeb Resources ({len(report.web_resources)}):")
            for url in report.web_resources[:3]:
                print(f"  - {url}")
        
        print("\n" + "="*60)
        print("All Results:")
        print("="*60)
        for i, result in enumerate(report.results, 1):
            print(f"\n{i}. {result.title}")
            print(f"   Source: {result.source}")
            print(f"   URL: {result.url}")
            if result.published_date:
                print(f"   Date: {result.published_date[:10]}")
    
    # Run test
    asyncio.run(test_research())
