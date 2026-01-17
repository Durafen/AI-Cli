"""Codex CLI provider (OpenAI)."""

from .cli import CLIConfig, CLIProvider


class CodexProvider(CLIProvider):
    """Provider for Codex CLI (OpenAI)."""

    name = "codex"
    cli_name = "codex"
    config = CLIConfig(
        base_cmd=["codex", "exec"],
        model_args=["--model"],
        json_args=[],  # codex doesn't support json output flag
        yolo_args=["-s", "danger-full-access"],
        prompt_mode="arg",
    )

    KNOWN_MODELS = ["gpt-5.2-codex", "gpt-5.1-codex-max", "gpt-5.1-codex-mini", "gpt-5.2"]
