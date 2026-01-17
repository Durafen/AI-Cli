"""CLI entry point and command handling for ai-cli."""

import argparse
import platform
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from .aliases import resolve_alias, KNOWN_PROVIDERS
from .config import Config, load_config
from .constants import DEFAULT_ALIASES, RESERVED_COMMANDS
from .exceptions import AIError, UnknownAliasError
from .providers import PROVIDERS

# For single-keypress reading (Unix only)
try:
    import termios
    import tty
    HAS_TERMIOS = True
except ImportError:
    HAS_TERMIOS = False


def die(msg: str, hint: str | None = None) -> None:
    """Print error message to stderr and exit with code 1."""
    print(f"Error: {msg}", file=sys.stderr)
    if hint:
        print(f"Tip: {hint}", file=sys.stderr)
    sys.exit(1)


def run_init() -> None:
    """Initialize: detect tools and discover models."""
    print("Initializing ai-cli...")

    config = load_config()

    # Detect CLI tools
    installed = config.detect_cli_tools()
    print(f"Detected CLI tools: {', '.join(installed) if installed else 'none'}")

    # Build models dict by iterating over registered providers
    models: dict[str, list[str]] = {}

    for provider_name, provider_cls in PROVIDERS.items():
        if provider_name == "ollama":
            # Ollama: get installed models dynamically
            if "ollama" in installed:
                models["ollama"] = provider_cls.get_installed_models()
                print(f"  ollama models: {', '.join(models['ollama']) if models['ollama'] else 'none'}")
        elif provider_name == "openrouter":
            # OpenRouter: fetch free models from API
            print("Fetching OpenRouter free models...")
            models["openrouter"] = provider_cls.get_free_models()
            print(f"  openrouter free models: {len(models['openrouter'])} found")
        elif provider_name == "glm":
            # GLM: use KNOWN_MODELS if provider has API key configured
            if provider_cls().is_available():
                models["glm"] = provider_cls.KNOWN_MODELS
                print(f"  glm models: {', '.join(models['glm'])}")
        elif provider_name in installed:
            # CLI providers: use KNOWN_MODELS if available
            if hasattr(provider_cls, "KNOWN_MODELS"):
                models[provider_name] = provider_cls.KNOWN_MODELS
                print(f"  {provider_name} models: {', '.join(models[provider_name])}")

    # Build aliases
    aliases = dict(DEFAULT_ALIASES)

    # Generate aliases for providers that support it
    for provider_name, provider_cls in PROVIDERS.items():
        if hasattr(provider_cls, "generate_aliases"):
            provider_models = models.get(provider_name, [])
            if provider_models:
                aliases.update(provider_cls.generate_aliases(provider_models, aliases))

    # Update config
    config.models = models
    config.aliases = aliases

    # Validate existing default alias
    if config.default_alias and config.default_alias not in aliases:
        print(f"Warning: default '{config.default_alias}' no longer valid, cleared.")
        config.default_alias = None

    config.save()
    print(f"Config saved to {config.path}")


def show_list() -> None:
    """Show available models with aliases."""
    config = load_config()
    aliases = config.aliases
    models = config.models

    # Build reverse lookup: model -> best alias
    model_to_alias: dict[tuple[str, str], str] = {}
    for alias, (provider, model) in aliases.items():
        key = (provider, model)
        current = model_to_alias.get(key)
        if alias == model:
            model_to_alias[key] = alias
        elif current is None:
            model_to_alias[key] = alias
        elif current != model and len(alias) < len(current):
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

    installed = config.installed_tools
    if installed:
        print(f"\nInstalled CLI tools: {', '.join(installed)}")
    else:
        print("\nNo config found. Run 'ai init' to detect tools.")

    default = config.default_alias
    if default:
        print(f"\nDefault model: {default}")


