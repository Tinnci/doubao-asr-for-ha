"""Wyoming event handler for Doubao ASR."""

from __future__ import annotations

import logging
from typing import Protocol

from wyoming.asr import Transcribe, Transcript
from wyoming.audio import AudioChunk, AudioChunkConverter, AudioStop
from wyoming.event import Event
from wyoming.info import AsrModel, AsrProgram, Attribution, Describe, Info
from wyoming.server import AsyncEventHandler

from . import __version__
from .constants import CHANNELS, SAMPLE_RATE, SAMPLE_WIDTH

_LOGGER = logging.getLogger(__name__)


class TranscriptionClient(Protocol):
    async def transcribe_pcm(
        self,
        pcm_chunks,
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
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._info_event = wyoming_info.event()
        self._client = client
        self._language: str | None = None
        self._audio_chunks: list[bytes] = []
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
            self._language = transcribe.language
            self._audio_chunks.clear()
            return True

        if AudioChunk.is_type(event.type):
            chunk = self._audio_converter.convert(AudioChunk.from_event(event))
            self._audio_chunks.append(chunk.audio)
            return True

        if AudioStop.is_type(event.type):
            text = await self._client.transcribe_pcm(
                list(self._audio_chunks),
                language=self._language,
            )
            _LOGGER.info("Transcript: %s", text)
            await self.write_event(Transcript(text=text, language=self._language).event())
            self._audio_chunks.clear()
            self._language = None
            return False

        return True


def build_info() -> Info:
    attribution = Attribution(
        name="EvanDbg/doubao-ime-win",
        url="https://github.com/EvanDbg/doubao-ime-win",
    )
    return Info(
        asr=[
            AsrProgram(
                name="doubao-asr",
                description="Doubao ASR via Wyoming",
                attribution=attribution,
                installed=True,
                version=__version__,
                models=[
                    AsrModel(
                        name="doubao-realtime",
                        description="Doubao realtime ASR websocket service",
                        attribution=attribution,
                        installed=True,
                        version=__version__,
                        languages=["zh"],
                    )
                ],
            )
        ]
    )
