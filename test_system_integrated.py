#!/usr/bin/env python3
"""
Integrated Auto-GIT System Test
Comprehensive testing with progress tracking and error handling
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box

console = Console()


async def test_imports():
    """Test all critical imports"""
    console.print("\n[bold cyan]📦 Testing Imports...[/bold cyan]\n")
    
    imports = {
        "Core": ["asyncio", "sys", "pathlib"],
        "Rich UI": ["rich.console", "rich.panel", "rich.table", "rich.progress"],
        "LangChain/LangGraph": ["langchain", "langgraph", "langchain_ollama"],
        "LLM Providers": ["groq", "ollama"],
        "Research": ["arxiv", "duckduckgo_search", "tavily"],
        "GitHub": ["github"],
        "Auto-GIT": ["src.langraph_pipeline.workflow_enhanced", "src.agents.sequential_orchestrator"]
    }
    
    results = Table(title="Import Test Results", box=box.ROUNDED, border_style="cyan")
    results.add_column("Category", style="cyan")
    results.add_column("Status", style="green")
    results.add_column("Details", style="white")
    
    for category, modules in imports.items():
        try:
            for module in modules:
                __import__(module)
            results.add_row(category, "✅ PASS", f"{len(modules)} modules loaded")
        except ImportError as e:
            results.add_row(category, "❌ FAIL", str(e))
            return False
    
    console.print(results)
    return True


async def test_ollama_connection():
    """Test Ollama is running and has models"""
    console.print("\n[bold cyan]🤖 Testing Ollama Connection...[/bold cyan]\n")
    
    try:
        import httpx
        
        # Use httpx to connect directly to Ollama API
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:11434/api/tags", timeout=5.0)
            response.raise_for_status()
            data = response.json()
            
            models = data.get("models", [])
            model_names = [m.get("name", "unknown") for m in models]
            
            console.print(f"[green]✅ Ollama running with {len(model_names)} models:[/green]")
            for name in model_names[:5]:
                console.print(f"   • {name}")
            if len(model_names) > 5:
                console.print(f"   • ... and {len(model_names) - 5} more")
            
            return True
        
    except Exception as e:
        console.print(f"[red]❌ Ollama connection failed: {e}[/red]")
        console.print("[yellow]Try running: ollama serve[/yellow]")
        return False


async def test_config_files():
    """Test configuration files exist"""
    console.print("\n[bold cyan]⚙️  Testing Configuration Files...[/bold cyan]\n")
    
    config_files = {
        "config.yaml": "Main configuration",
        "requirements.txt": "Dependencies",
        ".env": "Environment variables (optional)",
    }
    
    results = Table(box=box.ROUNDED, border_style="cyan")
    results.add_column("File", style="cyan")
    results.add_column("Status", style="green")
    results.add_column("Description", style="white")
    
    for file, desc in config_files.items():
        path = Path(file)
        if path.exists():
            results.add_row(file, "✅ EXISTS", desc)
        elif file == ".env":
            results.add_row(file, "⚠️  OPTIONAL", desc)
        else:
            results.add_row(file, "❌ MISSING", desc)
    
    console.print(results)
    return True


async def test_pipeline_components():
    """Test key pipeline components"""
    console.print("\n[bold cyan]🔧 Testing Pipeline Components...[/bold cyan]\n")
    
    try:
        from src.langraph_pipeline.workflow_enhanced import run_auto_git_pipeline
        from src.langraph_pipeline.state import create_initial_state
        from src.agents.sequential_orchestrator import create_orchestrator
        
        console.print("[green]✅ Pipeline components loaded successfully[/green]")
        console.print("   • workflow_enhanced.run_auto_git_pipeline")
        console.print("   • state.create_initial_state")
        console.print("   • agents.sequential_orchestrator")
        
        return True
        
    except Exception as e:
        console.print(f"[red]❌ Pipeline component error: {e}[/red]")
        return False


async def run_diagnostic():
    """Run full diagnostic"""
    console.clear()
    
    console.print(Panel.fit(
        "[bold cyan]Auto-GIT System Diagnostic[/bold cyan]\n"
        "[dim]Testing all components before pipeline execution[/dim]",
        border_style="cyan"
    ))
    
    tests = [
        ("Imports", test_imports),
        ("Ollama", test_ollama_connection),
        ("Config", test_config_files),
        ("Pipeline", test_pipeline_components),
    ]
    
    results = []
    for name, test_func in tests:
        result = await test_func()
        results.append((name, result))
    
    # Summary
    console.print("\n" + "="*60 + "\n")
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    if passed == total:
        console.print(Panel.fit(
            f"[bold green]✅ ALL TESTS PASSED ({passed}/{total})[/bold green]\n"
            "[dim]System is ready for pipeline execution[/dim]",
            border_style="green"
        ))
        return True
    else:
        console.print(Panel.fit(
            f"[bold red]⚠️  SOME TESTS FAILED ({passed}/{total})[/bold red]\n"
            "[dim]Fix errors before running pipeline[/dim]",
            border_style="red"
        ))
        return False


async def run_simple_test_project():
    """Run a simple test project through the pipeline"""
    console.print("\n" + "="*60)
    console.print(Panel.fit(
        "[bold cyan]🚀 Running Test Project[/bold cyan]\n"
        "[dim]Testing: Simple REST API with FastAPI[/dim]",
        border_style="cyan"
    ))
    
    try:
        from src.langraph_pipeline.workflow_enhanced import run_auto_git_pipeline
        
        test_idea = "Create a simple REST API with FastAPI that manages a todo list"
        
        console.print(f"\n[yellow]Idea:[/yellow] {test_idea}\n")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Running pipeline...", total=None)
            
            result = await run_auto_git_pipeline(
                idea=test_idea,
                use_web_search=True,
                max_debate_rounds=1,  # Keep it short for testing
                min_consensus_score=0.5,
                auto_publish=False,  # Don't publish during test
                output_dir="output/test_run",
                stop_after=None  # Run full pipeline
            )
            
            progress.update(task, completed=True, description="[green]✅ Pipeline completed")
        
        # Display results
        console.print("\n[bold green]✅ Test Completed Successfully![/bold green]\n")
        
        # Show key results
        info = Table(title="Test Results", box=box.ROUNDED, border_style="green")
        info.add_column("Stage", style="cyan")
        info.add_column("Result", style="white")
        
        info.add_row("Research", f"{len(result.get('research_context', {}).get('papers', []))} papers found")
        info.add_row("Problems", f"{len(result.get('problems', []))} problems extracted")
        info.add_row("Solutions", f"{len(result.get('solutions', []))} solutions generated")
        
        final_code = result.get("final_code", "")
        if final_code:
            info.add_row("Code Generated", f"✅ {len(final_code)} characters")
        else:
            info.add_row("Code Generated", "❌ No code generated")
        
        console.print(info)
        
        return True
        
    except Exception as e:
        console.print(f"\n[bold red]❌ Pipeline Error:[/bold red] {e}\n")
        import traceback
        console.print("[dim]" + traceback.format_exc() + "[/dim]")
        return False


async def interactive_menu():
    """Interactive menu for testing"""
    while True:
        console.print("\n" + "="*60)
        console.print(Panel.fit(
            "[bold cyan]Auto-GIT Integrated Testing[/bold cyan]\n\n"
            "[1] Run System Diagnostic\n"
            "[2] Run Simple Test Project\n"
            "[3] Run Full Pipeline (Custom Idea)\n"
            "[4] Test Ollama Models\n"
            "[5] Exit\n",
            border_style="cyan"
        ))
        
        choice = console.input("\n[cyan]Select option (1-5):[/cyan] ").strip()
        
        if choice == "1":
            await run_diagnostic()
        
        elif choice == "2":
            success = await run_diagnostic()
            if success:
                await run_simple_test_project()
            else:
                console.print("\n[red]Fix diagnostic errors first![/red]")
        
        elif choice == "3":
            success = await run_diagnostic()
            if success:
                idea = console.input("\n[cyan]Enter your project idea:[/cyan] ").strip()
                if idea:
                    try:
                        from src.langraph_pipeline.workflow_enhanced import run_auto_git_pipeline
                        result = await run_auto_git_pipeline(
                            idea=idea,
                            use_web_search=True,
                            max_debate_rounds=2,
                            min_consensus_score=0.5,
                            auto_publish=False
                        )
                        console.print("\n[green]✅ Pipeline completed![/green]")
                    except Exception as e:
                        console.print(f"\n[red]❌ Error: {e}[/red]")
            else:
                console.print("\n[red]Fix diagnostic errors first![/red]")
        
        elif choice == "4":
            await test_ollama_connection()
        
        elif choice == "5":
            console.print("\n[cyan]👋 Goodbye![/cyan]\n")
            break
        
        else:
            console.print("\n[red]Invalid choice. Try again.[/red]")


async def main():
    """Main entry point"""
    console.clear()
    
    console.print("""[bold cyan]
   ___         __           _______ ______
  / _ | __ __ / /_ ___     / ___/  /  ___/
 / __ |/ // // __// _ \   / (_ / / / /    
/_/ |_|\_,_/ \__/ \___/   \___//_/ /_/     
                                           
[/bold cyan][dim]Integrated System Testing & Verification[/dim]
""")
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--diagnostic":
            await run_diagnostic()
        elif sys.argv[1] == "--test":
            success = await run_diagnostic()
            if success:
                await run_simple_test_project()
        elif sys.argv[1] == "--help":
            console.print("""
[bold cyan]Usage:[/bold cyan]
  python test_system_integrated.py              # Interactive menu
  python test_system_integrated.py --diagnostic # Run diagnostic only
  python test_system_integrated.py --test       # Run diagnostic + test project
  python test_system_integrated.py --help       # Show this help
""")
        else:
            console.print(f"[red]Unknown option: {sys.argv[1]}[/red]")
            console.print("Use --help for usage information")
    else:
        await interactive_menu()


if __name__ == "__main__":
    asyncio.run(main())
