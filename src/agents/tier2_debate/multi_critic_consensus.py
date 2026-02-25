"""
Multi-Critic Consensus System

Uses multiple critics with different perspectives to evaluate solutions,
then aggregates their opinions for more robust decision-making.

Features:
- Multiple critic perspectives (technical, practical, security, performance)
- Weighted voting based on critic expertise
- Consensus scoring and confidence metrics
- Disagreement analysis
- Evidence-based aggregation

Architecture:
- CriticPanel: Manages multiple critics
- ConsensusAggregator: Combines critic opinions
- DisagreementAnalyzer: Identifies contentious points
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import statistics

from src.models.schemas import SolutionProposal, CritiqueReport, ProblemStatement
from src.llm.hybrid_router import HybridRouter
from src.llm.multi_backend_manager import get_backend_manager
from src.utils.logger import get_logger

# Import cross-examination prompts for multi-round debates
try:
    from src.agents.meta_learning.cross_examination_prompts import (
        build_initial_critique_prompt,
        build_cross_examination_prompt,
        build_final_refinement_prompt
    )
    CROSS_EXAM_AVAILABLE = True
except ImportError:
    CROSS_EXAM_AVAILABLE = False
    logger.warning("Cross-examination prompts not available")

logger = get_logger("multi_critic_consensus")


@dataclass
class CriticPerspective:
    """Definition of a critic's perspective and expertise."""
    name: str
    role: str
    focus_areas: List[str]
    system_prompt: str
    weight: float = 1.0  # Importance weight in consensus


@dataclass
class CriticOpinion:
    """A single critic's opinion on a solution."""
    perspective: str
    critique: CritiqueReport
    confidence: float  # How confident the critic is (0-1)
    weight: float  # Weight of this critic's opinion


@dataclass
class ConsensusResult:
    """Aggregated consensus from multiple critics."""
    solution: SolutionProposal
    individual_critiques: List[CriticOpinion]
    consensus_score: float  # Overall consensus (0-10)
    confidence: float  # Confidence in consensus (0-1)
    agreement_level: float  # How much critics agree (0-1)
    
    # Aggregated fields
    avg_feasibility: float
    common_strengths: List[str]
    common_weaknesses: List[str]
    contentious_points: List[str]
    
    # Decision
    recommendation: str  # "accept", "revise", "reject"
    reasoning: str


# Define critic perspectives
CRITIC_PERSPECTIVES = [
    CriticPerspective(
        name="technical_architect",
        role="Technical Architect",
        focus_areas=["architecture", "scalability", "maintainability"],
        system_prompt="""You are a senior technical architect reviewing a solution proposal.
        
Focus on:
- Architecture soundness and design patterns
- Scalability and performance implications
- Code maintainability and modularity
- Technical debt and long-term viability

Be rigorous but constructive. Rate feasibility realistically.""",
        weight=1.2  # Higher weight for technical aspects
    ),
    
    CriticPerspective(
        name="security_expert",
        role="Security Expert",
        focus_areas=["security", "privacy", "vulnerabilities"],
        system_prompt="""You are a security expert reviewing a solution proposal.
        
Focus on:
- Security vulnerabilities and attack vectors
- Data privacy and protection
- Authentication and authorization
- Input validation and sanitization

Be thorough in identifying security risks.""",
        weight=1.3  # Highest weight - security is critical
    ),
    
    CriticPerspective(
        name="performance_engineer",
        role="Performance Engineer",
        focus_areas=["performance", "optimization", "efficiency"],
        system_prompt="""You are a performance engineer reviewing a solution proposal.
        
Focus on:
- Computational complexity and efficiency
- Memory usage and optimization
- I/O operations and bottlenecks
- Benchmarking and profiling strategy

Identify performance concerns and optimization opportunities.""",
        weight=1.0
    ),
    
    CriticPerspective(
        name="practical_implementer",
        role="Practical Implementer",
        focus_areas=["feasibility", "implementation", "real-world"],
        system_prompt="""You are a practical engineer who implements solutions.
        
Focus on:
- Real-world implementation feasibility
- Dependencies and external constraints
- Testing and debugging challenges
- Developer experience and tooling

Be pragmatic about what can actually be built.""",
        weight=1.1  # Practical perspective is important
    )
]


