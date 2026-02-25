"""
Multi-Backend LLM Manager for Hybrid AI System

This module manages multiple LLM backends (local, OpenRouter, Groq) in a unified interface,
providing intelligent routing, fallback, and load balancing capabilities.
"""

import os
import yaml
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Try to import agentlightning (optional, may not work on Windows)
try:
    import agentlightning as agl
    AGL_AVAILABLE = True
except ImportError as e:
    AGL_AVAILABLE = False
    agl = None  # type: ignore
    logging.warning(f"Agent Lightning not available: {e}")
    logging.warning("Training features disabled. Routing and fallback still work.")

logger = logging.getLogger(__name__)


@dataclass
class ModelInfo:
    """Information about a specific model."""
    name: str
    task_types: List[str]
    max_tokens: int = 4096
    temperature: float = 0.7


@dataclass
class BackendConfig:
    """Configuration for a backend provider."""
    name: str
    type: str
    endpoint: str
    api_key: Optional[str]
    models: List[ModelInfo]
    enabled: bool = True
    priority: int = 1


class MultiBackendLLMManager:
    """
    Manages multiple LLM backends in a hybrid configuration.
    
    Supports:
    - Local models (vLLM)
    - OpenRouter API (free tier models)
    - Groq Cloud API (fast inference)
    
    Features:
    - Intelligent routing based on task type
    - Automatic fallback on errors
    - Load balancing across backends
    - Cost optimization
    """
    
    def __init__(self, config_path: str = "config/model_backends.yaml"):
        """
        Initialize the multi-backend manager.
        
        Args:
            config_path: Path to YAML configuration file
        """
        self.backends: Dict[str, BackendConfig] = {}
        self.clients: Dict[str, AsyncOpenAI] = {}
        self.config = None
        self.config_path = config_path
        
        self.load_config(config_path)
        self._initialize_clients()
        
        logger.info(f"Initialized {len(self.backends)} backends: {list(self.backends.keys())}")
    
    def load_config(self, config_path: str) -> None:
        """
        Load backend configurations from YAML file.
        
        Args:
            config_path: Path to configuration file
        """
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Parse backend configurations
        for name, backend_config in self.config['model_backends'].items():
            if not backend_config.get('enabled', True):
                logger.info(f"Backend {name} is disabled, skipping")
                continue
            
            # Resolve environment variables in API keys
            api_key = backend_config.get('api_key', '')
            if api_key and api_key.startswith('${') and api_key.endswith('}'):
                env_var = api_key[2:-1]
                api_key = os.getenv(env_var)
                if not api_key:
                    logger.warning(f"API key not found for {name}: {env_var}")
            
            # Parse model configurations
            models = []
            for model_config in backend_config.get('models', []):
                models.append(ModelInfo(
                    name=model_config['name'],
                    task_types=model_config.get('task_types', []),
                    max_tokens=model_config.get('max_tokens', 4096),
                    temperature=model_config.get('temperature', 0.7)
                ))
            
            self.backends[name] = BackendConfig(
                name=name,
                type=backend_config['type'],
                endpoint=backend_config['endpoint'],
                api_key=api_key,
                models=models,
                enabled=backend_config.get('enabled', True),
                priority=backend_config.get('priority', 1)
            )
    
    def _initialize_clients(self) -> None:
        """Initialize OpenAI-compatible clients for each backend."""
        for name, backend in self.backends.items():
            try:
                self.clients[name] = AsyncOpenAI(
                    base_url=backend.endpoint,
                    api_key=backend.api_key or "dummy",
                    timeout=60.0
                )
                logger.info(f"Initialized client for backend: {name}")
            except Exception as e:
                logger.error(f"Failed to initialize client for {name}: {e}")
    
    def get_backend_for_task(
        self, 
        task_type: str, 
        strategy: Optional[str] = None
    ) -> Optional[str]:
        """
        Select the best backend for a given task type.
        
        Args:
            task_type: Type of task (e.g., "code_generation", "analysis")
            strategy: Routing strategy override
        
        Returns:
            Name of selected backend, or None if no suitable backend found
        """
        if strategy is None:
            strategy = self.config.get('hybrid_mode', {}).get('strategy', 'balanced')
        
        # Find backends that support this task type
        suitable_backends = []
        for name, backend in self.backends.items():
            for model in backend.models:
                if task_type in model.task_types:
                    suitable_backends.append((name, backend.priority))
                    break
        
        if not suitable_backends:
            # Fallback to first available backend
            logger.warning(f"No backend found for task type: {task_type}, using first available")
            if self.backends:
                return list(self.backends.keys())[0]
            return None
        
        # Apply routing strategy
        if strategy == "cost_optimized":
            # Prefer free/local models
            priority_order = ["local", "openrouter", "groq"]
        elif strategy == "latency_optimized":
            # Prefer fast models
            priority_order = ["groq", "local", "openrouter"]
        elif strategy == "quality_optimized":
            # Prefer powerful models
            priority_order = ["groq", "local", "openrouter"]
        elif strategy == "balanced":
            # Use priority from config
            suitable_backends.sort(key=lambda x: x[1], reverse=True)
            return suitable_backends[0][0]
        else:
            priority_order = [b[0] for b in suitable_backends]
        
        # Select based on priority
        for backend_name in priority_order:
            if any(b[0] == backend_name for b in suitable_backends):
                return backend_name
        
        return suitable_backends[0][0]
    
    def get_model_for_task(
        self,
        task_type: str,
        backend: Optional[str] = None
    ) -> Optional[ModelInfo]:
        """
        Get the best model for a specific task type.
        
        Args:
            task_type: Type of task
            backend: Specific backend to use (None = auto-select)
        
        Returns:
            ModelInfo object or None
        """
        if backend is None:
            backend = self.get_backend_for_task(task_type)
        
        if backend is None or backend not in self.backends:
            return None
        
        backend_config = self.backends[backend]
        
        # Find first model that supports this task type
        for model in backend_config.models:
            if task_type in model.task_types:
                return model
        
        # Fallback to first model if no specific match
        if backend_config.models:
            return backend_config.models[0]
        
        return None
    
    def get_llm_resource(
        self, 
        task_type: str, 
        model_name: Optional[str] = None,
        backend: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ):
        """
        Get an Agent Lightning LLM resource for the specified task.
        
        Note: Requires Agent Lightning to be installed (Linux/WSL/Docker only)
        
        Args:
            task_type: Type of task
            model_name: Specific model name (None = auto-select)
            backend: Specific backend (None = auto-select)
            temperature: Override temperature
            max_tokens: Override max tokens
        
        Returns:
            Agent Lightning LLM resource (if available)
        """
        if not AGL_AVAILABLE:
            raise RuntimeError(
                "Agent Lightning is not available. "
                "This is expected on Windows. "
                "See docs/WINDOWS_COMPATIBILITY.md for solutions. "
                "For routing/fallback features, use the router directly."
            )
        
        if backend is None:
            backend = self.get_backend_for_task(task_type)
        
        if backend is None:
            raise ValueError(f"No backend available for task type: {task_type}")
        
        backend_config = self.backends[backend]
        
        # Get model info
        if model_name is None:
            model_info = self.get_model_for_task(task_type, backend)
            if model_info is None:
                raise ValueError(f"No model found for task type: {task_type}")
            model_name = model_info.name
            default_temp = model_info.temperature
            default_max_tokens = model_info.max_tokens
        else:
            # Find model info by name
            model_info = None
            for m in backend_config.models:
                if m.name == model_name:
                    model_info = m
                    break
            
            if model_info:
                default_temp = model_info.temperature
                default_max_tokens = model_info.max_tokens
            else:
                default_temp = 0.7
                default_max_tokens = 4096
        
        # Use overrides if provided
        final_temp = temperature if temperature is not None else default_temp
        final_max_tokens = max_tokens if max_tokens is not None else default_max_tokens
        
        return agl.LLM(
            endpoint=backend_config.endpoint,
            model=model_name,
            api_key=backend_config.api_key,
            sampling_parameters={
                "temperature": final_temp,
                "max_tokens": final_max_tokens
            }
        )
    
    def get_client(self, backend: str) -> AsyncOpenAI:
        """
        Get the OpenAI client for a specific backend.
        
        Args:
            backend: Name of backend
        
        Returns:
            AsyncOpenAI client
        """
        if backend not in self.clients:
            raise ValueError(f"Backend not found: {backend}")
        return self.clients[backend]
    
    def get_fallback_order(self) -> List[str]:
        """
        Get the fallback order for backends.
        
        Returns:
            List of backend names in fallback order
        """
        fallback_config = self.config.get('hybrid_mode', {}).get('fallback_order', [])
        # Filter to only enabled backends
        return [b for b in fallback_config if b in self.backends]
    
    def get_all_backends(self) -> List[str]:
        """
        Get list of all enabled backends.
        
        Returns:
            List of backend names
        """
        return list(self.backends.keys())
    
    def list_models(self, backend: Optional[str] = None) -> Dict[str, List[str]]:
        """
        List all available models.
        
        Args:
            backend: Specific backend (None = all backends)
        
        Returns:
            Dictionary mapping backend names to model lists
        """
        if backend:
            if backend not in self.backends:
                return {}
            return {backend: [m.name for m in self.backends[backend].models]}
        
        result = {}
        for name, backend_config in self.backends.items():
            result[name] = [m.name for m in backend_config.models]
        return result
    
    def get_backend_info(self, backend: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a backend.
        
        Args:
            backend: Backend name
        
        Returns:
            Dictionary with backend information
        """
        if backend not in self.backends:
            return None
        
        config = self.backends[backend]
        return {
            "name": config.name,
            "type": config.type,
            "endpoint": config.endpoint,
            "enabled": config.enabled,
            "priority": config.priority,
            "models": [
                {
                    "name": m.name,
                    "task_types": m.task_types,
                    "max_tokens": m.max_tokens,
                    "temperature": m.temperature
                }
                for m in config.models
            ]
        }


# Singleton instance
_manager_instance: Optional[MultiBackendLLMManager] = None


def get_backend_manager(config_path: str = "config/model_backends.yaml") -> MultiBackendLLMManager:
    """
    Get or create the global backend manager instance.
    
    Args:
        config_path: Path to configuration file
    
    Returns:
        MultiBackendLLMManager instance
    """
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = MultiBackendLLMManager(config_path)
    return _manager_instance


if __name__ == "__main__":
    # Test the backend manager
    logging.basicConfig(level=logging.INFO)
    
    manager = MultiBackendLLMManager()
    
    print("\n=== Available Backends ===")
    for backend in manager.get_all_backends():
        info = manager.get_backend_info(backend)
        print(f"\n{backend}:")
        print(f"  Type: {info['type']}")
        print(f"  Endpoint: {info['endpoint']}")
        print(f"  Priority: {info['priority']}")
        print(f"  Models: {len(info['models'])}")
    
    print("\n=== Task Routing ===")
    task_types = ["code_generation", "analysis", "code_review", "planning"]
    for task_type in task_types:
        backend = manager.get_backend_for_task(task_type)
        model = manager.get_model_for_task(task_type)
        print(f"{task_type}: {backend} -> {model.name if model else 'N/A'}")
    
    print("\n=== Agent Lightning Status ===")
    if AGL_AVAILABLE:
        print("✓ Agent Lightning available - training features enabled")
        try:
            llm = manager.get_llm_resource("code_generation")
            print(f"✓ LLM Resource: {llm.model} @ {llm.endpoint}")
        except Exception as e:
            print(f"✗ Error: {e}")
    else:
        print("✗ Agent Lightning not available (expected on Windows)")
        print("  Routing and fallback features still work")
        print("  See docs/WINDOWS_COMPATIBILITY.md for training options")
