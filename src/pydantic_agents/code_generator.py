"""
Code Generator Agent
====================

Pydantic AI agent for generating clean, well-documented code.

Replaces: src/agents/code_generator.py (LangChain-based)
Benefits: 
- Direct Ollama integration
- Type-safe outputs
- Automatic tracing
- 5-10% faster (no wrapper overhead)
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from .base_agent import BaseAgent, AgentConfig


class CodeResult(BaseModel):
    """Structured output for code generation"""
    code: str = Field(description="Generated code")
    explanation: str = Field(description="Explanation of the code")
    language: str = Field(default="python", description="Programming language")
    test_cases: List[str] = Field(default_factory=list, description="Suggested test cases")
    dependencies: List[str] = Field(default_factory=list, description="Required dependencies")
    complexity: str = Field(default="medium", description="Code complexity (simple/medium/complex)")
    estimated_lines: int = Field(default=0, description="Estimated lines of code")


class CodeGeneratorAgent(BaseAgent[CodeResult]):
    """
    Agent specialized in generating high-quality code.
    
    Example:
        ```python
        agent = CodeGeneratorAgent()
        result = await agent.generate("Create a binary search function")
        
        print(result.code)
        print(result.explanation)
        print(result.test_cases)
        ```
    """
    
    def __init__(
        self,
        model: str = "ollama:qwen2.5-coder:7b",
        temperature: float = 0.7
    ):
        """
        Initialize code generator agent.
        
        Args:
            model: Ollama model to use (qwen2.5-coder recommended for code)
            temperature: Generation temperature (0.7 for balanced creativity)
        """
        config = AgentConfig(
            model=model,
            temperature=temperature,
            max_tokens=4096,
            timeout=120,  # Code generation can take longer
            retries=3
        )
        
        instructions = """You are an expert software engineer specializing in writing clean, efficient, and well-documented code.

Your responsibilities:
1. Generate production-ready code that follows best practices
2. Include comprehensive docstrings and comments
3. Suggest appropriate test cases
4. List required dependencies
5. Provide clear explanations of the implementation

Code quality standards:
- Follow PEP 8 style guide (for Python)
- Use type hints and annotations
- Handle edge cases and errors
- Write self-documenting code
- Optimize for readability and maintainability

When generating code:
- Start with imports
- Add docstrings to all functions/classes
- Include error handling
- Add inline comments for complex logic
- Suggest at least 3 test cases
"""
        
        super().__init__(
            result_type=CodeResult,
            instructions=instructions,
            config=config,
            name="CodeGeneratorAgent"
        )
    
    async def generate(
        self,
        requirement: str,
        language: str = "python",
        style: str = "clean",
        include_tests: bool = True
    ) -> CodeResult:
        """
        Generate code from requirements.
        
        Args:
            requirement: Description of what code to generate
            language: Programming language (default: python)
            style: Code style preference (clean/compact/verbose)
            include_tests: Whether to suggest test cases
        
        Returns:
            CodeResult with generated code and metadata
        
        Example:
            ```python
            result = await agent.generate(
                "Create a REST API endpoint for user authentication",
                language="python",
                style="clean"
            )
            ```
        """
        prompt = f"""Generate {language} code for the following requirement:

Requirement: {requirement}

Style preference: {style}
Include test cases: {include_tests}

Please provide:
1. Complete, runnable code
2. Clear explanation of the implementation
3. Suggested test cases (if requested)
4. List of dependencies
5. Complexity assessment
"""
        
        return await self.run(prompt)
    
    async def refactor(
        self,
        existing_code: str,
        improvement_goals: List[str]
    ) -> CodeResult:
        """
        Refactor existing code with specific goals.
        
        Args:
            existing_code: Code to refactor
            improvement_goals: List of improvements (e.g., "improve performance", "add error handling")
        
        Returns:
            CodeResult with refactored code
        
        Example:
            ```python
            result = await agent.refactor(
                existing_code=old_code,
                improvement_goals=["add type hints", "improve error handling"]
            )
            ```
        """
        goals_str = "\n".join(f"- {goal}" for goal in improvement_goals)
        
        prompt = f"""Refactor the following code with these goals:

{goals_str}

Existing code:
```python
{existing_code}
```

Please provide:
1. Refactored code
2. Explanation of changes made
3. Test cases for new functionality
"""
        
        return await self.run(prompt)
    
    async def fix_bug(
        self,
        buggy_code: str,
        error_message: str,
        context: Optional[str] = None
    ) -> CodeResult:
        """
        Fix a bug in existing code.
        
        Args:
            buggy_code: Code containing the bug
            error_message: Error message or bug description
            context: Additional context about the bug
        
        Returns:
            CodeResult with fixed code
        """
        prompt = f"""Fix the bug in the following code:

Error: {error_message}

{f'Context: {context}' if context else ''}

Buggy code:
```python
{buggy_code}
```

Please provide:
1. Fixed code
2. Explanation of the bug and fix
3. Test cases to prevent regression
"""
        
        return await self.run(prompt)
    
    async def explain(self, code: str) -> str:
        """
        Explain what existing code does.
        
        Args:
            code: Code to explain
        
        Returns:
            Plain text explanation
        """
        result = await self.run(f"""Explain what this code does:

```python
{code}
```

Provide a clear explanation for someone learning programming.""")
        
        return result.explanation


# Convenience functions for direct usage
async def generate_code(requirement: str, model: str = "ollama:qwen2.5-coder:7b") -> CodeResult:
    """
    Quick function to generate code without creating agent instance.
    
    Example:
        ```python
        from src.pydantic_agents import generate_code
        
        result = await generate_code("Create a binary search function")
        print(result.code)
        ```
    """
    agent = CodeGeneratorAgent(model=model)
    return await agent.generate(requirement)


def generate_code_sync(requirement: str, model: str = "ollama:qwen2.5-coder:7b") -> CodeResult:
    """Synchronous version of generate_code()"""
    import asyncio
    return asyncio.run(generate_code(requirement, model))
