"""Configuration management for ai-cli."""

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .constants import CONFIG_DIR, CONFIG_FILE, DEFAULT_ALIASES
from .exceptions import ConfigError


@dataclass
class Config:
    """Configuration container for ai-cli."""

    installed_tools: list[str] = field(default_factory=list)
    models: dict[str, list[str]] = field(default_factory=dict)
    aliases: dict[str, tuple[str, str]] = field(default_factory=lambda: dict(DEFAULT_ALIASES))
    default_alias: str | None = None

    _path: Path | None = field(default=None, repr=False)

    @property
    def path(self) -> Path:
        """Get the config file path."""
        return self._path or CONFIG_FILE

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        """Load config from file or return defaults."""
        config_path = path or CONFIG_FILE
        if config_path.exists():
            try:
                with open(config_path) as f:
                    data = json.load(f)
                return cls(
                    installed_tools=data.get("installed_tools", []),
                    models=data.get("models", {}),
                    aliases=cls._parse_aliases(data.get("aliases", DEFAULT_ALIASES)),
                    default_alias=data.get("default_alias"),
                    _path=config_path,
                )
            except json.JSONDecodeError as e:
                raise ConfigError(f"Invalid config file: {e}")
        return cls(_path=config_path)

    @staticmethod
    def _parse_aliases(aliases_data: dict) -> dict[str, tuple[str, str]]:
        """Parse aliases from JSON (lists) to tuples."""
        return {
            k: tuple(v) if isinstance(v, list) else v
            for k, v in aliases_data.items()
        }

    def save(self, path: Path | None = None) -> None:
        """Save config to file."""
        config_path = path or self._path or CONFIG_FILE
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "installed_tools": self.installed_tools,
            "models": self.models,
            "aliases": self.aliases,
            **({"default_alias": self.default_alias} if self.default_alias else {}),
        }

    def detect_cli_tools(self) -> list[str]:
        """Detect which CLI tools are installed."""
        tools = ["codex", "claude", "gemini", "qwen", "ollama"]
        self.installed_tools = [tool for tool in tools if shutil.which(tool)]
        return self.installed_tools

    def set_default(self, alias: str | None) -> None:
        """Set or clear the default alias."""
        if alias is None:
            self.default_alias = None
        elif alias not in self.aliases:
            raise ConfigError(f"Unknown alias: {alias}")
        else:
            self.default_alias = alias

    def add_alias(self, name: str, provider: str, model: str) -> None:
        """Add or update an alias."""
        self.aliases[name] = (provider, model)

    def remove_alias(self, name: str) -> bool:
        """Remove an alias. Returns True if removed, False if not found."""
        if name in self.aliases:
            del self.aliases[name]
            if self.default_alias == name:
                self.default_alias = None
            return True
        return False


def load_config(path: Path | None = None) -> Config:
    """Load configuration from file."""
    return Config.load(path)


def get_default_config() -> Config:
    """Get a fresh config with defaults."""
    return Config()
