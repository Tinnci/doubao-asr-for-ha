# Doubao ASR for Home Assistant

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![CI](https://github.com/Tinnci/doubao-asr-for-ha/actions/workflows/ci.yml/badge.svg)](https://github.com/Tinnci/doubao-asr-for-ha/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
[![Home Assistant Add-on](https://img.shields.io/badge/Home%20Assistant-Add--on-41BDF5.svg)](config.yaml)
[![Wyoming Protocol](https://img.shields.io/badge/protocol-Wyoming-orange.svg)](https://www.home-assistant.io/integrations/wyoming/)
[![Status: MVP](https://img.shields.io/badge/status-MVP-yellow.svg)](#后续方向--roadmap)

非官方 Home Assistant Wyoming 语音识别插件，基于豆包 ASR。

Unofficial Home Assistant Wyoming speech-to-text add-on backed by Doubao ASR.

本项目假定豆包 ASR 接口在当前使用场景下可公开访问，并要求使用者自行遵守相关服务条款、法律法规、隐私和数据保护要求。本项目不隶属于豆包、字节跳动、Home Assistant 或 Nabu Casa，也未获得其认可、赞助或维护。

This project assumes the Doubao ASR interface is publicly available for this use case. Users are responsible for complying with applicable service terms, laws, privacy rules, and data protection requirements. This project is not affiliated with, endorsed by, sponsored by, or maintained by Doubao, ByteDance, Home Assistant, or Nabu Casa.

## 功能 / Features

- 在 `10300/tcp` 提供 Wyoming ASR 服务。
- 提供 Home Assistant add-on 元数据：`config.yaml`、`build.yaml`、`Dockerfile`。
- 自动注册/缓存豆包设备信息和 token 到 `/data/doubao_credentials.json`。
- 基于 `EvanDbg/doubao-ime-win` 的 WebSocket/protobuf ASR 会话流程。
- 将 Wyoming PCM 音频转换为 16 kHz mono 20 ms Opus 帧后发送。
- 失败日志包含 ASR 阶段和 request id，便于真实 Home Assistant 环境排障。
- `StartTask` 认证/token 失败时自动刷新 token 并重试一次。

- Exposes a Wyoming ASR server on `10300/tcp`.
- Includes Home Assistant add-on metadata: `config.yaml`, `build.yaml`, `Dockerfile`.
- Registers and persists Doubao device credentials in `/data/doubao_credentials.json`.
- Implements the WebSocket/protobuf ASR session flow based on `EvanDbg/doubao-ime-win`.
- Converts Wyoming PCM audio into 16 kHz mono 20 ms Opus frames before sending.
- Logs ASR failure phase and request id for real Home Assistant troubleshooting.
- Refreshes the token and retries once when `StartTask` fails with an auth/token error.

## 上游来源 / Upstream Source

本仓库中的豆包 ASR API/协议定义来源于上游开源项目 `EvanDbg/doubao-ime-win`，尤其是：

The Doubao ASR API/protocol definitions in this repository are derived from the upstream open source project `EvanDbg/doubao-ime-win`, especially:

- `src/asr/client.rs`: https://github.com/EvanDbg/doubao-ime-win/blob/main/src/asr/client.rs
- `src/asr/constants.rs`: https://github.com/EvanDbg/doubao-ime-win/blob/main/src/asr/constants.rs

上游项目说明其实现基于对豆包输入法客户端协议的分析，并非官方 API。本仓库保留这一限制说明。更多见 `NOTICE.md` 和 `DISCLAIMER.md`。

The upstream project states that its implementation is based on analysis of the Doubao input method client protocol and is not an official API. This repository preserves that limitation. See `NOTICE.md` and `DISCLAIMER.md`.

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

The container uses default options when `/data/options.json` is missing. To override them, create:

```json
{"debug_logging": false, "response_timeout_s": 15}
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

当前本地验证 / Current local verification:

- `uv run pytest`: 16 passed.
- Wyoming smoke test: passed.
- Docker image build: passed.
- Container Wyoming smoke test: passed.
- GitHub Actions CI: Python tests and Docker build configured.

## 后续方向 / Roadmap

- 在真实 Home Assistant OS 和 Supervised 环境中验证镜像、安装和 Wyoming 发现。
- 对上游 ASR 服务执行端到端实时语音识别测试。
- 加固 WebSocket 超时、重试、token 刷新和错误日志。
- 增加发布检查和版本化 release。

- Validate image build, installation, and Wyoming discovery in real Home Assistant OS and Supervised environments.
- Run end-to-end live ASR tests against the upstream service.
- Harden websocket timeout, retry, token refresh, and error logging.
- Add release checks and versioned releases.

非目标：绕过访问控制、宣称官方豆包 API 支持、或添加 TTS/唤醒词等非 ASR 功能。

Non-goals: bypassing access controls, claiming official Doubao API support, or adding non-ASR features such as TTS and wake-word detection.

## 合规 / Legal

- 许可证 / License: MIT License. See `LICENSE`.
- 上游协议来源 / Upstream attribution: see `NOTICE.md`.
- 非官方状态、用户责任、第三方语音服务提示和免责声明 / Unofficial status, user responsibilities, third-party voice service notice, and warranty disclaimer: see `DISCLAIMER.md`.

## License

MIT License. See `LICENSE`.
