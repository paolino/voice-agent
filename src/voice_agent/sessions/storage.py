"""Session storage for persistence across restarts.

Stores session metadata to JSON file.
"""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class StoredSession:
    """Serializable session data for persistence.

    Attributes:
        chat_id: Telegram chat ID.
        name: Session name within the chat.
        cwd: Working directory.
        created_at: ISO format timestamp.
        message_count: Number of messages exchanged.
        claude_session_id: Claude CLI session ID for resume.
    """

    chat_id: int
    name: str
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
            name=data.get("name", "main"),
            cwd=data["cwd"],
            created_at=data["created_at"],
            message_count=data["message_count"],
            claude_session_id=data.get("claude_session_id"),
        )


@dataclass
class ChatStoredState:
    """Stored state for all sessions in a chat.

    Attributes:
        active_session: Name of the currently active session.
        sessions: Mapping of session names to stored sessions.
    """

    active_session: str
    sessions: dict[str, StoredSession] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "active_session": self.active_session,
            "sessions": {name: s.to_dict() for name, s in self.sessions.items()},
        }

    @classmethod
    def from_dict(cls, chat_id: int, data: dict[str, Any]) -> "ChatStoredState":
        """Create from dictionary.

        Args:
            chat_id: Telegram chat ID (needed for session creation).
            data: Raw dictionary data.
        """
        sessions = {}
        for name, s_data in data.get("sessions", {}).items():
            # Ensure chat_id is set on each session
            s_data["chat_id"] = chat_id
            sessions[name] = StoredSession.from_dict(s_data)
        return cls(
            active_session=data.get("active_session", "main"),
            sessions=sessions,
        )


