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
#       # anthropicApiKeyFile = "/run/secrets/anthropic-api-key";  # optional
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

    claudePackage = lib.mkOption {
      type = lib.types.nullOr lib.types.package;
      default = null;
      description = ''
        Claude Code CLI package. When set, the system CLI is used
        instead of the outdated binary bundled in the SDK.
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
      type = lib.types.nullOr lib.types.path;
      default = null;
      description = ''
        Path to a file containing the Anthropic API key.
        The file should contain only the key, no newline.
        Optional — if null, ANTHROPIC_API_KEY is not set.
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

    allowedChatIds = lib.mkOption {
      type = lib.types.listOf lib.types.int;
      default = [ ];
      description = ''
        List of Telegram chat IDs allowed to use the bot.
        If empty, all chats are allowed (not recommended).
      '';
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

      path = lib.optionals (cfg.claudePackage != null) [ cfg.claudePackage ];

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
        ] ++ lib.optionals (cfg.anthropicApiKeyFile != null) [
          "anthropic-api-key:${cfg.anthropicApiKeyFile}"
        ];

        # Hardening (light: service needs broad host access for
        # ~/.claude/ sessions, /code/ workdirs, and process inspection)
        NoNewPrivileges = true;
      };

      environment =
        {
          DEFAULT_CWD = cfg.workingDirectory;
          WHISPER_URL = cfg.whisperUrl;
          PERMISSION_TIMEOUT = toString cfg.permissionTimeout;
        }
        // lib.optionalAttrs (cfg.allowedChatIds != [ ]) {
          ALLOWED_CHAT_IDS = lib.concatMapStringsSep "," toString cfg.allowedChatIds;
        }
        // cfg.extraEnvironment;

      # Read secrets from systemd credentials at startup
      script = ''
        export TELEGRAM_BOT_TOKEN="$(cat $CREDENTIALS_DIRECTORY/telegram-bot-token)"
        ${lib.optionalString (cfg.anthropicApiKeyFile != null) ''
          export ANTHROPIC_API_KEY="$(cat $CREDENTIALS_DIRECTORY/anthropic-api-key)"
        ''}
        exec ${cfg.package}/bin/voice-agent
      '';
    };
  };
}
