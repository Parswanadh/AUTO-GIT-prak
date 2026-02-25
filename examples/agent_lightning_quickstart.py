"""
Quick Start Example: Agent Lightning with Hybrid Backends

This example demonstrates how to use the hybrid backend system with Agent Lightning
for training AI agents using local models, OpenRouter API, and Groq Cloud.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.llm.multi_backend_manager import MultiBackendLLMManager
from src.llm.hybrid_router import HybridRouter
import agentlightning as agl

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ===== EXAMPLE 1: Simple Generation with Fallback =====

async def example_simple_generation():
    """Example: Simple text generation with automatic fallback."""
    print("\n" + "="*60)
    print("EXAMPLE 1: Simple Generation with Fallback")
    print("="*60)
    
    # Initialize backend manager
    manager = MultiBackendLLMManager("config/model_backends.yaml")
    router = HybridRouter(manager)
    
    # Create a simple prompt
    messages = [
        {"role": "user", "content": "Write a Python function to calculate factorial"}
    ]
    
    # Generate with automatic fallback
    result = await router.generate_with_fallback(
        task_type="code_generation",
        messages=messages,
        max_retries=3,
        timeout=30.0
    )
    
    if result and result.success:
        print(f"\n✓ Generated code:")
        print(f"  Backend: {result.backend}")
        print(f"  Model: {result.model}")
        print(f"  Latency: {result.latency:.2f}s")
        print(f"  Tokens: {result.tokens}")
        print(f"\nCode:\n{result.content}")
    else:
        print(f"✗ Generation failed: {result.error if result else 'No result'}")


# ===== EXAMPLE 2: Parallel Generation for Consensus =====

async def example_parallel_consensus():
    """Example: Generate from multiple backends and find consensus."""
    print("\n" + "="*60)
    print("EXAMPLE 2: Parallel Generation for Consensus")
    print("="*60)
    
    manager = MultiBackendLLMManager("config/model_backends.yaml")
    router = HybridRouter(manager)
    
    messages = [
        {"role": "user", "content": "Is Python a compiled or interpreted language?"}
    ]
    
    # Generate from all backends in parallel
    results = await router.parallel_generate(
        task_type="general",
        messages=messages,
        return_first=False,
        timeout=30.0
    )
    
    print(f"\nReceived {len(results)} responses:")
    for i, result in enumerate(results, 1):
        if result.success:
            print(f"\n{i}. {result.backend} ({result.model}):")
            print(f"   {result.content[:100]}...")
            print(f"   Latency: {result.latency:.2f}s")
        else:
            print(f"\n{i}. {result.backend}: Failed - {result.error}")


# ===== EXAMPLE 3: Agent Lightning Training =====

@agl.rollout
async def code_quality_agent(task: dict, llm: agl.LLM) -> float:
    """
    Agent that generates code and returns a quality score.
    
    This is compatible with Agent Lightning's training system.
    """
    from openai import AsyncOpenAI
    
    client = AsyncOpenAI(
        base_url=llm.endpoint,
        api_key=llm.api_key or "dummy"
    )
    
    # Get task details
    description = task.get("description", "")
    requirements = task.get("requirements", "")
    
    # Generate code
    response = await client.chat.completions.create(
        model=llm.model,
        messages=[
            {
                "role": "system",
                "content": "You are an expert Python developer. Write clean, efficient, well-documented code."
            },
            {
                "role": "user",
                "content": f"Task: {description}\nRequirements: {requirements}\n\nGenerate Python code:"
            }
        ],
        temperature=llm.sampling_parameters.get("temperature", 0.7),
        max_tokens=llm.sampling_parameters.get("max_tokens", 2048)
    )
    
    code = response.choices[0].message.content or ""
    
    # Calculate reward based on code quality
    reward = calculate_code_reward(code, task)
    
    logger.info(f"Generated code with reward: {reward:.2f}")
    return reward


def calculate_code_reward(code: str, task: dict) -> float:
    """
    Calculate reward for generated code.
    
    This is a simple example - you can make this much more sophisticated.
    """
    reward = 0.0
    
    # Check if code is not empty
    if code and len(code) > 10:
        reward += 0.2
    
    # Check for Python syntax validity
    try:
        compile(code, '<string>', 'exec')
        reward += 0.3
    except SyntaxError:
        pass
    
    # Check for docstrings
    if '"""' in code or "'''" in code:
        reward += 0.1
    
    # Check for function definition
    if 'def ' in code:
        reward += 0.2
    
    # Check for type hints (modern Python)
    if '->' in code or ':' in code:
        reward += 0.1
    
    # Check for comments
    if '#' in code:
        reward += 0.1
    
    return min(reward, 1.0)  # Cap at 1.0


