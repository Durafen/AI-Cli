# Orchestration Progress

## Configuration
- Planning Model: TBD
- Coding Model: TBD
- Review Model: TBD
- Started: 2025-01-17

## Requirements Summary

### Feature Request
**Persistent Chat Mode**: `ai chat` command/flag that maintains conversation history across multiple independent CLI calls.
*Note: This is NOT an interactive REPL loop. It allows "stateless" CLI tools to have stateful conversations by reloading history.*

### Project Context
This is **ai-cli** - a unified CLI dispatcher that routes prompts to multiple AI backends (Claude, Codex, Gemini, Qwen, Ollama, OpenRouter) via short model aliases.

Current architecture:
- `cli.py` - Main CLI entry point with argparse
- `client.py` - AIClient library interface
- `config.py` - Config dataclass with JSON persistence at `~/.ai-cli/config.json`
- `providers/` - Provider implementations (CLI subprocess + HTTP)

### Command Pattern (from existing codebase)
- Subcommands: `init`, `list`, `default`, `completions`, `serve`
- Model aliases come first, then prompt
- Flags: `--json`, `--cmd`, `--run`, `--yolo`
- Reserved commands defined in `constants.py`

## Status: PLAN REVISION (Review Feedback Integration)

## Project Structure

### New Modules
- **`ai_cli/chat.py`**: Handles chat session management, persistence, and history formatting.
    - `ChatSession`: Class to manage individual chat history (load/save/update/truncate).
    - `ChatManager`: Class to manage, list, and delete chat sessions.

### Modifications
- **`ai_cli/constants.py`**: Add `chat` to `RESERVED_COMMANDS`.
- **`ai_cli/cli.py`**:
    - Update parsing logic to detect `chat` keyword or flag.
    - Handle new subcommands: `list`, `delete`.
    - Integrate `ChatSession` to load history, format prompt, and save response.
- **`ai_cli/config.py`**: No changes needed (chat storage is separate).

## Task Breakdown

### Task 1: Chat Core Logic (`ai_cli/chat.py`)
- **Goal**: Implement `ChatSession` and `ChatManager` for managing conversation history.
- **Scope**:
    - Define `ChatConfig` (paths).
    - `ChatSession` class:
        - `__init__(id, model, provider)`
        - `add_message(role, content)`
        - `save()` / `load(id)`
        - `format_history()` -> returns string transcript.
        - **Context Management**: Implement sliding window (keep last N messages or approx char count) to prevent context overflow.
    - `ChatManager` class:
        - `list_chats()` -> returns list of existing chat IDs/metadata.
        - `delete_chat(id)` -> removes the chat file.
        - `get_chat_path(id)`.
    - `generate_chat_id()` -> 3-char unique ID.
- **Dependencies**: `ai_cli/constants.py` (for paths).

### Task 2: CLI Integration (`ai_cli/cli.py` & `constants.py`)
- **Goal**: Wire up the `chat` command and its variants in the CLI.
- **Scope**:
    - Add "chat" to `RESERVED_COMMANDS` in `constants.py`.
    - Modify `cli.py` `main()`:
        - Detect `chat` keyword in `positionals`.
        - **Parsing Rules** (Support all three forms):
            1. `ai <model> chat <id> <prompt>`
            2. `ai chat <id> <model> <prompt>` (Command-first style)
            3. `ai <model> --chat <id> <prompt>` (Flag style)
            - Note: `<id>` is optional. If missing, create new. If present, load.
        - **Subcommands**:
            - `ai chat list` (or `ai chat`) -> List active sessions.
            - `ai chat delete <id>` -> Delete session.
        - **Execution**:
            - Resolve model/provider.
            - Load or create `ChatSession`.
            - Construct full prompt (History + New User Prompt).
            - Call `dispatch()`.
            - Save user prompt and AI response to session.
            - Output response + `[Chat: <ID>]` (to remind user of the ID).
- **Dependencies**: Task 1.

## Technical Details

### `ai_cli/chat.py`

```python
@dataclass
class Message:
    role: str  # "user" or "assistant"
    content: str
    timestamp: str

class ChatSession:
    id: str
    model: str
    provider: str
    messages: list[Message]
    
    def format_history(self) -> str:
        # 1. Truncate history if needed (e.g., keep last 10 messages or last 8000 chars)
        # 2. Format as "User: ...\nAssistant: ..."
        pass

    def enforce_limit(self):
        # Sliding window strategy
        pass
        
class ChatManager:
    def list_sessions(self) -> list[dict]:
        # Scan ~/.ai-cli/chats/*.json
        pass
        
    def delete_session(self, chat_id: str):
        # Remove file
        pass
```

### `ai_cli/cli.py`

- **Parsing Strategy**:
    - Pre-process `sys.argv` or `positionals` to normalize the command structure.
    - Check for `list` or `delete` subcommands under `chat`.
    - If `chat` is active:
        - Extract potential `chat_id` (regex: `^[A-Z0-9]{3}$`).
        - Differentiate `chat_id` from `model` (check against known aliases).
        - Use remaining text as `prompt`.

- **Execution Flow**:
    ```python
    if chat_mode:
        if chat_subcommand == "list":
             # ... show list
             return
        if chat_subcommand == "delete":
             # ... delete
             return

        session = ChatManager.get(chat_id) or ChatManager.create(model, provider)
        
        # Context Management handled in format_history
        full_prompt = session.format_history() + f"\nUser: {prompt}\nAssistant:"
        
        # Dispatch
        response = dispatch(...)
        
        # Save
        session.add_message("user", prompt)
        session.add_message("assistant", response)
        session.save()
        
        print(f"\n[Chat: {session.id}]")
    ```

## Implementation Notes

- **Format**:
    - Use standard `User:` / `Assistant:` separators.
- **IDs**:
    - Use `secrets.choice` or `random.choices` with uppercase letters + digits. 3 chars.
- **Context Limits**:
    - Since we don't have tokenizers for every provider, use a rough heuristic:
    - Default safe limit: Last ~4000 characters or ~10 messages.
    - Warn user if history is truncated (optional).
- **Session Management**:
    - Store chat files in `~/.ai-cli/chats/`.
    - `list` command should show ID, Model, Last Update, and Preview.
