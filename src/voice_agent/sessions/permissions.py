"""Permission handling for Claude SDK tool calls.

Manages the canUseTool callback flow for requesting user approval.
"""

import asyncio
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Coroutine


class PermissionState(Enum):
    """State of a pending permission request."""

    PENDING = auto()
    APPROVED = auto()
    DENIED = auto()
    TIMEOUT = auto()


@dataclass
class PendingPermission:
    """A permission request waiting for user approval.

    Attributes:
        tool_name: Name of the tool requesting permission.
        input_data: Input parameters for the tool.
        event: Event to signal when user responds.
        state: Current state of the permission.
        deny_message: Optional message explaining denial.
    """

    tool_name: str
    input_data: dict[str, Any]
    event: asyncio.Event = field(default_factory=asyncio.Event)
    state: PermissionState = PermissionState.PENDING
    deny_message: str | None = None


# Tools that are always safe to allow
SAFE_TOOLS = frozenset({"Read", "Glob", "Grep", "WebSearch", "WebFetch"})

# Bash commands that are safe (read-only)
SAFE_BASH_PATTERNS = frozenset(
    {
        "ls",
        "cat",
        "head",
        "tail",
        "pwd",
        "echo",
        "which",
        "git status",
        "git log",
        "git diff",
        "git branch",
        "git show",
    }
)


def is_safe_bash_command(command: str) -> bool:
    """Check if a bash command is safe to auto-approve.

    Args:
        command: The bash command string.

    Returns:
        True if the command is safe (read-only).
    """
    command = command.strip()
    for pattern in SAFE_BASH_PATTERNS:
        if command.startswith(pattern):
            return True
    return False


def is_safe_tool_call(tool_name: str, input_data: dict[str, Any]) -> bool:
    """Check if a tool call is safe to auto-approve.

    Args:
        tool_name: Name of the tool.
        input_data: Input parameters for the tool.

    Returns:
        True if the tool call is safe.
    """
    if tool_name in SAFE_TOOLS:
        return True

    if tool_name == "Bash":
        command = input_data.get("command", "")
        return is_safe_bash_command(command)

    return False


class PermissionHandler:
    """Handles permission requests for Claude SDK tool calls.

    Attributes:
        pending: Current pending permission, if any.
        timeout: Seconds to wait for user approval.
        notify_callback: Async callback to notify user of permission request.
    """

    def __init__(
        self,
        timeout: int = 300,
        notify_callback: Callable[
            [str, dict[str, Any]], Coroutine[Any, Any, None]
        ] | None = None,
    ) -> None:
        """Initialize the permission handler.

        Args:
            timeout: Seconds to wait for user approval.
            notify_callback: Async function to notify user of permission request.
        """
        self.pending: PendingPermission | None = None
        self.timeout = timeout
        self.notify_callback = notify_callback

    def has_pending(self) -> bool:
        """Check if there's a pending permission request.

        Returns:
            True if a permission is pending.
        """
        return self.pending is not None and self.pending.state == PermissionState.PENDING

    def get_pending_description(self) -> str | None:
        """Get a human-readable description of the pending permission.

        Returns:
            Description string or None if no pending permission.
        """
        if not self.pending:
            return None

        tool = self.pending.tool_name
        inputs = self.pending.input_data

        if tool == "Bash":
            return f"Run command: {inputs.get('command', 'unknown')}"
        if tool == "Write":
            return f"Write file: {inputs.get('file_path', 'unknown')}"
        if tool == "Edit":
            return f"Edit file: {inputs.get('file_path', 'unknown')}"

        return f"Use tool: {tool}"

    async def request_permission(
        self, tool_name: str, input_data: dict[str, Any]
    ) -> tuple[bool, str | None]:
        """Request permission for a tool call.

        Auto-approves safe tools, queues others for user approval.

        Args:
            tool_name: Name of the tool.
            input_data: Input parameters for the tool.

        Returns:
            Tuple of (approved, deny_message).
        """
        # Auto-approve safe tools
        if is_safe_tool_call(tool_name, input_data):
            return True, None

        # Create pending permission
        self.pending = PendingPermission(tool_name=tool_name, input_data=input_data)

        # Notify user if callback provided
        if self.notify_callback:
            await self.notify_callback(tool_name, input_data)

        # Wait for user response with timeout
        try:
            await asyncio.wait_for(self.pending.event.wait(), timeout=self.timeout)
            approved = self.pending.state == PermissionState.APPROVED
            message = self.pending.deny_message
            self.pending = None
            return approved, message
        except asyncio.TimeoutError:
            self.pending.state = PermissionState.TIMEOUT
            self.pending = None
            return False, "Permission request timed out"

    def approve(self) -> bool:
        """Approve the pending permission.

        Returns:
            True if there was a pending permission to approve.
        """
        if not self.pending or self.pending.state != PermissionState.PENDING:
            return False
        self.pending.state = PermissionState.APPROVED
        self.pending.event.set()
        return True

    def deny(self, message: str | None = None) -> bool:
        """Deny the pending permission.

        Args:
            message: Optional message explaining denial.

        Returns:
            True if there was a pending permission to deny.
        """
        if not self.pending or self.pending.state != PermissionState.PENDING:
            return False
        self.pending.state = PermissionState.DENIED
        self.pending.deny_message = message or "User rejected"
        self.pending.event.set()
        return True
