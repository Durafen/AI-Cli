"""Chat session management for persistent conversation history."""

import json
import re
import secrets
import string
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .constants import CONFIG_DIR


CHATS_DIR = CONFIG_DIR / "chats"


@dataclass
class Message:
    """A single message in a chat session."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ChatSession:
    """A single chat session with message history and metadata."""

    chat_id: str
    model_alias: str
    messages: list[Message] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def __post_init__(self):
        """Validate chat_id is safe (alphanumeric only)."""
        if not re.match(r'^[A-Za-z0-9]+$', self.chat_id):
            raise ValueError(
                f"Invalid chat_id '{self.chat_id}': "
                "must contain only alphanumeric characters"
            )

    @property
    def path(self) -> Path:
        """Get the file path for this chat session."""
        return CHATS_DIR / f"{self.chat_id}.json"

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the chat session."""
        self.messages.append(Message(role=role, content=content))
        self.updated_at = datetime.now().isoformat()

    def format_history(self) -> str:
        """Format message history as a string for prompt injection."""
        if not self.messages:
            return ""
        lines = []
        for msg in self.messages:
            lines.append(f"{msg.role.upper()}: {msg.content}")
        return "\n\n".join(lines)

    def save(self) -> None:
        """Save chat session to file."""
        CHATS_DIR.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, chat_id: str) -> "ChatSession | None":
        """Load chat session from file. Returns None if not found or invalid."""
        # Validate chat_id before path construction
        if not re.match(r'^[A-Za-z0-9]+$', chat_id):
            return None

        path = CHATS_DIR / f"{chat_id}.json"
        if not path.exists():
            return None

        try:
            with open(path) as f:
                data = json.load(f)
            return cls(
                chat_id=data["chat_id"],
                model_alias=data["model_alias"],
                messages=[Message(**msg) for msg in data.get("messages", [])],
                created_at=data.get("created_at", datetime.now().isoformat()),
                updated_at=data.get("updated_at", datetime.now().isoformat()),
            )
        except (json.JSONDecodeError, OSError, KeyError, TypeError):
            return None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "chat_id": self.chat_id,
            "model_alias": self.model_alias,
            "messages": [
                {"role": msg.role, "content": msg.content, "timestamp": msg.timestamp}
                for msg in self.messages
            ],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def enforce_limit(self, max_chars: int = 4000, max_messages: int = 10) -> None:
        """Enforce sliding window limit on message history."""
        if not self.messages:
            return

        # Keep trimming until we fit both constraints
        while (
            len(self.messages) > 1
            and (
                len(self.messages) > max_messages
                or sum(len(msg.content) for msg in self.messages) > max_chars
            )
        ):
            # Remove oldest message (index 0)
            self.messages.pop(0)


@dataclass
class ChatManager:
    """Manager for multiple chat sessions."""

    @staticmethod
    def generate_id() -> str:
        """Generate a unique 3-character chat ID with collision detection."""
        chars = string.ascii_uppercase + string.digits
        CHATS_DIR.mkdir(parents=True, exist_ok=True)

        for _ in range(100):  # Prevent infinite loop
            chat_id = "".join(secrets.choice(chars) for _ in range(3))
            if not (CHATS_DIR / f"{chat_id}.json").exists():
                return chat_id

        raise RuntimeError("Failed to generate unique chat ID after 100 attempts")

    @staticmethod
    def create(model_alias: str, chat_id: str | None = None) -> ChatSession:
        """Create a new chat session."""
        if chat_id is None:
            chat_id = ChatManager.generate_id()
        return ChatSession(chat_id=chat_id, model_alias=model_alias)

    @staticmethod
    def load(chat_id: str) -> ChatSession | None:
        """Load a chat session by ID."""
        return ChatSession.load(chat_id)

    @staticmethod
    def list_all() -> list[ChatSession]:
        """List all chat sessions."""
        CHATS_DIR.mkdir(parents=True, exist_ok=True)
        sessions = []
        for path in CHATS_DIR.glob("*.json"):
            chat_id = path.stem
            session = ChatSession.load(chat_id)
            if session:
                sessions.append(session)
        return sorted(sessions, key=lambda s: s.updated_at, reverse=True)

    @staticmethod
    def delete(chat_id: str) -> bool:
        """Delete a chat session. Returns True if deleted, False if not found."""
        path = CHATS_DIR / f"{chat_id}.json"
        if path.exists():
            path.unlink()
            return True
        return False

    @staticmethod
    def get_latest() -> "ChatSession | None":
        """Get most recently updated chat without loading all sessions."""
        CHATS_DIR.mkdir(parents=True, exist_ok=True)
        paths = list(CHATS_DIR.glob("*.json"))
        if not paths:
            return None
        # Sort by modification time (most recent first)
        paths.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return ChatSession.load(paths[0].stem)
