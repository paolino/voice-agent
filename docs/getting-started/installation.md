# Installation

## Using Nix (Recommended)

The project includes a Nix flake for reproducible builds:

```bash
# Enter development shell
nix develop

# Run directly
nix run github:paolino/voice-agent

# Build the package
nix build
```

## Using pip

```bash
# Install from source
pip install -e .

# Install with development dependencies
pip install -e ".[dev,test,docs]"
```

## Dependencies

The main dependencies are:

- `python-telegram-bot` - Async Telegram bot framework
- `httpx` - Async HTTP client for whisper-server
- `pydantic` - Settings validation
- `pydantic-settings` - Environment variable loading

## External Services

### Whisper Server

You need a running whisper-server instance for transcription. The server should expose a `/transcribe` endpoint that accepts audio files and returns JSON with a `text` field.

Example whisper-server: [github.com/paolino/whisper-server](https://github.com/paolino/whisper-server)

### Claude CLI

The bot uses the Claude CLI for interacting with Claude Code. Make sure it's installed and in your PATH:

```bash
# Verify installation
claude --version
```

### Telegram Bot

Create a bot via [@BotFather](https://t.me/BotFather) on Telegram:

1. Send `/newbot` to @BotFather
2. Choose a name and username
3. Copy the bot token
