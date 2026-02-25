# Agent Lightning Integration Guide

## Overview

This document outlines the integration of Microsoft's Agent Lightning framework into our agentic system, supporting multiple model backends including local models, OpenRouter API (free tier), and Groq Cloud API in a hybrid configuration.

## What is Agent Lightning?

Agent Lightning is Microsoft's framework for training and optimizing AI agents with:
- **Zero-code change integration** - Works with any agent framework
- **Reinforcement Learning (RL)** - Train agents with GRPO, PPO, and other algorithms
- **Automatic Prompt Optimization (APO)** - Optimize prompts automatically
- **Multi-agent support** - Selectively optimize agents in multi-agent systems
- **Framework agnostic** - Works with LangChain, AutoGen, CrewAI, or plain Python

## Installation

```bash
pip install agentlightning
```

## Architecture Integration

### 1. Hybrid Model Backend

Our system will support three backend types:

#### A. Local Models (vLLM)
- **Use case**: Privacy, cost control, offline operation
- **Models**: Qwen, LLaMA, DeepSeek, etc.
- **Setup**: vLLM server running locally

#### B. OpenRouter API (Free Tier)
- **Use case**: Access to diverse models without cost
- **Models**: Various free tier models
- **Benefits**: No infrastructure cost, multiple model options

#### C. Groq Cloud API
- **Use case**: Fast inference, production workloads
- **Models**: LLaMA, Mixtral, etc.
- **Benefits**: Ultra-fast inference, competitive pricing

### 2. Configuration Structure

```python
# config/model_backends.yaml
model_backends:
  local:
    enabled: true
    type: "vllm"
    endpoint: "http://localhost:8000/v1"
    models:
      - name: "Qwen/Qwen2.5-7B-Instruct"
        task_types: ["code_generation", "planning"]
      - name: "deepseek-ai/deepseek-coder-6.7b-instruct"
        task_types: ["code_generation"]
  
  openrouter:
    enabled: true
    type: "openai_compatible"
    endpoint: "https://openrouter.ai/api/v1"
    api_key: "${OPENROUTER_API_KEY}"
    models:
      - name: "google/gemini-flash-1.5-8b"
        task_types: ["analysis", "validation"]
      - name: "meta-llama/llama-3.2-3b-instruct:free"
        task_types: ["simple_tasks"]
  
  groq:
    enabled: true
    type: "openai_compatible"
    endpoint: "https://api.groq.com/openai/v1"
    api_key: "${GROQ_API_KEY}"
    models:
      - name: "llama-3.3-70b-versatile"
        task_types: ["complex_reasoning", "critic"]
      - name: "mixtral-8x7b-32768"
        task_types: ["code_review", "debate"]

hybrid_mode:
  enabled: true
  strategy: "cost_optimized"  # or "latency_optimized", "quality_optimized"
  fallback_order: ["local", "groq", "openrouter"]
  routing_rules:
    - task_complexity: "high"
      prefer: "groq"
    - task_complexity: "medium"
      prefer: "local"
    - task_complexity: "low"
      prefer: "openrouter"
```

## Implementation Components

### 1. Multi-Backend LLM Manager

