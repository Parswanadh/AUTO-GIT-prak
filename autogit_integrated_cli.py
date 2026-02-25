#!/usr/bin/env python3
"""
AUTO-GIT INTEGRATED CLI
Complete integrated system with all features in one place
"""

import asyncio
import sys
import os
import time
from pathlib import Path
from typing import Optional, List
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich import box
from rich.markdown import Markdown

console = Console()

# ASCII Art Logo
LOGO = """[bold cyan]
   ___         __           _______ ______
  / _ | __ __ / /_ ___     / ___/  /  ___/
 / __ |/ // // __// _ \   / (_ / / / /    
/_/ |_|\_,_/ \__/ \___/   \___//_/ /_/     
                                           
[/bold cyan][dim]Autonomous Research → Code → GitHub Pipeline
Powered by LangGraph | Built with ❤️[/dim]
"""

class AutoGITIntegratedCLI:
    """Integrated CLI for complete Auto-GIT system"""
    
    def __init__(self):
        self.console = console
        
    def show_banner(self):
        """Display welcome banner"""
        self.console.clear()
        self.console.print(LOGO)
        self.console.print()
    
    def show_main_menu(self):
        """Display main menu"""
        table = Table(
            title="🎯 Auto-GIT Integrated System",
            show_header=True,
            header_style="bold magenta",
            border_style="cyan",
            box=box.ROUNDED
        )
        
        table.add_column("Option", style="cyan", width=10)
        table.add_column("Command", style="green", width=20)
        table.add_column("Description", style="white")
        table.add_column("Status", style="yellow")
        
        table.add_row(
            "[1]", "generate", 
            "Full pipeline: research → debate → code → test → publish",
            "✅ Ready"
        )
        
        table.add_row(
            "[2]", "fix", 
            "Test & fix existing projects from output folder",
            "✅ Ready"
        )
        
        table.add_row(
            "[3]", "research", 
            "Research-only mode (papers + GitHub)",
            "✅ Ready"
        )
        
        table.add_row(
            "[4]", "debate", 
            "Multi-perspective expert debate",
            "✅ Ready"
        )
        
        table.add_row(
            "[5]", "batch", 
            "Process multiple ideas from file",
            "✅ Ready"
        )
        
        table.add_row(
            "[6]", "status", 
            "Check system health (Ollama, models)",
            "✅ Ready"
        )
        
        table.add_row(
            "[7]", "config", 
            "Configure settings (GitHub token, etc)",
            "⚙️  Config"
        )
        
        table.add_row(
            "[8]", "test", 
            "Run system tests",
            "🧪 Test"
        )
        
        table.add_row(
            "[0]", "exit", 
            "Exit the CLI",
            "👋"
        )
        
        self.console.print(table)
        self.console.print("\n💡 [dim]Type option number or command name[/dim]\n")
    
    async def check_system_status(self):
        """Check system health"""
        self.console.print("\n[bold cyan]🔍 System Status Check[/bold cyan]\n")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:
            
            # Check Ollama
            task1 = progress.add_task("[cyan]Checking Ollama...", total=None)
            ollama_ok = await self._check_ollama()
            progress.update(task1, completed=True)
            
            if ollama_ok:
                self.console.print("  [green]✅ Ollama running[/green]")
            else:
                self.console.print("  [red]❌ Ollama not responding[/red]")
                self.console.print("     [yellow]Start with: ollama serve[/yellow]")
            
            # Check models
            task2 = progress.add_task("[cyan]Checking models...", total=None)
            models = await self._check_models()
            progress.update(task2, completed=True)
            
            if models:
                self.console.print(f"  [green]✅ {len(models)} models available[/green]")
                for model in models[:5]:  # Show first 5
                    self.console.print(f"     • {model}")
                if len(models) > 5:
                    self.console.print(f"     [dim]... and {len(models) - 5} more[/dim]")
            else:
                self.console.print("  [yellow]⚠️  No models found[/yellow]")
            
            # Check GitHub token
            task3 = progress.add_task("[cyan]Checking GitHub...", total=None)
            github_ok = self._check_github()
            progress.update(task3, completed=True)
            
            if github_ok:
                self.console.print("  [green]✅ GitHub token configured[/green]")
            else:
                self.console.print("  [yellow]⚠️  GitHub token not set[/yellow]")
                self.console.print("     [dim]Set in .env: GITHUB_TOKEN=ghp_xxx[/dim]")
            
            # Check output directory
            task4 = progress.add_task("[cyan]Checking workspace...", total=None)
            output_ok = self._check_workspace()
            progress.update(task4, completed=True)
            
            if output_ok:
                self.console.print("  [green]✅ Workspace ready[/green]")
            else:
                self.console.print("  [yellow]⚠️  Creating workspace...[/yellow]")
        
        self.console.print("\n[bold green]✅ System check complete![/bold green]\n")
        return ollama_ok
    
    async def _check_ollama(self) -> bool:
        """Check if Ollama is running"""
        try:
            import httpx
            response = await httpx.AsyncClient().get(
                "http://localhost:11434/api/tags",
                timeout=5
            )
            return response.status_code == 200
        except Exception:
            return False
    
    async def _check_models(self) -> List[str]:
        """Get list of available Ollama models"""
        try:
            import httpx
            response = await httpx.AsyncClient().get(
                "http://localhost:11434/api/tags",
                timeout=5
            )
            if response.status_code == 200:
                models_data = response.json().get("models", [])
                return [m["name"] for m in models_data]
            return []
        except Exception:
            return []
    
    def _check_github(self) -> bool:
        """Check if GitHub token is configured"""
        return bool(os.getenv("GITHUB_TOKEN"))
    
    def _check_workspace(self) -> bool:
        """Check if workspace directories exist"""
        output = Path("output")
        logs = Path("logs")
        data = Path("data")
        
        for dir_path in [output, logs, data]:
            if not dir_path.exists():
                dir_path.mkdir(parents=True, exist_ok=True)
        
        return True
    
    async def generate_project(self, idea: Optional[str] = None):
        """Run full pipeline: research → debate → code → test → publish"""
        self.console.print("\n[bold cyan]🚀 Generate Project - Full Pipeline[/bold cyan]\n")
        
        if not idea:
            self.console.print("[yellow]Enter your research idea or problem statement:[/yellow]")
            self.console.print("[dim]Examples:[/dim]")
            self.console.print("  [dim]• Sparse attention mechanism for 4GB VRAM[/dim]")
            self.console.print("  [dim]• Integrating text LLM to understand images[/dim]")
            self.console.print("  [dim]• Efficient transformer with linear complexity[/dim]\n")
            
            idea = Prompt.ask("💡 Your idea")
            
            if not idea or len(idea) < 10:
                self.console.print("[red]❌ Idea too short. Please provide more details.[/red]\n")
                return
        
        self.console.print(f"\n[green]✓[/green] Idea: [cyan]{idea}[/cyan]\n")
        
        # Ask for options
        use_web = Confirm.ask("Enable web search (arXiv + GitHub)?", default=True)
        max_rounds = int(Prompt.ask("Max debate rounds", default="3"))
        
        self.console.print("\n[bold yellow]🔥 Starting pipeline...[/bold yellow]\n")
        
        try:
            # Import pipeline
            from src.langraph_pipeline.integrated_workflow import run_integrated_pipeline
            
            # Run pipeline
            start_time = time.time()
            
            result = await run_integrated_pipeline(
                idea=idea,
                use_web_search=use_web,
                max_rounds=max_rounds,
                min_consensus=0.7,
                thread_id=None,
                resume=False
            )
            
            elapsed = time.time() - start_time
            
            # Show results
            self.console.print("\n[bold green]✅ Pipeline Complete![/bold green]\n")
            self.console.print(f"⏱️  Total time: {elapsed:.1f}s ({elapsed/60:.1f} minutes)")
            self.console.print(f"📍 Final stage: {result.get('current_stage', 'completed')}")
            
            # Show output location
            if result.get("repo_url"):
                self.console.print(f"\n🎉 [bold green]Published to GitHub:[/bold green] {result['repo_url']}")
            elif result.get("output_path"):
                self.console.print(f"\n📁 [cyan]Code saved to:[/cyan] {result['output_path']}")
            
            self.console.print()
            
        except KeyboardInterrupt:
            self.console.print("\n[yellow]⚠️  Pipeline interrupted by user[/yellow]\n")
        except Exception as e:
            self.console.print(f"\n[red]❌ Error: {e}[/red]\n")
            import traceback
            self.console.print(f"[dim]{traceback.format_exc()}[/dim]\n")
    
    async def fix_project(self, project_name: Optional[str] = None):
        """Test and fix existing projects"""
        self.console.print("\n[bold cyan]🔧 Fix Project - Test & Debug[/bold cyan]\n")
        
        output_dir = Path("output")
        
        if not output_dir.exists():
            self.console.print("[red]❌ No output folder found. Generate a project first![/red]\n")
            return
        
        # List all projects
        projects = [d for d in output_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]
        
        if not projects:
            self.console.print("[red]❌ No projects found in output folder![/red]\n")
            return
        
        # Show available projects
        if not project_name:
            table = Table(title="📂 Available Projects", box=box.ROUNDED, border_style="cyan")
            table.add_column("#", style="cyan")
            table.add_column("Project", style="green")
            table.add_column("Last Modified", style="dim")
            
            for i, proj in enumerate(projects, 1):
                mtime = datetime.fromtimestamp(proj.stat().st_mtime)
                table.add_row(str(i), proj.name, mtime.strftime("%Y-%m-%d %H:%M"))
            
            self.console.print(table)
            self.console.print()
            
            choice = Prompt.ask("Select project number or name")
            
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(projects):
                    project_name = projects[idx].name
            except ValueError:
                project_name = choice
        
        # Find matching project
        matching_project = None
        for proj in projects:
            if project_name.lower() in proj.name.lower():
                matching_project = proj
                break
        
        if not matching_project:
            self.console.print(f"[red]❌ Project '{project_name}' not found![/red]\n")
            return
        
        self.console.print(f"\n[green]✓[/green] Selected: [cyan]{matching_project.name}[/cyan]\n")
        
        # Get latest code folder
        code_folders = [d for d in matching_project.iterdir() if d.is_dir()]
        if not code_folders:
            self.console.print("[red]❌ No code found in project![/red]\n")
            return
        
        latest_folder = max(code_folders, key=lambda x: x.stat().st_mtime)
        
        self.console.print(f"[dim]Location: {latest_folder}[/dim]\n")
        
        # Test and fix
        try:
            from src.utils.code_executor import CodeExecutor
            
            max_attempts = 6
            for attempt in range(1, max_attempts + 1):
                self.console.print(f"[bold yellow]🧪 Test Attempt {attempt}/{max_attempts}[/bold yellow]")
                
                executor = CodeExecutor(latest_folder)
                results = executor.run_full_test_suite()
                
                # Check if all tests pass
                all_pass = (
                    results.get("environment_created", False) and
                    results.get("dependencies_installed", False) and
                    results.get("syntax_valid", False) and
                    results.get("import_successful", False)
                )
                
                if all_pass:
                    self.console.print("\n[bold green]✅ All tests passed![/bold green]")
                    
                    if Confirm.ask("\nPublish to GitHub?", default=False):
                        await self._publish_project(latest_folder)
                    
                    break
                else:
                    self.console.print("\n[yellow]❌ Tests failed. Attempting fixes...[/yellow]")
                    
                    # Run code_fixing_node
                    from src.langraph_pipeline.nodes import code_fixing_node
                    from src.langraph_pipeline.state import create_initial_state
                    
                    state = create_initial_state()
                    state["generated_code"] = {}
                    
                    # Load files
                    for file_path in latest_folder.glob("*.py"):
                        state["generated_code"][file_path.name] = file_path.read_text()
                    
                    state["test_results"] = results
                    
                    # Fix
                    fixed_state = await code_fixing_node(state)
                    
                    # Save fixes
                    if fixed_state.get("generated_code"):
                        for filename, code in fixed_state["generated_code"].items():
                            file_path = latest_folder / filename
                            file_path.write_text(code)
                        
                        self.console.print("[green]✓ Fixes applied[/green]\n")
                    else:
                        self.console.print("[red]❌ No fixes generated[/red]\n")
                        break
            else:
                self.console.print("\n[red]❌ Max attempts reached. Project still has errors.[/red]\n")
        
        except Exception as e:
            self.console.print(f"\n[red]❌ Error: {e}[/red]\n")
    
    async def _publish_project(self, project_path: Path):
        """Publish project to GitHub"""
        try:
            from src.langraph_pipeline.nodes import git_publishing_node
            from src.langraph_pipeline.state import create_initial_state
            
            state = create_initial_state()
            state["output_path"] = str(project_path)
            state["generated_code"] = {}
            
            # Load files
            for file_path in project_path.glob("*.py"):
                state["generated_code"][file_path.name] = file_path.read_text()
            
            self.console.print("\n[yellow]Publishing to GitHub...[/yellow]")
            
            result = await git_publishing_node(state)
            
            if result.get("repo_url"):
                self.console.print(f"\n[bold green]✅ Published![/bold green] {result['repo_url']}\n")
            else:
                self.console.print("\n[red]❌ Publishing failed[/red]\n")
        
        except Exception as e:
            self.console.print(f"\n[red]❌ Error: {e}[/red]\n")
    
    async def research_only(self, topic: Optional[str] = None):
        """Research-only mode"""
        self.console.print("\n[bold cyan]🔍 Research Mode[/bold cyan]\n")
        
        if not topic:
            topic = Prompt.ask("🔍 Research topic")
        
        self.console.print(f"\n[green]✓[/green] Topic: [cyan]{topic}[/cyan]\n")
        self.console.print("[yellow]Searching arXiv and GitHub...[/yellow]\n")
        
        try:
            from src.utils.web_search import search_arxiv, search_github
            
            # Search arXiv
            papers = await search_arxiv(topic, max_results=5)
            
            # Search GitHub
            repos = await search_github(topic, max_results=5)
            
            # Display results
            if papers:
                table = Table(title="📚 arXiv Papers", box=box.ROUNDED)
                table.add_column("Title", style="cyan")
                table.add_column("Authors", style="dim")
                
                for paper in papers[:5]:
                    table.add_row(
                        paper.get("title", "N/A")[:60],
                        paper.get("authors", ["Unknown"])[0]
                    )
                
                self.console.print(table)
                self.console.print()
            
            if repos:
                table = Table(title="💻 GitHub Repositories", box=box.ROUNDED)
                table.add_column("Repository", style="green")
                table.add_column("Stars", style="yellow")
                
                for repo in repos[:5]:
                    table.add_row(
                        repo.get("full_name", "N/A"),
                        str(repo.get("stars", 0))
                    )
                
                self.console.print(table)
                self.console.print()
        
        except Exception as e:
            self.console.print(f"\n[red]❌ Error: {e}[/red]\n")
    
    async def debate_mode(self, problem: Optional[str] = None):
        """Multi-perspective debate"""
        self.console.print("\n[bold cyan]💬 Debate Mode[/bold cyan]\n")
        
        if not problem:
            problem = Prompt.ask("💬 Problem statement")
        
        self.console.print(f"\n[green]✓[/green] Problem: [cyan]{problem}[/cyan]\n")
        self.console.print("[yellow]Running multi-perspective debate...[/yellow]\n")
        
        try:
            from src.agents.sequential_orchestrator import create_orchestrator
            
            problem_dict = {
                "domain": "General",
                "challenge": problem,
                "current_solutions": [],
                "limitations": [],
                "requirements": []
            }
            
            orchestrator = create_orchestrator()
            result = await orchestrator.execute_pipeline(problem_dict, max_refinements=1)
            
            # Display results
            self.console.print("\n[bold green]✅ Debate Complete![/bold green]\n")
            self.console.print(f"Consensus Score: {result.consensus.weighted_score:.1f}/10")
            self.console.print(f"\n[cyan]Final Solution:[/cyan]")
            self.console.print(result.final_solution[:500] + "...\n")
        
        except Exception as e:
            self.console.print(f"\n[red]❌ Error: {e}[/red]\n")
    
    async def batch_process(self, ideas_file: Optional[str] = None):
        """Process multiple ideas from file"""
        self.console.print("\n[bold cyan]📦 Batch Processing[/bold cyan]\n")
        
        if not ideas_file:
            ideas_file = Prompt.ask("Ideas file path", default="ideas.txt")
        
        file_path = Path(ideas_file)
        
        if not file_path.exists():
            self.console.print(f"[red]❌ File not found: {ideas_file}[/red]\n")
            return
        
        # Read ideas
        ideas = [line.strip() for line in file_path.read_text().splitlines() if line.strip()]
        
        self.console.print(f"[green]✓[/green] Loaded {len(ideas)} ideas\n")
        
        # Process each
        for i, idea in enumerate(ideas, 1):
            self.console.print(f"\n[bold yellow]Processing {i}/{len(ideas)}:[/bold yellow] {idea[:60]}...")
            
            try:
                from src.langraph_pipeline.integrated_workflow import run_integrated_pipeline
                
                result = await run_integrated_pipeline(
                    idea=idea,
                    use_web_search=True,
                    max_rounds=2,
                    min_consensus=0.7
                )
                
                self.console.print(f"[green]✅ Completed {i}/{len(ideas)}[/green]")
            
            except Exception as e:
                self.console.print(f"[red]❌ Failed: {e}[/red]")
        
        self.console.print(f"\n[bold green]✅ Batch processing complete![/bold green]\n")
    
    async def run_tests(self):
        """Run system tests"""
        self.console.print("\n[bold cyan]🧪 Running System Tests[/bold cyan]\n")
        
        try:
            # Test imports
            self.console.print("[yellow]Testing imports...[/yellow]")
            from src.langraph_pipeline.integrated_workflow import run_integrated_pipeline
            from src.agents.sequential_orchestrator import create_orchestrator
            from src.utils.ollama_client import get_ollama_client
            self.console.print("[green]✅ Imports OK[/green]\n")
            
            # Test Ollama
            self.console.print("[yellow]Testing Ollama...[/yellow]")
            client = get_ollama_client()
            response = await client.generate("qwen2.5-coder:7b", "Say 'test'")
            if response:
                self.console.print("[green]✅ Ollama OK[/green]\n")
            else:
                self.console.print("[red]❌ Ollama failed[/red]\n")
            
            # Test orchestrator
            self.console.print("[yellow]Testing orchestrator...[/yellow]")
            orchestrator = create_orchestrator()
            self.console.print("[green]✅ Orchestrator OK[/green]\n")
            
            self.console.print("[bold green]✅ All tests passed![/bold green]\n")
        
        except Exception as e:
            self.console.print(f"\n[red]❌ Tests failed: {e}[/red]\n")
    
    def configure_settings(self):
        """Configure system settings"""
        self.console.print("\n[bold cyan]⚙️  Configuration[/bold cyan]\n")
        
        # GitHub token
        if Confirm.ask("Configure GitHub token?", default=False):
            token = Prompt.ask("GitHub Personal Access Token", password=True)
            
            if token:
                env_path = Path(".env")
                
                if env_path.exists():
                    content = env_path.read_text()
                    if "GITHUB_TOKEN" in content:
                        # Update existing
                        lines = content.splitlines()
                        new_lines = []
                        for line in lines:
                            if line.startswith("GITHUB_TOKEN="):
                                new_lines.append(f"GITHUB_TOKEN={token}")
                            else:
                                new_lines.append(line)
                        env_path.write_text("\n".join(new_lines))
                    else:
                        # Append
                        with env_path.open("a") as f:
                            f.write(f"\nGITHUB_TOKEN={token}\n")
                else:
                    # Create new
                    env_path.write_text(f"GITHUB_TOKEN={token}\n")
                
                self.console.print("[green]✅ GitHub token saved to .env[/green]")
        
        self.console.print()
    
    async def interactive_loop(self):
        """Main interactive loop"""
        self.show_banner()
        
        # Check system on startup
        ollama_ok = await self.check_system_status()
        
        if not ollama_ok:
            self.console.print("[red]⚠️  Ollama not running. Start it with: ollama serve[/red]\n")
            if not Confirm.ask("Continue anyway?", default=False):
                return
        
        while True:
            try:
                self.show_main_menu()
                
                choice = Prompt.ask("Choose option").strip().lower()
                
                if choice in ["0", "exit", "quit", "q"]:
                    self.console.print("\n[cyan]👋 Goodbye![/cyan]\n")
                    break
                
                elif choice in ["1", "generate"]:
                    await self.generate_project()
                
                elif choice in ["2", "fix"]:
                    await self.fix_project()
                
                elif choice in ["3", "research"]:
                    await self.research_only()
                
                elif choice in ["4", "debate"]:
                    await self.debate_mode()
                
                elif choice in ["5", "batch"]:
                    await self.batch_process()
                
                elif choice in ["6", "status"]:
                    await self.check_system_status()
                
                elif choice in ["7", "config"]:
                    self.configure_settings()
                
                elif choice in ["8", "test"]:
                    await self.run_tests()
                
                else:
                    self.console.print(f"[red]❌ Invalid option: {choice}[/red]\n")
                
                # Pause before showing menu again
                input("\nPress Enter to continue...")
                self.console.clear()
            
            except KeyboardInterrupt:
                self.console.print("\n[cyan]👋 Goodbye![/cyan]\n")
                break
            except Exception as e:
                self.console.print(f"\n[red]❌ Error: {e}[/red]\n")
                import traceback
                self.console.print(f"[dim]{traceback.format_exc()}[/dim]\n")


async def main():
    """Main entry point"""
    cli = AutoGITIntegratedCLI()
    await cli.interactive_loop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[cyan]👋 Goodbye![/cyan]\n")
        sys.exit(0)
