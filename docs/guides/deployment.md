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

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .
RUN pip install -e .

# Claude CLI must be installed and authenticated
# Mount the claude config directory at runtime

CMD ["python", "-m", "voice_agent"]
```

```yaml
# docker-compose.yml
version: "3.8"

services:
  voice-agent:
    build: .
    environment:
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - WHISPER_URL=http://whisper:8080/transcribe
      - ALLOWED_CHAT_IDS=${ALLOWED_CHAT_IDS}
    volumes:
      - ~/.claude:/root/.claude:ro  # Claude CLI config
      - /code:/code:rw              # Working directories
    depends_on:
      - whisper

  whisper:
    image: your-whisper-server
    ports:
      - "8080:8080"
```

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
2. **Mount config** - Mount your `.claude` directory
3. **Service account** - Run `claude login` as the service user
