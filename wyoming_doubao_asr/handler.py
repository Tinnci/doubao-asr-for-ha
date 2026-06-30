"""Wyoming event handler for Doubao ASR."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator, Iterable
from typing import Protocol

from wyoming.asr import Transcribe, Transcript
from wyoming.audio import AudioChunk, AudioChunkConverter, AudioStop
from wyoming.event import Event
from wyoming.info import AsrModel, AsrProgram, Attribution, Describe, Info
from wyoming.server import AsyncEventHandler

from . import __version__
from .client import DoubaoAsrError
from .constants import CHANNELS, SAMPLE_RATE, SAMPLE_WIDTH

_LOGGER = logging.getLogger(__name__)
STREAM_QUEUE_MAX_CHUNKS = 50


class TranscriptionClient(Protocol):
    async def transcribe_pcm(
        self,
        pcm_chunks: Iterable[bytes],
        *,
        language: str | None = None,
    ) -> str:
        """Transcribe 16 kHz mono signed 16-bit PCM chunks."""


class DoubaoEventHandler(AsyncEventHandler):
    """Handles Wyoming ASR events."""

    def __init__(
        self,
        wyoming_info: Info,
        client: TranscriptionClient,
        *args: object,
        **kwargs: object,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._info_event = wyoming_info.event()
        self._client = client
        self._language: str | None = None
        self._audio_chunks: list[bytes] = []
        self._stream_queue: asyncio.Queue[bytes | None] | None = None
        self._stream_task: asyncio.Task[str] | None = None
        self._audio_converter = AudioChunkConverter(
            rate=SAMPLE_RATE,
            width=SAMPLE_WIDTH,
            channels=CHANNELS,
        )

    async def handle_event(self, event: Event) -> bool:
        if Describe.is_type(event.type):
            await self.write_event(self._info_event)
            return True

        if Transcribe.is_type(event.type):
            transcribe = Transcribe.from_event(event)
            await self._cancel_stream_task()
            self._language = transcribe.language
            self._audio_chunks.clear()
            stream_method = getattr(self._client, "transcribe_pcm_stream", None)
            if callable(stream_method):
                self._stream_queue = asyncio.Queue(maxsize=STREAM_QUEUE_MAX_CHUNKS)
                self._stream_task = asyncio.create_task(
                    stream_method(
                        self._audio_stream(),
                        language=self._language,
                    ),
                    name="doubao_asr_stream",
                )
            return True

        if AudioChunk.is_type(event.type):
            chunk = self._audio_converter.convert(AudioChunk.from_event(event))
            if self._stream_queue is not None:
                self._raise_if_stream_stopped()
                await self._stream_queue.put(chunk.audio)
            else:
                self._audio_chunks.append(chunk.audio)
            return True

        if AudioStop.is_type(event.type):
            try:
                text = await self._finish_transcription()
            except DoubaoAsrError as err:
                _LOGGER.exception(
                    "Doubao ASR failed phase=%s request_id=%s",
                    err.phase,
                    err.request_id,
                )
                raise
            try:
                _LOGGER.info("Transcript: %s", text)
                await self.write_event(
                    Transcript(text=text, language=self._language).event()
                )
            finally:
                self._audio_chunks.clear()
                self._language = None
                self._stream_queue = None
                self._stream_task = None
            return False

        return True

    async def _audio_stream(self) -> AsyncIterator[bytes]:
        while self._stream_queue is not None:
            chunk = await self._stream_queue.get()
            if chunk is None:
                break
            yield chunk

    async def _finish_transcription(self) -> str:
        if self._stream_task is None:
            return await self._client.transcribe_pcm(
                list(self._audio_chunks),
                language=self._language,
            )
        if self._stream_queue is not None:
            await self._stream_queue.put(None)
        return await self._stream_task

    async def _cancel_stream_task(self) -> None:
        if self._stream_task is None or self._stream_task.done():
            return
        self._stream_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._stream_task

    def _raise_if_stream_stopped(self) -> None:
        if self._stream_task is None or not self._stream_task.done():
            return
        if self._stream_task.cancelled():
            raise DoubaoAsrError("stream_audio", "streaming task was cancelled")
        try:
            self._stream_task.result()
        except DoubaoAsrError:
            raise
        except Exception as err:
            raise DoubaoAsrError("stream_audio", str(err)) from err
        raise DoubaoAsrError("stream_audio", "streaming task ended before AudioStop")


def build_info() -> Info:
    attribution = Attribution(
        name="doubao-asr-for-ha",
        url="https://github.com/Tinnci/doubao-asr-for-ha",
    )
    return Info(
        asr=[
            AsrProgram(
                name="doubao-asr",
                description="Doubao ASR via Wyoming / 通过 Wyoming 接入豆包语音识别",
                attribution=attribution,
                installed=True,
                version=__version__,
                models=[
                    AsrModel(
                        name="doubao-realtime",
                        description=(
                            "Doubao realtime ASR websocket service / "
                            "豆包实时语音识别 WebSocket 服务"
                        ),
                        attribution=attribution,
                        installed=True,
                        version=__version__,
                        languages=["zh"],
                    )
                ],
            )
        ]
    )
