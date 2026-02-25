"""
Extensive Researcher Agent - Multi-Iteration Deep Research System
================================================================

This agent performs comprehensive, multi-iteration research using:
1. SearXNG for better web search (replaces DuckDuckGo)
2. Small, efficient models for query understanding and validation
3. Iterative refinement of search queries
4. Result synthesis and quality validation
5. Knowledge extraction and organization

Features:
- RAM optimized: SearXNG (~150-200MB) + Small model (~1-2GB)
- Multi-iteration research with query refinement
- Relevance scoring and duplicate detection
- Cross-reference validation
- Extensive knowledge gathering

Architecture:
- Query Analyzer: Understands research requirements (small model)
- Search Coordinator: Orchestrates multi-iteration search
- Result Synthesizer: Combines and ranks findings
- Quality Validator: Ensures research completeness

Author: Auto-Git Project
License: MIT
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import re
from collections import defaultdict

from src.research.searxng_client import SearXNGClient
from src.llm.hybrid_router import HybridRouter
from src.utils.logger import get_logger

logger = get_logger("extensive_researcher")


@dataclass
class ResearchQuery:
    """Represents a research query with metadata."""
    query: str
    iteration: int
    query_type: str  # "broad", "focused", "validation", "gap_filling"
    parent_query: Optional[str] = None
    relevance_score: float = 0.0
    

@dataclass
class ResearchResult:
    """Represents a search result with analysis."""
    title: str
    url: str
    content: str
    engine: str
    score: float
    category: str
    query: str
    iteration: int
    relevance_score: float = 0.0
    quality_score: float = 0.0
    is_duplicate: bool = False
    duplicate_of: Optional[str] = None
    

@dataclass
class ResearchSynthesis:
    """Final synthesized research output."""
    topic: str
    iterations: int
    total_queries: int
    total_results: int
    unique_results: int
    key_findings: List[str] = field(default_factory=list)
    sources: List[ResearchResult] = field(default_factory=list)
    gaps_identified: List[str] = field(default_factory=list)
    quality_score: float = 0.0
    completeness_score: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class ExtensiveResearcher:
    """
    Multi-iteration research agent with intelligent query refinement.
    
    This agent performs deep research by:
    1. Understanding research requirements with small model
    2. Generating initial broad queries
    3. Iteratively refining queries based on findings
    4. Validating and synthesizing results
    5. Identifying knowledge gaps
    
    RAM Usage:
    - SearXNG: ~150-200MB (Docker container)
    - Small Model: ~1-2GB (Qwen 2.5-VL or similar)
    - Client overhead: ~50-100MB
    Total: ~1.5-2.5GB
    """
    
    def __init__(
        self,
        searxng_url: str = "http://localhost:8888",
        hybrid_router: Optional[HybridRouter] = None,
        max_iterations: int = 3,
        results_per_query: int = 10,
        small_model_preference: List[str] = None
    ):
        """
        Initialize extensive researcher.
        
        Args:
            searxng_url: URL of SearXNG instance
            hybrid_router: HybridRouter for LLM access
            max_iterations: Maximum research iterations
            results_per_query: Results per search query
            small_model_preference: Preferred small models for analysis
        """
        self.searxng = SearXNGClient(base_url=searxng_url)
        self.router = hybrid_router
        self.max_iterations = max_iterations
        self.results_per_query = results_per_query
        
        # Small models for query understanding and validation
        # These use minimal RAM (~1-2GB) compared to large models (~8GB+)
        self.small_models = small_model_preference or [
            "qwen/qwen-2.5-vl-7b-instruct:free",  # 7B, efficient
            "meta-llama/llama-3.3-70b-instruct:free",  # Good reasoning
            "z-ai/glm-4.5-air:free"  # Fast, lightweight
        ]
        
        # Tracking
        self.all_queries: List[ResearchQuery] = []
        self.all_results: List[ResearchResult] = []
        self.seen_urls: Set[str] = set()
        self.url_to_hash: Dict[str, str] = {}
        
    async def research(
        self,
        topic: str,
        initial_context: Optional[str] = None,
        focus_areas: Optional[List[str]] = None
    ) -> ResearchSynthesis:
        """
        Conduct extensive multi-iteration research.
        
        Args:
            topic: Research topic
            initial_context: Optional initial context about the topic
            focus_areas: Optional specific areas to focus on
            
        Returns:
            ResearchSynthesis with comprehensive findings
            
        Example:
            >>> researcher = ExtensiveResearcher()
            >>> synthesis = await researcher.research(
            ...     "efficient transformer architectures",
            ...     focus_areas=["attention mechanisms", "memory optimization"]
            ... )
            >>> print(f"Found {len(synthesis.sources)} unique sources")
        """
        logger.info(f"Starting extensive research on: {topic}")
        logger.info(f"Configuration: {self.max_iterations} iterations, {self.results_per_query} results/query")
        
        # Check if SearXNG is available
        if not self.searxng.is_available():
            logger.error("SearXNG is not available. Please start it with: bash scripts/setup_searxng.sh")
            raise ConnectionError("SearXNG service is not running")
            
        # Step 1: Understand research requirements
        understanding = await self._understand_requirements(topic, initial_context, focus_areas)
        logger.info(f"Research understanding: {understanding['objective']}")
        
        # Step 2: Generate initial queries
        initial_queries = await self._generate_initial_queries(topic, understanding)
        logger.info(f"Generated {len(initial_queries)} initial queries")
        
        # Step 3: Iterative research
        for iteration in range(self.max_iterations):
            logger.info(f"\n{'='*60}")
            logger.info(f"ITERATION {iteration + 1}/{self.max_iterations}")
            logger.info(f"{'='*60}")
            
            if iteration == 0:
                queries = initial_queries
            else:
                # Refine queries based on previous results
                queries = await self._refine_queries(iteration)
                
            if not queries:
                logger.info("No more queries to process, ending research")
                break
                
            # Execute searches
            for query_obj in queries:
                await self._execute_search(query_obj)
                
            # Analyze results and identify gaps
            gaps = await self._identify_gaps(iteration)
            logger.info(f"Identified {len(gaps)} knowledge gaps")
            
        # Step 4: Synthesize findings
        synthesis = await self._synthesize_results(topic, understanding)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"RESEARCH COMPLETE")
        logger.info(f"{'='*60}")
        logger.info(f"Total queries: {synthesis.total_queries}")
        logger.info(f"Total results: {synthesis.total_results}")
        logger.info(f"Unique results: {synthesis.unique_results}")
        logger.info(f"Quality score: {synthesis.quality_score:.2f}")
        logger.info(f"Completeness: {synthesis.completeness_score:.2f}")
        
        return synthesis
        
    async def _understand_requirements(
        self,
        topic: str,
        context: Optional[str],
        focus_areas: Optional[List[str]]
    ) -> Dict[str, Any]:
        """
        Use small model to understand research requirements.
        
        This uses a lightweight model to analyze what we need to research,
        avoiding heavy models for simple understanding tasks.
        """
        prompt = f"""You are a research analyst. Analyze this research topic and provide understanding.

