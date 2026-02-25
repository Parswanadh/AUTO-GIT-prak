"""Self-reflection agent for code quality improvement."""

import asyncio
import logging
from typing import Optional, List, Dict, Tuple
from datetime import datetime

from src.agents.tier3_generation.quality_assessor import (
    QualityAssessor,
    QualityScore
)
from src.agents.meta_learning.reflection_models import (
    Reflection,
    ReflectionCycle,
    ReflectionHistory,
    FailureType,
    IssueEvidence
)
from src.agents.meta_learning.reflection_prompts import (
    REFLECTION_GENERATION_PROMPT,
    CODE_IMPROVEMENT_PROMPT,
    STOPPING_DECISION_PROMPT
)
from src.llm.hybrid_router import HybridRouter
from src.llm.multi_backend_manager import get_backend_manager
from src.utils.json_parser import extract_json_from_text

logger = logging.getLogger(__name__)


class ReflectiveAgent:
    """
    Self-reflection agent using quality metrics as feedback.
    
    Pattern: Execute → Assess → Reflect → Improve → Loop
    """
    
    def __init__(
        self,
        max_iterations: int = 3,
        quality_threshold: float = 70.0,
        min_improvement: float = 2.0,
        router: Optional[HybridRouter] = None
    ):
        """
        Initialize reflective agent.
        
        Args:
            max_iterations: Hard limit on reflection cycles
            quality_threshold: Target quality score
            min_improvement: Minimum score gain to continue
            router: Optional HybridRouter instance
        """
        self.max_iterations = max_iterations
        self.quality_threshold = quality_threshold
        self.min_improvement = min_improvement
        
        self.assessor = QualityAssessor()
        
        # Initialize router if not provided
        if router is None:
            backend_manager = get_backend_manager()
            self.router = HybridRouter(backend_manager, use_cache=False)
        else:
            self.router = router
    
    async def improve_with_reflection(
        self,
        initial_code: str,
        filename: str = "model.py",
        problem_id: str = "unknown"
    ) -> Tuple[str, ReflectionHistory]:
        """
        Main entry point: Improve code through reflection.
        
        Args:
            initial_code: Code to improve
            filename: Filename for context
            problem_id: Problem identifier for tracking
        
        Returns:
            (best_code, reflection_history)
        """
        logger.info(f"🔄 Starting reflection-based improvement (max {self.max_iterations} cycles)")
        
        history = ReflectionHistory(problem_id=problem_id)
        current_code = initial_code
        
        for iteration in range(1, self.max_iterations + 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"Reflection Cycle {iteration}/{self.max_iterations}")
            logger.info(f"{'='*60}")
            
            # Create cycle tracker
            cycle = ReflectionCycle(
                attempt_number=iteration,
                original_code=current_code,
                original_quality_score=0.0,
                original_metrics={}
            )
            start_time = datetime.now()
            
            # Step 1: Assess current code quality
            quality_score = await self.assessor.assess_code(
                code=current_code,
                filename=filename
            )
            
            cycle.original_quality_score = quality_score.overall_score
            cycle.original_metrics = self._extract_metrics(quality_score)
            
            logger.info(f"📊 Quality Score: {quality_score.overall_score:.1f}/100")
            
            # Check if threshold reached
            if quality_score.overall_score >= self.quality_threshold:
                logger.info(f"✅ Threshold reached ({quality_score.overall_score:.1f}≥{self.quality_threshold})")
                cycle.success = True
                cycle.stopped_reason = "threshold_met"
                cycle.improved_code = current_code
                cycle.improved_quality_score = quality_score.overall_score
                history.add_cycle(cycle)
                break
            
            # Check if should continue
            if iteration > 1 and not await self._should_continue(history):
                logger.info("🛑 Stopping: No significant improvement")
                cycle.stopped_reason = "no_improvement"
                history.add_cycle(cycle)
                break
            
            # Step 2: Generate reflection
            logger.info("🤔 Generating reflection...")
            reflection = await self._generate_reflection(
                code=current_code,
                quality_score=quality_score,
                previous_reflections=history.cycles
            )
            
            if not reflection:
                logger.error("Failed to generate reflection")
                cycle.stopped_reason = "reflection_failed"
                history.add_cycle(cycle)
                break
            
            cycle.reflection = reflection
            
            logger.info(f"💡 Root Cause: {reflection.root_cause}")
            logger.info(f"🎯 Fix Strategy: {reflection.fix_strategy}")
            
            # Step 3: Improve code based on reflection
            logger.info("🔧 Applying improvements...")
            improved_code = await self._improve_code(
                original_code=current_code,
                reflection=reflection
            )
            
            if not improved_code or improved_code == current_code:
                logger.warning("No code changes generated")
                cycle.stopped_reason = "no_changes"
                cycle.improved_code = current_code
                cycle.improved_quality_score = cycle.original_quality_score
                history.add_cycle(cycle)
                break
            
            # Step 4: Re-assess improved code
            improved_quality = await self.assessor.assess_code(
                code=improved_code,
                filename=filename
            )
            
            cycle.improved_code = improved_code
            cycle.improved_quality_score = improved_quality.overall_score
            cycle.improved_metrics = self._extract_metrics(improved_quality)
            cycle.calculate_improvement()
            
            cycle.time_taken = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"📈 Improvement: {cycle.improvement_delta:+.1f} points")
            logger.info(f"   {cycle.original_quality_score:.1f} → {cycle.improved_quality_score:.1f}")
            
            # Update for next iteration
            history.add_cycle(cycle)
            current_code = improved_code
            
            if cycle.success:
                logger.info("✅ Success! Threshold reached after improvement")
                break
        
        # Final summary
        if not history.cycles:
            logger.warning("No reflection cycles completed")
            return initial_code, history
        
        best_cycle = history.get_best_attempt()
        logger.info(f"\n{'='*60}")
        logger.info(f"Reflection Complete:")
        logger.info(f"  Iterations: {history.total_iterations}")
        logger.info(f"  Best Score: {best_cycle.improved_quality_score:.1f}/100")
        logger.info(f"  Total Improvement: {history.total_improvement:+.1f}")
        logger.info(f"  Success: {'✅' if history.success else '❌'}")
        logger.info(f"{'='*60}\n")
        
        return best_cycle.improved_code or initial_code, history
    
    async def _generate_reflection(
        self,
        code: str,
        quality_score: QualityScore,
        previous_reflections: List[ReflectionCycle]
    ) -> Optional[Reflection]:
        """Generate reflection from quality assessment."""
        
        # Format previous reflections
        prev_text = "\n".join([
            f"Cycle {c.attempt_number}: {c.reflection.root_cause if c.reflection else 'N/A'}"
            for c in previous_reflections[-2:]  # Last 2 only
        ]) if previous_reflections else "None"
        
        # Format issues
        issues = []
        if quality_score.syntax_score < 100:
            issues.extend([f"Syntax: {issue}" for issue in quality_score.critical_issues])
        if quality_score.complexity_score < 70:
            issues.append(
                f"Complexity: Cyclomatic={quality_score.metrics.cyclomatic_complexity}, "
                f"Cognitive={quality_score.metrics.cognitive_complexity}"
            )
        if quality_score.style_score < 80:
            issues.extend([f"Style: {issue.message}" for issue in quality_score.issues[:3]])
        
        # Build prompt
        prompt = REFLECTION_GENERATION_PROMPT.format(
            code=code,
            overall_score=quality_score.overall_score,
            syntax_score=quality_score.syntax_score,
            syntax_status="✅" if quality_score.syntax_score >= 90 else "❌",
            complexity_score=quality_score.complexity_score,
            complexity_status="✅" if quality_score.complexity_score >= 70 else "❌",
            cyclomatic=quality_score.metrics.cyclomatic_complexity,
            cognitive=quality_score.metrics.cognitive_complexity,
            style_score=quality_score.style_score,
            style_status="✅" if quality_score.style_score >= 80 else "❌",
            style_issues_count=len(quality_score.issues),
            docs_score=quality_score.documentation_score,
            docs_status="✅" if quality_score.documentation_score >= 70 else "❌",
            maintainability_score=quality_score.maintainability_score,
            maintainability_status="✅" if quality_score.maintainability_score >= 70 else "❌",
            semantic_score=quality_score.semantic_score,
            semantic_status="✅" if quality_score.semantic_score >= 70 else "❌",
            issues_list="\n".join(f"- {issue}" for issue in issues) or "None detected",
            previous_reflections=prev_text
        )
        
        # Call LLM
        messages = [
            {"role": "system", "content": "You are an expert code quality analyst performing root cause analysis."},
            {"role": "user", "content": prompt}
        ]
        
        result = await self.router.generate_with_fallback(
            task_type="code_review",
            messages=messages,
            temperature=0.3,
            max_tokens=4096
        )
        
        if not result or not result.success:
            logger.error(f"Reflection generation failed: {result.error if result else 'No result'}")
            return None
        
        response = result.content or ""
        logger.info(f"LLM Response length: {len(response)} chars")
        
        # Parse JSON
        reflection_data = extract_json_from_text(response)
        if not reflection_data:
            logger.error(f"Failed to parse reflection JSON. Response: {response[:500]}")
            return None
        
        # Build Reflection object
        try:
            reflection = Reflection(
                failure_type=FailureType(reflection_data.get("failure_type", "quality_issue")),
                root_cause=reflection_data.get("root_cause", "Unknown"),
                failing_components=reflection_data.get("failing_components", []),
                evidence=[],  # Parse from reflection_data if available
                fix_strategy=reflection_data.get("fix_strategy", ""),
                specific_changes=reflection_data.get("specific_changes", []),
                priority_order=reflection_data.get("priority_order", []),
                expected_improvements=reflection_data.get("expected_improvements", {}),
                reflection_cycle=len(previous_reflections) + 1,
                confidence=reflection_data.get("confidence", 0.5)
            )
            return reflection
        except Exception as e:
            logger.error(f"Failed to build Reflection object: {e}")
            return None
    
    async def _improve_code(
        self,
        original_code: str,
        reflection: Reflection
    ) -> Optional[str]:
        """Apply reflection to improve code."""
        
        prompt = CODE_IMPROVEMENT_PROMPT.format(
            original_code=original_code,
            failure_type=reflection.failure_type.value,
            root_cause=reflection.root_cause,
            failing_components="\n".join(f"- {c}" for c in reflection.failing_components),
            fix_strategy=reflection.fix_strategy,
            specific_changes="\n".join(reflection.specific_changes),
            expected_improvements=str(reflection.expected_improvements)
        )
        
        messages = [
            {"role": "system", "content": "You are a code refactoring expert applying structured improvements."},
            {"role": "user", "content": prompt}
        ]
        
        result = await self.router.generate_with_fallback(
            task_type="code_generation",
            messages=messages,
            temperature=0.2,
            max_tokens=8192
        )
        
        if not result or not result.success:
            logger.error(f"Code improvement failed: {result.error if result else 'No result'}")
            return None
        
        response = result.content or ""
        
        # Extract code (remove markdown if present)
        code = response.strip()
        if code.startswith("```python"):
            code = code.split("```python\n", 1)[1] if "\n" in code.split("```python", 1)[1] else code
            code = code.rsplit("```", 1)[0]
        elif code.startswith("```"):
            code = code.split("```\n", 1)[1] if "\n" in code.split("```", 1)[1] else code
            code = code.rsplit("```", 1)[0]
        
        return code.strip()
    
    async def _should_continue(self, history: ReflectionHistory) -> bool:
        """Decide if reflection should continue."""
        
        if len(history.cycles) >= self.max_iterations:
            return False
        
        if len(history.cycles) < 2:
            return True
        
        # Check last 2 improvements
        recent = history.cycles[-2:]
        avg_improvement = sum(c.improvement_delta for c in recent) / len(recent)
        
        if avg_improvement < self.min_improvement:
            logger.info(f"Diminishing returns: {avg_improvement:.1f} < {self.min_improvement}")
            return False
        
        return True
    
    def _extract_metrics(self, quality_score: QualityScore) -> Dict[str, float]:
        """Extract metrics dict from quality score."""
        return {
            "overall": quality_score.overall_score,
            "syntax": quality_score.syntax_score,
            "complexity": quality_score.complexity_score,
            "style": quality_score.style_score,
            "documentation": quality_score.documentation_score,
            "maintainability": quality_score.maintainability_score,
            "semantic": quality_score.semantic_score,
            "cyclomatic": quality_score.metrics.cyclomatic_complexity,
            "cognitive": quality_score.metrics.cognitive_complexity
        }


# ============================================
# LANGGRAPH NODE WRAPPER
# ============================================

async def reflective_improvement_node(state: Dict) -> Dict:
    """
    LangGraph node for reflective improvement.
    
    Args:
        state: Pipeline state with 'generated_code'
    
    Returns:
        Updated state with 'improved_code' and 'reflection_history'
    """
    generated_code = state.get("generated_code")
    if not generated_code:
        logger.error("No generated_code in state")
        return state
    
    agent = ReflectiveAgent()
    
    improved_code, history = await agent.improve_with_reflection(
        initial_code=generated_code,
        filename=state.get("filename", "model.py"),
        problem_id=state.get("problem_id", "unknown")
    )
    
    state["improved_code"] = improved_code
    state["reflection_history"] = history
    state["final_quality_score"] = history.final_score or 0.0
    
    return state
