"""
Sequential Agent Orchestrator for Single-Model Multi-Agent System.

Optimized for 8GB VRAM constraint:
- Uses qwen3:4b (4GB VRAM) as primary model
- Uses gemma2:2b (2GB VRAM) for fast routing
- Executes agents sequentially, not in parallel
- Model stays loaded, only system prompts change

Key Innovation: Persona-based specialization instead of multiple models.
Same qwen3:4b model with different system prompts creates specialized behavior.

Architecture:
    Problem → Router (gemma2:2b) → Researcher (qwen3:4b) → Architect (qwen3:4b)
    → Critiques (qwen3:4b × 4 personas) → Consensus (qwen3:4b) → Refiner (qwen3:4b)

Benefits:
- 6x perspective diversity (vs 1 in cloud LLMs)
- 262K context window (2x GPT-4's 128K)
- $0 cost (local inference)
- Sequential execution works within hardware constraints
"""

import asyncio
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from src.utils.ollama_client import OllamaClient, get_ollama_client
from src.llm.hybrid_router import HybridRouter
from src.llm.multi_backend_manager import get_backend_manager
from src.llm.free_tier_optimizer import get_free_tier_optimizer
from src.utils.logger import get_logger
from src.agents.personas import (
    PERSONA_CONFIGS,
    get_persona_prompt,
    get_persona_temperature,
    get_critique_personas,
    PERSONA_WEIGHTS
)

logger = get_logger("sequential_orchestrator")


# ============================================
# DATA STRUCTURES
# ============================================

@dataclass
class CritiqueResult:
    """Result from a single persona critique."""
    persona: str
    content: str
    score: float  # 0-10
    strengths: List[str]
    weaknesses: List[str]
    suggestions: List[str]
    tokens_used: int
    latency_seconds: float


@dataclass
class ConsensusResult:
    """Consensus from multiple critiques."""
    weighted_score: float  # 0-10
    confidence: float  # 0-1
    needs_refinement: bool
    common_strengths: List[str]
    common_weaknesses: List[str]
    disagreement_level: float  # Standard deviation of scores
    all_critiques: List[CritiqueResult] = field(default_factory=list)


@dataclass
class PipelineResult:
    """Result from full research pipeline."""
    final_solution: str
    consensus: ConsensusResult
    research_summary: str
    total_tokens: int
    total_latency: float
    stages_completed: List[str]


# ============================================
# SEQUENTIAL ORCHESTRATOR
# ============================================

