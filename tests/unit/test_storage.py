"""Unit tests for session storage."""

import json
from pathlib import Path

import pytest

from voice_agent.sessions.storage import (
    ChatStoredState,
    SessionStorage,
    StoredSession,
)


@pytest.mark.unit
class TestStoredSession:
    """Tests for StoredSession dataclass."""

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        session = StoredSession(
            chat_id=123,
            name="main",
            cwd="/code/project",
            created_at="2024-01-15T10:30:00",
            message_count=5,
            claude_session_id="abc-123",
        )
        result = session.to_dict()
        assert result == {
            "chat_id": 123,
            "name": "main",
            "cwd": "/code/project",
            "created_at": "2024-01-15T10:30:00",
            "message_count": 5,
            "claude_session_id": "abc-123",
        }

    def test_to_dict_without_session_id(self) -> None:
        """Test conversion to dictionary without Claude session ID."""
        session = StoredSession(
            chat_id=123,
            name="main",
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
            "name": "work",
            "cwd": "/code/other",
            "created_at": "2024-01-16T12:00:00",
            "message_count": 10,
            "claude_session_id": "xyz-789",
        }
        session = StoredSession.from_dict(data)
        assert session.chat_id == 456
        assert session.name == "work"
        assert session.cwd == "/code/other"
        assert session.created_at == "2024-01-16T12:00:00"
        assert session.message_count == 10
        assert session.claude_session_id == "xyz-789"

    def test_from_dict_missing_session_id(self) -> None:
        """Test creation from dictionary without Claude session ID."""
        data = {
            "chat_id": 456,
            "name": "main",
            "cwd": "/code/other",
            "created_at": "2024-01-16T12:00:00",
            "message_count": 10,
        }
        session = StoredSession.from_dict(data)
        assert session.claude_session_id is None

    def test_from_dict_missing_name_defaults_to_main(self) -> None:
        """Test creation from dictionary without name defaults to main."""
        data = {
            "chat_id": 456,
            "cwd": "/code/other",
            "created_at": "2024-01-16T12:00:00",
            "message_count": 10,
        }
        session = StoredSession.from_dict(data)
        assert session.name == "main"


@pytest.mark.unit
class TestChatStoredState:
    """Tests for ChatStoredState dataclass."""

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        session = StoredSession(
            chat_id=123,
            name="main",
            cwd="/code/project",
            created_at="2024-01-15T10:30:00",
            message_count=5,
        )
        state = ChatStoredState(
            active_session="main",
            sessions={"main": session},
        )
        result = state.to_dict()
        assert result["active_session"] == "main"
        assert "main" in result["sessions"]
        assert result["sessions"]["main"]["name"] == "main"

    def test_from_dict(self) -> None:
        """Test creation from dictionary."""
        data = {
            "active_session": "work",
            "sessions": {
                "main": {
                    "name": "main",
                    "cwd": "/code/a",
                    "created_at": "2024-01-15T10:00:00",
                    "message_count": 1,
                },
                "work": {
                    "name": "work",
                    "cwd": "/code/b",
                    "created_at": "2024-01-15T11:00:00",
                    "message_count": 2,
                },
            },
        }
        state = ChatStoredState.from_dict(123, data)
        assert state.active_session == "work"
        assert len(state.sessions) == 2
        assert state.sessions["main"].chat_id == 123
        assert state.sessions["work"].cwd == "/code/b"


