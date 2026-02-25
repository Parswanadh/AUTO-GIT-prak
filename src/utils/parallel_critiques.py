"""
Parallel critique generation for multi-agent debate.

Features:
- Concurrent execution of independent persona critiques
- Semaphore-based concurrency control
- Graceful degradation if persona fails
- Aggregate results with timing metrics
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional, TypeVar
import concurrent.futures

from src.utils.logger import get_logger
from src.utils.structured_logging import get_structured_logger
from src.utils.metrics import get_metrics_collector

logger = get_logger("parallel_critiques")
slog = get_structured_logger()
metrics = get_metrics_collector()


class CritiqueStatus(Enum):
    """Status of a critique generation."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class CritiqueResult:
    """
    Result of a single critique generation.

    Attributes:
        persona: Persona that generated the critique
        status: Generation status
        content: Generated critique content
        duration_ms: Generation duration
        error: Error message if failed
        timestamp: Generation timestamp
    """
    persona: dict[str, Any]
    status: CritiqueStatus
    content: Optional[str] = None
    duration_ms: float = 0
    error: Optional[str] = None
    timestamp: float = 0

    def __post_init__(self):
        if self.timestamp == 0:
            self.timestamp = time.time()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "persona": self.persona,
            "status": self.status.value,
            "content": self.content,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "timestamp": self.timestamp,
        }


@dataclass
class DebateResult:
    """
    Result of a multi-persona debate round.

    Attributes:
        round_number: Debate round number
        total_duration_ms: Total duration for all critiques
        results: List of individual critique results
        successful_count: Number of successful critiques
        failed_count: Number of failed critiques
        skipped_count: Number of skipped critiques
        consensus_reached: Whether consensus was reached
    """
    round_number: int
    total_duration_ms: float
    results: list[CritiqueResult] = field(default_factory=list)
    successful_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    consensus_reached: bool = False

    def __post_init__(self):
        self.successful_count = sum(
            1 for r in self.results if r.status == CritiqueStatus.COMPLETED
        )
        self.failed_count = sum(
            1 for r in self.results if r.status == CritiqueStatus.FAILED
        )
        self.skipped_count = sum(
            1 for r in self.results if r.status == CritiqueStatus.SKIPPED
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "round_number": self.round_number,
            "total_duration_ms": self.total_duration_ms,
            "successful_count": self.successful_count,
            "failed_count": self.failed_count,
            "skipped_count": self.skipped_count,
            "consensus_reached": self.consensus_reached,
            "results": [r.to_dict() for r in self.results],
        }


