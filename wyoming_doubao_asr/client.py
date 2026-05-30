"""Async Doubao ASR client."""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
import uuid
from collections.abc import Awaitable, Callable, Iterable
from typing import Protocol

import aiohttp
import opuslib

from .audio import iter_pcm_frames
from .constants import (
    AID,
    CHANNELS,
    FRAME_DURATION_MS,
    SAMPLE_RATE,
    SAMPLE_WIDTH,
    USER_AGENT,
    WEBSOCKET_URL,
)
from .device import DeviceCredentials
from .protocol import (
    FRAME_STATE_FIRST,
    FRAME_STATE_LAST,
    FRAME_STATE_MIDDLE,
    ResponseType,
    build_finish_session,
    build_start_session,
    build_start_task,
    build_task_request,
    parse_response,
)

_LOGGER = logging.getLogger(__name__)


class DoubaoWebSocket(Protocol):
    async def send_bytes(self, data: bytes) -> None:
        """Send a binary websocket message."""

    async def receive_bytes(self) -> bytes:
        """Receive a binary websocket message."""

    async def close(self) -> None:
        """Close the websocket."""


class DoubaoTransport(Protocol):
    async def connect(self, url: str, headers: dict[str, str]) -> DoubaoWebSocket:
        """Connect to the websocket endpoint."""


class AiohttpTransport:
    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None

    async def connect(self, url: str, headers: dict[str, str]) -> DoubaoWebSocket:
        self._session = aiohttp.ClientSession()
        return await self._session.ws_connect(url, headers=headers)

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None


class OpusFrameEncoder:
    def __init__(self) -> None:
        self._encoder = opuslib.Encoder(
            SAMPLE_RATE,
            CHANNELS,
            opuslib.APPLICATION_AUDIO,
        )

    def encode(self, pcm_frame: bytes) -> bytes:
        frame_size = len(pcm_frame) // (SAMPLE_WIDTH * CHANNELS)
        return self._encoder.encode(pcm_frame, frame_size)


CredentialsProvider = Callable[
    [],
    DeviceCredentials | Awaitable[DeviceCredentials],
]
RefreshCredentials = Callable[
    [],
    DeviceCredentials | Awaitable[DeviceCredentials],
]


class DoubaoAsrError(RuntimeError):
    """ASR error with enough context for Home Assistant logs."""

    def __init__(
        self,
        phase: str,
        message: str,
        *,
        request_id: str | None = None,
    ) -> None:
        self.phase = phase
        self.request_id = request_id
        prefix = f"Doubao ASR {phase} failed"
        if request_id:
            prefix = f"{prefix} (request_id={request_id})"
        super().__init__(f"{prefix}: {message}")