@pytest.mark.unit
class TestSessionStorage:
    """Tests for SessionStorage class."""

    def test_save_and_get(self, tmp_path: Path) -> None:
        """Test saving and retrieving a session."""
        storage = SessionStorage(path=tmp_path / "sessions.json")

        session = StoredSession(
            chat_id=123,
            name="main",
            cwd="/code/project",
            created_at="2024-01-15T10:30:00",
            message_count=5,
        )
        storage.save(session)

        retrieved = storage.get(123)
        assert retrieved is not None
        assert retrieved.chat_id == 123
        assert retrieved.name == "main"
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
            name="main",
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
            StoredSession(
                chat_id=123,
                name="main",
                cwd="/code/a",
                created_at="2024-01-15T10:00:00",
                message_count=1,
            ),
            StoredSession(
                chat_id=456,
                name="main",
                cwd="/code/b",
                created_at="2024-01-15T11:00:00",
                message_count=2,
            ),
            StoredSession(
                chat_id=789,
                name="main",
                cwd="/code/c",
                created_at="2024-01-15T12:00:00",
                message_count=3,
            ),
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
            name="main",
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
        assert retrieved.name == "main"
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
            name="main",
            cwd="/code/project",
            created_at="2024-01-15T10:30:00",
            message_count=5,
        )
        storage.save(session)

        # Update
        updated = StoredSession(
            chat_id=123,
            name="main",
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


@pytest.mark.unit
class TestSessionStorageMultiSession:
    """Tests for multi-session support in SessionStorage."""

    def test_save_multiple_sessions_same_chat(self, tmp_path: Path) -> None:
        """Test saving multiple sessions for the same chat."""
        storage = SessionStorage(path=tmp_path / "sessions.json")

        main_session = StoredSession(
            chat_id=123,
            name="main",
            cwd="/code/a",
            created_at="2024-01-15T10:00:00",
            message_count=5,
        )
        work_session = StoredSession(
            chat_id=123,
            name="work",
            cwd="/code/b",
            created_at="2024-01-15T11:00:00",
            message_count=3,
        )

        storage.save_session(main_session)
        storage.save_session(work_session)

        sessions = storage.list_sessions(123)
        assert len(sessions) == 2
        names = {s.name for s in sessions}
        assert names == {"main", "work"}

    def test_get_specific_session(self, tmp_path: Path) -> None:
        """Test getting a specific session by name."""
        storage = SessionStorage(path=tmp_path / "sessions.json")

        main_session = StoredSession(
            chat_id=123,
            name="main",
            cwd="/code/a",
            created_at="2024-01-15T10:00:00",
            message_count=5,
        )
        work_session = StoredSession(
            chat_id=123,
            name="work",
            cwd="/code/b",
            created_at="2024-01-15T11:00:00",
            message_count=3,
        )

        storage.save_session(main_session)
        storage.save_session(work_session)

        retrieved = storage.get_session(123, "work")
        assert retrieved is not None
        assert retrieved.name == "work"
        assert retrieved.cwd == "/code/b"

    def test_set_active_session(self, tmp_path: Path) -> None:
        """Test setting the active session."""
        storage = SessionStorage(path=tmp_path / "sessions.json")

        main_session = StoredSession(
            chat_id=123,
            name="main",
            cwd="/code/a",
            created_at="2024-01-15T10:00:00",
            message_count=5,
        )
        work_session = StoredSession(
            chat_id=123,
            name="work",
            cwd="/code/b",
            created_at="2024-01-15T11:00:00",
            message_count=3,
        )

        storage.save_session(main_session)
        storage.save_session(work_session)

        # Active should be main (first saved)
        active = storage.get_active_session(123)
        assert active is not None
        assert active.name == "main"

        # Switch to work
        storage.set_active_session(123, "work")
        active = storage.get_active_session(123)
        assert active is not None
        assert active.name == "work"

    def test_delete_specific_session(self, tmp_path: Path) -> None:
        """Test deleting a specific session."""
        storage = SessionStorage(path=tmp_path / "sessions.json")

        main_session = StoredSession(
            chat_id=123,
            name="main",
            cwd="/code/a",
            created_at="2024-01-15T10:00:00",
            message_count=5,
        )
        work_session = StoredSession(
            chat_id=123,
            name="work",
            cwd="/code/b",
            created_at="2024-01-15T11:00:00",
            message_count=3,
        )

        storage.save_session(main_session)
        storage.save_session(work_session)

        # Delete work session
        deleted = storage.delete_session(123, "work")
        assert deleted is True

        sessions = storage.list_sessions(123)
        assert len(sessions) == 1
        assert sessions[0].name == "main"

    def test_delete_active_session_switches_to_other(self, tmp_path: Path) -> None:
        """Test deleting active session switches to another."""
        storage = SessionStorage(path=tmp_path / "sessions.json")

        main_session = StoredSession(
            chat_id=123,
            name="main",
            cwd="/code/a",
            created_at="2024-01-15T10:00:00",
            message_count=5,
        )
        work_session = StoredSession(
            chat_id=123,
            name="work",
            cwd="/code/b",
            created_at="2024-01-15T11:00:00",
            message_count=3,
        )

        storage.save_session(main_session)
        storage.save_session(work_session)

        # Active is main
        assert storage.get_active_session(123).name == "main"

        # Delete main session
        storage.delete_session(123, "main")

        # Active should now be work
        active = storage.get_active_session(123)
        assert active is not None
        assert active.name == "work"

    def test_delete_last_session_removes_chat(self, tmp_path: Path) -> None:
        """Test deleting last session removes the chat entry."""
        storage = SessionStorage(path=tmp_path / "sessions.json")

        session = StoredSession(
            chat_id=123,
            name="main",
            cwd="/code/a",
            created_at="2024-01-15T10:00:00",
            message_count=5,
        )
        storage.save_session(session)

        storage.delete_session(123, "main")

        assert storage.get_chat_state(123) is None


@pytest.mark.unit
class TestSessionStorageMigration:
    """Tests for migrating old format to new format."""

    def test_migrate_old_format(self, tmp_path: Path) -> None:
        """Test migration from old single-session format."""
        path = tmp_path / "sessions.json"

        # Write old format data
        old_data = {
            "123": {
                "chat_id": 123,
                "cwd": "/code/project",
                "created_at": "2024-01-15T10:30:00",
                "message_count": 5,
                "claude_session_id": "old-session",
            }
        }
        path.write_text(json.dumps(old_data))

        # Load with new storage
        storage = SessionStorage(path=path)

        # Should have migrated to new format
        session = storage.get(123)
        assert session is not None
        assert session.name == "main"
        assert session.cwd == "/code/project"
        assert session.message_count == 5

        # Check file was updated to new format
        with open(path) as f:
            new_data = json.load(f)
        assert "active_session" in new_data["123"]
        assert "sessions" in new_data["123"]

    def test_migrate_preserves_data(self, tmp_path: Path) -> None:
        """Test migration preserves all session data."""
        path = tmp_path / "sessions.json"

        old_data = {
            "123": {
                "chat_id": 123,
                "cwd": "/code/a",
                "created_at": "2024-01-15T10:00:00",
                "message_count": 10,
                "claude_session_id": "session-id-123",
            },
            "456": {
                "chat_id": 456,
                "cwd": "/code/b",
                "created_at": "2024-01-15T11:00:00",
                "message_count": 20,
            },
        }
        path.write_text(json.dumps(old_data))

        storage = SessionStorage(path=path)

        # Check both chats were migrated
        s1 = storage.get(123)
        s2 = storage.get(456)

        assert s1 is not None
        assert s1.message_count == 10
        assert s1.claude_session_id == "session-id-123"

        assert s2 is not None
        assert s2.message_count == 20
        assert s2.claude_session_id is None
