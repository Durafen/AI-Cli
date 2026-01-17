"""Provider implementations for ai-cli."""

from .base import BaseProvider, Provider
from .cli import CLIConfig, CLIProvider
from .claude import ClaudeProvider
from .codex import CodexProvider
from .gemini import GeminiProvider
from .qwen import QwenProvider
from .ollama import OllamaProvider
from .openrouter import OpenRouterProvider
from .glm import GLMProvider

__all__ = [
    "Provider",
    "BaseProvider",
    "CLIConfig",
    "CLIProvider",
    "ClaudeProvider",
    "CodexProvider",
    "GeminiProvider",
    "QwenProvider",
    "OllamaProvider",
    "OpenRouterProvider",
    "GLMProvider",
]

# Provider registry for easy lookup by name
PROVIDERS = {
    "claude": ClaudeProvider,
    "codex": CodexProvider,
    "gemini": GeminiProvider,
    "qwen": QwenProvider,
    "ollama": OllamaProvider,
    "openrouter": OpenRouterProvider,
    "glm": GLMProvider,
}


def get_provider(name: str) -> type[BaseProvider]:
    """Get provider class by name."""
    if name not in PROVIDERS:
        raise ValueError(f"Unknown provider: {name}")
    return PROVIDERS[name]


def get_provider_instance(name: str) -> BaseProvider:
    """Get provider instance by name."""
    return get_provider(name)()
