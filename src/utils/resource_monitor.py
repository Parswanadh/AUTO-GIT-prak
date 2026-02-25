#!/usr/bin/env python3
"""
Resource Monitor for Auto-GIT
Monitors CPU, RAM, GPU VRAM to prevent crashes
"""

import psutil
import time
import threading
from typing import Optional, Dict, Any
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich import box

console = Console()


class ResourceMonitor:
    """Monitor system resources in real-time"""
    
    def __init__(self, check_interval: float = 2.0):
        self.check_interval = check_interval
        self.monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.stats = {
            "cpu_percent": 0.0,
            "ram_percent": 0.0,
            "ram_used_gb": 0.0,
            "ram_total_gb": 0.0,
            "gpu_vram_used_mb": 0.0,
            "gpu_vram_total_mb": 0.0,
            "gpu_utilization": 0.0,
        }
        self.warnings = []
    
    def get_gpu_stats(self) -> Dict[str, float]:
        """Get GPU statistics if available"""
        try:
            import gpustat
            gpu_stats = gpustat.GPUStatCollection.new_query()
            
            if gpu_stats and len(gpu_stats.gpus) > 0:
                gpu = gpu_stats.gpus[0]  # First GPU
                return {
                    "vram_used_mb": gpu.memory_used,
                    "vram_total_mb": gpu.memory_total,
                    "utilization": gpu.utilization,
                }
        except ImportError:
            # Try nvidia-ml-py
            try:
                import pynvml
                pynvml.nvmlInit()
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                
                info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                
                pynvml.nvmlShutdown()
                
                return {
                    "vram_used_mb": info.used / 1024 / 1024,
                    "vram_total_mb": info.total / 1024 / 1024,
                    "utilization": util.gpu,
                }
            except Exception:
                pass
        
        return {
            "vram_used_mb": 0.0,
            "vram_total_mb": 0.0,
            "utilization": 0.0,
        }
    
    def update_stats(self):
        """Update all resource statistics"""
        # CPU
        self.stats["cpu_percent"] = psutil.cpu_percent(interval=0.1)
        
        # RAM
        mem = psutil.virtual_memory()
        self.stats["ram_percent"] = mem.percent
        self.stats["ram_used_gb"] = mem.used / 1024 / 1024 / 1024
        self.stats["ram_total_gb"] = mem.total / 1024 / 1024 / 1024
        
        # GPU
        gpu_stats = self.get_gpu_stats()
        self.stats["gpu_vram_used_mb"] = gpu_stats["vram_used_mb"]
        self.stats["gpu_vram_total_mb"] = gpu_stats["vram_total_mb"]
        self.stats["gpu_utilization"] = gpu_stats["utilization"]
        
        # Check for warnings
        self.warnings = []
        
        if self.stats["ram_percent"] > 90:
            self.warnings.append("⚠️  RAM usage > 90%")
        
        if self.stats["gpu_vram_total_mb"] > 0:
            vram_percent = (self.stats["gpu_vram_used_mb"] / self.stats["gpu_vram_total_mb"]) * 100
            if vram_percent > 90:
                self.warnings.append("⚠️  GPU VRAM > 90%")
    
    def _monitor_loop(self):
        """Background monitoring loop"""
        while self.monitoring:
            self.update_stats()
            time.sleep(self.check_interval)
    
    def start(self):
        """Start monitoring in background"""
        if not self.monitoring:
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            console.print("[green]✓ Resource monitoring started[/green]")
    
    def stop(self):
        """Stop monitoring"""
        if self.monitoring:
            self.monitoring = False
            if self.monitor_thread:
                self.monitor_thread.join(timeout=5)
            console.print("[dim]Resource monitoring stopped[/dim]")
    
    def display(self):
        """Display current stats in a table"""
        self.update_stats()
        
        table = Table(title="📊 System Resources", box=box.ROUNDED, border_style="cyan")
        table.add_column("Resource", style="cyan")
        table.add_column("Usage", style="white")
        table.add_column("Status", style="green")
        
        # CPU
        cpu_status = "✓" if self.stats["cpu_percent"] < 80 else "⚠️"
        table.add_row(
            "CPU",
            f"{self.stats['cpu_percent']:.1f}%",
            cpu_status
        )
        
        # RAM
        ram_status = "✓" if self.stats["ram_percent"] < 80 else "⚠️"
        table.add_row(
            "RAM",
            f"{self.stats['ram_used_gb']:.1f} / {self.stats['ram_total_gb']:.1f} GB ({self.stats['ram_percent']:.1f}%)",
            ram_status
        )
        
        # GPU VRAM
        if self.stats["gpu_vram_total_mb"] > 0:
            vram_gb_used = self.stats["gpu_vram_used_mb"] / 1024
            vram_gb_total = self.stats["gpu_vram_total_mb"] / 1024
            vram_percent = (self.stats["gpu_vram_used_mb"] / self.stats["gpu_vram_total_mb"]) * 100
            vram_status = "✓" if vram_percent < 80 else "⚠️"
            
            table.add_row(
                "GPU VRAM",
                f"{vram_gb_used:.1f} / {vram_gb_total:.1f} GB ({vram_percent:.1f}%)",
                vram_status
            )
            
            # GPU Utilization
            gpu_util_status = "✓" if self.stats["gpu_utilization"] < 95 else "⚠️"
            table.add_row(
                "GPU Util",
                f"{self.stats['gpu_utilization']:.1f}%",
                gpu_util_status
            )
        
        console.print("\n")
        console.print(table)
        
        # Show warnings
        if self.warnings:
            console.print("\n[bold red]Warnings:[/bold red]")
            for warning in self.warnings:
                console.print(f"  {warning}")
        
        console.print("\n")
    
    def check_safe_to_proceed(self) -> bool:
        """Check if it's safe to proceed with heavy operations"""
        self.update_stats()
        
        # Check RAM
        if self.stats["ram_percent"] > 85:
            console.print("[red]⚠️  RAM usage too high (>85%). Wait before proceeding.[/red]")
            return False
        
        # Check GPU VRAM
        if self.stats["gpu_vram_total_mb"] > 0:
            vram_percent = (self.stats["gpu_vram_used_mb"] / self.stats["gpu_vram_total_mb"]) * 100
            if vram_percent > 85:
                console.print("[red]⚠️  GPU VRAM usage too high (>85%). Wait before proceeding.[/red]")
                return False
        
        return True
    
    def wait_for_resources(self, timeout: int = 60):
        """Wait for resources to become available"""
        console.print("[yellow]Waiting for resources to become available...[/yellow]")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.check_safe_to_proceed():
                console.print("[green]✓ Resources available[/green]")
                return True
            time.sleep(2)
        
        console.print("[red]⚠️  Timeout waiting for resources[/red]")
        return False


# Global monitor instance
_monitor: Optional[ResourceMonitor] = None


def get_monitor() -> ResourceMonitor:
    """Get or create global monitor instance"""
    global _monitor
    if _monitor is None:
        _monitor = ResourceMonitor()
    return _monitor


def start_monitoring():
    """Start global monitoring"""
    monitor = get_monitor()
    monitor.start()


def stop_monitoring():
    """Stop global monitoring"""
    monitor = get_monitor()
    monitor.stop()


def display_resources():
    """Display current resources"""
    monitor = get_monitor()
    monitor.display()


def check_resources() -> bool:
    """Check if resources are safe"""
    monitor = get_monitor()
    return monitor.check_safe_to_proceed()


if __name__ == "__main__":
    # Test monitoring
    monitor = ResourceMonitor()
    monitor.start()
    
    try:
        for i in range(10):
            console.print(f"\n[bold]Check {i+1}/10[/bold]")
            monitor.display()
            time.sleep(3)
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped by user[/yellow]")
    finally:
        monitor.stop()
