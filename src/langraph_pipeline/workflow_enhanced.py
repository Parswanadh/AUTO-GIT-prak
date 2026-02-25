"""
Enhanced LangGraph Workflow with Progress Monitoring

Adds Rich progress bars, live updates, and inter-stage output display.
"""

import os
import sys
import logging
import asyncio
from typing import Literal, Optional, Dict, Any

# Fix Windows cp1252 codec crashing on emoji in Rich console output
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from ..utils.model_manager import print_token_summary
from ..utils.pipeline_tracer import PipelineTracer
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich import box

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver


class _AsyncSqliteSaver(SqliteSaver):
    """SqliteSaver subclass that satisfies LangGraph's async astream() interface
    by delegating every async method to its synchronous counterpart.
    All state reads/writes are lightweight dict operations, so running them on
    the event-loop thread is fine for this single-threaded async pipeline."""

    async def aget_tuple(self, config):
        return self.get_tuple(config)

    async def alist(self, config, *, filter=None, before=None, limit=None):
        for item in self.list(config, filter=filter, before=before, limit=limit):
            yield item

    async def aput(self, config, checkpoint, metadata, new_versions):
        return self.put(config, checkpoint, metadata, new_versions)

    async def aput_writes(self, config, writes, task_id):
        return self.put_writes(config, writes, task_id)

from .state import AutoGITState, create_initial_state
from .nodes import (
    research_node,
    generate_perspectives_node,
    problem_extraction_node,
    solution_generation_node,
    critique_node,
    consensus_check_node,
    solution_selection_node,
    architect_spec_node,
    code_generation_node,
    code_review_agent_node,
    code_testing_node,
    strategy_reasoner_node,
    code_fixing_node,
    pipeline_self_eval_node,
    git_publishing_node
)

logger = logging.getLogger(__name__)
console = Console()


def display_research_results(state: AutoGITState):
    """Display research results in a formatted panel"""
    # Get research context
    research_context = state.get("research_context", {})
    papers = research_context.get("papers", []) if research_context else []
    web_results = research_context.get("web_results", []) if research_context else []
    implementations = research_context.get("implementations", []) if research_context else []
    
    table = Table(title="📚 Research Results", box=box.ROUNDED, border_style="cyan")
    table.add_column("Type", style="cyan")
    table.add_column("Count", style="green")
    table.add_column("Details", style="white")
    
    # Display paper info
    if papers:
        first_paper = str(papers[0].get('title', 'N/A'))[:50]
        table.add_row("arXiv Papers", str(len(papers)), f"{first_paper}...")
    else:
        table.add_row("arXiv Papers", "0", "None found")
    
    # Display web results
    if web_results:
        first_result = str(web_results[0].get('title', 'N/A'))[:50]
        table.add_row("Web Results", str(len(web_results)), f"{first_result}...")
    else:
        table.add_row("Web Results", "0", "None found")
    
    # Display implementations
    if implementations:
        table.add_row("Implementations", str(len(implementations)), f"{len(implementations)} found on GitHub")
    else:
        table.add_row("Implementations", "0", "None found")
    
    console.print("\n")
    console.print(table)
    console.print("\n")


def display_problems(state: AutoGITState):
    """Display extracted problems"""
    problems = state.get("problems", [])
    selected = state.get("selected_problem")
    
    console.print("\n")
    console.print(Panel(
        f"[bold cyan]🎯 Extracted {len(problems)} Research Problems[/bold cyan]",
        border_style="cyan"
    ))
    
    for i, problem in enumerate(problems[:3], 1):
        if isinstance(problem, dict):
            console.print(f"\n{i}. [yellow]{problem.get('title', 'Problem ' + str(i))}[/yellow]")
            console.print(f"   [dim]{str(problem.get('description', 'N/A'))[:100]}...[/dim]")
        else:
            # Problem is a string
            console.print(f"\n{i}. [yellow]{str(problem)[:100]}...[/yellow]")
    
    if selected:
        if isinstance(selected, dict):
            console.print(f"\n[bold green]✓ Selected:[/bold green] {selected.get('title', 'Problem 1')}")
        else:
            console.print(f"\n[bold green]✓ Selected:[/bold green] {str(selected)[:50]}...")
    console.print("\n")


