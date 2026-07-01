"""Small HTTP metrics adapter for Doubao ASR diagnostics."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Protocol
from urllib.parse import urlparse


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
            body = {"ok": True, "last_metrics": client.last_metrics}
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
