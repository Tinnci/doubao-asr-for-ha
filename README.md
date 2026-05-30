# Doubao ASR for Home Assistant

Home Assistant Wyoming speech-to-text add-on backed by Doubao ASR.

This project assumes the Doubao ASR interface is publicly available for this
use case and should be used in accordance with the service terms.

This is an unofficial project. It is not affiliated with, endorsed by, or
maintained by Doubao, ByteDance, Home Assistant, or Nabu Casa.

## What is included

- A Wyoming ASR server on port `10300`
- Home Assistant add-on metadata (`config.yaml`, `build.yaml`, `Dockerfile`)
- Doubao device registration and token persistence in `/data/doubao_credentials.json`
- WebSocket/protobuf ASR session flow based on `EvanDbg/doubao-ime-win`
- PCM conversion through Wyoming and Opus encoding before sending to Doubao

## Upstream API source

The Doubao ASR API/protocol definitions in this repository are derived from the
upstream open source project `EvanDbg/doubao-ime-win`, especially:

- `src/asr/client.rs`: https://github.com/EvanDbg/doubao-ime-win/blob/main/src/asr/client.rs
- `src/asr/constants.rs`: https://github.com/EvanDbg/doubao-ime-win/blob/main/src/asr/constants.rs

The upstream project README states that its implementation is based on analysis
of the Doubao input method client protocol and is not an official API. This
repository preserves that limitation. See `NOTICE.md` and `DISCLAIMER.md`.

## Local development

Use `uv`:

```bash
uv sync --dev
uv run pytest
uv run wyoming-doubao-asr \
  --uri tcp://127.0.0.1:10300 \
  --credentials-file /tmp/doubao_credentials.json \
  --log-level DEBUG
```

Smoke-test the Wyoming service:

```bash
printf '{ "type": "describe" }\n' | nc -w 1 127.0.0.1 10300
```

Current local verification:

- `uv run pytest`: 11 passed.
- Wyoming smoke test: passed.
- Docker image build: not verified locally because Docker daemon was unavailable.

## Home Assistant

Add this repository as a local/custom add-on repository, install `Doubao ASR`,
then add or discover it through the Wyoming Protocol integration. The add-on
listens on `10300/tcp`.

## Roadmap

- Validate the add-on image and Wyoming discovery in real Home Assistant OS and
  Supervised environments.
- Run end-to-end live ASR tests against the upstream service.
- Harden websocket timeout, retry, token refresh, and error reporting.
- Add CI for tests and release checks.

Non-goals: bypassing access controls, claiming official Doubao API support, or
adding non-ASR features such as TTS and wake-word detection.

## Notes

The current implementation is an MVP. It validates the local Wyoming protocol,
protobuf framing, and client sequencing with tests, but real Doubao ASR behavior
still depends on the availability and terms of the upstream service.

## License

MIT License. See `LICENSE`.
