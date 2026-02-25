"""
Ollama Client - Production-grade wrapper for local model inference.
"""

import asyncio
from typing import Optional, Dict, Any, List, AsyncIterator
import ollama
from ollama import AsyncClient
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

from src.utils.logger import get_logger
from src.utils.config import get_config


logger = get_logger("ollama_client")


class OllamaClient:
    """
    Production-grade Ollama client with error handling, retries, and streaming.
    
    Features:
    - Automatic retries with exponential backoff
    - Streaming support for long responses
    - Token counting and usage tracking
    - Error handling and logging
    - Connection pooling
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        timeout: int = 120,
        max_retries: int = 3
    ):
        """
        Initialize Ollama client.
        
        Args:
            base_url: Ollama server URL
            timeout: Request timeout in seconds
            max_retries: Max retry attempts
        """
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.client = AsyncClient(host=base_url, timeout=timeout)
        
        logger.info(f"Ollama client initialized: {base_url}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        reraise=True
    )
    async def generate(
        self,
        model: str,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        timeout: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate completion from Ollama model.

        Args:
            model: Model name (e.g., "qwen3:8b")
            prompt: User prompt
            system: System message (optional)
            temperature: Sampling temperature
            max_tokens: Max tokens to generate
            stream: Enable streaming
            timeout: Request timeout in seconds (overrides default)
            **kwargs: Additional Ollama parameters

        Returns:
            Response dict with content, model, tokens used
        """
        try:
            logger.debug(f"Generating with {model}: {prompt[:100]}...")

            options = {
                "temperature": temperature,
            }
            if max_tokens:
                options["num_predict"] = max_tokens

            options.update(kwargs)

            if stream:
                return await self._generate_stream(model, prompt, system, options)

            # Use custom timeout if provided, otherwise use default
            request_timeout = timeout if timeout is not None else self.timeout

            # Create a new client with the custom timeout for this request
            client = AsyncClient(host=self.base_url, timeout=request_timeout)

            response = await client.generate(
                model=model,
                prompt=prompt,
                system=system,
                options=options
            )
            
            result = {
                "content": response.get("response", ""),
                "model": model,
                "done": response.get("done", True),
                "context": response.get("context", []),
                "total_duration": response.get("total_duration", 0),
                "load_duration": response.get("load_duration", 0),
                "prompt_eval_count": response.get("prompt_eval_count", 0),
                "eval_count": response.get("eval_count", 0),
            }
            
            logger.info(
                f"Generated {result['eval_count']} tokens with {model} "
                f"in {result['total_duration'] / 1e9:.2f}s"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Generation failed with {model}: {str(e)}", exc_info=True)
            raise
    
    async def _generate_stream(
        self,
        model: str,
        prompt: str,
        system: Optional[str],
        options: Dict
    ) -> AsyncIterator[str]:
        """
        Stream generation from model.
        
        Args:
            model: Model name
            prompt: User prompt
            system: System message
            options: Generation options
        
        Yields:
            Streamed response chunks
        """
        full_response = ""
        
        async for chunk in await self.client.generate(
            model=model,
            prompt=prompt,
            system=system,
            options=options,
            stream=True
        ):
            content = chunk.get("response", "")
            full_response += content
            yield content
        
        logger.info(f"Streamed {len(full_response)} chars from {model}")
    
    async def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Chat completion with conversation history.
        
        Args:
            model: Model name
            messages: List of message dicts with "role" and "content"
            temperature: Sampling temperature
            max_tokens: Max tokens to generate
            **kwargs: Additional parameters
        
        Returns:
            Response dict
        """
        try:
            options = {"temperature": temperature}
            if max_tokens:
                options["num_predict"] = max_tokens
            
            options.update(kwargs)
            
            response = await self.client.chat(
                model=model,
                messages=messages,
                options=options
            )
            
            result = {
                "content": response["message"]["content"],
                "model": model,
                "role": response["message"]["role"],
                "done": response.get("done", True),
                "total_duration": response.get("total_duration", 0),
                "eval_count": response.get("eval_count", 0),
            }
            
            logger.info(f"Chat completed with {model}, {result['eval_count']} tokens")
            
            return result
            
        except Exception as e:
            logger.error(f"Chat failed with {model}: {str(e)}", exc_info=True)
            raise
    
    async def embed(
        self,
        model: str,
        text: str
    ) -> List[float]:
        """
        Generate embeddings for text.
        
        Args:
            model: Embedding model name (e.g., "all-minilm")
            text: Text to embed
        
        Returns:
            Embedding vector
        """
        try:
            response = await self.client.embeddings(
                model=model,
                prompt=text
            )
            
            embedding = response.get("embedding", [])
            logger.debug(f"Generated embedding of dimension {len(embedding)}")
            
            return embedding
            
        except Exception as e:
            logger.error(f"Embedding failed: {str(e)}", exc_info=True)
            raise
    
    async def list_models(self) -> List[Dict[str, Any]]:
        """
        List available models in Ollama.
        
        Returns:
            List of model metadata
        """
        try:
            response = await self.client.list()
            models = response.get("models", [])
            logger.info(f"Found {len(models)} available models")
            return models
            
        except Exception as e:
            logger.error(f"Failed to list models: {str(e)}", exc_info=True)
            raise
    
    async def show_model_info(self, model: str) -> Dict[str, Any]:
        """
        Get detailed model information.
        
        Args:
            model: Model name
        
        Returns:
            Model metadata
        """
        try:
            response = await self.client.show(model)
            logger.debug(f"Model info for {model}: {response.get('details', {})}")
            return response
            
        except Exception as e:
            logger.error(f"Failed to get model info: {str(e)}", exc_info=True)
            raise
    
    async def health_check(self) -> bool:
        """
        Check if Ollama server is healthy.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            models = await self.list_models()
            logger.info(f"Health check passed: {len(models)} models available")
            return True
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return False


# Global client instance
_client: Optional[OllamaClient] = None


def get_ollama_client() -> OllamaClient:
    """
    Get global Ollama client instance (singleton).
    
    Returns:
        OllamaClient instance
    """
    global _client
    
    if _client is None:
        config = get_config()
        _client = OllamaClient(
            base_url=getattr(config, "ollama_base_url", "http://localhost:11434"),
            timeout=getattr(config, "ollama_timeout", 120)
        )
    
    return _client


async def test_ollama_connection():
    """Test Ollama connection and available models."""
    client = get_ollama_client()
    
    logger.info("Testing Ollama connection...")
    
    if await client.health_check():
        models = await client.list_models()
        logger.info(f"[OK] Connected to Ollama: {len(models)} models available")
        
        for model in models[:5]:  # Show first 5
            name = model.get("name", "unknown")
            size = model.get("size", 0) / 1e9  # Convert to GB
            logger.info(f"  - {name} ({size:.1f} GB)")
        
        return True
    else:
        logger.error("[FAIL] Failed to connect to Ollama")
        return False
