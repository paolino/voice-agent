{
  pkgs,
  version,
  imageTag,
  python,
  claudeAgentSdk,
}:
let
  pythonEnv = python.withPackages (
    ps: [
      ps.python-telegram-bot
      ps.httpx
      ps.pydantic
      ps.pydantic-settings
      claudeAgentSdk
    ]
  );

  startScript = pkgs.writeShellScript "start-voice-agent" ''
    set -euo pipefail
    export HOME=/tmp
    export PYTHONPATH="/app:''${PYTHONPATH:-}"
    exec python -m voice_agent
  '';
in
pkgs.dockerTools.buildImage {
  name = "ghcr.io/paolino/voice-agent";
  tag = imageTag;

  copyToRoot = pkgs.buildEnv {
    name = "voice-agent-root";
    paths = [
      pythonEnv
      pkgs.cacert
      pkgs.bash
    ];
    pathsToLink = [
      "/bin"
      "/lib"
    ];
  };

  extraCommands = ''
    mkdir -p app/voice_agent tmp
    cp -r ${../src/voice_agent}/* app/voice_agent/
  '';

  config = {
    Cmd = [ startScript ];
    WorkingDir = "/app";
    Env = [
      "SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
      "WHISPER_URL=http://localhost:8080/transcribe"
      "DEFAULT_CWD=/code"
      "PERMISSION_TIMEOUT=300"
      "SHELL=/bin/bash"
    ];
    Labels = {
      "org.opencontainers.image.source" = "https://github.com/paolino/voice-agent";
      "org.opencontainers.image.description" = "Voice control for Claude Code via Telegram";
      "org.opencontainers.image.licenses" = "MIT";
      "org.opencontainers.image.version" = version;
    };
  };
}