def display_debate_round(state: AutoGITState):
    """Display debate round results"""
    rounds = state.get("debate_rounds", [])
    if not rounds:
        return
    
    current_round = rounds[-1]
    proposals = current_round.get("proposals", [])
    critiques = current_round.get("critiques", [])
    
    console.print("\n")
    console.print(Panel(
        f"[bold magenta]💡 Round {current_round.get('round_number', '?')} - {len(proposals)} Proposals, {len(critiques)} Critiques[/bold magenta]",
        border_style="magenta"
    ))
    
    # Show proposals
    for i, proposal in enumerate(proposals, 1):
        console.print(f"\n{i}. [cyan]{proposal.get('approach_name', 'Unnamed')}[/cyan]")
        console.print(f"   [green]Perspective:[/green] {proposal.get('perspective', 'N/A')}")
        console.print(f"   [dim]{str(proposal.get('key_innovation', 'N/A'))[:80]}...[/dim]")
        console.print(f"   [yellow]Novelty: {proposal.get('novelty_score', 0):.2f}[/yellow] | [blue]Feasibility: {proposal.get('feasibility_score', 0):.2f}[/blue]")
    
    console.print("\n")


def display_final_solution(state: AutoGITState):
    """Display the selected final solution"""
    solution = state.get("final_solution")
    if not solution:
        return
    
    console.print("\n")
    console.print(Panel(
        f"[bold green]🏆 SELECTED SOLUTION[/bold green]\n\n"
        f"[cyan]{solution.get('approach_name', 'N/A')}[/cyan]\n\n"
        f"[white]{solution.get('key_innovation', 'N/A')}[/white]\n\n"
        f"[dim]Architecture: {str(solution.get('architecture_design', 'N/A'))[:100]}...[/dim]",
        border_style="bright_green",
        box=box.DOUBLE
    ))
    console.print("\n")


def display_generated_code(state: AutoGITState):
    """Display generated code summary"""
    generated = state.get("generated_code", {})
    if not generated:
        return
    
    files = generated.get("files", {})
    
    console.print("\n")
    console.print(Panel(
        f"[bold cyan]💻 Generated Code[/bold cyan]",
        border_style="cyan"
    ))
    
    for filename, content in files.items():
        lines = len(content.split('\n')) if isinstance(content, str) else 0
        console.print(f"  [green]✓[/green] {filename} [dim]({lines} lines)[/dim]")
    
    console.print("\n")


def display_github_result(state: AutoGITState):
    """Display GitHub publishing result"""
    github_url = state.get("github_url")
    repo_name = state.get("repo_name")
    
    if github_url:
        console.print("\n")
        console.print(Panel(
            f"[bold green]🚀 Published to GitHub![/bold green]\n\n"
            f"[cyan]Repository:[/cyan] {repo_name}\n"
            f"[cyan]URL:[/cyan] [link={github_url}]{github_url}[/link]",
            border_style="bright_green",
            box=box.DOUBLE
        ))
        console.print("\n")


def display_test_results(state: AutoGITState):
    """Display code testing results"""
    test_results = state.get("test_results")
    tests_passed = state.get("tests_passed", False)
    
    if not test_results:
        return
    
    console.print("\n")
    
    # Create status table
    table = Table(title="🧪 Code Testing Results", box=box.ROUNDED, show_header=True)
    table.add_column("Test", style="cyan", width=30)
    table.add_column("Status", width=15)
    table.add_column("Details", style="dim", width=50)
    
    # Environment creation
    env_status = "✅ Pass" if test_results.get("environment_created") else "❌ Fail"
    table.add_row("Environment Creation", env_status, "Virtual environment setup")
    
    # Dependencies installation
    deps_status = "✅ Pass" if test_results.get("dependencies_installed") else "❌ Fail"
    table.add_row("Dependencies", deps_status, "Package installation")
    
    # Syntax validation
    syntax_status = "✅ Pass" if test_results.get("syntax_valid") else "❌ Fail"
    table.add_row("Syntax Check", syntax_status, "Python syntax validation")
    
    # Import testing
    import_status = "✅ Pass" if test_results.get("import_successful") else "❌ Fail"
    table.add_row("Import Test", import_status, "Module import validation")
    
    console.print(table)
    
    # Display errors if any
    errors = test_results.get("execution_errors", [])
    if errors:
        console.print("\n[bold red]⚠️ Errors Detected:[/bold red]")
        for error in errors[:5]:  # Limit to 5 errors
            console.print(f"  [red]•[/red] [dim]{error}[/dim]")
    
    # Display warnings if any
    warnings = test_results.get("warnings", [])
    if warnings:
        console.print("\n[bold yellow]⚠️ Warnings:[/bold yellow]")
        for warning in warnings[:3]:  # Limit to 3 warnings
            console.print(f"  [yellow]•[/yellow] [dim]{warning}[/dim]")
    
    # Overall status
    if tests_passed:
        console.print("\n[bold green]✅ All tests passed! Code is ready for publishing.[/bold green]")
    else:
        console.print("\n[bold red]❌ Tests failed! Auto-fixing will be attempted.[/bold red]")
        console.print("[yellow]Review errors above. You can choose to stop, continue fixing, or publish anyway.[/yellow]")
    
    console.print("\n")
    
    # Return whether user wants to continue
    return tests_passed


