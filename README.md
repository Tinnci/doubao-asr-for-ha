# Doubao ASR for Home Assistant

[English + 简体中文](README.md)

[![License: PolyForm Noncommercial 1.0.0](https://img.shields.io/badge/license-PolyForm%20Noncommercial%201.0.0-blue.svg)](LICENSE)
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
- Parses VAD, interim, and final ASR result events; callers can observe them
  through an optional client callback while Home Assistant still receives a
  final Wyoming `Transcript`.
- Streams Wyoming audio chunks to Doubao concurrently when the handler is backed
  by the async stream client path, so interim upstream events can update
  diagnostics before capture ends.
- Applies backpressure with a bounded 50-chunk streaming queue instead of
  accumulating unbounded stale audio when the provider or network is slow.
- Logs ASR phase and request id for troubleshooting.
- Keeps per-request diagnostic metrics such as audio bytes, sent frame count,
  upstream result-event counts, provider VAD start/finish flags, first interim
  latency, final-result latency, transcript length, and failure phase.
- Can expose the latest in-process metrics through an optional local HTTP
  endpoint with `--metrics-uri tcp://127.0.0.1:10301`; `/metrics` also exposes
  the static audio contract and stream concurrency model so satellite
  diagnostics do not need to infer them from source code.
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
- 协议层会解析 VAD、中间结果和最终结果；客户端可通过可选回调观察这些事件，但 Home Assistant 仍只接收最终 Wyoming `Transcript`。
- 当 handler 使用 async stream client 路径时，会边接收 Wyoming 音频边推送到豆包，所以上游中间事件可以在录音结束前更新诊断指标。
- 流式队列上限为 50 个 chunk；provider 或网络变慢时通过背压减速，而不是无限累积过期音频。
- 错误日志包含 ASR 阶段和 request id，便于排障。
- 保留每次请求的诊断指标，包括音频字节数、发送帧数、上游结果事件数、
  provider VAD 开始/结束标记、首个中间结果延迟、最终结果延迟、转写长度和失败阶段。
- 可通过 `--metrics-uri tcp://127.0.0.1:10301` 暴露本地 `/health` 和
  `/metrics`，供锁屏状态代理或 harness 抓取最近一次请求指标；`/metrics`
  同时暴露静态音频合约和流并发模型，避免卫星诊断从源码里推断。
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
metrics_uri: ""
```

Standalone Docker uses the same values when `/data/options.json` is absent. To
override them, create:

```json
{
  "debug_logging": false,
  "response_timeout_s": 15,
  "zeroconf_enabled": false,
  "zeroconf_timeout_s": 5,
  "metrics_uri": "tcp://127.0.0.1:10301"
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
- provider VAD/interim/final ASR metrics,
- WebSocket ASR session sequence,
- token refresh on auth failure,
- token redaction in errors,
- add-on run script option mapping,
- Docker/standalone defaults.

## Operational notes / 运维说明

- ASR quality depends on the upstream satellite capture chain. Wakeword
  sensitivity, microphone gain, echo cancellation, and capture/playback routing
  are not controlled by this project.
- The Wyoming handler now prefers the concurrent stream client path when
  available. Home Assistant still receives only the final Wyoming `Transcript`;
  live partial text should be treated as diagnostics/status, not user-visible
  final ASR output.
- Use `--metrics-uri tcp://127.0.0.1:10301` to expose `/health` and `/metrics`
  for local scraping by a display agent or harness.
- `/metrics` reports the expected Wyoming input as 16 kHz mono S16_LE and the
  Doubao upstream payload as 16 kHz mono `speech_opus` frames. Multiple rooms
  should be modeled above this service as separate Wyoming connections or
  separate service instances; this adapter does not own room-level capture
  orchestration.
- The service expects PCM from Wyoming and sends Opus to Doubao. It does not
  synthesize TTS and does not implement wake word detection.
- For Home Assistant Container deployments, keep zeroconf disabled unless the
  network stack is known to support it reliably.

## Roadmap / 后续方向

- Add real-audio end-to-end ASR tests that cover the full HA voice pipeline and
  exercise the stream path under live capture timing.
- Improve deployment docs for HA OS add-on repository setup and Container
  compose variants.

Non-goals:

- claiming official Doubao API support,
- adding TTS,
- adding wake-word detection,
- managing satellite speaker volume or local OPUS fallback prompts.

## Legal / 合规

- License: PolyForm Noncommercial License 1.0.0. Commercial use is not
  permitted without a separate license. See `LICENSE`.
- Credits and upstream MIT notices: see `NOTICE.md`.
- Unofficial status, user responsibilities, third-party voice service notice,
  and warranty disclaimer: see `DISCLAIMER.md`.

## License

Source-available for non-commercial use under the PolyForm Noncommercial
License 1.0.0. See `LICENSE`.

This is not an OSI open-source license because commercial use is restricted.
