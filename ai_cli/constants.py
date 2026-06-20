"""Constants and default configurations for ai-cli."""

from pathlib import Path

# Timeout for prompt execution across all providers (20 minutes)
EXECUTION_TIMEOUT = 1200

# Config file location
CONFIG_DIR = Path.home() / ".ai-cli"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Reserved command names (cannot be used as aliases)
RESERVED_COMMANDS = {"init", "list", "default", "cmd", "json", "help", "yolo", "run", "completions", "serve", "chat", "reply"}

# Default aliases: alias -> (provider, model)
DEFAULT_ALIASES = {
    # Claude CLI (Anthropic)
    "claude": ("claude", "sonnet"),
    "haiku": ("claude", "haiku"),
    "sonnet": ("claude", "sonnet"),
    "opus": ("claude", "opus"),
    "opus-m": ("claude", "opus@medium"),
    "opus-h": ("claude", "opus@high"),
    # Codex CLI (OpenAI)
    "codex": ("codex", "gpt-5.3-codex"),
    "codex-m": ("codex", "gpt-5.3-codex@medium"),
    "codex-h": ("codex", "gpt-5.3-codex@high"),
    "codex-xh": ("codex", "gpt-5.3-codex@xhigh"),
    "gpt": ("codex", "gpt-5.5"),
    "gpt-xh": ("codex", "gpt-5.5@xhigh"),
    "codex-max": ("codex", "gpt-5.1-codex-max"),
    "codex-mini": ("codex", "gpt-5.1-codex-mini"),
    # Gemini via the 'agy' CLI - short aliases default to max-quality (High)
    "gemini": ("gemini", "Gemini 3.5 Flash (High)"),
    "pro": ("gemini", "Gemini 3.1 Pro (High)"),
    "flash": ("gemini", "Gemini 3.5 Flash (High)"),
    "pro-low": ("gemini", "Gemini 3.1 Pro (Low)"),
    "flash-med": ("gemini", "Gemini 3.5 Flash (Medium)"),
    "flash-low": ("gemini", "Gemini 3.5 Flash (Low)"),
    # Qwen CLI (Alibaba)
    "qwen": ("qwen", "coder-model"),
    "qwen-vision": ("qwen", "vision-model"),
    # Ollama CLI (local)
    "ollama": ("ollama", "llama3"),
    # GLM API (Zhipu AI)
    "glm": ("glm", "glm-5"),
    "glm5": ("glm", "glm-5"),
    "glm4": ("glm", "glm-4.7"),
    "glm-air": ("glm", "glm-4.5-air"),
    # OpenRouter API (FREE models only)
    "mimo": ("openrouter", "xiaomi/mimo-v2-flash:free"),
    "olmo": ("openrouter", "allenai/olmo-3.1-32b-think:free"),
    "deepseek": ("openrouter", "nex-agi/deepseek-v3.1-nex-n1:free"),
    "chimera": ("openrouter", "tngtech/deepseek-r1t2-chimera:free"),
    "devstral": ("openrouter", "mistralai/devstral-2512:free"),
    "oss": ("openrouter", "openai/gpt-oss-120b:free"),
}
