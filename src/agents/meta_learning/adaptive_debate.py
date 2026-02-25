"""
Adaptive Debate Controller

Intelligently manages multi-round debates between critics using:
- Dynamic stopping conditions
- Confidence-based decisions
- Token budget management
- Convergence detection

Integration #10: Enhanced Multi-Critic Consensus with Dynamic Debate
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, List
from datetime import datetime

from src.agents.meta_learning.debate_dissent import DissentAnalysis, DissentAnalyzer
from src.models.schemas import CritiqueReport
from src.utils.logger import get_logger

logger = get_logger("adaptive_debate")


@dataclass
class DebateConfig:
    """Configuration for adaptive debate system."""
    max_rounds: int = 3                      # Hard limit on rounds
    min_confidence: float = 0.85             # Min confidence to stop early
    max_disagreement: float = 0.2            # Max disagreement for consensus
    convergence_threshold: float = 0.15      # Min convergence rate to continue
    token_budget: Optional[int] = None       # Max tokens (None = unlimited)
    enable_early_stopping: bool = True       # Allow stopping before max rounds
    stall_detection: bool = True             # Stop if no progress for 2 rounds


@dataclass
class DebateMetrics:
    """Metrics tracking for a complete debate session."""
    total_rounds: int = 0
    tokens_used: int = 0
    time_elapsed: float = 0.0
    consensus_reached: bool = False
    early_stop: bool = False
    stop_reason: str = ""
    final_disagreement: float = 1.0
    final_confidence: float = 0.0
    convergence_rate: float = 0.0
    round_timings: List[float] = field(default_factory=list)
    round_disagreements: List[float] = field(default_factory=list)


@dataclass
class CriticOpinion:
    """
    Extended critique with confidence and uncertainty tracking.
    
    Tracks not just WHAT critics think, but HOW CERTAIN they are.
    """
    critique: CritiqueReport
    confidence: float                        # 0.0-1.0: How certain?
    uncertainty_reasons: List[str]           # Why uncertain?
    would_change_mind: bool = False          # Open to revision?
    key_assumptions: List[str] = field(default_factory=list)  # What assumptions made?


class AdaptiveDebateController:
    """
    Manages multi-round debate with intelligent stopping conditions.
    
    Features:
    - Dynamic round management (1-3 rounds based on need)
    - Confidence-weighted decisions
    - Token budget tracking
    - Convergence detection
    - Stall detection (no progress = stop)
    """
    
    def __init__(self, config: Optional[DebateConfig] = None):
        """
        Initialize adaptive debate controller.
        
        Args:
            config: Debate configuration (uses defaults if None)
        """
        self.config = config or DebateConfig()
        self.dissent_analyzer = DissentAnalyzer(
            disagreement_threshold=self.config.max_disagreement,
            convergence_threshold=self.config.convergence_threshold
        )
        self.metrics = DebateMetrics()
        self.start_time: Optional[datetime] = None
        self.round_start_time: Optional[datetime] = None
    
    def start_debate(self):
        """Initialize debate session."""
        self.start_time = datetime.now()
        self.metrics = DebateMetrics()
        logger.info("🎭 Starting adaptive debate session")
        logger.info(f"  Max rounds: {self.config.max_rounds}")
        logger.info(f"  Min confidence: {self.config.min_confidence:.0%}")
        logger.info(f"  Max disagreement: {self.config.max_disagreement:.0%}")
    
    def start_round(self, round_num: int):
        """Mark start of debate round."""
        self.round_start_time = datetime.now()
        logger.info(f"\n🔄 DEBATE ROUND {round_num}/{self.config.max_rounds}")
    
    def should_continue_debate(
        self,
        round_num: int,
        critics: Dict[str, CritiqueReport],
        confidence: Optional[float] = None
    ) -> tuple[bool, str]:
        """
        Decide if debate should continue to next round.
        
        Args:
            round_num: Current round number
            critics: Dict of critic critiques
            confidence: Optional overall confidence score
        
        Returns:
            Tuple of (should_continue, reason)
        """
        # Analyze current round dissent
        dissent = self.dissent_analyzer.analyze_round(round_num, critics)
        
        # Record metrics
        self.metrics.total_rounds = round_num
        self.metrics.round_disagreements.append(dissent.disagreement_score)
        self.metrics.final_disagreement = dissent.disagreement_score
        self.metrics.convergence_rate = dissent.convergence_trend
        
        if self.round_start_time:
            round_time = (datetime.now() - self.round_start_time).total_seconds()
            self.metrics.round_timings.append(round_time)
        
        # Calculate overall confidence
        if confidence is None:
            confidence = self._calculate_confidence(critics, dissent)
        self.metrics.final_confidence = confidence
        
        # Decision logic (order matters - most restrictive first)
        
        # 1. Hard limit: Max rounds reached
        if round_num >= self.config.max_rounds:
            self.metrics.stop_reason = f"Max rounds ({self.config.max_rounds}) reached"
            self.metrics.early_stop = False
            logger.info(f"  🛑 {self.metrics.stop_reason}")
            return False, self.metrics.stop_reason
        
        # 2. Token budget exhausted
        if self.config.token_budget and self.metrics.tokens_used >= self.config.token_budget:
            self.metrics.stop_reason = f"Token budget ({self.config.token_budget}) exceeded"
            self.metrics.early_stop = True
            logger.warning(f"  ⚠️  {self.metrics.stop_reason}")
            return False, self.metrics.stop_reason
        
        if not self.config.enable_early_stopping:
            # Early stopping disabled - always continue until max rounds
            return True, "Continuing to max rounds"
        
        # 3. Perfect conditions: High consensus + high confidence
        if (dissent.disagreement_score < self.config.max_disagreement and 
            confidence >= self.config.min_confidence):
            self.metrics.stop_reason = f"Strong consensus (disagreement={dissent.disagreement_score:.1%}, confidence={confidence:.1%})"
            self.metrics.consensus_reached = True
            self.metrics.early_stop = True
            logger.info(f"  ✅ {self.metrics.stop_reason}")
            return False, self.metrics.stop_reason
        
        # 4. Stall detection: No progress for 2+ rounds
        if self.config.stall_detection and self._is_stalled(dissent):
            self.metrics.stop_reason = "Debate stalled (no convergence for 2 rounds)"
            self.metrics.early_stop = True
            logger.warning(f"  ⚠️  {self.metrics.stop_reason}")
            return False, self.metrics.stop_reason
        
        # 5. Divergence: Critics getting more divided
        if dissent.convergence_trend < -self.config.convergence_threshold:
            self.metrics.stop_reason = f"Critics diverging (trend={dissent.convergence_trend:+.2f})"
            self.metrics.early_stop = True
            logger.warning(f"  ⚠️  {self.metrics.stop_reason}")
            return False, self.metrics.stop_reason
        
        # Continue debate - still room for improvement
        reason = f"Disagreement={dissent.disagreement_score:.1%}, converging={dissent.convergence_trend:+.2f}"
        logger.info(f"  ➡️  Continuing: {reason}")
        return True, reason
    
    def _calculate_confidence(
        self,
        critics: Dict[str, CritiqueReport],
        dissent: DissentAnalysis
    ) -> float:
        """
        Calculate overall confidence in the debate outcome.
        
        High confidence requires:
        - Low disagreement (critics agree)
        - High feasibility scores (critics think it's good)
        - Consistent verdicts (not just lukewarm agreement)
        
        Returns:
            Confidence score 0.0-1.0
        """
        # Consensus component (low disagreement = high confidence)
        consensus_confidence = 1.0 - dissent.disagreement_score
        
        # Quality component (high scores = high confidence)
        avg_feasibility = sum(c.real_world_feasibility for c in critics.values()) / len(critics)
        quality_confidence = avg_feasibility / 10.0
        
        # Verdict consistency (all agree on verdict = high confidence)
        verdicts = [c.verdict for c in critics.values()]
        verdict_agreement = verdicts.count(verdicts[0]) / len(verdicts) if verdicts else 0.0
        
        # Weighted combination
        confidence = (
            consensus_confidence * 0.4 +  # Consensus is important
            quality_confidence * 0.35 +    # Quality matters
            verdict_agreement * 0.25       # Verdict consistency
        )
        
        return confidence
    
    def _is_stalled(self, dissent: DissentAnalysis) -> bool:
        """
        Detect if debate has stalled (no meaningful progress).
        
        Stalled if:
        - Disagreement hasn't decreased for 2+ rounds
        - Convergence trend near zero
        
        Returns:
            True if debate is stalled
        """
        # Need at least 3 rounds to detect stall
        if len(self.metrics.round_disagreements) < 3:
            return False
        
        # Check last 3 disagreement scores
        recent_disagreements = self.metrics.round_disagreements[-3:]
        
        # Calculate changes between rounds
        changes = [
            recent_disagreements[i-1] - recent_disagreements[i]
            for i in range(1, len(recent_disagreements))
        ]
        
        # Stalled if no meaningful decrease in disagreement
        avg_change = sum(changes) / len(changes)
        is_stalled = avg_change < 0.05  # Less than 5% improvement
        
        if is_stalled:
            logger.debug(f"  Stall detected: avg change = {avg_change:.3f}")
        
        return is_stalled
    
    def update_token_usage(self, tokens: int):
        """Update token usage tracking."""
        self.metrics.tokens_used += tokens
        
        if self.config.token_budget:
            remaining = self.config.token_budget - self.metrics.tokens_used
            pct_used = (self.metrics.tokens_used / self.config.token_budget) * 100
            logger.debug(f"  Tokens: {self.metrics.tokens_used}/{self.config.token_budget} ({pct_used:.1f}% used)")
    
    def end_debate(self) -> DebateMetrics:
        """
        Finalize debate and return metrics.
        
        Returns:
            Complete debate metrics
        """
        if self.start_time:
            self.metrics.time_elapsed = (datetime.now() - self.start_time).total_seconds()
        
        logger.info("\n📊 DEBATE SUMMARY")
        logger.info(f"  Rounds: {self.metrics.total_rounds}/{self.config.max_rounds}")
        logger.info(f"  Time: {self.metrics.time_elapsed:.1f}s")
        logger.info(f"  Tokens: {self.metrics.tokens_used}")
        logger.info(f"  Final disagreement: {self.metrics.final_disagreement:.1%}")
        logger.info(f"  Final confidence: {self.metrics.final_confidence:.1%}")
        logger.info(f"  Consensus reached: {self.metrics.consensus_reached}")
        logger.info(f"  Early stop: {self.metrics.early_stop}")
        logger.info(f"  Stop reason: {self.metrics.stop_reason}")
        
        return self.metrics
    
    def get_debate_summary(self) -> Dict:
        """
        Get comprehensive debate summary for meta-learning.
        
        Returns:
            Dict with all debate metrics and dissent analysis
        """
        dissent_summary = self.dissent_analyzer.get_debate_summary()
        
        return {
            "metrics": {
                "rounds": self.metrics.total_rounds,
                "max_rounds": self.config.max_rounds,
                "time_seconds": self.metrics.time_elapsed,
                "tokens_used": self.metrics.tokens_used,
                "token_budget": self.config.token_budget,
                "consensus_reached": self.metrics.consensus_reached,
                "early_stop": self.metrics.early_stop,
                "stop_reason": self.metrics.stop_reason,
                "final_disagreement": self.metrics.final_disagreement,
                "final_confidence": self.metrics.final_confidence,
                "convergence_rate": self.metrics.convergence_rate,
                "avg_round_time": sum(self.metrics.round_timings) / len(self.metrics.round_timings) if self.metrics.round_timings else 0.0
            },
            "dissent_analysis": dissent_summary,
            "efficiency": {
                "rounds_saved": self.config.max_rounds - self.metrics.total_rounds,
                "early_stop_success": self.metrics.early_stop and self.metrics.consensus_reached,
                "token_efficiency": 1.0 - (self.metrics.total_rounds / self.config.max_rounds) if self.metrics.early_stop else 0.0
            },
            "config": {
                "max_rounds": self.config.max_rounds,
                "min_confidence": self.config.min_confidence,
                "max_disagreement": self.config.max_disagreement,
                "convergence_threshold": self.config.convergence_threshold,
                "early_stopping_enabled": self.config.enable_early_stopping,
                "stall_detection_enabled": self.config.stall_detection
            }
        }


def create_debate_controller(
    max_rounds: int = 3,
    min_confidence: float = 0.85,
    max_disagreement: float = 0.2,
    token_budget: Optional[int] = None
) -> AdaptiveDebateController:
    """
    Convenience function to create debate controller with custom config.
    
    Args:
        max_rounds: Maximum debate rounds
        min_confidence: Minimum confidence to stop early
        max_disagreement: Maximum disagreement for consensus
        token_budget: Optional token limit
    
    Returns:
        Configured AdaptiveDebateController
    """
    config = DebateConfig(
        max_rounds=max_rounds,
        min_confidence=min_confidence,
        max_disagreement=max_disagreement,
        token_budget=token_budget
    )
    
    return AdaptiveDebateController(config)
