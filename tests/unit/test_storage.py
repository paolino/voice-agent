"""Unit tests for session storage."""

import json
from pathlib import Path

import pytest

from voice_agent.sessions.storage import SessionStorage, StoredSession


@pytest.mark.unit
class TestStoredSession:
    """Tests for StoredSession dataclass."""

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        session = StoredSession(
            chat_id=123,
            cwd="/code/project",
            created_at="2024-01-15T10:30:00",
            message_count=5,
            claude_session_id="abc-123",
        )
        result = session.to_dict()
        assert result == {
            "chat_id": 123,
            "cwd": "/code/project",
            "created_at": "2024-01-15T10:30:00",
            "message_count": 5,
            "claude_session_id": "abc-123",
        }

    def test_to_dict_without_session_id(self) -> None:
        """Test conversion to dictionary without Claude session ID."""
        session = StoredSession(
            chat_id=123,
            cwd="/code/project",
            created_at="2024-01-15T10:30:00",
            message_count=0,
        )
        result = session.to_dict()
        assert result["claude_session_id"] is None

    def test_from_dict(self) -> None:
        """Test creation from dictionary."""
        data = {
            "chat_id": 456,
            "cwd": "/code/other",
            "created_at": "2024-01-16T12:00:00",
            "message_count": 10,
            "claude_session_id": "xyz-789",
        }
        session = StoredSession.from_dict(data)
        assert session.chat_id == 456
        assert session.cwd == "/code/other"
        assert session.created_at == "2024-01-16T12:00:00"
        assert session.message_count == 10
        assert session.claude_session_id == "xyz-789"

    def test_from_dict_missing_session_id(self) -> None:
        """Test creation from dictionary without Claude session ID."""
        data = {
            "chat_id": 456,
            "cwd": "/code/other",
            "created_at": "2024-01-16T12:00:00",
            "message_count": 10,
        }
        session = StoredSession.from_dict(data)
        assert session.claude_session_id is None


@pytest.mark.unit
class TestSessionStorage:
    """Tests for SessionStorage class."""

    def test_save_and_get(self, tmp_path: Path) -> None:
        """Test saving and retrieving a session."""
        storage = SessionStorage(path=tmp_path / "sessions.json")

        session = StoredSession(
            chat_id=123,
            cwd="/code/project",
            created_at="2024-01-15T10:30:00",
            message_count=5,
        )
        storage.save(session)

        retrieved = storage.get(123)
        assert retrieved is not None
        assert retrieved.chat_id == 123
        assert retrieved.cwd == "/code/project"
        assert retrieved.message_count == 5

    def test_get_nonexistent(self, tmp_path: Path) -> None:
        """Test getting a nonexistent session returns None."""
        storage = SessionStorage(path=tmp_path / "sessions.json")
        assert storage.get(999) is None

    def test_delete(self, tmp_path: Path) -> None:
        """Test deleting a session."""
        storage = SessionStorage(path=tmp_path / "sessions.json")

        session = StoredSession(
            chat_id=123,
            cwd="/code/project",
            created_at="2024-01-15T10:30:00",
            message_count=5,
        )
        storage.save(session)
        assert storage.get(123) is not None

        storage.delete(123)
        assert storage.get(123) is None

    def test_delete_nonexistent(self, tmp_path: Path) -> None:
        """Test deleting a nonexistent session doesn't raise."""
        storage = SessionStorage(path=tmp_path / "sessions.json")
        storage.delete(999)  # Should not raise

    def test_list_all(self, tmp_path: Path) -> None:
        """Test listing all sessions."""
        storage = SessionStorage(path=tmp_path / "sessions.json")

        sessions = [
            StoredSession(chat_id=123, cwd="/code/a", created_at="2024-01-15T10:00:00", message_count=1),
            StoredSession(chat_id=456, cwd="/code/b", created_at="2024-01-15T11:00:00", message_count=2),
            StoredSession(chat_id=789, cwd="/code/c", created_at="2024-01-15T12:00:00", message_count=3),
        ]

        for session in sessions:
            storage.save(session)

        all_sessions = storage.list_all()
        assert len(all_sessions) == 3
        chat_ids = {s.chat_id for s in all_sessions}
        assert chat_ids == {123, 456, 789}

    def test_persistence(self, tmp_path: Path) -> None:
        """Test that sessions persist across storage instances."""
        path = tmp_path / "sessions.json"

        # Save with first instance
        storage1 = SessionStorage(path=path)
        session = StoredSession(
            chat_id=123,
            cwd="/code/project",
            created_at="2024-01-15T10:30:00",
            message_count=5,
            claude_session_id="test-session-id",
        )
        storage1.save(session)

        # Load with second instance
        storage2 = SessionStorage(path=path)
        retrieved = storage2.get(123)

        assert retrieved is not None
        assert retrieved.chat_id == 123
        assert retrieved.cwd == "/code/project"
        assert retrieved.claude_session_id == "test-session-id"

    def test_corrupted_file_starts_fresh(self, tmp_path: Path) -> None:
        """Test that corrupted JSON file results in fresh start."""
        path = tmp_path / "sessions.json"
        path.write_text("not valid json")

        storage = SessionStorage(path=path)
        assert storage.list_all() == []

    def test_update_existing(self, tmp_path: Path) -> None:
        """Test updating an existing session."""
        storage = SessionStorage(path=tmp_path / "sessions.json")

        # Save initial
        session = StoredSession(
            chat_id=123,
            cwd="/code/project",
            created_at="2024-01-15T10:30:00",
            message_count=5,
        )
        storage.save(session)

        # Update
        updated = StoredSession(
            chat_id=123,
            cwd="/code/project",
            created_at="2024-01-15T10:30:00",
            message_count=10,
            claude_session_id="new-session-id",
        )
        storage.save(updated)

        # Verify
        retrieved = storage.get(123)
        assert retrieved is not None
        assert retrieved.message_count == 10
        assert retrieved.claude_session_id == "new-session-id"
