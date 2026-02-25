"""
Debate Moderator Agent
Orchestrates multi-round debate between generator and critic.
"""

from datetime import datetime
from typing import Optional

from src.models.schemas import (
    SolutionProposal, CritiqueReport, DebateRound, FinalSolution, ProblemStatement
)
from src.utils.logger import get_logger
from src.llm.hybrid_router import HybridRouter
from src.llm.multi_backend_manager import get_backend_manager
from src.agents.tier2_debate.solution_generator import generate_solutions
from src.agents.tier2_debate.expert_critic import critique_solution
from src.agents.tier2_debate.multi_critic_consensus import MultiCriticPanel, evaluate_with_consensus
from src.pipeline.state import AgentState, update_state_status

logger = get_logger("debate_moderator")


MAX_DEBATE_ROUNDS = 3
ACCEPTANCE_THRESHOLD = 7.5
USE_MULTI_CRITIC = True  # Enable multi-critic consensus


async def moderate_debate(
    problem: ProblemStatement,
    max_rounds: int = MAX_DEBATE_ROUNDS,
    router: Optional[HybridRouter] = None
) -> Optional[FinalSolution]:
    """
    Facilitate debate between generator and critic.
    
    Args:
        problem: Problem to solve
        max_rounds: Maximum debate rounds
        router: Optional HybridRouter instance (creates one if None)
    
    Returns:
        FinalSolution after consensus or max rounds
    """
    logger.info(f"🎭 Starting debate (max {max_rounds} rounds)...")
    
    # Use shared router for all debate agents
    if router is None:
        manager = get_backend_manager()
        router = HybridRouter(manager)
    
    debate_history = []
    best_solution = None
    best_feasibility = 0.0
    previous_critique = None
    
    for round_num in range(1, max_rounds + 1):
        logger.info(f"\n{'='*60}")
        logger.info(f"🔄 DEBATE ROUND {round_num}/{max_rounds}")
        logger.info(f"{'='*60}\n")
        
        # Generator proposes solutions (pass shared router)
        solutions = await generate_solutions(problem, round_num, previous_critique, router)
        
        if not solutions:
            logger.error(f"No solutions generated in round {round_num}")
            break
        
        # Review each solution with multi-critic consensus or single critic
        logger.info(f"\n🔍 {'Multi-critic panel' if USE_MULTI_CRITIC else 'Critic'} reviewing {len(solutions)} proposals...")
        
        if USE_MULTI_CRITIC:
            # Use multi-critic consensus for more robust evaluation
            panel = MultiCriticPanel(router=router)
            
            for solution in solutions:
                consensus = await panel.evaluate_solution(solution, problem)
                
                if not consensus:
                    continue
                
                # Create critique from consensus (for compatibility)
                critique = CritiqueReport(
                    overall_assessment=consensus.recommendation,
                    strengths=consensus.common_strengths,
                    weaknesses=consensus.common_weaknesses,
                    technical_concerns=[c[:100] for c in consensus.contentious_points],
                    missing_considerations=[],
                    real_world_feasibility=consensus.avg_feasibility,
                    optimization_suggestions=[op.critique.optimization_suggestions[0] for op in consensus.individual_critiques if op.critique.optimization_suggestions][:3],
                    verdict=consensus.recommendation
                )
                
                # Record this round
                round_data = DebateRound(
                    round_number=round_num,
                    solution=solution,
                    critique=critique
                )
                debate_history.append(round_data)
                
                # Track best solution
                if consensus.avg_feasibility > best_feasibility:
                    best_feasibility = consensus.avg_feasibility
                    best_solution = solution
                
                # Check for acceptance (with higher threshold for multi-critic)
                if consensus.recommendation == "accept" and consensus.avg_feasibility >= ACCEPTANCE_THRESHOLD and consensus.agreement_level >= 0.7:
                    logger.info(f"\n🎉 MULTI-CRITIC CONSENSUS REACHED!")
                    logger.info(f"   Solution: {solution.approach_name}")
                    logger.info(f"   Avg Feasibility: {consensus.avg_feasibility:.1f}/10")
                    logger.info(f"   Agreement Level: {consensus.agreement_level:.1%}")
                    logger.info(f"   Confidence: {consensus.confidence:.1%}")
                    logger.info(f"   Rounds taken: {round_num}")
                    
                    return FinalSolution(
                        solution=solution,
                        debate_history=debate_history,
                        consensus_reached=True,
                        confidence_score=consensus.consensus_score,
                        iterations_taken=round_num,
                        final_verdict=f"Accepted by multi-critic panel after {round_num} rounds (agreement={consensus.agreement_level:.1%})"
                    )
        else:
            # Original single-critic approach
            for solution in solutions:
                critique = await critique_solution(solution, problem, router)
            
            if not critique:
                continue
            
            # Record this round
            round_data = DebateRound(
                round_number=round_num,
                solution=solution,
                critique=critique
            )
            debate_history.append(round_data)
            
            # Track best solution
            if critique.real_world_feasibility > best_feasibility:
                best_feasibility = critique.real_world_feasibility
                best_solution = solution
            
            # Check for acceptance
            if critique.verdict == "accept" and critique.real_world_feasibility >= ACCEPTANCE_THRESHOLD:
                logger.info(f"\n🎉 CONSENSUS REACHED!")
                logger.info(f"   Solution: {solution.approach_name}")
                logger.info(f"   Feasibility: {critique.real_world_feasibility:.1f}/10")
                logger.info(f"   Rounds taken: {round_num}")
                
                return FinalSolution(
                    solution=solution,
                    debate_history=debate_history,
                    consensus_reached=True,
                    confidence_score=critique.real_world_feasibility,
                    iterations_taken=round_num,
                    final_verdict=f"Accepted after {round_num} rounds of refinement"
                )
        
        # Prepare feedback for next round
        if debate_history:
            latest_critique = debate_history[-1].critique
            previous_critique = f"""
Previous Verdict: {latest_critique.verdict}
Key Weaknesses: {', '.join(latest_critique.weaknesses[:3])}
Top Suggestions: {', '.join(latest_critique.optimization_suggestions[:3])}
Feasibility Score: {latest_critique.real_world_feasibility}/10

Improve on these specific issues in your next proposal.
"""
            logger.info(f"\n💬 Feedback for Round {round_num + 1}:")
            logger.info(f"   Verdict: {latest_critique.verdict}")
            logger.info(f"   Top Issues: {', '.join(latest_critique.weaknesses[:2])}")
    
    # Max rounds reached without acceptance
    logger.warning(f"\n⚠️  Max rounds ({max_rounds}) reached without full consensus")
    
    if best_solution:
        logger.info(f"   Best solution: {best_solution.approach_name}")
        logger.info(f"   Feasibility: {best_feasibility:.1f}/10")
        
        return FinalSolution(
            solution=best_solution,
            debate_history=debate_history,
            consensus_reached=False,
            confidence_score=best_feasibility,
            iterations_taken=max_rounds,
            final_verdict=f"Best solution after {max_rounds} rounds (no full consensus)"
        )
    
    logger.error("❌ Debate failed - no viable solutions")
    return None