```python
# src/llm/multi_backend_manager.py
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import agentlightning as agl
from openai import AsyncOpenAI

@dataclass
class BackendConfig:
    name: str
    type: str
    endpoint: str
    api_key: Optional[str]
    models: List[Dict[str, Any]]
    enabled: bool = True

class MultiBackendLLMManager:
    """Manages multiple LLM backends in a hybrid configuration."""
    
    def __init__(self, config_path: str = "config/model_backends.yaml"):
        self.backends: Dict[str, BackendConfig] = {}
        self.load_config(config_path)
        self.clients: Dict[str, AsyncOpenAI] = {}
        self._initialize_clients()
    
    def load_config(self, config_path: str) -> None:
        """Load backend configurations from YAML file."""
        import yaml
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        for name, backend_config in config['model_backends'].items():
            if backend_config.get('enabled', True):
                # Resolve environment variables in API keys
                api_key = backend_config.get('api_key', '')
                if api_key.startswith('${') and api_key.endswith('}'):
                    env_var = api_key[2:-1]
                    api_key = os.getenv(env_var)
                
                self.backends[name] = BackendConfig(
                    name=name,
                    type=backend_config['type'],
                    endpoint=backend_config['endpoint'],
                    api_key=api_key,
                    models=backend_config['models']
                )
    
    def _initialize_clients(self) -> None:
        """Initialize OpenAI-compatible clients for each backend."""
        for name, backend in self.backends.items():
            self.clients[name] = AsyncOpenAI(
                base_url=backend.endpoint,
                api_key=backend.api_key or "dummy"
            )
    
    def get_backend_for_task(self, task_type: str, strategy: str = "cost_optimized") -> str:
        """Select the best backend for a given task type."""
        # Find backends that support this task type
        suitable_backends = []
        for name, backend in self.backends.items():
            for model in backend.models:
                if task_type in model.get('task_types', []):
                    suitable_backends.append(name)
                    break
        
        if not suitable_backends:
            # Fallback to first available backend
            return list(self.backends.keys())[0]
        
        # Apply routing strategy
        if strategy == "cost_optimized":
            # Prefer free/local models
            priority = ["local", "openrouter", "groq"]
        elif strategy == "latency_optimized":
            # Prefer fast models
            priority = ["groq", "local", "openrouter"]
        elif strategy == "quality_optimized":
            # Prefer powerful models
            priority = ["groq", "local", "openrouter"]
        else:
            priority = suitable_backends
        
        for backend_name in priority:
            if backend_name in suitable_backends:
                return backend_name
        
        return suitable_backends[0]
    
    def get_llm_resource(
        self, 
        task_type: str, 
        model_name: Optional[str] = None,
        backend: Optional[str] = None
    ) -> agl.LLM:
        """Get an Agent Lightning LLM resource for the specified task."""
        if backend is None:
            backend = self.get_backend_for_task(task_type)
        
        backend_config = self.backends[backend]
        
        # If model not specified, use first model for this task type
        if model_name is None:
            for model in backend_config.models:
                if task_type in model.get('task_types', []):
                    model_name = model['name']
                    break
        
        if model_name is None:
            model_name = backend_config.models[0]['name']
        
        return agl.LLM(
            endpoint=backend_config.endpoint,
            model=model_name,
            api_key=backend_config.api_key,
            sampling_parameters={
                "temperature": 0.7,
                "max_tokens": 2048
            }
        )
    
    def get_client(self, backend: str) -> AsyncOpenAI:
        """Get the OpenAI client for a specific backend."""
        return self.clients[backend]
```

### 2. Agent Lightning Integration