class MultiCriticPanel:
    """
    Manages multiple critics with different perspectives for consensus-based evaluation.
    """
    
    def __init__(
        self,
        router: Optional[HybridRouter] = None,
        perspectives: Optional[List[CriticPerspective]] = None,
        min_agreement_threshold: float = 0.6
    ):
        """
        Initialize multi-critic panel.
        
        Args:
            router: HybridRouter for LLM access
            perspectives: List of critic perspectives (uses defaults if None)
            min_agreement_threshold: Minimum agreement level for consensus
        """
        self.router = router or HybridRouter(get_backend_manager())
        self.perspectives = perspectives or CRITIC_PERSPECTIVES
        self.min_agreement_threshold = min_agreement_threshold
        
        logger.info(f"MultiCriticPanel initialized with {len(self.perspectives)} critics")
        for p in self.perspectives:
            logger.info(f"  - {p.role} (weight={p.weight})")
    
    async def evaluate_solution(
        self,
        solution: SolutionProposal,
        problem: ProblemStatement,
        round_number: int = 1,
        previous_critiques: Optional[Dict[str, CritiqueReport]] = None,
        contentious_points: Optional[List[str]] = None,
        debate_history: Optional[str] = None
    ) -> ConsensusResult:
        """
        Get opinions from all critics and aggregate into consensus.
        Supports multi-round debates with cross-examination.
        
        Args:
            solution: Solution to evaluate
            problem: Original problem statement
            round_number: Current debate round (1=initial, 2+=cross-exam, 3=final)
            previous_critiques: Critiques from previous round (for cross-examination)
            contentious_points: Points of disagreement from previous round
            debate_history: Summary of previous rounds
            
        Returns:
            ConsensusResult with aggregated opinions and token usage
        """
        if round_number > 1:
            logger.info(f"🔍 Multi-critic evaluation (Round {round_number}): {solution.approach_name}")
        else:
            logger.info(f"🔍 Multi-critic evaluation: {solution.approach_name}")
        
        # Collect opinions from all critics
        opinions: List[CriticOpinion] = []
        
        for perspective in self.perspectives:
            if round_number > 1:
                logger.info(f"  Consulting {perspective.role} (Round {round_number})...")
            else:
                logger.info(f"  Consulting {perspective.role}...")
            
            opinion = await self._get_critic_opinion(
                solution=solution,
                problem=problem,
                perspective=perspective,
                round_number=round_number,
                previous_critiques=previous_critiques,
                contentious_points=contentious_points,
                debate_history=debate_history
            )
            
            if opinion:
                opinions.append(opinion)
                logger.info(f"    ✓ Feasibility: {opinion.critique.real_world_feasibility:.1f}/10")
        
        if not opinions:
            logger.error("No critic opinions collected!")
            return None
        
        # Aggregate into consensus
        consensus = self._aggregate_consensus(solution, opinions)
        
        logger.info(f"\n📊 Consensus Result:")
        logger.info(f"  Score: {consensus.consensus_score:.1f}/10")
        logger.info(f"  Agreement: {consensus.agreement_level:.1%}")
        logger.info(f"  Recommendation: {consensus.recommendation}")
        
        return consensus
    
    async def _get_critic_opinion(
        self,
        solution: SolutionProposal,
        problem: ProblemStatement,
        perspective: CriticPerspective,
        round_number: int = 1,
        previous_critiques: Optional[Dict[str, CritiqueReport]] = None,
        contentious_points: Optional[List[str]] = None,
        debate_history: Optional[str] = None
    ) -> Optional[CriticOpinion]:
        """
        Get opinion from a specific critic perspective.
        Supports multi-round debates with cross-examination.
        """
        # Build critique prompt based on round number
        prompt = self._build_critique_prompt(
            solution, problem, perspective, round_number,
            previous_critiques, contentious_points, debate_history
        )
        
        messages = [
            {"role": "system", "content": perspective.system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        try:
            result = await self.router.generate_with_fallback(
                task_type="critique",
                messages=messages,
                temperature=0.4,  # Balanced for critique
                max_tokens=4096
            )
            
            if not result or not result.success:
                logger.warning(f"Failed to get opinion from {perspective.role}")
                return None
            
            # Parse critique (simplified - reuse existing parsing)
            from src.utils.json_parser import safe_parse_critique
            critique_data = safe_parse_critique(result.content)
            
            if not critique_data:
                logger.warning(f"Failed to parse critique from {perspective.role}")
                return None
            
            critique = CritiqueReport(**critique_data)
            
            # Calculate confidence based on critique completeness
            confidence = self._calculate_confidence(critique)
            
            return CriticOpinion(
                perspective=perspective.name,
                critique=critique,
                confidence=confidence,
                weight=perspective.weight
            )
            
        except Exception as e:
            logger.error(f"Error getting opinion from {perspective.role}: {e}")
            return None
    
    def _build_critique_prompt(
        self,
        solution: SolutionProposal,
        problem: ProblemStatement,
        perspective: CriticPerspective,
        round_number: int = 1,
        previous_critiques: Optional[Dict[str, CritiqueReport]] = None,
        contentious_points: Optional[List[str]] = None,
        debate_history: Optional[str] = None
    ) -> str:
        """Build critique prompt tailored to perspective and round."""
        
        # Use cross-examination prompts if available and round > 1
        if CROSS_EXAM_AVAILABLE and round_number > 1 and previous_critiques:
            # Prepare previous critiques in format expected by cross-exam prompts
            other_critiques = {
                name: critique
                for name, critique in previous_critiques.items()
                if name != perspective.name  # Exclude self
            }
            
            # Convert problem and solution to dict format for prompts
            problem_str = problem.challenge
            solution_dict = {
                'approach_name': solution.approach_name,
                'key_innovation': solution.key_innovation,
                'architecture_design': solution.architecture_design,
                'implementation_plan': solution.implementation_plan if isinstance(solution.implementation_plan, list) else [solution.implementation_plan],
                'expected_advantages': solution.expected_advantages,
                'expected_performance': solution.expected_performance
            }
            
            if round_number >= 3 and debate_history:
                # Final refinement round
                return build_final_refinement_prompt(
                    persona_name=perspective.name,
                    persona_description=perspective.system_prompt,
                    problem=problem_str,
                    solution=solution_dict,
                    other_critics_opinions=other_critiques,
                    debate_history=debate_history,
                    contentious_points=contentious_points or []
                )
            else:
                # Cross-examination round
                return build_cross_examination_prompt(
                    persona_name=perspective.name,
                    persona_description=perspective.system_prompt,
                    problem=problem_str,
                    solution=solution_dict,
                    other_critics_opinions=other_critiques,
                    contentious_points=contentious_points or []
                )
        
        # Round 1 or no cross-exam available: use initial prompt
        if CROSS_EXAM_AVAILABLE and round_number == 1:
            solution_dict = {
                'approach_name': solution.approach_name,
                'key_innovation': solution.key_innovation,
                'architecture_design': solution.architecture_design,
                'implementation_plan': solution.implementation_plan if isinstance(solution.implementation_plan, list) else [solution.implementation_plan],
                'expected_advantages': solution.expected_advantages,
                'expected_performance': solution.expected_performance
            }
            
            return build_initial_critique_prompt(
                persona_name=perspective.name,
                persona_description=perspective.system_prompt,
                problem=problem.challenge,
                solution=solution_dict
            )
        
        # Fallback to legacy prompt if cross-exam not available
        focus_str = ", ".join(perspective.focus_areas)
        
        prompt = f"""Review this solution from your perspective ({perspective.role}).

PROBLEM:
{problem.challenge}

Limitations: {', '.join(problem.limitations)}

PROPOSED SOLUTION:
Name: {solution.approach_name}
Innovation: {solution.key_innovation}
Architecture: {solution.architecture_design}
Implementation: {solution.implementation_plan}
Advantages: {', '.join(solution.expected_advantages)}

YOUR FOCUS AREAS: {focus_str}

Provide critique in JSON format:
{{
  "overall_assessment": "promising|needs-work|flawed",
  "strengths": ["strength 1", "strength 2"],
  "weaknesses": ["weakness 1", "weakness 2"],
  "technical_concerns": ["concern 1", "concern 2"],
  "missing_considerations": ["missing 1", "missing 2"],
  "real_world_feasibility": 7.5,
  "optimization_suggestions": ["suggestion 1", "suggestion 2"],
  "verdict": "accept|revise|reject"
}}

Output ONLY valid JSON, no other text."""
        
        return prompt
    
    def _calculate_confidence(self, critique: CritiqueReport) -> float:
        """Calculate confidence based on critique completeness."""
        score = 0.0
        
        # More detailed critique = higher confidence
        if len(critique.strengths) >= 2:
            score += 0.25
        if len(critique.weaknesses) >= 2:
            score += 0.25
        if len(critique.technical_concerns) >= 1:
            score += 0.2
        if len(critique.optimization_suggestions) >= 1:
            score += 0.15
        if len(critique.missing_considerations) >= 1:
            score += 0.15
        
        return min(score, 1.0)
    
    def _aggregate_consensus(
        self,
        solution: SolutionProposal,
        opinions: List[CriticOpinion]
    ) -> ConsensusResult:
        """
        Aggregate multiple critic opinions into consensus.
        """
        # Calculate weighted average feasibility
        total_weight = sum(op.weight * op.confidence for op in opinions)
        weighted_feasibility = sum(
            op.critique.real_world_feasibility * op.weight * op.confidence
            for op in opinions
        ) / total_weight if total_weight > 0 else 0
        
        # Count verdicts
        verdict_counts = defaultdict(int)
        for op in opinions:
            verdict_counts[op.critique.verdict] += op.weight * op.confidence
        
        # Most common weighted verdict
        recommendation = max(verdict_counts.items(), key=lambda x: x[1])[0]
        
        # Calculate agreement level (inverse of standard deviation of feasibility scores)
        feasibilities = [op.critique.real_world_feasibility for op in opinions]
        if len(feasibilities) > 1:
            stdev = statistics.stdev(feasibilities)
            agreement_level = max(0, 1 - (stdev / 5.0))  # Normalize to 0-1
        else:
            agreement_level = 1.0
        
        # Find common strengths/weaknesses (mentioned by multiple critics)
        strength_counts = defaultdict(int)
        weakness_counts = defaultdict(int)
        
        for op in opinions:
            for s in op.critique.strengths:
                strength_counts[s.lower()] += 1
            for w in op.critique.weaknesses:
                weakness_counts[w.lower()] += 1
        
        # Keep items mentioned by at least 2 critics
        min_mentions = max(2, len(opinions) // 2)
        common_strengths = [
            s for s, count in strength_counts.items() if count >= min_mentions
        ]
        common_weaknesses = [
            w for w, count in weakness_counts.items() if count >= min_mentions
        ]
        
        # Identify contentious points (high disagreement)
        contentious = []
        if agreement_level < self.min_agreement_threshold:
            contentious.append(f"Critics disagree on feasibility (σ={statistics.stdev(feasibilities):.1f})")
        
        verdict_diversity = len(verdict_counts)
        if verdict_diversity > 1:
            contentious.append(f"Mixed verdicts: {dict(verdict_counts)}")
        
        # Calculate overall consensus score
        consensus_score = (
            weighted_feasibility * 0.6 +  # 60% from feasibility
            agreement_level * 10 * 0.3 +   # 30% from agreement
            (1 if recommendation == "accept" else 0.5 if recommendation == "revise" else 0) * 10 * 0.1  # 10% from recommendation
        )
        
        # Calculate confidence in consensus
        confidence = agreement_level * (sum(op.confidence for op in opinions) / len(opinions))
        
        # Generate reasoning
        reasoning = self._generate_reasoning(
            opinions, weighted_feasibility, agreement_level, recommendation
        )
        
        return ConsensusResult(
            solution=solution,
            individual_critiques=opinions,
            consensus_score=consensus_score,
            confidence=confidence,
            agreement_level=agreement_level,
            avg_feasibility=weighted_feasibility,
            common_strengths=common_strengths[:5],  # Top 5
            common_weaknesses=common_weaknesses[:5],  # Top 5
            contentious_points=contentious,
            recommendation=recommendation,
            reasoning=reasoning
        )
    
    def _generate_reasoning(
        self,
        opinions: List[CriticOpinion],
        avg_feasibility: float,
        agreement_level: float,
        recommendation: str
    ) -> str:
        """Generate human-readable reasoning for consensus."""
        
        perspectives_str = ", ".join([op.perspective.replace("_", " ").title() for op in opinions])
        
        agreement_desc = (
            "strong agreement" if agreement_level > 0.8 else
            "moderate agreement" if agreement_level > 0.6 else
            "some disagreement"
        )
        
        reasoning = f"""
Consensus from {len(opinions)} expert perspectives ({perspectives_str}):

- Average feasibility: {avg_feasibility:.1f}/10
- Agreement level: {agreement_level:.1%} ({agreement_desc})
- Weighted recommendation: {recommendation}

The panel shows {agreement_desc} on this solution's viability.
"""
        
        return reasoning.strip()


async def evaluate_with_consensus(
    solution: SolutionProposal,
    problem: ProblemStatement,
    router: Optional[HybridRouter] = None
) -> ConsensusResult:
    """
    Convenience function to evaluate solution with multi-critic consensus.
    
    Args:
        solution: Solution to evaluate
        problem: Original problem
        router: Optional router (creates if None)
        
    Returns:
        ConsensusResult
    """
    panel = MultiCriticPanel(router=router)
    return await panel.evaluate_solution(solution, problem)
