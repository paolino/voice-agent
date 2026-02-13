# Changelog

## [0.4.0](https://github.com/paolino/voice-agent/compare/v0.3.0...v0.4.0) (2026-02-13)


### Features

* add voice skill invocation and cleanup justfile ([141cb1c](https://github.com/paolino/voice-agent/commit/141cb1c8699cfbc75f552a4bf3af71f00da13295))
* forward unknown /commands to Claude for skill invocation ([237e8e0](https://github.com/paolino/voice-agent/commit/237e8e0d9ca5b937b3a4bfb96d3374c8712be91a))
* support image attachments in Telegram messages ([ac0ab99](https://github.com/paolino/voice-agent/commit/ac0ab99891de2f66fab207220e7f0a3d2a704e46)), closes [#40](https://github.com/paolino/voice-agent/issues/40)


### Bug Fixes

* deploy recipes to use local docker compose ([e9d80f6](https://github.com/paolino/voice-agent/commit/e9d80f6bcaea197d9907ccf6c50a43dbecef69fb))
* prevent out-of-order responses after stop button ([4f142a3](https://github.com/paolino/voice-agent/commit/4f142a3b9f286dbd49447f9cff69cfd72f2a2f98)), closes [#70](https://github.com/paolino/voice-agent/issues/70)
* use absolute python path in docker entrypoint ([34455f3](https://github.com/paolino/voice-agent/commit/34455f3b4d35296c1d72b2ad96634747b1a5ad97))

## [0.3.0](https://github.com/paolino/voice-agent/compare/v0.2.0...v0.3.0) (2026-02-03)


### Features

* add deploy-local command for docker compose ([089a5db](https://github.com/paolino/voice-agent/commit/089a5db3b5acd7e58ec41d6a64a5d26dfefe681f))
* add image-tag flake output for deployment ([2c63b60](https://github.com/paolino/voice-agent/commit/2c63b602bf03862c8b4aef2ea2ee2581a7f197d3))
* add test-local commands for feature testing ([f1a28be](https://github.com/paolino/voice-agent/commit/f1a28be3fa8f75c5eb4502d8f9d0e375d3b65bbf))
* separate local sessions with optional clean flag ([281a3e6](https://github.com/paolino/voice-agent/commit/281a3e67942d80057fe9c58d3cbe853ba6e6060e))
* tag docker images with commit hash ([8666eb2](https://github.com/paolino/voice-agent/commit/8666eb2ba8ecb552495ce2561185e1ee3e3d17b4))
* use Cachix for docker image distribution ([bf08776](https://github.com/paolino/voice-agent/commit/bf08776e5510e8a4db2b85500f86f8207b9a52ea))
* use shared session storage for local testing ([bcace67](https://github.com/paolino/voice-agent/commit/bcace671818c8a1e19d1679e0fc57474886eebf7))


### Bug Fixes

* add workflow_dispatch to release workflow ([242cefa](https://github.com/paolino/voice-agent/commit/242cefaf82fa04cd67130a169a7f7b6230f57989))
* create data directory before starting ([1937f58](https://github.com/paolino/voice-agent/commit/1937f58fd14a1d5faf7066f8d03612da9cd4ccbe))
* deploy command escaping and missing env var ([9b6c439](https://github.com/paolino/voice-agent/commit/9b6c4392e78cef14d37142611b5aba866103a3d8))
* use ~/.config/voice-agent/data for sessions ([718aba5](https://github.com/paolino/voice-agent/commit/718aba55468e99b9c11c626e29e0fb01fc1b6a82))
* use consistent python version in docker image ([eebd27e](https://github.com/paolino/voice-agent/commit/eebd27e78fae9797386c599ed99478cb571fb449))


### Documentation

* add Docker deployment guide with Claude CLI mounting ([5e2b997](https://github.com/paolino/voice-agent/commit/5e2b9973650e20c825ed76411ca3579550f4d2d4))
* update NixOS example with privileged mode and NIX_CONFIG ([3a7fba1](https://github.com/paolino/voice-agent/commit/3a7fba1bd54a6417e8e1556ba1b93e6ad7f5bbb8))

## [0.2.0](https://github.com/paolino/voice-agent/compare/v0.1.0...v0.2.0) (2026-02-02)


### Features

* add /restart command to clear session and sticky approvals ([737b532](https://github.com/paolino/voice-agent/commit/737b5327623baaf2d0f26a916a3f94cf5624bed6)), closes [#35](https://github.com/paolino/voice-agent/issues/35)
* manage permission auto-approvals via Telegram ([22a1108](https://github.com/paolino/voice-agent/commit/22a11089db13b1ec11c0d4ecf6246dcf5e06f27f)), closes [#32](https://github.com/paolino/voice-agent/issues/32)


### Bug Fixes

* load user config (CLAUDE.md, MCP servers) on session start ([5bb1fdf](https://github.com/paolino/voice-agent/commit/5bb1fdf56bc6f5be5dd62e338258360d34872a08)), closes [#37](https://github.com/paolino/voice-agent/issues/37)
* require exact match for restart and add confirmation dialog ([f8f6462](https://github.com/paolino/voice-agent/commit/f8f6462383c53c53b7e712e1e6bfe82226b7d036))

## 0.1.0 (2026-02-01)


### Features

* add Docker build/run commands to justfile ([f2e2a19](https://github.com/paolino/voice-agent/commit/f2e2a19fba91b08a51c7dfc2e28947dd1525da7c))
* add docs build to flake and GitHub Pages deployment ([1950a5d](https://github.com/paolino/voice-agent/commit/1950a5dd82dcdf1d75f8321aa5a4472cda36ea4d)), closes [#8](https://github.com/paolino/voice-agent/issues/8)
* add escape/cancel functionality to stop running tasks ([be17990](https://github.com/paolino/voice-agent/commit/be1799063a97af24a2f3f042ec0ab01b6ee36eb0)), closes [#24](https://github.com/paolino/voice-agent/issues/24)
* add inline keyboard buttons for permission approval ([1a7e539](https://github.com/paolino/voice-agent/commit/1a7e539e6fb21543cfaa6df0e313028988a4bef4)), closes [#17](https://github.com/paolino/voice-agent/issues/17)
* add nix-based Docker image build ([402c16f](https://github.com/paolino/voice-agent/commit/402c16f1b8ccc3bb0038fab1bfa850b4cb16f841))
* add session persistence for M2 ([6babcf0](https://github.com/paolino/voice-agent/commit/6babcf0b14175940946f94bab79d66890ef2db97))
* add sticky session approvals for similar tool calls ([aea9c8f](https://github.com/paolino/voice-agent/commit/aea9c8ff5b35a09bc65723d671f4876e0100528e)), closes [#25](https://github.com/paolino/voice-agent/issues/25)
* add tests as nix flake output ([554507b](https://github.com/paolino/voice-agent/commit/554507bdf23d03221af49aaa927740d4117c80e9))
* convert Markdown to Telegram-compatible formatting ([bea8e25](https://github.com/paolino/voice-agent/commit/bea8e2550b31a748eb6f29e3bce2297636b166a8)), closes [#16](https://github.com/paolino/voice-agent/issues/16)
* improve permission approval/rejection feedback ([9907c99](https://github.com/paolino/voice-agent/commit/9907c9963ad9083922a0764088d880c45daf6a5c)), closes [#21](https://github.com/paolino/voice-agent/issues/21)
* initial implementation of voice-agent ([97fd764](https://github.com/paolino/voice-agent/commit/97fd7649bc4e0fc75ee8ef2629ca397399142d5d))
* support text messages from Telegram keyboard ([bcc0156](https://github.com/paolino/voice-agent/commit/bcc015642c8b9c9e380c08e523eaf8d83d95bdd7)), closes [#2](https://github.com/paolino/voice-agent/issues/2)
* switch to Claude Agent SDK for persistent sessions ([ae0ebfa](https://github.com/paolino/voice-agent/commit/ae0ebfa3e236aec5ab965be98c36ac76be833b49))
* use italic formatting for transcription messages ([08baff0](https://github.com/paolino/voice-agent/commit/08baff05ea454aa229302bac64dab426f629b1d7)), closes [#19](https://github.com/paolino/voice-agent/issues/19)
* use mermaid diagrams in documentation ([c19e1cf](https://github.com/paolino/voice-agent/commit/c19e1cfee9360c7a53f9e2f5d159e53409dacde2))
* wire permission handler to Claude SDK canUseTool callback ([62d6c04](https://github.com/paolino/voice-agent/commit/62d6c04977cceca63eea550d2acbb312c6381687)), closes [#3](https://github.com/paolino/voice-agent/issues/3)


### Bug Fixes

* bundle conftest.py with test suite and fix asyncio mode ([9f9ec89](https://github.com/paolino/voice-agent/commit/9f9ec89a4c00f44e8a8be3de5eb3e8496d0cabf7))
* resolve permission flow blocking and add bot management commands ([5c8dc91](https://github.com/paolino/voice-agent/commit/5c8dc9122e7f88e4c85cd76e39148aff62bb9e50))
* resolve race condition when cancelling tasks via Stop button ([cbe193f](https://github.com/paolino/voice-agent/commit/cbe193f57caabfa0901cdb9fa83c2cd8cdb10fd6)), closes [#28](https://github.com/paolino/voice-agent/issues/28)
* serialize prompt handling per chat to prevent message interleaving ([5b8c274](https://github.com/paolino/voice-agent/commit/5b8c27474ece92fd99e7d0e75cf24e34ebfd0e78))
* use --continue flag to resume Claude sessions ([70ab0f4](https://github.com/paolino/voice-agent/commit/70ab0f45df620c3ac4d5c696e428df1bda181ce6))
* use 'audio' field for whisper-server API ([cd908de](https://github.com/paolino/voice-agent/commit/cd908deb9a592b40d58cd4c6f0c9e34618001523))
* use system Claude CLI instead of bundled SDK version ([31b9c39](https://github.com/paolino/voice-agent/commit/31b9c39b5db2a85dcb1b46ba174f6434af415649))


### Documentation

* add README with link to documentation ([7b18414](https://github.com/paolino/voice-agent/commit/7b1841413dfca959d151c3401dac504a07aa84a8))
* document flake decisions ([fc6ed89](https://github.com/paolino/voice-agent/commit/fc6ed893612adb3e9945c5263f45b65dd42bb430))
* update architecture docs with session persistence ([da09b52](https://github.com/paolino/voice-agent/commit/da09b52bcb363c75fd3816bb4b3558f671bceb1a))