class ParallelCritiqueExecutor:
    """
    Executes persona critiques in parallel.

    Features:
    - Concurrent execution with controlled concurrency
    - Timeout per critique
    - Graceful degradation on failure
    - Detailed timing and error tracking
    """

    def __init__(
        self,
        max_concurrency: int = 5,
        timeout_per_critique: float = 120,
        continue_on_error: bool = True,
    ):
        """
        Initialize parallel critique executor.

        Args:
            max_concurrency: Maximum number of concurrent critiques
            timeout_per_critique: Timeout in seconds for each critique
            continue_on_error: Whether to continue if one critique fails
        """
        self.max_concurrency = max_concurrency
        self.timeout_per_critique = timeout_per_critique
        self.continue_on_error = continue_on_error
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def generate_critique(
        self,
        persona: dict[str, Any],
        content: str,
        context: dict[str, Any],
        critique_fn: Callable,
    ) -> CritiqueResult:
        """
        Generate a single critique with timeout and error handling.

        Args:
            persona: Persona configuration
            content: Content to critique
            context: Additional context
            critique_fn: Async function to generate critique

        Returns:
            CritiqueResult with generation outcome
        """
        start_time = time.time()
        persona_name = persona.get("name", "Unknown")

        logger.debug(f"Starting critique for persona: {persona_name}")

        try:
            async with self._semaphore:
                # Execute with timeout
                result = await asyncio.wait_for(
                    critique_fn(persona, content, context),
                    timeout=self.timeout_per_critique,
                )

                duration_ms = (time.time() - start_time) * 1000

                logger.info(f"✅ Critique completed for {persona_name} in {duration_ms:.1f}ms")

                slog.info(
                    f"Critique completed: {persona_name}",
                    agent=f"critique_{persona_name}",
                    duration_ms=duration_ms,
                    extra={"persona": persona_name},
                )

                return CritiqueResult(
                    persona=persona,
                    status=CritiqueStatus.COMPLETED,
                    content=result,
                    duration_ms=duration_ms,
                )

        except asyncio.TimeoutError:
            duration_ms = (time.time() - start_time) * 1000
            error_msg = f"Critique timed out after {self.timeout_per_critique}s"

            logger.warning(f"⏱️ Critique timed out for {persona_name}")
            slog.warning(
                f"Critique timed out: {persona_name}",
                agent=f"critique_{persona_name}",
                duration_ms=duration_ms,
                error_message=error_msg,
            )

            metrics.record_failure("critique_timeout", error_msg)

            return CritiqueResult(
                persona=persona,
                status=CritiqueStatus.FAILED,
                duration_ms=duration_ms,
                error=error_msg,
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            error_msg = f"{type(e).__name__}: {str(e)[:200]}"

            logger.error(f"❌ Critique failed for {persona_name}: {error_msg}")
            slog.error(
                f"Critique failed: {persona_name}",
                agent=f"critique_{persona_name}",
                duration_ms=duration_ms,
                error_type=type(e).__name__,
                error_message=error_msg,
            )

            metrics.record_failure("critique_generation", error_msg)

            return CritiqueResult(
                persona=persona,
                status=CritiqueStatus.FAILED,
                duration_ms=duration_ms,
                error=error_msg,
            )

    async def execute_debate_round(
        self,
        personas: list[dict[str, Any]],
        content: str,
        context: dict[str, Any],
        critique_fn: Callable,
        round_number: int = 1,
    ) -> DebateResult:
        """
        Execute a full debate round with all personas.

        Args:
            personas: List of persona configurations
            content: Content to critique
            context: Additional context
            critique_fn: Async function to generate critique
            round_number: Debate round number

        Returns:
            DebateResult with all critique outcomes
        """
        start_time = time.time()
        logger.info(f"Starting debate round {round_number} with {len(personas)} personas")

        # Create tasks for all personas
        tasks = [
            self.generate_critique(persona, content, context, critique_fn)
            for persona in personas
        ]

        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any unexpected exceptions from gather
        critique_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Unexpected error in debate round: {result}")
                continue
            if isinstance(result, CritiqueResult):
                critique_results.append(result)

        total_duration_ms = (time.time() - start_time) * 1000

        # Determine if consensus was reached (simple heuristic)
        successful_critiques = [
            r for r in critique_results
            if r.status == CritiqueStatus.COMPLETED and r.content
        ]
        consensus_reached = len(successful_critiques) >= len(personas) * 0.8

        debate_result = DebateResult(
            round_number=round_number,
            total_duration_ms=total_duration_ms,
            results=critique_results,
            consensus_reached=consensus_reached,
        )

        logger.info(
            f"✅ Debate round {round_number} completed in {total_duration_ms:.1f}ms: "
            f"{debate_result.successful_count} successful, "
            f"{debate_result.failed_count} failed, "
            f"{debate_result.skipped_count} skipped"
        )

        slog.info(
            f"Debate round {round_number} completed",
            agent="debate_moderator",
            duration_ms=total_duration_ms,
            extra={
                "round_number": round_number,
                "successful": debate_result.successful_count,
                "failed": debate_result.failed_count,
                "consensus": consensus_reached,
            },
        )

        return debate_result

    async def execute_multi_round_debate(
        self,
        personas: list[dict[str, Any]],
        content: str,
        context: dict[str, Any],
        critique_fn: Callable,
        max_rounds: int = 3,
        consensus_threshold: float = 0.8,
    ) -> list[DebateResult]:
        """
        Execute multiple debate rounds with early exit on consensus.

        Args:
            personas: List of persona configurations
            content: Content to critique
            context: Additional context
            critique_fn: Async function to generate critique
            max_rounds: Maximum number of debate rounds
            consensus_threshold: Consensus threshold (0-1)

        Returns:
            List of DebateResult for each round
        """
        logger.info(f"Starting multi-round debate (max {max_rounds} rounds)")

        all_results = []
        current_content = content

        for round_num in range(1, max_rounds + 1):
            # Update context with previous round results
            context["round"] = round_num
            context["previous_rounds"] = [r.to_dict() for r in all_results]

            # Execute debate round
            result = await self.execute_debate_round(
                personas=personas,
                content=current_content,
                context=context,
                critique_fn=critique_fn,
                round_number=round_num,
            )

            all_results.append(result)

            # Check for early exit
            if result.consensus_reached:
                logger.info(
                    f"✅ Consensus reached in round {round_num}, stopping debate"
                )
                slog.info(
                    f"Consensus reached at round {round_num}",
                    agent="debate_moderator",
                    extra={"round_number": round_num},
                )
                break

            # If too many failures, stop early
            if result.failed_count > len(personas) * 0.5:
                logger.warning(
                    f"⚠️ Too many failures in round {round_num}, stopping debate"
                )
                break

        return all_results


def create_critique_function(llm_client, prompt_template: str) -> Callable:
    """
    Create a critique function that uses an LLM client.

    Args:
        llm_client: LLM client (e.g., OllamaClient)
        prompt_template: Prompt template with placeholders for {persona}, {content}, {context}

    Returns:
        Async function for generating critiques
    """

    async def critique_fn(persona: dict[str, Any], content: str, context: dict[str, Any]) -> str:
        """Generate critique using LLM."""
        prompt = prompt_template.format(
            persona_name=persona.get("name", "Reviewer"),
            persona_role=persona.get("role", "Reviewer"),
            persona_perspective=persona.get("perspective", ""),
            persona_tone=persona.get("tone", "neutral"),
            content=content,
            context=context,
        )

        response = await llm_client.generate(
            model="qwen3:8b",  # Or whatever model you use
            prompt=prompt,
            temperature=0.7,
        )

        return response.get("content", "")

    return critique_fn


# Example usage and testing
async def example_parallel_critiques():
    """
    Example of using parallel critique generation.
    """
    from src.utils.ollama_client import get_ollama_client

    # Sample personas
    personas = [
        {
            "name": "TechnicalReviewer",
            "role": "Technical Reviewer",
            "perspective": "Focuses on code correctness and efficiency",
            "tone": "analytical",
        },
        {
            "name": "SafetyAuditor",
            "role": "Safety Auditor",
            "perspective": "Identifies security vulnerabilities",
            "tone": "cautious",
        },
        {
            "name": "UserAdvocate",
            "role": "User Advocate",
            "perspective": "Evaluates usability and value",
            "tone": "empathetic",
        },
    ]

    # Sample content to critique
    content = """
    def process_data(data):
        result = []
        for item in data:
            if item > 0:
                result.append(item * 2)
        return result
    """

    # Mock critique function (replace with actual LLM call)
    async def mock_critique_fn(persona: dict, content: str, context: dict) -> str:
        await asyncio.sleep(0.5)  # Simulate processing time
        return f"Review from {persona['name']}: The code looks good."

    # Create executor
    executor = ParallelCritiqueExecutor(
        max_concurrency=3,
        timeout_per_critique=10,
    )

    # Execute debate round
    result = await executor.execute_debate_round(
        personas=personas,
        content=content,
        context={},
        critique_fn=mock_critique_fn,
        round_number=1,
    )

    print(f"Debate completed in {result.total_duration_ms:.1f}ms")
    print(f"Successful: {result.successful_count}/{len(personas)}")

    return result


if __name__ == "__main__":
    # Run example
    asyncio.run(example_parallel_critiques())
