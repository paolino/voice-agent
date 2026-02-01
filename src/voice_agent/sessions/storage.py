"""Session storage for persistence across restarts.

Stores session metadata to JSON file.
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class StoredSession:
    """Serializable session data for persistence.

    Attributes:
        chat_id: Telegram chat ID.
        cwd: Working directory.
        created_at: ISO format timestamp.
        message_count: Number of messages exchanged.
        claude_session_id: Claude CLI session ID for resume.
    """

    chat_id: int
    cwd: str
    created_at: str
    message_count: int
    claude_session_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StoredSession":
        """Create from dictionary."""
        return cls(
            chat_id=data["chat_id"],
            cwd=data["cwd"],
            created_at=data["created_at"],
            message_count=data["message_count"],
            claude_session_id=data.get("claude_session_id"),
        )


class SessionStorage:
    """Persistent storage for session data.

    Stores sessions in a JSON file.

    Attributes:
        path: Path to the JSON storage file.
    """

    def __init__(self, path: str | Path = "sessions.json") -> None:
        """Initialize storage.

        Args:
            path: Path to the JSON storage file.
        """
        self.path = Path(path)
        self._data: dict[int, StoredSession] = {}
        self._load()

    def _load(self) -> None:
        """Load sessions from disk."""
        if not self.path.exists():
            return

        try:
            with open(self.path) as f:
                raw = json.load(f)
                for chat_id_str, session_data in raw.items():
                    chat_id = int(chat_id_str)
                    self._data[chat_id] = StoredSession.from_dict(session_data)
        except (json.JSONDecodeError, KeyError, ValueError):
            # Corrupted file, start fresh
            self._data = {}

    def _save(self) -> None:
        """Save sessions to disk."""
        raw = {str(k): v.to_dict() for k, v in self._data.items()}
        with open(self.path, "w") as f:
            json.dump(raw, f, indent=2)

    def get(self, chat_id: int) -> StoredSession | None:
        """Get stored session for a chat.

        Args:
            chat_id: Telegram chat ID.

        Returns:
            StoredSession or None if not found.
        """
        return self._data.get(chat_id)

    def save(self, session: StoredSession) -> None:
        """Save a session.

        Args:
            session: Session to save.
        """
        self._data[session.chat_id] = session
        self._save()

    def delete(self, chat_id: int) -> None:
        """Delete a stored session.

        Args:
            chat_id: Telegram chat ID.
        """
        if chat_id in self._data:
            del self._data[chat_id]
            self._save()

    def list_all(self) -> list[StoredSession]:
        """List all stored sessions.

        Returns:
            List of all stored sessions.
        """
        return list(self._data.values())
