#!/usr/bin/env python3
"""
ai - Unified AI CLI tool
Dispatches prompts to different AI CLI tools based on model alias.

Usage:
    ai <model> "prompt"          # Basic usage
    ai "prompt"                  # Use default model (if set)
    ai json [model] "prompt"     # JSON output (or: ai <model> json "prompt")
    ai cmd [model] "prompt"      # Return only terminal command
    ai run [model] "prompt"      # Generate command, confirm, execute
    ai <model> run "prompt"      # Same (flags work in any position)
    ai run -y "prompt"           # Skip confirmation (auto-execute)
    ai yolo [model] "prompt"     # Auto-approve file edits
    ai init                      # Initialize (detect tools)
    ai list                      # List available models
    ai default [alias]           # Get/set default model
    ai default --clear           # Remove default model
    cat file.txt | ai <model>    # Stdin input
"""

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

# For single-keypress reading (Unix only)
try:
    import termios
    import tty
    HAS_TERMIOS = True
except ImportError:
    HAS_TERMIOS = False

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
RESERVED_COMMANDS = {"init", "list", "default", "cmd", "json", "help", "yolo", "run"}

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

# Provider CLI configurations for unified dispatch
# prompt_mode: "stdin" = pass via stdin, "arg" = append as argument
PROVIDER_CLI_CONFIG = {
    "claude": {
        "base_cmd": ["claude", "--print"],
        "model_args": ["--model"],
        "json_args": ["--output-format", "json"],
        "yolo_args": ["--dangerously-skip-permissions"],
        "prompt_mode": "stdin",
    },
    "codex": {
        "base_cmd": ["codex", "exec"],
        "model_args": ["--model"],
        "json_args": [],  # codex doesn't support json output flag
        "yolo_args": ["-s", "danger-full-access", "-a", "never"],
        "prompt_mode": "arg",
    },
    "gemini": {
        "base_cmd": ["gemini"],
        "model_args": ["--model"],
        "json_args": ["--output-format", "json"],
        "yolo_args": ["--yolo"],
        "prompt_mode": "arg",
    },
    "qwen": {
        "base_cmd": ["qwen"],
        "model_args": ["--model"],
        "json_args": ["--output-format", "json"],
        "yolo_args": ["--yolo"],
        "prompt_mode": "arg",
    },
    "ollama": {
        "base_cmd": ["ollama", "run"],
        "model_args": [],
        "json_args": ["--format", "json"],
        "yolo_args": [],
        "prompt_mode": "arg",
        "extra_args": ["--hidethinking"],
        "model_positional": True,  # model comes after flags, before prompt
    },
}


class UnknownAliasError(Exception):
    """Raised when a model alias cannot be resolved."""
    pass


