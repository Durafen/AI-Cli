# ai-cli

One command for all your AI CLI tools. No API keys required.

```bash
ai sonnet "explain this code"
ai gemini "write a haiku"
ai llama-3.3 "review my PR"
```

## Why?

**Uses your existing CLI subscriptions** - not API tokens. If you have Claude Code, Gemini CLI, or Codex installed, this tool dispatches to them directly. No per-token costs, no API key management.

Instead of remembering different CLI tools and flags:
```bash
claude --print --model sonnet ...
gemini --model gemini-2.5-flash ...
codex exec --model gpt-5.2-codex ...
```

Just use:
```bash
ai <model> "prompt"
```

## Features

- **No API keys** - uses your existing CLI tools (Claude, Gemini, Codex, Qwen, Ollama)
- **One command** for all providers
- **Smart aliases** - `llama-3.3` instead of `meta-llama/llama-3.3-70b-instruct:free`
- **Auto-discovery** - `ai init` detects installed tools and fetches available models
- **Free OpenRouter models** - 31 free cloud models when you need them
- **Stdin support** - `cat code.py | ai sonnet "review this"`

## Installation

```bash
# Make executable
chmod +x ai.py

# Create symlink to make 'ai' available globally
ln -sf "/path/to/ai-cli/ai.py" /usr/local/bin/ai

# Initialize (detect installed tools + fetch models)
ai init
```

For OpenRouter free models (optional):
```bash
echo "OPENROUTER_API_KEY=your-key-here" > .env
ai init  # re-run to fetch free models
```

## Usage

```bash
# Basic usage
ai sonnet "Explain recursion"
ai gemini "Write a haiku"
ai llama-3.3 "Code review this"

# Set a default model
ai default sonnet

# Use default model (no alias needed)
ai "Explain recursion"

# JSON output
ai json sonnet "Return structured data"

# Get terminal command
ai cmd "list all docker containers"

# Stdin for large prompts
cat file.txt | ai haiku

# List available models
ai list

# Re-initialize to update models
ai init
```

### Zsh users

If prompts with `?`, `*`, or other special characters fail, add this to `~/.zshrc`:

```bash
alias ai='noglob ai'
```

This lets you type `ai sonnet "what's up?"` without quoting.

## Supported Providers

### CLI Tools (no API keys)

| Provider | Aliases | Models |
|----------|---------|--------|
| **Claude** (Anthropic) | `haiku`, `sonnet`, `opus` | haiku, sonnet, opus |
| **Codex** (OpenAI) | `gpt`, `gpt-max`, `gpt-mini` | gpt-5.2-codex, gpt-5.1-codex-max, gpt-5.1-codex-mini |
| **Gemini** (Google) | `pro`, `flash`, `pro-2.5`, `flash-2.5` | gemini-3-pro-preview, gemini-3-flash-preview, gemini-2.5-* |
| **Qwen** (Alibaba) | `qwen`, `qwen-vision` | coder-model, vision-model |
| **Ollama** (local) | Auto-generated | Detected via `ollama list` |

### OpenRouter (free models)

31 free models fetched from OpenRouter API. Smart aliases auto-generated:

```
ai trinity       # arcee-ai/trinity-mini:free
ai glm           # z-ai/glm-4.5-air:free
ai llama-3.3     # meta-llama/llama-3.3-70b-instruct:free
ai mistral       # mistralai/mistral-7b-instruct:free
ai deepseek-r1   # deepseek/deepseek-r1-0528:free
```

## Example output

```
$ ai list
Available models:

  claude: (3)
    haiku
    sonnet
    opus

  codex: (4)
    gpt                  -> gpt-5.2-codex
    gpt-max              -> gpt-5.1-codex-max
    gpt-mini             -> gpt-5.1-codex-mini
    gpt-5.2

  gemini: (5)
    pro                  -> gemini-3-pro-preview
    flash                -> gemini-3-flash-preview
    ...

  openrouter: (31)
    trinity              -> arcee-ai/trinity-mini:free
    glm                  -> z-ai/glm-4.5-air:free
    llama-3.3            -> meta-llama/llama-3.3-70b-instruct:free
    ...

Installed CLI tools: codex, claude, gemini, qwen, ollama

Default model: sonnet
```

## How it works

1. `ai init` detects installed CLI tools and fetches available models
2. Auto-generates short aliases from model names
3. On each call, resolves alias → (provider, model)
4. Dispatches to the appropriate CLI tool via subprocess
5. Returns output

## License

MIT
