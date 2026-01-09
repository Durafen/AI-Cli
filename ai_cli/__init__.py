"""
ai-cli - Unified AI CLI tool and library.

Dispatches prompts to multiple AI backends (Claude, Codex, Gemini, Qwen, Ollama, OpenRouter)
via short model aliases.

Library usage:
    from ai_cli import AIClient

    client = AIClient()
    response = client.call("sonnet", "Explain Python's GIL")

    # With options
    response = client.call("opus", "List 3 colors", json_mode=True)

    # List available models
    for alias, (provider, model) in client.list_models().items():
        print(f"{alias} -> {provider}:{model}")

CLI usage:
    ai <model> "prompt"          # Basic usage
    ai "prompt"                  # Use default model (if set)
    ai init                      # Initialize (detect tools)
    ai list                      # List available models
    ai serve                     # Start HTTP server for cross-language access
"""

import os
from pathlib import Path


def _load_dotenv() -> None:
    """Load .env file from package directory or current working directory."""
    # Try package directory first (where ai_cli is installed/located)
    pkg_dir = Path(__file__).resolve().parent.parent
    env_locations = [
        pkg_dir / ".env",           # Next to ai_cli package
        Path.cwd() / ".env",        # Current working directory
    ]

    for env_file in env_locations:
        if env_file.exists():
            try:
                from dotenv import load_dotenv
                load_dotenv(env_file)
            except ImportError:
                # Fallback: manual .env parsing (no dependency needed)
                for line in env_file.read_text().splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))
            break  # Stop after first .env found


# Load .env on import so library users get API keys loaded
_load_dotenv()

from .client import AIClient
from .config import Config, load_config
from .exceptions import AIError, ConfigError, ProviderError, UnknownAliasError
from .aliases import resolve_alias

__version__ = "2.0.0"

__all__ = [
    # Main interface
    "AIClient",
    # Configuration
    "Config",
    "load_config",
    # Exceptions
    "AIError",
    "ConfigError",
    "ProviderError",
    "UnknownAliasError",
    # Utilities
    "resolve_alias",
    # Version
    "__version__",
]
