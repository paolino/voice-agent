"""Integration tests for session manager."""

import pytest

from voice_agent.sessions import SessionManager


@pytest.mark.integration
class TestSessionManager:
    """Integration tests for SessionManager."""

    def test_get_or_create_new_session(
        self, session_manager: SessionManager
    ) -> None:
        """Test creating a new session."""
        session = session_manager.get_or_create(123)

        assert session.chat_id == 123
        assert session.cwd == "/code"
        assert session.message_count == 0

    def test_get_or_create_existing_session(
        self, session_manager: SessionManager
    ) -> None:
        """Test getting an existing session."""
        session1 = session_manager.get_or_create(123)
        session1.message_count = 5

        session2 = session_manager.get_or_create(123)

        assert session1 is session2
        assert session2.message_count == 5

    def test_create_new_replaces_existing(
        self, session_manager: SessionManager
    ) -> None:
        """Test creating new session replaces existing."""
        session1 = session_manager.get_or_create(123)
        session1.message_count = 5

        session2 = session_manager.create_new(123)

        assert session1 is not session2
        assert session2.message_count == 0

    def test_get_nonexistent_returns_none(
        self, session_manager: SessionManager
    ) -> None:
        """Test getting nonexistent session returns None."""
        session = session_manager.get(999)
        assert session is None

    def test_set_cwd(self, session_manager: SessionManager) -> None:
        """Test setting working directory."""
        session_manager.get_or_create(123)
        session = session_manager.set_cwd(123, "/other/path")

        assert session.cwd == "/other/path"

    def test_get_status_with_session(
        self, session_manager: SessionManager
    ) -> None:
        """Test getting status with active session."""
        session_manager.get_or_create(123)
        status = session_manager.get_status(123)

        assert status is not None
        assert "Working directory: /code" in status
        assert "Messages: 0" in status

    def test_get_status_no_session(
        self, session_manager: SessionManager
    ) -> None:
        """Test getting status without session."""
        status = session_manager.get_status(999)
        assert status is None

    def test_multiple_chats(self, session_manager: SessionManager) -> None:
        """Test managing sessions for multiple chats."""
        session1 = session_manager.get_or_create(123, "/path/1")
        session2 = session_manager.get_or_create(456, "/path/2")

        assert session1.chat_id == 123
        assert session1.cwd == "/path/1"
        assert session2.chat_id == 456
        assert session2.cwd == "/path/2"

    def test_session_status_with_pending_permission(
        self, session_manager: SessionManager
    ) -> None:
        """Test status shows pending permission."""
        from voice_agent.sessions.permissions import PendingPermission

        session = session_manager.get_or_create(123)
        session.permission_handler.pending = PendingPermission(
            tool_name="Write", input_data={"file_path": "/tmp/test.txt"}
        )

        status = session.get_status()
        assert "Pending approval" in status
        assert "Write file" in status
