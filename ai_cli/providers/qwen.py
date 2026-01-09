"""Qwen CLI provider (Alibaba)."""

from .cli import CLIConfig, CLIProvider


class QwenProvider(CLIProvider):
    """Provider for Qwen CLI (Alibaba)."""

    name = "qwen"
    cli_name = "qwen"
    config = CLIConfig(
        base_cmd=["qwen"],
        model_args=["--model"],
        json_args=["--output-format", "json"],
        yolo_args=["--yolo"],
        prompt_mode="arg",
    )

    KNOWN_MODELS = ["coder-model", "vision-model"]
