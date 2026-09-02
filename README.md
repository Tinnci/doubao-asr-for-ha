# Doubao ASR for Home Assistant

[![CI](https://github.com/Tinnci/doubao-asr-for-ha/actions/workflows/ci.yml/badge.svg)](https://github.com/Tinnci/doubao-asr-for-ha/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
[![Wyoming Protocol](https://img.shields.io/badge/protocol-Wyoming-orange.svg)](https://www.home-assistant.io/integrations/wyoming/)

Use Doubao speech recognition through the Home Assistant Wyoming Protocol.

The service runs as a Home Assistant add-on or a standalone container. It
accepts Wyoming PCM audio and returns one final Wyoming `Transcript`.

> [!IMPORTANT]
> This project is unofficial. It is not affiliated with Doubao, ByteDance,
> Home Assistant, or Nabu Casa.

## Supported use

The Wyoming `Describe` response advertises Chinese (`zh`) recognition. English
documentation does not mean that the upstream service supports English ASR.

| Boundary | Format |
| --- | --- |
| Wyoming input | 16 kHz, mono, signed 16-bit PCM |
| Doubao upload | 16 kHz, mono, 20 ms `speech_opus` frames |
| Home Assistant result | Final Wyoming `Transcript` |

The service does not provide TTS, wake-word detection, or satellite audio
routing.

## Features

- Wyoming ASR server on TCP port `10300`
- Home Assistant add-on and standalone container modes
- Credential storage in `/data/doubao_credentials.json`
- WebSocket sessions with Doubao ASR
- Concurrent capture and provider upload
- A bounded 50-chunk queue for backpressure
- Provider VAD, interim result, and final result parsing
- One token refresh and retry after a `StartTask` authentication failure
- Token removal from raised errors
- Optional local health and metrics endpoint
- Zeroconf disabled by default in standalone container mode

The service can send interim events to an optional callback. Home Assistant
still receives only the final transcript.

## Diagnostics and privacy

Set `metrics_uri` to expose `GET /health` and `GET /metrics` on a local
address.

The metrics include:

- request phase and request ID,
- audio byte and frame counts,
- provider VAD and result-event counts,
- first interim and final result latency,
- transcript character count,
- endpoint state and failure phase,
- the static audio and concurrency contracts.

INFO logs do not contain transcript text. They record the transcript character
count and request metadata. Keep DEBUG logs disabled unless you need them for a
short investigation.

The compact `endpoint` object uses these states:

- `silence`
- `speech_start`
- `partial`
- `endpoint_detected`
- `complete`
- `timeout`
- `provider_error`
- `error`

Use `speech_started` when a caller needs one stable boolean value.

## Home Assistant OS

Home Assistant OS supports add-ons.

1. Add this repository as a custom add-on repository.
2. Install **Doubao ASR** from the Add-on Store.
3. Start the add-on.
4. Add it through the Wyoming Protocol integration.

Default options:

```yaml
debug_logging: false
response_timeout_s: 15
zeroconf_enabled: false
zeroconf_timeout_s: 5
metrics_uri: ""
```

Use `tcp://127.0.0.1:10301` for a local metrics listener.

## Home Assistant Container

Home Assistant Container does not support add-ons. Run this service as another
container. Then add its Wyoming address to Home Assistant.

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

Add the Docker host and port `10300` in the Wyoming Protocol integration. The
correct host depends on your container network.

When `/data/options.json` does not exist, the container uses the add-on
defaults. Create the file to override them:

```json
{
  "debug_logging": false,
  "response_timeout_s": 15,
  "zeroconf_enabled": false,
  "zeroconf_timeout_s": 5,
  "metrics_uri": "tcp://127.0.0.1:10301"
}
```

## Verification

Check the Wyoming server:

```bash
printf '{ "type": "describe" }\n' | nc -w 1 127.0.0.1 10300
```

This command only checks the server connection. It does not test recognition.

For an ASR test:

1. Prepare clear Chinese audio that matches the PCM input contract.
2. Send the audio through a Wyoming client.
3. Confirm that the service returns a final transcript.
4. Check `/metrics` for a complete endpoint state.

## Runtime boundary

ASR quality depends on the satellite capture chain. This project does not own
microphone gain, wake-word sensitivity, echo cancellation, audio routing,
speaker volume, or local fallback prompts.

One Wyoming connection owns one ASR stream. A multi-room system must create
separate connections or service instances above this adapter.

Keep zeroconf disabled in container deployments unless the network supports it.

## Development

Use `uv` for the Python environment.

```bash
uv sync --dev
uv run pytest
uvx ruff check .
uvx ruff format --check .
git diff --check
```

Run the service locally:

```bash
uv run wyoming-doubao-asr \
  --uri tcp://127.0.0.1:10300 \
  --credentials-file /tmp/doubao_credentials.json \
  --log-level DEBUG
```

Tests cover protocol packets, frame splitting, stream sequencing, endpoint
metrics, token refresh, token redaction, and runtime option mapping.

## Security and legal notice

- Protect `/data/doubao_credentials.json` and its backups.
- Do not publish credentials, raw audio, or transcripts in an issue.
- Follow the provider terms, privacy rules, and data protection laws.
- Read [DISCLAIMER.md](DISCLAIMER.md) before production use.
- See [NOTICE.md](NOTICE.md) for upstream notices.

## Documentation style

This README applies practical rules from ASD-STE100 Simplified Technical
English, Issue 9. It uses active voice, short sentences, and consistent terms.

This use is not an ASD-STE100 compliance certification. Project-specific terms
remain necessary.

Reference: ASD STEMG. [ASD-STE100 Simplified Technical English](https://www.asd-ste100.org/), Issue 9, 2025.

## License

This source is available for non-commercial use under the
[PolyForm Noncommercial License 1.0.0](LICENSE).

Commercial use requires a separate license. This license is not an OSI
open-source license.