def handle_default(args: list[str]) -> None:
    """Handle 'ai default' subcommand."""
    config = load_config()

    if args and args[0] == "--clear":
        if config.default_alias:
            config.default_alias = None
            config.save()
            print("Default model cleared.")
        else:
            print("No default model set.")
        return

    if args:
        alias = args[0]
        if alias in RESERVED_COMMANDS:
            die(f"'{alias}' is a reserved command, cannot be used as default.")
        if alias not in config.aliases:
            die(f"unknown alias '{alias}'. Run 'ai list' to see available models.")
        config.default_alias = alias
        config.save()
        provider, model = config.aliases[alias]
        print(f"Default model set: {alias} -> {provider}:{model}")
        return

    default = config.default_alias
    if default:
        if default in config.aliases:
            provider, model = config.aliases[default]
            print(f"{default} -> {provider}:{model}")
        else:
            print(f"{default} (alias no longer valid)")
    else:
        print("No default model set. Use 'ai default <alias>' to set one.")


def get_completion_words() -> list[str]:
    """Get all valid completion words (subcommands, aliases, flags)."""
    config = load_config()
    aliases = list(config.aliases.keys())
    subcommands = ["init", "list", "default", "completions", "serve"]
    flags = ["--json", "--cmd", "--run", "--yolo", "-j", "-c", "-r", "-y"]
    return sorted(set(subcommands + aliases + flags))


def generate_completion_script(shell: str) -> str:
    """Generate shell completion script."""
    if shell == "bash":
        return '''# ai-cli bash completion
# Add to ~/.bashrc: eval "$(ai completions bash)"
_ai_completions() {
    local cur="${COMP_WORDS[COMP_CWORD]}"
    local words
    words=$(ai --completions 2>/dev/null)
    COMPREPLY=($(compgen -W "$words" -- "$cur"))
}
complete -F _ai_completions ai'''

    elif shell == "zsh":
        return '''# ai-cli zsh completion
# Add to ~/.zshrc: eval "$(ai completions zsh)"
_ai_completions() {
    local words
    words=(${(f)"$(ai --completions 2>/dev/null)"})
    _describe 'ai' words
}
compdef _ai_completions ai'''

    elif shell == "fish":
        return '''# ai-cli fish completion
# Add to ~/.config/fish/config.fish: ai completions fish | source
complete -c ai -f -a "(ai --completions 2>/dev/null)"'''

    else:
        return f"Unknown shell: {shell}. Supported: bash, zsh, fish"


def handle_completions(args: list[str]) -> None:
    """Handle 'ai completions' subcommand."""
    if not args:
        print("Usage: ai completions <shell>")
        print("Shells: bash, zsh, fish")
        print("\nSetup:")
        print('  bash: eval "$(ai completions bash)" >> ~/.bashrc')
        print('  zsh:  eval "$(ai completions zsh)" >> ~/.zshrc')
        print("  fish: ai completions fish | source")
        return
    print(generate_completion_script(args[0]))


def _is_emoji(char: str) -> bool:
    """Check if a character is an emoji using Unicode ranges."""
    cp = ord(char)
    # Common emoji ranges
    return (
        0x1F300 <= cp <= 0x1F9FF or  # Misc Symbols, Emoticons, Symbols & Pictographs
        0x2600 <= cp <= 0x26FF or    # Misc Symbols
        0x2700 <= cp <= 0x27BF or    # Dingbats
        0x1F600 <= cp <= 0x1F64F or  # Emoticons
        0x1F680 <= cp <= 0x1F6FF or  # Transport & Map Symbols
        0x1FA00 <= cp <= 0x1FAFF or  # Chess, Extended-A symbols
        0xFE00 <= cp <= 0xFE0F or    # Variation Selectors
        0x200D == cp                  # Zero Width Joiner (for combined emoji)
    )