def die(msg: str, hint: str = None):
    """Print error message to stderr and exit with code 1."""
    print(f"Error: {msg}", file=sys.stderr)
    if hint:
        print(f"Tip: {hint}", file=sys.stderr)
    sys.exit(1)


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
    """Fetch free models from OpenRouter API. Returns empty if no API key."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return []

    try:
        import urllib.request
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return [m["id"] for m in data.get("data", []) if m["id"].endswith(":free")]
    except Exception:
        return []


def generate_ollama_aliases(models: list[str], existing: dict) -> dict:
    """Generate short aliases for Ollama models."""
    aliases = {}
    if not models:
        return aliases

    # Set default ollama alias to first model
    aliases["ollama"] = ("ollama", models[0])

    for model in models:
        short_name = model.split(":")[0]  # llama3:latest -> llama3
        if short_name not in existing and short_name not in RESERVED_COMMANDS:
            aliases[short_name] = ("ollama", model)
    return aliases


def shorten_openrouter_name(full_name: str) -> str:
    """Shorten an OpenRouter model name by removing common suffixes and versions."""
    name = full_name
    # Remove common suffixes
    for suffix in ["-instruct", "-it", "-pro", "-air", "-exp", "-mini",
                   "-small", "-nano", "-flash", "-plus", "-chat", "-base",
                   "-preview", "-edition", "-venice-edition"]:
        name = name.replace(suffix, "")
    # Remove version patterns
    name = re.sub(r'-v\d+', '', name)  # -v2, -v3
    name = re.sub(r'-\d+(\.\d+)?b?$', '', name)  # -24b, -3.1, -70b
    name = re.sub(r'-\d+\.\d+-', '-', name)  # -3.1- in middle
    name = re.sub(r'-\d+b-', '-', name)  # -24b- in middle
    return name.strip('-') or full_name


def generate_openrouter_aliases(models: list[str], existing: dict) -> dict:
    """Generate short aliases for OpenRouter models, handling conflicts."""
    aliases = {}
    if not models:
        return aliases

    # First pass: collect candidates
    candidates = {}  # short_name -> [models]
    full_names = {}  # model -> full_name

    for model in models:
        if "/" not in model:
            continue
        full_name = model.split("/")[1].replace(":free", "")
        full_names[model] = full_name
        short_name = shorten_openrouter_name(full_name)
        candidates.setdefault(short_name, []).append(model)

    # Second pass: assign aliases
    for short_name, model_list in candidates.items():
        if len(model_list) == 1:
            model = model_list[0]
            full_name = full_names[model]
            if short_name not in existing and short_name not in RESERVED_COMMANDS:
                aliases[short_name] = ("openrouter", model)
            elif full_name not in existing and full_name not in RESERVED_COMMANDS:
                aliases[full_name] = ("openrouter", model)
        else:
            # Conflict - use full names
            for model in model_list:
                full_name = full_names[model]
                if full_name not in existing and full_name not in RESERVED_COMMANDS:
                    aliases[full_name] = ("openrouter", model)

    return aliases


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

    # Build aliases
    aliases = dict(DEFAULT_ALIASES)
    aliases.update(generate_ollama_aliases(models.get("ollama", []), aliases))
    aliases.update(generate_openrouter_aliases(models.get("openrouter", []), aliases))

    # Save config (preserve existing default_alias)
    old_config = load_config()
    config = {
        "installed_tools": installed,
        "models": models,
        "aliases": aliases,
    }
    if "default_alias" in old_config:
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
            die(f"'{alias}' is a reserved command, cannot be used as default.")
        aliases = config.get("aliases", DEFAULT_ALIASES)
        if alias not in aliases:
            die(f"unknown alias '{alias}'. Run 'ai list' to see available models.")
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
    """Resolve model argument to (provider, model). Raises UnknownAliasError if not found."""
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

    raise UnknownAliasError(model_arg)


def call_cli(provider: str, model: str, prompt: str, json_output: bool, yolo: bool = False) -> str:
    """Unified CLI caller for subprocess-based providers."""
    cfg = PROVIDER_CLI_CONFIG[provider]

    # Build command
    cmd = list(cfg["base_cmd"])
    if cfg["model_args"]:
        cmd.extend(cfg["model_args"])
        cmd.append(model)
    if json_output and cfg["json_args"]:
        cmd.extend(cfg["json_args"])
    if yolo and cfg["yolo_args"]:
        cmd.extend(cfg["yolo_args"])
    if cfg.get("extra_args"):
        cmd.extend(cfg["extra_args"])

    # Some providers (e.g., ollama) need model as positional arg after flags
    if cfg.get("model_positional"):
        cmd.append(model)

    # Execute with prompt via stdin or as argument
    if cfg["prompt_mode"] == "stdin":
        result = subprocess.run(cmd, input=prompt, capture_output=True, text=True)
    else:
        cmd.append(prompt)
        result = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL)

    if result.returncode != 0:
        raise RuntimeError(f"{provider} error: {result.stderr}")
    return result.stdout


def call_openrouter(model: str, prompt: str, json_output: bool, yolo: bool = False) -> str:
    """Call OpenRouter API (free models only, yolo ignored - API only)."""
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


def dispatch(provider: str, model: str, prompt: str, json_output: bool, yolo: bool = False) -> str:
    """Dispatch to appropriate handler."""
    if provider == "openrouter":
        return call_openrouter(model, prompt, json_output, yolo)

    if provider not in PROVIDER_CLI_CONFIG:
        raise RuntimeError(f"Unknown provider: {provider}")

    # Check if CLI tool exists
    if not shutil.which(provider):
        raise RuntimeError(f"CLI tool '{provider}' not found. Run 'ai init' to check available tools.")

    return call_cli(provider, model, prompt, json_output, yolo)


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="ai",
        description="Unified AI CLI dispatcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Output mode flags
    parser.add_argument("--json", "-j", action="store_true", help="JSON output format")
    parser.add_argument("--cmd", "-c", action="store_true", help="Return only terminal command")
    parser.add_argument("--run", "-r", action="store_true", help="Generate command, confirm, execute")
    parser.add_argument("--yolo", "-y", action="store_true", help="Auto-approve file edits (or skip confirm for --run)")

    # Positional args: [model] prompt...
    parser.add_argument("args", nargs="*", metavar="[model] prompt", help="Model alias and/or prompt text")

    return parser


def normalize_args(argv: list[str]) -> list[str]:
    """Convert legacy bare keywords to flags for backwards compat."""
    # Map bare words to flags (must be first in remaining args to be treated as flags)
    flag_words = {"json": "--json", "cmd": "--cmd", "run": "--run", "yolo": "--yolo"}
    normalized = []
    for arg in argv:
        if arg in flag_words:
            normalized.append(flag_words[arg])
        else:
            normalized.append(arg)
    return normalized


def sanitize_command(text: str) -> str:
    """Strip markdown code blocks, emojis, and other non-command text."""
    text = text.strip()
    # Remove leading emojis first (common unicode emoji ranges)
    while text and (text[0] > "\U0001F000" or text[0] in "🤖💡✨⚡🔥"):
        text = text[1:].lstrip()
    # Remove markdown code blocks
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```bash or similar) and last line (```)
        lines = [l for l in lines[1:] if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    return text.strip()


def read_keypress() -> str | None:
    """Read a single keypress without waiting for Enter. Returns key or None on error."""
    if not HAS_TERMIOS or not sys.stdin.isatty():
        return None
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        # Handle escape sequences (arrows, ESC, etc.)
        if ch == '\x1b':  # ESC
            # Check if it's a longer escape sequence or just ESC
            import select
            if select.select([sys.stdin], [], [], 0.05)[0]:
                sys.stdin.read(2)  # consume rest of escape sequence
            return 'esc'
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def main():
    argv = sys.argv[1:]

    # Handle subcommands before argparse (they have different arg structures)
    if argv:
        if argv[0] == "init":
            run_init()
            return
        if argv[0] in ("list", "-l"):
            show_list()
            return
        if argv[0] == "default":
            handle_default(argv[1:])
            return

    # Show help for no args (unless piping stdin with a default set)
    config = load_config()
    if not argv:
        if config.get("default_alias") and not sys.stdin.isatty():
            pass  # Continue to handle stdin with default model
        else:
            create_parser().print_help()
            return

    # Normalize legacy bare keywords and parse
    # Use parse_intermixed_args to allow flags anywhere (e.g., "ai sonnet run prompt")
    parser = create_parser()
    args = parser.parse_intermixed_args(normalize_args(argv))

    aliases = config.get("aliases", DEFAULT_ALIASES)
    positionals = args.args

    # Determine model and prompt
    if not positionals:
        # No positional args - use default + stdin
        default_alias = config.get("default_alias")
        if default_alias and not sys.stdin.isatty():
            model_arg = default_alias
            prompt = sys.stdin.read().strip()
        else:
            die("model or prompt required")
    elif positionals[0] in aliases or ":" in positionals[0]:
        # First arg is a known alias or provider:model
        model_arg = positionals[0]
        if len(positionals) >= 2:
            prompt = " ".join(positionals[1:])
        elif not sys.stdin.isatty():
            prompt = sys.stdin.read().strip()
        else:
            die("prompt required (as argument or via stdin)")
    else:
        # First arg is not an alias - use default model if set
        default_alias = config.get("default_alias")
        if default_alias:
            model_arg = default_alias
            prompt = " ".join(positionals)
        else:
            die(f"unknown model '{positionals[0]}'. Run 'ai list' to see available models.",
                hint="Set a default with 'ai default <alias>' to use 'ai \"prompt\"' directly.")

    try:
        provider, model = resolve_alias(model_arg, config)
    except UnknownAliasError:
        die(f"unknown model '{model_arg}'. Run 'ai list' to see available models.")

    # Wrap prompt for cmd/run mode
    if args.cmd or args.run:
        os_name = platform.system()  # Darwin, Linux, Windows
        shell = os.path.basename(os.environ.get("SHELL", "sh"))
        prompt = (
            f"[SYSTEM: OS={os_name}, Shell={shell}. OUTPUT MODE: Your entire response "
            "will be piped directly to /bin/sh for execution. Return ONLY a single "
            "shell command. Any text that is not a valid command will cause an error. "
            f"No prose, no markdown, no explanation.]\n\n{prompt}"
        )

    try:
        result = dispatch(provider, model, prompt, args.json, args.yolo if not args.run else False)
        if args.cmd or args.run:
            result = sanitize_command(result)

        if args.run:
            # Show command and confirm
            print(f"\033[90m$ \033[0m\033[1m{result}\033[0m")
            if not args.yolo:
                try:
                    print("\033[90m[Enter/Space] run, [Esc/n] cancel: \033[0m", end="", flush=True)
                    key = read_keypress()
                    print()  # newline after keypress
                    if key is None:
                        # Fallback to line input if keypress reading unavailable
                        response = input().strip().lower()
                        if response in ("n", "no"):
                            print("Cancelled.")
                            return
                    elif key in ('esc', 'n', 'N', '\x03'):  # ESC, n, or Ctrl+C
                        print("Cancelled.")
                        return
                    elif key not in ('\r', '\n', ' ', 'y', 'Y'):
                        # Unknown key - cancel for safety
                        print("Cancelled.")
                        return
                except (KeyboardInterrupt, EOFError):
                    print("\nCancelled.")
                    return
            # Execute
            exec_result = subprocess.run(result, shell=True)
            sys.exit(exec_result.returncode)
        else:
            print(result)
    except RuntimeError as e:
        die(str(e))
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