class SessionStorage:
    """Persistent storage for session data.

    Stores sessions in a JSON file with multi-session support per chat.

    Attributes:
        path: Path to the JSON storage file.
    """

    def __init__(self, path: str | Path = "sessions.json") -> None:
        """Initialize storage.

        Args:
            path: Path to the JSON storage file.
        """
        self.path = Path(path)
        self._data: dict[int, ChatStoredState] = {}
        self._load()

    def _is_old_format(self, data: dict[str, Any]) -> bool:
        """Check if data is in old single-session format.

        Old format has "cwd" at top level of session data.
        New format has "active_session" and "sessions" keys.
        """
        return "cwd" in data

    def _migrate_old_format(
        self, chat_id: int, old_data: dict[str, Any]
    ) -> ChatStoredState:
        """Migrate old single-session format to new multi-session format.

        Args:
            chat_id: Telegram chat ID.
            old_data: Old format session data with cwd at top level.

        Returns:
            ChatStoredState with single "main" session.
        """
        old_data["name"] = "main"
        session = StoredSession.from_dict(old_data)
        return ChatStoredState(
            active_session="main",
            sessions={"main": session},
        )

    def _load(self) -> None:
        """Load sessions from disk with automatic migration."""
        if not self.path.exists():
            return

        try:
            with open(self.path) as f:
                raw = json.load(f)
                needs_save = False
                for chat_id_str, chat_data in raw.items():
                    chat_id = int(chat_id_str)
                    if self._is_old_format(chat_data):
                        # Migrate old format
                        self._data[chat_id] = self._migrate_old_format(
                            chat_id, chat_data
                        )
                        needs_save = True
                    else:
                        self._data[chat_id] = ChatStoredState.from_dict(
                            chat_id, chat_data
                        )
                # Save migrated data
                if needs_save:
                    self._save()
        except (json.JSONDecodeError, KeyError, ValueError):
            # Corrupted file, start fresh
            self._data = {}

    def _save(self) -> None:
        """Save sessions to disk."""
        raw = {str(k): v.to_dict() for k, v in self._data.items()}
        with open(self.path, "w") as f:
            json.dump(raw, f, indent=2)

    def get_chat_state(self, chat_id: int) -> ChatStoredState | None:
        """Get stored state for a chat.

        Args:
            chat_id: Telegram chat ID.

        Returns:
            ChatStoredState or None if not found.
        """
        return self._data.get(chat_id)

    def get_session(self, chat_id: int, name: str) -> StoredSession | None:
        """Get a specific session for a chat.

        Args:
            chat_id: Telegram chat ID.
            name: Session name.

        Returns:
            StoredSession or None if not found.
        """
        state = self._data.get(chat_id)
        if state:
            return state.sessions.get(name)
        return None

    def get_active_session(self, chat_id: int) -> StoredSession | None:
        """Get the active session for a chat.

        Args:
            chat_id: Telegram chat ID.

        Returns:
            Active StoredSession or None if not found.
        """
        state = self._data.get(chat_id)
        if state:
            return state.sessions.get(state.active_session)
        return None

    def save_session(self, session: StoredSession) -> None:
        """Save a session.

        Args:
            session: Session to save.
        """
        chat_id = session.chat_id
        if chat_id not in self._data:
            self._data[chat_id] = ChatStoredState(
                active_session=session.name,
                sessions={},
            )
        self._data[chat_id].sessions[session.name] = session
        self._save()

    def set_active_session(self, chat_id: int, name: str) -> bool:
        """Set the active session for a chat.

        Args:
            chat_id: Telegram chat ID.
            name: Session name to make active.

        Returns:
            True if successful, False if session not found.
        """
        state = self._data.get(chat_id)
        if state and name in state.sessions:
            state.active_session = name
            self._save()
            return True
        return False

    def delete_session(self, chat_id: int, name: str) -> bool:
        """Delete a specific session.

        Args:
            chat_id: Telegram chat ID.
            name: Session name to delete.

        Returns:
            True if deleted, False if not found.
        """
        state = self._data.get(chat_id)
        if not state or name not in state.sessions:
            return False

        del state.sessions[name]

        # If we deleted the active session, switch to another or remove chat
        if state.active_session == name:
            if state.sessions:
                state.active_session = next(iter(state.sessions))
            else:
                del self._data[chat_id]

        self._save()
        return True

    def rename_session(self, chat_id: int, old_name: str, new_name: str) -> bool:
        """Rename a session.

        Args:
            chat_id: Telegram chat ID.
            old_name: Current session name.
            new_name: New session name.

        Returns:
            True if renamed, False if not found or name exists.
        """
        state = self._data.get(chat_id)
        if not state or old_name not in state.sessions:
            return False

        if new_name in state.sessions:
            return False

        session = state.sessions.pop(old_name)
        session.name = new_name
        state.sessions[new_name] = session

        if state.active_session == old_name:
            state.active_session = new_name

        self._save()
        return True

    def delete_chat(self, chat_id: int) -> bool:
        """Delete all sessions for a chat.

        Args:
            chat_id: Telegram chat ID.

        Returns:
            True if deleted, False if not found.
        """
        if chat_id in self._data:
            del self._data[chat_id]
            self._save()
            return True
        return False

    def list_sessions(self, chat_id: int) -> list[StoredSession]:
        """List all sessions for a chat.

        Args:
            chat_id: Telegram chat ID.

        Returns:
            List of stored sessions.
        """
        state = self._data.get(chat_id)
        if state:
            return list(state.sessions.values())
        return []

    def list_all_chats(self) -> list[int]:
        """List all chat IDs with sessions.

        Returns:
            List of chat IDs.
        """
        return list(self._data.keys())

    # Legacy compatibility methods

    def get(self, chat_id: int) -> StoredSession | None:
        """Get active session for a chat (legacy compatibility).

        Args:
            chat_id: Telegram chat ID.

        Returns:
            Active StoredSession or None if not found.
        """
        return self.get_active_session(chat_id)

    def save(self, session: StoredSession) -> None:
        """Save a session (legacy compatibility).

        Args:
            session: Session to save.
        """
        self.save_session(session)

    def delete(self, chat_id: int) -> None:
        """Delete all sessions for a chat (legacy compatibility).

        Args:
            chat_id: Telegram chat ID.
        """
        self.delete_chat(chat_id)

    def list_all(self) -> list[StoredSession]:
        """List all active sessions across all chats (legacy compatibility).

        Returns:
            List of active stored sessions.
        """
        result = []
        for chat_id in self._data:
            session = self.get_active_session(chat_id)
            if session:
                result.append(session)
        return result
