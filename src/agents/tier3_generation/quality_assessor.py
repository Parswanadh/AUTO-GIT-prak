"""
Quality Assessment System for Code Generation.

Provides multi-dimensional quality scoring for generated code:
1. Syntax validation (AST parsing)
2. Code complexity metrics (cyclomatic, cognitive)
3. Style compliance (PEP8, naming conventions)
4. Documentation quality (docstrings, comments)
5. Test coverage estimation
6. LLM-based semantic quality assessment

This integrates with Integration #5 (Test Generation) and provides
feedback for the debate/generation loop.
"""

import ast
import logging
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class CodeMetrics:
    """Quantitative code metrics."""
    lines_of_code: int = 0
    comment_lines: int = 0
    blank_lines: int = 0
    cyclomatic_complexity: int = 0
    cognitive_complexity: int = 0
    max_function_length: int = 0
    avg_function_length: float = 0.0
    num_functions: int = 0
    num_classes: int = 0
    comment_ratio: float = 0.0


@dataclass
class StyleIssue:
    """Style/quality issue found in code."""
    severity: str  # "error", "warning", "info"
    line: int
    column: int
    message: str
    rule: str  # e.g., "E501", "missing-docstring"


@dataclass
class QualityScore:
    """Multi-dimensional quality assessment."""
    overall_score: float = 0.0  # 0-100
    
    # Dimension scores (0-100 each)
    syntax_score: float = 0.0
    complexity_score: float = 0.0
    style_score: float = 0.0
    documentation_score: float = 0.0
    maintainability_score: float = 0.0
    semantic_score: float = 0.0
    
    # Detailed metrics
    metrics: Optional[CodeMetrics] = None
    issues: List[StyleIssue] = field(default_factory=list)
    
    # Quality gates
    passes_minimum: bool = False  # Overall > 60
    is_production_ready: bool = False  # Overall > 80
    
    # Feedback for improvement
    improvement_suggestions: List[str] = field(default_factory=list)
    critical_issues: List[str] = field(default_factory=list)


