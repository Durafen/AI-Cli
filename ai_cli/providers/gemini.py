"""Gemini CLI provider (Google)."""

from .cli import CLIConfig, CLIProvider


class GeminiProvider(CLIProvider):
    """Provider for Gemini CLI (Google)."""

    name = "gemini"
    cli_name = "agy"  # Gemini CLI is now the multi-model 'agy' binary
    config = CLIConfig(
        base_cmd=["agy"],
        model_args=["--model"],
        json_args=[],  # agy has no JSON output mode
        yolo_args=["--dangerously-skip-permissions"],
        prompt_mode="arg",
        extra_args=["--print"],  # non-interactive single-prompt mode; prompt is appended after
    )

    # agy --model expects these exact display strings (it silently falls back
    # to a default on an unrecognized model, so the names must match precisely).
    KNOWN_MODELS = [
        "Gemini 3.1 Pro (High)",
        "Gemini 3.1 Pro (Low)",
        "Gemini 3.5 Flash (High)",
        "Gemini 3.5 Flash (Medium)",
        "Gemini 3.5 Flash (Low)",
    ]
