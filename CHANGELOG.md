# Changelog

## 0.1.0 (2026-02-01)


### Features

* add Docker build/run commands to justfile ([db487f3](https://github.com/paolino/voice-agent/commit/db487f3e8621d968833ea7a8da09bbce1df5da7c))
* add nix-based Docker image build ([f6891b4](https://github.com/paolino/voice-agent/commit/f6891b4ad840f38079babe23b50817d95c9cff10))
* add session persistence for M2 ([4ff5755](https://github.com/paolino/voice-agent/commit/4ff575581772fe2bc4587436f17a134dcab3ba4b))
* add tests as nix flake output ([32b1d4c](https://github.com/paolino/voice-agent/commit/32b1d4c64fdd83d6f991f2ec32473992b5af454c))
* initial implementation of voice-agent ([97fd764](https://github.com/paolino/voice-agent/commit/97fd7649bc4e0fc75ee8ef2629ca397399142d5d))
* switch to Claude Agent SDK for persistent sessions ([4978ce1](https://github.com/paolino/voice-agent/commit/4978ce134a6b5bd4ede074e53f486acb5024e9c8))


### Bug Fixes

* bundle conftest.py with test suite and fix asyncio mode ([1bc7eb0](https://github.com/paolino/voice-agent/commit/1bc7eb06c9305d68fcd41c0952ac0d8986f6516b))
* use --continue flag to resume Claude sessions ([523984b](https://github.com/paolino/voice-agent/commit/523984bcb5308b096571a1f50cbcccccab6c9666))
* use 'audio' field for whisper-server API ([cd908de](https://github.com/paolino/voice-agent/commit/cd908deb9a592b40d58cd4c6f0c9e34618001523))
* use system Claude CLI instead of bundled SDK version ([ecc9a76](https://github.com/paolino/voice-agent/commit/ecc9a7602cfb0016887574dbde3e1c7cd5cb4a0b))


### Documentation

* document flake decisions ([9d0f3fc](https://github.com/paolino/voice-agent/commit/9d0f3fc35312d11f4bafdd5f9328e9d7b4518651))
* update architecture docs with session persistence ([f521ade](https://github.com/paolino/voice-agent/commit/f521adeb984fb600fde81d8ec0f075f4aef10cf3))
