#!/usr/bin/env python3
"""
ai - Unified AI CLI tool

Dispatches prompts to different AI CLI tools based on model alias.

Usage:
    ai <model> "prompt"          # Basic usage
    ai "prompt"                  # Use default model (if set)
    ai json [model] "prompt"     # JSON output (or: ai <model> json "prompt")
    ai cmd [model] "prompt"      # Return only terminal command
    ai run [model] "prompt"      # Generate command, confirm, execute
    ai <model> run "prompt"      # Same (flags work in any position)
    ai run -y "prompt"           # Skip confirmation (auto-execute)
    ai yolo [model] "prompt"     # Auto-approve file edits
    ai init                      # Initialize (detect tools)
    ai list                      # List available models
    ai default [alias]           # Get/set default model
    ai default --clear           # Remove default model
    ai serve [port]              # Start HTTP server (default: 8765)
    cat file.txt | ai <model>    # Stdin input

Library usage:
    from ai_cli import AIClient
    client = AIClient()
    response = client.call("sonnet", "Hello!")
"""

import os
from pathlib import Path

# Load .env file from script directory (for API keys)
# Note: resolve() first to follow symlinks, then get parent
SCRIPT_DIR = Path(__file__).resolve().parent
try:
    from dotenv import load_dotenv
    load_dotenv(SCRIPT_DIR / ".env")
except ImportError:
    # Fallback: manual .env parsing (no dependency needed)
    env_file = SCRIPT_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def main():
    """Entry point for CLI."""
    from ai_cli.cli import main as cli_main
    cli_main()


if __name__ == "__main__":
    main()
