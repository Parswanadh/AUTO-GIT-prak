"""Task Distributor - Intelligent task distribution for parallel agents"""

import logging
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """Task priority levels"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Task:
    """Represents a distributed task"""
    task_id: str
    operation: str
    func: Callable
    kwargs: Dict[str, Any]
    priority: TaskPriority = TaskPriority.NORMAL
    estimated_duration: float = 30.0  # seconds
    dependencies: List[str] = None  # Task IDs that must complete first
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


class TaskDistributor:
    """
    Intelligent task distribution for parallel execution
    
    Features:
    - Priority-based scheduling
    - Dependency resolution
    - Load balancing
    - Task grouping
    """
    
    def __init__(self):
        """Initialize task distributor"""
        self.tasks: Dict[str, Task] = {}
        self.completed: set = set()
        logger.info("Task distributor initialized")
    
    def add_task(
        self,
        task_id: str,
        operation: str,
        func: Callable,
        kwargs: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
        estimated_duration: float = 30.0,
        dependencies: Optional[List[str]] = None
    ):
        """
        Add a task to the distributor
        
        Args:
            task_id: Unique task identifier
            operation: Operation name
            func: Async function to execute
            kwargs: Function arguments
            priority: Task priority
            estimated_duration: Estimated time in seconds
            dependencies: List of task IDs that must complete first
        """
        task = Task(
            task_id=task_id,
            operation=operation,
            func=func,
            kwargs=kwargs,
            priority=priority,
            estimated_duration=estimated_duration,
            dependencies=dependencies or []
        )
        
        self.tasks[task_id] = task
        logger.debug(f"Added task: {task_id} ({operation})")
    
    def get_ready_tasks(self) -> List[Task]:
        """
        Get tasks that are ready to execute (no pending dependencies)
        
        Returns:
            List of ready tasks, sorted by priority
        """
        ready = []
        
        for task_id, task in self.tasks.items():
            # Skip completed
            if task_id in self.completed:
                continue
            
            # Check dependencies
            deps_satisfied = all(
                dep in self.completed 
                for dep in task.dependencies
            )
            
            if deps_satisfied:
                ready.append(task)
        
        # Sort by priority (highest first), then by estimated duration (shortest first)
        ready.sort(
            key=lambda t: (-t.priority.value, t.estimated_duration)
        )
        
        return ready
    
    def mark_completed(self, task_id: str):
        """Mark a task as completed"""
        self.completed.add(task_id)
        logger.debug(f"Task completed: {task_id}")
    
    def get_batch(
        self,
        batch_size: int,
        max_duration: Optional[float] = None
    ) -> List[Task]:
        """
        Get a batch of tasks for parallel execution
        
        Args:
            batch_size: Maximum number of tasks
            max_duration: Maximum total estimated duration
            
        Returns:
            List of tasks to execute
        """
        ready = self.get_ready_tasks()
        
        if not ready:
            return []
        
        batch = []
        total_duration = 0.0
        
        for task in ready:
            if len(batch) >= batch_size:
                break
            
            if max_duration and (total_duration + task.estimated_duration) > max_duration:
                break
            
            batch.append(task)
            total_duration += task.estimated_duration
        
        logger.info(
            f"Created batch: {len(batch)} tasks, "
            f"~{total_duration:.1f}s estimated"
        )
        
        return batch
    
    def get_independent_groups(self) -> List[List[Task]]:
        """
        Group tasks into independent batches that can run in parallel
        
        Returns:
            List of task groups
        """
        groups = []
        processed = set()
        
        for task_id, task in self.tasks.items():
            if task_id in processed or task_id in self.completed:
                continue
            
            # Find all tasks with same dependencies
            group = [task]
            processed.add(task_id)
            
            for other_id, other_task in self.tasks.items():
                if (other_id not in processed and 
                    other_id not in self.completed and
                    set(other_task.dependencies) == set(task.dependencies)):
                    group.append(other_task)
                    processed.add(other_id)
            
            groups.append(group)
        
        return groups
    
    def estimate_total_time(
        self,
        max_concurrent: int = 5
    ) -> float:
        """
        Estimate total execution time with parallel execution
        
        Args:
            max_concurrent: Maximum concurrent tasks
            
        Returns:
            Estimated time in seconds
        """
        # Simple simulation
        remaining = list(self.tasks.values())
        total_time = 0.0
        
        while remaining:
            # Get ready tasks
            ready = [
                t for t in remaining 
                if all(dep in self.completed for dep in t.dependencies)
            ]
            
            if not ready:
                break
            
            # Execute batch
            batch = ready[:max_concurrent]
            batch_time = max(t.estimated_duration for t in batch)
            total_time += batch_time
            
            # Mark as complete
            for task in batch:
                self.completed.add(task.task_id)
                remaining.remove(task)
        
        # Reset completed set
        self.completed.clear()
        
        return total_time
    
    def visualize_dependencies(self) -> str:
        """
        Create ASCII visualization of task dependencies
        
        Returns:
            ASCII tree string
        """
        lines = []
        lines.append("Task Dependency Graph")
        lines.append("=" * 60)
        
        # Find root tasks (no dependencies)
        roots = [
            t for t in self.tasks.values()
            if not t.dependencies
        ]
        
        def render_task(task: Task, prefix: str = "", is_last: bool = True):
            """Recursively render task tree"""
            status = "✅" if task.task_id in self.completed else "⏳"
            priority_icon = {
                TaskPriority.LOW: "🔵",
                TaskPriority.NORMAL: "⚪",
                TaskPriority.HIGH: "🟡",
                TaskPriority.CRITICAL: "🔴"
            }.get(task.priority, "⚪")
            
            connector = "└── " if is_last else "├── "
            lines.append(
                f"{prefix}{connector}{status} {task.operation} "
                f"({task.estimated_duration:.0f}s) {priority_icon}"
            )
            
            # Find children (tasks that depend on this one)
            children = [
                t for t in self.tasks.values()
                if task.task_id in t.dependencies
            ]
            
            # Render children
            child_prefix = prefix + ("    " if is_last else "│   ")
            for i, child in enumerate(children):
                render_task(child, child_prefix, i == len(children) - 1)
        
        # Render from roots
        for i, root in enumerate(roots):
            render_task(root, "", i == len(roots) - 1)
        
        return "\n".join(lines)
    
    def get_critical_path(self) -> List[Task]:
        """
        Get critical path (longest dependency chain)
        
        Returns:
            List of tasks in critical path
        """
        def get_path_duration(task: Task, path: List[Task]) -> Tuple[float, List[Task]]:
            """Recursively find longest path"""
            children = [
                t for t in self.tasks.values()
                if task.task_id in t.dependencies
            ]
            
            if not children:
                return task.estimated_duration, path + [task]
            
            max_duration = 0
            max_path = path + [task]
            
            for child in children:
                duration, child_path = get_path_duration(child, path + [task])
                if duration > max_duration:
                    max_duration = duration
                    max_path = child_path
            
            return task.estimated_duration + max_duration, max_path
        
        # Find root tasks
        roots = [
            t for t in self.tasks.values()
            if not t.dependencies
        ]
        
        if not roots:
            return []
        
        # Find longest path from any root
        max_duration = 0
        critical_path = []
        
        for root in roots:
            duration, path = get_path_duration(root, [])
            if duration > max_duration:
                max_duration = duration
                critical_path = path
        
        return critical_path
    
    def clear(self):
        """Clear all tasks and completed status"""
        self.tasks.clear()
        self.completed.clear()
        logger.info("Task distributor cleared")