class SequentialAgentOrchestrator:
    """
    Execute agents sequentially using qwen3:4b.

    Optimized for 8GB VRAM constraint:
    - Single primary model (qwen3:4b) with multiple personas
    - Fast router model (gemma2:2b) for task classification
    - Sequential execution: model stays loaded, only prompts change

    Key Insight: Same model + different system prompts = specialized agents
    """

    # Model configuration (exact names from ollama list)
    PRIMARY_MODEL = "qwen3:4b"  # 2.5GB VRAM, 262K context
    ROUTER_MODEL = "gemma2:2b"  # 1.6GB VRAM, for fast routing
    EMBEDDING_MODEL = "all-minilm:latest"  # 45MB VRAM

    def __init__(
        self,
        ollama_client: Optional[OllamaClient] = None,
        router: Optional[HybridRouter] = None,
        use_multi_backend: bool = True
    ):
        """
        Initialize sequential orchestrator.

        Args:
            ollama_client: Ollama client (uses singleton if None) - for backward compatibility
            router: HybridRouter for multi-backend support (creates if None and use_multi_backend=True)
            use_multi_backend: If True, use HybridRouter with free-tier optimization
        """
        self.use_multi_backend = use_multi_backend
        
        if use_multi_backend:
            if router is None:
                manager = get_backend_manager()
                self.router = HybridRouter(manager)
            else:
                self.router = router
            self.optimizer = get_free_tier_optimizer()
            self.client = None  # Not used when multi-backend enabled
            logger.info("SequentialAgentOrchestrator: Using multi-backend with free-tier optimization")
        else:
            self.client = ollama_client or get_ollama_client()
            self.router = None
            self.optimizer = None
            logger.info("SequentialAgentOrchestrator: Using local Ollama only")
        
        self._loaded_model = None

        logger.info(
            f"SequentialAgentOrchestrator initialized: "
            f"primary={self.PRIMARY_MODEL}, router={self.ROUTER_MODEL}"
        )

    async def execute_with_persona(
        self,
        task: str,
        persona: str,
        context: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute task with specified persona.

        Uses same model (qwen3:4b) with different system prompts.
        Model stays loaded, only prompt changes (~0.5s overhead).

        Args:
            task: Task description
            persona: Persona name (from personas.py)
            context: Additional context (problem, solution, etc.)
            temperature: Override persona temperature (optional)
            max_tokens: Override persona max tokens (optional)
            **kwargs: Additional generation parameters

        Returns:
            Response dict with content, tokens, latency
        """
        start_time = time.time()

        # Validate persona
        if not get_persona_prompt(persona):
            raise ValueError(f"Unknown persona: {persona}")

        # Build prompt with context
        prompt = self._build_prompt(task, persona, context)

        # Get persona configuration (with overrides)
        if temperature is None:
            temperature = get_persona_temperature(persona)
        if max_tokens is None:
            max_tokens = PERSONA_CONFIGS[persona].max_tokens

        # Execute with multi-backend or local-only
        if self.use_multi_backend and self.router:
            # Use HybridRouter with free-tier optimization
            optimal_backend = self.optimizer.get_optimal_backend(
                task_type="reasoning",  # Personas typically do reasoning
                prefer_speed=False
            )
            
            messages = [
                {"role": "system", "content": get_persona_prompt(persona)},
                {"role": "user", "content": prompt}
            ]
            
            result_obj = await self.router.generate_with_fallback(
                task_type="reasoning",
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            if not result_obj or not result_obj.success:
                logger.error(f"Multi-backend generation failed: {result_obj.error if result_obj else 'No result'}")
                return {"content": "", "error": result_obj.error if result_obj else "Generation failed"}
            
            # Record usage
            self.optimizer.record_usage(result_obj.backend, result_obj.model, result_obj.tokens)
            
            response_content = result_obj.content or ""
            response_tokens = result_obj.tokens
        else:
            # Use local Ollama client (original behavior)
            response = await self.client.generate(
                model=self.PRIMARY_MODEL,
                prompt=prompt,
                system=get_persona_prompt(persona),
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            response_content = response["content"]
            response_tokens = response.get("tokens_used", 0)

        latency = time.time() - start_time

        result = {
            "content": response_content,
            "model": self.PRIMARY_MODEL,
            "persona": persona,
            "tokens_used": response_tokens,
            "latency_seconds": latency,
            "load_duration": 0 if self.use_multi_backend else (response.get("load_duration", 0) / 1e9)
        }

        logger.info(
            f"[{persona}] Generated {result['tokens_used']} tokens "
            f"in {latency:.2f}s"
        )

        return result

    async def execute_pipeline(
        self,
        problem: Dict[str, Any],
        max_refinements: int = 1
    ) -> PipelineResult:
        """
        Execute full research pipeline sequentially.

        Pipeline stages:
        1. Research (qwen3:4b with researcher persona)
        2. Generate solution (qwen3:4b with architect persona)
        3. Critique from 4 perspectives (qwen3:4b × 4 personas)
        4. Build consensus (weighted voting)
        5. Refine if needed (qwen3:4b with architect persona)

        Args:
            problem: Problem dict with domain, challenge, limitations, etc.
            max_refinements: Maximum refinement iterations

        Returns:
            PipelineResult with final solution and metadata
        """
        total_tokens = 0
        total_latency = 0
        stages_completed = []

        logger.info(f"Starting research pipeline for: {problem.get('challenge', 'Unknown')[:50]}...")
        start_time = time.time()

        # Stage 1: Research
        logger.info("[Stage 1/5] Researching literature and related work...")
        research_result = await self._research_stage(problem)
        total_tokens += research_result["tokens_used"]
        total_latency += research_result["latency_seconds"]
        stages_completed.append("research")

        # Stage 2: Generate initial solution
        logger.info("[Stage 2/5] Generating solution proposal...")
        solution_result = await self._generate_stage(problem, research_result["content"])
        total_tokens += solution_result["tokens_used"]
        total_latency += solution_result["latency_seconds"]
        stages_completed.append("generate")
        initial_solution = solution_result["content"]

        # Stage 3: Critique from 4 perspectives
        logger.info("[Stage 3/5] Running multi-perspective critique...")
        critiques = await self._critique_stage(initial_solution, problem)
        for critique in critiques:
            total_tokens += critique.tokens_used
            total_latency += critique.latency_seconds
        stages_completed.append("critique")

        # Stage 4: Build consensus
        logger.info("[Stage 4/5] Building consensus from critiques...")
        consensus = await self._consensus_stage(critiques)
        stages_completed.append("consensus")

        # Stage 5: Refine if needed
        final_solution = initial_solution
        if consensus.needs_refinement and max_refinements > 0:
            logger.info(f"[Stage 5/5] Refining solution (score: {consensus.weighted_score:.1f}/10)...")
            refine_result = await self._refine_stage(
                initial_solution,
                problem,
                consensus
            )
            total_tokens += refine_result["tokens_used"]
            total_latency += refine_result["latency_seconds"]
            final_solution = refine_result["content"]
            stages_completed.append("refine")
        else:
            logger.info(f"[Stage 5/5] Solution acceptable (score: {consensus.weighted_score:.1f}/10), skipping refine")

        total_latency = time.time() - start_time

        logger.info(
            f"Pipeline complete: {total_tokens} tokens, {total_latency:.1f}s, "
            f"{len(stages_completed)} stages"
        )

        return PipelineResult(
            final_solution=final_solution,
            consensus=consensus,
            research_summary=research_result["content"],
            total_tokens=total_tokens,
            total_latency=total_latency,
            stages_completed=stages_completed
        )

    async def _research_stage(self, problem: Dict[str, Any]) -> Dict[str, Any]:
        """Stage 1: Research literature and identify gaps."""
        task = f"""Research and analyze this problem:

DOMAIN: {problem.get('domain', 'Unknown')}
CHALLENGE: {problem.get('challenge', 'Unknown')}

Current Solutions:
{chr(10).join(f'- {s}' for s in problem.get('current_solutions', []))}

Limitations:
{chr(10).join(f'- {l}' for l in problem.get('limitations', []))}

Tasks:
1. Identify key related research areas
2. Find promising approaches not yet explored
3. Highlight connections between different research threads
4. Specify genuine research gaps

Provide a comprehensive research summary."""
        return await self.execute_with_persona(task, "researcher", context=problem)

    async def _generate_stage(
        self,
        problem: Dict[str, Any],
        research_summary: str
    ) -> Dict[str, Any]:
        """Stage 2: Generate solution proposal."""
        task = f"""Design a solution to this challenge:

PROBLEM: {problem.get('challenge', 'Unknown')}

RESEARCH CONTEXT:
{research_summary}

REQUIREMENTS:
{chr(10).join(f'- {r}' for r in problem.get('requirements', []))}

Design a comprehensive solution that:
1. Addresses the core challenge
2. Leverages insights from related research
3. Is technically sound and implementable
4. Considers computational constraints
5. Has a clear path to production

Provide detailed architecture and implementation plan."""
        return await self.execute_with_persona(
            task,
            "architect",
            context={**problem, "research_summary": research_summary}
        )

    async def _critique_stage(
        self,
        solution: str,
        problem: Dict[str, Any]
    ) -> List[CritiqueResult]:
        """Stage 3: Critique from multiple perspectives (sequential)."""
        critiques = []
        personas = get_critique_personas()

        task = f"""Critique this solution:

PROBLEM: {problem.get('challenge', 'Unknown')}

PROPOSED SOLUTION:
{solution}

Provide:
1. Overall score (0-10)
2. Key strengths (3-5 points)
3. Critical weaknesses (2-4 points)
4. Specific improvements (3-5 suggestions)

Be thorough but constructive."""

        for i, persona in enumerate(personas):
            logger.info(f"  Running {persona} critique ({i+1}/{len(personas)})...")
            result = await self.execute_with_persona(
                task,
                persona,
                context={"solution": solution, "problem": problem}
            )

            # Parse critique to extract structured info
            critique = self._parse_critique(result, persona)
            critiques.append(critique)

        return critiques

    async def _consensus_stage(self, critiques: List[CritiqueResult]) -> ConsensusResult:
        """Stage 4: Build weighted consensus from critiques."""
        import statistics

        # Calculate weighted score
        weighted_score = sum(
            c.score * PERSONA_WEIGHTS[c.persona]
            for c in critiques
        )

        # Measure disagreement (standard deviation of scores)
        scores = [c.score for c in critiques]
        disagreement = statistics.stdev(scores) if len(scores) > 1 else 0.0

        # Calculate confidence (inverse of disagreement)
        confidence = max(0.0, 1.0 - (disagreement / 5.0))

        # Identify common strengths and weaknesses
        common_strengths = self._find_common_items([c.strengths for c in critiques])
        common_weaknesses = self._find_common_items([c.weaknesses for c in critiques])

        # Determine if refinement needed
        needs_refinement = weighted_score < 7.5 or disagreement > 2.0

        return ConsensusResult(
            weighted_score=weighted_score,
            confidence=confidence,
            needs_refinement=needs_refinement,
            common_strengths=common_strengths,
            common_weaknesses=common_weaknesses,
            disagreement_level=disagreement,
            all_critiques=critiques
        )

    async def _refine_stage(
        self,
        solution: str,
        problem: Dict[str, Any],
        consensus: ConsensusResult
    ) -> Dict[str, Any]:
        """Stage 5: Refine solution based on consensus feedback."""
        task = f"""Refine this solution based on critiques:

ORIGINAL SOLUTION:
{solution}

CONSENSUS FEEDBACK:
Weighted Score: {consensus.weighted_score:.1f}/10
Confidence: {consensus.confidence:.1%}

Common Strengths:
{chr(10).join(f'- {s}' for s in consensus.common_strengths)}

Common Weaknesses:
{chr(10).join(f'- {w}' for w in consensus.common_weaknesses)}

ALL CRITIQUES:
{self._format_all_critiques(consensus.all_critiques)}

Refine the solution to:
1. Address the common weaknesses
2. Incorporate the best suggestions
3. Maintain the strengths
4. Improve the overall score to 8+/10

Provide the refined solution with clear explanations of changes made."""
        return await self.execute_with_persona(
            task,
            "architect",
            context={
                "solution": solution,
                "problem": problem,
                "consensus": consensus
            }
        )

    def _build_prompt(
        self,
        task: str,
        persona: str,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Build full prompt with context."""
        if not context:
            return task

        # Add relevant context to prompt
        context_str = ""
        if "problem" in context:
            context_str += f"PROBLEM: {context['problem']}\n\n"
        if "solution" in context:
            context_str += f"SOLUTION: {context['solution']}\n\n"
        if "research_summary" in context:
            context_str += f"RESEARCH: {context['research_summary']}\n\n"
        if "consensus" in context:
            context_str += f"FEEDBACK: Score {context['consensus'].weighted_score:.1f}/10\n"

        return context_str + task

    def _parse_critique(self, result: Dict[str, Any], persona: str) -> CritiqueResult:
        """Parse critique response to extract structured information."""
        content = result["content"]

        # Simple parsing (can be enhanced with structured output)
        # Try to extract score from response
        score = 7.0  # Default
        import re
        score_match = re.search(r'score[:\s]+(\d+(?:\.\d+)?)', content, re.IGNORECASE)
        if score_match:
            score = float(score_match.group(1))

        # Extract strengths, weaknesses, suggestions
        strengths = []
        weaknesses = []
        suggestions = []

        lines = content.split('\n')
        current_section = None
        for line in lines:
            line_lower = line.lower()
            if 'strength' in line_lower or 'pro' in line_lower:
                current_section = 'strengths'
            elif 'weakness' in line_lower or 'con' in line_lower or 'issue' in line_lower:
                current_section = 'weaknesses'
            elif 'suggest' in line_lower or 'improve' in line_lower or 'recommend' in line_lower:
                current_section = 'suggestions'
            elif line.strip().startswith(('-', '*', '•', '1.', '2.', '3.', '4.', '5.')):
                item = line.strip().lstrip('-*•123456789.')
                item = item.strip('. ')
                if item:
                    if current_section == 'strengths':
                        strengths.append(item[:100])  # Truncate long items
                    elif current_section == 'weaknesses':
                        weaknesses.append(item[:100])
                    elif current_section == 'suggestions':
                        suggestions.append(item[:100])

        return CritiqueResult(
            persona=persona,
            content=content,
            score=score,
            strengths=strengths or ["No specific strengths listed"],
            weaknesses=weaknesses or ["No specific weaknesses listed"],
            suggestions=suggestions or ["No specific suggestions"],
            tokens_used=result["tokens_used"],
            latency_seconds=result["latency_seconds"]
        )

    def _find_common_items(self, item_lists: List[List[str]]) -> List[str]:
        """Find items that appear in multiple lists."""
        if not item_lists:
            return []

        # Count item occurrences (fuzzy matching)
        from collections import Counter
        all_items = []
        for lst in item_lists:
            all_items.extend([item.lower().strip() for item in lst])

        # Items appearing 2+ times are "common"
        counter = Counter(all_items)
        return [item for item, count in counter.items() if count >= 2]

    def _format_all_critiques(self, critiques: List[CritiqueResult]) -> str:
        """Format all critiques for display."""
        formatted = []
        for c in critiques:
            formatted.append(f"\n[{c.persona.upper()}] Score: {c.score}/10")
            formatted.append(f"Strengths: {', '.join(c.strengths[:3])}")
            formatted.append(f"Weaknesses: {', '.join(c.weaknesses[:3])}")
        return '\n'.join(formatted)


# ============================================
# UTILITY FUNCTIONS
# ============================================

def create_orchestrator() -> SequentialAgentOrchestrator:
    """Create a new SequentialAgentOrchestrator instance."""
    return SequentialAgentOrchestrator()


async def quick_critique(
    solution: str,
    problem: Dict[str, Any]
) -> ConsensusResult:
    """
    Quick critique without full pipeline.

    Useful for rapid iteration on existing solutions.
    """
    orchestrator = create_orchestrator()
    critiques = await orchestrator._critique_stage(solution, problem)
    return await orchestrator._consensus_stage(critiques)
