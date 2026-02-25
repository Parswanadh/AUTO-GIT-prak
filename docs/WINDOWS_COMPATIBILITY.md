# Agent Lightning Windows Compatibility Note

## Issue: fcntl Module Not Available on Windows

Agent Lightning has a dependency on the `fcntl` module, which is Unix-only and not available on Windows by default. This is a known limitation.

## Solutions

### Option 1: Use WSL (Windows Subsystem for Linux) - RECOMMENDED

This is the best solution for Windows users:

1. **Install WSL**:
```powershell
wsl --install
```

2. **Install Python in WSL**:
```bash
sudo apt update
sudo apt install python3.11 python3.11-pip python3.11-venv
```

3. **Setup your project in WSL**:
```bash
cd /mnt/d/Projects/auto-git
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

4. **Run Agent Lightning**:
```bash
python examples/agent_lightning_quickstart.py
```

### Option 2: Use Docker

Use Docker to run Agent Lightning in a Linux container:

1. **Create Dockerfile**:
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
CMD ["python", "examples/agent_lightning_quickstart.py"]
```

2. **Build and run**:
```bash
docker build -t agent-lightning .
docker run -it --rm agent-lightning
```

### Option 3: Use GitHub Codespaces or Cloud IDE

Run your code in a cloud Linux environment:
- GitHub Codespaces
- Replit
- Google Colab (with modifications)

### Option 4: Use Only the Hybrid Router (Without Training)

You can still use the multi-backend system without Agent Lightning training features:

```python
# This works on Windows!
from src.llm.multi_backend_manager import MultiBackendLLMManager
from src.llm.hybrid_router import HybridRouter

# Note: Skip agentlightning import
# Just use the routing and fallback features

async def main():
    manager = MultiBackendLLMManager()
    router = HybridRouter(manager)
    
    # Use for generation (works on Windows)
    result = await router.generate_with_fallback(
        task_type="code_generation",
        messages=[{"role": "user", "content": "Write code"}]
    )
```

### Option 5: Mock fcntl (For Development Only)

Create a mock `fcntl` module (NOT for production):

```python
# mock_fcntl.py
import sys
from unittest.mock import MagicMock

sys.modules['fcntl'] = MagicMock()
```

Then import before agentlightning:
```python
import mock_fcntl  # Import this first
import agentlightning as agl
```

## Recommended Approach

For **development on Windows**:
1. Use WSL2 for Agent Lightning training features
2. Use native Windows for routing/API features only

For **production deployment**:
1. Use Linux servers (AWS, Azure, GCP)
2. Use Docker containers
3. Use Kubernetes for scaling

## What Works on Windows Without Agent Lightning

Even without Agent Lightning, you still get:
- ✅ Multi-backend routing (local, OpenRouter, Groq)
- ✅ Automatic fallback
- ✅ Parallel generation
- ✅ Consensus mechanisms
- ✅ Cost optimization
- ✅ Statistics tracking

What requires Linux (via WSL/Docker):
- ❌ Agent Lightning training (GRPO, APO)
- ❌ LoRA fine-tuning
- ❌ Distributed training

## Quick Test on Windows

Test the routing system (which works on Windows):

```python
# test_windows_routing.py
import asyncio
import sys
sys.path.insert(0, '.')

from src.llm.multi_backend_manager import MultiBackendLLMManager
from src.llm.hybrid_router import HybridRouter

async def test():
    manager = MultiBackendLLMManager("config/model_backends.yaml")
    router = HybridRouter(manager)
    
    print("Backends:", manager.get_all_backends())
    
    # Test routing
    messages = [{"role": "user", "content": "Hello"}]
    result = await router.generate_with_fallback(
        task_type="general",
        messages=messages
    )
    
    if result and result.success:
        print(f"✓ Success: {result.content[:100]}")
    else:
        print(f"✗ Failed: {result.error if result else 'No result'}")

asyncio.run(test())
```

## GitHub Issue

This is a known issue tracked in Agent Lightning repository:
- https://github.com/microsoft/agent-lightning/issues

## Alternative: Use OpenAI SDK Directly for Training

If you need RL training on Windows, consider alternatives:
- OpenAI's fine-tuning API
- Hugging Face TRL library
- Ray RLlib (with modifications)

## Summary

- **For Windows users**: Use WSL2 or Docker for full Agent Lightning features
- **For routing only**: Native Windows works fine
- **For production**: Use Linux servers anyway (better performance)

The hybrid routing system (our main contribution) works perfectly on Windows! 🎉
