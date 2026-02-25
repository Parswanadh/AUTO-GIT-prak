"""
Base Pydantic AI Agent
======================

Foundation class for all Pydantic AI agents in the system.

Features:
- Automatic Logfire tracing
- Type-safe responses
- Error handling with retries
- Performance metrics collection
"""

import asyncio
from typing import TypeVar, Generic, Optional, Dict, Any
from pydantic import BaseModel
from pydantic_ai import Agent as PydanticAgent
from pydantic_ai.exceptions import UserError
import logfire

# Configure Logfire (automatic tracing)
try:
    logfire.configure()
    LOGFIRE_ENABLED = True
except Exception as e:
    print(f"Warning: Logfire not configured: {e}")
    LOGFIRE_ENABLED = False

T = TypeVar('T', bound=BaseModel)


class AgentConfig(BaseModel):
    """Configuration for agent behavior"""
    model: str = "ollama:qwen2.5-coder:7b"
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    timeout: int = 60
    retries: int = 3
    retry_delay: float = 1.0


class BaseAgent(Generic[T]):
    """
    Base class for Pydantic AI agents.
    
    Example:
        ```python
        class MyResult(BaseModel):
            output: str
            confidence: float
        
        class MyAgent(BaseAgent[MyResult]):
            def __init__(self):
                super().__init__(
                    result_type=MyResult,
                    instructions="You are a helpful assistant"
                )
        
        agent = MyAgent()
        result = await agent.run("Hello")
        ```
    """
    
    def __init__(
        self,
        result_type: type[T],
        instructions: str,
        config: Optional[AgentConfig] = None,
        name: Optional[str] = None
    ):
        """
        Initialize base agent.
        
        Args:
            result_type: Pydantic model for structured outputs
            instructions: System instructions for the agent
            config: Agent configuration
            name: Agent name for logging/tracing
        """
        self.result_type = result_type
        self.instructions = instructions
        self.config = config or AgentConfig()
        self.name = name or self.__class__.__name__
        
        # Create Pydantic AI agent
        self._agent = PydanticAgent(
            self.config.model,
            result_type=result_type,
            system_prompt=instructions
        )
        
        # Metrics
        self.call_count = 0
        self.error_count = 0
        self.total_latency = 0.0
    
    async def run(
        self,
        prompt: str,
        deps: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> T:
        """
        Run the agent with automatic tracing and error handling.
        
        Args:
            prompt: User prompt
            deps: Optional dependencies to pass to agent
            **kwargs: Additional arguments for agent.run()
        
        Returns:
            Structured result of type T
        
        Raises:
            UserError: If agent execution fails after retries
        """
        import time
        
        start_time = time.time()
        
        # Log to Logfire
        with logfire.span(
            f"{self.name}.run",
            prompt=prompt[:100],  # Truncate for readability
            model=self.config.model
        ):
            for attempt in range(self.config.retries):
                try:
                    # Run agent
                    result = await self._agent.run(
                        prompt,
                        deps=deps,
                        **kwargs
                    )
                    
                    # Update metrics
                    self.call_count += 1
                    latency = time.time() - start_time
                    self.total_latency += latency
                    
                    # Log success
                    logfire.info(
                        f"{self.name} success",
                        latency=latency,
                        attempt=attempt + 1,
                        call_count=self.call_count
                    )
                    
                    return result.data
                
                except Exception as e:
                    self.error_count += 1
                    
                    logfire.error(
                        f"{self.name} error",
                        error=str(e),
                        attempt=attempt + 1,
                        retries_left=self.config.retries - attempt - 1
                    )
                    
                    # Retry with exponential backoff
                    if attempt < self.config.retries - 1:
                        delay = self.config.retry_delay * (2 ** attempt)
                        await asyncio.sleep(delay)
                    else:
                        raise UserError(f"{self.name} failed after {self.config.retries} attempts: {e}")
    
    def run_sync(self, prompt: str, **kwargs) -> T:
        """
        Synchronous version of run().
        
        Args:
            prompt: User prompt
            **kwargs: Additional arguments
        
        Returns:
            Structured result of type T
        """
        return asyncio.run(self.run(prompt, **kwargs))
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get agent performance metrics.
        
        Returns:
            Dictionary with metrics (calls, errors, avg latency)
        """
        avg_latency = self.total_latency / self.call_count if self.call_count > 0 else 0
        
        return {
            "name": self.name,
            "model": self.config.model,
            "call_count": self.call_count,
            "error_count": self.error_count,
            "error_rate": self.error_count / self.call_count if self.call_count > 0 else 0,
            "avg_latency": avg_latency,
            "total_latency": self.total_latency
        }
    
    def reset_metrics(self):
        """Reset performance metrics."""
        self.call_count = 0
        self.error_count = 0
        self.total_latency = 0.0
