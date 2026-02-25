"""Tests for Knowledge Graph Integration"""

import pytest
import tempfile
import shutil
from pathlib import Path

from src.knowledge_graph import KnowledgeGraph, PatternLearner, QueryEngine


class TestKnowledgeGraph:
    """Test KnowledgeGraph class"""
    
    def setup_method(self):
        """Setup test database"""
        self.test_dir = tempfile.mkdtemp()
        self.db_path = Path(self.test_dir) / "test_graph.db"
        self.graph = KnowledgeGraph(str(self.db_path))
    
    def teardown_method(self):
        """Cleanup test database"""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_add_and_get_node(self):
        """Test adding and retrieving nodes"""
        print("\n=== Test 1: Add and Get Node ===")
        
        # Add a node
        node = self.graph.add_node(
            node_id="prob1",
            node_type="problem",
            data={"description": "Create Python CLI"},
            metadata={"complexity": "medium"}
        )
        
        assert node.node_id == "prob1"
        assert node.node_type == "problem"
        
        # Retrieve the node
        retrieved = self.graph.get_node("prob1")
        assert retrieved is not None
        assert retrieved.node_id == "prob1"
        assert retrieved.data["description"] == "Create Python CLI"
        
        print(f"✓ Added and retrieved node: {node.node_id}")
        print(f"  Type: {node.node_type}")
        print(f"  Data: {node.data}")
    
    def test_add_edges_and_find_related(self):
        """Test adding edges and finding related nodes"""
        print("\n=== Test 2: Edges and Related Nodes ===")
        
        # Add nodes
        self.graph.add_node("prob1", "problem", {"desc": "API error"})
        self.graph.add_node("sol1", "solution", {"desc": "Add error handling"})
        self.graph.add_node("sol2", "solution", {"desc": "Retry logic"})
        
        # Add edges
        self.graph.add_edge("e1", "prob1", "sol1", "solves", weight=0.9)
        self.graph.add_edge("e2", "prob1", "sol2", "solves", weight=0.7)
        
        # Find solutions for problem
        solutions = self.graph.find_related("prob1", relationship="solves")
        
        assert len(solutions) == 2
        assert all(s.node_type == "solution" for s in solutions)
        
        print(f"✓ Problem 'prob1' has {len(solutions)} solutions:")
        for sol in solutions:
            print(f"  - {sol.node_id}: {sol.data}")
    
    def test_record_and_get_patterns(self):
        """Test pattern recording and retrieval"""
        print("\n=== Test 3: Pattern Recording ===")
        
        # Record patterns
        self.graph.record_pattern(
            pattern_type="error",
            signature="error:import",
            data={"message": "Module not found"},
            success=False
        )
        
        self.graph.record_pattern(
            pattern_type="error",
            signature="error:import",
            data={"message": "Module not found"},
            success=False
        )
        
        self.graph.record_pattern(
            pattern_type="solution",
            signature=".py:3|.txt:1",
            data={"files": ["main.py", "utils.py", "test.py", "README.txt"]},
            success=True
        )
        
        # Get patterns
        error_patterns = self.graph.get_patterns(pattern_type="error")
        solution_patterns = self.graph.get_patterns(pattern_type="solution")
        
        assert len(error_patterns) == 1
        assert error_patterns[0]["occurrences"] == 2
        assert error_patterns[0]["success_rate"] == 0.0
        
        assert len(solution_patterns) == 1
        assert solution_patterns[0]["success_rate"] == 1.0
        
        print(f"✓ Error patterns: {len(error_patterns)}")
        for p in error_patterns:
            print(f"  - {p['signature']}: {p['occurrences']} times, {p['success_rate']*100:.0f}% success")
        
        print(f"✓ Solution patterns: {len(solution_patterns)}")
        for p in solution_patterns:
            print(f"  - {p['signature']}: {p['success_rate']*100:.0f}% success")
    
    def test_graph_stats(self):
        """Test graph statistics"""
        print("\n=== Test 4: Graph Statistics ===")
        
        # Add test data
        self.graph.add_node("n1", "problem", {})
        self.graph.add_node("n2", "solution", {})
        self.graph.add_node("n3", "error", {})
        self.graph.add_edge("e1", "n1", "n2", "solves")
        
        self.graph.record_pattern("error", "sig1", {}, False)
        self.graph.record_pattern("fix", "sig2", {}, True)
        
        # Get stats
        stats = self.graph.get_stats()
        
        assert stats["total_nodes"] == 3
        assert stats["total_edges"] == 1
        assert stats["total_patterns"] == 2
        
        print(f"✓ Graph statistics:")
        print(f"  - Total nodes: {stats['total_nodes']}")
        print(f"  - Nodes by type: {stats['nodes_by_type']}")
        print(f"  - Total edges: {stats['total_edges']}")
        print(f"  - Total patterns: {stats['total_patterns']}")
        print(f"  - Patterns by type: {stats['patterns_by_type']}")


