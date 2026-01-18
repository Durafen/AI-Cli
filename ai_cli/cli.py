"""CLI entry point and command handling for ai-cli."""

import argparse
import platform
import os
import re
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
    flags = ["--json", "--cmd", "--run", "--yolo", "--no-chat", "--reply", "-j", "-c", "-r", "-y"]
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
  ai sonnet "explain this"      Start new chat (auto-saves)
  ai chat ABC "continue"        Continue chat ABC
  ai reply "continue"           Continue most recent chat
  ai sonnet reply "switch"      Continue last chat with different model
  ai chat list                  List all chat sessions
  ai chat delete ABC            Delete chat session(s)
  ai json sonnet "return JSON"  JSON output mode
  ai cmd "list docker"          Shell command only
  ai run "stop nginx"           Generate + execute
  ai serve                      Start HTTP server
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
    parser.add_argument("--no-chat", action="store_true", help="Skip chat creation for one-off queries")
    parser.add_argument("--reply", action="store_true", help="Reply to most recent chat (or use bare: reply)")
    parser.add_argument("--completions", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("args", nargs="*", metavar="[model] prompt", help="Model alias and/or prompt text")
    return parser


def normalize_args(argv: list[str]) -> list[str]:
    """Convert legacy bare keywords to flags for backwards compat."""
    flag_words = {"json": "--json", "cmd": "--cmd", "run": "--run", "yolo": "--yolo", "reply": "--reply"}
    return [flag_words.get(arg, arg) for arg in argv]


def _is_provider_model_format(arg: str) -> bool:
    """Check if arg is in provider:model format with a valid provider."""
    if ":" not in arg:
        return False
    provider = arg.split(":", 1)[0]
    return provider in KNOWN_PROVIDERS


def detect_chat_mode(argv: list[str], config: Config) -> dict:
    """
    Detect and parse chat mode from command line arguments.

    Returns:
        Dict with keys:
        - 'mode': 'chat' or None
        - 'reply_mode': bool
        - 'subcommand': 'list', 'delete', or None
        - 'chat_id': 3-char code or None
        - 'chat_ids': list of 3-char codes (for bulk delete)
        - 'model': model alias or None
        - 'remaining_args': args to process after chat extraction
    """
    import re
    result = {
        'mode': None,
        'reply_mode': False,
        'subcommand': None,
        'chat_id': None,
        'chat_ids': [],
        'model': None,
        'remaining_args': argv.copy()
    }

    def is_valid_chat_id(s: str) -> bool:
        return bool(re.fullmatch(r'[A-Za-z0-9]{3}', s))

    def normalize_chat_id(s: str) -> str:
        return s.upper()

    # 1. Detect 'reply' mode (keyword or flag)
    reply_idx = None
    if '--reply' in argv:
        reply_idx = argv.index('--reply')
    elif len(argv) > 0 and argv[0] == 'reply':
        reply_idx = 0
    elif len(argv) > 1 and argv[1] == 'reply' and (argv[0] in config.aliases or _is_provider_model_format(argv[0])):
        reply_idx = 1

    if reply_idx is not None:
        result['reply_mode'] = True
        before = argv[:reply_idx]
        after = argv[reply_idx+1:]
        if before:
            potential_model = before[-1]
            if potential_model in config.aliases or _is_provider_model_format(potential_model):
                result['model'] = potential_model
                before = before[:-1]
        result['remaining_args'] = before + after
        return result

    # 2. Detect 'chat' mode (keyword or flag)
    chat_idx = None
    if '--chat' in argv:
        chat_idx = argv.index('--chat')
    elif len(argv) > 0 and argv[0] == 'chat':
        chat_idx = 0
    elif len(argv) > 1 and argv[1] == 'chat' and (argv[0] in config.aliases or _is_provider_model_format(argv[0])):
        chat_idx = 1

    if chat_idx is not None:
        before = argv[:chat_idx]
        after = argv[chat_idx+1:]

        # Extract model from before
        if before:
            potential_model = before[-1]
            if potential_model in config.aliases or _is_provider_model_format(potential_model):
                result['model'] = potential_model
                before = before[:-1]

        if not after:
            result['mode'] = 'chat'
            result['remaining_args'] = before
            return result

        next_arg = after[0]
        if next_arg == 'list':
            result['mode'] = 'chat'
            result['subcommand'] = 'list'
            result['remaining_args'] = before + after[1:]
            return result
        elif next_arg == 'delete':
            result['mode'] = 'chat'
            result['subcommand'] = 'delete'
            chat_ids = []
            i = 1
            while i < len(after):
                potential_id = after[i]
                if is_valid_chat_id(potential_id):
                    chat_ids.append(normalize_chat_id(potential_id))
                    i += 1
                else:
                    break
            result['chat_ids'] = chat_ids
            if chat_ids:
                result['chat_id'] = chat_ids[0]
            result['remaining_args'] = before + after[i:]
            return result
        elif is_valid_chat_id(next_arg):
            result['mode'] = 'chat'
            result['chat_id'] = normalize_chat_id(next_arg)
            result['remaining_args'] = before + after[1:]
            return result
        elif argv[chat_idx] == '--chat':
            result['mode'] = 'chat'
            result['remaining_args'] = before + after
            return result

    return result


def dispatch(provider: str, model: str, prompt: str, json_output: bool, yolo: bool = False) -> str:
    """Dispatch to appropriate handler."""
    from .providers import get_provider_instance
    provider_instance = get_provider_instance(provider)
    return provider_instance.call(model, prompt, json_output=json_output, yolo=yolo)


def dispatch_multi(aliases: list[str], prompt: str, config: Config, json_output: bool = False) -> None:
    """Run multiple models in parallel and print labeled results."""

    def call_model(alias: str) -> tuple[str, str, float, str | None]:
        """Call a single model, return (alias, result, elapsed, error)."""
        import time
        start = time.time()
        try:
            from .aliases import resolve_alias
            provider, model = resolve_alias(alias, config)
            result = dispatch(provider, model, prompt, json_output)
            return (alias, result, time.time() - start, None)
        except Exception as e:
            return (alias, "", time.time() - start, str(e))

    import time
    from concurrent.futures import ThreadPoolExecutor, as_completed
    results: dict[str, tuple[str, float, str | None]] = {}
    with ThreadPoolExecutor(max_workers=len(aliases)) as executor:
        futures = {executor.submit(call_model, alias): alias for alias in aliases}
        for future in as_completed(futures):
            alias, result, elapsed, error = future.result()
            results[alias] = (result, elapsed, error)

    for i, alias in enumerate(aliases):
        result, elapsed, error = results[alias]
        print(f"[1;36m━━━ {alias} [0;90m({elapsed:.1f}s)[1;36m ━━━[0m")
        if error:
            print(f"[31mError: {error}[0m")
        else:
            print(result)
        if i < len(aliases) - 1:
            print()


def main() -> None:
    """Main CLI entry point."""
    argv = sys.argv[1:]

    if "--completions" in argv:
        for word in get_completion_words():
            print(word)
        return

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
    original_argv = argv.copy()
    chat_info = detect_chat_mode(argv, config)

    # Handle empty 'ai reply' - show last exchange or helpful message
    if chat_info['reply_mode'] and not any(arg not in ["--reply", "--json", "--cmd", "--run", "--yolo", "--no-chat"] for arg in argv):
        from .chat import ChatManager
        session = ChatManager.get_latest()
        if not session:
            die("No chat sessions to reply to. Start one with 'ai <model> <msg>'")
        if session.messages:
            last_msg = session.messages[-1]
            print(f"Chat: {session.chat_id} (model: {session.model_alias})")
            print(f"Last {last_msg.role.upper()}: {last_msg.content}")
        else:
            print(f"Chat: {session.chat_id} (model: {session.model_alias})")
            print("No messages yet.")
        return

    if chat_info['subcommand']:
        from .chat import ChatManager
        if chat_info['subcommand'] == 'list':
            sessions = ChatManager.list_all()
            if not sessions:
                print("No chat sessions found.")
            else:
                max_id = max(len(s.chat_id) for s in sessions) if sessions else 3
                max_model = max(len(s.model_alias) for s in sessions) if sessions else 5
                max_created = 19
                max_count = max(len(str(len(s.messages))) for s in sessions) if sessions else 1
                id_width = max(max_id, 2)
                model_width = max(max_model, 5)
                created_width = max_created
                count_width = max(max_count, 12)
                header = f" {'ID':<{id_width}} | {'Model':<{model_width}} | {'Created':<{created_width}} | {'Message Count':<{count_width}}"
                print(header)
                print("-" * len(header))
                for session in sessions:
                    msg_count = len(session.messages)
                    created = session.created_at[:19]
                    print(f" {session.chat_id:<{id_width}} | {session.model_alias:<{model_width}} | {created:<{created_width}} | {msg_count:>{count_width}}")
            return
        elif chat_info['subcommand'] == 'delete':
            chat_ids = chat_info.get('chat_ids', [])
            if not chat_ids:
                die("chat delete requires at least one chat ID", hint="Usage: ai chat delete <CODE> [<CODE> ...]")
            deleted = []
            not_found = []
            for chat_id in chat_ids:
                if ChatManager.delete(chat_id):
                    deleted.append(chat_id)
                else:
                    not_found.append(chat_id)
            if deleted:
                for chat_id in deleted:
                    print(f"Deleted chat session: {chat_id}")
            if not_found:
                for chat_id in not_found:
                    print(f"Chat session '{chat_id}' not found", file=sys.stderr)
                sys.exit(1)
            return

    if (chat_info['chat_id'] or chat_info['reply_mode']) and not chat_info['subcommand']:
        from .chat import ChatManager
        if chat_info['chat_id'] and ChatManager.load(chat_info['chat_id']) is None:
            die(f"Chat session '{chat_info['chat_id']}' not found")
        argv = ([(chat_info['model'])] if chat_info['model'] else []) + chat_info['remaining_args']
    elif chat_info['remaining_args'] != original_argv:
        argv = chat_info['remaining_args']

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
    model_args: list[str] = []
    prompt_start = 0
    for i, arg in enumerate(positionals):
        if arg in aliases or _is_provider_model_format(arg):
            model_args.append(arg)
            prompt_start = i + 1
        else:
            break

    if prompt_start < len(positionals):
        prompt = " ".join(positionals[prompt_start:])
    elif not sys.stdin.isatty():
        prompt = sys.stdin.read().strip()
    elif model_args:
        die("prompt required (as argument or via stdin)")
    else:
        prompt = ""

    if not model_args:
        default_alias = config.default_alias
        if default_alias:
            if positionals:
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

    if len(model_args) > 1:
        if args.cmd or args.run:
            die("--cmd and --run not supported with multiple models")
        if args.yolo:
            die("--yolo not supported with multiple models")
        # Chat is disabled in multi-model mode
        if chat_info['chat_id'] or chat_info['reply_mode']:
            print("Note: Chat mode is disabled when using multiple models", file=sys.stderr)
        try:
            dispatch_multi(model_args, prompt, config, args.json)
        except KeyboardInterrupt:
            print("\nInterrupted", file=sys.stderr); sys.exit(130)
        return

    model_arg = model_args[0]
    model_explicit = bool(chat_info['model'])
    if not model_explicit and chat_info['remaining_args'] and chat_info['remaining_args'][0] == model_arg:
        model_explicit = True

    from .chat import ChatManager
    chat_id = None
    session = None
    # Skip chat creation for --no-chat flag or multi-model (already handled)
    if args.no_chat:
        session = None
    elif chat_info['chat_id']:
        session = ChatManager.load(chat_info['chat_id'])
        if not model_explicit: model_arg = session.model_alias
        chat_id = session.chat_id
    elif chat_info['reply_mode']:
        session = ChatManager.get_latest()
        if not session:
            die("No chat sessions to reply to. Start one with 'ai <model> <msg>'")
        if not model_explicit: model_arg = session.model_alias
        chat_id = session.chat_id
    else:
        # Always create chat for normal prompts
        session = ChatManager.create(model_arg)
        chat_id = session.chat_id

    try:
        from .aliases import resolve_alias
        provider, model = resolve_alias(model_arg, config)
    except UnknownAliasError:
        die(f"unknown model '{model_arg}'. Run 'ai list' to see available models.")

    if session:
        session.enforce_limit()
        original_prompt = prompt
        history = session.format_history()
        if history: prompt = f"{history}\n\nUSER: {prompt}"
        else: prompt = f"USER: {prompt}"

    if args.cmd or args.run:
        import platform
        os_name = platform.system()
        shell = os.path.basename(os.environ.get("SHELL", "sh"))
        prompt = (f"[SYSTEM: OS={os_name}, Shell={shell}. OUTPUT MODE: Your entire response "
                  "will be piped directly to /bin/sh for execution. Return ONLY a single "
                  "shell command. Any text that is not a valid command will cause an error. "
                  f"No prose, no markdown, no explanation.]\n\n{prompt}")

    try:
        result = dispatch(provider, model, prompt, args.json, args.yolo if not args.run else False)
        if session:
            session.add_message("user", original_prompt)
            session.add_message("assistant", result)
            session.model_alias = model_arg
            session.save()
        if args.cmd or args.run:
            result = sanitize_command(result)
        footer = ""
        if chat_id:
            # Footer to stderr for pipes, cmd mode, or json mode
            if args.json or args.cmd or not sys.stdout.isatty():
                print(f"[Chat: {chat_id}]", file=sys.stderr)
            else:
                footer = f"\n\n[Chat: {chat_id}]"
        if args.run:
            print(f"[90m$ [0m[1m{result}[0m{footer}")
            if not args.yolo:
                try:
                    print("[90m[Enter/Space] run, [Esc/n] cancel: [0m", end="", flush=True)
                    key = read_keypress(); print()
                    if key is None:
                        response = input().strip().lower()
                        if response in ("n", "no"): print("Cancelled."); return
                    elif key in ('esc', 'n', 'N', '\x03'): print("Cancelled."); return
                    elif key not in ('\r', '\n', ' ', 'y', 'Y'): print("Cancelled."); return
                except (KeyboardInterrupt, EOFError): print("\nCancelled."); return
            import subprocess
            exec_result = subprocess.run(result, shell=True)
            sys.exit(exec_result.returncode)
        else:
            print(f"{result}{footer}")
    except AIError as e: die(e.message, e.hint)
    except RuntimeError as e: die(str(e))
    except KeyboardInterrupt: print("\nInterrupted", file=sys.stderr); sys.exit(130)

if __name__ == "__main__":
    main()
