#!/usr/bin/env python3
"""
ai - Unified AI CLI tool
Dispatches prompts to different AI CLI tools based on model alias.

Usage:
    ai <model> "prompt"          # Basic usage
    ai --json <model> "prompt"   # JSON output
    ai init                      # Initialize (detect tools)
    ai --list                    # List available models
    cat file.txt | ai <model>    # Stdin input
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Load .env file from script directory (for API keys)
# Note: resolve() first to follow symlinks, then get parent
SCRIPT_DIR = Path(__file__).resolve().parent
try:
    from dotenv import load_dotenv
    load_dotenv(SCRIPT_DIR / ".env")
except ImportError:
    pass  # dotenv not installed, rely on environment variables

CONFIG_DIR = Path.home() / ".ai-cli"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Known models per provider (from CLI /model commands)
KNOWN_MODELS = {
    "claude": ["haiku", "sonnet", "opus"],
    "codex": ["gpt-5.2-codex", "gpt-5.1-codex-max", "gpt-5.1-codex-mini", "gpt-5.2"],
    "gemini": ["gemini-3-pro-preview", "gemini-3-flash-preview", "gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite"],
    "qwen": ["coder-model", "vision-model"],
}

# Default aliases: alias -> (provider, model)
DEFAULT_ALIASES = {
    # Claude CLI (Anthropic)
    "claude": ("claude", "sonnet"),
    "haiku": ("claude", "haiku"),
    "sonnet": ("claude", "sonnet"),
    "opus": ("claude", "opus"),
    # Codex CLI (OpenAI)
    "codex": ("codex", "gpt-5.2-codex"),
    "gpt": ("codex", "gpt-5.2-codex"),
    "gpt-max": ("codex", "gpt-5.1-codex-max"),
    "gpt-mini": ("codex", "gpt-5.1-codex-mini"),
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


def load_config() -> dict:
    """Load config from file or return defaults."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {"installed_tools": [], "models": {}, "aliases": DEFAULT_ALIASES}


def save_config(config: dict):
    """Save config to file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def detect_cli_tools() -> list[str]:
    """Detect which CLI tools are installed."""
    tools = ["codex", "claude", "gemini", "qwen", "ollama"]
    installed = []
    for tool in tools:
        if shutil.which(tool):
            installed.append(tool)
    return installed


def get_ollama_models() -> list[str]:
    """Get list of installed ollama models."""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            return []
        # Parse output: NAME ID SIZE MODIFIED
        models = []
        for line in result.stdout.strip().split("\n")[1:]:  # Skip header
            if line.strip():
                name = line.split()[0]
                models.append(name)
        return models
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def get_openrouter_free_models() -> list[str]:
    """Fetch free models from OpenRouter API."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        # Return known free models as fallback
        return [
            "xiaomi/mimo-v2-flash:free",
            "allenai/olmo-3.1-32b-think:free",
            "nex-agi/deepseek-v3.1-nex-n1:free",
            "tngtech/deepseek-r1t2-chimera:free",
            "mistralai/devstral-2512:free",
            "openai/gpt-oss-120b:free",
        ]

    try:
        import urllib.request
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            # Filter for free models (ends with :free)
            return [m["id"] for m in data.get("data", []) if m["id"].endswith(":free")]
    except Exception:
        # Return known free models as fallback
        return [
            "xiaomi/mimo-v2-flash:free",
            "allenai/olmo-3.1-32b-think:free",
            "nex-agi/deepseek-v3.1-nex-n1:free",
        ]


