"""Regression coverage for abandoned Wyoming command windows."""

import asyncio
from collections.abc import AsyncIterator

import pytest
from wyoming.asr import Transcribe

from tests.test_handler import PausedStreamingFakeClient, make_handler
from wyoming_doubao_asr.client import DoubaoAsrClient


async def test_disconnect_cancels_stream_waiting_for_first_audio() -> None:
    client = PausedStreamingFakeClient()
    handler, written = make_handler(client)
    await handler.handle_event(Transcribe(language="zh").event())
    await client.started.wait()
    # Inspect the owned task to prove it was awaited, not merely detached.
    task = handler._stream_task  # noqa: SLF001
    await handler.disconnect()
    assert task.cancelled()
    assert handler._stream_task is None  # noqa: SLF001
    assert handler._stream_queue is None  # noqa: SLF001
    assert written == []


async def test_cancelled_startup_is_terminal_telemetry() -> None:
    started = asyncio.Event()

    async def credentials() -> None:
        started.set()
        await asyncio.Event().wait()

    async def audio() -> AsyncIterator[bytes]:
        yield b"\x00\x00"

    client = DoubaoAsrClient(credentials_provider=credentials)
    task = asyncio.create_task(client.transcribe_pcm_stream(audio()))
    await started.wait()
    assert client.last_metrics["phase"] == "starting"
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    metrics = client.last_metrics
    assert metrics["phase"] == "cancelled"
    assert metrics["endpoint"]["state"] == "cancelled"
    assert metrics["endpoint"]["terminal"] is True
    assert not metrics["endpoint"]["interrupt_ready"]
