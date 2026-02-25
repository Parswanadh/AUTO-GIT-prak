"""Parallel Executor - Asyncio-based parallel task execution"""

import asyncio
import logging
from typing import List, Callable, Any, Dict, Optional, Tuple
from datetime import datetime
import time

logger = logging.getLogger(__name__)


class ParallelExecutor:
    """
    Execute multiple tasks in parallel using asyncio
    
    Features:
    - Concurrent task execution
    - Error isolation (one failure doesn't stop others)
    - Timeout support
    - Result aggregation
    - Performance tracking
    """
    
    def __init__(
        self,
        max_concurrent: int = 5,
        default_timeout: float = 60.0
    ):
        """
        Initialize parallel executor
        
        Args:
            max_concurrent: Maximum concurrent tasks
            default_timeout: Default timeout per task in seconds
        """
        self.max_concurrent = max_concurrent
        self.default_timeout = default_timeout
        self.semaphore = asyncio.Semaphore(max_concurrent)
        
        logger.info(
            f"Parallel executor initialized: "
            f"max_concurrent={max_concurrent}, timeout={default_timeout}s"
        )
    
    async def execute_parallel(
        self,
        tasks: List[Tuple[Callable, Dict[str, Any]]],
        timeout: Optional[float] = None,
        fail_fast: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Execute multiple tasks in parallel
        
        Args:
            tasks: List of (async_func, kwargs) tuples
            timeout: Timeout per task (uses default if None)
            fail_fast: Stop all tasks if one fails
            
        Returns:
            List of results (same order as input tasks)
        """
        timeout = timeout or self.default_timeout
        
        logger.info(f"Starting parallel execution of {len(tasks)} tasks")
        start_time = time.time()
        
        # Create coroutines
        coroutines = [
            self._execute_single_task(i, func, kwargs, timeout)
            for i, (func, kwargs) in enumerate(tasks)
        ]
        
        # Execute in parallel
        if fail_fast:
            # Return first exception, stop others
            results = await asyncio.gather(*coroutines)
        else:
            # Continue even if some fail
            results = await asyncio.gather(*coroutines, return_exceptions=True)
        
        # Process results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Task {i} failed: {result}")
                processed_results.append({
                    "success": False,
                    "error": str(result),
                    "task_index": i
                })
            else:
                processed_results.append(result)
        
        elapsed = time.time() - start_time
        successful = sum(1 for r in processed_results if r.get("success", False))
        
        logger.info(
            f"Parallel execution complete: {successful}/{len(tasks)} succeeded "
            f"in {elapsed:.2f}s"
        )
        
        return processed_results
    
    async def _execute_single_task(
        self,
        task_id: int,
        func: Callable,
        kwargs: Dict[str, Any],
        timeout: float
    ) -> Dict[str, Any]:
        """Execute a single task with semaphore and timeout"""
        async with self.semaphore:
            try:
                logger.debug(f"Starting task {task_id}")
                start = time.time()
                
                # Execute with timeout
                result = await asyncio.wait_for(
                    func(**kwargs),
                    timeout=timeout
                )
                
                elapsed = time.time() - start
                logger.debug(f"Task {task_id} completed in {elapsed:.2f}s")
                
                return {
                    "success": True,
                    "result": result,
                    "task_index": task_id,
                    "elapsed_seconds": elapsed
                }
                
            except asyncio.TimeoutError:
                logger.error(f"Task {task_id} timed out after {timeout}s")
                return {
                    "success": False,
                    "error": f"Timeout after {timeout}s",
                    "task_index": task_id
                }
            except Exception as e:
                logger.error(f"Task {task_id} failed: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "task_index": task_id
                }
    
    async def map_parallel(
        self,
        func: Callable,
        items: List[Any],
        timeout: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Map a function over items in parallel
        
        Args:
            func: Async function to call
            items: List of items to process
            timeout: Timeout per item
            
        Returns:
            List of results
        """
        tasks = [(func, {"item": item}) for item in items]
        return await self.execute_parallel(tasks, timeout=timeout)
    
    async def race(
        self,
        tasks: List[Tuple[Callable, Dict[str, Any]]],
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Race multiple tasks, return first successful result
        
        Args:
            tasks: List of (async_func, kwargs) tuples
            timeout: Overall timeout
            
        Returns:
            First successful result
        """
        timeout = timeout or self.default_timeout
        
        logger.info(f"Racing {len(tasks)} tasks")
        
        # Create tasks (not coroutines)
        task_objects = [
            asyncio.create_task(
                self._execute_single_task(i, func, kwargs, timeout)
            )
            for i, (func, kwargs) in enumerate(tasks)
        ]
        
        try:
            # Wait for first successful completion
            done, pending = await asyncio.wait(
                task_objects,
                timeout=timeout,
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel remaining tasks
            for task in pending:
                task.cancel()
            
            # Get first result
            if done:
                result = list(done)[0].result()
                if result.get("success"):
                    logger.info(f"Race winner: task {result['task_index']}")
                    return result
            
            # No successful completion
            logger.warning("Race: No task completed successfully")
            return {
                "success": False,
                "error": "No task completed successfully"
            }
            
        except asyncio.TimeoutError:
            logger.error(f"Race timed out after {timeout}s")
            # Cancel all tasks
            for task in task_objects:
                task.cancel()
            return {
                "success": False,
                "error": f"Race timeout after {timeout}s"
            }
    
    async def batch_execute(
        self,
        tasks: List[Tuple[Callable, Dict[str, Any]]],
        batch_size: int = 5,
        timeout: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute tasks in batches
        
        Args:
            tasks: List of (async_func, kwargs) tuples
            batch_size: Number of tasks per batch
            timeout: Timeout per task
            
        Returns:
            List of all results
        """
        logger.info(
            f"Executing {len(tasks)} tasks in batches of {batch_size}"
        )
        
        all_results = []
        
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i+batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}")
            
            results = await self.execute_parallel(batch, timeout=timeout)
            all_results.extend(results)
        
        return all_results
    
    def get_stats(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Get statistics from execution results
        
        Args:
            results: List of execution results
            
        Returns:
            Statistics dict
        """
        successful = [r for r in results if r.get("success", False)]
        failed = [r for r in results if not r.get("success", False)]
        
        elapsed_times = [
            r.get("elapsed_seconds", 0) 
            for r in successful
        ]
        
        return {
            "total_tasks": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "success_rate": len(successful) / len(results) if results else 0,
            "avg_elapsed": sum(elapsed_times) / len(elapsed_times) if elapsed_times else 0,
            "min_elapsed": min(elapsed_times) if elapsed_times else 0,
            "max_elapsed": max(elapsed_times) if elapsed_times else 0,
            "total_elapsed": sum(elapsed_times),
        }
