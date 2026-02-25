"""
Code Reviewer Agent
===================

Pydantic AI agent for reviewing code quality and suggesting improvements.

Model: deepseek-r1:8b (reasoning model, better for analysis)
"""

from typing import List
from pydantic import BaseModel, Field
from .base_agent import BaseAgent, AgentConfig


class CodeIssue(BaseModel):
    """Represents a code quality issue"""
    severity: str = Field(description="Severity: critical/high/medium/low")
    category: str = Field(description="Category: bug/performance/style/security")
    line_number: int = Field(default=0, description="Approximate line number")
    description: str = Field(description="Description of the issue")
    suggestion: str = Field(description="Suggested fix")


class CodeReview(BaseModel):
    """Structured output for code review"""
    approved: bool = Field(description="Whether code is approved")
    overall_quality: str = Field(description="Overall quality: excellent/good/fair/poor")
    score: float = Field(ge=0, le=10, description="Quality score (0-10)")
    issues: List[CodeIssue] = Field(default_factory=list, description="List of issues found")
    strengths: List[str] = Field(default_factory=list, description="Code strengths")
    improvements: List[str] = Field(default_factory=list, description="Suggested improvements")
    security_concerns: List[str] = Field(default_factory=list, description="Security issues")
    performance_notes: List[str] = Field(default_factory=list, description="Performance observations")
    summary: str = Field(description="Executive summary of review")


class CodeReviewerAgent(BaseAgent[CodeReview]):
    """
    Agent specialized in code review and quality assessment.
    
    Uses DeepSeek-R1 for enhanced reasoning capabilities.
    
    Example:
        ```python
        agent = CodeReviewerAgent()
        review = await agent.review(code)
        
        if not review.approved:
            for issue in review.issues:
                print(f"{issue.severity}: {issue.description}")
        ```
    """
    
    def __init__(
        self,
        model: str = "ollama:deepseek-r1:8b",
        temperature: float = 0.3  # Lower for more consistent reviews
    ):
        """
        Initialize code reviewer agent.
        
        Args:
            model: Ollama model to use (deepseek-r1 recommended for reasoning)
            temperature: Generation temperature (0.3 for consistent reviews)
        """
        config = AgentConfig(
            model=model,
            temperature=temperature,
            max_tokens=4096,
            timeout=90,
            retries=3
        )
        
        instructions = """You are a senior code reviewer with expertise in software engineering best practices.

Your responsibilities:
1. Thoroughly review code for bugs, security issues, and performance problems
2. Assess code quality, readability, and maintainability
3. Provide constructive feedback with specific suggestions
4. Identify both strengths and areas for improvement
5. Give a final approval decision

Review criteria:
- **Bugs**: Logic errors, edge cases, null checks
- **Security**: Input validation, SQL injection, XSS, secrets in code
- **Performance**: Time complexity, unnecessary loops, memory usage
- **Style**: PEP 8 compliance, naming conventions, documentation
- **Maintainability**: Code organization, DRY principle, testability
- **Error Handling**: Try-except blocks, error messages, recovery

Severity levels:
- **Critical**: Must fix before merging (security/data loss)
- **High**: Should fix before merging (bugs/major issues)
- **Medium**: Should address soon (code quality)
- **Low**: Nice to have (style/optimization)

Be thorough but constructive. Recognize good practices and provide actionable feedback.
"""
        
        super().__init__(
            result_type=CodeReview,
            instructions=instructions,
            config=config,
            name="CodeReviewerAgent"
        )
    
    async def review(
        self,
        code: str,
        context: str = "",
        check_security: bool = True,
        check_performance: bool = True
    ) -> CodeReview:
        """
        Perform comprehensive code review.
        
        Args:
            code: Code to review
            context: Additional context about the code's purpose
            check_security: Whether to perform security analysis
            check_performance: Whether to analyze performance
        
        Returns:
            CodeReview with detailed findings
        
        Example:
            ```python
            review = await agent.review(
                code=my_code,
                context="This is a REST API endpoint for user authentication"
            )
            
            print(f"Quality Score: {review.score}/10")
            print(f"Approved: {review.approved}")
            ```
        """
        prompt = f"""Review the following code:

{f'Context: {context}' if context else ''}

Code to review:
```python
{code}
```

Perform a comprehensive review including:
- Bug detection and logic errors
{f'- Security analysis (SQL injection, XSS, auth issues)' if check_security else ''}
{f'- Performance analysis (complexity, optimization)' if check_performance else ''}
- Code quality and style
- Error handling
- Documentation quality

Provide:
1. List of issues (severity, description, suggestion)
2. Code strengths
3. Suggested improvements
4. Security concerns (if applicable)
5. Performance notes (if applicable)
6. Overall quality assessment and approval decision
"""
        
        return await self.run(prompt)
    
    async def quick_review(self, code: str) -> bool:
        """
        Quick approval check without detailed analysis.
        
        Args:
            code: Code to review
        
        Returns:
            True if approved, False otherwise
        """
        review = await self.review(code, check_security=False, check_performance=False)
        return review.approved
    
    async def security_audit(self, code: str) -> List[CodeIssue]:
        """
        Focused security audit.
        
        Args:
            code: Code to audit
        
        Returns:
            List of security issues
        """
        prompt = f"""Perform a security audit on this code:

```python
{code}
```

Focus on:
- SQL injection vulnerabilities
- XSS (Cross-Site Scripting)
- Authentication/Authorization flaws
- Secrets in code
- Input validation
- File system access
- Command injection
- Insecure dependencies

Return only security-related issues with severity and suggestions.
"""
        
        review = await self.run(prompt)
        return [issue for issue in review.issues if issue.category == "security"]
    
    async def compare_implementations(
        self,
        code_v1: str,
        code_v2: str
    ) -> CodeReview:
        """
        Compare two implementations and recommend the better one.
        
        Args:
            code_v1: First implementation
            code_v2: Second implementation
        
        Returns:
            CodeReview with comparison
        """
        prompt = f"""Compare these two implementations:

Implementation 1:
```python
{code_v1}
```

Implementation 2:
```python
{code_v2}
```

Analyze:
- Which is more correct?
- Which has better performance?
- Which is more readable?
- Which is more maintainable?

Recommend the better implementation and explain why.
"""
        
        return await self.run(prompt)


# Convenience functions
async def review_code(code: str, model: str = "ollama:deepseek-r1:8b") -> CodeReview:
    """
    Quick function to review code without creating agent instance.
    
    Example:
        ```python
        from src.pydantic_agents import review_code
        
        review = await review_code(my_code)
        if review.approved:
            print("✅ Code approved!")
        ```
    """
    agent = CodeReviewerAgent(model=model)
    return await agent.review(code)


def review_code_sync(code: str, model: str = "ollama:deepseek-r1:8b") -> CodeReview:
    """Synchronous version of review_code()"""
    import asyncio
    return asyncio.run(review_code(code, model))
