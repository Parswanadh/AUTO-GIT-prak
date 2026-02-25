"""
Simple pipeline test with enhanced validation

Tests the entire Auto-GIT pipeline with a simple calculator project.
This will verify that the enhanced validation works end-to-end.
"""

import asyncio
import sys
import os
from pathlib import Path

# Setup path properly
project_root = Path(__file__).parent
os.chdir(project_root)
sys.path.insert(0, str(project_root))

# Import using absolute paths from project root
from src.langraph_pipeline.workflow_enhanced import build_workflow
from src.langraph_pipeline.state import AutoGITState
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_simple_pipeline():
    """Test pipeline with a simple calculator project"""
    
    print("=" * 70)
    print("🧪 TESTING FULL PIPELINE WITH ENHANCED VALIDATION")
    print("=" * 70)
    print()
    
    # Simple test case - calculator
    test_idea = """
Create a simple command-line calculator in Python.

Requirements:
- Support basic operations: add, subtract, multiply, divide
- Handle invalid input gracefully
- Use type hints for all functions
- Include proper error handling
- Command-line interface
"""
    
    print(f"📋 Test Idea: Simple Calculator")
    print(f"📦 Type: Command-line tool")
    print()
    
    # Create initial state
    initial_state = {
        "idea": test_idea,
        "user_requirements": None,
        "requirements": None,
        "research_context": None,
        "related_work_summary": None,
        "research_report": None,
        "research_summary": None,
        "problems": [],
        "selected_problem": None,
        "debate_rounds": [],
        "current_round": 0,
        "max_rounds": 2,  # Keep it short for testing
        "perspectives": [],
        "final_solution": None,
        "selection_reasoning": None,
        "generated_code": [],
        "implementation_notes": None,
        "test_results": None,
        "tests_passed": False,
        "fix_attempts": 0,
        "max_fix_attempts": 2,
        "repo_name": "simple-calculator",
        "commit_message": None,
        "published": False,
        "publication_url": None,
        "pipeline_start_time": "",
        "current_stage": "initialized",
        "errors": [],
        "warnings": [],
        "use_web_search": False,  # Skip web search for faster testing
        "max_debate_rounds": 2,
        "min_consensus_score": 0.7
    }
    
    print("🔧 Creating workflow...")
    workflow = build_workflow()
    app = workflow.compile()
    
    print("🚀 Running pipeline...")
    print("-" * 70)
    print()
    
    try:
        # Run the workflow
        final_state = None
        async for state in app.astream(initial_state):
            # Get the last state
            if state:
                final_state = state
                
                # Extract the state dict (it might be wrapped)
                if isinstance(state, dict):
                    for key, value in state.items():
                        if isinstance(value, dict):
                            current_stage = value.get("current_stage", "")
                            if current_stage:
                                print(f"📍 Stage: {current_stage}")
                                
                                # Show validation results if available
                                if current_stage == "testing_complete":
                                    test_results = value.get("test_results", {})
                                    validation_results = test_results.get("validation_results", {})
                                    
                                    if validation_results:
                                        print()
                                        print("🔍 ENHANCED VALIDATION RESULTS:")
                                        print("-" * 70)
                                        
                                        for filename, validation in validation_results.items():
                                            print(f"\n  📄 {filename}:")
                                            print(f"    ✅ Passed: {validation.get('passed', False)}")
                                            print(f"    📝 Syntax: {'✅' if validation.get('syntax_valid') else '❌'}")
                                            print(f"    🔍 Type Safe: {'✅' if validation.get('type_safe') else '⚠️'}")
                                            print(f"    🔒 Security: {validation.get('security_score', 0)}/100")
                                            print(f"    ✨ Lint: {validation.get('lint_score', 0)}/100")
                                            print(f"    🎯 Quality: {validation.get('quality_score', 0)}/100")
                                            
                                            # Show issues
                                            errors = validation.get('errors', [])
                                            if errors:
                                                print(f"    ❌ Errors: {len(errors)}")
                                                for err in errors[:3]:
                                                    print(f"      - {err}")
                                            
                                            warnings = validation.get('warnings', [])
                                            if warnings:
                                                print(f"    ⚠️  Warnings: {len(warnings)}")
                                                for warn in warnings[:3]:
                                                    print(f"      - {warn}")
                                        
                                        avg_quality = test_results.get("average_quality", 0)
                                        print(f"\n  📊 Average Quality: {avg_quality:.1f}/100")
                                        print(f"  {'✅ PASSED' if avg_quality >= 50 else '❌ FAILED'} (threshold: 50/100)")
                                        print()
        
        if final_state:
            # Extract final state
            if isinstance(final_state, dict):
                for value in final_state.values():
                    if isinstance(value, dict):
                        final_state = value
                        break
            
            print()
            print("=" * 70)
            print("📊 FINAL RESULTS")
            print("=" * 70)
            
            current_stage = final_state.get("current_stage", "unknown")
            tests_passed = final_state.get("tests_passed", False)
            code_quality = final_state.get("code_quality", 0)
            
            print(f"  Final Stage: {current_stage}")
            print(f"  Tests Passed: {'✅ Yes' if tests_passed else '❌ No'}")
            print(f"  Code Quality: {code_quality:.1f}/100")
            
            # Show generated files
            generated_code = final_state.get("generated_code", {})
            files = generated_code.get("files", {})
            if files:
                print(f"  Generated Files: {len(files)}")
                for filename in files.keys():
                    print(f"    - {filename}")
            
            errors = final_state.get("errors", [])
            if errors:
                print(f"  Errors: {len(errors)}")
                for err in errors[:5]:
                    print(f"    - {err}")
            
            print()
            
            if tests_passed and code_quality >= 50:
                print("✅ PIPELINE TEST SUCCESSFUL!")
                print(f"✅ Enhanced validation working correctly")
                print(f"✅ Quality threshold enforced (≥50/100)")
                return True
            else:
                print("⚠️  PIPELINE TEST COMPLETED WITH ISSUES")
                if not tests_passed:
                    print("  - Tests did not pass")
                if code_quality < 50:
                    print(f"  - Quality too low: {code_quality:.1f}/100")
                return False
        else:
            print("❌ No final state received")
            return False
            
    except Exception as e:
        print()
        print("=" * 70)
        print("❌ PIPELINE TEST FAILED")
        print("=" * 70)
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main entry point"""
    success = await test_simple_pipeline()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
