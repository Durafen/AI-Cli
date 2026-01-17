"""Constants and default configurations for ai-cli."""

from pathlib import Path

# Config file location
CONFIG_DIR = Path.home() / ".ai-cli"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Reserved command names (cannot be used as aliases)
RESERVED_COMMANDS = {"init", "list", "default", "cmd", "json", "help", "yolo", "run", "completions", "serve"}

# Default aliases: alias -> (provider, model)
DEFAULT_ALIASES = {
    # Claude CLI (Anthropic)
    "claude": ("claude", "sonnet"),
    "haiku": ("claude", "haiku"),
    "sonnet": ("claude", "sonnet"),
    "opus": ("claude", "opus"),
    # Codex CLI (OpenAI)
    "codex": ("codex", "gpt-5.2-codex"),
    "gpt": ("codex", "gpt-5.2"),
    "codex-max": ("codex", "gpt-5.1-codex-max"),
    "codex-mini": ("codex", "gpt-5.1-codex-mini"),
    # Gemini CLI (Google) - short aliases point to newest models
    "gemini": ("gemini", "gemini-3-flash-preview"),
    "pro": ("gemini", "gemini-3-pro-preview"),
    "flash": ("gemini", "gemini-3-flash-preview"),
    "pro-2.5": ("gemini", "gemini-2.5-pro"),
    "flash-2.5": ("gemini", "gemini-2.5-flash"),
    "flash-lite": ("gemini", "gemini-2.5-flash-lite"),
    # Qwen CLI (Alibaba)
    "qwen": ("qwen", "coder-model"),
    "qwen-vision": ("qwen", "vision-model"),
    # Ollama CLI (local)
    "ollama": ("ollama", "llama3"),
    # OpenRouter API (FREE models only)
    "mimo": ("openrouter", "xiaomi/mimo-v2-flash:free"),
    "olmo": ("openrouter", "allenai/olmo-3.1-32b-think:free"),
    "deepseek": ("openrouter", "nex-agi/deepseek-v3.1-nex-n1:free"),
    "chimera": ("openrouter", "tngtech/deepseek-r1t2-chimera:free"),
    "devstral": ("openrouter", "mistralai/devstral-2512:free"),
    "oss": ("openrouter", "openai/gpt-oss-120b:free"),
}
