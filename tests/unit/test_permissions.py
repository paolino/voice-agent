"""Unit tests for permission handling."""

import asyncio

import pytest

from voice_agent.sessions.permissions import (
    PermissionHandler,
    PermissionState,
    is_safe_bash_command,
    is_safe_tool_call,
)


@pytest.mark.unit
class TestSafetyChecks:
    """Tests for safety check functions."""

    @pytest.mark.parametrize(
        "command",
        [
            "ls",
            "ls -la",
            "cat file.txt",
            "head -n 10 file.txt",
            "tail -f log.txt",
            "pwd",
            "echo hello",
            "which python",
            "git status",
            "git log",
            "git diff",
            "git branch",
            "git show HEAD",
        ],
    )
    def test_safe_bash_commands(self, command: str) -> None:
        """Test safe bash commands are detected."""
        assert is_safe_bash_command(command) is True

    @pytest.mark.parametrize(
        "command",
        [
            "rm file.txt",
            "rm -rf /",
            "mv file.txt other.txt",
            "cp file.txt other.txt",
            "chmod 755 file.txt",
            "sudo anything",
            "curl http://example.com",
            "wget http://example.com",
            "python script.py",
            "git push",
            "git commit",
            "git checkout",
        ],
    )
    def test_unsafe_bash_commands(self, command: str) -> None:
        """Test unsafe bash commands are detected."""
        assert is_safe_bash_command(command) is False

    @pytest.mark.parametrize(
        "tool_name",
        ["Read", "Glob", "Grep", "WebSearch", "WebFetch"],
    )
    def test_safe_tools(self, tool_name: str) -> None:
        """Test safe tools are auto-approved."""
        assert is_safe_tool_call(tool_name, {}) is True

    @pytest.mark.parametrize(
        "tool_name",
        ["Write", "Edit", "NotebookEdit"],
    )
    def test_unsafe_tools(self, tool_name: str) -> None:
        """Test unsafe tools are not auto-approved."""
        assert is_safe_tool_call(tool_name, {}) is False

    def test_bash_with_safe_command(self) -> None:
        """Test Bash with safe command is approved."""
        assert is_safe_tool_call("Bash", {"command": "ls -la"}) is True

    def test_bash_with_unsafe_command(self) -> None:
        """Test Bash with unsafe command is not approved."""
        assert is_safe_tool_call("Bash", {"command": "rm file.txt"}) is False


@pytest.mark.unit
class TestPermissionHandler:
    """Tests for PermissionHandler class."""

    def test_initial_state(self, permission_handler: PermissionHandler) -> None:
        """Test initial state has no pending permission."""
        assert permission_handler.has_pending() is False
        assert permission_handler.get_pending_description() is None

    async def test_safe_tool_auto_approved(
        self, permission_handler: PermissionHandler
    ) -> None:
        """Test safe tools are auto-approved."""
        approved, message = await permission_handler.request_permission("Read", {})
        assert approved is True
        assert message is None
        assert permission_handler.has_pending() is False

    async def test_unsafe_tool_creates_pending(
        self, permission_handler: PermissionHandler
    ) -> None:
        """Test unsafe tools create pending permission."""
        # Start permission request in background
        task = asyncio.create_task(
            permission_handler.request_permission("Write", {"file_path": "/tmp/test"})
        )

        # Wait a bit for the pending to be created
        await asyncio.sleep(0.01)

        assert permission_handler.has_pending() is True

        # Approve to complete
        permission_handler.approve()
        approved, _ = await task
        assert approved is True

    def test_approve_pending(self, permission_handler: PermissionHandler) -> None:
        """Test approving a pending permission."""
        # Create pending manually for sync test
        from voice_agent.sessions.permissions import PendingPermission

        permission_handler.pending = PendingPermission(
            tool_name="Write", input_data={"file_path": "/tmp/test"}
        )

        assert permission_handler.approve() is True
        assert permission_handler.pending.state == PermissionState.APPROVED

    def test_deny_pending(self, permission_handler: PermissionHandler) -> None:
        """Test denying a pending permission."""
        from voice_agent.sessions.permissions import PendingPermission

        permission_handler.pending = PendingPermission(
            tool_name="Write", input_data={"file_path": "/tmp/test"}
        )

        assert permission_handler.deny("user said no") is True
        assert permission_handler.pending.state == PermissionState.DENIED
        assert permission_handler.pending.deny_message == "user said no"

    def test_approve_no_pending(self, permission_handler: PermissionHandler) -> None:
        """Test approve when no pending permission."""
        assert permission_handler.approve() is False

    def test_deny_no_pending(self, permission_handler: PermissionHandler) -> None:
        """Test deny when no pending permission."""
        assert permission_handler.deny() is False

    def test_get_pending_description_bash(
        self, permission_handler: PermissionHandler
    ) -> None:
        """Test description for Bash tool."""
        from voice_agent.sessions.permissions import PendingPermission

        permission_handler.pending = PendingPermission(
            tool_name="Bash", input_data={"command": "rm -rf /tmp/*"}
        )

        desc = permission_handler.get_pending_description()
        assert desc == "Run command: rm -rf /tmp/*"

    def test_get_pending_description_write(
        self, permission_handler: PermissionHandler
    ) -> None:
        """Test description for Write tool."""
        from voice_agent.sessions.permissions import PendingPermission

        permission_handler.pending = PendingPermission(
            tool_name="Write", input_data={"file_path": "/tmp/test.txt"}
        )

        desc = permission_handler.get_pending_description()
        assert desc == "Write file: /tmp/test.txt"

    def test_get_pending_description_edit(
        self, permission_handler: PermissionHandler
    ) -> None:
        """Test description for Edit tool."""
        from voice_agent.sessions.permissions import PendingPermission

        permission_handler.pending = PendingPermission(
            tool_name="Edit", input_data={"file_path": "/tmp/test.txt"}
        )

        desc = permission_handler.get_pending_description()
        assert desc == "Edit file: /tmp/test.txt"

    def test_get_pending_description_other(
        self, permission_handler: PermissionHandler
    ) -> None:
        """Test description for other tools."""
        from voice_agent.sessions.permissions import PendingPermission

        permission_handler.pending = PendingPermission(
            tool_name="SomeOtherTool", input_data={}
        )

        desc = permission_handler.get_pending_description()
        assert desc == "Use tool: SomeOtherTool"

    async def test_timeout_denies(self) -> None:
        """Test timeout results in denial."""
        handler = PermissionHandler(timeout=0.01)  # Very short timeout

        approved, message = await handler.request_permission(
            "Write", {"file_path": "/tmp/test"}
        )

        assert approved is False
        assert message == "Permission request timed out"
