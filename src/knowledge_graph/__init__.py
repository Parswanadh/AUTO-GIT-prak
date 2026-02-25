"""Knowledge Graph Module (Integration #23)

SQLite + JSON-based knowledge storage for:
- Pattern learning from past runs
- Solution templates
- Common error patterns
- Best practices accumulation
"""

from .graph import KnowledgeGraph
from .pattern_learner import PatternLearner
from .query_engine import QueryEngine

__all__ = [
    "KnowledgeGraph",
    "PatternLearner",
    "QueryEngine",
]
