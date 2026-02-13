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

    def _build_command(self, model: str, prompt: str, json_output: bool, yolo: bool) -> list[str]:
        """Build command, extracting @effort suffix if present."""
        effort = None
        if "@" in model:
            model, effort = model.rsplit("@", 1)
        cmd = super()._build_command(model, prompt, json_output, yolo)
        if effort:
            cmd.extend(["--effort", effort])
        return cmd
