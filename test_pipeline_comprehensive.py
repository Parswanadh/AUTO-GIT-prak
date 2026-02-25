#!/usr/bin/env python3
"""
Real-world pipeline test with comprehensive logging
Tests the entire auto-git pipeline with a practical project
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

console = Console()

async def test_pipeline():
    """Run comprehensive pipeline test"""
    
    # Test project ideas (from simple to complex)
    test_cases = [
        {
            "name": "Simple Task API",
            "idea": "Create a FastAPI REST API for task management with CRUD operations, JWT authentication, and SQLite database",
            "expected_features": ["FastAPI", "JWT", "CRUD", "SQLite", "authentication"],
            "complexity": "Medium"
        },
        {
            "name": "Web Scraper",
            "idea": "Build a Python web scraper that extracts product data from e-commerce sites with rate limiting and error handling",
            "expected_features": ["BeautifulSoup", "requests", "rate limiting", "error handling"],
            "complexity": "Simple"
        }
    ]
    
    console.print(Panel.fit(
        "[bold cyan]🧪 AUTO-GIT PIPELINE COMPREHENSIVE TEST[/bold cyan]\n"
        f"[dim]Testing {len(test_cases)} real-world projects[/dim]",
        border_style="cyan"
    ))
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        console.print(f"\n{'='*70}")
        console.print(f"[bold yellow]TEST {i}/{len(test_cases)}: {test_case['name']}[/bold yellow]")
        console.print(f"[dim]Complexity: {test_case['complexity']}[/dim]")
        console.print(f"{'='*70}\n")
        
        console.print(f"[cyan]💡 Idea:[/cyan] {test_case['idea']}\n")
        
        try:
            # Import pipeline
            from src.langraph_pipeline.workflow_enhanced import run_auto_git_pipeline
            
            # Run pipeline
            start_time = datetime.now()
            
            result = await run_auto_git_pipeline(
                idea=test_case['idea'],
                use_web_search=True,
                max_debate_rounds=2,
                min_consensus_score=0.5,
                auto_publish=False,
                output_dir=f"output/test_{i}_{test_case['name'].replace(' ', '_').lower()}"
            )
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # Analyze results
            research_context = result.get('research_context', {})
            papers = research_context.get('papers', []) if research_context else []
            web_results = research_context.get('web_results', []) if research_context else []
            
            problems = result.get('problems', [])
            solutions = result.get('solutions', [])
            final_code = result.get('final_code', '')
            selected_solution = result.get('selected_solution', {})
            
            # Check for expected features in code
            features_found = []
            if final_code:
                for feature in test_case['expected_features']:
                    if feature.lower() in final_code.lower():
                        features_found.append(feature)
            
            # Compile results
            test_result = {
                'name': test_case['name'],
                'status': 'SUCCESS' if final_code else 'PARTIAL',
                'duration': f"{duration:.1f}s",
                'research': {
                    'papers': len(papers),
                    'web_results': len(web_results)
                },
                'problems_extracted': len(problems),
                'solutions_generated': len(solutions),
                'code_generated': len(final_code),
                'features_found': len(features_found),
                'expected_features': len(test_case['expected_features']),
                'consensus': selected_solution.get('consensus_score', 0) if isinstance(selected_solution, dict) else 0
            }
            
            results.append(test_result)
            
            # Display results
            console.print("\n[bold green]✅ TEST COMPLETED[/bold green]\n")
            
            info_table = Table(box=box.ROUNDED, border_style="green")
            info_table.add_column("Metric", style="cyan")
            info_table.add_column("Result", style="white")
            
            info_table.add_row("Duration", f"{duration:.1f} seconds")
            info_table.add_row("Papers Found", str(len(papers)))
            info_table.add_row("Web Results", str(len(web_results)))
            info_table.add_row("Problems Extracted", str(len(problems)))
            info_table.add_row("Solutions Generated", str(len(solutions)))
            info_table.add_row("Code Length", f"{len(final_code):,} characters")
            info_table.add_row("Features Found", f"{len(features_found)}/{len(test_case['expected_features'])}")
            info_table.add_row("Consensus Score", f"{test_result['consensus']:.2f}" if test_result['consensus'] else "N/A")
            
            console.print(info_table)
            
            # Show code snippet if generated
            if final_code:
                console.print("\n[bold]📄 Generated Code Preview:[/bold]")
                preview = final_code[:500] if len(final_code) > 500 else final_code
                console.print(f"[dim]{preview}[/dim]")
                if len(final_code) > 500:
                    console.print(f"[dim]... ({len(final_code) - 500:,} more characters)[/dim]")
            else:
                console.print("\n[yellow]⚠️  No code was generated[/yellow]")
            
            # Show problems if any
            if problems:
                console.print("\n[bold]🎯 Problems Identified:[/bold]")
                for j, problem in enumerate(problems[:3], 1):
                    if isinstance(problem, dict):
                        console.print(f"  {j}. [dim]{problem.get('title', 'Problem')[:80]}[/dim]")
                    else:
                        console.print(f"  {j}. [dim]{str(problem)[:80]}[/dim]")
            
            # Show solutions if any
            if solutions:
                console.print("\n[bold]💡 Solutions Proposed:[/bold]")
                for j, solution in enumerate(solutions[:3], 1):
                    if isinstance(solution, dict):
                        console.print(f"  {j}. [dim]{solution.get('title', 'Solution')[:80]}[/dim]")
                    else:
                        console.print(f"  {j}. [dim]{str(solution)[:80]}[/dim]")
            
        except Exception as e:
            console.print(f"\n[bold red]❌ TEST FAILED[/bold red]")
            console.print(f"[red]Error: {e}[/red]\n")
            
            import traceback
            console.print("[dim]Traceback:[/dim]")
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
            
            results.append({
                'name': test_case['name'],
                'status': 'FAILED',
                'error': str(e)
            })
    
    # Summary
    console.print(f"\n\n{'='*70}")
    console.print("[bold cyan]📊 FINAL TEST SUMMARY[/bold cyan]")
    console.print(f"{'='*70}\n")
    
    summary_table = Table(title="Test Results", box=box.ROUNDED, border_style="cyan")
    summary_table.add_column("Test", style="cyan")
    summary_table.add_column("Status", style="green")
    summary_table.add_column("Duration", style="yellow")
    summary_table.add_column("Code", style="white")
    summary_table.add_column("Features", style="white")
    
    for result in results:
        status_icon = "✅" if result['status'] == 'SUCCESS' else "⚠️" if result['status'] == 'PARTIAL' else "❌"
        summary_table.add_row(
            result['name'],
            f"{status_icon} {result['status']}",
            result.get('duration', 'N/A'),
            f"{result.get('code_generated', 0):,} chars" if 'code_generated' in result else 'N/A',
            f"{result.get('features_found', 0)}/{result.get('expected_features', 0)}" if 'features_found' in result else 'N/A'
        )
    
    console.print(summary_table)
    
    # Overall statistics
    success_count = sum(1 for r in results if r['status'] == 'SUCCESS')
    partial_count = sum(1 for r in results if r['status'] == 'PARTIAL')
    failed_count = sum(1 for r in results if r['status'] == 'FAILED')
    
    console.print(f"\n[bold]Overall:[/bold]")
    console.print(f"  ✅ Success: {success_count}/{len(results)}")
    console.print(f"  ⚠️  Partial: {partial_count}/{len(results)}")
    console.print(f"  ❌ Failed: {failed_count}/{len(results)}")
    
    if success_count == len(results):
        console.print("\n[bold green]🎉 ALL TESTS PASSED![/bold green]")
    elif success_count + partial_count == len(results):
        console.print("\n[bold yellow]⚠️  TESTS COMPLETED WITH WARNINGS[/bold yellow]")
    else:
        console.print("\n[bold red]❌ SOME TESTS FAILED[/bold red]")
    
    console.print()
    
    return results


async def main():
    """Entry point"""
    console.clear()
    
    console.print("""[bold cyan]
   ___         __           _______ ______
  / _ | __ __ / /_ ___     / ___/  /  ___/
 / __ |/ // // __// _ \   / (_ / / / /    
/_/ |_|\_,_/ \__/ \___/   \___//_/ /_/     
                                           
[/bold cyan][dim]Pipeline Integration Test[/dim]
""")
    
    results = await test_pipeline()
    
    # Save results to file
    output_file = Path("output/test_results.txt")
    output_file.parent.mkdir(exist_ok=True)
    
    with open(output_file, 'w') as f:
        f.write(f"Auto-GIT Pipeline Test Results\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        for result in results:
            f.write(f"\nTest: {result['name']}\n")
            f.write(f"Status: {result['status']}\n")
            if 'duration' in result:
                f.write(f"Duration: {result['duration']}\n")
            if 'code_generated' in result:
                f.write(f"Code Generated: {result['code_generated']} characters\n")
            if 'error' in result:
                f.write(f"Error: {result['error']}\n")
    
    console.print(f"[dim]Results saved to: {output_file}[/dim]\n")


if __name__ == "__main__":
    asyncio.run(main())
