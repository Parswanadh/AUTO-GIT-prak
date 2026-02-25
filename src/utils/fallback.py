"""
Fallback mechanisms for resilient operation.

Features:
- Persona generation fallback (dynamic → base personas)
- LLM call fallback (primary → alternative models → templates)
- Search fallback chains (arxiv → cache → ChromaDB)
- Graceful degradation for all critical operations
"""

import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Callable, TypeVar, Generic
from functools import wraps

from src.utils.error_types import PipelineError, PersonaGenerationError
from src.utils.logger import get_logger
from src.utils.structured_logging import get_structured_logger
from src.utils.metrics import get_metrics_collector

logger = get_logger("fallback")
slog = get_structured_logger()
metrics = get_metrics_collector()


class FallbackResult(Enum):
    """Result of fallback execution."""
    PRIMARY_SUCCEEDED = "primary_succeeded"
    FALLBACK_SUCCEEDED = "fallback_succeeded"
    ALL_FAILED = "all_failed"


T = TypeVar("T")


@dataclass
class FallbackAttempt:
    """Record of a fallback attempt."""
    level: str
    success: bool
    duration_ms: float
    error: Optional[str] = None


@dataclass
class FallbackSummary(Generic[T]):
    """Summary of fallback execution."""
    result: FallbackResult
    value: Optional[T] = None
    attempts: list[FallbackAttempt] = None
    successful_level: Optional[str] = None

    def __post_init__(self):
        if self.attempts is None:
            self.attempts = []


class BaseFallbackChain(ABC, Generic[T]):
    """
    Base class for fallback chains.

    Implements a chain of responsibility pattern where each
    fallback level is tried in sequence until one succeeds.
    """

    def __init__(self, name: str):
        """
        Initialize fallback chain.

        Args:
            name: Name of the fallback chain (for logging)
        """
        self.name = name
        self._fallbacks: list[Callable[[], T]] = []
        self._level_names: list[str] = []

    def add_fallback(self, func: Callable[[], T], level_name: str) -> "BaseFallbackChain[T]":
        """
        Add a fallback level to the chain.

        Args:
            func: Function to call for this level
            level_name: Name of this fallback level

        Returns:
            Self for chaining
        """
        self._fallbacks.append(func)
        self._level_names.append(level_name)
        return self

    async def execute(self) -> FallbackSummary[T]:
        """
        Execute the fallback chain.

        Tries each level in sequence until one succeeds.
        Returns a summary of the execution.

        Returns:
            FallbackSummary with result and value
        """
        attempts = []

        for i, (fallback, level_name) in enumerate(zip(self._fallbacks, self._level_names)):
            start_time = asyncio.get_event_loop().time()
            level_num = i + 1
            total_levels = len(self._fallbacks)

            try:
                logger.info(
                    f"[{self.name}] Trying level {level_num}/{total_levels}: {level_name}"
                )

                # Check if function is async
                if asyncio.iscoroutinefunction(fallback):
                    result = await fallback()
                else:
                    result = fallback()

                duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000

                attempts.append(FallbackAttempt(
                    level=level_name,
                    success=True,
                    duration_ms=duration_ms,
                ))

                logger.info(f"✅ [{self.name}] Level {level_name} succeeded")

                return FallbackSummary(
                    result=(
                        FallbackResult.PRIMARY_SUCCEEDED if i == 0
                        else FallbackResult.FALLBACK_SUCCEEDED
                    ),
                    value=result,
                    attempts=attempts,
                    successful_level=level_name,
                )

            except Exception as e:
                duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
                error_msg = f"{type(e).__name__}: {str(e)[:200]}"

                attempts.append(FallbackAttempt(
                    level=level_name,
                    success=False,
                    duration_ms=duration_ms,
                    error=error_msg,
                ))

                logger.warning(
                    f"❌ [{self.name}] Level {level_name} failed: {error_msg[:100]}"
                )

                # Record failure in metrics
                metrics.record_failure(f"{self.name}_{level_name}", error_msg)

                # If this is not the last level, continue
                if i < len(self._fallbacks) - 1:
                    logger.info(f"[{self.name}] Trying next fallback level...")
                    continue

                # All levels failed
                logger.error(
                    f"❌ [{self.name}] All {total_levels} fallback levels failed"
                )

                return FallbackSummary(
                    result=FallbackResult.ALL_FAILED,
                    value=None,
                    attempts=attempts,
                )


