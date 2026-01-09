# ai-cli

Unified CLI tool that dispatches prompts to different AI CLI tools based on model alias.

## Installation

```bash
# Make executable
chmod +x ai.py

# Create symlink to make 'ai' available globally
ln -sf "/path/to/ai-cli/ai.py" /usr/local/bin/ai

# Setup OpenRouter API key (for free cloud models)
echo "OPENROUTER_API_KEY=your-key-here" > .env

# Initialize (detect installed tools + fetch models)
ai init
```

## Usage

```bash
# Basic usage with short aliases
ai sonnet "Explain recursion"
ai gemini "Write a haiku"
ai kimi-k2 "Hello world"
ai llama-3.3-70b-instruct "Code review this"

# JSON output
ai --json sonnet "Return structured data"

# Stdin for large prompts
cat file.txt | ai haiku
echo "prompt" | ai gpt

# List available models
ai --list

# Re-initialize to update models
ai init
```

## Supported Providers

### CLI Tools (subprocess)

| Provider | Aliases | Models |
|----------|---------|--------|
| **Claude** (Anthropic) | `haiku`, `sonnet`, `opus` | haiku, sonnet, opus |
| **Codex** (OpenAI) | `gpt`, `gpt-max`, `gpt-mini` | gpt-5.2-codex, gpt-5.1-codex-max, gpt-5.1-codex-mini, gpt-5.2 |
| **Gemini** (Google) | `pro`, `flash`, `flash-lite`, `gemini-preview` | gemini-3-pro-preview, gemini-3-flash-preview, gemini-2.5-pro, gemini-2.5-flash, gemini-2.5-flash-lite |
| **Qwen** (Alibaba) | `qwen`, `qwen-vision` | coder-model, vision-model |
| **Ollama** (local) | Auto-generated from model names | Dynamically detected via `ollama list` |

### OpenRouter API (FREE models only)

All free models are fetched dynamically from OpenRouter API during `ai init`.
Aliases are auto-generated from model names:

```
xiaomi/mimo-v2-flash:free      → mimo
meta-llama/llama-3.3-70b-instruct:free → llama-3.3-70b-instruct
qwen/qwen3-coder:free          → qwen3-coder
moonshotai/kimi-k2:free        → kimi-k2
```

Use any free model directly:
```bash
ai kimi-k2 "hello"
ai llama-3.3-70b-instruct "explain this code"
ai qwen3-coder "write a function"
```

## Configuration

### Config file: `~/.ai-cli/config.json`

Created by `ai init`. Contains:
- `installed_tools` - detected CLI tools
- `models` - available models per provider
- `aliases` - auto-generated shortcut mappings

### Environment: `.env`

Place in the ai-cli directory (same folder as ai.py):
```
OPENROUTER_API_KEY=sk-or-...
```

## How it works

1. `ai init` detects installed CLI tools and fetches available models
2. Auto-generates short aliases from model names
3. On each call, resolves alias → (provider, model)
4. Dispatches to appropriate handler:
   - **CLI tools**: subprocess call to `claude`, `codex`, `gemini`, `qwen`, `ollama`
   - **OpenRouter**: HTTP API call (free models only, enforces `:free` suffix)
5. Returns output

## Example output

```
$ ai --list
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

  openrouter: (31)
    mimo                 -> xiaomi/mimo-v2-flash:free
    kimi-k2              -> moonshotai/kimi-k2:free
    llama-3.3-70b-instruct -> meta-llama/llama-3.3-70b-instruct:free
    qwen3-coder          -> qwen/qwen3-coder:free
    ...

Installed CLI tools: codex, claude, gemini, qwen, ollama
```

## License

MIT
