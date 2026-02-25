#!/usr/bin/env python3
"""Quick test of model manager setup without loading models"""

from src.utils.model_manager import ModelManager
from rich.console import Console

console = Console()

console.print("\n[bold cyan]Testing Model Manager Setup[/bold cyan]\n")

# Create manager
manager = ModelManager()

# Show available profiles
console.print("[bold]Available Model Profiles:[/bold]\n")
for profile, config in manager.MODEL_CONFIGS.items():
    console.print(f"  [cyan]{profile}[/cyan]:")
    console.print(f"    Model: {config['model']}")
    console.print(f"    Use: {config['use_case']}")
    console.print()

# Show current state
console.print("[bold]Current State:[/bold]")
info = manager.get_current_info()
for key, value in info.items():
    console.print(f"  {key}: {value}")

console.print("\n[green]✓ Model manager initialized successfully[/green]")
console.print("[yellow]Note: Models will only load when actually used in pipeline[/yellow]\n")
