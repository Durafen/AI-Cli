"""Base class for CLI-based providers (subprocess execution)."""

import shutil
import subprocess
from dataclasses import dataclass

from .base import BaseProvider
from ..exceptions import ProviderError

# Default timeout for subprocess calls (5 minutes)
DEFAULT_TIMEOUT = 300


@dataclass
class CLIConfig:
    """Configuration for a CLI-based provider."""

    base_cmd: list[str]
    model_args: list[str]
    json_args: list[str]
    yolo_args: list[str]
    prompt_mode: str  # "stdin" or "arg"
    extra_args: list[str] | None = None
    model_positional: bool = False  # model comes after flags, before prompt
    timeout: int | None = None  # Override default timeout
    default_args: list[str] | None = None  # Args passed when NOT in yolo mode


class CLIProvider(BaseProvider):
    """Base class for providers that use subprocess CLI tools."""

    name: str = "cli"
    cli_name: str = "cli"  # The actual CLI command name
    config: CLIConfig

    def is_available(self) -> bool:
        """Check if the CLI tool is installed."""
        return shutil.which(self.cli_name) is not None

    def call(
        self,
        model: str,
        prompt: str,
        json_output: bool = False,
        yolo: bool = False,
        timeout: int | None = None,
    ) -> str:
        """Execute the CLI tool with the given parameters."""
        if not self.is_available():
            raise ProviderError(
                self.name,
                f"CLI tool '{self.cli_name}' not found. Run 'ai init' to check available tools."
            )

        cmd = self._build_command(model, prompt, json_output, yolo)
        call_timeout = timeout or self.config.timeout or DEFAULT_TIMEOUT

        try:
            if self.config.prompt_mode == "stdin":
                result = subprocess.run(
                    cmd, input=prompt, capture_output=True, text=True, timeout=call_timeout
                )
            else:
                cmd.append(prompt)
                result = subprocess.run(
                    cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=call_timeout
                )
        except subprocess.TimeoutExpired:
            raise ProviderError(self.name, f"Command timed out after {call_timeout}s")

        if result.returncode != 0:
            raise ProviderError(self.name, result.stderr.strip())

        return result.stdout

    def _build_command(
        self,
        model: str,
        prompt: str,
        json_output: bool,
        yolo: bool,
    ) -> list[str]:
        """Build the command list for subprocess execution."""
        cfg = self.config
        cmd = list(cfg.base_cmd)

        if cfg.model_args:
            cmd.extend(cfg.model_args)
            cmd.append(model)

        if json_output and cfg.json_args:
            cmd.extend(cfg.json_args)

        if yolo and cfg.yolo_args:
            cmd.extend(cfg.yolo_args)
        elif cfg.default_args:
            cmd.extend(cfg.default_args)

        if cfg.extra_args:
            cmd.extend(cfg.extra_args)

        # Some providers (e.g., ollama) need model as positional arg after flags
        if cfg.model_positional:
            cmd.append(model)

        return cmd