def should_continue_debate(state: AutoGITState) -> Literal["continue", "select"]:
    """Routing function: Decide whether to continue debate or select solution"""
    current_stage = state.get("current_stage", "")

    # Always proceed to selection on terminal/success stages
    if current_stage in ("consensus_reached", "max_rounds_reached"):
        return "select"

    # Proceed to selection on failure stages – prevents infinite retry loop
    if current_stage in (
        "solution_generation_failed",
        "critique_failed",
        "no_debate_rounds",
    ):
        logger.warning(f"Debate stage failed ({current_stage}), proceeding to solution selection")
        return "select"

    # If no proposals were generated at all, don't loop forever
    debate_rounds = state.get("debate_rounds") or []
    if not debate_rounds:
        return "select"
    last_round = debate_rounds[-1] if debate_rounds else {}
    if not last_round.get("proposals"):
        return "select"

    # Still in debate – keep going
    return "continue"


def should_regen_or_publish(state: AutoGITState) -> Literal["fix", "publish"]:
    """Routing from pipeline_self_eval: low score → code_fixing, approved → git_publishing"""
    stage = state.get("current_stage", "")
    fix_attempts = state.get("fix_attempts", 0)
    max_attempts = state.get("max_fix_attempts", 3)
    if stage == "self_eval_needs_regen":
        # Don't send back for more fixing if we've already exhausted attempts
        if fix_attempts >= max_attempts:
            logger.warning(f"   self_eval wants regen but fix_attempts={fix_attempts} >= max={max_attempts} — publishing anyway")
            return "publish"
        return "fix"
    return "publish"


def should_fix_code(state: AutoGITState) -> Literal["fix", "publish"]:
    """Routing function: Decide whether to fix code or proceed to publishing"""
    tests_passed = state.get("tests_passed", True)
    fix_attempts = state.get("fix_attempts", 0)
    max_attempts = state.get("max_fix_attempts", 3)  # Reduced from 6 to prevent OOM
    current_stage = state.get("current_stage", "")
    
    # CRITICAL: If no files were generated, skip fixing entirely
    generated_code = state.get("generated_code", {})
    files = generated_code.get("files", {})
    if not files or current_stage == "code_generation_skipped":
        logger.info("   No code to fix, routing to publish")
        return "publish"
    
    # If tests passed, go to self-eval/publishing
    if tests_passed:
        return "publish"
    
    # If testing was skipped (no errors to fix), go to self-eval/publish
    if current_stage in ["testing_skipped", "no_errors_to_fix", "fixing_failed", "fixing_error"]:
        logger.info(f"   Stage {current_stage}, routing to publish")
        return "publish"

    # HARD CAP: never exceed max attempts regardless of reason
    if fix_attempts >= max_attempts:
        logger.warning(f"   Max fix attempts reached ({fix_attempts}/{max_attempts}) — giving up")
        return "publish"
    
    # Still have budget — try to fix
    logger.info(f"   Fix attempt {fix_attempts + 1}/{max_attempts}")
    return "fix"


