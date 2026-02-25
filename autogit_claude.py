#!/usr/bin/env python3
"""
Auto-GIT Claude Code Edition
Main entry point for the enhanced CLI
"""

import sys
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.cli.claude_code_cli import ClaudeCodeCLI


def main():
    """Main entry point"""
    try:
        cli = ClaudeCodeCLI()
        asyncio.run(cli.run())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
