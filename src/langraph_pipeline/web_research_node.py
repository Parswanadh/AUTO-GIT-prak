"""
Integration #11: Web Search Research Node for LangGraph Pipeline

Performs multi-source research using DuckDuckGo + arXiv before problem extraction.
"""

import logging
from typing import Dict, Any
from rich.console import Console

from .state import AutoGITState

logger = logging.getLogger(__name__)
console = Console()


async def web_research_node(state: AutoGITState) -> Dict[str, Any]:
    """
    Integration #11: Multi-source web research node
    
    Searches DuckDuckGo + arXiv for latest information, best practices,
    and academic papers related to the user's idea.
    
    This runs BEFORE problem extraction to ground solutions in research.
    
    Args:
        state: Current pipeline state with 'idea' field
        
    Returns:
        Dict with research_report and research_summary
    """
    idea = state['idea']
    logger.info(f"🔍 Integration #11 Research: '{idea}'")
    
    console.print(f"\n[cyan]🔍 Web Research:[/cyan] [bold]{idea}[/bold]")
    console.print("[dim]  • DuckDuckGo (latest info + best practices)[/dim]")
    console.print("[dim]  • arXiv (academic papers)[/dim]")
    console.print("[dim]  • Quality validation + deduplication[/dim]\n")
    
    # Skip if disabled
    if not state.get("use_web_search", True):
        logger.info("Web search disabled, skipping research")
        console.print("[yellow]⚠ Web search disabled, skipping research[/yellow]\n")
        return {
            "current_stage": "research_skipped",
            "research_report": None,
            "research_summary": "Web search disabled"
        }
    
    try:
        # Import ResearchCoordinator (late import to avoid circular deps)
        from agents.research import ResearchCoordinator, ResearchConfig
        
        # Configure research for this use case
        config = ResearchConfig(
            max_iterations=2,              # 2 rounds max (fast)
            max_results_per_source=5,      # 5 results per source
            min_total_results=8,            # Stop at 8+ results
            enable_duckduckgo=True,         # Latest info
            enable_arxiv=True,              # Academic papers
            enable_query_refinement=True,   # Auto-refine queries
            cache_ttl_seconds=3600          # 1 hour cache
        )
        
        coordinator = ResearchCoordinator(config)
        
        # Build research query from idea
        # Add keywords for better results
        query = f"{idea} best practices implementation"
        
        console.print(f"[dim]Searching for: {query}[/dim]\n")
        
        # Execute research
        report = await coordinator.research(query, max_iterations=2)
        
        # Display results
        console.print(f"[green]✓ Found {report.total_results} results[/green]")
        console.print(f"[dim]  • Sources: {', '.join(report.sources_used)}[/dim]")
        console.print(f"[dim]  • Papers: {len(report.related_papers)}[/dim]")
        console.print(f"[dim]  • Web: {len(report.web_resources)}[/dim]")
        console.print(f"[dim]  • Iterations: {report.iterations}[/dim]\n")
        
        # Show top 3 results
        if report.results:
            console.print("[cyan]Top Research Results:[/cyan]")
            for i, result in enumerate(report.results[:3], 1):
                console.print(f"  {i}. [bold]{result.title}[/bold]")
                console.print(f"     [dim]{result.source} | {result.url[:60]}...[/dim]")
        
        # Create concise summary for prompts
        research_summary = _create_prompt_summary(report)
        
        logger.info(f"✓ Research complete: {report.total_results} results from {len(report.sources_used)} sources")
        
        return {
            "current_stage": "research_complete",
            "research_report": report,  # Full report object
            "research_summary": research_summary  # Concise text for prompts
        }
        
    except ImportError as e:
        logger.warning(f"Research module not available: {e}")
        console.print(f"[yellow]⚠ Research module not available, skipping[/yellow]\n")
        return {
            "current_stage": "research_unavailable",
            "research_report": None,
            "research_summary": "Research module not available"
        }
        
    except Exception as e:
        logger.error(f"Research failed: {e}", exc_info=True)
        console.print(f"[red]✗ Research failed: {e}[/red]\n")
        
        # Don't fail the pipeline, just continue without research
        return {
            "current_stage": "research_failed",
            "research_report": None,
            "research_summary": f"Research failed: {str(e)}",
            "warnings": [f"Research failed: {str(e)}"]
        }


def _create_prompt_summary(report) -> str:
    """
    Create a concise summary for inclusion in LLM prompts.
    
    Keeps it short to avoid token bloat while providing key insights.
    """
    lines = []
    
    lines.append(f"RESEARCH SUMMARY ({report.total_results} results from {len(report.sources_used)} sources)")
    lines.append("")
    
    # Top 5 findings
    if report.results:
        lines.append("Key Findings:")
        for i, result in enumerate(report.results[:5], 1):
            lines.append(f"  {i}. {result.title}")
            lines.append(f"     {result.url}")
            if result.content:
                # First 200 chars of content
                snippet = result.content[:200].strip()
                if len(result.content) > 200:
                    snippet += "..."
                lines.append(f"     {snippet}")
            lines.append("")
    
    # Related papers
    if report.related_papers:
        lines.append("Related Academic Papers:")
        for paper in report.related_papers[:3]:
            lines.append(f"  • {paper}")
        if len(report.related_papers) > 3:
            lines.append(f"  ... and {len(report.related_papers) - 3} more")
        lines.append("")
    
    # Web resources
    if report.web_resources:
        lines.append("Relevant Web Resources:")
        for url in report.web_resources[:3]:
            lines.append(f"  • {url}")
        if len(report.web_resources) > 3:
            lines.append(f"  ... and {len(report.web_resources) - 3} more")
    
    return "\n".join(lines)


# Synchronous wrapper for non-async pipelines
def web_research_node_sync(state: AutoGITState) -> Dict[str, Any]:
    """Synchronous wrapper for web_research_node."""
    import asyncio
    
    # Run in event loop
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(web_research_node(state))
