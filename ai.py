#!/usr/bin/env python3
"""
ai - Unified AI CLI tool
Dispatches prompts to different AI CLI tools based on model alias.

Usage:
    ai <model> "prompt"          # Basic usage
    ai "prompt"                  # Use default model (if set)
    ai json [model] "prompt"     # JSON output
    ai cmd [model] "prompt"      # Return only terminal command
    ai init                      # Initialize (detect tools)
    ai list                      # List available models
    ai default [alias]           # Get/set default model
    ai default --clear           # Remove default model
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
    # Fallback: manual .env parsing (no dependency needed)
    env_file = SCRIPT_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip().strip("\"'"))

CONFIG_DIR = Path.home() / ".ai-cli"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Reserved command names (cannot be used as aliases)
RESERVED_COMMANDS = {"init", "list", "default", "cmd", "json", "help"}

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
            if short_name not in aliases and short_name not in RESERVED_COMMANDS:
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
                # Unique among OpenRouter - but check existing aliases and reserved
                model = model_list[0]
                full_name = full_names[model]
                if short_name not in aliases and short_name not in RESERVED_COMMANDS:
                    aliases[short_name] = ("openrouter", model)
                elif full_name not in aliases and full_name not in RESERVED_COMMANDS:
                    # Short name taken, try full name
                    aliases[full_name] = ("openrouter", model)
            else:
                # Conflict - use full names for all
                for model in model_list:
                    full_name = full_names[model]
                    if full_name not in aliases and full_name not in RESERVED_COMMANDS:
                        aliases[full_name] = ("openrouter", model)

    # Save config (preserve existing default_alias)
    old_config = load_config()
    config = {
        "installed_tools": installed,
        "models": models,
        "aliases": aliases,
    }
    if "default_alias" in old_config:
        # Validate it still exists in new aliases
        if old_config["default_alias"] in aliases:
            config["default_alias"] = old_config["default_alias"]
        else:
            print(f"Warning: default '{old_config['default_alias']}' no longer valid, cleared.")
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

    # Show default model
    default = config.get("default_alias")
    if default:
        print(f"\nDefault model: {default}")


def handle_default(args: list[str]):
    """Handle 'ai default' subcommand."""
    config = load_config()

    # ai default --clear
    if args and args[0] == "--clear":
        if "default_alias" in config:
            del config["default_alias"]
            save_config(config)
            print("Default model cleared.")
        else:
            print("No default model set.")
        return

    # ai default <alias> - set default
    if args:
        alias = args[0]
        if alias in RESERVED_COMMANDS:
            print(f"Error: '{alias}' is a reserved command, cannot be used as default.")
            sys.exit(1)
        aliases = config.get("aliases", DEFAULT_ALIASES)
        if alias not in aliases:
            print(f"Error: unknown alias '{alias}'. Run 'ai list' to see available models.")
            sys.exit(1)
        config["default_alias"] = alias
        save_config(config)
        provider, model = aliases[alias]
        print(f"Default model set: {alias} -> {provider}:{model}")
        return

    # ai default - show current
    default = config.get("default_alias")
    if default:
        aliases = config.get("aliases", DEFAULT_ALIASES)
        if default in aliases:
            provider, model = aliases[default]
            print(f"{default} -> {provider}:{model}")
        else:
            print(f"{default} (alias no longer valid)")
    else:
        print("No default model set. Use 'ai default <alias>' to set one.")


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
        # No args - check for default + stdin before showing usage
        config = load_config()
        default_alias = config.get("default_alias")
        if default_alias and not sys.stdin.isatty():
            # Will be handled below after flag parsing
            pass
        else:
            print_usage()
            sys.exit(0)

    # Check for subcommands (only if args exist)
    if args:
        if args[0] == "init":
            run_init()
            sys.exit(0)

        if args[0] in ("list", "--list", "-l"):
            show_list()
            sys.exit(0)

        if args[0] == "default":
            handle_default(args[1:])
            sys.exit(0)

        if args[0] in ("help", "--help", "-h"):
            print_usage()
            sys.exit(0)

    # Parse json subcommand: ai json [model] "prompt"
    json_output = False
    if args and args[0] in ("json", "--json"):
        json_output = True
        args = args[1:]

    # Parse cmd subcommand: ai cmd [model] "prompt"
    cmd_mode = False
    if args and args[0] in ("cmd", "--cmd"):
        cmd_mode = True
        args = args[1:]

    # Load config early (needed to check aliases and default)
    config = load_config()
    aliases = config.get("aliases", DEFAULT_ALIASES)

    if len(args) < 1:
        # No args - need either default + stdin, or show usage
        default_alias = config.get("default_alias")
        if default_alias and not sys.stdin.isatty():
            model_arg = default_alias
            prompt = sys.stdin.read().strip()
        else:
            print("Error: model or prompt required")
            print_usage()
            sys.exit(1)
    elif args[0] in aliases or ":" in args[0]:
        # First arg is a known alias or provider:model format
        model_arg = args[0]
        if len(args) >= 2:
            prompt = " ".join(args[1:])
        elif not sys.stdin.isatty():
            prompt = sys.stdin.read().strip()
        else:
            print("Error: prompt required (as argument or via stdin)")
            sys.exit(1)
    else:
        # First arg is not an alias - check for default
        default_alias = config.get("default_alias")
        if default_alias:
            model_arg = default_alias
            # Treat all args as prompt
            prompt = " ".join(args)
        else:
            # No default - treat as unknown alias error
            print(f"Error: unknown model '{args[0]}'. Run 'ai list' to see available models.")
            print("Tip: Set a default with 'ai default <alias>' to use 'ai \"prompt\"' directly.")
            sys.exit(1)

    provider, model = resolve_alias(model_arg, config)

    if provider is None:
        print(f"Error: unknown model '{model_arg}'. Run 'ai list' to see available models.")
        sys.exit(1)

    # Wrap prompt for cmd mode
    if cmd_mode:
        prompt = f"Respond with ONLY a terminal command that accomplishes this task. No explanation, no markdown, no code blocks - just the raw command that can be executed directly.\n\nTask: {prompt}"

    try:
        result = dispatch(provider, model, prompt, json_output)
        # Strip whitespace in cmd mode for clean piping
        if cmd_mode:
            result = result.strip()
        print(result)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
