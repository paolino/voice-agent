"""Integration tests for session manager."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from voice_agent.sessions import SessionManager


@pytest.mark.integration
class TestSessionManager:
    """Integration tests for SessionManager."""

    def test_get_or_create_new_session(self, session_manager: SessionManager) -> None:
        """Test creating a new session."""
        session = session_manager.get_or_create(123)

        assert session.chat_id == 123
        assert session.name == "main"
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
        """Test creating new session replaces existing with same name."""
        session1 = session_manager.get_or_create(123)
        session1.message_count = 5

        session2 = session_manager.create_new(123)

        assert session1 is not session2
        assert session2.message_count == 0
        assert session2.name == "main"

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

    def test_get_status_with_session(self, session_manager: SessionManager) -> None:
        """Test getting status with active session."""
        session_manager.get_or_create(123)
        status = session_manager.get_status(123)

        assert status is not None
        assert "Session: main" in status
        assert "Working directory: /code" in status
        assert "Messages: 0" in status

    def test_get_status_no_session(self, session_manager: SessionManager) -> None:
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


@pytest.mark.integration
class TestSessionManagerMultiSession:
    """Integration tests for multi-session support."""

    def test_create_named_session(self, session_manager: SessionManager) -> None:
        """Test creating a named session."""
        session = session_manager.get_or_create(123, name="work")

        assert session.name == "work"
        assert session.chat_id == 123

    def test_list_sessions(self, session_manager: SessionManager) -> None:
        """Test listing all sessions for a chat."""
        session_manager.get_or_create(123, name="main")
        session_manager.create_new(123, name="work")

        sessions = session_manager.list_sessions(123)

        assert len(sessions) == 2
        names = {s.name for s in sessions}
        assert names == {"main", "work"}

    def test_switch_session(self, session_manager: SessionManager) -> None:
        """Test switching between sessions."""
        session_manager.get_or_create(123, name="main")
        session_manager.create_new(123, name="work")

        # Active is work (last created)
        assert session_manager.get_active_session_name(123) == "work"

        # Switch to main
        session = session_manager.switch_session(123, "main")
        assert session is not None
        assert session.name == "main"
        assert session_manager.get_active_session_name(123) == "main"

    def test_switch_nonexistent_returns_none(
        self, session_manager: SessionManager
    ) -> None:
        """Test switching to nonexistent session returns None."""
        session_manager.get_or_create(123)

        result = session_manager.switch_session(123, "nonexistent")
        assert result is None

    def test_generate_session_name(self, session_manager: SessionManager) -> None:
        """Test generating unique session names."""
        session_manager.get_or_create(123, name="main")

        name = session_manager.generate_session_name(123)
        assert name == "session-2"

        session_manager.create_new(123, name="session-2")
        name = session_manager.generate_session_name(123)
        assert name == "session-3"

    def test_close_session(self, session_manager: SessionManager) -> None:
        """Test closing a specific session."""
        session_manager.get_or_create(123, name="main")
        session_manager.create_new(123, name="work")

        closed = session_manager.close_session(123, "work")
        assert closed is True

        sessions = session_manager.list_sessions(123)
        assert len(sessions) == 1
        assert sessions[0].name == "main"

    def test_close_active_session_switches(
        self, session_manager: SessionManager
    ) -> None:
        """Test closing active session switches to another."""
        session_manager.get_or_create(123, name="main")
        session_manager.create_new(123, name="work")

        # Active is work
        assert session_manager.get_active_session_name(123) == "work"

        # Close work
        session_manager.close_session(123, "work")

        # Active should be main now
        assert session_manager.get_active_session_name(123) == "main"

    def test_session_info_is_active(self, session_manager: SessionManager) -> None:
        """Test SessionInfo.is_active flag."""
        session_manager.get_or_create(123, name="main")
        session_manager.create_new(123, name="work")

        sessions = session_manager.list_sessions(123)
        main_info = next(s for s in sessions if s.name == "main")
        work_info = next(s for s in sessions if s.name == "work")

        assert work_info.is_active is True
        assert main_info.is_active is False


@pytest.mark.integration
class TestPermissionCallbackWiring:
    """Tests for permission callback wiring to SDK."""

    async def test_safe_tool_auto_approved_via_callback(
        self, session_manager: SessionManager
    ) -> None:
        """Test safe tools are auto-approved through SDK callback."""
        session = session_manager.get_or_create(123)

        # Mock the SDK imports and client
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        captured_callback = None

        def mock_options_init(**kwargs):
            nonlocal captured_callback
            captured_callback = kwargs.get("can_use_tool")
            return MagicMock()

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch(
                "claude_agent_sdk.ClaudeAgentOptions",
                side_effect=mock_options_init,
            ):
                with patch(
                    "claude_agent_sdk.ClaudeSDKClient",
                    return_value=mock_client,
                ):
                    with patch("claude_agent_sdk.PermissionResultAllow") as mock_allow:
                        with patch("claude_agent_sdk.PermissionResultDeny"):
                            with patch("claude_agent_sdk.ToolPermissionContext"):
                                await session_manager._get_or_create_client(session)

                                # Verify callback was captured
                                assert captured_callback is not None

                                # Call the callback with a safe tool
                                mock_context = MagicMock()
                                result = await captured_callback(
                                    "Read", {}, mock_context
                                )

                                # Safe tool should return PermissionResultAllow
                                mock_allow.assert_called_once()

    async def test_unsafe_tool_waits_for_approval(
        self, session_manager: SessionManager
    ) -> None:
        """Test unsafe tools wait for user approval through SDK callback."""
        session = session_manager.get_or_create(123)

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        captured_callback = None

        def mock_options_init(**kwargs):
            nonlocal captured_callback
            captured_callback = kwargs.get("can_use_tool")
            return MagicMock()

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch(
                "claude_agent_sdk.ClaudeAgentOptions",
                side_effect=mock_options_init,
            ):
                with patch(
                    "claude_agent_sdk.ClaudeSDKClient",
                    return_value=mock_client,
                ):
                    with patch("claude_agent_sdk.PermissionResultAllow") as mock_allow:
                        with patch("claude_agent_sdk.PermissionResultDeny"):
                            with patch("claude_agent_sdk.ToolPermissionContext"):
                                await session_manager._get_or_create_client(session)

                                assert captured_callback is not None

                                # Start permission request in background
                                mock_context = MagicMock()
                                callback_task = asyncio.create_task(
                                    captured_callback(
                                        "Write",
                                        {"file_path": "/tmp/test.txt"},
                                        mock_context,
                                    )
                                )

                                # Wait for pending permission to be created
                                await asyncio.sleep(0.01)
                                assert session.permission_handler.has_pending()

                                # Approve the permission
                                session.permission_handler.approve()

                                # Wait for callback to complete
                                await callback_task

                                # Should have called PermissionResultAllow
                                mock_allow.assert_called_once()

    async def test_unsafe_tool_denied(self, session_manager: SessionManager) -> None:
        """Test unsafe tools can be denied through SDK callback."""
        session = session_manager.get_or_create(123)

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        captured_callback = None

        def mock_options_init(**kwargs):
            nonlocal captured_callback
            captured_callback = kwargs.get("can_use_tool")
            return MagicMock()

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch(
                "claude_agent_sdk.ClaudeAgentOptions",
                side_effect=mock_options_init,
            ):
                with patch(
                    "claude_agent_sdk.ClaudeSDKClient",
                    return_value=mock_client,
                ):
                    with patch("claude_agent_sdk.PermissionResultAllow"):
                        with patch(
                            "claude_agent_sdk.PermissionResultDeny"
                        ) as mock_deny:
                            with patch("claude_agent_sdk.ToolPermissionContext"):
                                await session_manager._get_or_create_client(session)

                                assert captured_callback is not None

                                # Start permission request in background
                                mock_context = MagicMock()
                                callback_task = asyncio.create_task(
                                    captured_callback(
                                        "Write",
                                        {"file_path": "/tmp/test.txt"},
                                        mock_context,
                                    )
                                )

                                # Wait for pending permission
                                await asyncio.sleep(0.01)
                                assert session.permission_handler.has_pending()

                                # Deny the permission
                                session.permission_handler.deny("User rejected")

                                # Wait for callback to complete
                                await callback_task

                                # Should have called PermissionResultDeny with message
                                mock_deny.assert_called_once_with(
                                    message="User rejected"
                                )
