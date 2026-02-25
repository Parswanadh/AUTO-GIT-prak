"""Data models for self-reflection system."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional
from enum import Enum


class FailureType(Enum):
    """Types of code generation failures."""
    QUALITY_ISSUE = "quality_issue"
    COMPLEXITY = "complexity"
    STYLE_VIOLATIONS = "style_violations"
    DOCUMENTATION = "documentation"
    SYNTAX_ERROR = "syntax_error"
    TEST_FAILURE = "test_failure"
    SEMANTIC_ERROR = "semantic_error"


@dataclass
class IssueEvidence:
    """Evidence for a specific issue."""
    dimension: str
    current_score: float
    target_score: float
    specific_problems: List[str]
    metrics: Dict[str, float]


@dataclass
class Reflection:
    """Structured reflection output."""
    
    # Diagnosis
    failure_type: FailureType
    root_cause: str
    failing_components: List[str]
    evidence: List[IssueEvidence] = field(default_factory=list)
    
    # Action Plan
    fix_strategy: str = ""
    specific_changes: List[str] = field(default_factory=list)
    priority_order: List[int] = field(default_factory=list)
    expected_improvements: Dict[str, float] = field(default_factory=dict)
    
    # Meta
    reflection_cycle: int = 1
    timestamp: datetime = field(default_factory=datetime.now)
    confidence: float = 0.0
    estimated_effort: str = "medium"
    
    def to_dict(self) -> Dict:
        """Convert to dict for serialization."""
        return {
            "failure_type": self.failure_type.value,
            "root_cause": self.root_cause,
            "failing_components": self.failing_components,
            "fix_strategy": self.fix_strategy,
            "specific_changes": self.specific_changes,
            "confidence": self.confidence,
            "cycle": self.reflection_cycle
        }


@dataclass
class ReflectionCycle:
    """One complete reflection iteration."""
    
    attempt_number: int
    original_code: str
    original_quality_score: float
    original_metrics: Dict[str, float]
    
    reflection: Optional[Reflection] = None
    improved_code: Optional[str] = None
    improved_quality_score: Optional[float] = None
    improved_metrics: Optional[Dict[str, float]] = None
    
    improvement_delta: float = 0.0
    time_taken: float = 0.0
    tokens_used: int = 0
    
    success: bool = False
    stopped_reason: str = ""
    
    def calculate_improvement(self):
        """Calculate improvement metrics."""
        if self.improved_quality_score is not None:
            self.improvement_delta = (
                self.improved_quality_score - self.original_quality_score
            )
            self.success = self.improved_quality_score >= 70.0


@dataclass
class ReflectionHistory:
    """Complete history of reflection attempts."""
    
    problem_id: str
    cycles: List[ReflectionCycle] = field(default_factory=list)
    final_code: Optional[str] = None
    final_score: Optional[float] = None
    total_iterations: int = 0
    total_improvement: float = 0.0
    success: bool = False
    
    def add_cycle(self, cycle: ReflectionCycle):
        """Add a reflection cycle."""
        self.cycles.append(cycle)
        self.total_iterations += 1
        
        if cycle.success:
            self.final_code = cycle.improved_code
            self.final_score = cycle.improved_quality_score
            self.success = True
            if self.cycles:
                self.total_improvement = (
                    self.final_score - self.cycles[0].original_quality_score
                )
    
    def get_best_attempt(self) -> ReflectionCycle:
        """Get cycle with highest quality score."""
        if not self.cycles:
            raise ValueError("No cycles in history")
        return max(
            self.cycles,
            key=lambda c: c.improved_quality_score if c.improved_quality_score else 0
        )