class PersonaFallbackChain(BaseFallbackChain[dict[str, Any]]):
    """
    Fallback chain for persona generation.

    Levels:
    1. Dynamic generation via LLM
    2. Cached personas for domain
    3. Hardcoded domain-specific personas
    4. Base 3 personas only (final fallback)
    """

    # Hardcoded base personas
    BASE_PERSONAS = [
        {
            "name": "TechnicalReviewer",
            "role": "Technical Reviewer",
            "perspective": "Focuses on code correctness, efficiency, and best practices",
            "tone": "analytical and constructive",
        },
        {
            "name": "SafetyAuditor",
            "role": "Safety Auditor",
            "perspective": "Identifies potential security vulnerabilities and ethical concerns",
            "tone": "cautious and thorough",
        },
        {
            "name": "UserAdvocate",
            "role": "User Advocate",
            "perspective": "Evaluates usability and practical value for end users",
            "tone": "empathetic and practical",
        },
    ]

    # Domain-specific fallback personas
    DOMAIN_PERSONAS = {
        "machine learning": [
            {
                "name": "MLExpert",
                "role": "Machine Learning Expert",
                "perspective": "Specializes in ML algorithms, model architecture, and training techniques",
                "tone": "technical and insightful",
            },
        ],
        "quantum computing": [
            {
                "name": "QuantumSpecialist",
                "role": "Quantum Computing Specialist",
                "perspective": "Expert in quantum algorithms, circuit design, and quantum error correction",
                "tone": "precise and theoretical",
            },
        ],
        "computer vision": [
            {
                "name": "VisionExpert",
                "role": "Computer Vision Expert",
                "perspective": "Specializes in image processing, CNNs, and visual perception",
                "tone": "observant and detail-oriented",
            },
        ],
    }

    def __init__(self, domain: str = "general"):
        """
        Initialize persona fallback chain.

        Args:
            domain: Paper domain for domain-specific personas
        """
        super().__init__(name="persona_generation")
        self.domain = domain.lower()
        self._cache_path = Path("./data/cache/personas.json")
        self._load_cache()

    def _load_cache(self):
        """Load cached personas from disk."""
        self._cache = {}
        if self._cache_path.exists():
            try:
                with open(self._cache_path, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
            except (json.JSONDecodeError, IOError):
                logger.warning("Failed to load persona cache")

    def _save_cache(self):
        """Save personas to cache."""
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._cache_path, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, indent=2)
        except IOError:
            logger.warning("Failed to save persona cache")

    def level_1_dynamic_generation(self) -> dict[str, Any]:
        """
        Level 1: Generate personas dynamically via LLM.

        This would call the persona generation agent.
        For now, we'll raise an error to trigger fallback.
        """
        raise PersonaGenerationError(
            "Dynamic generation not implemented in fallback",
            domain=self.domain,
        )

    def level_2_cached_personas(self) -> dict[str, Any]:
        """
        Level 2: Use cached personas for this domain.

        Returns cached personas if available, otherwise fails.
        """
        if self.domain in self._cache:
            logger.info(f"Using cached personas for domain: {self.domain}")
            return {"personas": self._cache[self.domain], "source": "cache"}

        raise PersonaGenerationError(
            f"No cached personas for domain: {self.domain}",
            domain=self.domain,
        )

    def level_3_domain_specific(self) -> dict[str, Any]:
        """
        Level 3: Use hardcoded domain-specific personas.

        Returns domain-specific personas if available, otherwise fails.
        """
        for key, personas in self.DOMAIN_PERSONAS.items():
            if key in self.domain:
                logger.info(f"Using hardcoded personas for domain: {key}")
                result = self.BASE_PERSONAS + personas
                return {"personas": result, "source": "hardcoded_domain"}

        # No matching domain-specific personas
        raise PersonaGenerationError(
            f"No hardcoded personas for domain: {self.domain}",
            domain=self.domain,
        )

    def level_4_base_personas(self) -> dict[str, Any]:
        """
        Level 4: Use base 3 personas only.

        This always succeeds - it's the final fallback.
        """
        logger.info("Using base 3 personas (final fallback)")
        return {"personas": self.BASE_PERSONAS, "source": "base"}

    def build_chain(self) -> "PersonaFallbackChain":
        """Build the complete fallback chain."""
        self.add_fallback(self.level_1_dynamic_generation, "dynamic_generation")
        self.add_fallback(self.level_2_cached_personas, "cached_personas")
        self.add_fallback(self.level_3_domain_specific, "domain_specific")
        self.add_fallback(self.level_4_base_personas, "base_personas")
        return self


