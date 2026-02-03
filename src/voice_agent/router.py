"""Command routing for voice transcriptions.

Parses intent from transcribed text and routes to appropriate handlers.
"""

from dataclasses import dataclass
from enum import Enum, auto


class CommandType(Enum):
    """Types of commands that can be parsed from voice input."""

    APPROVE = auto()
    REJECT = auto()
    STICKY_APPROVE = auto()
    CLEAR_STICKY = auto()
    LIST_APPROVALS = auto()
    STATUS = auto()
    NEW_SESSION = auto()
    CONTINUE_SESSION = auto()
    SWITCH_PROJECT = auto()
    CANCEL = auto()
    RESTART = auto()
    SESSIONS = auto()
    PROMPT = auto()


@dataclass
class ParsedCommand:
    """Result of parsing a voice transcription.

    Attributes:
        command_type: The type of command detected.
        text: The original transcription text.
        project: Project name if SWITCH_PROJECT command.
    """

    command_type: CommandType
    text: str
    project: str | None = None


# Keywords for command detection (lowercase)
APPROVE_KEYWORDS = frozenset(
    {"yes", "approve", "approved", "allow", "ok", "okay", "go ahead", "yep"}
)
REJECT_KEYWORDS = frozenset(
    {"no", "reject", "rejected", "stop", "deny", "denied", "cancel", "nope"}
)
STATUS_KEYWORDS = frozenset({"status", "what's happening", "progress", "state"})
NEW_SESSION_KEYWORDS = frozenset(
    {"new session", "fresh session", "start over", "reset"}
)
CONTINUE_SESSION_KEYWORDS = frozenset(
    {
        "continue",
        "resume",
        "continue session",
        "resume session",
        "pick up where we left off",
    }
)
STICKY_APPROVE_KEYWORDS = frozenset(
    {
        "always approve",
        "sticky yes",
        "remember yes",
        "always yes",
        "always allow",
    }
)
CLEAR_STICKY_KEYWORDS = frozenset(
    {
        "clear sticky",
        "clear approvals",
        "forget approvals",
    }
)
LIST_APPROVALS_KEYWORDS = frozenset(
    {
        "list approvals",
        "show approvals",
        "approvals",
        "what's approved",
        "whats approved",
    }
)
CANCEL_KEYWORDS = frozenset(
    {
        "escape",
        "abort",
        "interrupt",
        "stop task",
        "cancel task",
        "stop it",
        "fermati",
        "basta",
    }
)
RESTART_KEYWORDS = frozenset(
    {
        "restart",
        "restart session",
        "riavvia",
        "ricomincia",
    }
)
SESSIONS_KEYWORDS = frozenset(
    {
        "sessions",
        "show sessions",
        "list sessions",
        "my sessions",
    }
)


def parse_command(text: str, projects: dict[str, str] | None = None) -> ParsedCommand:
    """Parse a voice transcription into a command.

    Args:
        text: Transcribed text from voice input.
        projects: Optional mapping of project names to paths for switch detection.

    Returns:
        ParsedCommand with detected intent.
    """
    # Strip punctuation and whitespace for matching
    lower_text = text.lower().strip().rstrip(".,!?")

    # Check for exact or near-exact matches first
    if lower_text in APPROVE_KEYWORDS:
        return ParsedCommand(command_type=CommandType.APPROVE, text=text)

    if lower_text in REJECT_KEYWORDS:
        return ParsedCommand(command_type=CommandType.REJECT, text=text)

    # Check for status keywords
    for keyword in STATUS_KEYWORDS:
        if keyword in lower_text:
            return ParsedCommand(command_type=CommandType.STATUS, text=text)

    # Check for new session keywords
    for keyword in NEW_SESSION_KEYWORDS:
        if keyword in lower_text:
            return ParsedCommand(command_type=CommandType.NEW_SESSION, text=text)

    # Check for continue session keywords
    for keyword in CONTINUE_SESSION_KEYWORDS:
        if keyword in lower_text:
            return ParsedCommand(command_type=CommandType.CONTINUE_SESSION, text=text)

    # Check for sticky approve keywords
    for keyword in STICKY_APPROVE_KEYWORDS:
        if keyword in lower_text:
            return ParsedCommand(command_type=CommandType.STICKY_APPROVE, text=text)

    # Check for clear sticky keywords
    for keyword in CLEAR_STICKY_KEYWORDS:
        if keyword in lower_text:
            return ParsedCommand(command_type=CommandType.CLEAR_STICKY, text=text)

    # Check for list approvals keywords
    for keyword in LIST_APPROVALS_KEYWORDS:
        if keyword in lower_text:
            return ParsedCommand(command_type=CommandType.LIST_APPROVALS, text=text)

    # Check for cancel/escape keywords
    for keyword in CANCEL_KEYWORDS:
        if keyword in lower_text:
            return ParsedCommand(command_type=CommandType.CANCEL, text=text)

    # Check for restart keywords (exact match to avoid false positives)
    if lower_text in RESTART_KEYWORDS:
        return ParsedCommand(command_type=CommandType.RESTART, text=text)

    # Check for sessions keywords
    for keyword in SESSIONS_KEYWORDS:
        if keyword in lower_text:
            return ParsedCommand(command_type=CommandType.SESSIONS, text=text)

    # Check for project switch commands
    if projects:
        # Check for "on PROJECT: command" format first
        if lower_text.startswith("on ") and ":" in lower_text:
            parts = lower_text.split(":", 1)
            project_part = parts[0][3:].strip()
            for name in projects:
                if name in project_part or project_part in name:
                    return ParsedCommand(
                        command_type=CommandType.SWITCH_PROJECT,
                        text=parts[1].strip() if len(parts) > 1 else text,
                        project=name,
                    )

        for prefix in ("work on ", "switch to ", "on "):
            if lower_text.startswith(prefix):
                project_name = lower_text[len(prefix) :].strip().rstrip(":")
                if project_name in projects:
                    return ParsedCommand(
                        command_type=CommandType.SWITCH_PROJECT,
                        text=text,
                        project=project_name,
                    )
                # Check partial matches
                for name in projects:
                    if name in project_name or project_name in name:
                        return ParsedCommand(
                            command_type=CommandType.SWITCH_PROJECT,
                            text=text,
                            project=name,
                        )

    # Check for skill invocation: "skill X" -> "/X"
    if lower_text.startswith("skill "):
        skill_name = lower_text[6:].strip()
        if skill_name:
            return ParsedCommand(
                command_type=CommandType.PROMPT, text=f"/{skill_name}"
            )

    # Default: treat as a prompt to send to Claude
    return ParsedCommand(command_type=CommandType.PROMPT, text=text)
