"""Quick test of parallel generation with local models."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.llm.hybrid_router import HybridRouter
from src.llm.multi_backend_manager import MultiBackendLLMManager


async def test_local_parallel():
    """Test parallel generation with local Ollama models."""
    print("\n" + "="*80)
    print("Testing Parallel Generation with Local Models")
    print("="*80 + "\n")
    
    # Initialize
    backend_manager = MultiBackendLLMManager()
    router = HybridRouter(backend_manager)
    
    # Simple test prompt
    messages = [
        {"role": "user", "content": "Write a one-line Python function that adds two numbers."}
    ]
    
    # Use Groq models (fast, reliable - OpenRouter free tier has rate limits)
    models = [
        "groq/llama-3.1-8b-instant",
        "groq/llama-3.3-70b-versatile"
    ]
    
    print(f"🚀 Generating with {len(models)} models in parallel...")
    print(f"Models: {models}\n")
    
    try:
        # Test parallel generation (cloud APIs are fast)
        result, metadata = await router.parallel_generate_with_consensus(
            messages=messages,
            models=models,
            task_type="code_generation",
            timeout=30.0
        )
        
        print("✅ SUCCESS!")
        print(f"\nBest Model: {metadata.get('best_model', 'unknown')}")
        best_score = metadata.get('best_score', 0)
        if isinstance(best_score, (int, float)):
            print(f"Quality Score: {best_score:.3f}")
        else:
            print(f"Quality Score: {best_score}")
        
        print(f"\nSuccessful Models: {metadata.get('successful_models', [])}")
        print(f"Failed Models: {metadata.get('failed_models', [])}")
        
        print(f"\n" + "-"*80)
        print("Selected Response:")
        print("-"*80)
        print(result.content)
        print("-"*80)
        
        return True
        
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_local_parallel())
    print(f"\n{'='*80}")
    print(f"Test Result: {'✅ PASSED' if success else '❌ FAILED'}")
    print(f"{'='*80}\n")
    sys.exit(0 if success else 1)
