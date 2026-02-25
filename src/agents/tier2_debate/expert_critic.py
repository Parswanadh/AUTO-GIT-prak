"""
Expert Critic Agent
Reviews and critiques solution proposals.
"""

import json
from typing import Optional

from src.models.schemas import SolutionProposal, CritiqueReport, ProblemStatement
from src.utils.logger import get_logger
from src.llm.hybrid_router import HybridRouter
from src.llm.multi_backend_manager import get_backend_manager
from src.llm.free_tier_optimizer import get_free_tier_optimizer
from src.utils.json_parser import safe_parse_critique
from src.agents.tier2_debate.prompts import get_expert_critic_prompt
from src.pipeline.state import AgentState

logger = get_logger("expert_critic")


async def critique_solution(
    solution: SolutionProposal,
    problem: ProblemStatement,
    router: Optional[HybridRouter] = None
) -> Optional[CritiqueReport]:
    """
    Critique a solution proposal.
    
    Args:
        solution: Solution to critique
        problem: Original problem
        router: Optional HybridRouter instance (creates one if None)
    
    Returns:
        CritiqueReport or None on error
    """
    logger.info(f"🔍 Critiquing: {solution.approach_name}...")
    
    # Use multi-backend router for better model access
    if router is None:
        manager = get_backend_manager()
        router = HybridRouter(manager)
    
    # Get optimal free backend for critique (reasoning task)
    optimizer = get_free_tier_optimizer()
    optimal_backend = optimizer.get_optimal_backend(
        task_type="reasoning",
        prefer_speed=False  # Prefer quality for critiques
    )
    
    # Build prompt (not f-string to avoid brace escaping issues)
    prompt = """You are a senior AI researcher peer-reviewing a proposed solution.
Be thorough, critical, and constructive.

PROBLEM:
""" + problem.challenge + """

Limitations of Current Solutions:
""" + '\n'.join(f"- {lim}" for lim in problem.limitations) + """

PROPOSED SOLUTION:
Name: """ + solution.approach_name + """
Innovation: """ + solution.key_innovation + """
Architecture: """ + solution.architecture_design + """
Implementation: """ + str(solution.implementation_plan) + """
Expected Advantages: """ + ', '.join(solution.expected_advantages) + """

EVALUATE:
1. Technical Soundness: Is the approach theoretically valid?
2. Novelty: Is this truly different from existing work?
3. Feasibility: Can this be implemented in PyTorch realistically?
4. Efficiency: What's the computational cost?
5. Scalability: Will this work on large datasets?
6. Real-world Applicability: Is this practical?

Be harsh but fair. Find the flaws.

CRITICAL: Output ONLY a JSON object. No text before or after.
Start with { and end with }

JSON format:
{
  "overall_assessment": "promising|needs-work|flawed",
  "strengths": ["strength 1", "strength 2"],
  "weaknesses": ["weakness 1", "weakness 2"],
  "technical_concerns": ["concern 1", "concern 2"],
  "missing_considerations": ["missing 1", "missing 2"],
  "real_world_feasibility": 7.5,
  "optimization_suggestions": ["suggestion 1", "suggestion 2"],
  "verdict": "accept|revise|reject"
}"""

    # Convert to messages format
    messages = [
        {"role": "system", "content": "You are a senior AI researcher peer-reviewing a proposed solution."},
        {"role": "user", "content": prompt}
    ]

    try:
        # Use hybrid router with free-tier optimization
        result = await router.generate_with_fallback(
            task_type="reasoning",
            messages=messages,
            temperature=0.4,  # Balanced for critique
            max_tokens=4096
        )
        
        if not result or not result.success:
            logger.error(f"Critique generation failed: {result.error if result else 'No result'}")
            return None
        
        # Record usage for free-tier tracking
        optimizer.record_usage(result.backend, result.model, result.tokens)
        
        content = result.content or ""
        
        # Log what we got
        logger.info("="*60)
        logger.info(f"RAW CRITIQUE FROM {result.backend}/{result.model} ({len(content)} chars, {result.latency:.2f}s):")
        logger.info(content[:500] if len(content) > 500 else content)
        logger.info("="*60)
        
        # Parse JSON
        try:
            # Try to extract JSON from markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            # Try to find JSON
            if content.strip().startswith('{'):
                critique_data = json.loads(content)
            else:
                import re
                json_match = re.search(r'{.*}', content, re.DOTALL)
                if json_match:
                    critique_data = json.loads(json_match.group(0))
                else:
                    raise json.JSONDecodeError("No JSON found", content, 0)
            
            critique = CritiqueReport(**critique_data)
            
            logger.info(f"  Assessment: {critique.overall_assessment}")
            logger.info(f"  Verdict: {critique.verdict}")
            logger.info(f"  Feasibility: {critique.real_world_feasibility:.1f}/10")
            logger.info(f"  Strengths: {len(critique.strengths)} | Weaknesses: {len(critique.weaknesses)}")
            
            return critique
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse critique: {e}")
            logger.debug(f"Raw response: {content[:500]}...")
            
            # Fallback critique
            return CritiqueReport(
                overall_assessment="needs-work",
                strengths=["See response for details"],
                weaknesses=["See response for details"],
                technical_concerns=[],
                missing_considerations=[],
                real_world_feasibility=5.0,
                optimization_suggestions=[],
                verdict="revise"
            )
        
    except Exception as e:
        logger.error(f"Critique generation failed: {e}")
        return None


async def expert_critic_node(state: AgentState) -> AgentState:
    """
    LangGraph node for solution critique.
    
    Args:
        state: Pipeline state
    
    Returns:
        Updated state with critiques
    """
    problem = state.get("problem_statement")
    solutions = state.get("solution_proposals", [])
    
    if not problem or not solutions:
        logger.error("Missing problem or solutions in state")
        return state
    
    logger.info(f"🔍 Critiquing {len(solutions)} solutions...")
    
    critiques = []
    for solution in solutions:
        critique = await critique_solution(solution, problem)
        if critique:
            critiques.append((solution, critique))
    
    state["solution_critiques"] = critiques
    logger.info(f"✅ Generated {len(critiques)} critiques")
    
    # Store latest critique text for next iteration
    if critiques:
        best_critique = max(critiques, key=lambda x: x[1].real_world_feasibility)
        state["latest_critique"] = f"""
Verdict: {best_critique[1].verdict}
Weaknesses: {', '.join(best_critique[1].weaknesses)}
Suggestions: {', '.join(best_critique[1].optimization_suggestions)}
"""
    
    return state
