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

        version = "0.1.0";

        python = pkgs.python311;

        pythonPackages = python.pkgs;

        # Build claude-agent-sdk from PyPI (not in nixpkgs)
        # The SDK bundles the Claude CLI binary
        claudeAgentSdk = pythonPackages.buildPythonPackage {
          pname = "claude-agent-sdk";
          version = "0.1.27";
          format = "wheel";

          src = pkgs.fetchurl {
            url = "https://files.pythonhosted.org/packages/84/06/886931dcbce8cd586aa38afa3ebdefe7d9eaa4ad389fa795560317c1f891/claude_agent_sdk-0.1.27-py3-none-manylinux_2_17_x86_64.whl";
            sha256 = "0yw8bwph5pdk5kycwmdqciyqsyri1sz2i3i117wvvrwc83rj43ny";
          };

          propagatedBuildInputs = [
            pythonPackages.httpx
            pythonPackages.pydantic
            pythonPackages.mcp
          ];

          # Fix bundled CLI permissions
          postInstall = ''
            chmod +x $out/lib/python*/site-packages/claude_agent_sdk/_bundled/claude
          '';

          doCheck = false;
        };

        dockerImage = import ./nix/docker-image.nix {
          inherit pkgs version claudeAgentSdk;
        };

        voiceAgent = pythonPackages.buildPythonApplication {
          pname = "voice-agent";
          inherit version;
          pyproject = true;

          src = ./.;

          build-system = [ pythonPackages.setuptools ];

          dependencies = [
            pythonPackages.python-telegram-bot
            pythonPackages.httpx
            pythonPackages.pydantic
            pythonPackages.pydantic-settings
            claudeAgentSdk
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

        # Python environment with test dependencies
        testEnv = python.withPackages (ps: [
          ps.pytest
          ps.pytest-asyncio
          ps.pytest-cov
          ps.pytest-httpx
          ps.pytest-mock
          ps.python-telegram-bot
          ps.httpx
          ps.pydantic
          ps.pydantic-settings
        ]);

        # Copy tests and conftest together
        testSuite = pkgs.runCommand "voice-agent-test-suite" {} ''
          mkdir -p $out/unit
          cp ${./tests/conftest.py} $out/conftest.py
          cp -r ${./tests/unit}/* $out/unit/
        '';

        # Test runner as a script
        testRunner = pkgs.writeShellScriptBin "voice-agent-tests" ''
          export PYTHONPATH="${./src}:$PYTHONPATH"
          exec ${testEnv}/bin/python -m pytest ${testSuite}/unit \
            --confcutdir=${testSuite} \
            -p pytest_asyncio \
            -o asyncio_mode=auto \
            -o asyncio_default_fixture_loop_scope=function \
            -v "$@"
        '';

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
            claudeAgentSdk
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
          docker-image = dockerImage;
          tests = testRunner;
        };

        devShells.default = devShell;

        apps = {
          default = {
            type = "app";
            program = "${voiceAgent}/bin/voice-agent";
          };
          tests = {
            type = "app";
            program = "${testRunner}/bin/voice-agent-tests";
          };
        };
      }
    );
}