def run_init():
    """Initialize: detect tools and discover models."""
    print("Initializing ai-cli...")

    # Detect CLI tools
    installed = detect_cli_tools()
    print(f"Detected CLI tools: {', '.join(installed) if installed else 'none'}")

    # Build models dict
    models = {}
    for tool in installed:
        if tool == "ollama":
            models["ollama"] = get_ollama_models()
            print(f"  ollama models: {', '.join(models['ollama']) if models['ollama'] else 'none'}")
        elif tool in KNOWN_MODELS:
            models[tool] = KNOWN_MODELS[tool]
            print(f"  {tool} models: {', '.join(models[tool])}")

    # Get OpenRouter free models
    print("Fetching OpenRouter free models...")
    models["openrouter"] = get_openrouter_free_models()
    print(f"  openrouter free models: {len(models['openrouter'])} found")

    # Build aliases from defaults + dynamic models
    aliases = dict(DEFAULT_ALIASES)

    # Auto-generate ollama aliases
    if "ollama" in models and models["ollama"]:
        aliases["ollama"] = ("ollama", models["ollama"][0])
        for model in models["ollama"]:
            short_name = model.split(":")[0]  # llama3:latest -> llama3
            if short_name not in aliases:
                aliases[short_name] = ("ollama", model)

    # Auto-generate openrouter aliases from model names (smart shortening)
    if "openrouter" in models and models["openrouter"]:
        # First pass: generate candidate short names for each model
        candidates = {}  # short_name -> [list of models that want this name]
        full_names = {}  # model -> full extracted name

        for model in models["openrouter"]:
            if "/" not in model:
                continue
            # Extract name: xiaomi/mimo-v2-flash:free -> mimo-v2-flash
            full_name = model.split("/")[1].replace(":free", "")
            full_names[model] = full_name

            # Generate progressively shorter names
            name = full_name
            # Remove common suffixes to shorten
            for suffix in ["-instruct", "-it", "-pro", "-air", "-exp", "-mini",
                          "-small", "-nano", "-flash", "-plus", "-chat", "-base",
                          "-preview", "-edition", "-venice-edition"]:
                name = name.replace(suffix, "")
            # Remove version patterns like -v2, -3.1, -2.5, -24b, -70b, etc.
            import re
            name = re.sub(r'-v\d+', '', name)  # -v2, -v3
            name = re.sub(r'-\d+(\.\d+)?b?$', '', name)  # -24b, -3.1, -70b
            name = re.sub(r'-\d+\.\d+-', '-', name)  # -3.1- in middle
            name = re.sub(r'-\d+b-', '-', name)  # -24b- in middle
            name = name.strip('-')

            # Use shortened name as candidate
            short_name = name if name else full_name
            candidates.setdefault(short_name, []).append(model)

        # Second pass: assign aliases, handle conflicts
        for short_name, model_list in candidates.items():
            if len(model_list) == 1:
                # Unique among OpenRouter - but check existing aliases
                model = model_list[0]
                full_name = full_names[model]
                if short_name not in aliases:
                    aliases[short_name] = ("openrouter", model)
                elif full_name not in aliases:
                    # Short name taken, try full name
                    aliases[full_name] = ("openrouter", model)
            else:
                # Conflict - use full names for all
                for model in model_list:
                    full_name = full_names[model]
                    if full_name not in aliases:
                        aliases[full_name] = ("openrouter", model)

    # Save config
    config = {
        "installed_tools": installed,
        "models": models,
        "aliases": aliases,
    }
    save_config(config)
    print(f"Config saved to {CONFIG_FILE}")


def show_list():
    """Show available models with aliases."""
    config = load_config()
    aliases = config.get("aliases", DEFAULT_ALIASES)
    models = config.get("models", {})

    # Build reverse lookup: model -> best alias
    # Prefer alias that matches model name, otherwise shortest
    model_to_alias = {}
    for alias, (provider, model) in aliases.items():
        key = (provider, model)
        current = model_to_alias.get(key)
        # Prefer alias that equals model name
        if alias == model:
            model_to_alias[key] = alias
        elif current is None:
            model_to_alias[key] = alias
        elif current != model and len(alias) < len(current):
            # Only replace with shorter if current isn't the model name
            model_to_alias[key] = alias

    print("Available models:")

    for provider, model_list in sorted(models.items()):
        if model_list:
            print(f"\n  {provider}: ({len(model_list)})")
            for model in model_list:
                alias = model_to_alias.get((provider, model))
                if alias and alias != model:
                    print(f"    {alias:20} -> {model}")
                else:
                    print(f"    {model}")

    # Show installed tools
    installed = config.get("installed_tools", [])
    if installed:
        print(f"\nInstalled CLI tools: {', '.join(installed)}")
    else:
        print("\nNo config found. Run 'ai init' to detect tools.")


