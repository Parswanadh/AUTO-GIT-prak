#!/usr/bin/env python3
"""
Claude Code-style CLI for Auto-GIT
Replicates Claude Code's UX with MCP support and sequential thinking
"""

import asyncio
import sys
from typing import Optional, List, Dict, Any
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.markdown import Markdown
from rich.table import Table
from rich.live import Live
from rich.spinner import Spinner
from rich import box
from rich.syntax import Syntax
from rich.tree import Tree
import json

console = Console()


class SequentialThinking:
    """
    Sequential thinking system for planning and reasoning
    Inspired by o1-style reasoning
    """
    
    def __init__(self, model="qwen2.5-coder:7b"):
        self.model = model
        self.thinking_history = []
        self.visible = True
    
    async def think(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute sequential thinking before taking action
        
        Returns:
            {
                "reasoning": "...",  # Thinking process
                "plan": ["step1", "step2", ...],  # Action plan
                "confidence": 0.85,  # Confidence score
                "decision": "..."  # Final decision
            }
        """
        thinking_prompt = f"""
<thinking>
You are planning how to respond to the user's request.

Context:
{json.dumps(context, indent=2)}

User Request:
{prompt}

Think step-by-step:
1. What is the user asking for?
2. What information do I need?
3. What tools should I use?
4. What's the best sequence of actions?
5. What could go wrong?
6. What's my plan?

Respond in JSON format:
{{
    "reasoning": "Your detailed thinking process",
    "plan": ["step1", "step2", "step3"],
    "confidence": 0.0-1.0,
    "decision": "Your final decision"
}}
</thinking>
"""
        
        # Show thinking spinner if visible
        if self.visible:
            with console.status("[dim italic]Thinking...[/dim italic]", spinner="dots"):
                try:
                    from src.utils.model_manager import get_fallback_llm
                    from langchain_core.messages import HumanMessage
                    llm = get_fallback_llm("fast")
                    response = await llm.ainvoke([HumanMessage(content=thinking_prompt)])
                    raw = response.content.strip()
                    # Try to parse JSON from response
                    import re as _re_think
                    raw = _re_think.sub(r"^```[a-z]*\n?", "", raw)
                    raw = _re_think.sub(r"\n?```$", "", raw.strip())
                    result = json.loads(raw)
                except Exception as e:
                    # Fallback to basic plan
                    result = {
                        "reasoning": f"Planning response to: {prompt[:100]}",
                        "plan": ["Analyze request", "Execute appropriate action", "Return results"],
                        "confidence": 0.7,
                        "decision": "Execute user request"
                    }
        else:
            result = {
                "reasoning": "Internal reasoning hidden",
                "plan": ["Execute request"],
                "confidence": 0.9,
                "decision": "Proceed"
            }
        
        self.thinking_history.append(result)
        
        if self.visible:
            self._display_thinking(result)
        
        return result
    
    def _display_thinking(self, result: Dict[str, Any]):
        """Display thinking process to user"""
        console.print("\n[dim italic]💭 Thinking Process:[/dim italic]")
        console.print(f"[dim]{result['reasoning']}[/dim]\n")
        
        console.print("[dim italic]📋 Plan:[/dim italic]")
        for i, step in enumerate(result['plan'], 1):
            console.print(f"[dim]{i}. {step}[/dim]")
        
        console.print(f"\n[dim italic]📊 Confidence: {result['confidence']:.0%}[/dim italic]")
        console.print(f"[dim italic]✓ Decision: {result['decision']}[/dim italic]\n")
    
    def toggle_visibility(self):
        """Toggle thinking visibility (Ctrl+O in Claude Code)"""
        self.visible = not self.visible
        status = "visible" if self.visible else "hidden"
        console.print(f"\n[dim]Thinking is now {status}[/dim]\n")


class MCPServerManager:
    """
    Model Context Protocol (MCP) Server Manager
    Manages multiple MCP servers for tools, resources, and prompts
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path("config/.mcp.json")
        self.servers = {}
        self.tools = {}
        self.resources = {}
        self.prompts = {}
    
    async def load_config(self):
        """Load MCP server configuration"""
        if not self.config_path.exists():
            # Create default config
            default_config = {
                "mcpServers": {
                    "filesystem": {
                        "command": "python",
                        "args": ["-m", "mcp_server_filesystem"],
                        "description": "Read, write, and manage files"
                    },
                    "web-search": {
                        "command": "python",
                        "args": ["-m", "mcp_server_web_search"],
                        "description": "Search the web (DuckDuckGo, SearXNG)"
                    },
                    "git": {
                        "command": "python",
                        "args": ["-m", "mcp_server_git"],
                        "description": "Git operations and GitHub integration"
                    }
                }
            }
            
            self.config_path.parent.mkdir(exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(default_config, f, indent=2)
            
            console.print(f"[dim]Created default MCP config at {self.config_path}[/dim]\n")
        
        with open(self.config_path) as f:
            config = json.load(f)
        
        return config.get("mcpServers", {})
    
    async def initialize_servers(self):
        """Initialize all MCP servers via subprocess + JSON-RPC 2.0"""
        server_configs = await self.load_config()
        
        console.print("[cyan]🔌 Initializing MCP Servers...[/cyan]\n")
        
        for name, config in server_configs.items():
            try:
                import subprocess
                import shutil
                
                cmd = config.get("command", "python")
                args_list = config.get("args", [])
                full_cmd = [cmd] + args_list
                
                # Check if the command exists
                if not shutil.which(cmd):
                    console.print(f"  ✗ {name}: command '{cmd}' not found")
                    self.servers[name] = {
                        "config": config,
                        "status": "error",
                        "error": f"Command '{cmd}' not found",
                        "process": None,
                        "tools": [],
                    }
                    continue
                
                # Start MCP server as a subprocess with stdio transport
                proc = subprocess.Popen(
                    full_cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                )
                
                # Send JSON-RPC initialize request
                init_request = json.dumps({
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "auto-git", "version": "1.0.0"},
                    },
                })
                
                try:
                    proc.stdin.write(init_request + "\n")
                    proc.stdin.flush()
                    
                    # Read response with timeout
                    import select
                    import platform
                    if platform.system() == "Windows":
                        # Windows doesn't support select on pipes, use threading
                        import threading
                        response_line = [None]
                        def _read():
                            try:
                                response_line[0] = proc.stdout.readline()
                            except Exception:
                                pass
                        t = threading.Thread(target=_read, daemon=True)
                        t.start()
                        t.join(timeout=5)
                        resp_text = response_line[0]
                    else:
                        ready, _, _ = select.select([proc.stdout], [], [], 5)
                        resp_text = proc.stdout.readline() if ready else None
                    
                    if resp_text:
                        resp = json.loads(resp_text.strip())
                        server_info = resp.get("result", {}).get("serverInfo", {})
                        self.servers[name] = {
                            "config": config,
                            "status": "ready",
                            "process": proc,
                            "server_info": server_info,
                            "tools": [],
                        }
                        console.print(f"  ✓ {name}: {config.get('description', 'N/A')} [dim](pid={proc.pid})[/dim]")
                    else:
                        # Server didn't respond to initialize — might not support MCP
                        proc.terminate()
                        self.servers[name] = {
                            "config": config,
                            "status": "ready",  # mark as ready anyway — mock tools
                            "process": None,
                            "tools": [],
                        }
                        console.print(f"  ⚠ {name}: no MCP response (mock mode)")
                        
                except Exception as init_err:
                    proc.terminate()
                    self.servers[name] = {
                        "config": config,
                        "status": "ready",
                        "process": None,
                        "tools": [],
                    }
                    console.print(f"  ⚠ {name}: init failed ({init_err}), running in mock mode")
                    
            except Exception as e:
                self.servers[name] = {
                    "config": config,
                    "status": "error",
                    "error": str(e),
                    "process": None,
                    "tools": [],
                }
                console.print(f"  ✗ {name}: {e}")
        
        # Discover tools from active servers
        await self._discover_all_tools()
        console.print()
    
    async def _discover_all_tools(self):
        """Discover tools from all active MCP servers via JSON-RPC."""
        for server_name, server_info in self.servers.items():
            proc = server_info.get("process")
            if proc and proc.poll() is None:
                try:
                    # Send tools/list request
                    request = json.dumps({
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/list",
                        "params": {},
                    })
                    proc.stdin.write(request + "\n")
                    proc.stdin.flush()
                    
                    import threading
                    response_line = [None]
                    def _read():
                        try:
                            response_line[0] = proc.stdout.readline()
                        except Exception:
                            pass
                    t = threading.Thread(target=_read, daemon=True)
                    t.start()
                    t.join(timeout=5)
                    
                    if response_line[0]:
                        resp = json.loads(response_line[0].strip())
                        tools = resp.get("result", {}).get("tools", [])
                        for tool in tools:
                            tool["server"] = server_name
                        server_info["tools"] = tools
                        self.tools.update({t["name"]: t for t in tools})
                except Exception as e:
                    pass  # Discovery failed, will use mock tools
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List all available tools from MCP servers"""
        all_tools = []
        
        for server_name, server_info in self.servers.items():
            # Use discovered tools if available
            discovered = server_info.get("tools", [])
            if discovered:
                all_tools.extend(discovered)
                continue
            
            # Fallback: provide built-in tool definitions based on server type
            if server_name == "filesystem":
                all_tools.extend([
                    {"name": "read_file", "server": server_name, "description": "Read file contents",
                     "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}}},
                    {"name": "write_file", "server": server_name, "description": "Write file contents",
                     "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}}},
                    {"name": "list_directory", "server": server_name, "description": "List directory contents",
                     "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}}},
                ])
            elif server_name == "web-search":
                all_tools.extend([
                    {"name": "web_search", "server": server_name, "description": "Search the web",
                     "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}}},
                    {"name": "fetch_url", "server": server_name, "description": "Fetch URL content",
                     "inputSchema": {"type": "object", "properties": {"url": {"type": "string"}}}},
                ])
            elif server_name == "git":
                all_tools.extend([
                    {"name": "git_status", "server": server_name, "description": "Get git status",
                     "inputSchema": {"type": "object", "properties": {}}},
                    {"name": "git_commit", "server": server_name, "description": "Create git commit",
                     "inputSchema": {"type": "object", "properties": {"message": {"type": "string"}}}},
                    {"name": "github_create_repo", "server": server_name, "description": "Create GitHub repository",
                     "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}, "description": {"type": "string"}}}},
                ])
        
        return all_tools
    
    async def execute_tool(self, tool_name: str, params: Dict[str, Any]) -> Any:
        """Execute a tool via MCP server using JSON-RPC 2.0"""
        # Find which server has this tool
        target_server = None
        for server_name, server_info in self.servers.items():
            server_tools = [t.get("name", "") for t in server_info.get("tools", [])]
            if tool_name in server_tools:
                target_server = server_name
                break
        
        # Also check built-in tool mappings
        if not target_server:
            tool_server_map = {
                "read_file": "filesystem", "write_file": "filesystem", "list_directory": "filesystem",
                "web_search": "web-search", "fetch_url": "web-search",
                "git_status": "git", "git_commit": "git", "github_create_repo": "git",
            }
            target_server = tool_server_map.get(tool_name)
        
        if not target_server or target_server not in self.servers:
            return {"status": "error", "error": f"Tool '{tool_name}' not found in any server"}
        
        server_info = self.servers[target_server]
        proc = server_info.get("process")
        
        if proc and proc.poll() is None:
            try:
                # Send JSON-RPC tool call
                request = json.dumps({
                    "jsonrpc": "2.0",
                    "id": 100,
                    "method": "tools/call",
                    "params": {"name": tool_name, "arguments": params},
                })
                proc.stdin.write(request + "\n")
                proc.stdin.flush()
                
                import threading
                response_line = [None]
                def _read():
                    try:
                        response_line[0] = proc.stdout.readline()
                    except Exception:
                        pass
                t = threading.Thread(target=_read, daemon=True)
                t.start()
                t.join(timeout=30)
                
                if response_line[0]:
                    resp = json.loads(response_line[0].strip())
                    if "error" in resp:
                        return {"status": "error", "error": resp["error"]}
                    return {"status": "success", "result": resp.get("result", {})}
                else:
                    return {"status": "error", "error": "Server timed out"}
            except Exception as e:
                return {"status": "error", "error": str(e)}
        
        # Fallback: execute built-in implementation
        return await self._execute_builtin(tool_name, params)
    
    async def _execute_builtin(self, tool_name: str, params: Dict[str, Any]) -> Any:
        """Built-in fallback implementations for common tools."""
        import os
        
        if tool_name == "read_file":
            path = params.get("path", "")
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                return {"status": "success", "result": content}
            except Exception as e:
                return {"status": "error", "error": str(e)}
        
        elif tool_name == "write_file":
            path = params.get("path", "")
            content = params.get("content", "")
            try:
                os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                return {"status": "success", "result": f"Written {len(content)} bytes to {path}"}
            except Exception as e:
                return {"status": "error", "error": str(e)}
        
        elif tool_name == "list_directory":
            path = params.get("path", ".")
            try:
                entries = os.listdir(path)
                return {"status": "success", "result": entries}
            except Exception as e:
                return {"status": "error", "error": str(e)}
        
        elif tool_name == "web_search":
            query = params.get("query", "")
            try:
                from src.utils.web_search import web_search
                results = web_search(query)
                return {"status": "success", "result": results}
            except Exception as e:
                return {"status": "error", "error": str(e)}
        
        elif tool_name == "git_status":
            import subprocess
            try:
                result = subprocess.run(["git", "status", "--short"], capture_output=True, text=True)
                return {"status": "success", "result": result.stdout}
            except Exception as e:
                return {"status": "error", "error": str(e)}
        
        return {"status": "error", "error": f"No built-in implementation for '{tool_name}'"}
    
    def display_servers(self):
        """Display available MCP servers"""
        table = Table(title="🔌 MCP Servers", box=box.ROUNDED, border_style="cyan")
        table.add_column("Server", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Description", style="white")
        
        for name, info in self.servers.items():
            table.add_row(
                name,
                "✓ Ready" if info["status"] == "ready" else "✗ Error",
                info["config"].get("description", "N/A")
            )
        
        console.print("\n")
        console.print(table)
        console.print("\n")


class SubAgent:
    """
    Sub-agent system for parallel/background tasks
    Inspired by Claude Code's agent management
    """
    
    def __init__(self, name: str, system_prompt: str, tools: Optional[List[str]] = None):
        self.name = name
        self.system_prompt = system_prompt
        self.tools = tools or []
        self.status = "idle"
        self.context = {}
    
    async def run(self, task: str, foreground: bool = True) -> Dict[str, Any]:
        """
        Run agent task
        
        Args:
            task: Task description
            foreground: If True, block until complete. If False, run in background.
        """
        self.status = "running"
        
        if foreground:
            console.print(f"\n[cyan]🤖 {self.name} is working...[/cyan]\n")
            # Execute task
            result = await self._execute(task)
            self.status = "completed"
            return result
        else:
            # Background execution
            console.print(f"\n[dim]🤖 {self.name} started in background[/dim]\n")
            asyncio.create_task(self._execute_background(task))
            return {"status": "background", "agent": self.name}
    
    async def _execute(self, task: str) -> Dict[str, Any]:
        """Execute agent task (placeholder)"""
        await asyncio.sleep(2)  # Simulate work
        return {"status": "success", "result": f"{self.name} completed: {task}"}
    
    async def _execute_background(self, task: str):
        """Execute task in background"""
        result = await self._execute(task)
        console.print(f"\n[dim]✓ {self.name} completed background task[/dim]\n")


class ClaudeCodeCLI:
    """
    Main Claude Code-style CLI
    """
    
    LOGO = """[bold cyan]
   ___         __           _______ ______
  / _ | __ __ / /_ ___     / ___/  /  ___/
 / __ |/ // // __// _ \   / (_ / / / /    
