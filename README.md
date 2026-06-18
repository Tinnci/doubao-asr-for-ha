# Doubao ASR for Home Assistant

[English + 简体中文](README.md)

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![CI](https://github.com/Tinnci/doubao-asr-for-ha/actions/workflows/ci.yml/badge.svg)](https://github.com/Tinnci/doubao-asr-for-ha/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
[![Home Assistant Add-on](https://img.shields.io/badge/Home%20Assistant-Add--on-41BDF5.svg)](config.yaml)
[![Wyoming Protocol](https://img.shields.io/badge/protocol-Wyoming-orange.svg)](https://www.home-assistant.io/integrations/wyoming/)

非官方 Home Assistant Wyoming 语音识别服务，基于豆包 ASR。

Unofficial Home Assistant Wyoming speech-to-text service backed by Doubao ASR.

本项目要求使用者自行遵守相关服务条款、法律法规、隐私和数据保护要求。本项目不隶属于豆包、字节跳动、Home Assistant 或 Nabu Casa，也未获得其认可、赞助或维护。

Users are responsible for complying with applicable service terms, laws, privacy
rules, and data protection requirements. This project is not affiliated with,
endorsed by, sponsored by, or maintained by Doubao, ByteDance, Home Assistant,
or Nabu Casa.

## Current capabilities / 当前能力

- Exposes a Wyoming ASR server on `10300/tcp`.
- Works as a Home Assistant add-on or as a standalone Docker container.
- Registers and persists device credentials in `/data/doubao_credentials.json`.
- Uses a WebSocket-based Doubao ASR session.
- Converts incoming Wyoming PCM into 16 kHz mono 20 ms Opus frames.
- Logs ASR phase and request id for troubleshooting.
- Redacts tokens from raised errors.
- Refreshes the token and retries once when `StartTask` fails with an
  authentication/token error.
- Disables zeroconf by default in standalone Docker mode so the TCP server starts
  reliably.

中文概述：

- 在 `10300/tcp` 提供 Wyoming ASR 服务。
- 支持 Home Assistant add-on 和独立 Docker 容器两种运行方式。
- 自动注册并缓存设备凭据到 `/data/doubao_credentials.json`。
- 将 Wyoming PCM 音频转换为 16 kHz mono 20 ms Opus 帧后发送给豆包 ASR。
- 错误日志包含 ASR 阶段和 request id，便于排障。
- `StartTask` 认证/token 失败时自动刷新 token 并重试一次。

## Runtime options / 运行选项

Language support note / 多语言说明：

- Repository docs and Home Assistant add-on metadata are maintained in English
  and Simplified Chinese.
- The current upstream ASR capability is advertised as `zh` in Wyoming
  `Describe`. Do not treat the bilingual metadata as English ASR support.
- 文档和 Home Assistant add-on 元数据会同时维护英文和简体中文。
- 当前上游识别能力在 Wyoming `Describe` 中仍声明为 `zh`。双语元数据不代表英文 ASR 已可用。

Home Assistant add-on options:

```yaml
debug_logging: false
response_timeout_s: 15
zeroconf_enabled: false
zeroconf_timeout_s: 5
```

Standalone Docker uses the same values when `/data/options.json` is absent. To
override them, create:

```json
{
  "debug_logging": false,
  "response_timeout_s": 15,
  "zeroconf_enabled": false,
  "zeroconf_timeout_s": 5
}
```

## Home Assistant OS

Home Assistant OS supports add-ons. Add this repository as a local/custom add-on
repository, install `Doubao ASR`, then add it through the Wyoming Protocol
integration.

Home Assistant OS 支持 add-ons。推荐直接把本仓库添加为本地/自定义 add-on 仓库，在 Add-on Store 安装 `Doubao ASR`，然后通过 Wyoming Protocol 集成发现或手动添加。

## Home Assistant Container / Docker

Home Assistant Container does not support add-ons. Run this project as a
standalone container and add a Wyoming integration manually in Home Assistant.

Minimal compose example:

```yaml
services:
  doubao-asr:
    image: ghcr.io/tinnci/doubao-asr-for-ha:latest
    container_name: doubao-asr
    restart: unless-stopped
    ports:
      - "10300:10300"
    volumes:
      - ./doubao-asr-data:/data
```

In Home Assistant, add Wyoming manually with:

- host: the Docker host IP, `127.0.0.1`, or the compose service name depending on
  your network mode,
- port: `10300`.

## Development / 开发

Use `uv`:

```bash
uv sync --dev
uv run pytest
uv run wyoming-doubao-asr \
  --uri tcp://127.0.0.1:10300 \
  --credentials-file /tmp/doubao_credentials.json \
  --log-level DEBUG
```

Wyoming smoke test:

```bash
printf '{ "type": "describe" }\n' | nc -w 1 127.0.0.1 10300
```

Real ASR verification:

1. Prepare clear Chinese 16 kHz mono signed 16-bit PCM audio.
2. Feed it directly to the Wyoming ASR service.
3. Confirm a final transcript is returned.

Do not treat `describe` alone as a pass; it only verifies that the Wyoming server
is reachable.

## Test coverage / 测试覆盖

The current test suite covers:

- Wyoming `Describe`,
- PCM frame splitting,
- Doubao protocol packet construction/parsing,
- WebSocket ASR session sequence,
- token refresh on auth failure,
- token redaction in errors,
- add-on run script option mapping,
- Docker/standalone defaults.

## Operational notes / 运维说明

- ASR quality depends on the upstream satellite capture chain. Wakeword
  sensitivity, microphone gain, echo cancellation, and TTS playback gates are not
  controlled by this project.
- The service expects PCM from Wyoming and sends Opus to Doubao. It does not
  synthesize TTS and does not implement wake word detection.
- For Home Assistant Container deployments, keep zeroconf disabled unless the
  network stack is known to support it reliably.

## Roadmap / 后续方向

- Add real-audio end-to-end ASR tests that cover the full HA voice pipeline.
- Add richer metrics for latency, transcript length, and upstream ASR failure
  phase.
- Improve deployment docs for HA OS add-on repository setup and Container
  compose variants.

Non-goals:

- claiming official Doubao API support,
- adding TTS,
- adding wake-word detection,
- managing satellite speaker volume or local OPUS fallback prompts.

## Legal / 合规

- License: MIT License. See `LICENSE`.
- Credits: see `NOTICE.md`.
- Unofficial status, user responsibilities, third-party voice service notice,
  and warranty disclaimer: see `DISCLAIMER.md`.

## License

MIT License. See `LICENSE`.