class LLMFallbackChain(BaseFallbackChain[str]):
    """
    Fallback chain for LLM calls.

    Levels:
    1. Primary model (e.g., qwen3:8b)
    2. Alternative model (e.g., gemma2:2b for simpler tasks)
    3. Increased timeout retry
    4. Template-based response
    """

    def __init__(
        self,
        primary_model: str,
        prompt: str,
        system_prompt: Optional[str] = None,
    ):
        """
        Initialize LLM fallback chain.

        Args:
            primary_model: Primary model to use
            prompt: User prompt
            system_prompt: Optional system prompt
        """
        super().__init__(name="llm_generation")
        self.primary_model = primary_model
        self.prompt = prompt
        self.system_prompt = system_prompt
        self._attempt_count = 0

    def level_1_primary_model(self) -> str:
        """Level 1: Try primary model."""
        raise NotImplementedError("Use async version")

    def level_2_alternative_model(self) -> str:
        """Level 2: Try alternative smaller model."""
        raise NotImplementedError("Use async version")

    def level_3_timeout_retry(self) -> str:
        """Level 3: Retry with increased timeout."""
        raise NotImplementedError("Use async version")

    def level_4_template_response(self) -> str:
        """Level 4: Return template-based response."""
        return "LLM unavailable - using template response"

    def build_chain(self) -> "LLMFallbackChain":
        """Build the complete fallback chain."""
        self.add_fallback(self.level_1_primary_model, "primary_model")
        self.add_fallback(self.level_2_alternative_model, "alternative_model")
        self.add_fallback(self.level_3_timeout_retry, "timeout_retry")
        self.add_fallback(self.level_4_template_response, "template_response")
        return self


class SearchFallbackChain(BaseFallbackChain[Any]):
    """
    Fallback chain for arXiv paper search.

    Levels:
    1. arxiv Python library (direct API)
    2. Cached recent results
    3. Pre-indexed ChromaDB papers
    4. Fail gracefully (return empty)
    """

    def __init__(self, query: str, max_results: int = 10):
        """
        Initialize search fallback chain.

        Args:
            query: Search query
            max_results: Maximum results to return
        """
        super().__init__(name="arxiv_search")
        self.query = query
        self.max_results = max_results
        self._cache_path = Path("./data/cache/arxiv_search.json")
        self._load_cache()

    def _load_cache(self):
        """Load cached search results."""
        self._cache = {}
        if self._cache_path.exists():
            try:
                with open(self._cache_path, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
            except (json.JSONDecodeError, IOError):
                logger.warning("Failed to load arxiv search cache")

    def _save_cache(self):
        """Save search results to cache."""
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._cache_path, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, indent=2)
        except IOError:
            logger.warning("Failed to save arxiv search cache")

    def level_1_arxiv_api(self) -> list[dict[str, Any]]:
        """Level 1: Use arxiv Python library."""
        import arxiv

        search = arxiv.Search(
            query=self.query,
            max_results=self.max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
        )

        results = []
        for result in search.results():
            results.append({
                "title": result.title,
                "abstract": result.summary,
                "authors": [a.name for a in result.authors],
                "published": result.published.isoformat(),
                "pdf_url": result.pdf_url,
                "entry_id": result.entry_id,
            })

        # Cache the results
        self._cache[self.query] = results
        self._save_cache()

        return results

    def level_2_cached_results(self) -> list[dict[str, Any]]:
        """Level 2: Use cached results."""
        if self.query in self._cache:
            logger.info(f"Using cached search results for: {self.query[:50]}")
            return self._cache[self.query]

        raise PipelineError(
            f"No cached results for query: {self.query[:50]}",
            category="PERMANENT",
        )

    def level_3_chromadb_search(self) -> list[dict[str, Any]]:
        """Level 3: Search in local ChromaDB."""
        try:
            import chromadb
            client = chromadb.PersistentClient(path="./data/vector_db")
            collection = client.get_collection("papers_novelty")

            results = collection.query(
                query_texts=[self.query],
                n_results=self.max_results,
            )

            # Convert ChromaDB results to standard format
            papers = []
            if results and results.get("metadatas"):
                for i, metadata in enumerate(results["metadatas"][0]):
                    papers.append({
                        "title": metadata.get("title", "Unknown"),
                        "abstract": metadata.get("abstract", ""),
                        "entry_id": metadata.get("entry_id", ""),
                        "source": "chromadb",
                    })

            logger.info(f"Found {len(papers)} papers in ChromaDB")
            return papers

        except Exception as e:
            raise PipelineError(
                f"ChromaDB search failed: {str(e)}",
                category="TRANSIENT",
            )

    def level_4_empty_results(self) -> list[dict[str, Any]]:
        """Level 4: Return empty results (fail gracefully)."""
        logger.warning(f"Search failed for '{self.query[:50]}', returning empty results")
        return []

    def build_chain(self) -> "SearchFallbackChain":
        """Build the complete fallback chain."""
        self.add_fallback(self.level_1_arxiv_api, "arxiv_api")
        self.add_fallback(self.level_2_cached_results, "cached_results")
        self.add_fallback(self.level_3_chromadb_search, "chromadb_search")
        self.add_fallback(self.level_4_empty_results, "empty_results")
        return self


