"""
Integration #13: Consensus Selector for Parallel Multi-Model Generation

Implements intelligent selection algorithms to choose the best response from multiple model outputs.
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ScoredResponse:
    """Response with quality scores."""
    content: str
    model: str
    backend: str
    total_score: float
    scores: Dict[str, float]  # Individual criterion scores
    metadata: Dict[str, Any]


class ConsensusSelector:
    """
    Selects best response from multiple model outputs using various strategies.
    
    Strategies:
    1. Quality Scoring - Score each response on multiple criteria
    2. Majority Vote - For classification/choice tasks
    3. Ensemble - For numerical tasks
    """
    
    def __init__(
        self,
        strategy: str = "quality_score",
        quality_weights: Optional[Dict[str, float]] = None
    ):
        """
        Initialize consensus selector.
        
        Args:
            strategy: Selection strategy ("quality_score", "majority_vote", "ensemble")
            quality_weights: Custom weights for quality criteria
        """
        self.strategy = strategy
        
        # Default quality weights
        self.quality_weights = quality_weights or {
            'completeness': 0.30,   # Addresses all aspects
            'correctness': 0.30,    # Logic seems sound
            'clarity': 0.20,        # Easy to understand
            'structure': 0.10,      # Well-formatted
            'brevity': 0.10         # Not unnecessarily verbose
        }
        
        logger.info(f"ConsensusSelector initialized with strategy={strategy}")
    
    def select_best(
        self,
        responses: List[Dict[str, Any]],
        task_type: str = "general"
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Select best response using configured strategy.
        
        Args:
            responses: List of response dicts with 'content', 'model', 'backend', etc.
            task_type: Type of task (affects selection logic)
            
        Returns:
            Tuple of (best_content, metadata)
        """
        if not responses:
            raise ValueError("No responses to select from")
        
        if len(responses) == 1:
            logger.info("Only one response, returning it")
            return responses[0]['content'], {'single_response': True}
        
        # Route to appropriate strategy
        if self.strategy == "quality_score":
            return self._select_by_quality_score(responses, task_type)
        elif self.strategy == "majority_vote":
            return self._select_by_majority_vote(responses)
        elif self.strategy == "ensemble":
            return self._select_by_ensemble(responses)
        else:
            logger.warning(f"Unknown strategy {self.strategy}, using quality_score")
            return self._select_by_quality_score(responses, task_type)
    
    def _select_by_quality_score(
        self,
        responses: List[Dict[str, Any]],
        task_type: str
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Select response with highest quality score.
        
        Scores each response on:
        - Completeness (addresses all requirements)
        - Correctness (logical soundness)
        - Clarity (readability)
        - Structure (formatting)
        - Brevity (conciseness)
        """
        scored_responses = []
        
        for response in responses:
            content = response.get('content', '')
            model = response.get('model', 'unknown')
            backend = response.get('backend', 'unknown')
            
            # Calculate individual scores
            scores = {
                'completeness': self._score_completeness(content, task_type),
                'correctness': self._score_correctness(content, task_type),
                'clarity': self._score_clarity(content),
                'structure': self._score_structure(content, task_type),
                'brevity': self._score_brevity(content)
            }
            
            # Calculate weighted total
            total_score = sum(
                scores[criterion] * weight
                for criterion, weight in self.quality_weights.items()
            )
            
            scored = ScoredResponse(
                content=content,
                model=model,
                backend=backend,
                total_score=total_score,
                scores=scores,
                metadata=response
            )
            scored_responses.append(scored)
        
        # Sort by total score
        scored_responses.sort(key=lambda x: x.total_score, reverse=True)
        
        # Get best
        best = scored_responses[0]
        
        logger.info(f"Best response: model={best.model}, score={best.total_score:.3f}")
        logger.debug(f"  Individual scores: {best.scores}")
        
        # Prepare metadata
        metadata = {
            'selection_strategy': 'quality_score',
            'total_responses': len(responses),
            'best_model': best.model,
            'best_backend': best.backend,
            'best_score': best.total_score,
            'scores_breakdown': best.scores,
            'all_scores': [
                {
                    'model': r.model,
                    'score': r.total_score,
                    'breakdown': r.scores
                }
                for r in scored_responses
            ]
        }
        
        return best.content, metadata
    
    def _score_completeness(self, content: str, task_type: str) -> float:
        """
        Score completeness based on content length and coverage.
        
        Returns: 0.0 to 1.0
        """
        # Base score on reasonable length
        length = len(content)
        
        if task_type == "code_generation":
            # Code should be substantial but not bloated
            optimal_length = 1500  # ~50 lines of code
            if length < 200:
                return 0.2  # Too short
            elif length < optimal_length:
                return length / optimal_length
            elif length < optimal_length * 3:
                return 1.0
            else:
                return 0.8  # Too long, might be bloated
        
        elif task_type == "critique":
            # Critique should be detailed
            optimal_length = 800
            if length < 100:
                return 0.1
            elif length < optimal_length:
                return length / optimal_length
            else:
                return 1.0
        
        else:
            # General response
            optimal_length = 600
            if length < 50:
                return 0.1
            elif length < optimal_length:
                return length / optimal_length
            else:
                return min(1.0, optimal_length / length)
    
    def _score_correctness(self, content: str, task_type: str) -> float:
        """
        Score correctness by looking for error indicators.
        
        Returns: 0.0 to 1.0
        """
        score = 1.0
        
        # Penalize error indicators
        error_indicators = [
            "error", "exception", "failed", "incorrect",
            "wrong", "invalid", "bug", "issue"
        ]
        
        content_lower = content.lower()
        for indicator in error_indicators:
            if indicator in content_lower:
                score -= 0.1
        
        # Bonus for correctness indicators
        correctness_indicators = [
            "correct", "valid", "works", "successful",
            "passes", "tested", "verified"
        ]
        
        for indicator in correctness_indicators:
            if indicator in content_lower:
                score += 0.05
        
        # Penalize if code has obvious syntax errors (for code generation)
        if task_type == "code_generation":
            if "def (" in content or "def)" in content:  # Missing function name
                score -= 0.3
            if content.count("(") != content.count(")"):  # Unmatched parens
                score -= 0.2
            if content.count("{") != content.count("}"):  # Unmatched braces
                score -= 0.2
        
        return max(0.0, min(1.0, score))
    
    def _score_clarity(self, content: str) -> float:
        """
        Score clarity based on readability and formatting.
        
        Returns: 0.0 to 1.0
        """
        score = 0.5  # Start at middle
        
        # Bonus for good formatting
        if "```" in content:  # Has code blocks
            score += 0.15
        
        if "\n\n" in content:  # Has paragraphs/sections
            score += 0.10
        
        # Check for explanations
        explanation_markers = ["#", "//", "/*", "'''", '"""', "Note:", "Example:"]
        if any(marker in content for marker in explanation_markers):
            score += 0.15
        
        # Penalize wall of text
        lines = content.split('\n')
        avg_line_length = sum(len(line) for line in lines) / max(len(lines), 1)
        if avg_line_length > 120:
            score -= 0.1
        
        # Penalize excessive capitalization
        caps_ratio = sum(1 for c in content if c.isupper()) / max(len(content), 1)
        if caps_ratio > 0.2:
            score -= 0.1
        
        return max(0.0, min(1.0, score))
    
    def _score_structure(self, content: str, task_type: str) -> float:
        """
        Score structure based on organization and formatting.
        
        Returns: 0.0 to 1.0
        """
        score = 0.5
        
        if task_type == "code_generation":
            # Look for good code structure
            if "def " in content or "class " in content:
                score += 0.15
            if "import " in content:
                score += 0.10
            if "return " in content:
                score += 0.10
            if '"""' in content or "'''" in content:  # Docstrings
                score += 0.15
        
        elif task_type == "critique":
            # Look for organized critique
            if "Strengths:" in content or "Weaknesses:" in content:
                score += 0.20
            if any(marker in content for marker in ["1.", "2.", "3.", "- ", "* "]):
                score += 0.15
        
        else:
            # General structure
            if any(header in content for header in ["##", "###", "**"]):
                score += 0.15
            if any(marker in content for marker in ["- ", "* ", "1.", "2."]):
                score += 0.15
        
        return max(0.0, min(1.0, score))
    
    def _score_brevity(self, content: str) -> float:
        """
        Score brevity (not too verbose).
        
        Returns: 0.0 to 1.0
        """
        length = len(content)
        
        # Optimal range: 500-2000 chars
        if length < 100:
            return 0.3  # Too short
        elif length < 500:
            return 0.7
        elif length < 2000:
            return 1.0  # Sweet spot
        elif length < 5000:
            return 0.8  # A bit long
        else:
            return 0.5  # Too verbose
    
    def _select_by_majority_vote(
        self,
        responses: List[Dict[str, Any]]
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Select response by majority vote (for classification/choice tasks).
        
        Finds the most common response.
        """
        # Extract contents
        contents = [r.get('content', '') for r in responses]
        
        # Count occurrences
        from collections import Counter
        counter = Counter(contents)
        
        # Get most common
        most_common_content, count = counter.most_common(1)[0]
        
        # Find the response object
        best_response = next(
            r for r in responses 
            if r.get('content') == most_common_content
        )
        
        logger.info(f"Majority vote: {count}/{len(responses)} models agreed")
        
        metadata = {
            'selection_strategy': 'majority_vote',
            'total_responses': len(responses),
            'votes_for_winner': count,
            'consensus_ratio': count / len(responses),
            'model': best_response.get('model'),
            'all_votes': dict(counter)
        }
        
        return most_common_content, metadata
    
    def _select_by_ensemble(
        self,
        responses: List[Dict[str, Any]]
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Select by ensemble (for numerical tasks).
        
        Returns average/median of responses.
        """
        # Try to extract numbers from responses
        numbers = []
        for response in responses:
            content = response.get('content', '')
            # Find numbers in response
            matches = re.findall(r'\d+\.?\d*', content)
            if matches:
                try:
                    num = float(matches[0])
                    numbers.append(num)
                except:
                    pass
        
        if not numbers:
            logger.warning("No numbers found for ensemble, falling back to quality score")
            return self._select_by_quality_score(responses, "general")
        
        # Calculate ensemble value (median more robust than mean)
        ensemble_value = sorted(numbers)[len(numbers) // 2]
        
        # Find response closest to ensemble value
        best_idx = min(
            range(len(numbers)),
            key=lambda i: abs(numbers[i] - ensemble_value)
        )
        
        best_response = responses[best_idx]
        
        logger.info(f"Ensemble: median={ensemble_value}, selected={numbers[best_idx]}")
        
        metadata = {
            'selection_strategy': 'ensemble',
            'total_responses': len(responses),
            'all_values': numbers,
            'ensemble_value': ensemble_value,
            'selected_value': numbers[best_idx],
            'model': best_response.get('model')
        }
        
        return best_response.get('content', ''), metadata


# Factory function
def get_consensus_selector(
    strategy: str = "quality_score",
    quality_weights: Optional[Dict[str, float]] = None
) -> ConsensusSelector:
    """
    Get a ConsensusSelector instance.
    
    Args:
        strategy: Selection strategy
        quality_weights: Custom weights for quality scoring
        
    Returns:
        ConsensusSelector instance
    """
    return ConsensusSelector(strategy=strategy, quality_weights=quality_weights)


# Test code
if __name__ == "__main__":
    print("\n" + "="*80)
    print("INTEGRATION #13: CONSENSUS SELECTOR TEST")
    print("="*80)
    
    # Test responses
    responses = [
        {
            'content': '''def binary_search(arr, target):
    """Binary search implementation."""
    left, right = 0, len(arr) - 1
    
    while left <= right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    
    return -1''',
            'model': 'qwen3-coder',
            'backend': 'groq'
        },
        {
            'content': '''def binary_search(arr, target):
    left = 0
    right = len(arr) - 1
    while left <= right:
        mid = left + (right - left) / 2
        if arr[mid] == target:
            return mid''',
            'model': 'mimo-v2',
            'backend': 'openrouter'
        },
        {
            'content': '''Here's a binary search:

```python
def binary_search(arr, target):
    """
    Perform binary search on sorted array.
    
    Args:
        arr: Sorted array
        target: Value to find
        
    Returns:
        Index of target or -1 if not found
    """
    left, right = 0, len(arr) - 1
    
    while left <= right:
        mid = (left + right) // 2
        
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    
    return -1

# Example usage
arr = [1, 3, 5, 7, 9]
result = binary_search(arr, 5)
print(f"Found at index: {result}")
```

This implementation has O(log n) time complexity.''',
            'model': 'devstral',
            'backend': 'openrouter'
        }
    ]
    
    # Test quality scoring
    selector = ConsensusSelector(strategy="quality_score")
    best_content, metadata = selector.select_best(responses, task_type="code_generation")
    
    print(f"\n✅ Best Response Selected:")
    print(f"  Model: {metadata['best_model']}")
    print(f"  Backend: {metadata['best_backend']}")
    print(f"  Score: {metadata['best_score']:.3f}")
    print(f"\n  Score Breakdown:")
    for criterion, score in metadata['scores_breakdown'].items():
        print(f"    {criterion}: {score:.3f}")
    
    print(f"\n  All Scores:")
    for i, score_info in enumerate(metadata['all_scores'], 1):
        print(f"    {i}. {score_info['model']}: {score_info['score']:.3f}")
    
    print(f"\n  Content Preview:")
    print(f"    {best_content[:200]}...")
    
    print("\n" + "="*80)
    print("✅ CONSENSUS SELECTOR TEST PASSED!")
    print("="*80)