def build_workflow() -> StateGraph:
    """Build the LangGraph StateGraph workflow with all nodes"""
    workflow = StateGraph(AutoGITState)
    
    # Add nodes
    workflow.add_node("research", research_node)
    workflow.add_node("generate_perspectives", generate_perspectives_node)
    workflow.add_node("problem_extraction", problem_extraction_node)
    workflow.add_node("solution_generation", solution_generation_node)
    workflow.add_node("critique", critique_node)
    workflow.add_node("consensus_check", consensus_check_node)
    workflow.add_node("solution_selection", solution_selection_node)
    workflow.add_node("architect_spec", architect_spec_node)
    workflow.add_node("code_generation", code_generation_node)
    workflow.add_node("code_review_agent", code_review_agent_node)
    workflow.add_node("code_testing", code_testing_node)
    workflow.add_node("strategy_reasoner", strategy_reasoner_node)
    workflow.add_node("code_fixing", code_fixing_node)
    workflow.add_node("pipeline_self_eval", pipeline_self_eval_node)
    workflow.add_node("git_publishing", git_publishing_node)
    
    # Define the flow
    workflow.set_entry_point("research")
    workflow.add_edge("research", "generate_perspectives")
    workflow.add_edge("generate_perspectives", "problem_extraction")
    workflow.add_edge("problem_extraction", "solution_generation")
    workflow.add_edge("solution_generation", "critique")
    workflow.add_edge("critique", "consensus_check")
    
    # Conditional routing from consensus_check
    workflow.add_conditional_edges(
        "consensus_check",
        should_continue_debate,
        {
            "continue": "solution_generation",
            "select": "solution_selection"
        }
    )
    
    # Final flow with self-healing loop
    workflow.add_edge("solution_selection", "architect_spec")
    workflow.add_edge("architect_spec", "code_generation")
    workflow.add_edge("code_generation", "code_review_agent")
    workflow.add_edge("code_review_agent", "code_testing")
    
    # Conditional: if tests fail, reason about WHY then fix; if pass, go to self-eval
    workflow.add_conditional_edges(
        "code_testing",
        should_fix_code,
        {
            "fix": "strategy_reasoner",    # reason first, then fix
            "publish": "pipeline_self_eval"   # renamed from git_publishing — eval first
        }
    )

    # Strategy reasoner always flows into code_fixing
    workflow.add_edge("strategy_reasoner", "code_fixing")

    # After fixing: route through code_review_agent for a quick sanity check,
    # or skip to eval if nothing to fix
    def _after_fixing(state: AutoGITState) -> Literal["review", "eval"]:
        stage = state.get("current_stage", "")
        if stage in ("no_errors_to_fix", "fixing_failed", "fixing_error"):
            logger.info(f"   code_fixing returned '{stage}' — skipping review, going to self-eval")
            return "eval"
        return "review"

    workflow.add_conditional_edges(
        "code_fixing",
        _after_fixing,
        {
            "review": "code_review_agent",   # review fixes before retesting
            "eval": "pipeline_self_eval",
        }
    )

    # Self-eval: approved → publish; needs_work → reason + fix again
    workflow.add_conditional_edges(
        "pipeline_self_eval",
        should_regen_or_publish,
        {
            "fix": "strategy_reasoner",   # reason before fixing on self-eval too
            "publish": "git_publishing",
        }
    )
    
    workflow.add_edge("git_publishing", END)
    
    return workflow


def compile_workflow() -> StateGraph:
    """Compile the workflow with memory persistence"""
    workflow = build_workflow()
    memory = MemorySaver()
    return workflow.compile(
        checkpointer=memory,
        debug=False
    )