class TestPatternLearner:
    """Test PatternLearner class"""
    
    def setup_method(self):
        """Setup test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.db_path = Path(self.test_dir) / "test_graph.db"
        self.graph = KnowledgeGraph(str(self.db_path))
        self.learner = PatternLearner(self.graph)
    
    def teardown_method(self):
        """Cleanup test environment"""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_learn_from_successful_run(self):
        """Test learning from successful run"""
        print("\n=== Test 5: Learn from Successful Run ===")
        
        run_data = {
            "idea": "Create a simple Python API",
            "files_generated": ["main.py", "models.py", "routes.py"],
            "errors": [],
            "fixes_applied": [],
            "model_used": "qwen2.5-coder:7b",
            "stages": ["research", "code_gen", "validation"],
            "duration": 45.2
        }
        
        self.learner.learn_from_run(run_data, success=True)
        
        # Check patterns were recorded
        problem_patterns = self.graph.get_patterns(pattern_type="problem")
        solution_patterns = self.graph.get_patterns(pattern_type="solution")
        technique_patterns = self.graph.get_patterns(pattern_type="technique")
        
        assert len(problem_patterns) > 0
        assert len(solution_patterns) > 0
        assert len(technique_patterns) > 0
        
        print(f"✓ Learned from successful run:")
        print(f"  - Problem patterns: {len(problem_patterns)}")
        print(f"  - Solution patterns: {len(solution_patterns)}")
        print(f"  - Technique patterns: {len(technique_patterns)}")
    
    def test_learn_from_failed_run(self):
        """Test learning from failed run"""
        print("\n=== Test 6: Learn from Failed Run ===")
        
        run_data = {
            "idea": "Create a complex ML pipeline",
            "files_generated": ["train.py"],
            "errors": [
                {
                    "type": "ImportError",
                    "message": "No module named 'tensorflow'",
                    "context": {"line": 5}
                }
            ],
            "fixes_applied": [
                {
                    "type": "add_import",
                    "description": "Install tensorflow",
                    "effectiveness": 0.8
                }
            ],
            "model_used": "llama2:7b",
            "stages": ["research", "code_gen"]
        }
        
        self.learner.learn_from_run(run_data, success=False)
        
        # Check patterns
        error_patterns = self.graph.get_patterns(pattern_type="error")
        fix_patterns = self.graph.get_patterns(pattern_type="fix")
        
        assert len(error_patterns) > 0
        assert len(fix_patterns) > 0
        
        print(f"✓ Learned from failed run:")
        print(f"  - Error patterns: {len(error_patterns)}")
        for e in error_patterns:
            print(f"    • {e['signature']}: {e['occurrences']} times")
        print(f"  - Fix patterns: {len(fix_patterns)}")
        for f in fix_patterns:
            print(f"    • {f['signature']}: {f['success_rate']*100:.0f}% effective")
    
    def test_find_similar_problems(self):
        """Test finding similar problems"""
        print("\n=== Test 7: Find Similar Problems ===")
        
        # Learn from multiple runs
        runs = [
            {
                "idea": "Create Python CLI tool",
                "files_generated": ["cli.py"],
                "errors": [],
                "fixes_applied": [],
                "model_used": "qwen2.5-coder:7b",
                "stages": ["code_gen"]
            },
            {
                "idea": "Build simple CLI application",
                "files_generated": ["main.py"],
                "errors": [],
                "fixes_applied": [],
                "model_used": "qwen2.5-coder:7b",
                "stages": ["code_gen"]
            },
            {
                "idea": "Create web API server",
                "files_generated": ["api.py"],
                "errors": [],
                "fixes_applied": [],
                "model_used": "deepseek-r1:8b",
                "stages": ["code_gen"]
            }
        ]
        
        for run in runs:
            self.learner.learn_from_run(run, success=True)
        
        # Find similar to CLI problem
        similar = self.learner.get_similar_problems("Build a CLI tool in Python")
        
        assert len(similar) > 0
        
        print(f"✓ Found {len(similar)} similar problems:")
        for s in similar[:3]:
            print(f"  - {s['signature']}")
            print(f"    Similarity: {s.get('similarity', 0)*100:.0f}%")
            print(f"    Success rate: {s['success_rate']*100:.0f}%")
    
    def test_get_solution_template(self):
        """Test getting solution templates"""
        print("\n=== Test 8: Get Solution Template ===")
        
        # Learn from successful runs with solutions
        for i in range(3):
            self.learner.learn_from_run({
                "idea": "Create Python API",
                "files_generated": ["main.py", "models.py", "routes.py"],
                "errors": [],
                "fixes_applied": [],
                "model_used": "qwen2.5-coder:7b",
                "stages": ["code_gen"]
            }, success=True)
        
        # Get template
        template = self.learner.get_solution_template("Build an API in Python")
        
        if template:
            print(f"✓ Got solution template:")
            print(f"  - Confidence: {template['confidence']*100:.0f}%")
            print(f"  - Template: {template['template']['signature']}")
            print(f"  - Occurrences: {template['template']['occurrences']}")
        else:
            print("✗ No template found (may need more data)")
    
    def test_generate_learning_report(self):
        """Test generating learning report"""
        print("\n=== Test 9: Generate Learning Report ===")
        
        # Learn from multiple runs
        for success in [True, True, False]:
            self.learner.learn_from_run({
                "idea": "Create Python tool",
                "files_generated": ["main.py"],
                "errors": [] if success else [{"type": "Error", "message": "Test error"}],
                "fixes_applied": [],
                "model_used": "qwen2.5-coder:7b",
                "stages": ["code_gen"]
            }, success=success)
        
        # Generate report
        report = self.learner.generate_report()
        
        assert "Pattern Learning Report" in report
        assert "Problem Patterns" in report
        
        print("✓ Generated learning report:")
        print(report)


class TestQueryEngine:
    """Test QueryEngine class"""
    
    def setup_method(self):
        """Setup test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.db_path = Path(self.test_dir) / "test_graph.db"
        self.graph = KnowledgeGraph(str(self.db_path))
        self.learner = PatternLearner(self.graph)
        self.query_engine = QueryEngine(self.graph, self.learner)
        
        # Add test data
        self._setup_test_data()
    
    def teardown_method(self):
        """Cleanup test environment"""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def _setup_test_data(self):
        """Setup test data for queries"""
        # Learn from sample runs
        runs = [
            {
                "idea": "Create Python CLI",
                "files_generated": ["cli.py", "utils.py"],
                "errors": [],
                "fixes_applied": [],
                "model_used": "qwen2.5-coder:7b",
                "stages": ["code_gen"]
            },
            {
                "idea": "Build web API",
                "files_generated": ["api.py"],
                "errors": [
                    {"type": "ImportError", "message": "Module not found"}
                ],
                "fixes_applied": [
                    {"type": "add_import", "description": "Install package"}
                ],
                "model_used": "deepseek-r1:8b",
                "stages": ["code_gen", "validation"]
            }
        ]
        
        self.learner.learn_from_run(runs[0], success=True)
        self.learner.learn_from_run(runs[1], success=False)
    
    def test_query_errors(self):
        """Test querying for errors"""
        print("\n=== Test 10: Query Errors ===")
        
        results = self.query_engine.query("What are common import errors?")
        
        assert results["type"] == "error_query"
        assert "patterns" in results
        
        print(f"✓ Query: {results['query']}")
        print(f"  Found {len(results['patterns'])} error patterns")
        if results["recommendations"]:
            print(f"  Recommendations: {len(results['recommendations'])}")
    
    def test_query_solutions(self):
        """Test querying for solutions"""
        print("\n=== Test 11: Query Solutions ===")
        
        results = self.query_engine.query("How to solve import errors?")
        
        assert results["type"] == "solution_query"
        
        print(f"✓ Query: {results['query']}")
        print(f"  Found {len(results.get('patterns', []))} solution patterns")
        print(f"  Recommendations: {len(results.get('recommendations', []))}")
    
    def test_query_recommendations(self):
        """Test querying for recommendations"""
        print("\n=== Test 12: Query Recommendations ===")
        
        results = self.query_engine.query("What's the best approach for Python CLI?")
        
        assert results["type"] == "recommendation_query"
        assert "recommendations" in results
        
        print(f"✓ Query: {results['query']}")
        print(f"  Generated {len(results['recommendations'])} recommendations:")
        for i, rec in enumerate(results["recommendations"], 1):
            print(f"    {i}. {rec['type']}: {rec.get('message', '')}")
    
    def test_query_stats(self):
        """Test querying for statistics"""
        print("\n=== Test 13: Query Stats ===")
        
        results = self.query_engine.query("Show statistics")
        
        assert results["type"] == "stats_query"
        assert "stats" in results
        
        print(f"✓ Query: {results['query']}")
        print(f"  Statistics:")
        for key, value in results["stats"].items():
            if isinstance(value, dict):
                print(f"    {key}:")
                for k, v in value.items():
                    print(f"      - {k}: {v}")
            else:
                print(f"    {key}: {value}")
    
    def test_get_learning_insights(self):
        """Test getting learning insights"""
        print("\n=== Test 14: Learning Insights ===")
        
        insights = self.query_engine.get_learning_insights()
        
        assert "total_patterns" in insights
        assert "best_practices" in insights
        
        print(f"✓ Learning insights:")
        print(f"  - Total patterns: {insights['total_patterns']}")
        print(f"  - Best practices: {len(insights['best_practices'])}")
        print(f"  - Common failures: {len(insights['common_failures'])}")
        print(f"  - Improvement areas: {len(insights['improvement_areas'])}")
    
    def test_export_knowledge_summary(self):
        """Test exporting knowledge summary"""
        print("\n=== Test 15: Export Knowledge Summary ===")
        
        summary = self.query_engine.export_knowledge_summary()
        
        assert "Knowledge Graph Summary" in summary
        assert "Statistics" in summary
        
        print("✓ Exported knowledge summary:")
        print(summary)