async def example_agent_training():
    """Example: Train an agent using Agent Lightning."""
    print("\n" + "="*60)
    print("EXAMPLE 3: Agent Lightning Training")
    print("="*60)
    
    # Initialize backend manager
    manager = MultiBackendLLMManager("config/model_backends.yaml")
    
    # Get LLM resource for code generation
    llm_resource = manager.get_llm_resource(
        task_type="code_generation",
        backend="local"  # Use local model for training
    )
    
    print(f"\nUsing model: {llm_resource.model}")
    print(f"Endpoint: {llm_resource.endpoint}")
    
    # Create training dataset
    train_dataset = [
        {
            "description": "Calculate factorial",
            "requirements": "Use recursion, handle negative numbers"
        },
        {
            "description": "Sort a list",
            "requirements": "Implement quicksort algorithm"
        },
        {
            "description": "Binary search",
            "requirements": "Return index of element, -1 if not found"
        },
        {
            "description": "FizzBuzz",
            "requirements": "Print numbers 1-100, Fizz for multiples of 3, Buzz for 5, FizzBuzz for both"
        }
    ]
    
    # Create validation dataset
    val_dataset = [
        {
            "description": "Fibonacci sequence",
            "requirements": "Generate first n numbers"
        }
    ]
    
    print(f"\nTraining dataset: {len(train_dataset)} tasks")
    print(f"Validation dataset: {len(val_dataset)} tasks")
    
    # Setup in-memory store
    store = agl.InMemoryLightningStore()
    
    # Create trainer
    trainer = agl.Trainer(
        n_runners=2,  # Use 2 parallel workers
        initial_resources={"llm": llm_resource},
        store=store
    )
    
    print("\nStarting training... (Note: This is a demo, set n_runners and epochs higher for real training)")
    
    # Note: This will actually try to train. In a real setup, you'd want:
    # 1. A local vLLM server running
    # 2. Proper GRPO/APO algorithm configured
    # 3. More training data
    # 4. Longer training time
    
    # For demo purposes, just run a few iterations
    try:
        trainer.dev(code_quality_agent, train_dataset[:2])  # Just 2 tasks for demo
        print("\n✓ Training demo completed!")
    except Exception as e:
        print(f"\n✗ Training error (expected if no local server): {e}")
        print("   To actually train, start a vLLM server first:")
        print("   vllm serve Qwen/Qwen2.5-7B-Instruct --port 8000")


# ===== EXAMPLE 4: Hybrid Model Selection =====

async def example_smart_routing():
    """Example: Intelligent routing based on task complexity."""
    print("\n" + "="*60)
    print("EXAMPLE 4: Smart Routing Based on Task Type")
    print("="*60)
    
    manager = MultiBackendLLMManager("config/model_backends.yaml")
    
    # Different task types
    tasks = [
        ("code_generation", "Generate a sorting algorithm"),
        ("analysis", "Analyze this code for bugs"),
        ("simple_tasks", "What is 2+2?"),
        ("complex_reasoning", "Explain quantum computing to a 5-year-old"),
    ]
    
    for task_type, description in tasks:
        backend = manager.get_backend_for_task(task_type)
        model = manager.get_model_for_task(task_type)
        
        print(f"\nTask: {task_type}")
        print(f"  Description: {description}")
        print(f"  → Backend: {backend}")
        print(f"  → Model: {model.name if model else 'N/A'}")


# ===== EXAMPLE 5: Backend Information =====

def example_backend_info():
    """Example: Display information about all configured backends."""
    print("\n" + "="*60)
    print("EXAMPLE 5: Backend Configuration")
    print("="*60)
    
    manager = MultiBackendLLMManager("config/model_backends.yaml")
    
    print(f"\nConfigured backends: {len(manager.get_all_backends())}")
    
    for backend_name in manager.get_all_backends():
        info = manager.get_backend_info(backend_name)
        
        print(f"\n{backend_name.upper()}:")
        print(f"  Type: {info['type']}")
        print(f"  Endpoint: {info['endpoint']}")
        print(f"  Priority: {info['priority']}")
        print(f"  Models ({len(info['models'])}):")
        
        for model in info['models']:
            print(f"    • {model['name']}")
            print(f"      Task types: {', '.join(model['task_types'])}")
            print(f"      Max tokens: {model['max_tokens']}")
    
    # Show routing statistics
    print("\n" + "-"*60)
    print("Fallback order:", manager.get_fallback_order())


# ===== MAIN =====

async def main():
    """Run all examples."""
    print("\n" + "="*60)
    print("Agent Lightning + Hybrid Backends - Quick Start")
    print("="*60)
    
    try:
        # Example 1: Simple generation
        await example_simple_generation()
        
        # Example 2: Parallel consensus (may fail if no backends available)
        # await example_parallel_consensus()
        
        # Example 3: Agent training (will fail if no local server)
        # await example_agent_training()
        
        # Example 4: Smart routing
        await example_smart_routing()
        
        # Example 5: Backend info
        example_backend_info()
        
    except Exception as e:
        logger.error(f"Error running examples: {e}", exc_info=True)
    
    print("\n" + "="*60)
    print("Quick start completed!")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