async def run_auto_git_pipeline(
    idea: str,
    user_requirements: str = None,
    requirements: Dict[str, Any] = None,  # Structured requirements from conversation
    use_web_search: bool = True,
    max_debate_rounds: int = 2,
    min_consensus_score: float = 0.7,
    auto_publish: bool = False,
    output_dir: Optional[str] = None,
    stop_after: Optional[str] = None,
    thread_id: str = "default",
    interactive: bool = True,
    resume: bool = True,
) -> AutoGITState:
    """
    Run the complete Auto-GIT pipeline with progress monitoring
    
    Args:
        idea: Research idea or topic
        user_requirements: Optional additional requirements
        requirements: Structured requirements from conversation agent (IMPORTANT!)
        use_web_search: Enable web search
        max_debate_rounds: Maximum debate rounds
        min_consensus_score: Minimum consensus score (0-1)
        auto_publish: Automatically publish to GitHub
        output_dir: Output directory for generated code
        stop_after: Stop after this node (for testing)
        thread_id: Thread ID for checkpointing
        resume: If True (default) and a prior checkpoint exists for thread_id,
                resume from the last completed node instead of starting fresh.
                Set to False to force a clean run (existing checkpoint is kept
                but ignored; new checkpoints overwrite it for this thread_id).
        
    Returns:
        Final state after pipeline execution
    """
    
    # Create initial state
    initial_state = create_initial_state(
        idea=idea,
        user_requirements=user_requirements,
        requirements=requirements,  # Pass requirements to state
        use_web_search=use_web_search,
        max_rounds=max_debate_rounds,
        min_consensus=min_consensus_score
    )
    
    # Add flags to state
    initial_state["auto_publish"] = auto_publish
    initial_state["output_dir"] = output_dir or "output"
    
    # ── Disk-backed checkpoint — enables resume after crash/laptop-sleep ─────
    checkpoint_db = os.path.join("logs", "pipeline_checkpoints.db")
    os.makedirs("logs", exist_ok=True)
    import sqlite3 as _sqlite3
    _conn = _sqlite3.connect(checkpoint_db, check_same_thread=False)
    checkpointer = _AsyncSqliteSaver(_conn)

    config = {
        "configurable": {
            "thread_id": thread_id
        },
        "recursion_limit": 100,  # Prevent infinite loops
    }

    # Build workflow with disk-persistent checkpointer
    workflow = build_workflow().compile(checkpointer=checkpointer, debug=False)

    # Detect prior checkpoint for this thread → resume vs fresh start
    existing_checkpoint = checkpointer.get(config)
    if resume and existing_checkpoint is not None:
        console.print(Panel(
            f"[bold green]\u267b\ufe0f  Resuming from last checkpoint[/bold green]\n"
            f"Thread : [cyan]{thread_id}[/cyan]\n"
            f"DB     : [dim]{checkpoint_db}[/dim]\n\n"
            f"[dim]Pass resume=False or delete {checkpoint_db!r} to force a fresh run.[/dim]",
            title="Resume Mode", border_style="green",
        ))
        astream_input: Optional[AutoGITState] = None  # LangGraph resumes from saved state
    else:
        if resume:
            console.print(f"[dim]No checkpoint found for thread '{thread_id}' — starting fresh.[/dim]")
        astream_input = initial_state
    
    # Pipeline stages for progress tracking
    stages = [
        ("research", "🔍 SOTA research (compound-beta web search)..."),
        ("generate_perspectives", "🧠 Generating domain-specific experts..."),
        ("problem_extraction", "🎯 Extracting research problems..."),
        ("solution_generation", "💡 Generating solutions (Round {})..."),
        ("critique", "🔍 Cross-perspective review..."),
        ("consensus_check", "⚖️  Checking consensus..."),
        ("solution_selection", "🏆 Selecting best solution..."),
        ("architect_spec",    "📐 Designing technical architecture..."),
        ("code_generation",   "💻 Generating implementation code..."),
        ("code_review_agent", "🔍 Deep code review..."),
        ("code_testing",      "🧪 Testing code..."),
        ("strategy_reasoner", "🧠 Reasoning about failures..."),
        ("code_fixing",       "🔧 Auto-fixing issues..."),
        ("pipeline_self_eval","🔬 Self-evaluating quality..."),
        ("git_publishing",    "📤 Publishing to GitHub..."),
    ]
    
    # Progress bar setup
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console
    ) as progress:
        
        main_task = progress.add_task("[cyan]Pipeline Progress", total=len(stages))
        
        final_state = None
        accumulated_state = {}  # Track full state across all node outputs
        current_round = 1
        visited_nodes = set()

        # ── Observability tracer (writes logs/pipeline_trace_*.jsonl + agent_status_*.md) ──
        tracer = PipelineTracer(logs_dir="logs", idea=idea, thread_id=thread_id)

        # ── Lightweight progress heartbeat (survives terminal deletion) ──
        _progress_path = os.path.join("logs", "pipeline_progress.txt")
        def _write_progress(msg: str):
            import time as _t
            line = f"[{__import__('datetime').datetime.now().strftime('%H:%M:%S')}] {msg}\n"
            try:
                with open(_progress_path, "a", encoding="utf-8") as _f:
                    _f.write(line)
            except Exception:
                pass
        _write_progress("workflow astream starting…")

        try:
            async for state in workflow.astream(astream_input, config):
                for node_name, node_state in state.items():
                    
                    # Update progress
                    current_stage = node_state.get("current_stage", "")
                    
                    # Track rounds
                    if node_name == "solution_generation" and node_name in visited_nodes:
                        current_round += 1
                    
                    visited_nodes.add(node_name)
                    
                    # Find matching stage
                    for stage_name, stage_desc in stages:
                        if stage_name == node_name:
                            desc = stage_desc.format(current_round) if '{}' in stage_desc else stage_desc
                            progress.update(main_task, description=f"[cyan]{desc}")
                            progress.advance(main_task, 0.5)
                            break
                    
                    # Display inter-stage results
                    if node_name == "research" and current_stage == "research_complete":
                        display_research_results(node_state)
                    
                    elif node_name == "problem_extraction" and current_stage == "problems_extracted":
                        display_problems(node_state)
                    
                    elif node_name == "critique" and current_stage == "critiques_complete":
                        display_debate_round(node_state)
                    
                    elif node_name == "solution_selection" and current_stage == "solution_selected":
                        display_final_solution(node_state)
                    
                    elif node_name == "code_generation" and current_stage == "code_generated":
                        display_generated_code(node_state)
                    
                    elif node_name == "code_testing" and current_stage == "testing_complete":
                        tests_passed = display_test_results(node_state)

                        if not tests_passed:
                            fix_attempts = node_state.get("fix_attempts", 0)
                            max_attempts = node_state.get("max_fix_attempts", 3)
                            console.print(f"[dim]Fix attempt {fix_attempts}/{max_attempts} — auto-continuing...[/dim]\n")
                    
                    elif node_name == "code_fixing" and current_stage == "code_fixed":
                        fix_attempts = node_state.get("fix_attempts", 0)
                        max_attempts = node_state.get("max_fix_attempts", 3)
                        console.print(f"\n[green]\u2705 Fix attempt {fix_attempts}/{max_attempts} completed. Re-testing...[/green]\n")
                        # No interactive prompt — max_fix_attempts cap stops the loop automatically.
                    
                    elif node_name == "pipeline_self_eval":
                        se_score = node_state.get("self_eval_score", -1)
                        se_stage = node_state.get("current_stage", "")
                        if se_stage == "self_eval_approved":
                            score_label = f"{se_score:.1f}/10" if se_score >= 0 else "skipped"
                            console.print(f"[bold green]\n\u2705 Self-eval approved (score {score_label})[/bold green]")
                        elif se_stage == "self_eval_needs_regen":
                            console.print(f"[bold yellow]\n⚠️  Self-eval score {se_score:.1f}/10 — triggering fix loop[/bold yellow]")

                    elif node_name == "git_publishing" and current_stage == "published":
                        display_github_result(node_state)
                    
                    # ── Trace this node completion ──────────────────────
                    tracer.on_node_complete(node_name, node_state)
                    _write_progress(f"NODE DONE: {node_name} → stage={current_stage}")

                    final_state = node_state
                    accumulated_state.update(node_state)  # Merge all partial states

                    # Stop if requested
                    if stop_after and node_name == stop_after:
                        progress.update(main_task, completed=len(stages))
                        tracer.finish(accumulated_state)
                        return accumulated_state

            progress.update(main_task, completed=len(stages))
            print_token_summary()
            tracer.finish(accumulated_state)
            _write_progress("PIPELINE COMPLETE ✅")
            return accumulated_state

        except Exception as e:
            console.print(f"\n[bold red]❌ Pipeline failed: {e}[/bold red]")
            print_token_summary()
            tracer.finish(accumulated_state)
            _write_progress(f"PIPELINE FAILED ❌: {type(e).__name__}: {e}")
            raise
