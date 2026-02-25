"""
Debate Dissent Analysis Module

Tracks disagreements between critics and identifies contentious points
for focused re-debate in multi-round consensus building.

Integration #10: Enhanced Multi-Critic Consensus with Dynamic Debate
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple
from collections import Counter
import statistics

from src.models.schemas import CritiqueReport
from src.utils.logger import get_logger

logger = get_logger("debate_dissent")


@dataclass
class DissentAnalysis:
    """
    Analysis of disagreements between critics.
    
    Attributes:
        contentious_points: Specific issues critics disagree on
        disagreement_score: Overall disagreement level (0.0-1.0)
        convergence_trend: Rate of convergence across rounds (-1.0 to 1.0)
        requires_refinement: Whether debate should continue
        focused_areas: Specific topics to re-debate
        agreement_matrix: Pairwise agreement between critics
        critic_positions: Summary of each critic's stance
    """
    contentious_points: List[str] = field(default_factory=list)
    disagreement_score: float = 0.0
    convergence_trend: float = 0.0
    requires_refinement: bool = True
    focused_areas: List[str] = field(default_factory=list)
    agreement_matrix: Dict[str, Dict[str, float]] = field(default_factory=dict)
    critic_positions: Dict[str, str] = field(default_factory=dict)


@dataclass
class DebateRoundHistory:
    """History of a single debate round for convergence tracking."""
    round_num: int
    disagreement_score: float
    consensus_level: float
    contentious_points: List[str]
    verdicts: Dict[str, str]  # critic_name -> verdict


class DissentAnalyzer:
    """
    Analyzes disagreements between critics to guide multi-round debate.
    
    Identifies:
    - What critics disagree on (contentious points)
    - How much they disagree (disagreement score)
    - Whether they're converging (trend analysis)
    - What to focus on in next round (focused areas)
    """
    
    def __init__(
        self,
        disagreement_threshold: float = 0.3,
        convergence_threshold: float = 0.15
    ):
        """
        Initialize dissent analyzer.
        
        Args:
            disagreement_threshold: Min disagreement to continue debate (0.0-1.0)
            convergence_threshold: Min convergence rate to stop (0.0-1.0)
        """
        self.disagreement_threshold = disagreement_threshold
        self.convergence_threshold = convergence_threshold
        self.history: List[DebateRoundHistory] = []
    
    def analyze_round(
        self,
        round_num: int,
        critics: Dict[str, CritiqueReport]
    ) -> DissentAnalysis:
        """
        Analyze disagreements in current debate round.
        
        Args:
            round_num: Current round number
            critics: Dict mapping critic name to their critique
        
        Returns:
            DissentAnalysis with detailed disagreement metrics
        """
        logger.info(f"📊 Analyzing dissent (Round {round_num})")
        
        if len(critics) < 2:
            logger.warning("Need at least 2 critics for dissent analysis")
            return DissentAnalysis(
                disagreement_score=0.0,
                requires_refinement=False
            )
        
        # Extract verdicts and scores
        verdicts = {name: c.verdict for name, c in critics.items()}
        scores = {name: c.real_world_feasibility for name, c in critics.items()}
        
        # Calculate disagreement metrics
        disagreement_score = self._calculate_disagreement(verdicts, scores)
        contentious_points = self._identify_contentious_points(critics)
        agreement_matrix = self._build_agreement_matrix(critics)
        consensus_level = 1.0 - disagreement_score
        
        # Store round history
        round_history = DebateRoundHistory(
            round_num=round_num,
            disagreement_score=disagreement_score,
            consensus_level=consensus_level,
            contentious_points=contentious_points,
            verdicts=verdicts
        )
        self.history.append(round_history)
        
        # Calculate convergence trend
        convergence_trend = self._calculate_convergence_trend()
        
        # Determine if refinement needed
        requires_refinement = self._should_continue_debate(
            disagreement_score,
            convergence_trend
        )
        
        # Identify focused areas for next round
        focused_areas = self._get_focused_areas(critics, contentious_points)
        
        # Build critic position summary
        critic_positions = {
            name: f"{c.verdict} (score: {c.real_world_feasibility:.1f}/10)"
            for name, c in critics.items()
        }
        
        analysis = DissentAnalysis(
            contentious_points=contentious_points,
            disagreement_score=disagreement_score,
            convergence_trend=convergence_trend,
            requires_refinement=requires_refinement,
            focused_areas=focused_areas,
            agreement_matrix=agreement_matrix,
            critic_positions=critic_positions
        )
        
        logger.info(f"  Disagreement: {disagreement_score:.2%}")
        logger.info(f"  Convergence trend: {convergence_trend:+.2f}")
        logger.info(f"  Contentious points: {len(contentious_points)}")
        logger.info(f"  Continue debate: {requires_refinement}")
        
        return analysis
    
    def _calculate_disagreement(
        self,
        verdicts: Dict[str, str],
        scores: Dict[str, float]
    ) -> float:
        """
        Calculate overall disagreement score.
        
        Combines:
        - Verdict disagreement (accept/revise/reject)
        - Score variance (how spread out are feasibility scores?)
        
        Returns:
            Disagreement score 0.0-1.0 (0=full agreement, 1=max disagreement)
        """
        # Verdict disagreement (categorical)
        verdict_counts = Counter(verdicts.values())
        most_common_count = verdict_counts.most_common(1)[0][1]
        verdict_disagreement = 1.0 - (most_common_count / len(verdicts))
        
        # Score disagreement (numerical)
        score_values = list(scores.values())
        if len(score_values) > 1:
            score_range = max(score_values) - min(score_values)
            score_std = statistics.stdev(score_values)
            # Normalize: range contributes 60%, std contributes 40%
            score_disagreement = (score_range / 10.0) * 0.6 + (score_std / 3.0) * 0.4
        else:
            score_disagreement = 0.0
        
        # Weighted combination: verdicts matter more (70/30)
        overall_disagreement = (
            verdict_disagreement * 0.7 +
            score_disagreement * 0.3
        )
        
        return min(overall_disagreement, 1.0)
    
    def _identify_contentious_points(
        self,
        critics: Dict[str, CritiqueReport]
    ) -> List[str]:
        """
        Find specific issues critics disagree on.
        
        Looks at:
        - Strengths mentioned by some but not others
        - Weaknesses mentioned by some but not others
        - Technical concerns with conflicting opinions
        
        Returns:
            List of contentious point descriptions
        """
        contentious = []
        
        # Collect all mentioned strengths/weaknesses
        all_strengths = []
        all_weaknesses = []
        all_concerns = []
        
        for name, critique in critics.items():
            all_strengths.extend(critique.strengths)
            all_weaknesses.extend(critique.weaknesses)
            all_concerns.extend(critique.technical_concerns)
        
        # Find items mentioned by some but not all
        strength_counts = Counter(all_strengths)
        weakness_counts = Counter(all_weaknesses)
        concern_counts = Counter(all_concerns)
        
        num_critics = len(critics)
        
        # Contentious strength (some see it, others don't)
        for strength, count in strength_counts.items():
            if 0 < count < num_critics:
                contentious.append(
                    f"Strength '{strength[:60]}...' - only {count}/{num_critics} critics agree"
                )
        
        # Contentious weakness (some see it, others don't)
        for weakness, count in weakness_counts.items():
            if 0 < count < num_critics:
                contentious.append(
                    f"Weakness '{weakness[:60]}...' - only {count}/{num_critics} critics agree"
                )
        
        # Limit to top 5 most contentious
        return contentious[:5]
    
    def _build_agreement_matrix(
        self,
        critics: Dict[str, CritiqueReport]
    ) -> Dict[str, Dict[str, float]]:
        """
        Calculate pairwise agreement between critics.
        
        Returns:
            Matrix: critic1 -> critic2 -> agreement_score (0.0-1.0)
        """
        critic_names = list(critics.keys())
        matrix = {}
        
        for i, name1 in enumerate(critic_names):
            matrix[name1] = {}
            for name2 in critic_names:
                if name1 == name2:
                    matrix[name1][name2] = 1.0
                else:
                    # Calculate agreement based on verdict + score similarity
                    c1 = critics[name1]
                    c2 = critics[name2]
                    
                    # Verdict agreement (0 or 1)
                    verdict_agreement = 1.0 if c1.verdict == c2.verdict else 0.0
                    
                    # Score similarity (0.0-1.0)
                    score_diff = abs(c1.real_world_feasibility - c2.real_world_feasibility)
                    score_similarity = 1.0 - (score_diff / 10.0)
                    
                    # Weighted: verdict 60%, score 40%
                    agreement = verdict_agreement * 0.6 + score_similarity * 0.4
                    matrix[name1][name2] = agreement
        
        return matrix
    
    def _calculate_convergence_trend(self) -> float:
        """
        Calculate rate of convergence across rounds.
        
        Positive trend = converging (disagreement decreasing)
        Negative trend = diverging (disagreement increasing)
        Zero trend = stalled (no change)
        
        Returns:
            Convergence rate (-1.0 to 1.0)
        """
        if len(self.history) < 2:
            return 0.0
        
        # Look at last 3 rounds (or all if fewer)
        recent_rounds = self.history[-3:]
        disagreements = [r.disagreement_score for r in recent_rounds]
        
        # Calculate trend (negative slope = converging)
        if len(disagreements) >= 2:
            # Simple linear trend
            changes = [
                disagreements[i-1] - disagreements[i]
                for i in range(1, len(disagreements))
            ]
            avg_change = statistics.mean(changes)
            
            # Normalize to -1.0 to 1.0 range
            # Positive change = converging, negative = diverging
            return min(max(avg_change, -1.0), 1.0)
        
        return 0.0
    
    def _should_continue_debate(
        self,
        disagreement_score: float,
        convergence_trend: float
    ) -> bool:
        """
        Determine if debate should continue based on metrics.
        
        Continue if:
        - Disagreement above threshold AND
        - Either converging OR not yet stalled
        
        Args:
            disagreement_score: Current disagreement level
            convergence_trend: Rate of convergence
        
        Returns:
            True if debate should continue
        """
        # High consensus reached - stop
        if disagreement_score < self.disagreement_threshold:
            logger.info("  ✅ High consensus reached, stopping debate")
            return False
        
        # Diverging or stalled - stop to avoid waste
        if convergence_trend < -self.convergence_threshold:
            logger.info("  ⚠️  Critics diverging, stopping debate")
            return False
        
        if len(self.history) >= 2 and convergence_trend < self.convergence_threshold:
            logger.info("  ⚠️  Debate stalled, stopping")
            return False
        
        # Still disagreeing and converging - continue
        logger.info("  🔄 Disagreement high, debate continues")
        return True
    
    def _get_focused_areas(
        self,
        critics: Dict[str, CritiqueReport],
        contentious_points: List[str]
    ) -> List[str]:
        """
        Identify specific areas to focus on in next round.
        
        Returns:
            List of focused topic areas for cross-examination
        """
        focused = []
        
        # Extract themes from contentious points
        for point in contentious_points:
            if "implementation" in point.lower():
                focused.append("Implementation approach")
            elif "performance" in point.lower() or "efficiency" in point.lower():
                focused.append("Performance and efficiency")
            elif "complexity" in point.lower():
                focused.append("Solution complexity")
            elif "feasibility" in point.lower() or "practical" in point.lower():
                focused.append("Real-world feasibility")
            elif "novel" in point.lower() or "innovation" in point.lower():
                focused.append("Novelty and innovation")
        
        # Remove duplicates, keep top 3
        focused = list(dict.fromkeys(focused))[:3]
        
        # If no specific themes, use general areas
        if not focused:
            focused = ["Overall approach", "Technical implementation", "Practical feasibility"]
        
        return focused
    
    def get_debate_summary(self) -> Dict[str, any]:
        """
        Get summary of entire debate progression.
        
        Returns:
            Dict with round-by-round metrics and trends
        """
        if not self.history:
            return {"rounds": 0, "final_consensus": 0.0}
        
        return {
            "rounds": len(self.history),
            "initial_disagreement": self.history[0].disagreement_score,
            "final_disagreement": self.history[-1].disagreement_score,
            "final_consensus": self.history[-1].consensus_level,
            "convergence_achieved": self.history[0].disagreement_score > self.history[-1].disagreement_score,
            "improvement": self.history[0].disagreement_score - self.history[-1].disagreement_score,
            "round_history": [
                {
                    "round": r.round_num,
                    "disagreement": r.disagreement_score,
                    "consensus": r.consensus_level,
                    "contentious_points": len(r.contentious_points)
                }
                for r in self.history
            ]
        }


def analyze_debate_dissent(
    round_num: int,
    critics: Dict[str, CritiqueReport],
    analyzer: DissentAnalyzer = None
) -> DissentAnalysis:
    """
    Convenience function to analyze dissent in a debate round.
    
    Args:
        round_num: Current round number
        critics: Dict of critic name -> critique
        analyzer: Optional existing analyzer (creates new if None)
    
    Returns:
        DissentAnalysis with detailed metrics
    """
    if analyzer is None:
        analyzer = DissentAnalyzer()
    
    return analyzer.analyze_round(round_num, critics)