def with_fallback(
    fallback_chain: BaseFallbackChain[T],
    on_all_failed: str = "raise",  # "raise", "return_none", "return_default"
    default_value: Optional[T] = None,
):
    """
    Decorator for wrapping functions with fallback chain.

    Args:
        fallback_chain: Configured fallback chain
        on_all_failed: What to do if all fallbacks fail
        default_value: Default value if on_all_failed="return_default"

    Example:
        chain = PersonaFallbackChain(domain="machine learning").build_chain()

        @with_fallback(chain, on_all_failed="return_default",
                       default_value={"personas": PersonaFallbackChain.BASE_PERSONAS})
        async def get_personas(domain: str):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            summary = await fallback_chain.execute()

            if summary.result == FallbackResult.ALL_FAILED:
                metrics.increment_counter("fallback_all_failed")

                if on_all_failed == "return_none":
                    return None
                elif on_all_failed == "return_default":
                    return default_value
                else:
                    raise PipelineError(
                        f"All fallback levels failed for {fallback_chain.name}"
                    )

            # Log which level succeeded
            if summary.result == FallbackResult.FALLBACK_SUCCEEDED:
                metrics.increment_counter("fallback_succeeded")
                slog.info(
                    f"✅ Fallback succeeded at level: {summary.successful_level}",
                    agent=fallback_chain.name,
                    extra={"successful_level": summary.successful_level},
                )
            else:
                metrics.increment_counter("primary_succeeded")

            return summary.value

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, we'd need to run async fallback in executor
            # For now, just call the original function
            return func(*args, **kwargs)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# Convenience functions
async def get_personas_with_fallback(
    domain: str = "general",
    generate_func: Optional[Callable] = None,
) -> dict[str, Any]:
    """
    Get personas with automatic fallback.

    Args:
        domain: Paper domain
        generate_func: Optional function for dynamic generation

    Returns:
        Dictionary with personas and source
    """
    chain = PersonaFallbackChain(domain=domain)

    # If generate function provided, use it for level 1
    if generate_func:
        chain.add_fallback(generate_func, "dynamic_generation")
    else:
        chain.add_fallback(chain.level_1_dynamic_generation, "dynamic_generation")

    chain.build_chain()
    summary = await chain.execute()

    return summary.value


async def search_arxiv_with_fallback(
    query: str,
    max_results: int = 10,
) -> list[dict[str, Any]]:
    """
    Search arXiv with automatic fallback.

    Args:
        query: Search query
        max_results: Maximum results

    Returns:
        List of paper dictionaries
    """
    chain = SearchFallbackChain(query=query, max_results=max_results)
    chain.build_chain()
    summary = await chain.execute()

    return summary.value or []
