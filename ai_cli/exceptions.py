"""Exception classes for ai-cli."""


class AIError(Exception):
    """Base exception for ai-cli errors."""

    def __init__(self, message: str, hint: str | None = None):
        super().__init__(message)
        self.message = message
        self.hint = hint


class UnknownAliasError(AIError):
    """Raised when a model alias cannot be resolved."""

    def __init__(self, alias: str):
        super().__init__(
            f"Unknown alias '{alias}'. Run 'ai list' to see available models.",
            hint="Set a default with 'ai default <alias>' to use 'ai \"prompt\"' directly."
        )
        self.alias = alias


class ProviderError(AIError):
    """Raised when a provider fails to execute."""

    def __init__(self, provider: str, message: str):
        super().__init__(f"{provider} error: {message}")
        self.provider = provider


class ConfigError(AIError):
    """Raised when configuration is invalid or missing."""
    pass
