#!/usr/bin/env python3
"""
Test Auto-GIT pipeline with resource monitoring
This prevents VRAM thrashing and crashes
"""

import asyncio
import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.resource_monitor import ResourceMonitor
from src.langraph_pipeline.workflow_enhanced import run_auto_git_pipeline

console = Console()


async def test_with_monitoring(idea: str, output_dir: str):
    """Run pipeline with resource monitoring"""
    
    monitor = ResourceMonitor(check_interval=2.0)
    
    console.print(Panel.fit(
        f"[bold cyan]Testing Auto-GIT with Resource Monitoring[/bold cyan]\n\n"
        f"Idea: {idea}\n"
        f"Output: {output_dir}",
        border_style="cyan"
    ))
    
    # Display initial resources
    console.print("\n[bold]Initial Resource State:[/bold]")
    monitor.display()
    
    # Check if safe to proceed
    if not monitor.check_safe_to_proceed():
        console.print("[red]Cannot start - resources not available[/red]")
        return False
    
    # Start monitoring
    monitor.start()
    
    try:
        console.print("\n[bold green]Starting pipeline...[/bold green]\n")
        
        result = await run_auto_git_pipeline(
            idea=idea,
            use_web_search=False,  # Disable web search for stability
            max_debate_rounds=1,
            auto_publish=False,
            output_dir=output_dir
        )
        
        console.print("\n[bold green]✓ Pipeline completed![/bold green]")
        
        # Display final resources
        console.print("\n[bold]Final Resource State:[/bold]")
        monitor.display()
        
        return True
        
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Stopped by user[/yellow]")
        return False
        
    except Exception as e:
        console.print(f"\n[bold red]✗ Pipeline failed:[/bold red] {e}")
        
        # Display resources at failure
        console.print("\n[bold]Resources at Failure:[/bold]")
        monitor.display()
        
        import traceback
        console.print("\n[dim]Full traceback:[/dim]")
        console.print(traceback.format_exc())
        
        return False
        
    finally:
        monitor.stop()


async def main():
    """Run tests"""
    
    console.print("\n[bold cyan]═══════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]   Auto-GIT Resource-Monitored Test   [/bold cyan]")
    console.print("[bold cyan]═══════════════════════════════════════[/bold cyan]\n")
    
    # Simple test case
    test_cases = [
        {
            "name": "Simple Calculator",
            "idea": "Create a simple command-line calculator that can add, subtract, multiply and divide two numbers",
            "output": "output/test_calculator"
        },
    ]
    
    results = []
    
    for i, test in enumerate(test_cases, 1):
        console.print(f"\n[bold]═══ Test {i}/{len(test_cases)}: {test['name']} ═══[/bold]\n")
        
        success = await test_with_monitoring(
            idea=test["idea"],
            output_dir=test["output"]
        )
        
        results.append({
            "name": test["name"],
            "success": success
        })
        
        if not success:
            console.print(f"\n[red]Test '{test['name']}' failed. Stopping tests.[/red]")
            break
    
    # Summary
    console.print("\n\n[bold cyan]═══════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]           Test Summary                [/bold cyan]")
    console.print("[bold cyan]═══════════════════════════════════════[/bold cyan]\n")
    
    for result in results:
        status = "[green]✓ PASSED[/green]" if result["success"] else "[red]✗ FAILED[/red]"
        console.print(f"  {status} - {result['name']}")
    
    passed = sum(1 for r in results if r["success"])
    total = len(results)
    
    console.print(f"\n[bold]Result: {passed}/{total} tests passed[/bold]\n")


if __name__ == "__main__":
    asyncio.run(main())
