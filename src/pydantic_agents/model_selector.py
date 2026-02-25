"""
Model Selector Agent
===================

Intelligent LLM-based model router to replace manual if-else logic.

Uses lightweight model to make fast routing decisions based on task characteristics.
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from .base_agent import BaseAgent, AgentConfig


class ModelSelection(BaseModel):
    """Structured output for model selection"""
    selected_model: str = Field(description="Chosen model name (e.g., 'qwen2.5-coder:7b')")
    reasoning: str = Field(description="Explanation for why this model was selected")
    confidence: float = Field(ge=0, le=1, description="Confidence in selection (0-1)")
    estimated_tokens: int = Field(gt=0, description="Estimated tokens needed")
    estimated_latency_ms: int = Field(gt=0, description="Estimated response time in ms")
    alternative_models: List[str] = Field(default_factory=list, description="Backup options")


class ModelSelectorAgent(BaseAgent[ModelSelection]):
    """
    Agent that intelligently routes tasks to the most appropriate model.
    
    Replaces manual routing logic with LLM-based decision making.
    
    Available models:
    - qwen2.5-coder:7b - Code generation/refactoring (fast, 7B params)
    - deepseek-r1:8b - Reasoning/analysis (slower, better for complex tasks)
    - phi4-mini:3.8b - Simple queries (fastest, smallest)
    - nomic-embed-text - Embeddings only
    
    Example:
        ```python
        selector = ModelSelectorAgent()
        
        selection = await selector.select_model(
            task="Generate a REST API endpoint",
            complexity="medium"
        )
        
        print(f"Use {selection.selected_model} - {selection.reasoning}")
        ```
    """
    
    def __init__(
        self,
        model: str = "ollama:qwen2.5-coder:7b",  # Fast lightweight model
        temperature: float = 0.1  # Low temperature for consistent routing
    ):
        """
        Initialize model selector agent.
        
        Args:
            model: Model to use for making selection decisions
            temperature: Low temperature for consistent routing
        """
        config = AgentConfig(
            model=model,
            temperature=temperature,
            max_tokens=512,  # Short responses
            timeout=10,  # Fast decisions
            retries=2
        )
        
        instructions = """You are an intelligent model router that selects the best LLM for each task.

Available models in our system:

1. **qwen2.5-coder:7b** (7B parameters, 4096 context)
   - Best for: Code generation, refactoring, code explanation
   - Speed: Fast (~2-3s for 500 tokens)
   - Quality: Excellent for programming tasks
   - When to use: Any coding task, documentation generation

2. **deepseek-r1:8b** (8B parameters, 8192 context)
   - Best for: Complex reasoning, code review, architecture decisions
   - Speed: Slower (~4-5s for 500 tokens)
   - Quality: Superior reasoning capabilities
   - When to use: Code review, debugging, analysis, planning

3. **phi4-mini:3.8b** (3.8B parameters, 2048 context)
   - Best for: Simple queries, quick answers, classification
   - Speed: Fastest (~1-2s for 500 tokens)
   - Quality: Good for simple tasks
   - When to use: Quick lookups, simple explanations, yes/no questions

4. **nomic-embed-text** (Embedding model only)
   - Best for: Generating embeddings for vector search
   - Speed: Very fast
   - When to use: Semantic search, RAG, similarity comparisons

Selection criteria:
- **Task complexity**: Simple → phi4-mini, Medium → qwen2.5-coder, Complex → deepseek-r1
- **Token budget**: Large outputs need models with bigger context windows
- **Latency requirements**: Time-sensitive → phi4-mini, Quality-sensitive → deepseek-r1
- **Task type**: Code → qwen2.5-coder, Reasoning → deepseek-r1, Quick → phi4-mini