def resolve_alias(model_arg: str, config: dict) -> tuple[str, str]:
    """Resolve model argument to (provider, model)."""
    aliases = config.get("aliases", DEFAULT_ALIASES)

    # Check if it's a known alias
    if model_arg in aliases:
        return aliases[model_arg]

    # Check for provider:model format
    if ":" in model_arg:
        parts = model_arg.split(":", 1)
        provider = parts[0]
        model = parts[1]
        # Handle openrouter:org/model:free format
        if provider == "openrouter" and "/" in model:
            return ("openrouter", model)
        return (provider, model)

    # Unknown alias
    return (None, model_arg)


def call_claude(model: str, prompt: str, json_output: bool) -> str:
    """Call claude CLI."""
    cmd = ["claude", "--print", "--model", model]
    if json_output:
        cmd.extend(["--output-format", "json"])

    result = subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude error: {result.stderr}")
    return result.stdout


def call_codex(model: str, prompt: str, json_output: bool) -> str:
    """Call codex CLI."""
    cmd = ["codex", "exec", "--model", model, prompt]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        raise RuntimeError(f"codex error: {result.stderr}")
    return result.stdout


def call_gemini(model: str, prompt: str, json_output: bool) -> str:
    """Call gemini CLI."""
    cmd = ["gemini", "--model", model]
    if json_output:
        cmd.extend(["--output-format", "json"])
    cmd.append(prompt)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        raise RuntimeError(f"gemini error: {result.stderr}")
    return result.stdout


def call_qwen(model: str, prompt: str, json_output: bool) -> str:
    """Call qwen CLI."""
    cmd = ["qwen", "--model", model]
    if json_output:
        cmd.extend(["--output-format", "json"])
    cmd.append(prompt)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        raise RuntimeError(f"qwen error: {result.stderr}")
    return result.stdout


def call_ollama(model: str, prompt: str, json_output: bool) -> str:
    """Call ollama CLI."""
    cmd = ["ollama", "run"]
    if json_output:
        cmd.extend(["--format", "json"])
    cmd.extend(["--hidethinking", model, prompt])

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ollama error: {result.stderr}")
    return result.stdout


def call_openrouter(model: str, prompt: str, json_output: bool) -> str:
    """Call OpenRouter API (free models only)."""
    # Enforce free model
    if not model.endswith(":free"):
        raise RuntimeError(f"OpenRouter model must end with ':free'. Got: {model}")

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set")

    import urllib.request

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }
    if json_output:
        payload["response_format"] = {"type": "json_object"}

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode())
        return data["choices"][0]["message"]["content"]


def dispatch(provider: str, model: str, prompt: str, json_output: bool) -> str:
    """Dispatch to appropriate handler."""
    handlers = {
        "claude": call_claude,
        "codex": call_codex,
        "gemini": call_gemini,
        "qwen": call_qwen,
        "ollama": call_ollama,
        "openrouter": call_openrouter,
    }

    if provider not in handlers:
        raise RuntimeError(f"Unknown provider: {provider}")

    # Check if CLI tool exists (except openrouter which is API)
    if provider != "openrouter" and not shutil.which(provider):
        raise RuntimeError(f"CLI tool '{provider}' not found. Run 'ai init' to check available tools.")

    return handlers[provider](model, prompt, json_output)


def print_usage():
    """Print usage information."""
    print(__doc__)


def main():
    args = sys.argv[1:]

    if not args:
        print_usage()
        sys.exit(0)

    # Check for init command
    if args[0] == "init":
        run_init()
        sys.exit(0)

    # Check for --list
    if args[0] in ("--list", "-l"):
        show_list()
        sys.exit(0)

    # Check for --help
    if args[0] in ("--help", "-h"):
        print_usage()
        sys.exit(0)

    # Parse --json flag
    json_output = False
    if "--json" in args:
        json_output = True
        args.remove("--json")

    if len(args) < 1:
        print("Error: model required")
        print_usage()
        sys.exit(1)

    model_arg = args[0]

    # Get prompt from args or stdin
    if len(args) >= 2:
        prompt = " ".join(args[1:])
    elif not sys.stdin.isatty():
        prompt = sys.stdin.read().strip()
    else:
        print("Error: prompt required (as argument or via stdin)")
        sys.exit(1)

    # Load config and resolve alias
    config = load_config()
    provider, model = resolve_alias(model_arg, config)

    if provider is None:
        print(f"Error: unknown model '{model_arg}'. Run 'ai --list' to see available models.")
        sys.exit(1)

    try:
        result = dispatch(provider, model, prompt, json_output)
        print(result)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
