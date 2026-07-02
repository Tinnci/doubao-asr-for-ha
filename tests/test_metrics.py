"""Tests for the optional ASR metrics adapter."""

import asyncio
import json

from wyoming_doubao_asr.metrics import start_metrics_server


class FakeClient:
    @property
    def last_metrics(self) -> dict[str, object]:
        return {"phase": "complete", "total_latency_ms": 123}


async def _http_get(host: str, port: int, path: str) -> dict[str, object]:
    reader, writer = await asyncio.open_connection(host, port)
    request = (
        f"GET {path} HTTP/1.1\r\nHost: fixture\r\nConnection: close\r\n\r\n"
    ).encode()
    writer.write(request)
    await writer.drain()
    raw = await reader.read()
    writer.close()
    await writer.wait_closed()
    _, body = raw.split(b"\r\n\r\n", 1)
    return json.loads(body.decode())


async def test_metrics_server_returns_last_metrics() -> None:
    server = await start_metrics_server("tcp://127.0.0.1:0", FakeClient())
    try:
        sock = server.sockets[0]
        host, port = sock.getsockname()[:2]

        data = await _http_get(host, port, "/metrics")

        assert data["ok"] is True
        assert data["audio_contract"]["wyoming_input"] == {
            "sample_rate_hz": 16000,
            "channels": 1,
            "sample_width_bytes": 2,
            "format": "S16_LE",
        }
        assert data["audio_contract"]["upstream_payload"]["codec"] == "speech_opus"
        assert data["streaming"]["handler_scope"] == "one_stream_per_wyoming_connection"
        assert data["streaming"]["parallel_room_manager"] is False
        assert (
            data["streaming"]["session_model"] == "one_asr_stream_per_satellite_session"
        )
        assert (
            data["streaming"]["future_multi_room_orchestrator"]["implemented"] is False
        )
        assert (
            data["streaming"]["future_multi_room_orchestrator"]["seam"]
            == "orchestrator_above_independent_wyoming_streams"
        )
        assert data["last_metrics"]["total_latency_ms"] == 123
    finally:
        server.close()
        await server.wait_closed()
