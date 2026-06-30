import asyncio
import logging

import pytest
from wyoming.asr import Transcribe, Transcript
from wyoming.audio import AudioChunk, AudioStop
from wyoming.info import Describe

from wyoming_doubao_asr.client import DoubaoAsrError
from wyoming_doubao_asr.handler import (
    STREAM_QUEUE_MAX_CHUNKS,
    DoubaoEventHandler,
    build_info,
)


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[list[bytes], str | None]] = []

    async def transcribe_pcm(
        self,
        pcm_chunks,
        *,
        language: str | None = None,
    ) -> str:
        chunks = list(pcm_chunks)
        self.calls.append((chunks, language))
        return "打开客厅灯"


class StreamingFakeClient:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.calls: list[str | None] = []
        self.chunks: list[bytes] = []

    async def transcribe_pcm_stream(
        self,
        pcm_chunks,
        *,
        language: str | None = None,
    ) -> str:
        self.calls.append(language)
        self.started.set()
        async for chunk in pcm_chunks:
            self.chunks.append(chunk)
        return "打开客厅灯"


class PausedStreamingFakeClient:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.chunks: list[bytes] = []

    async def transcribe_pcm_stream(
        self,
        pcm_chunks,
        *,
        language: str | None = None,
    ) -> str:
        del language
        self.started.set()
        await self.release.wait()
        async for chunk in pcm_chunks:
            self.chunks.append(chunk)
        return "打开客厅灯"


class FailingClient:
    async def transcribe_pcm(
        self,
        pcm_chunks,
        *,
        language: str | None = None,
    ) -> str:
        raise DoubaoAsrError("connect", "network down", request_id="request-1")


class EarlyFailingStreamingClient:
    def __init__(self) -> None:
        self.started = asyncio.Event()

    async def transcribe_pcm_stream(
        self,
        pcm_chunks,
        *,
        language: str | None = None,
    ) -> str:
        del pcm_chunks, language
        self.started.set()
        raise DoubaoAsrError("connect", "network down", request_id="request-1")


def make_handler(fake_client: FakeClient) -> tuple[DoubaoEventHandler, list]:
    handler = DoubaoEventHandler(
        build_info(),
        fake_client,
        asyncio.StreamReader(),
        object(),
    )
    written = []

    async def capture(event):
        written.append(event)

    handler.write_event = capture
    return handler, written


async def test_describe_returns_doubao_asr_info() -> None:
    handler, written = make_handler(FakeClient())

    keep_running = await handler.handle_event(Describe().event())

    assert keep_running is True
    assert written[0].type == "info"
    assert written[0].data["asr"][0]["name"] == "doubao-asr"


async def test_audio_stop_transcribes_collected_audio() -> None:
    fake_client = FakeClient()
    handler, written = make_handler(fake_client)

    await handler.handle_event(Transcribe(language="zh").event())
    await handler.handle_event(
        AudioChunk(rate=16000, width=2, channels=1, audio=b"\x01\x00").event()
    )
    keep_running = await handler.handle_event(AudioStop().event())

    transcript = Transcript.from_event(written[0])
    assert keep_running is False
    assert transcript.text == "打开客厅灯"
    assert fake_client.calls == [([b"\x01\x00"], "zh")]


async def test_streaming_client_starts_before_audio_stop() -> None:
    fake_client = StreamingFakeClient()
    handler, written = make_handler(fake_client)

    await handler.handle_event(Transcribe(language="zh").event())
    await asyncio.wait_for(fake_client.started.wait(), timeout=1)
    await handler.handle_event(
        AudioChunk(rate=16000, width=2, channels=1, audio=b"\x01\x00").event()
    )
    keep_running = await handler.handle_event(AudioStop().event())

    transcript = Transcript.from_event(written[0])
    assert keep_running is False
    assert transcript.text == "打开客厅灯"
    assert fake_client.calls == ["zh"]
    assert fake_client.chunks == [b"\x01\x00"]


async def test_streaming_audio_queue_applies_backpressure() -> None:
    fake_client = PausedStreamingFakeClient()
    handler, written = make_handler(fake_client)

    await handler.handle_event(Transcribe(language="zh").event())
    await asyncio.wait_for(fake_client.started.wait(), timeout=1)
    for _ in range(STREAM_QUEUE_MAX_CHUNKS):
        await handler.handle_event(
            AudioChunk(rate=16000, width=2, channels=1, audio=b"\x01\x00").event()
        )

    blocked_put = asyncio.create_task(
        handler.handle_event(
            AudioChunk(rate=16000, width=2, channels=1, audio=b"\x02\x00").event()
        )
    )
    await asyncio.sleep(0)

    assert blocked_put.done() is False

    fake_client.release.set()
    await asyncio.wait_for(blocked_put, timeout=1)
    keep_running = await handler.handle_event(AudioStop().event())

    transcript = Transcript.from_event(written[0])
    assert keep_running is False
    assert transcript.text == "打开客厅灯"
    assert fake_client.chunks[-1] == b"\x02\x00"


async def test_streaming_client_failure_surfaces_before_queueing_audio() -> None:
    fake_client = EarlyFailingStreamingClient()
    handler, _written = make_handler(fake_client)

    await handler.handle_event(Transcribe(language="zh").event())
    await asyncio.wait_for(fake_client.started.wait(), timeout=1)

    with pytest.raises(DoubaoAsrError) as exc_info:
        await handler.handle_event(
            AudioChunk(rate=16000, width=2, channels=1, audio=b"\x01\x00").event()
        )

    assert exc_info.value.phase == "connect"
    assert exc_info.value.request_id == "request-1"


async def test_audio_stop_logs_asr_error_phase(caplog) -> None:
    handler, _written = make_handler(FailingClient())
    caplog.set_level(logging.ERROR)

    await handler.handle_event(Transcribe(language="zh").event())
    await handler.handle_event(
        AudioChunk(rate=16000, width=2, channels=1, audio=b"\x01\x00").event()
    )

    try:
        await handler.handle_event(AudioStop().event())
    except DoubaoAsrError:
        pass
    else:
        raise AssertionError("expected DoubaoAsrError")

    assert "phase=connect" in caplog.text
    assert "request_id=request-1" in caplog.text
