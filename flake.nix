# Voice Agent Nix Flake
#
# Key decisions documented below. Run with:
#   nix run .#voice-agent    - Run the bot
#   nix run .#tests          - Run unit tests
#   nix build .#docker-image - Build Docker image
#   nix develop              - Enter dev shell
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
        # =====================================================================
        # Package Overrides
        # =====================================================================
        # Why apscheduler.doCheck = false:
        #   - apscheduler 3.11.1 has a flaky test in CI environments:
        #     test_submit_job[processpool-pytz-executed] fails with
        #     "assert 16384 == 4096" due to timing/resource constraints
        #   - python-telegram-bot depends on apscheduler, so this blocks builds
        # =====================================================================
        pkgs = import nixpkgs {
          inherit system;
          overlays = [
            (final: prev: {
              python311 = prev.python311.override {
                packageOverrides = pyFinal: pyPrev: {
                  # apscheduler has flaky tests in CI (processpool timing issues)
                  apscheduler = pyPrev.apscheduler.overrideAttrs (old: {
                    doCheck = false;
                  });
                  # python-telegram-bot's test deps include apscheduler
                  python-telegram-bot = pyPrev.python-telegram-bot.overrideAttrs (old: {
                    doCheck = false;
                  });
                };
              };
            })
          ];
        };

        version = "0.1.0";

        python = pkgs.python311;

        pythonPackages = python.pkgs;

        # =====================================================================
        # Claude Agent SDK
        # =====================================================================
        # Why wheel format:
        #   - claude-agent-sdk is not in nixpkgs
        #   - The SDK bundles a pre-compiled Claude CLI binary that must be
        #     preserved (building from source would lose it)
        #
        # Why propagatedBuildInputs includes mcp:
        #   - The SDK's wheel metadata doesn't declare mcp as a dependency,
        #     but it imports mcp.types at runtime. Without this, you get:
        #     "ModuleNotFoundError: No module named 'mcp'"
        #
        # Why postInstall chmod:
        #   - The bundled CLI binary loses execute permissions when unpacked
        #     from the wheel. Without this fix, SDK fails to spawn Claude.
        # =====================================================================
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
            pythonPackages.mcp # Required but not declared in wheel metadata
          ];

          postInstall = ''
            chmod +x $out/lib/python*/site-packages/claude_agent_sdk/_bundled/claude
          '';

          doCheck = false;
        };

        # Docker image built with dockerTools (see nix/docker-image.nix)
        dockerImage = import ./nix/docker-image.nix {
          inherit pkgs version claudeAgentSdk;
        };

        # =====================================================================
        # Voice Agent Application
        # =====================================================================
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

        # =====================================================================
        # Test Infrastructure
        # =====================================================================
        # Why testEnv lists dependencies explicitly (not voiceAgent):
        #   - Including voiceAgent would create import issues since tests
        #     need to import from src/ directly via PYTHONPATH
        #   - We mirror the runtime dependencies here for test isolation
        #
        # Why testSuite copies conftest.py:
        #   - When pytest runs from the nix store, it can't find conftest.py
        #     in the original source tree. Bundling it ensures fixtures
        #     (permission_handler, mock_settings, etc.) are discovered.
        #
        # Why testRunner uses CLI options instead of pyproject.toml:
        #   - pytest runs from nix store, can't read pyproject.toml
        #   - asyncio_mode=auto: Auto-detect async tests without @pytest.mark.asyncio
        #   - confcutdir: Tell pytest where to find conftest.py
        # =====================================================================
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

        testSuite = pkgs.runCommand "voice-agent-test-suite" {} ''
          mkdir -p $out/unit
          cp ${./tests/conftest.py} $out/conftest.py
          cp -r ${./tests/unit}/* $out/unit/
        '';

        testRunner = pkgs.writeShellScriptBin "voice-agent-tests" ''
          export PYTHONPATH="${./src}:$PYTHONPATH"
          exec ${testEnv}/bin/python -m pytest ${testSuite}/unit \
            --confcutdir=${testSuite} \
            -p pytest_asyncio \
            -o asyncio_mode=auto \
            -o asyncio_default_fixture_loop_scope=function \
            -v "$@"
        '';

        # =====================================================================
        # Documentation
        # =====================================================================
        docs = pkgs.stdenv.mkDerivation {
          name = "voice-agent-docs";
          src = ./.;
          buildInputs = [
            pythonPackages.mkdocs
            pythonPackages.mkdocs-material
            pythonPackages.mkdocstrings
            pythonPackages.mkdocstrings-python
            pythonPackages.python-telegram-bot
            pythonPackages.httpx
            pythonPackages.pydantic
            pythonPackages.pydantic-settings
          ];
          buildPhase = ''
            export PYTHONPATH="$PWD/src:$PYTHONPATH"
            mkdocs build -d $out
          '';
          dontInstall = true;
        };

        # =====================================================================
        # Development Shell
        # =====================================================================
        # Why shellHook sets PYTHONPATH:
        #   - Allows `python -m voice_agent` and `pytest tests/` to work
        #     directly without installing the package
        #   - Enables fast iteration: edit src/, run immediately
        # =====================================================================
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
            pythonPackages.mkdocs
            pythonPackages.mkdocs-material
            pythonPackages.mkdocstrings
            pythonPackages.mkdocstrings-python
            pkgs.just
            claudeAgentSdk
          ];

          shellHook = ''
            export PYTHONPATH="$PWD/src:$PYTHONPATH"
          '';
        };
      in
      {
        # =====================================================================
        # Outputs
        # =====================================================================
        # packages.default     - The voice-agent Python application
        # packages.docker-image - Docker image (load with: docker load < result)
        # packages.tests       - Test runner script
        #
        # apps.default         - nix run .#         (runs the bot)
        # apps.tests           - nix run .#tests    (runs unit tests)
        #
        # devShells.default    - nix develop        (dev environment)
        # =====================================================================
        packages = {
          default = voiceAgent;
          voice-agent = voiceAgent;
          docker-image = dockerImage;
          tests = testRunner;
          docs = docs;
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