def run_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("KNOWLEDGE GRAPH INTEGRATION TESTS")
    print("="*60)
    
    # Test KnowledgeGraph
    kg_tests = TestKnowledgeGraph()
    kg_tests.setup_method()
    kg_tests.test_add_and_get_node()
    kg_tests.test_add_edges_and_find_related()
    kg_tests.test_record_and_get_patterns()
    kg_tests.test_graph_stats()
    kg_tests.teardown_method()
    
    # Test PatternLearner
    pl_tests = TestPatternLearner()
    pl_tests.setup_method()
    pl_tests.test_learn_from_successful_run()
    pl_tests.teardown_method()
    
    pl_tests.setup_method()
    pl_tests.test_learn_from_failed_run()
    pl_tests.teardown_method()
    
    pl_tests.setup_method()
    pl_tests.test_find_similar_problems()
    pl_tests.teardown_method()
    
    pl_tests.setup_method()
    pl_tests.test_get_solution_template()
    pl_tests.teardown_method()
    
    pl_tests.setup_method()
    pl_tests.test_generate_learning_report()
    pl_tests.teardown_method()
    
    # Test QueryEngine
    qe_tests = TestQueryEngine()
    qe_tests.setup_method()
    qe_tests.test_query_errors()
    qe_tests.test_query_solutions()
    qe_tests.test_query_recommendations()
    qe_tests.test_query_stats()
    qe_tests.test_get_learning_insights()
    qe_tests.test_export_knowledge_summary()
    qe_tests.teardown_method()
    
    print("\n" + "="*60)
    print("🎉 ALL KNOWLEDGE GRAPH TESTS PASSED!")
    print("="*60)


if __name__ == "__main__":
    run_tests()
