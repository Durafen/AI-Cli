"""Main client interface for ai-cli library usage."""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .aliases import resolve_alias
from .config import Config, load_config
from .exceptions import AIError, ProviderError, UnknownAliasError
from .providers import PROVIDERS, get_provider_instance


class AIClient:
    """
    Main interface for using ai-cli as a library.

    Example usage:
        from ai_cli import AIClient

        client = AIClient()
        response = client.call("sonnet", "Explain Python's GIL")

        # With options
        response = client.call("opus", "List 3 colors", json_mode=True)

        # List available models
        for alias, (provider, model) in client.list_models().items():
            print(f"{alias} -> {provider}:{model}")
    """

    def __init__(self, config_path: str | Path | None = None):
        """
        Initialize the client.

        Args:
            config_path: Optional path to config file. If None, uses default location.
        """
        self._config_path = Path(config_path) if config_path else None
        self._config: Config | None = None
        self._config_lock = threading.Lock()
        self._providers: dict = {}
        self._providers_lock = threading.Lock()

    @property
    def config(self) -> Config:
        """Lazy-load configuration (thread-safe)."""
        if self._config is None:
            with self._config_lock:
                # Double-check after acquiring lock
                if self._config is None:
                    self._config = load_config(self._config_path)
        return self._config

    def reload_config(self) -> None:
        """Force reload configuration from disk."""
        self._config = None
        self._providers.clear()

    def call(
        self,
        alias: str,
        prompt: str,
        json_mode: bool = False,
        yolo: bool = False,
    ) -> str:
        """
        Execute a prompt using the specified model alias.

        Args:
            alias: Model alias (e.g., "sonnet", "gpt") or provider:model format
            prompt: The prompt to send
            json_mode: Request JSON output format
            yolo: Auto-approve file edits (for providers that support it)

        Returns:
            The model's response as a string

        Raises:
            UnknownAliasError: If the alias cannot be resolved
            ProviderError: If the provider fails to execute
        """
        provider_name, model = resolve_alias(alias, self.config)
        provider = self._get_provider(provider_name)
        return provider.call(model, prompt, json_output=json_mode, yolo=yolo)

    def call_direct(
        self,
        provider_name: str,
        model: str,
        prompt: str,
        json_mode: bool = False,
        yolo: bool = False,
    ) -> str:
        """
        Execute a prompt directly specifying provider and model.

        Args:
            provider_name: Provider name (e.g., "claude", "gemini")
            model: Model identifier
            prompt: The prompt to send
            json_mode: Request JSON output format
            yolo: Auto-approve file edits

        Returns:
            The model's response as a string
        """
        provider = self._get_provider(provider_name)
        return provider.call(model, prompt, json_output=json_mode, yolo=yolo)

    def call_multi(
        self,
        aliases: list[str],
        prompt: str,
        json_mode: bool = False,
    ) -> dict[str, str | Exception]:
        """
        Execute a prompt on multiple models in parallel.

        Args:
            aliases: List of model aliases to query
            prompt: The prompt to send to all models
            json_mode: Request JSON output format

        Returns:
            Dict mapping alias to response string or Exception if failed
        """
        def call_one(alias: str) -> tuple[str, str | Exception]:
            try:
                return (alias, self.call(alias, prompt, json_mode=json_mode))
            except Exception as e:
                return (alias, e)

        results: dict[str, str | Exception] = {}
        with ThreadPoolExecutor(max_workers=len(aliases)) as executor:
            futures = {executor.submit(call_one, alias): alias for alias in aliases}
            for future in as_completed(futures):
                alias, result = future.result()
                results[alias] = result

        # Return in original order
        return {alias: results[alias] for alias in aliases}

    def _get_provider(self, name: str):
        """Get or create a provider instance (thread-safe)."""
        if name not in self._providers:
            with self._providers_lock:
                # Double-check after acquiring lock
                if name not in self._providers:
                    self._providers[name] = get_provider_instance(name)
        return self._providers[name]

    def list_models(self) -> dict[str, tuple[str, str]]:
        """
        Get all available model aliases.

        Returns:
            Dict mapping alias to (provider, model) tuple
        """
        return dict(self.config.aliases)

    def list_providers(self) -> list[str]:
        """
        Get list of known provider names.

        Returns:
            List of provider names
        """
        return list(PROVIDERS.keys())

    def list_available_providers(self) -> list[str]:
        """
        Get list of providers that are currently available (installed/configured).

        Returns:
            List of available provider names
        """
        available = []
        for name in PROVIDERS:
            try:
                provider = self._get_provider(name)
                if provider.is_available():
                    available.append(name)
            except (ValueError, ProviderError):
                # Provider not found or failed to initialize - skip it
                pass
        return available

    def get_default_alias(self) -> str | None:
        """Get the default model alias, if set."""
        return self.config.default_alias

    def set_default_alias(self, alias: str | None) -> None:
        """
        Set or clear the default model alias.

        Args:
            alias: Alias to set as default, or None to clear
        """
        self.config.set_default(alias)
        self.config.save()

    def resolve(self, alias: str) -> tuple[str, str]:
        """
        Resolve an alias to (provider, model) without calling.

        Args:
            alias: Model alias to resolve

        Returns:
            Tuple of (provider_name, model_id)

        Raises:
            UnknownAliasError: If alias cannot be resolved
        """
        return resolve_alias(alias, self.config)

    def is_available(self, alias: str) -> bool:
        """
        Check if a model alias is available for use.

        Args:
            alias: Model alias to check

        Returns:
            True if the alias can be resolved and its provider is available
        """
        try:
            provider_name, _ = resolve_alias(alias, self.config)
            provider = self._get_provider(provider_name)
            return provider.is_available()
        except (UnknownAliasError, ValueError):
            return False
