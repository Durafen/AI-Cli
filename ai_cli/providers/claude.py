"""Claude CLI provider (Anthropic)."""

from .cli import CLIConfig, CLIProvider


class ClaudeProvider(CLIProvider):
    """Provider for Claude CLI (Anthropic)."""

    name = "claude"
    cli_name = "claude"
    config = CLIConfig(
        base_cmd=["claude", "--print"],
        model_args=["--model"],
        json_args=["--output-format", "json"],
        yolo_args=["--dangerously-skip-permissions"],
        prompt_mode="stdin",
    )

    # Known models for this provider
    KNOWN_MODELS = ["haiku", "sonnet", "opus"]
