"""
Hybrid Router with Fallback Support

Provides intelligent routing, automatic fallback, and parallel execution
capabilities for multi-backend LLM systems.
"""

import asyncio
import logging
import time
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from openai import AsyncOpenAI

from src.llm.semantic_cache import get_semantic_cache
from src.llm.consensus_selector import ConsensusSelector  # Integration #13

logger = logging.getLogger(__name__)


@dataclass
class GenerationResult:
    """Result from a generation request."""
    content: Optional[str]
    backend: str
    model: str
    latency: float
    tokens: int = 0
    success: bool = True
    error: Optional[str] = None


class HybridRouter:
    """
    Routes requests to appropriate backends with fallback support.
    
    Features:
    - Automatic fallback on errors
    - Parallel execution for consensus
    - Latency tracking
    - Error handling and logging
    """
    
    def __init__(self, backend_manager, use_cache: bool = True):
        """
        Initialize the hybrid router.
        
        Args:
            backend_manager: MultiBackendLLMManager instance
            use_cache: Enable semantic caching (default: True)
        """
        self.backend_manager = backend_manager
        self.fallback_order = backend_manager.get_fallback_order()
        self.use_cache = use_cache
        self.cache = get_semantic_cache() if use_cache else None
        
        # Statistics
        self.request_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.total_latency = 0.0
        
        logger.info(f"HybridRouter initialized with fallback order: {self.fallback_order}, cache={'enabled' if use_cache else 'disabled'}")
    
    async def generate_with_fallback(
        self,
        task_type: str,
        messages: List[Dict[str, str]],
        max_retries: Optional[int] = None,
        timeout: float = 60.0,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Optional[GenerationResult]:
        """
        Generate completion with automatic fallback.
        
        Tries backends in fallback order until one succeeds.
        
        Args:
            task_type: Type of task for routing
            messages: Chat messages
            max_retries: Maximum retry attempts (None = try all backends)
            timeout: Timeout per backend in seconds
            temperature: Override temperature
            max_tokens: Override max tokens
        
        Returns:
            GenerationResult or None if all backends fail
        """
        self.request_count += 1
        
        # Check cache first (if enabled)
        if self.cache:
            # Create cache key from messages
            cache_query = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
            
            cached = self.cache.get(cache_query)
            if cached:
                response, metadata = cached
                logger.info(f"✅ Cache hit (similarity={metadata['similarity']:.3f})")
                
                # Return cached result
                return GenerationResult(
                    content=response,
                    backend=metadata['backend'],
                    model=metadata['model'],
                    latency=0.0,  # Instant from cache
                    tokens=metadata['tokens'],
                    success=True,
                    error=None
                )
        
        errors = []
        
        if max_retries is None:
            max_retries = len(self.fallback_order)
        
        for i, backend_name in enumerate(self.fallback_order[:max_retries]):
            if backend_name not in self.backend_manager.backends:
                logger.warning(f"Backend {backend_name} not available, skipping")
                continue
            
            try:
                logger.info(f"Attempt {i+1}/{max_retries}: Trying backend '{backend_name}'")
                
                result = await self._generate_single(
                    backend_name=backend_name,
                    task_type=task_type,
                    messages=messages,
                    timeout=timeout,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                
                if result.success:
                    logger.info(f"✓ Success with backend '{backend_name}' (latency: {result.latency:.2f}s)")
                    self.success_count += 1
                    self.total_latency += result.latency
                    
                    # Cache the result (if enabled and has content)
                    if self.cache and result.content:
                        cache_query = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
                        self.cache.put(
                            query=cache_query,
                            response=result.content,
                            backend=result.backend,
                            model=result.model,
                            tokens=result.tokens
                        )
                    
                    return result
                else:
                    errors.append(f"{backend_name}: {result.error}")
                    logger.warning(f"✗ Failed with backend '{backend_name}': {result.error}")
                
            except asyncio.TimeoutError:
                error_msg = f"{backend_name}: Timeout after {timeout}s"
                logger.warning(error_msg)
                errors.append(error_msg)
                continue
                
            except Exception as e:
                error_msg = f"{backend_name}: {str(e)}"
                logger.warning(error_msg)
                errors.append(error_msg)
                continue
        
        # All backends failed
        self.failure_count += 1
        logger.error(f"All {len(self.fallback_order)} backends failed. Errors: {errors}")
        return GenerationResult(
            content=None,
            backend="none",
            model="none",
            latency=0.0,
            success=False,
            error="; ".join(errors)
        )
    
    async def parallel_generate(
        self,
        task_type: str,
        messages: List[Dict[str, str]],
        backends: Optional[List[str]] = None,
        return_first: bool = True,
        timeout: float = 60.0,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> List[GenerationResult]:
        """
        Generate from multiple backends in parallel.
        
        Useful for:
        - Getting fastest response
        - Consensus/voting across models
        - A/B testing
        
        Args:
            task_type: Type of task for routing
            messages: Chat messages
            backends: Specific backends to use (None = use all)
            return_first: Return immediately when first completes
            timeout: Timeout per backend
            temperature: Override temperature
            max_tokens: Override max tokens
        
        Returns:
            List of GenerationResult objects
        """
        if backends is None:
            backends = self.backend_manager.get_all_backends()
        
        tasks = []
        for backend_name in backends:
            if backend_name not in self.backend_manager.backends:
                logger.warning(f"Backend {backend_name} not available, skipping")
                continue
            
            task = self._generate_single(
                backend_name=backend_name,
                task_type=task_type,
                messages=messages,
                timeout=timeout,
                temperature=temperature,
                max_tokens=max_tokens
            )
            tasks.append(task)
        
        if not tasks:
            logger.error("No backends available for parallel generation")
            return []
        
        if return_first:
            # Return as soon as first completes
            done, pending = await asyncio.wait(
                tasks,
                return_when=asyncio.FIRST_COMPLETED,
                timeout=timeout
            )
            
            # Cancel pending tasks
            for task in pending:
                task.cancel()
            
            results = [task.result() for task in done if not task.cancelled()]
            logger.info(f"Parallel generation: first completed in {results[0].latency:.2f}s")
            return results
        else:
            # Wait for all (with timeout)
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Convert exceptions to failed results
            final_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    backend_name = backends[i] if i < len(backends) else "unknown"
                    final_results.append(GenerationResult(
                        content=None,
                        backend=backend_name,
                        model="unknown",
                        latency=0.0,
                        success=False,
                        error=str(result)
                    ))
                else:
                    final_results.append(result)
            
            successful = sum(1 for r in final_results if r.success)
            logger.info(f"Parallel generation: {successful}/{len(final_results)} succeeded")
            return final_results
    
    async def _generate_single(
        self,
        backend_name: str,
        task_type: str,
        messages: List[Dict[str, str]],
        timeout: float = 60.0,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> GenerationResult:
        """
        Generate from a single backend.
        
        Args:
            backend_name: Name of backend to use
            task_type: Type of task
            messages: Chat messages
            timeout: Timeout in seconds
            temperature: Override temperature
            max_tokens: Override max tokens
        
        Returns:
            GenerationResult object
        """
        start_time = time.time()
        
        try:
            # Get model info directly instead of using get_llm_resource
            backend_config = self.backend_manager.backends[backend_name]
            model_info = self.backend_manager.get_model_for_task(task_type, backend_name)
            
            if model_info is None:
                # Fallback to first model
                if backend_config.models:
                    model_info = backend_config.models[0]
                else:
                    raise ValueError(f"No models available for backend {backend_name}")
            
            # Use overrides or defaults
            final_temp = temperature if temperature is not None else model_info.temperature
            final_max_tokens = max_tokens if max_tokens is not None else model_info.max_tokens
            
            # Get client
            client = self.backend_manager.get_client(backend_name)
            
            # Make request with timeout
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=model_info.name,
                    messages=messages,
                    temperature=final_temp,
                    max_tokens=final_max_tokens
                ),
                timeout=timeout
            )
            
            latency = time.time() - start_time
            message = response.choices[0].message
            content = message.content
            
            # Handle reasoning models that put content in 'reasoning' field
            if not content and hasattr(message, 'reasoning'):
                content = message.reasoning
                logger.debug(f"Used reasoning field from {backend_name}")
            
            # Get token count if available
            tokens = 0
            if hasattr(response, 'usage') and response.usage:
                tokens = response.usage.total_tokens
            
            return GenerationResult(
                content=content,
                backend=backend_name,
                model=model_info.name,
                latency=latency,
                tokens=tokens,
                success=True,
                error=None
            )
            
        except asyncio.TimeoutError:
            latency = time.time() - start_time
            return GenerationResult(
                content=None,
                backend=backend_name,
                model="unknown",
                latency=latency,
                success=False,
                error=f"Timeout after {timeout}s"
            )
            
        except Exception as e:
            latency = time.time() - start_time
            logger.error(f"Error in {backend_name}: {str(e)}")
            return GenerationResult(
                content=None,
                backend=backend_name,
                model="unknown",
                latency=latency,
                success=False,
                error=str(e)
            )
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get router statistics.
        
        Returns:
            Dictionary with statistics
        """
        avg_latency = self.total_latency / self.success_count if self.success_count > 0 else 0.0
        success_rate = self.success_count / self.request_count if self.request_count > 0 else 0.0
        
        return {
            "total_requests": self.request_count,
            "successful_requests": self.success_count,
            "failed_requests": self.failure_count,
            "success_rate": success_rate,
            "average_latency": avg_latency
        }
    
    def reset_statistics(self) -> None:
        """Reset statistics counters."""
        self.request_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.total_latency = 0.0
        logger.info("Statistics reset")
    
    async def parallel_multi_model_generate(
        self,
        messages: List[Dict[str, str]],
        models: List[str],
        task_type: str = "general",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: float = 30.0
    ) -> List[GenerationResult]:
        """
        Generate responses from multiple models in parallel (Integration #13).
        
        Executes requests to multiple models simultaneously and returns all successful responses.
        This enables consensus-based selection for higher quality outputs.
        
        Args:
            messages: Chat messages
            models: List of model identifiers to query in parallel
            task_type: Type of task for routing
            temperature: Generation temperature
            max_tokens: Maximum tokens to generate
            timeout: Timeout for each model request
            
        Returns:
            List of GenerationResult objects (only successful responses)
            
        Example:
            results = await router.parallel_multi_model_generate(
                messages=[{"role": "user", "content": "Implement binary search"}],
                models=["qwen/qwen3-coder:free", "xiaomi/mimo-v2-flash:free"],
                task_type="code_generation"
            )
        """
        logger.info(f"Parallel generation with {len(models)} models: {models}")
        
        # Create tasks for each model
        tasks = []
        for model in models:
            task = self._generate_single_model(
                messages=messages,
                model=model,
                task_type=task_type,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout
            )
            tasks.append(task)
        
        # Execute all tasks in parallel
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time
        
        # Filter successful responses
        successful = []
        failed = []
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(f"Model {models[i]} failed with exception: {result}")
                failed.append(models[i])
            elif isinstance(result, GenerationResult) and result.success and result.content:
                successful.append(result)
            else:
                logger.warning(f"Model {models[i]} returned unsuccessful result")
                failed.append(models[i])
        
        success_rate = len(successful) / len(models) if models else 0
        
        logger.info(f"✅ Parallel generation complete: {len(successful)}/{len(models)} succeeded in {total_time:.2f}s")
        if failed:
            logger.info(f"   Failed models: {failed}")
        
        return successful
    
    async def _generate_single_model(
        self,
        messages: List[Dict[str, str]],
        model: str,
        task_type: str,
        temperature: Optional[float],
        max_tokens: Optional[int],
        timeout: float
    ) -> GenerationResult:
        """
        Generate from a single model (helper for parallel_multi_model_generate).
        
        Args:
            messages: Chat messages
            model: Model identifier (e.g., "qwen/qwen3-coder:free")
            task_type: Type of task
            temperature: Generation temperature
            max_tokens: Maximum tokens
            timeout: Timeout in seconds
            
        Returns:
            GenerationResult object
        """
        try:
            # Parse model string to get backend and model name
            if "/" in model:
                # Format: "backend/model" or "provider/model:tag"
                parts = model.split("/", 1)
                backend_hint = parts[0]
                model_name = parts[1]
            else:
                backend_hint = "local"
                model_name = model
            
            # Find appropriate backend
            backend_name = None
            if backend_hint in self.backend_manager.backends:
                backend_name = backend_hint
            elif backend_hint == "ollama":  # Alias for local
                backend_name = "local" if "local" in self.backend_manager.backends else None
            elif backend_hint == "qwen" or backend_hint == "xiaomi" or backend_hint == "mistralai" or backend_hint == "google" or backend_hint == "microsoft":
                # These are OpenRouter providers
                if "openrouter" in self.backend_manager.backends:
                    backend_name = "openrouter"
                    model_name = model  # Use full model string
            
            if not backend_name:
                logger.warning(f"No backend found for model {model}, using fallback")
                return await self.generate_with_fallback(
                    task_type=task_type,
                    messages=messages,
                    timeout=timeout,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            
            # Get backend client
            client = self.backend_manager.get_client(backend_name)
            
            # Generate with timeout
            start_time = time.time()
            
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=temperature or 0.7,
                    max_tokens=max_tokens or 2000
                ),
                timeout=timeout
            )
            
            latency = time.time() - start_time
            
            logger.debug(f"Model {model} responded in {latency:.2f}s")
            
            # Extract content from response
            if hasattr(response, 'choices') and response.choices:
                content = response.choices[0].message.content
                tokens = getattr(response.usage, 'total_tokens', 0) if hasattr(response, 'usage') else 0
            else:
                content = str(response)
                tokens = 0
            
            # Create GenerationResult
            return GenerationResult(
                content=content,
                backend=backend_name,
                model=model_name,
                latency=latency,
                tokens=tokens,
                success=True,
                error=None
            )
            
        except asyncio.TimeoutError:
            logger.warning(f"Model {model} timed out after {timeout}s")
            return GenerationResult(
                content="",
                backend="timeout",
                model=model,
                latency=timeout,
                tokens=0,
                success=False,
                error=f"Timeout after {timeout}s"
            )
        except Exception as e:
            logger.error(f"Model {model} failed: {e}")
            return GenerationResult(
                content="",
                backend="error",
                model=model,
                latency=0.0,
                tokens=0,
                success=False,
                error=str(e)
            )
    
    async def parallel_generate_with_consensus(
        self,
        messages: List[Dict[str, str]],
        models: List[str],
        task_type: str = "general",
        consensus_strategy: str = "quality_score",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: float = 30.0
    ) -> Tuple[GenerationResult, Dict[str, Any]]:
        """
        Generate with multiple models and select best via consensus (Integration #13).
        
        This is the main API for parallel multi-model generation with automatic
        consensus-based selection for higher quality outputs.
        
        Args:
            messages: Chat messages
            models: List of model identifiers
            task_type: Type of task (affects consensus scoring)
            consensus_strategy: Selection strategy ("quality_score", "majority_vote", "ensemble")
            temperature: Generation temperature
            max_tokens: Maximum tokens to generate
            timeout: Timeout for each model
            
        Returns:
            Tuple of (best_result, consensus_metadata)
            
        Example:
            result, metadata = await router.parallel_generate_with_consensus(
                messages=[{"role": "user", "content": "Implement quicksort"}],
                models=["qwen/qwen3-coder:free", "xiaomi/mimo-v2-flash:free"],
                task_type="code_generation"
            )
            print(f"Best model: {metadata['best_model']}")
            print(f"Quality score: {metadata['best_score']}")
        """
        # Get parallel responses
        results = await self.parallel_multi_model_generate(
            messages=messages,
            models=models,
            task_type=task_type,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout
        )
        
        if not results:
            logger.error("All models failed in parallel generation")
            return GenerationResult(
                content="",
                backend="none",
                model="none",
                latency=0.0,
                tokens=0,
                success=False,
                error="All models failed"
            ), {"error": "All models failed"}
        
        if len(results) == 1:
            logger.info("Only one model succeeded, returning its response")
            return results[0], {"single_response": True, "model": results[0].model}
        
        # Convert GenerationResult to dict format for consensus selector
        response_dicts = [
            {
                'content': r.content,
                'model': r.model,
                'backend': r.backend,
                'latency': r.latency,
                'tokens': r.tokens
            }
            for r in results
        ]
        
        # Select best via consensus
        selector = ConsensusSelector(strategy=consensus_strategy)
        best_content, metadata = selector.select_best(response_dicts, task_type=task_type)
        
        # Find the corresponding GenerationResult
        best_result = next(
            r for r in results
            if r.content == best_content
        )
        
        # Add consensus metadata
        metadata['parallel_models'] = models
        metadata['successful_models'] = [r.model for r in results]
        metadata['failed_models'] = list(set(models) - set([r.model for r in results]))
        
        logger.info(f"✅ Consensus selection complete: {metadata['best_model']} (score: {metadata.get('best_score', 'N/A')})")
        
        return best_result, metadata


async def consensus_generate(
    router: HybridRouter,
    task_type: str,
    messages: List[Dict[str, str]],
    min_agreements: int = 2,
    backends: Optional[List[str]] = None
) -> Tuple[Optional[str], float]:
    """
    Generate with consensus across multiple backends.
    
    Uses voting to select the most agreed-upon response.
    
    Args:
        router: HybridRouter instance
        task_type: Type of task
        messages: Chat messages
        min_agreements: Minimum number of agreeing responses
        backends: Specific backends to use
    
    Returns:
        Tuple of (consensus_content, confidence_score)
    """
    # Get responses from all backends
    results = await router.parallel_generate(
        task_type=task_type,
        messages=messages,
        backends=backends,
        return_first=False
    )
    
    # Filter successful results
    successful_results = [r for r in results if r.success and r.content]
    
    if len(successful_results) < min_agreements:
        logger.warning(f"Not enough responses for consensus: {len(successful_results)}/{min_agreements}")
        return None, 0.0
    
    # Simple voting: count identical responses
    response_counts: Dict[str, int] = {}
    for result in successful_results:
        content = result.content
        if content:
            response_counts[content] = response_counts.get(content, 0) + 1
    
    # Find most common response
    if not response_counts:
        return None, 0.0
    
    best_response = max(response_counts.items(), key=lambda x: x[1])
    consensus_content, agreement_count = best_response
    
    # Calculate confidence
    confidence = agreement_count / len(successful_results)
    
    logger.info(f"Consensus: {agreement_count}/{len(successful_results)} backends agreed (confidence: {confidence:.2f})")
    
    if agreement_count >= min_agreements:
        return consensus_content, confidence
    else:
        return None, confidence


if __name__ == "__main__":
    # Test the router
    import sys
    sys.path.append(".")
    from multi_backend_manager import MultiBackendLLMManager
    
    logging.basicConfig(level=logging.INFO)
    
    async def test_router():
        manager = MultiBackendLLMManager()
        router = HybridRouter(manager)
        
        messages = [
            {"role": "user", "content": "What is 2+2?"}
        ]
        
        print("\n=== Testing Fallback ===")
        result = await router.generate_with_fallback(
            task_type="general",
            messages=messages,
            max_retries=2
        )
        
        if result and result.success:
            print(f"✓ Response: {result.content[:100]}")
            print(f"  Backend: {result.backend}")
            print(f"  Model: {result.model}")
            print(f"  Latency: {result.latency:.2f}s")
        else:
            print(f"✗ Failed: {result.error if result else 'No result'}")
        
        print("\n=== Statistics ===")
        stats = router.get_statistics()
        for key, value in stats.items():
            print(f"{key}: {value}")
    
    asyncio.run(test_router())
