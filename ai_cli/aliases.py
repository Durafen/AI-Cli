"""Alias resolution for ai-cli."""

from .config import Config
from .constants import DEFAULT_ALIASES
from .exceptions import UnknownAliasError
from .providers import PROVIDERS

# Valid provider names derived from provider registry (single source of truth)
KNOWN_PROVIDERS = set(PROVIDERS.keys())


def resolve_alias(model_arg: str, config: Config) -> tuple[str, str]:
    """
    Resolve model argument to (provider, model) tuple.

    Accepts:
    - Known aliases (e.g., "sonnet", "gpt")
    - Provider:model format (e.g., "claude:opus", "openrouter:org/model:free")

    Raises:
        UnknownAliasError: If the alias cannot be resolved.
    """
    aliases = config.aliases

    # Check if it's a known alias
    if model_arg in aliases:
        return aliases[model_arg]

    # Check for provider:model format (only if prefix is a known provider)
    if ":" in model_arg:
        parts = model_arg.split(":", 1)
        provider = parts[0]
        model = parts[1]
        # Only treat as provider:model if provider is valid
        if provider in KNOWN_PROVIDERS:
            # Handle openrouter:org/model:free format
            if provider == "openrouter" and "/" in model:
                return ("openrouter", model)
            return (provider, model)

    raise UnknownAliasError(model_arg)


def get_model_for_alias(alias: str, config: Config) -> str | None:
    """Get just the model name for an alias, or None if not found."""
    try:
        _, model = resolve_alias(alias, config)
        return model
    except UnknownAliasError:
        return None


def get_provider_for_alias(alias: str, config: Config) -> str | None:
    """Get just the provider name for an alias, or None if not found."""
    try:
        provider, _ = resolve_alias(alias, config)
        return provider
    except UnknownAliasError:
        return None


def list_aliases_by_provider(config: Config) -> dict[str, list[tuple[str, str]]]:
    """
    Group aliases by provider.

    Returns:
        Dict mapping provider name to list of (alias, model) tuples.
    """
    by_provider: dict[str, list[tuple[str, str]]] = {}
    for alias, (provider, model) in config.aliases.items():
        if provider not in by_provider:
            by_provider[provider] = []
        by_provider[provider].append((alias, model))
    return by_provider
