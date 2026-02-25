"""Pattern Learner - Extract patterns from pipeline runs"""

import logging
import hashlib
from typing import List, Dict, Any, Optional
from pathlib import Path
from collections import Counter

from .graph import KnowledgeGraph

logger = logging.getLogger(__name__)


class PatternLearner:
    """
    Learn patterns from completed pipeline runs
    
    Features:
    - Extract success patterns
    - Identify failure patterns
    - Build solution templates
    - Track technique effectiveness
    """
    
    def __init__(self, graph: KnowledgeGraph):
        """Initialize pattern learner"""
        self.graph = graph
        logger.info("Pattern learner initialized")
    
    def learn_from_run(
        self,
        run_data: Dict[str, Any],
        success: bool
    ):
        """
        Learn patterns from a completed pipeline run
        
        Args:
            run_data: Pipeline run data including:
                - idea: Original idea
                - files_generated: List of files
                - errors: List of errors
                - fixes_applied: List of fixes
                - model_used: Model name
                - stages: List of completed stages
            success: Whether run succeeded
        """
        try:
            # Extract problem pattern
            problem_signature = self._extract_problem_pattern(run_data)
            if problem_signature:
                self.graph.record_pattern(
                    pattern_type="problem",
                    signature=problem_signature,
                    data={
                        "idea": run_data.get("idea", ""),
                        "files_count": len(run_data.get("files_generated", []))
                    },
                    success=success
                )
            
            # Extract solution pattern (if successful)
            if success:
                solution_signature = self._extract_solution_pattern(run_data)
                if solution_signature:
                    self.graph.record_pattern(
                        pattern_type="solution",
                        signature=solution_signature,
                        data={
                            "files": run_data.get("files_generated", []),
                            "model": run_data.get("model_used", ""),
                            "techniques": run_data.get("techniques", [])
                        },
                        success=True
                    )
            
            # Extract error patterns (if any)
            errors = run_data.get("errors", [])
            for error in errors:
                error_signature = self._extract_error_pattern(error)
                if error_signature:
                    self.graph.record_pattern(
                        pattern_type="error",
                        signature=error_signature,
                        data={
                            "error_type": error.get("type", ""),
                            "message": error.get("message", ""),
                            "context": error.get("context", {})
                        },
                        success=False
                    )
            
            # Extract fix patterns (if any)
            fixes = run_data.get("fixes_applied", [])
            for fix in fixes:
                fix_signature = self._extract_fix_pattern(fix)
                if fix_signature:
                    self.graph.record_pattern(
                        pattern_type="fix",
                        signature=fix_signature,
                        data={
                            "fix_type": fix.get("type", ""),
                            "description": fix.get("description", ""),
                            "effectiveness": fix.get("effectiveness", 1.0)
                        },
                        success=success
                    )
            
            # Extract technique patterns
            model = run_data.get("model_used", "")
            stages = run_data.get("stages", [])
            if model and stages:
                technique_signature = f"{model}:{','.join(stages)}"
                self.graph.record_pattern(
                    pattern_type="technique",
                    signature=technique_signature,
                    data={
                        "model": model,
                        "stages": stages,
                        "duration": run_data.get("duration", 0)
                    },
                    success=success
                )
            
            logger.info(f"Learned patterns from run (success={success})")
            
        except Exception as e:
            logger.error(f"Failed to learn from run: {e}")
    
    def _extract_problem_pattern(self, run_data: Dict[str, Any]) -> str:
        """Extract problem pattern signature"""
        idea = run_data.get("idea", "").lower()
        
        # Extract key problem indicators
        keywords = []
        
        # Programming language
        for lang in ["python", "javascript", "java", "c++", "rust", "go"]:
            if lang in idea:
                keywords.append(f"lang:{lang}")
        
        # Project type
        for proj_type in ["api", "cli", "web", "game", "ml", "data", "automation"]:
            if proj_type in idea:
                keywords.append(f"type:{proj_type}")
        
        # Complexity indicators
        if "simple" in idea or "basic" in idea:
            keywords.append("complexity:low")
        elif "complex" in idea or "advanced" in idea:
            keywords.append("complexity:high")
        else:
            keywords.append("complexity:medium")
        
        if not keywords:
            # Hash the idea as fallback
            return hashlib.md5(idea.encode()).hexdigest()[:12]
        
        return "|".join(sorted(keywords))
    
    def _extract_solution_pattern(self, run_data: Dict[str, Any]) -> str:
        """Extract solution pattern signature"""
        files = run_data.get("files_generated", [])
        
        # Extract file structure pattern
        file_types = []
        for file_path in files:
            path = Path(file_path)
            file_types.append(path.suffix or "dir")
        
        # Count file types
        type_counts = Counter(file_types)
        pattern_parts = [f"{ext}:{count}" for ext, count in sorted(type_counts.items())]
        
        return "|".join(pattern_parts)
    
    def _extract_error_pattern(self, error: Dict[str, Any]) -> str:
        """Extract error pattern signature"""
        error_type = error.get("type", "").lower()
        message = error.get("message", "").lower()
        
        # Common error patterns
        if "syntax" in error_type or "syntax" in message:
            return "error:syntax"
        elif "import" in error_type or "import" in message:
            return "error:import"
        elif "type" in error_type or "type" in message:
            return "error:type"
        elif "name" in error_type or "undefined" in message:
            return "error:undefined"
        elif "file not found" in message or "no such file" in message:
            return "error:file_not_found"
        else:
            # Hash error message for unique patterns
            return f"error:{hashlib.md5(message.encode()).hexdigest()[:8]}"
    
    def _extract_fix_pattern(self, fix: Dict[str, Any]) -> str:
        """Extract fix pattern signature"""
        fix_type = fix.get("type", "").lower()
        
        # Common fix patterns
        if "import" in fix_type:
            return "fix:add_import"
        elif "syntax" in fix_type:
            return "fix:syntax_correction"
        elif "type" in fix_type:
            return "fix:type_annotation"
        elif "refactor" in fix_type:
            return "fix:refactor"
        elif "rename" in fix_type:
            return "fix:rename"
        else:
            return f"fix:{fix_type}"
    
    def get_similar_problems(
        self,
        problem_description: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find similar problems from past runs
        
        Args:
            problem_description: Problem description
            limit: Maximum results
            
        Returns:
            List of similar problem patterns
        """
        # Extract pattern from description
        problem_pattern = self._extract_problem_pattern({"idea": problem_description})
        
        # Get all problem patterns
        all_patterns = self.graph.get_patterns(
            pattern_type="problem",
            min_occurrences=1
        )
        
        # Score similarity
        scored_patterns = []
        for pattern in all_patterns:
            signature = pattern["signature"]
            
            # Simple keyword overlap scoring
            pattern_keywords = set(signature.split("|"))
            query_keywords = set(problem_pattern.split("|"))
            
            overlap = len(pattern_keywords & query_keywords)
            total = len(pattern_keywords | query_keywords)
            
            if total > 0:
                similarity = overlap / total
                pattern["similarity"] = similarity
                scored_patterns.append(pattern)
        
        # Sort by similarity and success rate
        scored_patterns.sort(
            key=lambda p: (p["similarity"], p["success_rate"]),
            reverse=True
        )
        
        return scored_patterns[:limit]
    
    def get_solution_template(
        self,
        problem_description: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get a solution template for a problem
        
        Args:
            problem_description: Problem description
            
        Returns:
            Solution template or None
        """
        # Find similar successful problems
        similar = self.get_similar_problems(problem_description, limit=3)
        
        if not similar:
            return None
        
        # Get solutions for most similar problem
        best_match = similar[0]
        
        # Find solution patterns with high success rate
        solutions = self.graph.get_patterns(
            pattern_type="solution",
            min_success_rate=0.7
        )
        
        if not solutions:
            return None
        
        # Return most frequently used solution
        solutions.sort(key=lambda s: s["occurrences"], reverse=True)
        
        return {
            "template": solutions[0],
            "similar_problem": best_match,
            "confidence": best_match.get("similarity", 0.0) * solutions[0].get("success_rate", 0.0)
        }
    
    def get_common_errors(
        self,
        min_occurrences: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Get common error patterns
        
        Args:
            min_occurrences: Minimum occurrences
            
        Returns:
            List of common error patterns
        """
        errors = self.graph.get_patterns(
            pattern_type="error",
            min_occurrences=min_occurrences
        )
        
        # Sort by occurrence frequency
        errors.sort(key=lambda e: e["occurrences"], reverse=True)
        
        return errors
    
    def get_effective_fixes(
        self,
        error_signature: str
    ) -> List[Dict[str, Any]]:
        """
        Get effective fixes for an error pattern
        
        Args:
            error_signature: Error pattern signature
            
        Returns:
            List of effective fix patterns
        """
        # Get fix patterns with high success rate
        fixes = self.graph.get_patterns(
            pattern_type="fix",
            min_success_rate=0.6
        )
        
        # TODO: Link errors to fixes via graph edges
        # For now, return all effective fixes
        
        fixes.sort(
            key=lambda f: (f["success_rate"], f["occurrences"]),
            reverse=True
        )
        
        return fixes[:5]
    
    def get_best_techniques(
        self,
        problem_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get best techniques (model + stage combinations)
        
        Args:
            problem_type: Filter by problem type
            
        Returns:
            List of technique patterns sorted by effectiveness
        """
        techniques = self.graph.get_patterns(
            pattern_type="technique",
            min_occurrences=2,
            min_success_rate=0.5
        )
        
        # Sort by success rate and occurrences
        techniques.sort(
            key=lambda t: (t["success_rate"], t["occurrences"]),
            reverse=True
        )
        
        return techniques[:10]
    
    def generate_report(self) -> str:
        """Generate a learning report"""
        lines = ["# Pattern Learning Report", ""]
        
        # Problem patterns
        problems = self.graph.get_patterns(pattern_type="problem")
        lines.append(f"## Problem Patterns: {len(problems)}")
        lines.append("")
        
        if problems:
            # Top successful problems
            successful = [p for p in problems if p["success_rate"] >= 0.7]
            lines.append(f"### Successful: {len(successful)} ({len(successful)/len(problems)*100:.1f}%)")
            for p in successful[:5]:
                lines.append(f"- {p['signature']}: {p['occurrences']} runs, {p['success_rate']*100:.0f}% success")
            lines.append("")
        
        # Solution patterns
        solutions = self.graph.get_patterns(pattern_type="solution")
        lines.append(f"## Solution Patterns: {len(solutions)}")
        lines.append("")
        
        if solutions:
            solutions.sort(key=lambda s: s["occurrences"], reverse=True)
            lines.append("### Most Common:")
            for s in solutions[:5]:
                lines.append(f"- {s['signature']}: {s['occurrences']} times, {s['success_rate']*100:.0f}% success")
            lines.append("")
        
        # Error patterns
        errors = self.graph.get_patterns(pattern_type="error")
        lines.append(f"## Error Patterns: {len(errors)}")
        lines.append("")
        
        if errors:
            errors.sort(key=lambda e: e["occurrences"], reverse=True)
            lines.append("### Most Frequent:")
            for e in errors[:5]:
                lines.append(f"- {e['signature']}: {e['occurrences']} occurrences")
            lines.append("")
        
        # Fix patterns
        fixes = self.graph.get_patterns(pattern_type="fix")
        lines.append(f"## Fix Patterns: {len(fixes)}")
        lines.append("")
        
        if fixes:
            effective = [f for f in fixes if f["success_rate"] >= 0.7]
            lines.append(f"### Effective: {len(effective)} ({len(effective)/len(fixes)*100:.1f}%)")
            for f in effective[:5]:
                lines.append(f"- {f['signature']}: {f['occurrences']} times, {f['success_rate']*100:.0f}% success")
            lines.append("")
        
        # Technique patterns
        techniques = self.graph.get_patterns(pattern_type="technique")
        lines.append(f"## Technique Patterns: {len(techniques)}")
        lines.append("")
        
        if techniques:
            techniques.sort(
                key=lambda t: (t["success_rate"], t["occurrences"]),
                reverse=True
            )
            lines.append("### Best Performing:")
            for t in techniques[:5]:
                lines.append(f"- {t['signature']}: {t['success_rate']*100:.0f}% success over {t['occurrences']} runs")
            lines.append("")
        
        return "\n".join(lines)
