"""Unit tests for command routing."""

import pytest

from voice_agent.router import CommandType, parse_command


@pytest.mark.unit
class TestParseCommand:
    """Tests for parse_command function."""

    @pytest.mark.parametrize(
        "text",
        ["yes", "Yes", "YES", "approve", "Approve", "ok", "okay", "yep"],
    )
    def test_approve_keywords(self, text: str) -> None:
        """Test approval keyword detection."""
        result = parse_command(text)
        assert result.command_type == CommandType.APPROVE
        assert result.text == text

    @pytest.mark.parametrize(
        "text",
        ["no", "No", "NO", "reject", "Reject", "stop", "deny", "cancel", "nope"],
    )
    def test_reject_keywords(self, text: str) -> None:
        """Test rejection keyword detection."""
        result = parse_command(text)
        assert result.command_type == CommandType.REJECT
        assert result.text == text

    @pytest.mark.parametrize(
        "text",
        ["status", "Status", "what's happening", "progress", "state"],
    )
    def test_status_keywords(self, text: str) -> None:
        """Test status keyword detection."""
        result = parse_command(text)
        assert result.command_type == CommandType.STATUS

    @pytest.mark.parametrize(
        "text",
        ["new session", "New Session", "fresh session", "start over", "reset"],
    )
    def test_new_session_keywords(self, text: str) -> None:
        """Test new session keyword detection."""
        result = parse_command(text)
        assert result.command_type == CommandType.NEW_SESSION

    @pytest.mark.parametrize(
        "text",
        [
            "continue",
            "Continue",
            "resume",
            "Resume",
            "continue session",
            "resume session",
        ],
    )
    def test_continue_session_keywords(self, text: str) -> None:
        """Test continue session keyword detection."""
        result = parse_command(text)
        assert result.command_type == CommandType.CONTINUE_SESSION

    def test_switch_project_work_on(self) -> None:
        """Test 'work on PROJECT' format."""
        projects = {"whisper": "/code/whisper-server"}
        result = parse_command("work on whisper", projects)
        assert result.command_type == CommandType.SWITCH_PROJECT
        assert result.project == "whisper"

    def test_switch_project_switch_to(self) -> None:
        """Test 'switch to PROJECT' format."""
        projects = {"agent": "/code/voice-agent"}
        result = parse_command("switch to agent", projects)
        assert result.command_type == CommandType.SWITCH_PROJECT
        assert result.project == "agent"

    def test_switch_project_on_prefix(self) -> None:
        """Test 'on PROJECT:' format."""
        projects = {"whisper": "/code/whisper-server"}
        result = parse_command("on whisper: list files", projects)
        assert result.command_type == CommandType.SWITCH_PROJECT
        assert result.project == "whisper"
        assert result.text == "list files"

    def test_switch_project_unknown(self) -> None:
        """Test unknown project falls through to prompt."""
        projects = {"whisper": "/code/whisper-server"}
        result = parse_command("work on unknown", projects)
        assert result.command_type == CommandType.PROMPT

    def test_regular_prompt(self) -> None:
        """Test regular text becomes a prompt."""
        result = parse_command("list files in current directory")
        assert result.command_type == CommandType.PROMPT
        assert result.text == "list files in current directory"

    def test_prompt_with_projects_context(self) -> None:
        """Test regular prompt doesn't match project patterns."""
        projects = {"whisper": "/code/whisper-server"}
        result = parse_command("check the whisper server logs", projects)
        assert result.command_type == CommandType.PROMPT

    def test_empty_text(self) -> None:
        """Test empty text becomes prompt."""
        result = parse_command("")
        assert result.command_type == CommandType.PROMPT

    def test_whitespace_handling(self) -> None:
        """Test whitespace is handled correctly."""
        result = parse_command("  yes  ")
        assert result.command_type == CommandType.APPROVE

    @pytest.mark.parametrize(
        "text",
        [
            "always approve",
            "Always Approve",
            "sticky yes",
            "remember yes",
            "always yes",
            "always allow",
        ],
    )
    def test_sticky_approve_keywords(self, text: str) -> None:
        """Test sticky approve keyword detection."""
        result = parse_command(text)
        assert result.command_type == CommandType.STICKY_APPROVE
        assert result.text == text

    @pytest.mark.parametrize(
        "text",
        [
            "clear sticky",
            "Clear Sticky",
            "clear approvals",
            "forget approvals",
        ],
    )
    def test_clear_sticky_keywords(self, text: str) -> None:
        """Test clear sticky keyword detection."""
        result = parse_command(text)
        assert result.command_type == CommandType.CLEAR_STICKY
        assert result.text == text

    @pytest.mark.parametrize(
        "text",
        [
            "escape",
            "abort",
            "interrupt",
            "stop task",
            "cancel task",
            "stop it",
            "fermati",
            "basta",
        ],
    )
    def test_cancel_keywords(self, text: str) -> None:
        """Test cancel keyword detection."""
        result = parse_command(text)
        assert result.command_type == CommandType.CANCEL
        assert result.text == text

    @pytest.mark.parametrize(
        "text",
        [
            "list approvals",
            "List Approvals",
            "show approvals",
            "approvals",
            "what's approved",
            "whats approved",
        ],
    )
    def test_list_approvals_keywords(self, text: str) -> None:
        """Test list approvals keyword detection."""
        result = parse_command(text)
        assert result.command_type == CommandType.LIST_APPROVALS
        assert result.text == text
