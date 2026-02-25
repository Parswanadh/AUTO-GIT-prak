"""Multi-Agent Coordinator - High-level coordination of parallel agents"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime

from .parallel_executor import ParallelExecutor
from .task_distributor import TaskDistributor, TaskPriority

logger = logging.getLogger(__name__)


class MultiAgentCoordinator:
    """
    High-level coordinator for multi-agent parallel execution
    
    Use cases:
    - Parallel code generation (multiple files)
    - Concurrent critique from multiple perspectives
    - Simultaneous research queries
    - Multi-model voting/consensus
    """
    
    def __init__(
        self,
        max_concurrent: int = 5,
        default_timeout: float = 60.0
    ):
        """
        Initialize coordinator
        
        Args:
            max_concurrent: Maximum concurrent agents
            default_timeout: Default timeout per agent
        """
        self.executor = ParallelExecutor(
            max_concurrent=max_concurrent,
            default_timeout=default_timeout
        )
        self.distributor = TaskDistributor()
        
        logger.info(
            f"Multi-agent coordinator initialized: "
            f"max_concurrent={max_concurrent}"
        )
    
    async def generate_files_parallel(
        self,
        file_specs: List[Dict[str, str]],
        generate_func: Callable,
        timeout: float = 60.0
    ) -> List[Dict[str, Any]]:
        """
        Generate multiple code files in parallel
        
        Args:
            file_specs: List of {filename, prompt} dicts
            generate_func: Async function(filename, prompt) -> code
            timeout: Timeout per file
            
        Returns:
            List of {filename, code, success} dicts
        """
        logger.info(f"Generating {len(file_specs)} files in parallel")
        
        tasks = [
            (generate_func, {"filename": spec["filename"], "prompt": spec["prompt"]})
            for spec in file_specs
        ]
        
        results = await self.executor.execute_parallel(tasks, timeout=timeout)
        
        # Format results
        outputs = []
        for i, result in enumerate(results):
            if result.get("success"):
                outputs.append({
                    "filename": file_specs[i]["filename"],
                    "code": result.get("result"),
                    "success": True,
                    "elapsed": result.get("elapsed_seconds", 0)
                })
            else:
                outputs.append({
                    "filename": file_specs[i]["filename"],
                    "error": result.get("error"),
                    "success": False
                })
        
        successful = sum(1 for o in outputs if o["success"])
        logger.info(f"File generation: {successful}/{len(file_specs)} succeeded")
        
        return outputs
    
    async def critique_parallel(
        self,
        solution: str,
        perspectives: List[str],
        critique_func: Callable,
        timeout: float = 30.0
    ) -> List[Dict[str, Any]]:
        """
        Get critiques from multiple perspectives in parallel
        
        Args:
            solution: Solution to critique
            perspectives: List of perspective names
            critique_func: Async function(solution, perspective) -> critique
            timeout: Timeout per critique
            
        Returns:
            List of {perspective, critique, success} dicts
        """
        logger.info(f"Running {len(perspectives)} parallel critiques")
        
        tasks = [
            (critique_func, {"solution": solution, "perspective": p})
            for p in perspectives
        ]
        
        results = await self.executor.execute_parallel(tasks, timeout=timeout)
        
        # Format results
        outputs = []
        for i, result in enumerate(results):
            if result.get("success"):
                outputs.append({
                    "perspective": perspectives[i],
                    "critique": result.get("result"),
                    "success": True,
                    "elapsed": result.get("elapsed_seconds", 0)
                })
            else:
                outputs.append({
                    "perspective": perspectives[i],
                    "error": result.get("error"),
                    "success": False
                })
        
        return outputs
    
    async def research_parallel(
        self,
        queries: List[str],
        search_func: Callable,
        timeout: float = 30.0
    ) -> List[Dict[str, Any]]:
        """
        Execute multiple research queries in parallel
        
        Args:
            queries: List of search queries
            search_func: Async function(query) -> results
            timeout: Timeout per query
            
        Returns:
            List of {query, results, success} dicts
        """
        logger.info(f"Executing {len(queries)} parallel research queries")
        
        tasks = [
            (search_func, {"query": q})
            for q in queries
        ]
        
        results = await self.executor.execute_parallel(tasks, timeout=timeout)
        
        # Format results
        outputs = []
        for i, result in enumerate(results):
            if result.get("success"):
                outputs.append({
                    "query": queries[i],
                    "results": result.get("result"),
                    "success": True,
                    "elapsed": result.get("elapsed_seconds", 0)
                })
            else:
                outputs.append({
                    "query": queries[i],
                    "error": result.get("error"),
                    "success": False
                })
        
        return outputs
    
    async def multi_model_vote(
        self,
        prompt: str,
        models: List[str],
        generate_func: Callable,
        timeout: float = 30.0
    ) -> Dict[str, Any]:
        """
        Get responses from multiple models and find consensus
        
        Args:
            prompt: Input prompt
            models: List of model names
            generate_func: Async function(prompt, model) -> response
            timeout: Timeout per model
            
        Returns:
            Dict with {responses, consensus, votes}
        """
        logger.info(f"Multi-model voting with {len(models)} models")
        
        tasks = [
            (generate_func, {"prompt": prompt, "model": m})
            for m in models
        ]
        
        results = await self.executor.execute_parallel(tasks, timeout=timeout)
        
        # Collect responses
        responses = {}
        for i, result in enumerate(results):
            if result.get("success"):
                responses[models[i]] = result.get("result")
        
        # Simple voting: most common response
        if responses:
            from collections import Counter
            vote_counts = Counter(responses.values())
            consensus = vote_counts.most_common(1)[0][0]
            votes = dict(vote_counts)
        else:
            consensus = None
            votes = {}
        
        return {
            "responses": responses,
            "consensus": consensus,
            "votes": votes,
            "total_models": len(models),
            "successful_models": len(responses)
        }
    
    async def execute_with_dependencies(
        self,
        task_configs: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Execute tasks with dependency resolution
        
        Args:
            task_configs: List of task configs with:
                - task_id: str
                - operation: str
                - func: Callable
                - kwargs: Dict
                - priority: Optional[TaskPriority]
                - dependencies: Optional[List[str]]
                
        Returns:
            List of execution results
        """
        logger.info(f"Executing {len(task_configs)} tasks with dependencies")
        
        # Add tasks to distributor
        for config in task_configs:
            self.distributor.add_task(
                task_id=config["task_id"],
                operation=config["operation"],
                func=config["func"],
                kwargs=config.get("kwargs", {}),
                priority=config.get("priority", TaskPriority.NORMAL),
                estimated_duration=config.get("estimated_duration", 30.0),
                dependencies=config.get("dependencies", [])
            )
        
        # Visualize plan
        logger.info("\n" + self.distributor.visualize_dependencies())
        
        # Execute in waves
        all_results = {}
        wave = 1
        
        while True:
            # Get ready tasks
            ready = self.distributor.get_ready_tasks()
            
            if not ready:
                break
            
            logger.info(f"Wave {wave}: Executing {len(ready)} tasks")
            
            # Convert to executor format
            tasks = [
                (task.func, task.kwargs)
                for task in ready
            ]
            
            # Execute wave
            results = await self.executor.execute_parallel(tasks)
            
            # Store results and mark completed
            for i, task in enumerate(ready):
                all_results[task.task_id] = results[i]
                if results[i].get("success"):
                    self.distributor.mark_completed(task.task_id)
            
            wave += 1
        
        # Clear distributor
        self.distributor.clear()
        
        return [all_results[config["task_id"]] for config in task_configs]
    
    async def batch_process(
        self,
        items: List[Any],
        process_func: Callable,
        batch_size: int = 5,
        timeout: float = 30.0
    ) -> List[Dict[str, Any]]:
        """
        Process items in batches
        
        Args:
            items: List of items to process
            process_func: Async function(item) -> result
            batch_size: Items per batch
            timeout: Timeout per item
            
        Returns:
            List of results
        """
        logger.info(
            f"Batch processing {len(items)} items "
            f"(batch_size={batch_size})"
        )
        
        tasks = [(process_func, {"item": item}) for item in items]
        
        results = await self.executor.batch_execute(
            tasks,
            batch_size=batch_size,
            timeout=timeout
        )
        
        return results
    
    def get_performance_stats(
        self,
        results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Get performance statistics from execution results"""
        return self.executor.get_stats(results)