class QualityAssessor:
    """
    Multi-dimensional quality assessment for generated code.
    
    Evaluates:
    - Syntax correctness (AST parsing)
    - Code complexity (cyclomatic, cognitive)
    - Style compliance (PEP8-like rules)
    - Documentation quality
    - Maintainability metrics
    - Semantic quality (via LLM)
    
    Usage:
        assessor = QualityAssessor()
        score = await assessor.assess_code(code_content)
        
        if score.passes_minimum:
            print(f"Quality: {score.overall_score:.1f}/100")
        else:
            print(f"Failed: {score.critical_issues}")
    """
    
    def __init__(
        self,
        minimum_threshold: float = 60.0,
        production_threshold: float = 80.0,
        use_llm_assessment: bool = True
    ):
        """
        Initialize quality assessor.
        
        Args:
            minimum_threshold: Minimum score to pass (default: 60)
            production_threshold: Score needed for production (default: 80)
            use_llm_assessment: Enable LLM semantic assessment (default: True)
        """
        self.minimum_threshold = minimum_threshold
        self.production_threshold = production_threshold
        self.use_llm_assessment = use_llm_assessment
        
        logger.info(f"QualityAssessor initialized (min={minimum_threshold}, prod={production_threshold})")
    
    async def assess_code(
        self,
        code: str,
        filename: str = "code.py",
        context: Optional[str] = None
    ) -> QualityScore:
        """
        Perform comprehensive quality assessment.
        
        Args:
            code: Python code to assess
            filename: Name of file (for context)
            context: Additional context (e.g., purpose, requirements)
        
        Returns:
            QualityScore with multi-dimensional assessment
        """
        logger.info(f"Assessing quality for {filename} ({len(code)} chars)")
        
        score = QualityScore()
        
        # 1. Syntax validation (AST)
        syntax_valid, syntax_error = self._validate_syntax(code)
        if not syntax_valid:
            score.syntax_score = 0.0
            score.critical_issues.append(f"Syntax error: {syntax_error}")
            score.overall_score = 0.0
            return score
        
        score.syntax_score = 100.0
        logger.debug("✓ Syntax valid")
        
        # 2. Calculate metrics
        metrics = self._calculate_metrics(code)
        score.metrics = metrics
        
        # 3. Complexity assessment
        score.complexity_score = self._assess_complexity(metrics)
        logger.debug(f"✓ Complexity: {score.complexity_score:.1f}/100")
        
        # 4. Style compliance
        style_issues = self._check_style(code, filename)
        score.issues = style_issues
        score.style_score = self._calculate_style_score(style_issues)
        logger.debug(f"✓ Style: {score.style_score:.1f}/100 ({len(style_issues)} issues)")
        
        # 5. Documentation quality
        score.documentation_score = self._assess_documentation(code, metrics)
        logger.debug(f"✓ Documentation: {score.documentation_score:.1f}/100")
        
        # 6. Maintainability
        score.maintainability_score = self._assess_maintainability(metrics, style_issues)
        logger.debug(f"✓ Maintainability: {score.maintainability_score:.1f}/100")
        
        # 7. Semantic quality (LLM-based, optional)
        if self.use_llm_assessment:
            semantic_score, semantic_feedback = await self._llm_semantic_assessment(
                code, filename, context
            )
            score.semantic_score = semantic_score
            score.improvement_suggestions.extend(semantic_feedback)
            logger.debug(f"✓ Semantic: {score.semantic_score:.1f}/100")
        else:
            score.semantic_score = 70.0  # Neutral if not using LLM
        
        # 8. Calculate overall score (weighted average)
        score.overall_score = self._calculate_overall_score(score)
        
        # 9. Quality gates
        score.passes_minimum = score.overall_score >= self.minimum_threshold
        score.is_production_ready = score.overall_score >= self.production_threshold
        
        # 10. Generate improvement suggestions
        if not score.passes_minimum:
            score.improvement_suggestions.extend(
                self._generate_improvement_suggestions(score)
            )
        
        logger.info(f"✅ Quality assessment complete: {score.overall_score:.1f}/100")
        return score
    
    def _validate_syntax(self, code: str) -> Tuple[bool, Optional[str]]:
        """
        Validate Python syntax using AST.
        
        Args:
            code: Python code
        
        Returns:
            (is_valid, error_message)
        """
        try:
            ast.parse(code)
            return True, None
        except SyntaxError as e:
            return False, f"Line {e.lineno}: {e.msg}"
        except Exception as e:
            return False, str(e)
    
    def _calculate_metrics(self, code: str) -> CodeMetrics:
        """
        Calculate code metrics.
        
        Args:
            code: Python code
        
        Returns:
            CodeMetrics object
        """
        metrics = CodeMetrics()
        
        lines = code.split('\n')
        metrics.lines_of_code = len([l for l in lines if l.strip()])
        metrics.comment_lines = len([l for l in lines if l.strip().startswith('#')])
        metrics.blank_lines = len([l for l in lines if not l.strip()])
        
        if metrics.lines_of_code > 0:
            metrics.comment_ratio = metrics.comment_lines / metrics.lines_of_code
        
        # Parse AST for function/class metrics
        try:
            tree = ast.parse(code)
            
            function_lengths = []
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    metrics.num_functions += 1
                    # Estimate function length
                    if hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
                        func_len = node.end_lineno - node.lineno + 1
                        function_lengths.append(func_len)
                
                elif isinstance(node, ast.ClassDef):
                    metrics.num_classes += 1
            
            if function_lengths:
                metrics.max_function_length = max(function_lengths)
                metrics.avg_function_length = sum(function_lengths) / len(function_lengths)
            
            # Calculate cyclomatic complexity (simplified)
            metrics.cyclomatic_complexity = self._calculate_cyclomatic_complexity(tree)
            metrics.cognitive_complexity = self._calculate_cognitive_complexity(tree)
            
        except Exception as e:
            logger.warning(f"Metric calculation error: {e}")
        
        return metrics
    
    def _calculate_cyclomatic_complexity(self, tree: ast.AST) -> int:
        """
        Calculate cyclomatic complexity.
        
        McCabe's complexity = number of decision points + 1
        
        Args:
            tree: AST tree
        
        Returns:
            Complexity score
        """
        complexity = 1  # Base complexity
        
        for node in ast.walk(tree):
            # Decision points
            if isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(node, ast.BoolOp):
                complexity += len(node.values) - 1
        
        return complexity
    
    def _calculate_cognitive_complexity(self, tree: ast.AST) -> int:
        """
        Calculate cognitive complexity (simplified).
        
        More human-centric than cyclomatic complexity.
        Penalizes nested structures more heavily.
        
        Args:
            tree: AST tree
        
        Returns:
            Cognitive complexity score
        """
        complexity = 0
        
        def visit(node, depth=0):
            nonlocal complexity
            
            # Base increment for control flow
            if isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += (1 + depth)  # Nesting penalty
            
            elif isinstance(node, ast.BoolOp):
                complexity += 1
            
            # Recursively visit children with increased depth
            for child in ast.iter_child_nodes(node):
                if isinstance(node, (ast.If, ast.While, ast.For, ast.FunctionDef, ast.ClassDef)):
                    visit(child, depth + 1)
                else:
                    visit(child, depth)
        
        visit(tree)
        return complexity
    
    def _assess_complexity(self, metrics: CodeMetrics) -> float:
        """
        Score complexity (lower complexity = higher score).
        
        Args:
            metrics: Code metrics
        
        Returns:
            Score 0-100
        """
        # Cyclomatic complexity scoring
        cc_score = 100.0
        if metrics.cyclomatic_complexity > 50:
            cc_score = 0.0
        elif metrics.cyclomatic_complexity > 20:
            cc_score = 50.0
        elif metrics.cyclomatic_complexity > 10:
            cc_score = 75.0
        
        # Cognitive complexity scoring
        cog_score = 100.0
        if metrics.cognitive_complexity > 30:
            cog_score = 0.0
        elif metrics.cognitive_complexity > 15:
            cog_score = 50.0
        elif metrics.cognitive_complexity > 7:
            cog_score = 75.0
        
        # Function length scoring
        len_score = 100.0
        if metrics.max_function_length > 100:
            len_score = 50.0
        elif metrics.max_function_length > 50:
            len_score = 75.0
        
        # Weighted average
        return (cc_score * 0.4 + cog_score * 0.4 + len_score * 0.2)
    
    def _check_style(self, code: str, filename: str) -> List[StyleIssue]:
        """
        Check PEP8-like style issues.
        
        Args:
            code: Python code
            filename: Filename for context
        
        Returns:
            List of style issues
        """
        issues = []
        lines = code.split('\n')
        
        for i, line in enumerate(lines, 1):
            # Line length check (PEP8: 79 chars, relaxed to 100)
            if len(line) > 100:
                issues.append(StyleIssue(
                    severity="warning",
                    line=i,
                    column=100,
                    message=f"Line too long ({len(line)}/100)",
                    rule="E501"
                ))
            
            # Trailing whitespace
            if line.endswith(' ') or line.endswith('\t'):
                issues.append(StyleIssue(
                    severity="info",
                    line=i,
                    column=len(line),
                    message="Trailing whitespace",
                    rule="W291"
                ))
            
            # Multiple spaces after operator
            if '  ' in line and not line.strip().startswith('#'):
                issues.append(StyleIssue(
                    severity="info",
                    line=i,
                    column=line.index('  '),
                    message="Multiple spaces",
                    rule="E271"
                ))
        
        # Check for missing docstrings (AST-based)
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    if not ast.get_docstring(node):
                        issues.append(StyleIssue(
                            severity="warning",
                            line=node.lineno,
                            column=0,
                            message=f"{node.__class__.__name__} '{node.name}' has no docstring",
                            rule="D100"
                        ))
        except:
            pass
        
        return issues
    
    def _calculate_style_score(self, issues: List[StyleIssue]) -> float:
        """
        Calculate style score from issues.
        
        Args:
            issues: List of style issues
        
        Returns:
            Score 0-100
        """
        if not issues:
            return 100.0
        
        # Weight by severity
        error_count = sum(1 for i in issues if i.severity == "error")
        warning_count = sum(1 for i in issues if i.severity == "warning")
        info_count = sum(1 for i in issues if i.severity == "info")
        
        # Penalty calculation
        penalty = (error_count * 10) + (warning_count * 5) + (info_count * 2)
        
        score = max(0, 100 - penalty)
        return score
    
    def _assess_documentation(self, code: str, metrics: CodeMetrics) -> float:
        """
        Assess documentation quality.
        
        Args:
            code: Python code
            metrics: Code metrics
        
        Returns:
            Score 0-100
        """
        score = 50.0  # Base score
        
        # Comment ratio bonus
        if metrics.comment_ratio > 0.2:
            score += 20
        elif metrics.comment_ratio > 0.1:
            score += 10
        
        # Module docstring check
        try:
            tree = ast.parse(code)
            if ast.get_docstring(tree):
                score += 15
            
            # Function/class docstring coverage
            total_defs = 0
            documented_defs = 0
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    total_defs += 1
                    if ast.get_docstring(node):
                        documented_defs += 1
            
            if total_defs > 0:
                coverage = documented_defs / total_defs
                score += coverage * 15  # Up to 15 points
        except:
            pass
        
        return min(100, score)
    
    def _assess_maintainability(
        self,
        metrics: CodeMetrics,
        issues: List[StyleIssue]
    ) -> float:
        """
        Assess overall maintainability.
        
        Args:
            metrics: Code metrics
            issues: Style issues
        
        Returns:
            Score 0-100
        """
        score = 100.0
        
        # Complexity penalty
        if metrics.cyclomatic_complexity > 20:
            score -= 30
        elif metrics.cyclomatic_complexity > 10:
            score -= 15
        
        # Function length penalty
        if metrics.max_function_length > 100:
            score -= 20
        elif metrics.max_function_length > 50:
            score -= 10
        
        # Style issues penalty
        error_count = sum(1 for i in issues if i.severity == "error")
        warning_count = sum(1 for i in issues if i.severity == "warning")
        
        score -= (error_count * 5 + warning_count * 2)
        
        # Documentation bonus
        if metrics.comment_ratio > 0.15:
            score += 10
        
        return max(0, score)
    
    async def _llm_semantic_assessment(
        self,
        code: str,
        filename: str,
        context: Optional[str]
    ) -> Tuple[float, List[str]]:
        """
        LLM-based semantic quality assessment.
        
        Evaluates:
        - Code correctness and logic
        - Best practices adherence
        - Potential bugs
        - Design patterns usage
        
        Args:
            code: Python code
            filename: Filename
            context: Optional context
        
        Returns:
            (score, feedback_list)
        """
        # TODO: Integrate with HybridRouter when ready
        # For now, return neutral score
        logger.debug("LLM semantic assessment not yet implemented")
        return 70.0, []
    
    def _calculate_overall_score(self, score: QualityScore) -> float:
        """
        Calculate weighted overall score.
        
        Weights:
        - Syntax: 20% (critical)
        - Complexity: 15%
        - Style: 15%
        - Documentation: 15%
        - Maintainability: 20%
        - Semantic: 15%
        
        Args:
            score: QualityScore with dimension scores
        
        Returns:
            Overall score 0-100
        """
        weights = {
            'syntax': 0.20,
            'complexity': 0.15,
            'style': 0.15,
            'documentation': 0.15,
            'maintainability': 0.20,
            'semantic': 0.15
        }
        
        overall = (
            score.syntax_score * weights['syntax'] +
            score.complexity_score * weights['complexity'] +
            score.style_score * weights['style'] +
            score.documentation_score * weights['documentation'] +
            score.maintainability_score * weights['maintainability'] +
            score.semantic_score * weights['semantic']
        )
        
        return round(overall, 1)
    
    def _generate_improvement_suggestions(self, score: QualityScore) -> List[str]:
        """
        Generate actionable improvement suggestions.
        
        Args:
            score: QualityScore
        
        Returns:
            List of improvement suggestions
        """
        suggestions = []
        
        if score.complexity_score < 60:
            suggestions.append(
                "Reduce complexity: Break down large functions into smaller ones"
            )
        
        if score.style_score < 70:
            suggestions.append(
                f"Fix style issues: {len(score.issues)} issues found (run linter)"
            )
        
        if score.documentation_score < 60:
            suggestions.append(
                "Add documentation: Include docstrings for all functions/classes"
            )
        
        if score.maintainability_score < 70:
            suggestions.append(
                "Improve maintainability: Simplify logic and add comments"
            )
        
        if score.metrics and score.metrics.comment_ratio < 0.1:
            suggestions.append(
                "Add more comments: Current ratio is too low"
            )
        
        return suggestions


# Convenience function for quick assessment
async def assess_code_quality(
    code: str,
    filename: str = "code.py",
    minimum_threshold: float = 60.0
) -> QualityScore:
    """
    Quick quality assessment of code.
    
    Args:
        code: Python code to assess
        filename: Filename for context
        minimum_threshold: Minimum passing score
    
    Returns:
        QualityScore
    
    Example:
        score = await assess_code_quality(generated_code)
        if score.passes_minimum:
            print(f"✅ Quality: {score.overall_score:.1f}/100")
        else:
            print(f"❌ Failed: {score.critical_issues}")
    """
    assessor = QualityAssessor(minimum_threshold=minimum_threshold)
    return await assessor.assess_code(code, filename)
