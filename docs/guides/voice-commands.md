# Voice Commands

## Overview

voice-agent interprets your voice messages and routes them appropriately. Some phrases are recognized as commands, while others are sent directly to Claude.

## Permission Commands

When Claude requests permission for a potentially dangerous action:

| Say this | Effect |
|----------|--------|
| "yes" | Approve the pending permission |
| "approve" | Approve the pending permission |
| "ok" / "okay" | Approve the pending permission |
| "continue" | Approve the pending permission |
| "go ahead" | Approve the pending permission |
| "no" | Deny the pending permission |
| "reject" | Deny the pending permission |
| "stop" | Deny the pending permission |
| "cancel" | Deny the pending permission |

## Session Commands

| Say this | Effect |
|----------|--------|
| "status" | Show current session info |
| "new session" | Start a fresh session |
| "fresh session" | Start a fresh session |
| "start over" | Start a fresh session |
| "reset" | Start a fresh session |

## Project Switching

If you have projects configured:

| Say this | Effect |
|----------|--------|
| "work on whisper" | Switch to whisper project directory |
| "switch to agent" | Switch to agent project directory |
| "on whisper: list files" | Run command in whisper directory |

## Claude Prompts

Anything else is sent directly to Claude:

| Say this | Claude does |
|----------|-------------|
| "list files" | Lists files in current directory |
| "show me the readme" | Displays README content |
| "find all python files" | Searches for .py files |
| "what does this function do" | Explains code |
| "fix the bug in main.py" | Attempts to fix issues |

## Tips for Clear Commands

1. **Speak clearly** - Whisper works best with clear speech
2. **Be specific** - "list files in src" is better than "show me stuff"
3. **Use natural language** - Claude understands context
4. **Wait for responses** - Don't send multiple messages before Claude responds

## Examples

### Basic Usage

```
You: "list all python files"
Bot: list all python files (italic)
Bot: Here are the Python files...
```

### Permission Flow

```
You: "create a new file called test.py"
Bot: create a new file called test.py (italic)
Bot: Claude wants to: Write file: /code/test.py
     [Approve] [Reject] buttons
Bot: Approved.
Bot: Created test.py with...
```

### Project Switching

```
You: "work on whisper"
Bot: work on whisper (italic)
Bot: Switched to whisper (/code/whisper-server)

You: "show the main file"
Bot: [Shows files from whisper-server directory]
```