```python
# src/llm/agent_lightning_trainer.py
import agentlightning as agl
from typing import Any, Dict, List, Optional
from multi_backend_manager import MultiBackendLLMManager

class AgentTrainer:
    """Integrates Agent Lightning training with our multi-backend system."""
    
    def __init__(self, backend_manager: MultiBackendLLMManager):
        self.backend_manager = backend_manager
        self.store: Optional[agl.LightningStore] = None
        self.trainer: Optional[agl.Trainer] = None
    
    async def setup_training(
        self,
        algorithm_type: str = "grpo",  # or "apo", "ppo"
        n_runners: int = 4,
        use_external_store: bool = False,
        store_address: Optional[str] = None
    ) -> None:
        """Setup Agent Lightning training infrastructure."""
        
        # Setup store
        if use_external_store and store_address:
            # Connect to external store
            self.store = agl.RemoteLightningStore(store_address)
        else:
            # Use in-memory store
            self.store = agl.InMemoryLightningStore()
        
        # Configure algorithm
        if algorithm_type == "grpo":
            algorithm = self._create_grpo_algorithm()
        elif algorithm_type == "apo":
            algorithm = self._create_apo_algorithm()
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm_type}")
        
        # Get initial LLM resources
        initial_resources = {
            "main_llm": self.backend_manager.get_llm_resource("code_generation"),
            "critic_llm": self.backend_manager.get_llm_resource("code_review"),
        }
        
        # Create trainer
        self.trainer = agl.Trainer(
            algorithm=algorithm,
            n_runners=n_runners,
            initial_resources=initial_resources,
            store=self.store
        )
    
    def _create_grpo_algorithm(self) -> Dict[str, Any]:
        """Create GRPO (Generalized Reinforcement Policy Optimization) config."""
        return {
            "algorithm": {
                "adv_estimator": "grpo",
                "use_kl_in_reward": False,
            },
            "data": {
                "train_batch_size": 16,
                "max_prompt_length": 4096,
                "max_response_length": 2048,
            },
            "actor_rollout_ref": {
                "rollout": {
                    "tensor_model_parallel_size": 1,
                    "n": 4,
                    "log_prob_micro_batch_size_per_gpu": 4,
                    "multi_turn": {"format": "hermes"},
                    "name": "vllm",
                    "gpu_memory_utilization": 0.6,
                },
                "actor": {
                    "ppo_mini_batch_size": 16,
                    "ppo_micro_batch_size_per_gpu": 4,
                    "optim": {"lr": 1e-6},
                }
            }
        }
    
    def _create_apo_algorithm(self) -> agl.Algorithm:
        """Create APO (Automatic Prompt Optimization) algorithm."""
        from openai import AsyncOpenAI
        
        # Use Groq for APO (fast inference needed)
        groq_client = self.backend_manager.get_client("groq")
        
        return agl.algorithm.APO(
            groq_client,
            gradient_model="llama-3.3-70b-versatile",
            apply_edit_model="llama-3.3-70b-versatile",
            val_batch_size=16,
            gradient_batch_size=4,
            beam_width=2,
            branch_factor=2,
            beam_rounds=2
        )
    
    async def train_agent(
        self,
        agent: Any,
        train_dataset: List[Any],
        val_dataset: Optional[List[Any]] = None
    ) -> None:
        """Train an agent with Agent Lightning."""
        if self.trainer is None:
            raise RuntimeError("Trainer not setup. Call setup_training() first.")
        
        self.trainer.fit(
            agent=agent,
            train_dataset=train_dataset,
            val_dataset=val_dataset
        )
```

### 3. Hybrid Routing with Fallback

```python
# src/llm/hybrid_router.py
from typing import Optional, List, Dict, Any
import asyncio
from openai import AsyncOpenAI
import logging

logger = logging.getLogger(__name__)

class HybridRouter:
    """Routes requests to appropriate backends with fallback support."""
    
    def __init__(self, backend_manager):
        self.backend_manager = backend_manager
        self.fallback_order = ["local", "groq", "openrouter"]
    
    async def generate_with_fallback(
        self,
        task_type: str,
        messages: List[Dict[str, str]],
        max_retries: int = 3,
        timeout: float = 60.0
    ) -> Optional[str]:
        """
        Generate completion with automatic fallback.
        
        Tries backends in order until one succeeds.
        """
        errors = []
        
        for backend_name in self.fallback_order:
            if backend_name not in self.backend_manager.backends:
                continue
            
            try:
                logger.info(f"Attempting generation with backend: {backend_name}")
                
                llm_resource = self.backend_manager.get_llm_resource(
                    task_type=task_type,
                    backend=backend_name
                )
                
                client = self.backend_manager.get_client(backend_name)
                
                # Try with timeout
                response = await asyncio.wait_for(
                    client.chat.completions.create(
                        model=llm_resource.model,
                        messages=messages,
                        temperature=llm_resource.sampling_parameters.get("temperature", 0.7),
                        max_tokens=llm_resource.sampling_parameters.get("max_tokens", 2048)
                    ),
                    timeout=timeout
                )
                
                result = response.choices[0].message.content
                logger.info(f"Successfully generated with backend: {backend_name}")
                return result
                
            except asyncio.TimeoutError:
                error_msg = f"Timeout with backend {backend_name}"
                logger.warning(error_msg)
                errors.append(error_msg)
                continue
                
            except Exception as e:
                error_msg = f"Error with backend {backend_name}: {str(e)}"
                logger.warning(error_msg)
                errors.append(error_msg)
                continue
        
        # All backends failed
        logger.error(f"All backends failed. Errors: {errors}")
        return None
    
    async def parallel_generate(
        self,
        task_type: str,
        messages: List[Dict[str, str]],
        backends: Optional[List[str]] = None,
        return_first: bool = True
    ) -> List[Optional[str]]:
        """
        Generate from multiple backends in parallel.
        
        Args:
            task_type: Type of task for routing
            messages: Chat messages
            backends: Specific backends to use (None = use all)
            return_first: Return immediately when first completes
        
        Returns:
            List of responses from each backend
        """
        if backends is None:
            backends = list(self.backend_manager.backends.keys())
        
        tasks = []
        for backend_name in backends:
            task = self._generate_single(backend_name, task_type, messages)
            tasks.append(task)
        
        if return_first:
            # Return as soon as first completes
            done, pending = await asyncio.wait(
                tasks,
                return_when=asyncio.FIRST_COMPLETED
            )
            # Cancel pending tasks
            for task in pending:
                task.cancel()
            return [task.result() for task in done]
        else:
            # Wait for all
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return [r if not isinstance(r, Exception) else None for r in results]
    
    async def _generate_single(
        self,
        backend_name: str,
        task_type: str,
        messages: List[Dict[str, str]]
    ) -> Optional[str]:
        """Generate from a single backend."""
        try:
            llm_resource = self.backend_manager.get_llm_resource(
                task_type=task_type,
                backend=backend_name
            )
            
            client = self.backend_manager.get_client(backend_name)
            
            response = await client.chat.completions.create(
                model=llm_resource.model,
                messages=messages,
                temperature=llm_resource.sampling_parameters.get("temperature", 0.7),
                max_tokens=llm_resource.sampling_parameters.get("max_tokens", 2048)
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error in {backend_name}: {str(e)}")
            return None
```

