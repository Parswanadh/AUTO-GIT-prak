"""
Automated Test Generation System
Generates comprehensive test suites for generated code using LLM assistance.
"""

import ast
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from src.llm.hybrid_router import HybridRouter
from src.llm.multi_backend_manager import MultiBackendLLMManager

logger = logging.getLogger(__name__)


@dataclass
class TestSuite:
    """Generated test suite"""
    unit_tests: str
    edge_case_tests: str
    integration_tests: str
    full_suite: str
    function_count: int
    test_count: int


class TestGenerator:
    """
    Generate comprehensive test suites for code.
    
    Uses LLM to create:
    - Unit tests for each function
    - Edge case tests
    - Integration tests
    - pytest-compatible format
    """
    
    def __init__(self, router: Optional[HybridRouter] = None):
        """
        Initialize test generator.
        
        Args:
            router: HybridRouter instance (creates if None)
        """
        if router is None:
            backend_manager = MultiBackendLLMManager()
            self.router = HybridRouter(backend_manager, use_cache=True)
        else:
            self.router = router
        
        logger.info("TestGenerator initialized")
    
    async def generate_tests(
        self,
        code: str,
        specification: str
    ) -> TestSuite:
        """
        Generate comprehensive test suite.
        
        Args:
            code: Implementation code to test
            specification: Original specification/requirements
        
        Returns:
            TestSuite with all generated tests
        """
        logger.info("Generating test suite...")
        
        # Extract functions and classes from code
        functions = self._extract_functions(code)
        classes = self._extract_classes(code)
        
        logger.info(f"Found {len(functions)} functions and {len(classes)} classes")
        
        # Generate different types of tests
        unit_tests = await self._generate_unit_tests(functions, code)
        edge_case_tests = await self._generate_edge_case_tests(specification, code)
        integration_tests = await self._generate_integration_tests(specification, code)
        
        # Combine into full test suite
        full_suite = self._build_test_suite(
            unit_tests,
            edge_case_tests,
            integration_tests,
            functions,
            classes
        )
        
        # Count tests
        test_count = full_suite.count("def test_")
        
        return TestSuite(
            unit_tests=unit_tests,
            edge_case_tests=edge_case_tests,
            integration_tests=integration_tests,
            full_suite=full_suite,
            function_count=len(functions),
            test_count=test_count
        )
    
    def _extract_functions(self, code: str) -> List[str]:
        """Extract function names from code using AST"""
        try:
            tree = ast.parse(code)
            functions = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Skip private functions and __init__
                    if not node.name.startswith('_') or node.name == '__init__':
                        functions.append(node.name)
            
            return functions
        except SyntaxError as e:
            logger.warning(f"Failed to parse code: {e}")
            return []
    
    def _extract_classes(self, code: str) -> List[str]:
        """Extract class names from code using AST"""
        try:
            tree = ast.parse(code)
            classes = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    classes.append(node.name)
            
            return classes
        except SyntaxError as e:
            logger.warning(f"Failed to parse code: {e}")
            return []
    
    async def _generate_unit_tests(
        self,
        functions: List[str],
        code: str
    ) -> str:
        """Generate unit tests for each function"""
        
        if not functions:
            return "# No functions to test"
        
        prompt = f"""Generate pytest tests for these Python functions:

{code}

Functions: {', '.join(functions)}

Create simple unit tests that test basic functionality. Use pytest. Return only code."""

        result = await self.router.generate_with_fallback(
            task_type="code_generation",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1500,
            timeout=90.0  # Longer timeout
        )
        
        return result.content or result.reasoning or "# Test generation failed"
    
    async def _generate_edge_case_tests(
        self,
        specification: str,
        code: str
    ) -> str:
        """Generate edge case and boundary tests"""
        
        prompt = f"""Generate pytest edge case tests:

{code}

Test edge cases: empty inputs, None, boundaries, invalid types. Use pytest. Return only code."""

        result = await self.router.generate_with_fallback(
            task_type="code_generation",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1000,
            timeout=90.0
        )
        
        return result.content or result.reasoning or "# Edge case test generation failed"
    
    async def _generate_integration_tests(
        self,
        specification: str,
        code: str
    ) -> str:
        """Generate integration/end-to-end tests"""
        
        prompt = f"""Generate pytest integration tests:

{code}

Test complete workflows. Use pytest. Return only code."""

        result = await self.router.generate_with_fallback(
            task_type="code_generation",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1000,
            timeout=90.0
        )
        
        return result.content or result.reasoning or "# Integration test generation failed"
    
    def _build_test_suite(
        self,
        unit_tests: str,
        edge_case_tests: str,
        integration_tests: str,
        functions: List[str],
        classes: List[str]
    ) -> str:
        """Combine all tests into one comprehensive suite"""
        
        # Extract imports from each test section
        imports = set()
        imports.add("import pytest")
        imports.add("from typing import Any")
        
        # Clean up test code (remove duplicate imports)
        unit_tests_clean = self._remove_imports(unit_tests)
        edge_tests_clean = self._remove_imports(edge_case_tests)
        integration_tests_clean = self._remove_imports(integration_tests)
        
        test_suite = f'''"""
Auto-generated Test Suite
Generated for: {", ".join(functions[:3])}{"..." if len(functions) > 3 else ""}

Test Coverage:
- Unit tests: {unit_tests_clean.count("def test_")} tests
- Edge case tests: {edge_tests_clean.count("def test_")} tests  
- Integration tests: {integration_tests_clean.count("def test_")} tests

Functions tested: {len(functions)}
Classes tested: {len(classes)}
"""

import pytest
from typing import Any

# Import the code to test
# Adjust this import based on your module structure
# from implementation import *


# ============================================
# UNIT TESTS
# ============================================

{unit_tests_clean}


# ============================================
# EDGE CASE TESTS
# ============================================

{edge_tests_clean}


# ============================================
# INTEGRATION TESTS
# ============================================

{integration_tests_clean}


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "--tb=short"])
'''
        
        return test_suite
    
    def _remove_imports(self, code: str) -> str:
        """Remove import statements from code block"""
        lines = code.split('\n')
        cleaned_lines = []
        
        for line in lines:
            stripped = line.strip()
            # Skip import lines
            if stripped.startswith('import ') or stripped.startswith('from '):
                continue
            # Skip markdown code fences
            if stripped.startswith('```'):
                continue
            cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)


# Singleton instance
_generator_instance: Optional[TestGenerator] = None


def get_test_generator() -> TestGenerator:
    """Get or create global test generator instance"""
    global _generator_instance
    
    if _generator_instance is None:
        _generator_instance = TestGenerator()
    
    return _generator_instance
