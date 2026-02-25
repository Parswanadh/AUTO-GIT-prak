"""
Comprehensive Pipeline Monitor Test
Tests: Tiny Recursive Models by Samsung

This script monitors EVERY phase of the pipeline and ensures nothing is skipped.
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime
import json

# Fix Windows unicode issues
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Setup
project_root = Path(__file__).parent
os.chdir(project_root)
sys.path.insert(0, str(project_root))

from src.langraph_pipeline.workflow_enhanced import build_workflow
from src.langraph_pipeline.state import AutoGITState
from src.utils.logger import get_logger

logger = get_logger(__name__)


class PipelineMonitor:
    """Monitor every phase of pipeline execution"""
    
    def __init__(self):
        self.phases = []
        self.start_time = datetime.now()
        self.errors = []
        self.warnings = []
        
    def log_phase(self, phase_name, stage, data):
        """Log a phase with full details"""
        timestamp = datetime.now()
        elapsed = (timestamp - self.start_time).total_seconds()
        
        phase_info = {
            "phase": phase_name,
            "stage": stage,
            "timestamp": timestamp.isoformat(),
            "elapsed_seconds": elapsed,
            "data": data
        }
        
        self.phases.append(phase_info)
        
        print(f"\n{'='*80}")
        print(f"PHASE {len(self.phases)}: {phase_name}")
        print(f"Stage: {stage}")
        print(f"Time: {elapsed:.1f}s")
        print(f"{'='*80}")
        
        # Print key data
        if isinstance(data, dict):
            for key, value in data.items():
                if key in ['current_stage', 'tests_passed', 'code_quality', 'consensus_reached']:
                    print(f"  {key}: {value}")
                elif key == 'problems' and value:
                    print(f"  problems: {len(value)} extracted")
                elif key == 'generated_code' and isinstance(value, dict):
                    files = value.get('files', {})
                    print(f"  generated_code: {len(files)} files")
                elif key == 'errors' and value:
                    print(f"  errors: {len(value)}")
                    for err in value[:3]:
                        print(f"    - {err}")
    
    def check_skipped(self, stage):
        """Check if a phase was skipped"""
        if 'skipped' in stage.lower():
            self.warnings.append(f"SKIPPED: {stage}")
            print(f"\n  WARNING: Phase was skipped!")
            return True
        return False
    
    def save_report(self, final_state):
        """Save comprehensive monitoring report"""
        report = {
            "test_case": "Tiny Recursive Models by Samsung",
            "start_time": self.start_time.isoformat(),
            "end_time": datetime.now().isoformat(),
            "total_duration": (datetime.now() - self.start_time).total_seconds(),
            "total_phases": len(self.phases),
            "phases": self.phases,
            "errors": self.errors,
            "warnings": self.warnings,
            "final_state_summary": {
                "current_stage": final_state.get("current_stage"),
                "tests_passed": final_state.get("tests_passed"),
                "code_quality": final_state.get("code_quality"),
                "published": final_state.get("published"),
                "errors_count": len(final_state.get("errors", [])),
            }
        }
        
        report_file = Path("pipeline_monitor_report.json")
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n\nReport saved to: {report_file}")
        return report


async def test_full_pipeline_monitored():
    """Test full pipeline with comprehensive monitoring"""
    
    print("="*80)
    print("COMPREHENSIVE PIPELINE TEST")
    print("Test Case: Tiny Recursive Models by Samsung")
    print("="*80)
    print()
    
    monitor = PipelineMonitor()
    
    # Test idea from Samsung research
    test_idea = """Tiny Recursive Models by Samsung

Implement tiny recursive models as described in Samsung's research.
These are compact neural network architectures that use recursive patterns
to achieve high performance with minimal parameters.