/_/ |_|\_,_/ \__/ \___/   \___//_/ /_/     
                                           
[/bold cyan][dim]Claude Code Edition | MCP Enabled | Sequential Thinking[/dim]
"""
    
    def __init__(self):
        self.thinking = SequentialThinking()
        self.mcp = MCPServerManager()
        self.agents = {}
        self.session_history = []
        self.mode = "normal"  # normal, plan, auto-accept
    
    async def initialize(self):
        """Initialize CLI components"""
        await self.mcp.initialize_servers()
    
    def show_banner(self):
        """Display welcome banner"""
        console.clear()
        console.print(self.LOGO)
        console.print(Panel.fit(
            "[bold]Welcome to Auto-GIT Claude Code Edition![/bold]\n\n"
            "Commands:\n"
            "  /help       - Show all commands\n"
            "  /plan       - Enter plan mode (read-only analysis)\n"
            "  /agents     - Manage sub-agents\n"
            "  /servers    - View MCP servers\n"
            "  /thinking   - Toggle thinking visibility (Ctrl+O)\n"
            "  /exit       - Exit CLI\n\n"
            "Natural language: Just type your request!",
            border_style="cyan"
        ))
        console.print()
    
    async def handle_command(self, user_input: str):
        """Handle slash commands"""
        parts = user_input.split()
        command = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        
        if command == "/help":
            self.show_help()
        
        elif command == "/plan":
            self.mode = "plan"
            console.print("\n[yellow]📋 Entered PLAN mode - read-only analysis[/yellow]\n")
        
        elif command == "/normal":
            self.mode = "normal"
            console.print("\n[green]✓ Exited PLAN mode[/green]\n")
        
        elif command == "/agents":
            await self.manage_agents(args)
        
        elif command == "/servers":
            self.mcp.display_servers()
        
        elif command == "/thinking":
            self.thinking.toggle_visibility()
        
        elif command == "/exit" or command == "/quit":
            return "exit"
        
        else:
            console.print(f"[red]Unknown command: {command}[/red]")
            console.print("[dim]Type /help for available commands[/dim]\n")
    
    def show_help(self):
        """Show help information"""
        help_table = Table(title="📚 Commands", box=box.ROUNDED)
        help_table.add_column("Command", style="cyan")
        help_table.add_column("Description", style="white")
        
        commands = [
            ("/help", "Show this help message"),
            ("/plan", "Enter plan mode (read-only analysis first)"),
            ("/normal", "Exit plan mode, return to normal"),
            ("/agents", "List and manage sub-agents"),
            ("/agents create <name>", "Create new sub-agent"),
            ("/servers", "View MCP servers and tools"),
            ("/thinking", "Toggle thinking visibility (Ctrl+O)"),
            ("/exit", "Exit the CLI"),
            ("generate: <idea>", "Generate project from idea"),
            ("research: <topic>", "Research a topic"),
            ("@file.py", "Reference a file in your prompt")
        ]
        
        for cmd, desc in commands:
            help_table.add_row(cmd, desc)
        
        console.print("\n")
        console.print(help_table)
        console.print("\n")
    
    async def manage_agents(self, args: List[str]):
        """Manage sub-agents"""
        if not args:
            # List agents
            if not self.agents:
                console.print("\n[dim]No agents running[/dim]\n")
            else:
                table = Table(title="🤖 Sub-Agents", box=box.ROUNDED)
                table.add_column("Name", style="cyan")
                table.add_column("Status", style="green")
                table.add_column("Tools", style="white")
                
                for name, agent in self.agents.items():
                    table.add_row(name, agent.status, ", ".join(agent.tools))
                
                console.print("\n")
                console.print(table)
                console.print("\n")
        
        elif args[0] == "create":
            if len(args) < 2:
                console.print("[red]Usage: /agents create <name>[/red]\n")
                return
            
            name = args[1]
            system_prompt = Prompt.ask(f"System prompt for {name}")
            
            agent = SubAgent(name, system_prompt)
            self.agents[name] = agent
            
            console.print(f"\n[green]✓ Created agent: {name}[/green]\n")
    
    async def handle_natural_language(self, user_input: str):
        """Handle natural language input"""
        # Extract file references (@file.py)
        file_refs = []
        words = user_input.split()
        for word in words:
            if word.startswith('@'):
                file_refs.append(word[1:])
        
        # Build context
        context = {
            "mode": self.mode,
            "file_refs": file_refs,
            "available_tools": await self.mcp.list_tools(),
            "agents": list(self.agents.keys())
        }
        
        # Sequential thinking
        thinking_result = await self.thinking.think(user_input, context)
        
        # Execute based on plan
        if self.mode == "plan":
            console.print("\n[yellow]📋 PLAN MODE: Analysis only, no changes will be made[/yellow]\n")
            # Show what WOULD happen
            console.print("[dim]Would execute:[/dim]")
            for step in thinking_result['plan']:
                console.print(f"  [dim]• {step}[/dim]")
            console.print()
            
            if Confirm.ask("Execute this plan?"):
                self.mode = "normal"
                await self._execute_plan(thinking_result['plan'], user_input)
            else:
                console.print("\n[dim]Plan cancelled[/dim]\n")
        else:
            # Normal mode - execute directly
            await self._execute_plan(thinking_result['plan'], user_input)
    
    async def _execute_plan(self, plan: List[str], user_input: str):
        """Execute the planned steps"""
        console.print("\n[green]🚀 Executing...[/green]\n")
        
        # Check if this is a generate request
        if "generate" in user_input.lower() or "create" in user_input.lower():
            from src.langraph_pipeline.workflow_enhanced import run_auto_git_pipeline
            
            # Extract the idea
            idea = user_input.replace("generate:", "").replace("create:", "").strip()
            
            # Run pipeline
            try:
                result = await run_auto_git_pipeline(
                    idea=idea,
                    use_web_search=True,
                    max_debate_rounds=2,
                    auto_publish=False
                )
                
                console.print("\n[green]✅ Pipeline completed![/green]\n")
                
                # Show results
                if result.get("final_code"):
                    console.print("[bold]Generated Code:[/bold]\n")
                    syntax = Syntax(result["final_code"][:500], "python", theme="monokai")
                    console.print(syntax)
                    console.print("[dim]... (truncated)[/dim]\n")
            
            except Exception as e:
                console.print(f"\n[red]❌ Error: {e}[/red]\n")
        
        else:
            # Route general requests through sequential thinking → LLM
            console.print("[dim]Analyzing request...[/dim]\n")
            try:
                from src.utils.model_manager import get_fallback_llm
                llm = get_fallback_llm("balanced")
                response = llm.invoke(
                    f"You are a helpful coding assistant. The user said:\n\n{user_input}\n\n"
                    "Respond concisely and helpfully. If they're asking about code, provide examples."
                )
                content = response.content if hasattr(response, "content") else str(response)
                console.print(Markdown(content))
            except Exception as e:
                console.print(f"[yellow]Could not process request: {e}[/yellow]")
    
    async def run(self):
        """Main CLI loop"""
        await self.initialize()
        self.show_banner()
        
        while True:
            try:
                # Prompt
                mode_indicator = "📋" if self.mode == "plan" else "💻"
                user_input = Prompt.ask(f"\n{mode_indicator}").strip()
                
                if not user_input:
                    continue
                
                # Handle slash commands
                if user_input.startswith('/'):
                    result = await self.handle_command(user_input)
                    if result == "exit":
                        break
                
                # Handle natural language
                else:
                    await self.handle_natural_language(user_input)
            
            except KeyboardInterrupt:
                console.print("\n[dim]Use /exit to quit[/dim]\n")
                continue
            
            except EOFError:
                break
            
            except Exception as e:
                console.print(f"\n[red]❌ Error: {e}[/red]\n")
                import traceback
                console.print(f"[dim]{traceback.format_exc()}[/dim]\n")
        
        console.print("\n[cyan]👋 Goodbye![/cyan]\n")


async def main():
    """Entry point"""
    cli = ClaudeCodeCLI()
    await cli.run()


if __name__ == "__main__":
    asyncio.run(main())
