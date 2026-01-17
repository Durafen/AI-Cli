# ai-cli

One command for all your AI CLI tools. No API keys required. Also usable as a Python library.

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
- **Multi-model parallel** - `ai opus pro gpt "prompt"` runs all 3 simultaneously
- **Smart aliases** - `llama-3.3` instead of `meta-llama/llama-3.3-70b-instruct:free`
- **Auto-discovery** - `ai init` detects installed tools and fetches available models
- **Run mode** - `ai run` generates a command, shows it, and executes on confirm
- **YOLO mode** - `ai yolo` auto-approves file edits across all providers
- **Free OpenRouter models** - 31 free cloud models when you need them
- **Stdin support** - `cat code.py | ai sonnet "review this"`

## Installation

```bash
# Make executable
chmod +x ai.py

# Create symlink to make 'ai' available globally
ln -sf "/path/to/ai-cli/ai.py" /usr/local/bin/ai

# Or run as a Python module (no symlink needed)
python -m ai_cli <alias> "prompt"

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

# Get terminal command (print only)
ai cmd "list all docker containers"

# Generate, confirm, and execute command
ai run "list all docker containers"
ai sonnet run "stop nginx"  # model first also works
ai run -y "stop nginx"      # skip confirmation

# YOLO mode (auto-approve file edits)
ai yolo sonnet "refactor main.py"

# Stdin for large prompts
cat file.txt | ai haiku

# List available models
ai list

# Re-initialize to update models
ai init

# Multi-model (parallel execution)
ai opus pro gpt "review this code"
ai sonnet haiku mimo "explain recursion"
```

### Multi-Model Parallel Execution

Query multiple models simultaneously and compare responses:

```bash
ai opus pro gpt "what are the pros and cons of microservices?"
```

Output:
```
━━━ opus (18.2s) ━━━
[opus response]

━━━ pro (12.1s) ━━━
[pro response]

━━━ gpt (15.3s) ━━━
[gpt response]
```

- Runs all models in parallel (total time ≈ slowest model, not sum)
- Shows timing for each response
- Errors in one model don't affect others
- Works with stdin: `echo "prompt" | ai opus pro gpt`

### Shell Completion

Tab completion for commands and model aliases:

```bash
# Zsh
echo 'eval "$(ai completions zsh)"' >> ~/.zshrc

# Bash
echo 'eval "$(ai completions bash)"' >> ~/.bashrc

# Fish
echo 'ai completions fish | source' >> ~/.config/fish/config.fish
```

Then `ai son<TAB>` completes to `ai sonnet`.

### Zsh users

If prompts with `?`, `*`, or other special characters fail, add this to `~/.zshrc`:

```bash
alias ai='noglob ai'
```

This lets you type `ai sonnet "what's up?"` without quoting.

## Library Usage

Use ai-cli as a Python library in your scripts:

```python
from ai_cli import AIClient

client = AIClient()
response = client.call("sonnet", "Explain Python's GIL")

# With options
response = client.call("opus", "List 3 colors", json_mode=True)

# Multi-model parallel
results = client.call_multi(["opus", "pro", "gpt"], "Explain X")
for alias, response in results.items():
    print(f"{alias}: {response}")

# List available models
for alias, (provider, model) in client.list_models().items():
    print(f"{alias} -> {provider}:{model}")
```

## HTTP Server (for JavaScript/other languages)

Start a local HTTP server for cross-language access:

```bash
ai serve                      # Auto-generates auth token, prints it
ai serve 3000                 # Custom port
ai serve --token mytoken      # Use specific token
AI_CLI_SERVER_TOKEN=x ai serve  # Token from env var
ai serve --no-auth            # Disable auth (not recommended)
```

The server requires Bearer token authentication. Token priority: `--token` flag > `AI_CLI_SERVER_TOKEN` env var > auto-generated.

From JavaScript:

```javascript
const TOKEN = 'your-token-here';  // printed when server starts

const response = await fetch('http://localhost:8765/call', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${TOKEN}`
  },
  body: JSON.stringify({ alias: 'sonnet', prompt: 'Hello!' })
});
const { result } = await response.json();
```

Endpoints:
- `GET /health` - Health check (no auth required)
- `GET /models` - List available models
- `GET /providers` - List providers
- `POST /call` - Execute prompt (`{alias, prompt, json_mode?, yolo?}`)

## Supported Providers

### CLI Tools (no API keys)

| Provider | Aliases | Models |
|----------|---------|--------|
| **Claude** (Anthropic) | `haiku`, `sonnet`, `opus` | haiku, sonnet, opus |
| **Codex** (OpenAI) | `gpt`, `codex-max`, `codex-mini` | gpt-5.2, gpt-5.1-codex-max, gpt-5.1-codex-mini |
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
    gpt                  -> gpt-5.2
    codex-max            -> gpt-5.1-codex-max
    codex-mini           -> gpt-5.1-codex-mini
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
4. Dispatches to the appropriate provider (CLI subprocess or HTTP API)
5. Returns output

### Architecture

```
ai_cli/
├── client.py        # AIClient - library interface
├── providers/       # Provider implementations
│   ├── claude.py    # Claude CLI
│   ├── codex.py     # Codex CLI
│   ├── gemini.py    # Gemini CLI
│   ├── qwen.py      # Qwen CLI
│   ├── ollama.py    # Ollama CLI
│   └── openrouter.py # OpenRouter HTTP
├── cli.py           # CLI entry point
└── server.py        # HTTP server
```

## License

MIT