def sanitize_command(text: str) -> str:
    """Strip markdown code blocks, emojis, shell prompts, and other non-command text."""
    text = text.strip()

    # Remove leading emojis and whitespace
    while text and (_is_emoji(text[0]) or text[0] in ' \t'):
        text = text[1:]
    text = text.lstrip()

    # Remove markdown code blocks
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```bash or similar) and closing ```
        lines = [l for l in lines[1:] if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    # Remove inline code backticks
    if text.startswith("`") and text.endswith("`") and not text.startswith("```"):
        text = text[1:-1]

    # Strip common shell prompt prefixes ($ , > , % )
    # Only take first line if multiple lines returned
    lines = text.strip().split("\n")
    first_line = lines[0].strip()
    if first_line.startswith("$ "):
        first_line = first_line[2:]
    elif first_line.startswith("> "):
        first_line = first_line[2:]
    elif first_line.startswith("% "):
        first_line = first_line[2:]

    return first_line.strip()


def read_keypress() -> str | None:
    """Read a single keypress without waiting for Enter. Returns key or None on error."""
    if not HAS_TERMIOS or not sys.stdin.isatty():
        return None
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == '\x1b':  # ESC
            import select
            if select.select([sys.stdin], [], [], 0.05)[0]:
                sys.stdin.read(2)
            return 'esc'
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    epilog = """
examples:
  ai sonnet "explain this code"      Basic usage
  ai "write a haiku"                 Use default model
  ai json sonnet "return JSON"       JSON output (bare keyword)
  ai sonnet --json "return JSON"     JSON output (flag)
  ai cmd "list docker containers"    Get shell command only
  ai run "stop nginx"                Generate, confirm, execute
  ai run -y "stop nginx"             Skip confirmation
  ai yolo sonnet "refactor main.py"  Auto-approve file edits
  ai serve                           Start HTTP server (port 8765)

subcommands:
  ai init          Detect tools and fetch models
  ai list          Show available models
  ai default       Get/set default model
  ai completions   Shell completion scripts
"""
    parser = argparse.ArgumentParser(
        prog="ai",
        description="Unified AI CLI dispatcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog,
    )
    parser.add_argument("--json", "-j", action="store_true", help="JSON output (or use bare: json)")
    parser.add_argument("--cmd", "-c", action="store_true", help="Shell command only (or use bare: cmd)")
    parser.add_argument("--run", "-r", action="store_true", help="Generate + execute (or use bare: run)")
    parser.add_argument("--yolo", "-y", action="store_true", help="Auto-approve edits (or use bare: yolo)")
    parser.add_argument("--completions", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("args", nargs="*", metavar="[model] prompt", help="Model alias and/or prompt text")
    return parser


def normalize_args(argv: list[str]) -> list[str]:
    """Convert legacy bare keywords to flags for backwards compat."""
    flag_words = {"json": "--json", "cmd": "--cmd", "run": "--run", "yolo": "--yolo"}
    return [flag_words.get(arg, arg) for arg in argv]


def _is_provider_model_format(arg: str) -> bool:
    """Check if arg is in provider:model format with a valid provider."""
    if ":" not in arg:
        return False
    provider = arg.split(":", 1)[0]
    return provider in KNOWN_PROVIDERS


def dispatch(provider: str, model: str, prompt: str, json_output: bool, yolo: bool = False) -> str:
    """Dispatch to appropriate handler."""
    from .providers import get_provider_instance
    provider_instance = get_provider_instance(provider)
    return provider_instance.call(model, prompt, json_output=json_output, yolo=yolo)


def dispatch_multi(aliases: list[str], prompt: str, config: Config, json_output: bool = False) -> None:
    """Run multiple models in parallel and print labeled results."""

    def call_model(alias: str) -> tuple[str, str, float, str | None]:
        """Call a single model, return (alias, result, elapsed, error)."""
        start = time.time()
        try:
            provider, model = resolve_alias(alias, config)
            result = dispatch(provider, model, prompt, json_output)
            return (alias, result, time.time() - start, None)
        except Exception as e:
            return (alias, "", time.time() - start, str(e))

    # Run all models in parallel
    results: dict[str, tuple[str, float, str | None]] = {}
    with ThreadPoolExecutor(max_workers=len(aliases)) as executor:
        futures = {executor.submit(call_model, alias): alias for alias in aliases}
        for future in as_completed(futures):
            alias, result, elapsed, error = future.result()
            results[alias] = (result, elapsed, error)

    # Print results in original order with labels
    for i, alias in enumerate(aliases):
        result, elapsed, error = results[alias]
        # Header with alias and timing
        print(f"\033[1;36m━━━ {alias} \033[0;90m({elapsed:.1f}s)\033[1;36m ━━━\033[0m")
        if error:
            print(f"\033[31mError: {error}\033[0m")
        else:
            print(result)
        # Add spacing between models (but not after last)
        if i < len(aliases) - 1:
            print()


def main() -> None:
    """Main CLI entry point."""
    argv = sys.argv[1:]

    # Handle --completions flag early
    if "--completions" in argv:
        for word in get_completion_words():
            print(word)
        return

    # Handle subcommands before argparse
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
        if argv[0] == "completions":
            handle_completions(argv[1:])
            return
        if argv[0] == "serve":
            from .server import run_server
            # Parse serve options: serve [port] [--token TOKEN] [--no-auth]
            port = 8765
            token = None
            no_auth = False
            i = 1
            while i < len(argv):
                if argv[i] == "--token" and i + 1 < len(argv):
                    token = argv[i + 1]
                    i += 2
                elif argv[i] == "--no-auth":
                    no_auth = True
                    i += 1
                elif argv[i].isdigit():
                    port = int(argv[i])
                    if not (1 <= port <= 65535):
                        die(f"Invalid port {port}: must be between 1 and 65535")
                    i += 1
                else:
                    i += 1
            run_server(port=port, token=token, no_auth=no_auth)
            return

    config = load_config()

    # Show help for no args (unless piping stdin with a default set)
    if not argv:
        if config.default_alias and not sys.stdin.isatty():
            pass
        else:
            create_parser().print_help()
            return

    parser = create_parser()
    args = parser.parse_intermixed_args(normalize_args(argv))

    aliases = config.aliases
    positionals = args.args

    # Consume consecutive leading aliases (for multi-model mode)
    model_args: list[str] = []
    prompt_start = 0
    for i, arg in enumerate(positionals):
        if arg in aliases or _is_provider_model_format(arg):
            model_args.append(arg)
            prompt_start = i + 1
        else:
            break

    # Determine prompt from remaining args or stdin
    if prompt_start < len(positionals):
        prompt = " ".join(positionals[prompt_start:])
    elif not sys.stdin.isatty():
        prompt = sys.stdin.read().strip()
    elif model_args:
        die("prompt required (as argument or via stdin)")
    else:
        prompt = ""

    # Handle no models specified
    if not model_args:
        default_alias = config.default_alias
        if default_alias:
            if positionals:
                # Check if first arg looks like a model alias attempt (short, no spaces)
                first = positionals[0]
                if len(first) <= 20 and first.replace("-", "").replace("_", "").isalnum():
                    die(f"unknown model '{first}'. Run 'ai list' to see available models.")
                # Otherwise treat all positionals as prompt
                model_args = [default_alias]
                prompt = " ".join(positionals)
            elif prompt:
                model_args = [default_alias]
            else:
                die("model or prompt required")
        else:
            if positionals:
                die(f"unknown model '{positionals[0]}'. Run 'ai list' to see available models.",
                    hint="Set a default with 'ai default <alias>' to use 'ai \"prompt\"' directly.")
            else:
                die("model or prompt required")

    # Multi-model mode: run in parallel
    if len(model_args) > 1:
        if args.cmd or args.run:
            die("--cmd and --run not supported with multiple models")
        if args.yolo:
            die("--yolo not supported with multiple models")
        try:
            dispatch_multi(model_args, prompt, config, args.json)
        except KeyboardInterrupt:
            print("\nInterrupted", file=sys.stderr)
            sys.exit(130)
        return

    # Single model mode (existing behavior)
    model_arg = model_args[0]
    try:
        provider, model = resolve_alias(model_arg, config)
    except UnknownAliasError:
        die(f"unknown model '{model_arg}'. Run 'ai list' to see available models.")

    # Wrap prompt for cmd/run mode
    if args.cmd or args.run:
        os_name = platform.system()
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
            print(f"\033[90m$ \033[0m\033[1m{result}\033[0m")
            if not args.yolo:
                try:
                    print("\033[90m[Enter/Space] run, [Esc/n] cancel: \033[0m", end="", flush=True)
                    key = read_keypress()
                    print()
                    if key is None:
                        response = input().strip().lower()
                        if response in ("n", "no"):
                            print("Cancelled.")
                            return
                    elif key in ('esc', 'n', 'N', '\x03'):
                        print("Cancelled.")
                        return
                    elif key not in ('\r', '\n', ' ', 'y', 'Y'):
                        print("Cancelled.")
                        return
                except (KeyboardInterrupt, EOFError):
                    print("\nCancelled.")
                    return
            exec_result = subprocess.run(result, shell=True)
            sys.exit(exec_result.returncode)
        else:
            print(result)
    except AIError as e:
        die(e.message, e.hint)
    except RuntimeError as e:
        die(str(e))
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