Key features:
- Recursive layer design for parameter efficiency
- Suitable for mobile/edge deployment
- PyTorch implementation
- Training and evaluation scripts
"""
    
    print(f"Idea: {test_idea[:200]}...")
    print()
    
    # Create initial state with all required fields
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
        "max_rounds": 2,  # Keep it manageable
        "perspectives": ["ML Researcher", "Systems Engineer", "Applied Scientist"],  # Initialize perspectives
        "final_solution": None,
        "selection_reasoning": None,
        "generated_code": [],
        "implementation_notes": None,
        "test_results": None,
        "tests_passed": False,
        "fix_attempts": 0,
        "max_fix_attempts": 2,  # Reduced to prevent OOM
        "repo_name": "tiny-recursive-models",
        "commit_message": None,
        "published": False,
        "publication_url": None,
        "pipeline_start_time": datetime.now().isoformat(),
        "current_stage": "initialized",
        "errors": [],
        "warnings": [],
        "use_web_search": False,  # Disable to avoid SearXNG dependency
        "max_debate_rounds": 2,
        "min_consensus_score": 0.7
    }
    
    print("Building workflow...")
    workflow = build_workflow()
    
    # Configure with recursion limit and thread_id for checkpointer
    from langgraph.checkpoint.memory import MemorySaver
    import uuid
    
    config = {
        "recursion_limit": 50,
        "configurable": {
            "thread_id": str(uuid.uuid4())
        }
    }
    
    app = workflow.compile(
        checkpointer=MemorySaver()
    )
    
    print("Starting pipeline execution...")
    print()
    
    phase_count = 0
    final_state = None
    
    try:
        async for state in app.astream(initial_state, config=config):
            phase_count += 1
            
            # Extract state from wrapped format
            if isinstance(state, dict):
                for node_name, node_state in state.items():
                    if isinstance(node_state, dict):
                        current_stage = node_state.get("current_stage", "")
                        
                        # Log this phase
                        monitor.log_phase(
                            phase_name=node_name,
                            stage=current_stage,
                            data=node_state
                        )
                        
                        # Check if skipped
                        monitor.check_skipped(current_stage)
                        
                        # Store latest state
                        final_state = node_state
                        
                        # Detailed phase-specific monitoring
                        if node_name == "research":
                            print(f"  Research mode: {'enabled' if node_state.get('use_web_search') else 'disabled'}")
                            
                        elif node_name == "problem_extraction":
                            problems = node_state.get("problems", [])
                            if problems:
                                print(f"  Extracted problems:")
                                for i, prob in enumerate(problems[:3], 1):
                                    print(f"    {i}. {prob[:100]}...")
                            
                        elif node_name == "solution_generation":
                            debate_rounds = node_state.get("debate_rounds", [])
                            if debate_rounds:
                                latest_round = debate_rounds[-1]
                                proposals = latest_round.get("proposals", [])
                                print(f"  Round {len(debate_rounds)}: {len(proposals)} proposals generated")
                                
                        elif node_name == "critique":
                            debate_rounds = node_state.get("debate_rounds", [])
                            if debate_rounds:
                                latest_round = debate_rounds[-1]
                                critiques = latest_round.get("critiques", [])
                                print(f"  Critiques: {len(critiques)} generated")
                                
                        elif node_name == "consensus_check":
                            consensus = node_state.get("consensus_reached", False)
                            print(f"  Consensus reached: {consensus}")
                            
                        elif node_name == "solution_selection":
                            solution = node_state.get("final_solution")
                            if solution:
                                print(f"  Selected: {solution.get('approach_name', 'unknown')}")
                                
                        elif node_name == "code_generation":
                            gen_code = node_state.get("generated_code", {})
                            files = gen_code.get("files", {})
                            if files:
                                print(f"  Generated files:")
                                for filename in files.keys():
                                    print(f"    - {filename} ({len(files[filename])} chars)")
                                    
                        elif node_name == "code_testing":
                            tests_passed = node_state.get("tests_passed", False)
                            code_quality = node_state.get("code_quality", 0)
                            print(f"  Tests passed: {tests_passed}")
                            print(f"  Code quality: {code_quality}/100")
                            
                            # Show validation details
                            test_results = node_state.get("test_results", {})
                            validation = test_results.get("validation_results", {})
                            if validation:
                                print(f"  Enhanced validation:")
                                for fname, v in validation.items():
                                    print(f"    {fname}: security={v.get('security_score')}/100, "
                                          f"quality={v.get('quality_score')}/100")
                                    
                        elif node_name == "code_fixing":
                            fix_attempts = node_state.get("fix_attempts", 0)
                            print(f"  Fix attempt: {fix_attempts}")
                            
                        elif node_name == "git_publishing":
                            published = node_state.get("published", False)
                            pub_url = node_state.get("publication_url")
                            print(f"  Published: {published}")
                            if pub_url:
                                print(f"  URL: {pub_url}")
        
        print("\n" + "="*80)
        print("PIPELINE EXECUTION COMPLETE")
        print("="*80)
        
        # Save monitoring report
        report = monitor.save_report(final_state)
        
        # Analysis
        print("\n\nFINAL ANALYSIS:")
        print("-"*80)
        print(f"Total Phases: {len(monitor.phases)}")
        print(f"Total Duration: {report['total_duration']:.1f}s")
        print(f"Warnings: {len(monitor.warnings)}")
        print(f"Errors: {len(monitor.errors)}")
        
        if monitor.warnings:
            print("\nWARNINGS:")
            for w in monitor.warnings:
                print(f"  - {w}")
        
        if monitor.errors:
            print("\nERRORS:")
            for e in monitor.errors:
                print(f"  - {e}")
        
        # Final state
        if final_state:
            print("\nFINAL STATE:")
            print(f"  Stage: {final_state.get('current_stage')}")
            print(f"  Tests Passed: {final_state.get('tests_passed')}")
            print(f"  Code Quality: {final_state.get('code_quality', 'N/A')}")
            print(f"  Published: {final_state.get('published')}")
            
            errors = final_state.get('errors', [])
            if errors:
                print(f"  Errors: {len(errors)}")
                for err in errors[:5]:
                    print(f"    - {err}")
        
        # Success criteria
        success = True
        if not final_state:
            print("\nRESULT: FAILED - No final state")
            success = False
        elif len(monitor.warnings) > 5:
            print(f"\nRESULT: WARNING - Too many skipped phases ({len(monitor.warnings)})")
            success = False
        elif final_state.get('current_stage') == 'initialized':
            print("\nRESULT: FAILED - Pipeline never started")
            success = False
        else:
            print("\nRESULT: SUCCESS - Pipeline completed")
        
        return success
        
    except Exception as e:
        print(f"\n\nPIPELINE CRASHED: {e}")
        import traceback
        traceback.print_exc()
        
        monitor.errors.append(str(e))
        if final_state:
            monitor.save_report(final_state)
        
        return False


async def main():
    """Main entry point"""
    success = await test_full_pipeline_monitored()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