class DoubaoAsrClient:
    def __init__(
        self,
        *,
        credentials_provider: CredentialsProvider,
        refresh_credentials: RefreshCredentials | None = None,
        transport: DoubaoTransport | None = None,
        encoder_factory: Callable[[], OpusFrameEncoder] = OpusFrameEncoder,
        request_id_factory: Callable[[], str] | None = None,
        time_ms_factory: Callable[[], int] | None = None,
        response_timeout_s: float = 15.0,
    ) -> None:
        self._credentials_provider = credentials_provider
        self._refresh_credentials = refresh_credentials
        self._transport = transport or AiohttpTransport()
        self._encoder_factory = encoder_factory
        self._request_id_factory = request_id_factory or (lambda: str(uuid.uuid4()))
        self._time_ms_factory = time_ms_factory or (lambda: int(time.time() * 1000))
        self._response_timeout_s = response_timeout_s

    async def transcribe_pcm(
        self,
        pcm_chunks: Iterable[bytes],
        *,
        language: str | None = None,
    ) -> str:
        del language
        request_id = self._request_id_factory()
        _LOGGER.info("Doubao ASR request started request_id=%s", request_id)
        audio_chunks = list(pcm_chunks)

        try:
            credentials = await self._get_credentials()
        except Exception as err:
            raise DoubaoAsrError(
                "credentials",
                str(err),
                request_id=request_id,
            ) from err

        try:
            return await self._transcribe_with_credentials(
                audio_chunks,
                credentials,
                request_id,
            )
        except DoubaoAsrError as err:
            if not (
                (err.phase == "start_task")
                and _is_auth_error(str(err))
                and (self._refresh_credentials is not None)
            ):
                raise

            _LOGGER.warning(
                "Doubao ASR auth failed; refreshing credentials request_id=%s",
                request_id,
            )
            refreshed_credentials = await self._refresh_credentials_now()
            return await self._transcribe_with_credentials(
                audio_chunks,
                refreshed_credentials,
                request_id,
            )

    async def _transcribe_with_credentials(
        self,
        pcm_chunks: list[bytes],
        credentials: DeviceCredentials,
        request_id: str,
    ) -> str:
        try:
            ws = await self._transport.connect(
                self._ws_url(credentials.device_id),
                self._headers(),
            )
        except Exception as err:
            raise DoubaoAsrError("connect", str(err), request_id=request_id) from err

        try:
            _LOGGER.debug("Doubao ASR StartTask request_id=%s", request_id)
            await ws.send_bytes(build_start_task(request_id, credentials.token))
            await self._expect(
                ws,
                ResponseType.TASK_STARTED,
                "start_task",
                request_id,
            )

            _LOGGER.debug("Doubao ASR StartSession request_id=%s", request_id)
            await ws.send_bytes(
                build_start_session(request_id, credentials.token, credentials.device_id)
            )
            await self._expect(
                ws,
                ResponseType.SESSION_STARTED,
                "start_session",
                request_id,
            )

            encoder = self._encoder_factory()
            start_time_ms = self._time_ms_factory()
            frame_index = 0

            try:
                for pcm_frame in iter_pcm_frames(
                    pcm_chunks,
                    sample_rate=SAMPLE_RATE,
                    channels=CHANNELS,
                    width=SAMPLE_WIDTH,
                ):
                    frame_state = (
                        FRAME_STATE_FIRST if frame_index == 0 else FRAME_STATE_MIDDLE
                    )
                    timestamp_ms = start_time_ms + frame_index * FRAME_DURATION_MS
                    await ws.send_bytes(
                        build_task_request(
                            request_id,
                            encoder.encode(pcm_frame),
                            frame_state,
                            timestamp_ms,
                        )
                    )
                    frame_index += 1

                if frame_index > 0:
                    await ws.send_bytes(
                        build_task_request(
                            request_id,
                            b"\x00" * 100,
                            FRAME_STATE_LAST,
                            start_time_ms + frame_index * FRAME_DURATION_MS,
                        )
                    )
            except Exception as err:
                raise DoubaoAsrError(
                    "send_audio",
                    str(err),
                    request_id=request_id,
                ) from err

            _LOGGER.debug(
                "Doubao ASR sent audio request_id=%s frames=%s",
                request_id,
                frame_index,
            )
            try:
                await ws.send_bytes(build_finish_session(request_id, credentials.token))
            except Exception as err:
                raise DoubaoAsrError(
                    "finish_session",
                    str(err),
                    request_id=request_id,
                ) from err

            text = await self._read_transcript(ws, request_id)
            _LOGGER.info(
                "Doubao ASR request completed request_id=%s transcript_chars=%s",
                request_id,
                len(text),
            )
            return text
        finally:
            await ws.close()
            close_transport = getattr(self._transport, "close", None)
            if close_transport is not None:
                result = close_transport()
                if inspect.isawaitable(result):
                    await result

    async def _refresh_credentials_now(self) -> DeviceCredentials:
        assert self._refresh_credentials is not None
        credentials = self._refresh_credentials()
        if inspect.isawaitable(credentials):
            return await credentials
        return credentials

    async def _get_credentials(self) -> DeviceCredentials:
        credentials = self._credentials_provider()
        if inspect.isawaitable(credentials):
            return await credentials
        return credentials

    async def _expect(
        self,
        ws: DoubaoWebSocket,
        expected_type: ResponseType,
        phase: str,
        request_id: str,
    ) -> None:
        try:
            data = await asyncio.wait_for(
                ws.receive_bytes(),
                timeout=self._response_timeout_s,
            )
        except TimeoutError as err:
            raise DoubaoAsrError(
                phase,
                f"timed out after {self._response_timeout_s:g}s",
                request_id=request_id,
            ) from err

        response = parse_response(data)
        if response.response_type is ResponseType.ERROR:
            raise DoubaoAsrError(
                phase,
                response.error_msg or "upstream returned an error",
                request_id=request_id,
            )
        if response.response_type is not expected_type:
            raise DoubaoAsrError(
                phase,
                f"expected {expected_type.name}, got {response.response_type.name}",
                request_id=request_id,
            )

    async def _read_transcript(self, ws: DoubaoWebSocket, request_id: str) -> str:
        final_text = ""

        while True:
            try:
                data = await asyncio.wait_for(
                    ws.receive_bytes(),
                    timeout=self._response_timeout_s,
                )
            except TimeoutError as err:
                raise DoubaoAsrError(
                    "read_transcript",
                    f"timed out after {self._response_timeout_s:g}s",
                    request_id=request_id,
                ) from err

            response = parse_response(data)

            if response.response_type is ResponseType.ERROR:
                raise DoubaoAsrError(
                    "read_transcript",
                    response.error_msg or "upstream returned an error",
                    request_id=request_id,
                )

            if response.response_type is ResponseType.FINAL_RESULT and response.text:
                final_text = response.text

            if response.response_type is ResponseType.SESSION_FINISHED:
                return final_text

    def _ws_url(self, device_id: str) -> str:
        return f"{WEBSOCKET_URL}?aid={AID}&device_id={device_id}"

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": USER_AGENT,
            "proto-version": "v2",
            "x-custom-keepalive": "true",
            "Host": "frontier-audio-ime-ws.doubao.com",
        }


def _is_auth_error(message: str) -> bool:
    normalized = message.lower()
    return any(
        marker in normalized
        for marker in (
            "auth",
            "unauthorized",
            "forbidden",
            "token",
            "app_key",
            "permission",
        )
    )