Be pragmatic: Don't use heavyweight models for simple tasks. Balance quality vs speed.
"""
        
        super().__init__(
            result_type=ModelSelection,
            instructions=instructions,
            config=config,
            name="ModelSelectorAgent"
        )
    
    async def select_model(
        self,
        task_description: str,
        complexity: str = "medium",  # low/medium/high
        max_latency_ms: Optional[int] = None,
        max_tokens: Optional[int] = None,
        priority: str = "balanced"  # speed/quality/balanced
    ) -> ModelSelection:
        """
        Select the most appropriate model for a task.
        
        Args:
            task_description: Description of the task to perform
            complexity: Task complexity (low/medium/high)
            max_latency_ms: Maximum acceptable latency in milliseconds
            max_tokens: Maximum tokens expected in response
            priority: Optimization priority (speed/quality/balanced)
        
        Returns:
            ModelSelection with chosen model and reasoning
        
        Example:
            ```python
            selection = await selector.select_model(
                task_description="Fix a bug in authentication logic",
                complexity="high",
                priority="quality"
            )
            
            # Use selected model
            if selection.confidence > 0.8:
                use_model = selection.selected_model
            else:
                # Fall back to default
                use_model = "qwen2.5-coder:7b"
            ```
        """
        prompt = f"""Select the best model for this task:

Task: {task_description}
Complexity: {complexity}
{f'Max latency: {max_latency_ms}ms' if max_latency_ms else ''}
{f'Max tokens: {max_tokens}' if max_tokens else ''}
Priority: {priority}

Consider:
1. Task type (coding/reasoning/simple query)
2. Complexity level
3. Latency requirements
4. Token budget
5. Quality vs speed tradeoff

Select the optimal model and explain your reasoning. Be specific about why this model is best.
"""
        
        return await self.run(prompt)
    
    async def select_for_code_task(
        self,
        task_type: str,  # generate/review/refactor/explain/debug
        code_complexity: str = "medium"
    ) -> ModelSelection:
        """
        Specialized selector for code-related tasks.
        
        Args:
            task_type: Type of code task (generate/review/refactor/explain/debug)
            code_complexity: Code complexity (simple/medium/complex)
        
        Returns:
            ModelSelection optimized for code tasks
        """
        task_map = {
            "generate": "Generate new code from requirements",
            "review": "Review code for quality and issues",
            "refactor": "Refactor existing code to improve it",
            "explain": "Explain what code does",
            "debug": "Debug and fix code issues"
        }
        
        description = task_map.get(task_type, task_type)
        
        # Review/debug need reasoning → use deepseek-r1
        if task_type in ["review", "debug"]:
            priority = "quality"
        # Generate/refactor need speed → use qwen2.5-coder
        elif task_type in ["generate", "refactor"]:
            priority = "balanced"
        # Explain is simple → can use faster model
        else:
            priority = "speed"
        
        return await self.select_model(
            task_description=f"Code task: {description}",
            complexity=code_complexity,
            priority=priority
        )
    
    async def batch_route(
        self,
        tasks: List[str]
    ) -> List[ModelSelection]:
        """
        Route multiple tasks efficiently.
        
        Args:
            tasks: List of task descriptions
        
        Returns:
            List of ModelSelection for each task
        """
        prompt = f"""Route these {len(tasks)} tasks to appropriate models:

{chr(10).join(f'{i+1}. {task}' for i, task in enumerate(tasks))}

For each task, select the optimal model considering:
- Task type and complexity
- Efficiency (don't overuse heavy models)
- Load balancing (distribute across models when possible)

Return {len(tasks)} selections, one per task.
"""
        
        # For batch routing, we'd need to modify the return type
        # For now, route individually
        selections = []
        for task in tasks:
            selection = await self.select_model(task)
            selections.append(selection)
        
        return selections


# Convenience functions
async def select_model_for_task(
    task: str,
    complexity: str = "medium"
) -> str:
    """
    Quick function to get model name without creating agent instance.
    
    Returns just the model name as a string.
    
    Example:
        ```python
        from src.pydantic_agents import select_model_for_task
        
        model = await select_model_for_task("Generate a Flask API")
        # Returns: "qwen2.5-coder:7b"
        ```
    """
    selector = ModelSelectorAgent()
    selection = await selector.select_model(task, complexity=complexity)
    return selection.selected_model


def select_model_for_task_sync(task: str, complexity: str = "medium") -> str:
    """Synchronous version of select_model_for_task()"""
    import asyncio
    return asyncio.run(select_model_for_task(task, complexity))
