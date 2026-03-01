# NixOS module for voice-agent.
#
# Optional deployment method. The voice-agent application itself is pure
# Python with zero NixOS dependency. This module wires it to systemd for
# users who deploy on NixOS.
#
# Usage (in your NixOS configuration):
#
#   {
#     imports = [ voice-agent.nixosModules.default ];
#
#     services.voice-agent = {
#       enable = true;
#       user = "paolino";
#       telegramBotTokenFile = "/run/secrets/telegram-bot-token";
#       anthropicApiKeyFile = "/run/secrets/anthropic-api-key";
#       workingDirectory = "/code";
#       whisperUrl = "http://localhost:9003/transcribe";
#     };
#   }
{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.services.voice-agent;
in
{
  options.services.voice-agent = {
    enable = lib.mkEnableOption "voice-agent Telegram bot for Claude Code";

    package = lib.mkOption {
      type = lib.types.package;
      description = ''
        The voice-agent package to run.
        Override this to use a different build.
      '';
    };

    user = lib.mkOption {
      type = lib.types.str;
      description = ''
        System user to run the service as. Must have access to
        ~/.claude/ for session discovery and handoff.
      '';
    };

    group = lib.mkOption {
      type = lib.types.str;
      default = "users";
      description = "Group to run the service as.";
    };

    telegramBotTokenFile = lib.mkOption {
      type = lib.types.path;
      description = ''
        Path to a file containing the Telegram bot token.
        The file should contain only the token, no newline.
        Compatible with sops-nix and agenix.
      '';
    };

    anthropicApiKeyFile = lib.mkOption {
      type = lib.types.path;
      description = ''
        Path to a file containing the Anthropic API key.
        The file should contain only the key, no newline.
      '';
    };

    workingDirectory = lib.mkOption {
      type = lib.types.str;
      default = "/code";
      description = "Default working directory for Claude sessions.";
    };

    whisperUrl = lib.mkOption {
      type = lib.types.str;
      default = "http://localhost:9003/transcribe";
      description = "URL of the Whisper transcription service.";
    };

    permissionTimeout = lib.mkOption {
      type = lib.types.int;
      default = 300;
      description = "Timeout in seconds for permission requests.";
    };

    extraEnvironment = lib.mkOption {
      type = lib.types.attrsOf lib.types.str;
      default = { };
      description = ''
        Additional environment variables to set.
        Do NOT put secrets here -- use the *File options instead.
      '';
    };
  };

  config = lib.mkIf cfg.enable {
    systemd.services.voice-agent = {
      description = "Voice Agent - Telegram bot for Claude Code";
      after = [
        "network-online.target"
      ];
      wants = [
        "network-online.target"
      ];
      wantedBy = [
        "multi-user.target"
      ];

      serviceConfig = {
        Type = "simple";
        User = cfg.user;
        Group = cfg.group;
        WorkingDirectory = cfg.workingDirectory;
        Restart = "on-failure";
        RestartSec = 10;

        # Load secrets from files at runtime
        LoadCredential = [
          "telegram-bot-token:${cfg.telegramBotTokenFile}"
          "anthropic-api-key:${cfg.anthropicApiKeyFile}"
        ];

        # Hardening
        NoNewPrivileges = true;
        ProtectSystem = "strict";
        ProtectHome = "no"; # Needs ~/.claude/ access
        ReadWritePaths = [
          cfg.workingDirectory
          "/home/${cfg.user}/.claude"
          "/tmp"
        ];
      };

      environment =
        {
          DEFAULT_CWD = cfg.workingDirectory;
          WHISPER_URL = cfg.whisperUrl;
          PERMISSION_TIMEOUT = toString cfg.permissionTimeout;
        }
        // cfg.extraEnvironment;

      # Read secrets from systemd credentials at startup
      script = ''
        export TELEGRAM_BOT_TOKEN="$(cat $CREDENTIALS_DIRECTORY/telegram-bot-token)"
        export ANTHROPIC_API_KEY="$(cat $CREDENTIALS_DIRECTORY/anthropic-api-key)"
        exec ${cfg.package}/bin/voice-agent
      '';
    };
  };
}
