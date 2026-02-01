# SDK Integration

## Current Implementation

The current implementation uses the Claude CLI in `--print` mode:

```python
cmd = [
    "claude",
    "--print",
    "--dangerously-skip-permissions",
    prompt,
]

process = await asyncio.create_subprocess_exec(
    *cmd,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
    cwd=session.cwd,
)
```

This approach:

- Uses `--print` to get plain text output
- Uses `--dangerously-skip-permissions` for non-interactive use
- Streams output line by line back to Telegram
- Uses Claude CLI's own authentication (via `claude login`)

## Authentication

Claude CLI handles its own authentication. Before running voice-agent:

```bash
claude login
```

This stores credentials that the CLI uses automatically.

## Future: Claude Agent SDK

The plan is to migrate to the official Claude Agent SDK for:

- **Structured responses**: Native message types instead of text parsing
- **Permission callbacks**: `canUseTool` callback for approval flow
- **Session persistence**: Resume sessions via `session_id`

### Planned SDK Usage

```python
from claude_code_sdk import ClaudeCodeClient

async def can_use_tool(tool_name: str, input_data: dict) -> bool:
    if is_safe_tool_call(tool_name, input_data):
        return True

    # Queue for user approval
    await notify_user(tool_name, input_data)
    return await wait_for_approval()

client = ClaudeCodeClient(
    cwd="/code/project",
    can_use_tool=can_use_tool,
)

async for message in client.query("list files"):
    process_message(message)
```

### Benefits of SDK

| CLI Approach | SDK Approach |
|--------------|--------------|
| Parse text output | Structured message objects |
| `--dangerously-skip-permissions` | `canUseTool` callback |
| Text streaming | Typed message objects |
| One process per prompt | Persistent client instance |

### Migration Path

1. Keep CLI implementation as fallback
2. Add SDK client alongside CLI
3. Switch based on configuration/availability
4. Remove CLI fallback once SDK is stable
