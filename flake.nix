{
  description = "Voice control for Claude Code via Telegram";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = nixpkgs.legacyPackages.${system};

        python = pkgs.python311;

        pythonPackages = python.pkgs;

        voiceAgent = pythonPackages.buildPythonApplication {
          pname = "voice-agent";
          version = "0.1.0";
          pyproject = true;

          src = ./.;

          build-system = [ pythonPackages.setuptools ];

          dependencies = [
            pythonPackages.python-telegram-bot
            pythonPackages.httpx
            pythonPackages.pydantic
            pythonPackages.pydantic-settings
          ];

          nativeCheckInputs = [
            pythonPackages.pytest
            pythonPackages.pytest-asyncio
            pythonPackages.pytest-cov
            pythonPackages.pytest-httpx
            pythonPackages.pytest-mock
          ];

          checkPhase = ''
            runHook preCheck
            pytest tests/unit -v
            runHook postCheck
          '';

          meta = {
            description = "Voice control for Claude Code via Telegram";
            mainProgram = "voice-agent";
          };
        };

        devShell = pkgs.mkShell {
          packages = [
            python
            pythonPackages.python-telegram-bot
            pythonPackages.httpx
            pythonPackages.pydantic
            pythonPackages.pydantic-settings
            pythonPackages.pytest
            pythonPackages.pytest-asyncio
            pythonPackages.pytest-cov
            pythonPackages.pytest-httpx
            pythonPackages.pytest-mock
            pythonPackages.ruff
            pythonPackages.mypy
            pkgs.just
          ];

          shellHook = ''
            export PYTHONPATH="$PWD/src:$PYTHONPATH"
          '';
        };
      in
      {
        packages = {
          default = voiceAgent;
          voice-agent = voiceAgent;
        };

        devShells.default = devShell;

        apps.default = {
          type = "app";
          program = "${voiceAgent}/bin/voice-agent";
        };
      }
    );
}
