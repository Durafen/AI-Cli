"""Ollama provider (local models)."""

import subprocess
from .cli import CLIConfig, CLIProvider


class OllamaProvider(CLIProvider):
    """Provider for Ollama (local models)."""

    name = "ollama"
    cli_name = "ollama"
    config = CLIConfig(
        base_cmd=["ollama", "run"],
        model_args=[],  # model is positional
        json_args=["--format", "json"],
        yolo_args=[],  # ollama doesn't need yolo
        prompt_mode="arg",
        extra_args=["--hidethinking"],
        model_positional=True,
    )

    @classmethod
    def get_installed_models(cls) -> list[str]:
        """Get list of installed ollama models."""
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                return []
            # Parse output: NAME ID SIZE MODIFIED
            models = []
            for line in result.stdout.strip().split("\n")[1:]:  # Skip header
                if line.strip():
                    name = line.split()[0]
                    models.append(name)
            return models
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return []

    @classmethod
    def generate_aliases(cls, models: list[str], existing: dict) -> dict:
        """Generate short aliases for Ollama models."""
        from ..constants import RESERVED_COMMANDS

        aliases = {}
        if not models:
            return aliases

        # Set default ollama alias to first model
        aliases["ollama"] = ("ollama", models[0])

        for model in models:
            short_name = model.split(":")[0]  # llama3:latest -> llama3
            if short_name not in existing and short_name not in RESERVED_COMMANDS:
                aliases[short_name] = ("ollama", model)

        return aliases
