# CLAUDE.md

## Project Overview

**ai-cli** is a unified CLI dispatcher that routes prompts to multiple AI backends (Claude, Codex, Gemini, Qwen, Ollama, OpenRouter) via short model aliases. Single-file Python tool with no dependencies beyond stdlib (optional: python-dotenv).

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

# Stdin input
cat file.txt | ai <alias>
```

## Architecture

Single-file architecture (`ai.py`):

1. **Config**: `~/.ai-cli/config.json` stores installed_tools, models, aliases, default_alias
2. **Aliases**: Resolve short names → (provider, model) tuples
3. **Reserved**: `RESERVED_COMMANDS` prevents conflicts with subcommands (init, list, default, cmd, json, help, yolo, run)
4. **Dispatch**: Route to provider-specific `call_*()` functions
5. **Handlers**: CLI tools use subprocess; OpenRouter uses urllib HTTP API

Key flow: `main()` → `resolve_alias()` → `dispatch()` → `call_<provider>()`

## Provider Details

| Provider | Handler | YOLO Flag |
|----------|---------|-----------|
| claude | subprocess `claude --print --model` | `--dangerously-skip-permissions` |
| codex | subprocess `codex exec --model` | `-s danger-full-access -a never` |
| gemini | subprocess `gemini --model` | `--yolo` |
| qwen | subprocess `qwen --model` | `--yolo` |
| ollama | subprocess `ollama run` | (ignored) |
| openrouter | urllib HTTP | (ignored) |

## Environment

- `OPENROUTER_API_KEY` in `.env` (same dir as ai.py) or environment
- `.env` loads via python-dotenv if installed

## Alias Generation (on `init`)

- **CLI tools**: Static mappings in `DEFAULT_ALIASES` + `KNOWN_MODELS`
- **Ollama**: Auto-generated from `ollama list` output
- **OpenRouter**: Smart shortening removes version suffixes (`-v2`, `-3.1`), common suffixes (`-instruct`, `-flash`), handles conflicts
