# Doubao ASR for Home Assistant

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![CI](https://github.com/Tinnci/doubao-asr-for-ha/actions/workflows/ci.yml/badge.svg)](https://github.com/Tinnci/doubao-asr-for-ha/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
[![Home Assistant Add-on](https://img.shields.io/badge/Home%20Assistant-Add--on-41BDF5.svg)](config.yaml)
[![Wyoming Protocol](https://img.shields.io/badge/protocol-Wyoming-orange.svg)](https://www.home-assistant.io/integrations/wyoming/)

非官方 Home Assistant Wyoming 语音识别插件，基于豆包 ASR。

Unofficial Home Assistant Wyoming speech-to-text add-on backed by Doubao ASR.

本项目要求使用者自行遵守相关服务条款、法律法规、隐私和数据保护要求。本项目不隶属于豆包、字节跳动、Home Assistant 或 Nabu Casa，也未获得其认可、赞助或维护。

Users are responsible for complying with applicable service terms, laws, privacy rules, and data protection requirements. This project is not affiliated with, endorsed by, sponsored by, or maintained by Doubao, ByteDance, Home Assistant, or Nabu Casa.

## 功能 / Features

- 在 `10300/tcp` 提供 Wyoming ASR 服务。
- 提供 Home Assistant add-on 元数据：`config.yaml`、`build.yaml`、`Dockerfile`。
- 自动注册/缓存设备凭据和 token 到 `/data/doubao_credentials.json`。
- 实现基于 WebSocket 的 ASR 会话流程。
- 将 Wyoming PCM 音频转换为 16 kHz mono 20 ms Opus 帧后发送。
- 失败日志包含 ASR 阶段和 request id，便于排障。
- `StartTask` 认证/token 失败时自动刷新 token 并重试一次。

- Exposes a Wyoming ASR server on `10300/tcp`.
- Includes Home Assistant add-on metadata: `config.yaml`, `build.yaml`, `Dockerfile`.
- Registers and persists device credentials in `/data/doubao_credentials.json`.
- Implements a WebSocket-based ASR session flow.
- Converts Wyoming PCM audio into 16 kHz mono 20 ms Opus frames before sending.
- Logs the ASR failure phase and request id for troubleshooting.
- Refreshes the token and retries once when `StartTask` fails with an auth/token error.

## 使用 / Home Assistant

将本仓库作为 Home Assistant 本地/自定义 add-on 仓库添加，安装 `Doubao ASR`，然后通过 Wyoming Protocol 集成发现或手动添加。插件监听 `10300/tcp`。

Add this repository as a local/custom Home Assistant add-on repository, install `Doubao ASR`, then discover or add it through the Wyoming Protocol integration. The add-on listens on `10300/tcp`.

## HA OS vs Docker

Home Assistant OS 支持 add-ons：推荐直接添加本仓库并通过 Add-on Store 安装。

Home Assistant Container/Docker 不支持 add-ons：需要把本项目作为独立容器运行，再在 Home Assistant 里手动添加 Wyoming integration，地址填容器服务名或宿主机 IP，端口 `10300`。

Home Assistant OS supports add-ons: add this repository and install it from the Add-on Store.

Home Assistant Container/Docker does not support add-ons: run this project as a separate container, then manually add the Wyoming integration in Home Assistant. Use the container service name or host IP with port `10300`.

Minimal Docker Compose example:

```yaml
services:
  doubao-asr:
    image: ghcr.io/tinnci/doubao-asr-for-ha:latest
    ports:
      - "10300:10300"
    volumes:
      - ./doubao-asr-data:/data
```

The container uses default options when `/data/options.json` is missing. Standalone
Docker mode disables zeroconf by default so the Wyoming TCP server starts reliably;
add the Wyoming integration manually in Home Assistant with host `127.0.0.1` or the
Docker host IP and port `10300`. To override options, create:

```json
{"debug_logging": false, "response_timeout_s": 15, "zeroconf_enabled": false}
```

## 开发 / Development

使用 `uv`：

Use `uv`:

```bash
uv sync --dev
uv run pytest
uv run wyoming-doubao-asr \
  --uri tcp://127.0.0.1:10300 \
  --credentials-file /tmp/doubao_credentials.json \
  --log-level DEBUG
```

Wyoming 烟测 / Wyoming smoke test:

```bash
printf '{ "type": "describe" }\n' | nc -w 1 127.0.0.1 10300
```

真实 ASR 验证 / Real ASR check:

1. 准备一段清晰中文的 16 kHz mono signed 16-bit PCM 音频。
2. 直接发送给 Wyoming ASR 服务。
3. 确认返回最终转写文本。不要只测 `describe`。

1. Prepare 16 kHz mono signed 16-bit PCM with clear Chinese speech.
2. Feed it directly to the Wyoming ASR service.
3. Confirm a final transcript is returned. Do not treat `describe` alone as a pass.

## 后续方向 / Roadmap

- 加固 WebSocket 超时、重试、token 刷新和错误日志。
- 增加真实音频端到端识别测试，覆盖完整 HA 语音管线。
- 增加发布检查和版本化 release。

- Harden websocket timeout, retry, token refresh, and error logging.
- Add real-audio end-to-end ASR tests that cover the full HA voice pipeline.
- Add release checks and versioned releases.

非目标：宣称官方豆包 API 支持，或添加 TTS/唤醒词等非 ASR 功能。

Non-goals: claiming official Doubao API support, or adding non-ASR features such as TTS and wake-word detection.

## 合规 / Legal

- 许可证 / License: MIT License. See `LICENSE`.
- 致谢 / Credits: see `NOTICE.md`.
- 非官方状态、用户责任、第三方语音服务提示和免责声明 / Unofficial status, user responsibilities, third-party voice service notice, and warranty disclaimer: see `DISCLAIMER.md`.

## License

MIT License. See `LICENSE`.
