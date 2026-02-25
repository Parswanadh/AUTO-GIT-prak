"""Simple synchronous test to check if backends are accessible."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.llm.multi_backend_manager import MultiBackendLLMManager

print("\n" + "="*80)
print("Testing Backend Initialization")
print("="*80 + "\n")

try:
    manager = MultiBackendLLMManager()
    print("✅ Backend manager initialized")
    
    # Check available backends
    print("\n📋 Checking available backends...")
    
    # Try to get Groq client
    try:
        groq_client = manager.get_client("groq")
        print("✅ Groq backend accessible")
    except Exception as e:
        print(f"❌ Groq backend failed: {e}")
    
    # Try to get OpenRouter client
    try:
        or_client = manager.get_client("openrouter")
        print("✅ OpenRouter backend accessible")
    except Exception as e:
        print(f"❌ OpenRouter backend failed: {e}")
    
    # Try to get local client
    try:
        local_client = manager.get_client("local")
        print("✅ Local backend accessible")
    except Exception as e:
        print(f"❌ Local backend failed: {e}")
    
    print("\n" + "="*80)
    print("✅ Test completed successfully")
    print("="*80)
    
except Exception as e:
    print(f"❌ Failed to initialize: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
