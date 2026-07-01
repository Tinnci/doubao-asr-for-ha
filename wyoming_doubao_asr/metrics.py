"""Small HTTP metrics adapter for Doubao ASR diagnostics."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Protocol
from urllib.parse import urlparse

from .constants import CHANNELS, FRAME_DURATION_MS, SAMPLE_RATE, SAMPLE_WIDTH


class MetricsClient(Protocol):
    @property
    def last_metrics(self) -> dict[str, Any]:
        """Return the most recent ASR request metrics."""


async def start_metrics_server(
    uri: str, client: MetricsClient
) -> asyncio.AbstractServer:
    """Start a tiny JSON HTTP server for health and metrics."""
    parsed = urlparse(uri)
    if parsed.scheme != "tcp" or not parsed.hostname or parsed.port is None:
        raise ValueError("--metrics-uri must look like tcp://127.0.0.1:10301")
    return await asyncio.start_server(
        lambda reader, writer: handle_metrics_request(reader, writer, client),
        parsed.hostname,
        parsed.port,
    )


async def handle_metrics_request(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    client: MetricsClient,
) -> None:
    """Handle one minimal HTTP metrics request."""
    code = 200
    body: dict[str, Any] = {"ok": True}
    try:
        request_line = (
            (await asyncio.wait_for(reader.readline(), 2))
            .decode(errors="replace")
            .strip()
        )
        method, path, _ = request_line.split(" ", 2)
        while line := await asyncio.wait_for(reader.readline(), 2):
            if line in {b"\r\n", b"\n"}:
                break

        if method != "GET":
            code, body = 405, {"ok": False, "error": "method not allowed"}
        elif path == "/health":
            body = {"ok": True, "service": "doubao-asr"}
        elif path == "/metrics":
            body = {
                "ok": True,
                "audio_contract": audio_contract(),
                "streaming": streaming_capabilities(),
                "last_metrics": client.last_metrics,
            }
        else:
            code, body = 404, {"ok": False, "error": "not found"}
    except (ValueError, TimeoutError):
        code, body = 400, {"ok": False, "error": "bad request"}

    payload = json.dumps(body, ensure_ascii=False).encode()
    reason = "OK" if code == 200 else "Error"
    writer.write(
        (
            f"HTTP/1.1 {code} {reason}\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(payload)}\r\n"
            "Connection: close\r\n\r\n"
        ).encode()
        + payload
    )
    await writer.drain()
    writer.close()
    await writer.wait_closed()


def audio_contract() -> dict[str, Any]:
    """Return the ASR audio format contract exposed for diagnostics."""
    return {
        "wyoming_input": {
            "sample_rate_hz": SAMPLE_RATE,
            "channels": CHANNELS,
            "sample_width_bytes": SAMPLE_WIDTH,
            "format": "S16_LE",
        },
        "upstream_payload": {
            "sample_rate_hz": SAMPLE_RATE,
            "channels": CHANNELS,
            "codec": "speech_opus",
            "frame_duration_ms": FRAME_DURATION_MS,
        },
        "conversion_owner": "wyoming_doubao_asr.handler.AudioChunkConverter",
    }


def streaming_capabilities() -> dict[str, Any]:
    """Return the ASR stream concurrency model for diagnostics."""
    return {
        "handler_scope": "one_stream_per_wyoming_connection",
        "continuous_capture_owner": "wyoming-satellite",
        "parallel_room_manager": False,
        "partial_results_are_diagnostics": True,
    }
