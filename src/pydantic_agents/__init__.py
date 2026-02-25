"""
Pydantic AI Agents Module
==========================

Modern agent framework using Pydantic AI for type-safe, observable LLM interactions.

Key Benefits:
- Direct Ollama integration (no LangChain wrapper)
- Automatic distributed tracing via Logfire
- Type-safe structured outputs
- Built-in error handling and retries

Usage:
    from src.pydantic_agents import CodeGeneratorAgent
    
    agent = CodeGeneratorAgent()
    result = await agent.generate("Create a REST API endpoint")
"""

__version__ = "1.0.0"
__author__ = "Auto-Git Team"

from .base_agent import BaseAgent
from .code_generator import CodeGeneratorAgent
from .code_reviewer import CodeReviewerAgent
from .model_selector import ModelSelectorAgent

__all__ = [
    "BaseAgent",
    "CodeGeneratorAgent",
    "CodeReviewerAgent",
    "ModelSelectorAgent",
]