### 4. Integration with Existing System

```python
# src/agents/enhanced_agent.py
import agentlightning as agl
from typing import Any, Dict

@agl.rollout
async def code_generation_agent(task: Dict[str, Any], llm: agl.LLM) -> float:
    """
    Agent Lightning compatible agent for code generation.
    
    This function is decorated with @agl.rollout to enable:
    - Automatic trace collection
    - Reward signal tracking
    - Integration with training algorithms
    """
    from openai import AsyncOpenAI
    
    client = AsyncOpenAI(
        base_url=llm.endpoint,
        api_key=llm.api_key or "dummy"
    )
    
    # Extract task details
    description = task.get("description", "")
    requirements = task.get("requirements", "")
    
    # Generate code
    response = await client.chat.completions.create(
        model=llm.model,
        messages=[
            {"role": "system", "content": "You are an expert code generator."},
            {"role": "user", "content": f"Description: {description}\nRequirements: {requirements}"}
        ],
        temperature=llm.sampling_parameters.get("temperature", 0.7),
        max_tokens=llm.sampling_parameters.get("max_tokens", 2048)
    )
    
    generated_code = response.choices[0].message.content
    
    # Validate and calculate reward
    reward = await calculate_code_quality(generated_code, task)
    
    return reward

async def calculate_code_quality(code: str, task: Dict[str, Any]) -> float:
    """Calculate reward signal for code generation."""
    # Implement your reward calculation logic
    # Could include: syntax checking, test pass rate, style compliance, etc.
    reward = 0.0
    
    # Example: syntax check
    try:
        compile(code, '<string>', 'exec')
        reward += 0.3
    except SyntaxError:
        pass
    
    # Add more validation logic...
    
    return reward
```

## Usage Examples

### 1. Training with Hybrid Backends

```python
# examples/train_with_hybrid.py
import asyncio
from src.llm.multi_backend_manager import MultiBackendLLMManager
from src.llm.agent_lightning_trainer import AgentTrainer
from src.agents.enhanced_agent import code_generation_agent

async def main():
    # Initialize multi-backend manager
    backend_manager = MultiBackendLLMManager("config/model_backends.yaml")
    
    # Setup trainer
    trainer = AgentTrainer(backend_manager)
    await trainer.setup_training(
        algorithm_type="grpo",
        n_runners=4
    )
    
    # Prepare training data
    train_dataset = [
        {"description": "Create a function to sort a list", "requirements": "Use quicksort"},
        # ... more tasks
    ]
    
    # Train the agent
    await trainer.train_agent(
        agent=code_generation_agent,
        train_dataset=train_dataset
    )

if __name__ == "__main__":
    asyncio.run(main())
```