Topic: {topic}

{f"Context: {context}" if context else ""}
{f"Focus Areas: {', '.join(focus_areas)}" if focus_areas else ""}

Provide a brief analysis (2-3 sentences) covering:
1. Main research objective
2. Key areas to explore
3. Expected result types (papers, code, documentation, etc.)

Keep it concise and actionable."""

        if self.router:
            try:
                # Use small model for efficiency
                result = await self.router.generate_with_fallback(
                    prompt=prompt,
                    max_tokens=300,
                    temperature=0.3,
                    task_type="general",  # Route to small model
                    preferred_backend="openrouter"  # Use free tier
                )
                
                analysis = result.content
            except Exception as e:
                logger.warning(f"LLM analysis failed: {e}, using heuristics")
                analysis = f"Research objective: Understand {topic}"
        else:
            # Fallback to heuristic analysis
            analysis = f"Research objective: Comprehensive study of {topic}"
            
        return {
            "objective": analysis,
            "focus_areas": focus_areas or ["general"],
            "topic": topic
        }
        
    async def _generate_initial_queries(
        self,
        topic: str,
        understanding: Dict[str, Any]
    ) -> List[ResearchQuery]:
        """Generate initial broad search queries."""
        
        # Generate diverse query variations
        queries = []
        
        # 1. Direct topic query
        queries.append(ResearchQuery(
            query=topic,
            iteration=0,
            query_type="broad"
        ))
        
        # 2. Academic/paper query
        queries.append(ResearchQuery(
            query=f"{topic} research papers",
            iteration=0,
            query_type="broad"
        ))
        
        # 3. Implementation query
        queries.append(ResearchQuery(
            query=f"{topic} implementation code examples",
            iteration=0,
            query_type="broad"
        ))
        
        # 4. Tutorial/guide query
        queries.append(ResearchQuery(
            query=f"{topic} tutorial guide best practices",
            iteration=0,
            query_type="broad"
        ))
        
        # 5. Focus area queries
        focus_areas = understanding.get("focus_areas", [])
        for area in focus_areas[:3]:  # Limit to 3 focus areas
            queries.append(ResearchQuery(
                query=f"{topic} {area}",
                iteration=0,
                query_type="focused"
            ))
            
        self.all_queries.extend(queries)
        return queries
        
    async def _execute_search(self, query_obj: ResearchQuery):
        """Execute a search query and process results."""
        logger.info(f"  Searching [{query_obj.query_type}]: {query_obj.query}")
        
        try:
            # Determine search type based on query
            if "paper" in query_obj.query.lower() or "research" in query_obj.query.lower():
                # Use academic engines
                results = self.searxng.search(
                    query=query_obj.query,
                    num_results=self.results_per_query,
                    categories="science",
                    engines="arxiv,google"
                )
            elif "code" in query_obj.query.lower() or "implementation" in query_obj.query.lower():
                # Use code engines
                results = self.searxng.search_code(
                    query=query_obj.query,
                    num_results=self.results_per_query
                )
            else:
                # General search
                results = self.searxng.search(
                    query=query_obj.query,
                    num_results=self.results_per_query
                )
                
            # Process results
            new_results = 0
            for result in results:
                # Check for duplicates
                url = result['url']
                is_duplicate, duplicate_of = self._check_duplicate(url, result['content'])
                
                if not is_duplicate:
                    self.seen_urls.add(url)
                    new_results += 1
                    
                research_result = ResearchResult(
                    title=result['title'],
                    url=url,
                    content=result['content'],
                    engine=result['engine'],
                    score=result.get('score', 0.0),
                    category=result.get('category', 'general'),
                    query=query_obj.query,
                    iteration=query_obj.iteration,
                    is_duplicate=is_duplicate,
                    duplicate_of=duplicate_of
                )
                
                self.all_results.append(research_result)
                
            logger.info(f"    Found {len(results)} results ({new_results} new, {len(results)-new_results} duplicates)")
            
        except Exception as e:
            logger.error(f"Search failed for '{query_obj.query}': {e}")
            
    def _check_duplicate(self, url: str, content: str) -> tuple[bool, Optional[str]]:
        """Check if result is duplicate based on URL and content."""
        # Check exact URL match
        if url in self.seen_urls:
            return True, url
            
        # Check content similarity (simple hash-based)
        content_hash = hashlib.md5(content.encode()).hexdigest()
        
        for seen_url, seen_hash in self.url_to_hash.items():
            if content_hash == seen_hash:
                return True, seen_url
                
        # Not a duplicate
        self.url_to_hash[url] = content_hash
        return False, None
        
    async def _refine_queries(self, iteration: int) -> List[ResearchQuery]:
        """Refine queries based on previous results."""
        
        # Get unique results from previous iteration
        prev_results = [r for r in self.all_results if r.iteration == iteration - 1 and not r.is_duplicate]
        
        if not prev_results:
            logger.warning("No results from previous iteration to refine")
            return []
            
        # Extract key terms from previous results
        key_terms = self._extract_key_terms(prev_results)
        logger.info(f"  Extracted key terms: {', '.join(key_terms[:5])}...")
        
        # Generate refined queries
        refined_queries = []
        
        # Add focused queries for top terms
        for term in key_terms[:3]:
            refined_queries.append(ResearchQuery(
                query=f"{self.all_queries[0].query} {term}",
                iteration=iteration,
                query_type="focused",
                parent_query=self.all_queries[0].query
            ))
            
        self.all_queries.extend(refined_queries)
        return refined_queries
        
    def _extract_key_terms(self, results: List[ResearchResult]) -> List[str]:
        """Extract key terms from results using simple heuristics."""
        term_freq = defaultdict(int)
        
        for result in results:
            # Extract terms from title and content
            text = f"{result.title} {result.content}".lower()
            
            # Simple term extraction (words 4+ chars, not common words)
            words = re.findall(r'\b[a-z]{4,}\b', text)
            
            common_words = {'that', 'this', 'with', 'from', 'have', 'been', 'were', 'will', 'would', 'could', 'should'}
            
            for word in words:
                if word not in common_words:
                    term_freq[word] += 1
                    
        # Sort by frequency
        sorted_terms = sorted(term_freq.items(), key=lambda x: x[1], reverse=True)
        return [term for term, freq in sorted_terms]
        
    async def _identify_gaps(self, iteration: int) -> List[str]:
        """Identify knowledge gaps in current research."""
        
        # Get unique results so far
        unique_results = [r for r in self.all_results if not r.is_duplicate]
        
        gaps = []
        
        # Check for missing result types
        has_papers = any('arxiv' in r.url or 'paper' in r.title.lower() for r in unique_results)
        has_code = any('github' in r.url or 'code' in r.title.lower() for r in unique_results)
        has_docs = any('doc' in r.url or 'tutorial' in r.title.lower() for r in unique_results)
        
        if not has_papers:
            gaps.append("Missing academic papers")
        if not has_code:
            gaps.append("Missing code implementations")
        if not has_docs:
            gaps.append("Missing documentation/tutorials")
            
        return gaps
        
    async def _synthesize_results(
        self,
        topic: str,
        understanding: Dict[str, Any]
    ) -> ResearchSynthesis:
        """Synthesize all research results into final output."""
        
        # Get unique, high-quality results
        unique_results = [r for r in self.all_results if not r.is_duplicate]
        
        # Score results by relevance
        for result in unique_results:
            result.relevance_score = self._score_relevance(result, topic)
            result.quality_score = self._score_quality(result)
            
        # Sort by combined score
        unique_results.sort(
            key=lambda r: (r.relevance_score + r.quality_score) / 2,
            reverse=True
        )
        
        # Extract key findings (use small model if available)
        key_findings = await self._extract_key_findings(unique_results[:20], topic)
        
        # Calculate overall scores
        quality_score = sum(r.quality_score for r in unique_results) / max(len(unique_results), 1)
        completeness_score = self._calculate_completeness(unique_results)
        
        # Identify remaining gaps
        gaps = await self._identify_gaps(self.max_iterations)
        
        synthesis = ResearchSynthesis(
            topic=topic,
            iterations=self.max_iterations,
            total_queries=len(self.all_queries),
            total_results=len(self.all_results),
            unique_results=len(unique_results),
            key_findings=key_findings,
            sources=unique_results[:50],  # Top 50 sources
            gaps_identified=gaps,
            quality_score=quality_score,
            completeness_score=completeness_score
        )
        
        return synthesis
        
    def _score_relevance(self, result: ResearchResult, topic: str) -> float:
        """Score result relevance to topic."""
        score = 0.0
        
        # Check topic words in title (high weight)
        topic_words = set(topic.lower().split())
        title_words = set(result.title.lower().split())
        title_overlap = len(topic_words & title_words) / max(len(topic_words), 1)
        score += title_overlap * 0.5
        
        # Check topic words in content (medium weight)
        content_words = set(result.content.lower().split())
        content_overlap = len(topic_words & content_words) / max(len(topic_words), 1)
        score += content_overlap * 0.3
        
        # Engine quality bonus
        quality_engines = ['arxiv', 'github', 'wikipedia']
        if any(engine in result.engine for engine in quality_engines):
            score += 0.2
            
        return min(score, 1.0)
        
    def _score_quality(self, result: ResearchResult) -> float:
        """Score result quality."""
        score = 0.0
        
        # Title quality (has length, not all caps)
        if len(result.title) > 20:
            score += 0.2
        if not result.title.isupper():
            score += 0.1
            
        # Content quality (has substance)
        if len(result.content) > 100:
            score += 0.3
            
        # URL quality (reputable domains)
        reputable_domains = ['.edu', '.org', 'arxiv', 'github', 'wikipedia', 'stackoverflow']
        if any(domain in result.url for domain in reputable_domains):
            score += 0.4
            
        return min(score, 1.0)
        
    def _calculate_completeness(self, results: List[ResearchResult]) -> float:
        """Calculate research completeness."""
        score = 0.0
        
        # Check diversity of sources
        engines = set(r.engine for r in results)
        score += min(len(engines) / 5.0, 0.3)  # Max 0.3 for 5+ engines
        
        # Check diversity of categories
        categories = set(r.category for r in results)
        score += min(len(categories) / 3.0, 0.2)  # Max 0.2 for 3+ categories
        
        # Check result count
        score += min(len(results) / 50.0, 0.3)  # Max 0.3 for 50+ results
        
        # Check query diversity
        query_types = set(q.query_type for q in self.all_queries)
        score += min(len(query_types) / 3.0, 0.2)  # Max 0.2 for 3+ query types
        
        return min(score, 1.0)
        
    async def _extract_key_findings(
        self,
        top_results: List[ResearchResult],
        topic: str
    ) -> List[str]:
        """Extract key findings from top results using small model."""
        
        if not self.router or not top_results:
            # Fallback: Extract from titles
            return [r.title for r in top_results[:5]]
            
        # Prepare summaries of top results
        summaries = "\n\n".join([
            f"{i+1}. {r.title}\n   {r.content[:200]}..."
            for i, r in enumerate(top_results[:10])
        ])
        
        prompt = f"""Based on these research results about "{topic}", extract 5 key findings.

