# CLAUDE.md

## Project Overview

**ai-cli** is a unified CLI dispatcher and Python library that routes prompts to multiple AI backends (Claude, Codex, Gemini, Qwen, Ollama, OpenRouter) via short model aliases. Modular Python package with no dependencies beyond stdlib (optional: python-dotenv).

## Commands

```bash
# Run directly
python3 ai.py <alias> "prompt"

# Via symlink (if installed)
ai <alias> "prompt"

# Use default model (if set)
ai "prompt"

# Set/get default model
ai default sonnet
ai default

# Initialize (detect CLIs + fetch OpenRouter free models)
ai init

# List all available aliases and models
ai list

# JSON output mode
ai json <alias> "prompt"

# Get terminal command (print only)
ai cmd "list docker containers"

# Generate command, confirm, then execute
ai run "list docker containers"
ai sonnet run "list docker containers"  # model first also works
ai run -y "list docker containers"      # skip confirmation

# YOLO mode (auto-approve file edits)
ai yolo <alias> "refactor main.py"

# Start HTTP server (for JS/cross-language access)
ai serve [port]  # default: 8765

# Stdin input
cat file.txt | ai <alias>
```

## Library Usage

```python
from ai_cli import AIClient

client = AIClient()
response = client.call("sonnet", "Explain Python's GIL")

# With options
response = client.call("opus", "List 3 colors", json_mode=True)

# List available models
for alias, (provider, model) in client.list_models().items():
    print(f"{alias} -> {provider}:{model}")

# Direct provider access
from ai_cli.providers import ClaudeProvider
claude = ClaudeProvider()
result = claude.call("sonnet", "Hello!")
```

## Architecture

Modular package structure:

```
ai_cli/
├── __init__.py          # Public API: AIClient, exceptions
├── client.py            # AIClient class - main library interface
├── config.py            # Config class (load/save, no globals)
├── aliases.py           # Alias resolution logic
├── constants.py         # RESERVED_COMMANDS, DEFAULT_ALIASES
├── exceptions.py        # AIError, UnknownAliasError, ProviderError
├── cli.py               # CLI entry point (main)
├── server.py            # HTTP server for cross-language access
└── providers/
    ├── __init__.py      # Provider registry, get_provider()
    ├── base.py          # Provider protocol + BaseProvider ABC
    ├── cli.py           # CLIProvider base for subprocess providers
    ├── claude.py        # Claude provider
    ├── codex.py         # Codex provider
    ├── gemini.py        # Gemini provider
    ├── qwen.py          # Qwen provider
    ├── ollama.py        # Ollama provider
    └── openrouter.py    # OpenRouter HTTP provider
```

**Key flows:**
- CLI: `ai.py` → `cli.main()` → `resolve_alias()` → `dispatch()` → `Provider.call()`
- Library: `AIClient.call()` → `resolve_alias()` → `Provider.call()`
- HTTP: `server.py` → `AIClient.call()` → `Provider.call()`

## Provider Details

| Provider | Type | Handler | YOLO Flag |
|----------|------|---------|-----------|
| claude | CLI | subprocess `claude --print --model` | `--dangerously-skip-permissions` |
| codex | CLI | subprocess `codex exec --model` | `-s danger-full-access -a never` |
| gemini | CLI | subprocess `gemini --model` | `--yolo` |
| qwen | CLI | subprocess `qwen --model` | `--yolo` |
| ollama | CLI | subprocess `ollama run` | (ignored) |
| openrouter | HTTP | urllib to OpenRouter API | (ignored) |

All CLI providers inherit from `CLIProvider` base class with shared command-building logic.

## Environment

- `OPENROUTER_API_KEY` in `.env` (same dir as ai.py) or environment
- `.env` loads via python-dotenv if installed, or manual parsing fallback
- Config stored at `~/.ai-cli/config.json`

## Alias Generation (on `init`)

- **CLI tools**: Static mappings in `DEFAULT_ALIASES` + provider `KNOWN_MODELS`
- **Ollama**: Auto-generated from `ollama list` output via `OllamaProvider.generate_aliases()`
- **OpenRouter**: Smart shortening via `OpenRouterProvider.shorten_name()`, handles conflicts

## HTTP Server

For cross-language access (JavaScript, etc.):

```bash
ai serve 8765
```

Endpoints:
- `GET /health` - Health check
- `GET /models` - List available models
- `GET /providers` - List providers
- `POST /call` - Execute prompt `{"alias": "sonnet", "prompt": "..."}`