### 2. Using Hybrid Router for Generation

```python
# examples/use_hybrid_router.py
import asyncio
from src.llm.multi_backend_manager import MultiBackendLLMManager
from src.llm.hybrid_router import HybridRouter

async def main():
    backend_manager = MultiBackendLLMManager("config/model_backends.yaml")
    router = HybridRouter(backend_manager)
    
    messages = [
        {"role": "user", "content": "Write a Python function to calculate fibonacci numbers"}
    ]
    
    # Generate with automatic fallback
    result = await router.generate_with_fallback(
        task_type="code_generation",
        messages=messages
    )
    
    print(f"Generated code:\n{result}")

if __name__ == "__main__":
    asyncio.run(main())
```

### 3. Parallel Generation for Consensus

```python
# examples/parallel_consensus.py
import asyncio
from src.llm.multi_backend_manager import MultiBackendLLMManager
from src.llm.hybrid_router import HybridRouter

async def main():
    backend_manager = MultiBackendLLMManager("config/model_backends.yaml")
    router = HybridRouter(backend_manager)
    
    messages = [
        {"role": "user", "content": "Review this code for bugs: def add(a,b): return a+b"}
    ]
    
    # Get responses from all backends
    results = await router.parallel_generate(
        task_type="code_review",
        messages=messages,
        return_first=False
    )
    
    # Implement consensus logic
    print(f"Received {len([r for r in results if r])} responses")
    for i, result in enumerate(results):
        if result:
            print(f"\nBackend {i}:\n{result}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Environment Setup

Create a `.env` file:

```bash
# OpenRouter (Free Tier)
OPENROUTER_API_KEY=your_openrouter_key_here

# Groq Cloud
GROQ_API_KEY=your_groq_key_here

# Optional: OpenAI for testing
OPENAI_API_KEY=your_openai_key_here

# Local vLLM (if using)
VLLM_ENDPOINT=http://localhost:8000/v1

# Agent Lightning Store (optional)
AGL_STORE_ADDRESS=http://localhost:4747

# Weights & Biases (optional)
WANDB_API_KEY=your_wandb_key_here
```

## Best Practices

### 1. Cost Optimization
- Use local models for high-volume, low-complexity tasks
- Route complex reasoning to Groq (fast inference)
- Use OpenRouter free tier for diversity and experimentation

### 2. Latency Optimization
- Prefer Groq for production critical paths
- Use parallel generation with `return_first=True` for speed
- Cache responses when appropriate

### 3. Quality Optimization
- Use ensemble methods with multiple backends
- Implement voting/consensus mechanisms
- Fine-tune local models with Agent Lightning

### 4. Reliability
- Always configure fallback chains
- Implement timeouts and retries
- Monitor backend availability

## Next Steps

1. **Setup Configuration**: Create `config/model_backends.yaml` with your API keys
2. **Test Backends**: Verify each backend works independently
3. **Integrate Agents**: Update existing agents to use `@agl.rollout` decorator
4. **Define Rewards**: Implement reward functions for your use cases
5. **Start Training**: Run training loops with GRPO or APO
6. **Monitor & Iterate**: Track metrics and refine configurations

## Resources

- [Agent Lightning Documentation](https://microsoft.github.io/agent-lightning/)
- [OpenRouter Free Models](https://openrouter.ai/models?max_price=0)
- [Groq Cloud Documentation](https://console.groq.com/docs)
- [vLLM Documentation](https://docs.vllm.ai/)

## Troubleshooting

### Issue: Backend Timeout
**Solution**: Increase timeout values or reduce max_tokens

### Issue: API Rate Limits
**Solution**: Implement rate limiting or use multiple backends in parallel

### Issue: Out of Memory (Local)
**Solution**: Reduce `gpu_memory_utilization` or use smaller models

### Issue: Training Not Converging
**Solution**: Adjust learning rate, batch size, or reward function
