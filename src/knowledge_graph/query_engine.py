"""Query Engine - Natural language queries over knowledge graph"""

import logging
import hashlib
from typing import List, Dict, Any, Optional

from .graph import KnowledgeGraph
from .pattern_learner import PatternLearner

logger = logging.getLogger(__name__)


class QueryEngine:
    """
    Query knowledge graph using natural language
    
    Features:
    - Pattern matching
    - Similarity search
    - Recommendation generation
    - Knowledge retrieval
    """
    
    def __init__(self, graph: KnowledgeGraph, learner: PatternLearner):
        """Initialize query engine"""
        self.graph = graph
        self.learner = learner
        logger.info("Query engine initialized")
    
    def query(self, query_text: str) -> Dict[str, Any]:
        """
        Execute a natural language query
        
        Args:
            query_text: Query in natural language
            
        Returns:
            Query results with relevant patterns and recommendations
        """
        query_lower = query_text.lower()
        
        results = {
            "query": query_text,
            "patterns": [],
            "recommendations": [],
            "related_nodes": [],
            "stats": {}
        }
        
        try:
            # Detect query type and route
            if any(word in query_lower for word in ["error", "fail", "problem"]):
                results.update(self._query_errors(query_text))
            elif any(word in query_lower for word in ["solution", "fix", "resolve"]):
                results.update(self._query_solutions(query_text))
            elif any(word in query_lower for word in ["similar", "like", "related"]):
                results.update(self._query_similar(query_text))
            elif any(word in query_lower for word in ["best", "recommend", "suggest"]):
                results.update(self._query_recommendations(query_text))
            elif any(word in query_lower for word in ["stats", "statistics", "summary"]):
                results.update(self._query_stats())
            else:
                # General search
                results.update(self._query_general(query_text))
            
            logger.info(f"Query executed: {query_text}")
            
        except Exception as e:
            logger.error(f"Query failed: {e}")
            results["error"] = str(e)
        
        return results
    
    def _query_errors(self, query_text: str) -> Dict[str, Any]:
        """Query for error patterns"""
        errors = self.learner.get_common_errors(min_occurrences=1)
        
        # Filter errors by relevance
        relevant = []
        query_words = set(query_text.lower().split())
        
        for error in errors:
            error_data = error.get("data", {})
            error_text = f"{error['signature']} {error_data.get('message', '')}".lower()
            error_words = set(error_text.split())
            
            # Calculate relevance
            overlap = len(query_words & error_words)
            if overlap > 0:
                error["relevance"] = overlap / len(query_words)
                relevant.append(error)
        
        # Sort by relevance
        relevant.sort(key=lambda e: e.get("relevance", 0), reverse=True)
        
        # Get fixes for top errors
        recommendations = []
        for error in relevant[:3]:
            fixes = self.learner.get_effective_fixes(error["signature"])
            if fixes:
                recommendations.append({
                    "error": error["signature"],
                    "fixes": fixes[:3]
                })
        
        return {
            "patterns": relevant[:10],
            "recommendations": recommendations,
            "type": "error_query"
        }
    
    def _query_solutions(self, query_text: str) -> Dict[str, Any]:
        """Query for solution patterns"""
        solutions = self.graph.get_patterns(
            pattern_type="solution",
            min_success_rate=0.5
        )
        
        # Get solution template
        template = self.learner.get_solution_template(query_text)
        
        recommendations = []
        if template:
            recommendations.append({
                "type": "solution_template",
                "template": template["template"],
                "confidence": template["confidence"]
            })
        
        return {
            "patterns": solutions[:10],
            "recommendations": recommendations,
            "type": "solution_query"
        }
    
    def _query_similar(self, query_text: str) -> Dict[str, Any]:
        """Query for similar patterns"""
        # Extract problem from query
        # Remove "similar to", "like", etc.
        clean_query = query_text.lower()
        for phrase in ["similar to", "like", "related to"]:
            clean_query = clean_query.replace(phrase, "")
        
        similar_problems = self.learner.get_similar_problems(
            clean_query.strip(),
            limit=10
        )
        
        return {
            "patterns": similar_problems,
            "type": "similarity_query"
        }
    
    def _query_recommendations(self, query_text: str) -> Dict[str, Any]:
        """Query for recommendations"""
        recommendations = []
        
        # Get best techniques
        techniques = self.learner.get_best_techniques()
        if techniques:
            recommendations.append({
                "type": "techniques",
                "data": techniques[:5],
                "message": "Most effective model + stage combinations"
            })
        
        # Get solution template
        template = self.learner.get_solution_template(query_text)
        if template:
            recommendations.append({
                "type": "solution_template",
                "data": template,
                "message": "Suggested solution template based on similar problems"
            })
        
        # Get common patterns
        solutions = self.graph.get_patterns(
            pattern_type="solution",
            min_success_rate=0.8,
            min_occurrences=2
        )
        if solutions:
            recommendations.append({
                "type": "proven_solutions",
                "data": solutions[:5],
                "message": "Proven solution patterns with high success rate"
            })
        
        return {
            "recommendations": recommendations,
            "type": "recommendation_query"
        }
    
    def _query_stats(self) -> Dict[str, Any]:
        """Query for statistics"""
        stats = self.graph.get_stats()
        
        # Get pattern statistics
        for pattern_type in ["problem", "solution", "error", "fix", "technique"]:
            patterns = self.graph.get_patterns(pattern_type=pattern_type)
            
            if patterns:
                total = len(patterns)
                avg_occurrences = sum(p["occurrences"] for p in patterns) / total
                avg_success = sum(p["success_rate"] for p in patterns) / total
                
                stats[f"{pattern_type}_patterns"] = {
                    "count": total,
                    "avg_occurrences": avg_occurrences,
                    "avg_success_rate": avg_success
                }
        
        return {
            "stats": stats,
            "type": "stats_query"
        }
    
    def _query_general(self, query_text: str) -> Dict[str, Any]:
        """General query across all pattern types"""
        all_patterns = []
        
        for pattern_type in ["problem", "solution", "error", "fix", "technique"]:
            patterns = self.graph.get_patterns(
                pattern_type=pattern_type,
                min_occurrences=1
            )
            
            # Score relevance
            query_words = set(query_text.lower().split())
            
            for pattern in patterns:
                pattern_text = f"{pattern['signature']} {pattern.get('data', {})}".lower()
                pattern_words = set(pattern_text.split())
                
                overlap = len(query_words & pattern_words)
                if overlap > 0:
                    pattern["relevance"] = overlap / len(query_words)
                    pattern["pattern_type"] = pattern_type
                    all_patterns.append(pattern)
        
        # Sort by relevance
        all_patterns.sort(key=lambda p: p.get("relevance", 0), reverse=True)
        
        return {
            "patterns": all_patterns[:20],
            "type": "general_query"
        }
    
    def find_solutions_for_error(
        self,
        error_description: str
    ) -> List[Dict[str, Any]]:
        """
        Find solutions for a specific error
        
        Args:
            error_description: Error description or message
            
        Returns:
            List of potential solutions
        """
        # Extract error pattern
        error_pattern = self.learner._extract_error_pattern({
            "type": "error",
            "message": error_description
        })
        
        # Get effective fixes
        fixes = self.learner.get_effective_fixes(error_pattern)
        
        return fixes
    
    def suggest_improvements(
        self,
        current_approach: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Suggest improvements based on current approach
        
        Args:
            current_approach: Current approach details (model, stages, etc.)
            
        Returns:
            List of improvement suggestions
        """
        suggestions = []
        
        # Get best techniques
        best_techniques = self.learner.get_best_techniques()
        
        current_model = current_approach.get("model", "")
        current_stages = current_approach.get("stages", [])
        
        # Compare with best techniques
        for technique in best_techniques[:5]:
            tech_data = technique.get("data", {})
            tech_model = tech_data.get("model", "")
            tech_stages = tech_data.get("stages", [])
            
            if tech_model != current_model or tech_stages != current_stages:
                suggestions.append({
                    "type": "technique_alternative",
                    "current": {
                        "model": current_model,
                        "stages": current_stages
                    },
                    "suggested": {
                        "model": tech_model,
                        "stages": tech_stages
                    },
                    "success_rate": technique["success_rate"],
                    "occurrences": technique["occurrences"],
                    "reason": f"This technique has {technique['success_rate']*100:.0f}% success rate over {technique['occurrences']} runs"
                })
        
        return suggestions
    
    def get_learning_insights(self) -> Dict[str, Any]:
        """Get insights from accumulated knowledge"""
        insights = {
            "total_patterns": 0,
            "success_trends": [],
            "common_failures": [],
            "best_practices": [],
            "improvement_areas": []
        }
        
        # Get all patterns
        all_pattern_types = ["problem", "solution", "error", "fix", "technique"]
        
        for pattern_type in all_pattern_types:
            patterns = self.graph.get_patterns(pattern_type=pattern_type)
            insights["total_patterns"] += len(patterns)
            
            if pattern_type == "problem":
                # Success trends
                successful = [p for p in patterns if p["success_rate"] >= 0.8]
                if successful:
                    insights["success_trends"].append({
                        "category": "problems",
                        "count": len(successful),
                        "avg_success": sum(p["success_rate"] for p in successful) / len(successful)
                    })
            
            elif pattern_type == "error":
                # Common failures
                common_errors = [p for p in patterns if p["occurrences"] >= 3]
                common_errors.sort(key=lambda e: e["occurrences"], reverse=True)
                insights["common_failures"] = common_errors[:5]
            
            elif pattern_type == "technique":
                # Best practices
                best_techniques = [p for p in patterns if p["success_rate"] >= 0.9]
                best_techniques.sort(
                    key=lambda t: (t["success_rate"], t["occurrences"]),
                    reverse=True
                )
                insights["best_practices"] = best_techniques[:5]
            
            elif pattern_type == "fix":
                # Improvement areas (ineffective fixes)
                ineffective = [p for p in patterns if p["success_rate"] < 0.5]
                insights["improvement_areas"].extend(ineffective[:5])
        
        return insights
    
    def export_knowledge_summary(self) -> str:
        """Export a human-readable knowledge summary"""
        lines = ["# Knowledge Graph Summary", ""]
        
        # Stats
        stats = self.graph.get_stats()
        lines.append("## Statistics")
        lines.append(f"- Total Nodes: {stats.get('total_nodes', 0)}")
        lines.append(f"- Total Edges: {stats.get('total_edges', 0)}")
        lines.append(f"- Total Patterns: {stats.get('total_patterns', 0)}")
        lines.append("")
        
        # Insights
        insights = self.get_learning_insights()
        
        lines.append("## Best Practices")
        for practice in insights["best_practices"][:5]:
            lines.append(f"- {practice['signature']}: {practice['success_rate']*100:.0f}% success, {practice['occurrences']} runs")
        lines.append("")
        
        lines.append("## Common Failures")
        for failure in insights["common_failures"][:5]:
            lines.append(f"- {failure['signature']}: {failure['occurrences']} occurrences")
        lines.append("")
        
        lines.append("## Improvement Areas")
        for area in insights["improvement_areas"][:5]:
            lines.append(f"- {area['signature']}: Only {area['success_rate']*100:.0f}% effective")
        lines.append("")
        
        return "\n".join(lines)
