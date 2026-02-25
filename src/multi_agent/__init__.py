"""Multi-Agent Parallel Execution Module

Asyncio-based parallel agent coordination for:
- Concurrent code generation
- Parallel critique analysis
- Simultaneous research queries
- Multi-perspective debate
"""

from .coordinator import MultiAgentCoordinator
from .parallel_executor import ParallelExecutor
from .task_distributor import TaskDistributor

__all__ = [
    "MultiAgentCoordinator",
    "ParallelExecutor",
    "TaskDistributor",
]
