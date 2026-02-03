# Deployment Guide

## Systemd Service

Create `/etc/systemd/system/voice-agent.service`:

```ini
[Unit]
Description=Voice Agent - Telegram bot for Claude Code
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/opt/voice-agent
EnvironmentFile=/opt/voice-agent/.env
ExecStart=/usr/bin/python -m voice_agent
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable voice-agent
sudo systemctl start voice-agent
sudo journalctl -u voice-agent -f  # View logs
```

## NixOS Module

```nix
{ config, pkgs, ... }:

{
  systemd.services.voice-agent = {
    description = "Voice Agent Telegram Bot";
    after = [ "network.target" ];
    wantedBy = [ "multi-user.target" ];

    serviceConfig = {
      Type = "simple";
      User = "voice-agent";
      WorkingDirectory = "/var/lib/voice-agent";
      ExecStart = "${pkgs.voice-agent}/bin/voice-agent";
      Restart = "always";
      RestartSec = 10;
    };

    environment = {
      TELEGRAM_BOT_TOKEN = "your-token";
      WHISPER_URL = "http://localhost:8080/transcribe";
      ALLOWED_CHAT_IDS = "123456789";
      DEFAULT_CWD = "/code";
    };
  };

  users.users.voice-agent = {
    isSystemUser = true;
    group = "voice-agent";
    home = "/var/lib/voice-agent";
  };

  users.groups.voice-agent = {};
}
```

## Docker

### Claude CLI Requirement

Voice-agent uses the Claude Agent SDK which spawns Claude Code CLI as a subprocess.
The Docker container does **not** include Claude CLI - you must provide it by mounting
the executable from your host system.

This design allows voice-agent to use your authenticated Claude CLI with your API key
and settings, rather than bundling a potentially outdated version.

### Standard Linux (FHS)

If Claude CLI is installed at a standard location (e.g., `/usr/local/bin/claude`):

```yaml
services:
  voice-agent:
    image: ghcr.io/paolino/voice-agent:latest
    environment:
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}
      WHISPER_URL: http://whisper:9003/transcribe
      DEFAULT_CWD: /code
      HOME: /home/user
      PATH: /usr/local/bin:/usr/bin:/bin
    volumes:
      - ~/.claude:/home/user/.claude           # Claude settings (read-write)
      - /code:/code                            # Working directory
      - /usr/local/bin/claude:/usr/local/bin/claude:ro  # Claude CLI
```

### NixOS

On NixOS, Claude CLI and its dependencies are in `/nix/store`. Mount the entire
nix store and the system binaries:

```yaml
services:
  whisper:
    image: ghcr.io/paolino/whisper-server:latest
    environment:
      WHISPER_MODEL: ${WHISPER_MODEL:-small}
      WHISPER_HTTP_PORT: "9003"
      WHISPER_DEVICE: auto
      WHISPER_COMPUTE_TYPE: auto
    ports:
      - "9003:9003"
    restart: unless-stopped

  voice-agent:
    image: ghcr.io/paolino/voice-agent:${VOICE_AGENT_VERSION:-latest}
    environment:
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}
      WHISPER_URL: http://whisper:9003/transcribe
      SESSION_STORAGE_PATH: /data/sessions.json
      DEFAULT_CWD: /code
      HOME: /tmp
      PATH: /run/current-system/sw/bin:/usr/bin:/bin
    volumes:
      - ./data:/data                                      # Session storage
      - ${HOME}/.claude:/tmp/.claude                      # Claude settings
      - /code:/code                                       # Working directory
      - /nix/store:/nix/store:ro                          # Nix store (dependencies)
      - /run/current-system/sw/bin:/run/current-system/sw/bin:ro  # System binaries
    depends_on:
      - whisper
    restart: unless-stopped
```

Key points for NixOS:

- `/nix/store` contains Claude CLI and all its dependencies (node, bash, etc.)
- `/run/current-system/sw/bin` contains the `claude` wrapper script
- `HOME=/tmp` because `.claude` is mounted at `/tmp/.claude`
- `.claude` must be read-write (Claude writes debug files, todos, etc.)

### Configuration

Create `~/.config/voice-agent/.env`:

```bash
TELEGRAM_BOT_TOKEN=your-bot-token
VOICE_AGENT_VERSION=latest  # or specific commit hash
ALLOWED_CHAT_IDS=123456789  # optional
```

Start with:

```bash
docker compose --env-file ~/.config/voice-agent/.env up -d
```

### Using just (voice-agent repo)

The voice-agent repo includes a `just deploy-local` command:

```bash
cd /code/voice-agent
just deploy-local  # Builds image, updates version, restarts compose
```

This command:
1. Builds the Docker image with nix
2. Loads it into Docker
3. Updates `VOICE_AGENT_VERSION` in `~/.config/voice-agent/.env`
4. Restarts the compose stack

## Environment Variables

Store secrets securely:

```bash
# Using systemd
sudo systemctl edit voice-agent
# Add:
# [Service]
# Environment="TELEGRAM_BOT_TOKEN=secret"

# Using env file (chmod 600)
echo "TELEGRAM_BOT_TOKEN=secret" >> /opt/voice-agent/.env
chmod 600 /opt/voice-agent/.env
```

## Health Checks

The bot logs to stdout/journald. Monitor for:

- "Starting Voice Agent bot..." - Successful start
- "Downloaded X bytes of audio" - Processing messages
- "Transcription failed" - Whisper server issues

## Claude CLI Authentication

The service needs Claude CLI authenticated. Options:

1. **Run as your user** - Has your `~/.claude` config
2. **Mount config** - Mount your `.claude` directory (must be read-write)
3. **Service account** - Run `claude login` as the service user

### Troubleshooting

**"Claude Code not found"**: The container can't find the `claude` executable.
Check that it's mounted and in PATH.

**"Control request timeout: initialize"**: Claude CLI is found but can't start.
Usually means `.claude` is mounted read-only. Claude needs to write debug files.

**"EROFS: read-only file system"**: The `.claude` directory is mounted with `:ro`.
Remove the read-only flag - Claude needs write access.
