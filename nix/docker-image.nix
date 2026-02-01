{
  pkgs,
  version,
}:
let
  pythonEnv = pkgs.python3.withPackages (
    ps: with ps; [
      python-telegram-bot
      httpx
      pydantic
      pydantic-settings
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
  tag = version;

  copyToRoot = pkgs.buildEnv {
    name = "voice-agent-root";
    paths = [
      pythonEnv
      pkgs.cacert
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
    ];
    Labels = {
      "org.opencontainers.image.source" = "https://github.com/paolino/voice-agent";
      "org.opencontainers.image.description" = "Voice control for Claude Code via Telegram";
      "org.opencontainers.image.licenses" = "MIT";
      "org.opencontainers.image.version" = version;
    };
  };
}
