"""
Task Coordinator - Integration #15

Coordinates complex tasks by:
1. Analyzing task complexity
2. Decomposing into subtasks
3. Assigning specialist agents
4. Executing in parallel
5. Synthesizing results

This enables tackling complex problems requiring multiple specialized approaches.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Subtask:
    """Represents a subtask to be executed by a specialist."""
    id: str
    description: str
    specialist_type: str
    priority: int = 1
    dependencies: List[str] = None
    context: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.context is None:
            self.context = {}


@dataclass
class TaskAnalysis:
    """Analysis of task complexity and requirements."""
    complexity: str  # "low", "medium", "high"
    estimated_subtasks: int
    required_specialists: List[str]
    parallel_executable: bool
    reasoning: str


class TaskCoordinator:
    """
    Coordinate complex tasks across specialist agents.
    
    Workflow:
    1. Analyze task complexity
    2. Decompose into subtasks
    3. Select appropriate specialists
    4. Execute subtasks in parallel
    5. Synthesize results into coherent solution
    """
    
    def __init__(self, llm_router=None):
        """
        Initialize task coordinator.
        
        Args:
            llm_router: Optional HybridRouter for LLM calls
        """
        self.llm_router = llm_router
        self.specialist_registry = {}
        
        logger.info("TaskCoordinator initialized")
    
    def register_specialist(self, specialist_type: str, specialist_instance):
        """
        Register a specialist agent.
        
        Args:
            specialist_type: Type identifier (e.g., "code", "testing")
            specialist_instance: Instance of specialist agent
        """
        self.specialist_registry[specialist_type] = specialist_instance
        logger.info(f"Registered specialist: {specialist_type}")
    
    async def coordinate(self, 
                        task: str,
                        context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Main coordination workflow.
        
        Args:
            task: Task description
            context: Optional context (requirements, constraints, etc.)
            
        Returns:
            Dictionary with synthesized results and metadata
        """
        logger.info(f"🎯 Coordinating task: {task[:100]}...")
        
        # 1. Analyze task
        analysis = await self.analyze_task(task, context)
        logger.info(f"Task complexity: {analysis.complexity}")
        
        # If task is simple, skip coordination overhead
        if analysis.complexity == "low":
            logger.info("Task is simple, skipping hierarchical coordination")
            return {
                "approach": "direct",
                "result": None,
                "message": "Task complexity too low for coordination"
            }
        
        # 2. Decompose into subtasks
        subtasks = await self.decompose(task, analysis, context)
        logger.info(f"Decomposed into {len(subtasks)} subtasks")
        
        # 3. Execute subtasks
        results = await self.execute_subtasks(subtasks)
        logger.info(f"Executed {len(results)} subtasks successfully")
        
        # 4. Synthesize results
        final = await self.synthesize(results, task, context)
        logger.info("✅ Coordination complete")
        
        return final
    
    async def analyze_task(self, 
                          task: str,
                          context: Optional[Dict[str, Any]] = None) -> TaskAnalysis:
        """
        Analyze task complexity and requirements.
        
        Args:
            task: Task description
            context: Optional context
            
        Returns:
            TaskAnalysis object
        """
        # Simple heuristic-based analysis
        task_lower = task.lower()
        
        # Complexity indicators
        complexity_indicators = {
            "high": ["implement", "build", "create", "design", "develop", "refactor"],
            "medium": ["add", "modify", "update", "enhance", "improve"],
            "low": ["fix", "debug", "change", "rename"]
        }
        
        # Count complexity indicators
        high_count = sum(1 for word in complexity_indicators["high"] if word in task_lower)
        medium_count = sum(1 for word in complexity_indicators["medium"] if word in task_lower)
        
        # Check for multiple components
        component_keywords = ["test", "doc", "api", "database", "auth", "ui", "cli"]
        component_count = sum(1 for word in component_keywords if word in task_lower)
        
        # Determine complexity
        if high_count > 0 or component_count >= 2:
            complexity = "high"
            estimated_subtasks = 3 + component_count
        elif medium_count > 0 or component_count == 1:
            complexity = "medium"
            estimated_subtasks = 2
        else:
            complexity = "low"
            estimated_subtasks = 1
        
        # Identify required specialists
        required_specialists = []
        if any(word in task_lower for word in ["implement", "build", "create", "code"]):
            required_specialists.append("code")
        if "test" in task_lower:
            required_specialists.append("testing")
        if any(word in task_lower for word in ["doc", "documentation", "readme"]):
            required_specialists.append("documentation")
        if any(word in task_lower for word in ["design", "architecture", "structure"]):
            required_specialists.append("architecture")
        if any(word in task_lower for word in ["optimize", "performance", "speed"]):
            required_specialists.append("performance")
        
        # If no specialists identified, default to code
        if not required_specialists:
            required_specialists = ["code"]
        
        parallel_executable = len(required_specialists) > 1
        
        reasoning = f"Detected {high_count} high-complexity keywords, {component_count} components"
        
        return TaskAnalysis(
            complexity=complexity,
            estimated_subtasks=estimated_subtasks,
            required_specialists=required_specialists,
            parallel_executable=parallel_executable,
            reasoning=reasoning
        )
    
    async def decompose(self,
                       task: str,
                       analysis: TaskAnalysis,
                       context: Optional[Dict[str, Any]] = None) -> List[Subtask]:
        """
        Decompose task into subtasks.
        
        Args:
            task: Original task
            analysis: Task analysis
            context: Optional context
            
        Returns:
            List of Subtask objects
        """
        subtasks = []
        
        # Create subtasks based on required specialists
        for i, specialist_type in enumerate(analysis.required_specialists):
            if specialist_type == "code":
                subtask = Subtask(
                    id=f"subtask_{i+1}",
                    description=f"Implement core functionality for: {task}",
                    specialist_type="code",
                    priority=1,
                    context=context or {}
                )
            elif specialist_type == "testing":
                subtask = Subtask(
                    id=f"subtask_{i+1}",
                    description=f"Create comprehensive tests for: {task}",
                    specialist_type="testing",
                    priority=2,
                    dependencies=["subtask_1"] if "code" in analysis.required_specialists else [],
                    context=context or {}
                )
            elif specialist_type == "documentation":
                subtask = Subtask(
                    id=f"subtask_{i+1}",
                    description=f"Write documentation for: {task}",
                    specialist_type="documentation",
                    priority=3,
                    dependencies=["subtask_1"] if "code" in analysis.required_specialists else [],
                    context=context or {}
                )
            elif specialist_type == "architecture":
                subtask = Subtask(
                    id=f"subtask_{i+1}",
                    description=f"Design architecture for: {task}",
                    specialist_type="architecture",
                    priority=1,
                    context=context or {}
                )
            elif specialist_type == "performance":
                subtask = Subtask(
                    id=f"subtask_{i+1}",
                    description=f"Optimize performance for: {task}",
                    specialist_type="performance",
                    priority=2,
                    dependencies=["subtask_1"] if "code" in analysis.required_specialists else [],
                    context=context or {}
                )
            else:
                # Generic subtask
                subtask = Subtask(
                    id=f"subtask_{i+1}",
                    description=f"Handle {specialist_type} aspect of: {task}",
                    specialist_type=specialist_type,
                    priority=2,
                    context=context or {}
                )
            
            subtasks.append(subtask)
        
        return subtasks
    
    async def execute_subtasks(self, subtasks: List[Subtask]) -> List[Dict[str, Any]]:
        """
        Execute subtasks in parallel (respecting dependencies).
        
        Args:
            subtasks: List of subtasks to execute
            
        Returns:
            List of results from each subtask
        """
        results = []
        completed = set()
        
        # Group subtasks by dependency level
        while len(completed) < len(subtasks):
            # Find subtasks ready to execute (no unmet dependencies)
            ready_subtasks = [
                st for st in subtasks 
                if st.id not in completed and all(dep in completed for dep in st.dependencies)
            ]
            
            if not ready_subtasks:
                logger.warning("No ready subtasks found - possible circular dependency")
                break
            
            # Execute ready subtasks in parallel
            logger.info(f"Executing {len(ready_subtasks)} subtasks in parallel...")
            
            tasks = [self._execute_single_subtask(st) for st in ready_subtasks]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for subtask, result in zip(ready_subtasks, batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Subtask {subtask.id} failed: {result}")
                    results.append({
                        "subtask_id": subtask.id,
                        "specialist_type": subtask.specialist_type,
                        "success": False,
                        "error": str(result)
                    })
                else:
                    results.append(result)
                
                completed.add(subtask.id)
        
        return results
    
    async def _execute_single_subtask(self, subtask: Subtask) -> Dict[str, Any]:
        """
        Execute a single subtask using appropriate specialist.
        
        Args:
            subtask: Subtask to execute
            
        Returns:
            Result dictionary
        """
        logger.info(f"Executing subtask {subtask.id}: {subtask.specialist_type}")
        
        # Check if specialist is registered
        if subtask.specialist_type not in self.specialist_registry:
            logger.warning(f"No specialist registered for: {subtask.specialist_type}")
            return {
                "subtask_id": subtask.id,
                "specialist_type": subtask.specialist_type,
                "success": False,
                "error": "Specialist not registered",
                "result": None
            }
        
        # Get specialist
        specialist = self.specialist_registry[subtask.specialist_type]
        
        try:
            # Execute subtask
            result = await specialist.execute(subtask)
            
            return {
                "subtask_id": subtask.id,
                "specialist_type": subtask.specialist_type,
                "success": True,
                "result": result
            }
        except Exception as e:
            logger.error(f"Specialist execution failed: {e}")
            return {
                "subtask_id": subtask.id,
                "specialist_type": subtask.specialist_type,
                "success": False,
                "error": str(e),
                "result": None
            }
    
    async def synthesize(self,
                        results: List[Dict[str, Any]],
                        original_task: str,
                        context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Synthesize specialist results into coherent solution.
        
        Args:
            results: List of specialist results
            original_task: Original task description
            context: Optional context
            
        Returns:
            Final synthesized result
        """
        logger.info("Synthesizing results...")
        
        # Organize results by specialist type
        organized = {}
        for result in results:
            if result["success"]:
                specialist_type = result["specialist_type"]
                organized[specialist_type] = result["result"]
        
        # Count successes and failures
        successful = sum(1 for r in results if r["success"])
        total = len(results)
        
        return {
            "approach": "hierarchical",
            "original_task": original_task,
            "subtasks_completed": successful,
            "subtasks_total": total,
            "success_rate": successful / total if total > 0 else 0,
            "results": organized,
            "metadata": {
                "specialists_used": list(organized.keys()),
                "parallel_execution": True
            }
        }


if __name__ == "__main__":
    # Test coordinator
    print("Testing TaskCoordinator...")
    
    async def test():
        coordinator = TaskCoordinator()
        
        # Test task analysis
        print("\n1. Testing task analysis...")
        analysis = await coordinator.analyze_task(
            "Implement user authentication system with tests and documentation"
        )
        print(f"   Complexity: {analysis.complexity}")
        print(f"   Specialists: {analysis.required_specialists}")
        print(f"   Parallel: {analysis.parallel_executable}")
        
        # Test decomposition
        print("\n2. Testing decomposition...")
        subtasks = await coordinator.decompose(
            "Build REST API with tests",
            analysis
        )
        print(f"   Subtasks: {len(subtasks)}")
        for st in subtasks:
            print(f"   - {st.id}: {st.specialist_type} (priority {st.priority})")
        
        print("\n✅ TaskCoordinator test complete!")
    
    asyncio.run(test())