async def debate_moderator_node(state: AgentState) -> AgentState:
    """
    LangGraph node for debate moderation.
    
    Args:
        state: Pipeline state
    
    Returns:
        Updated state with final_solution
    """
    problem = state.get("problem_statement")
    
    if not problem:
        logger.error("No problem statement in state")
        return state
    
    logger.info("🎭 Debate Moderator: Starting multi-round debate...")
    
    final_solution = await moderate_debate(problem, max_rounds=MAX_DEBATE_ROUNDS)
    
    if final_solution:
        state["final_solution"] = final_solution
        state = update_state_status(state, "solution_finalized", f"Debate completed - {final_solution.solution.approach_name}")
        
        logger.info(f"\n{'='*60}")
        logger.info("✅ DEBATE COMPLETE")
        logger.info(f"{'='*60}")
        logger.info(f"Solution: {final_solution.solution.approach_name}")
        logger.info(f"Consensus: {'YES' if final_solution.consensus_reached else 'NO'}")
        logger.info(f"Confidence: {final_solution.confidence_score:.1f}/10")
        logger.info(f"Iterations: {final_solution.iterations_taken}")
        logger.info(f"Verdict: {final_solution.final_verdict}")
        logger.info(f"{'='*60}\n")
    else:
        logger.error("❌ Debate failed to produce solution")
    
    return state


def should_continue_debate(state: AgentState) -> str:
    """
    Conditional edge: Check if debate should continue.
    
    Args:
        state: Pipeline state
    
    Returns:
        Next node name
    """
    final_solution = state.get("final_solution")
    
    if not final_solution:
        return "END"  # Failed
    
    if final_solution.consensus_reached and final_solution.confidence_score >= ACCEPTANCE_THRESHOLD:
        return "real_world_validator"  # Proceed to validation
    elif final_solution.confidence_score >= 6.0:
        return "real_world_validator"  # Marginal - validate anyway
    else:
        logger.warning(f"Solution quality too low ({final_solution.confidence_score:.1f}/10)")
        return "paper_scout"  # Try next paper
