"""Debug test to find where the hang occurs."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

print("1. Starting imports...")

print("2. Importing MultiBackendLLMManager...")
from src.llm.multi_backend_manager import MultiBackendLLMManager

print("3. Importing HybridRouter...")
from src.llm.hybrid_router import HybridRouter

print("4. Creating backend manager...")
backend_manager = MultiBackendLLMManager()

print("5. Creating router...")
router = HybridRouter(backend_manager)

print("6. ✅ All initialized successfully!")
print("7. Backend manager has backends:", list(backend_manager.backends.keys()) if hasattr(backend_manager, 'backends') else "No backends attribute")

print("\n✅ SUCCESS - No hang detected!")
