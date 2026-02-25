"""
LLM Module - Multi-Backend Management and Routing

This module provides unified access to multiple LLM backends:
- Local models (vLLM)
- OpenRouter API (free tier)
- Groq Cloud (fast inference)

Features:
- Intelligent routing based on task type
- Automatic fallback on errors
- Parallel execution for consensus
- Cost optimization
- Integration with Agent Lightning
"""

from .multi_backend_manager import (
    MultiBackendLLMManager,
    BackendConfig,
    ModelInfo,
    get_backend_manager
)

from .hybrid_router import (
    HybridRouter,
    GenerationResult,
    consensus_generate
)

__all__ = [
    # Backend Manager
    'MultiBackendLLMManager',
    'BackendConfig',
    'ModelInfo',
    'get_backend_manager',
    
    # Router
    'HybridRouter',
    'GenerationResult',
    'consensus_generate',
]

__version__ = '1.0.0'
