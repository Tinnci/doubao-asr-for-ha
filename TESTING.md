# Testing

This repository currently validates the local Wyoming service boundary and the
Doubao protocol implementation without sending live audio to the upstream
service.

## Verified locally

Run:

```bash
uv run pytest
```

Current coverage:

- PCM chunk framing into 20 ms, 16 kHz, mono, signed 16-bit frames.
- Doubao protobuf request encoding for `StartTask`, `StartSession`, and
  `TaskRequest`.
- Doubao response parsing for final results and error messages.
- Wyoming `describe`, `transcribe`, `audio-chunk`, and `audio-stop` handling.
- Client session ordering with a fake websocket transport.

## Wyoming smoke test

Start the local server:

```bash
uv run wyoming-doubao-asr \
  --uri tcp://127.0.0.1:10301 \
  --credentials-file /tmp/doubao-asr-for-ha-smoke-creds.json \
  --log-level DEBUG
```

In another terminal:

```bash
uv run python - <<'PY'
import asyncio
from wyoming.event import async_read_event, async_write_event
from wyoming.info import Describe

async def main():
    reader, writer = await asyncio.open_connection("127.0.0.1", 10301)
    await async_write_event(Describe().event(), writer)
    event = await async_read_event(reader)
    print(event.type)
    print(event.data["asr"][0]["name"])
    writer.close()
    await writer.wait_closed()

asyncio.run(main())
PY
```

Expected output:

```text
info
doubao-asr
```

## Not yet verified

The following require a real runtime environment and should be treated as next
validation targets:

- Docker image build on a machine with a running Docker daemon.
- Home Assistant add-on installation and Wyoming discovery.
- Live Doubao device registration and token retrieval.
- End-to-end live audio transcription against the upstream ASR service.
- Behavior under upstream API errors, rate limits, regional restrictions, and
  protocol changes.

## Current local result

As of the latest repository update:

- `uv run pytest`: 11 passed.
- Wyoming smoke test: passed.
- Docker image build: not run locally because Docker daemon was unavailable.
