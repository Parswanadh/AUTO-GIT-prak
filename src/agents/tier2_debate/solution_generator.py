"""
Solution Generator Agent
Proposes novel solutions to research problems.
"""

import json
from typing import List, Optional

from src.models.schemas import ProblemStatement, SolutionProposal
from src.utils.logger import get_logger
from src.utils.ollama_client import get_ollama_client
from src.llm.hybrid_router import HybridRouter
from src.llm.multi_backend_manager import get_backend_manager
from src.llm.free_tier_optimizer import get_free_tier_optimizer
from src.utils.json_parser import safe_parse_solutions
from src.agents.tier2_debate.prompts import get_solution_generator_prompt
from src.pipeline.state import AgentState, add_warning

logger = get_logger("solution_generator")


async def generate_solutions(
    problem: ProblemStatement,
    iteration: int = 1,
    previous_critique: str = None,
    router: Optional[HybridRouter] = None
) -> List[SolutionProposal]:
    """
    Generate novel solutions to a problem.
    
    Args:
        problem: Problem statement
        iteration: Which iteration (1, 2, 3)
        previous_critique: Feedback from critic (if any)
        router: Optional HybridRouter instance (creates one if None)
    
    Returns:
        List of solution proposals
    """
    logger.info(f"💡 Generating solutions (iteration {iteration})...")
    
    # Use multi-backend router for better model access
    if router is None:
        manager = get_backend_manager()
        router = HybridRouter(manager)
    
    # Get optimal free backend
    optimizer = get_free_tier_optimizer()
    optimal_backend = optimizer.get_optimal_backend(
        task_type="code_generation",
        prefer_speed=False  # Prefer quality for solutions
    )
    
    # Use centralized prompt
    prompt = get_solution_generator_prompt(problem, iteration, previous_critique)
    
    # Convert to messages format
    messages = [
        {"role": "system", "content": "You are an expert AI researcher proposing novel solutions."},
        {"role": "user", "content": prompt}
    ]

    try:
        # Use hybrid router with free-tier optimization
        result = await router.generate_with_fallback(
            task_type="code_generation",
            messages=messages,
            temperature=0.8,  # Higher for creativity
            max_tokens=8192
        )
        
        if not result or not result.success:
            logger.error(f"Generation failed: {result.error if result else 'No result'}")
            return []
        
        # Record usage for free-tier tracking
        optimizer.record_usage(result.backend, result.model, result.tokens)
        
        content = result.content or ""
        
        # Log what we got for debugging
        logger.info("="*60)
        logger.info(f"RAW OUTPUT FROM {result.backend}/{result.model} ({len(content)} chars, {result.latency:.2f}s):")
        logger.info(content[:500] if len(content) > 500 else content)
        logger.info("="*60)
        
        # Use robust parser
        solutions_data = safe_parse_solutions(content, iteration)
        
        if not solutions_data:
            logger.error("No valid solutions parsed from response")
            return []
        
        # Create SolutionProposal objects
        solutions = []
        for i, sol_data in enumerate(solutions_data[:3], 1):  # Max 3
            try:
                solution = SolutionProposal(**sol_data)
                solutions.append(solution)
                logger.info(f"  {i}. {solution.approach_name}")
            except Exception as e:
                logger.warning(f"Failed to create solution {i}: {e}")
                continue
        
        logger.info(f"✅ Generated {len(solutions)} solutions")
        return solutions
        
    except Exception as e:
        logger.error(f"Solution generation failed: {e}")
        return []


async def solution_generator_node(state: AgentState) -> AgentState:
    """
    LangGraph node for solution generation.
    
    Args:
        state: Pipeline state
    
    Returns:
        Updated state with solution_proposals
    """
    problem = state.get("problem_statement")
    if not problem:
        logger.error("No problem statement in state")
        return state
    
    iteration = state.get("debate_iteration", 1)
    previous_critique = state.get("latest_critique")
    
    solutions = await generate_solutions(problem, iteration, previous_critique)
    
    if solutions:
        state["solution_proposals"] = solutions
        logger.info(f"✅ Proposed {len(solutions)} solutions")
    else:
        state = add_warning(state, "Solution generation failed", tier=2)
    
    return state
