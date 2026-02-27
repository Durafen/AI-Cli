"""Gemini CLI provider (Google)."""

from .cli import CLIConfig, CLIProvider


class GeminiProvider(CLIProvider):
    """Provider for Gemini CLI (Google)."""

    name = "gemini"
    cli_name = "gemini"
    config = CLIConfig(
        base_cmd=["gemini"],
        model_args=["--model"],
        json_args=["--output-format", "json"],
        yolo_args=["--yolo"],
        prompt_mode="arg",
        default_args=[
            "--allowed-tools", "run_shell_command", "read_file",
            "list_directory", "search_file_content", "glob",
        ],
    )

    KNOWN_MODELS = [
        "gemini-3.1-pro-preview",
        "gemini-3-flash-preview",
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
    ]
