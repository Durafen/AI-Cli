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
        default_args=["-s", "workspace-write"],  # sandbox when NOT yolo
        prompt_mode="arg",
        extra_args=["--skip-git-repo-check"],  # always: bypass trust check
    )

    KNOWN_MODELS = ["gpt-5.3-codex", "gpt-5.2-codex", "gpt-5.1-codex-max", "gpt-5.1-codex-mini", "gpt-5.2"]

    def _build_command(self, model: str, prompt: str, json_output: bool, yolo: bool) -> list[str]:
        """Build command, extracting @effort suffix if present."""
        effort = None
        if "@" in model:
            model, effort = model.rsplit("@", 1)
        cmd = super()._build_command(model, prompt, json_output, yolo)
        if effort:
            cmd.extend(["-c", f'model_reasoning_effort="{effort}"'])
        return cmd