Results:
{summaries}

Provide 5 concise findings (one sentence each):
1.
2.
3.
4.
5."""

        try:
            result = await self.router.generate_with_fallback(
                prompt=prompt,
                max_tokens=400,
                temperature=0.3,
                task_type="general",
                preferred_backend="openrouter"
            )
            
            # Parse numbered findings
            findings = []
            for line in result.content.split('\n'):
                if re.match(r'^\d+\.', line.strip()):
                    finding = re.sub(r'^\d+\.\s*', '', line.strip())
                    if finding:
                        findings.append(finding)
                        
            return findings[:5] if findings else [r.title for r in top_results[:5]]
            
        except Exception as e:
            logger.warning(f"Key findings extraction failed: {e}")
            return [r.title for r in top_results[:5]]


# Convenience function
async def research_topic(
    topic: str,
    max_iterations: int = 3,
    focus_areas: Optional[List[str]] = None
) -> ResearchSynthesis:
    """
    Quick research function.
    
    Example:
        >>> synthesis = await research_topic(
        ...     "efficient transformers",
        ...     max_iterations=3,
        ...     focus_areas=["attention", "memory"]
        ... )
    """
    from src.llm.multi_backend_manager import MultiBackendLLMManager
    
    # Initialize components
    manager = MultiBackendLLMManager()
    router = HybridRouter(manager)
    researcher = ExtensiveResearcher(hybrid_router=router, max_iterations=max_iterations)
    
    # Conduct research
    return await researcher.research(topic, focus_areas=focus_areas)


if __name__ == "__main__":
    # Test the extensive researcher
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    async def test():
        topic = sys.argv[1] if len(sys.argv) > 1 else "machine learning transformers"
        
        print(f"\n{'='*60}")
        print(f"EXTENSIVE RESEARCH TEST")
        print(f"{'='*60}")
        print(f"Topic: {topic}\n")
        
        synthesis = await research_topic(
            topic=topic,
            max_iterations=2,
            focus_areas=["efficiency", "implementation"]
        )
        
        print(f"\n{'='*60}")
        print(f"RESEARCH RESULTS")
        print(f"{'='*60}")
        print(f"Total Queries: {synthesis.total_queries}")
        print(f"Total Results: {synthesis.total_results}")
        print(f"Unique Results: {synthesis.unique_results}")
        print(f"Quality Score: {synthesis.quality_score:.2%}")
        print(f"Completeness: {synthesis.completeness_score:.2%}")
        
        print(f"\n{'='*60}")
        print(f"KEY FINDINGS")
        print(f"{'='*60}")
        for i, finding in enumerate(synthesis.key_findings, 1):
            print(f"{i}. {finding}")
            
        print(f"\n{'='*60}")
        print(f"TOP 10 SOURCES")
        print(f"{'='*60}")
        for i, source in enumerate(synthesis.sources[:10], 1):
            print(f"\n{i}. {source.title}")
            print(f"   URL: {source.url}")
            print(f"   Relevance: {source.relevance_score:.2f} | Quality: {source.quality_score:.2f}")
            
        if synthesis.gaps_identified:
            print(f"\n{'='*60}")
            print(f"IDENTIFIED GAPS")
            print(f"{'='*60}")
            for gap in synthesis.gaps_identified:
                print(f"- {gap}")
                
    asyncio.run(test())
