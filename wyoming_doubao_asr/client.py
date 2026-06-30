"""Async Doubao ASR client."""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import logging
import time
import uuid
from collections.abc import AsyncIterable, Awaitable, Callable, Iterable
from typing import Any, Protocol
from urllib.parse import urlencode

import aiohttp
import opuslib

from .audio import async_iter_pcm_frames, iter_pcm_frames
from .constants import (
    ACCESS,
    AID,
    APP_NAME,
    CHANNEL,
    CHANNELS,
    DEVICE_BRAND,
    DEVICE_PLATFORM,
    DEVICE_TYPE,
    FRAME_DURATION_MS,
    FRONTIER_HOST,
    OS_VERSION,
    PROTO_VERSION,
    SAMPLE_RATE,
    SAMPLE_WIDTH,
    USER_AGENT,
    VERSION_CODE,
    VERSION_NAME,
    WEBSOCKET_URL,
)
from .device import DeviceCredentials
from .protocol import (
    FRAME_STATE_FIRST,
    FRAME_STATE_LAST,
    FRAME_STATE_MIDDLE,
    AsrResponse,
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
AsrResultCallback = Callable[[AsrResponse], object | Awaitable[object]]
AsrMetricsCallback = Callable[[dict[str, Any]], object | Awaitable[object]]


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
        self._last_metrics: dict[str, Any] = {}

    @property
    def last_metrics(self) -> dict[str, Any]:
        """Return a copy of the latest request metrics for diagnostics."""
        return dict(self._last_metrics)

    async def transcribe_pcm(
        self,
        pcm_chunks: Iterable[bytes],
        *,
        language: str | None = None,
        on_result: AsrResultCallback | None = None,
    ) -> str:
        del language
        request_id = self._request_id_factory()
        request_started = time.monotonic()
        _LOGGER.info("Doubao ASR request started request_id=%s", request_id)
        audio_chunks = list(pcm_chunks)
        audio_bytes = sum(len(chunk) for chunk in audio_chunks)

        try:
            credentials = await self._get_credentials()
        except Exception as err:
            self._record_error_metrics(
                request_id,
                "credentials",
                request_started,
                audio_bytes=audio_bytes,
            )
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
                on_result,
                request_started,
                audio_bytes,
            )
        except DoubaoAsrError as err:
            if not (
                (err.phase == "start_task")
                and _is_auth_error(str(err))
                and (self._refresh_credentials is not None)
            ):
                self._record_error_metrics(
                    request_id,
                    err.phase,
                    request_started,
                    audio_bytes=audio_bytes,
                )
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
                on_result,
                request_started,
                audio_bytes,
            )

    async def transcribe_pcm_stream(
        self,
        pcm_chunks: AsyncIterable[bytes],
        *,
        language: str | None = None,
        on_result: AsrResultCallback | None = None,
    ) -> str:
        del language
        request_id = self._request_id_factory()
        request_started = time.monotonic()
        _LOGGER.info("Doubao ASR streaming request started request_id=%s", request_id)
        self._last_metrics = {
            "request_id": request_id,
            "phase": "starting",
            "audio_bytes": 0,
            "frames": 0,
            "audio_duration_ms": 0,
            "total_latency_ms": 0,
        }

        try:
            credentials = await self._get_credentials()
        except Exception as err:
            self._record_error_metrics(
                request_id,
                "credentials",
                request_started,
                audio_bytes=0,
            )
            raise DoubaoAsrError(
                "credentials",
                str(err),
                request_id=request_id,
            ) from err

        try:
            return await self._transcribe_stream_with_credentials(
                pcm_chunks,
                credentials,
                request_id,
                on_result,
                request_started,
            )
        except DoubaoAsrError as err:
            if not (
                (err.phase == "start_task")
                and _is_auth_error(str(err))
                and (self._refresh_credentials is not None)
            ):
                self._record_error_metrics(
                    request_id,
                    err.phase,
                    request_started,
                    audio_bytes=int(self._last_metrics.get("audio_bytes") or 0),
                )
                raise

            _LOGGER.warning(
                "Doubao ASR streaming auth failed; refreshing credentials "
                "request_id=%s",
                request_id,
            )
            refreshed_credentials = await self._refresh_credentials_now()
            return await self._transcribe_stream_with_credentials(
                pcm_chunks,
                refreshed_credentials,
                request_id,
                on_result,
                request_started,
            )

    async def _transcribe_with_credentials(
        self,
        pcm_chunks: list[bytes],
        credentials: DeviceCredentials,
        request_id: str,
        on_result: AsrResultCallback | None,
        request_started: float,
        audio_bytes: int,
    ) -> str:
        try:
            ws = await self._transport.connect(
                self._ws_url(credentials),
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
                build_start_session(
                    request_id, credentials.token, credentials.device_id
                )
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
            send_started = time.monotonic()

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
                send_metrics = _audio_send_metrics(
                    frame_index,
                    send_started=send_started,
                    request_started=request_started,
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

            text, result_metrics = await self._read_transcript(
                ws, request_id, on_result, request_started
            )
            self._last_metrics = {
                "request_id": request_id,
                "phase": "complete",
                "audio_bytes": audio_bytes,
                "frames": frame_index,
                "transcript_chars": len(text),
                "total_latency_ms": _elapsed_ms(request_started),
                **send_metrics,
                **result_metrics,
            }
            self._last_metrics.update(
                _post_audio_latency_metrics(self._last_metrics)
            )
            _LOGGER.info(
                "Doubao ASR request completed request_id=%s frames=%s "
                "transcript_chars=%s first_result_latency_ms=%s "
                "final_result_latency_ms=%s total_latency_ms=%s",
                request_id,
                frame_index,
                len(text),
                self._last_metrics.get("first_result_latency_ms"),
                self._last_metrics.get("final_result_latency_ms"),
                self._last_metrics.get("total_latency_ms"),
            )
            return text
        finally:
            await ws.close()
            close_transport = getattr(self._transport, "close", None)
            if close_transport is not None:
                result = close_transport()
                if inspect.isawaitable(result):
                    await result

    async def _transcribe_stream_with_credentials(
        self,
        pcm_chunks: AsyncIterable[bytes],
        credentials: DeviceCredentials,
        request_id: str,
        on_result: AsrResultCallback | None,
        request_started: float,
    ) -> str:
        try:
            ws = await self._transport.connect(
                self._ws_url(credentials),
                self._headers(),
            )
        except Exception as err:
            raise DoubaoAsrError("connect", str(err), request_id=request_id) from err

        progress: dict[str, Any] = {"audio_bytes": 0, "frames": 0}
        send_metrics: dict[str, Any] = {}

        def record_stream_metrics(result_metrics: dict[str, Any]) -> None:
            streaming_send_metrics = _streaming_progress_metrics(progress)
            self._last_metrics = {
                "request_id": request_id,
                "phase": "streaming",
                "audio_bytes": progress["audio_bytes"],
                "frames": progress["frames"],
                "audio_duration_ms": _audio_duration_ms(progress["frames"]),
                "total_latency_ms": _elapsed_ms(request_started),
                **streaming_send_metrics,
                **result_metrics,
            }

        reader_task: asyncio.Task[tuple[str, dict[str, Any]]] | None = None
        try:
            _LOGGER.debug("Doubao ASR streaming StartTask request_id=%s", request_id)
            await ws.send_bytes(build_start_task(request_id, credentials.token))
            await self._expect(
                ws,
                ResponseType.TASK_STARTED,
                "start_task",
                request_id,
            )

            _LOGGER.debug("Doubao ASR streaming StartSession request_id=%s", request_id)
            await ws.send_bytes(
                build_start_session(
                    request_id, credentials.token, credentials.device_id
                )
            )
            await self._expect(
                ws,
                ResponseType.SESSION_STARTED,
                "start_session",
                request_id,
            )

            reader_task = asyncio.create_task(
                self._read_transcript(
                    ws,
                    request_id,
                    on_result,
                    request_started,
                    on_metrics=record_stream_metrics,
                ),
                name=f"doubao_asr_read_{request_id}",
            )
            start_time_ms = self._time_ms_factory()
            try:
                send_started = time.monotonic()
                await self._send_pcm_stream(
                    ws,
                    request_id,
                    pcm_chunks,
                    start_time_ms=start_time_ms,
                    progress=progress,
                    send_started=send_started,
                    request_started=request_started,
                )
                send_metrics = _audio_send_metrics(
                    progress["frames"],
                    send_started=send_started,
                    request_started=request_started,
                    first_frame_started=progress.get("_first_frame_started"),
                )
            except Exception as err:
                raise DoubaoAsrError(
                    "send_audio",
                    str(err),
                    request_id=request_id,
                ) from err

            _LOGGER.debug(
                "Doubao ASR streamed audio request_id=%s frames=%s",
                request_id,
                progress["frames"],
            )
            try:
                await ws.send_bytes(build_finish_session(request_id, credentials.token))
            except Exception as err:
                raise DoubaoAsrError(
                    "finish_session",
                    str(err),
                    request_id=request_id,
                ) from err

            text, result_metrics = await reader_task
            self._last_metrics = {
                "request_id": request_id,
                "phase": "complete",
                "audio_bytes": progress["audio_bytes"],
                "frames": progress["frames"],
                "transcript_chars": len(text),
                "total_latency_ms": _elapsed_ms(request_started),
                **send_metrics,
                **result_metrics,
            }
            self._last_metrics.update(
                _post_audio_latency_metrics(self._last_metrics)
            )
            _LOGGER.info(
                "Doubao ASR streaming request completed request_id=%s frames=%s "
                "transcript_chars=%s first_result_latency_ms=%s "
                "final_result_latency_ms=%s total_latency_ms=%s",
                request_id,
                progress["frames"],
                len(text),
                self._last_metrics.get("first_result_latency_ms"),
                self._last_metrics.get("final_result_latency_ms"),
                self._last_metrics.get("total_latency_ms"),
            )
            return text
        finally:
            if reader_task is not None and not reader_task.done():
                reader_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await reader_task
            await ws.close()
            close_transport = getattr(self._transport, "close", None)
            if close_transport is not None:
                result = close_transport()
                if inspect.isawaitable(result):
                    await result

    async def _send_pcm_stream(
        self,
        ws: DoubaoWebSocket,
        request_id: str,
        pcm_chunks: AsyncIterable[bytes],
        *,
        start_time_ms: int,
        progress: dict[str, Any],
        send_started: float,
        request_started: float,
    ) -> None:
        encoder = self._encoder_factory()
        frame_index = 0
        async for pcm_frame in async_iter_pcm_frames(
            pcm_chunks,
            sample_rate=SAMPLE_RATE,
            channels=CHANNELS,
            width=SAMPLE_WIDTH,
        ):
            if frame_index == 0:
                first_frame_started = time.monotonic()
                progress["_first_frame_started"] = first_frame_started
                progress["first_audio_frame_latency_ms"] = _elapsed_ms(
                    request_started
                )
                progress["audio_source_wait_ms"] = _elapsed_ms(send_started)
            frame_state = FRAME_STATE_FIRST if frame_index == 0 else FRAME_STATE_MIDDLE
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
            progress["frames"] = frame_index
            progress["audio_bytes"] += len(pcm_frame)

        if frame_index > 0:
            await ws.send_bytes(
                build_task_request(
                    request_id,
                    b"\x00" * 100,
                    FRAME_STATE_LAST,
                    start_time_ms + frame_index * FRAME_DURATION_MS,
                )
            )

    async def _refresh_credentials_now(self) -> DeviceCredentials:
        if self._refresh_credentials is None:
            raise RuntimeError("credential refresh callback is not configured")
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

    async def _read_transcript(
        self,
        ws: DoubaoWebSocket,
        request_id: str,
        on_result: AsrResultCallback | None = None,
        request_started: float | None = None,
        on_metrics: AsrMetricsCallback | None = None,
    ) -> tuple[str, dict[str, Any]]:
        final_text = ""
        started = request_started or time.monotonic()
        metrics: dict[str, Any] = {
            "response_events": 0,
            "vad_events": 0,
            "interim_results": 0,
            "final_results": 0,
            "vad_start_seen": False,
            "vad_finished_seen": False,
            "vad_start_latency_ms": None,
            "vad_finished_latency_ms": None,
            "first_result_latency_ms": None,
            "first_interim_latency_ms": None,
            "final_result_latency_ms": None,
            "final_packet_number": None,
        }

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
            metrics["response_events"] += 1

            if response.response_type is ResponseType.ERROR:
                raise DoubaoAsrError(
                    "read_transcript",
                    response.error_msg or "upstream returned an error",
                    request_id=request_id,
                )

            if response.response_type in {
                ResponseType.VAD_START,
                ResponseType.INTERIM_RESULT,
                ResponseType.FINAL_RESULT,
            }:
                event_latency_ms = _elapsed_ms(started)
                if metrics["first_result_latency_ms"] is None:
                    metrics["first_result_latency_ms"] = event_latency_ms
                if response.response_type is ResponseType.VAD_START:
                    metrics["vad_events"] += 1
                    metrics["vad_start_seen"] = True
                    if metrics["vad_start_latency_ms"] is None:
                        metrics["vad_start_latency_ms"] = event_latency_ms
                elif response.response_type is ResponseType.INTERIM_RESULT:
                    metrics["interim_results"] += 1
                    if metrics["first_interim_latency_ms"] is None:
                        metrics["first_interim_latency_ms"] = event_latency_ms
                elif response.response_type is ResponseType.FINAL_RESULT:
                    metrics["final_results"] += 1
                    if response.vad_finished:
                        metrics["vad_finished_seen"] = True
                        if metrics["vad_finished_latency_ms"] is None:
                            metrics["vad_finished_latency_ms"] = event_latency_ms
                    if metrics["final_result_latency_ms"] is None:
                        metrics["final_result_latency_ms"] = event_latency_ms
                await self._notify_metrics(on_metrics, metrics, request_id)
                await self._notify_result(on_result, response, request_id)

            if response.response_type is ResponseType.FINAL_RESULT and response.text:
                final_text = response.text
                metrics["final_packet_number"] = response.packet_number

            if response.response_type is ResponseType.SESSION_FINISHED:
                return final_text, metrics

    async def _notify_result(
        self,
        callback: AsrResultCallback | None,
        response: AsrResponse,
        request_id: str,
    ) -> None:
        if callback is None:
            return
        try:
            result = callback(response)
            if inspect.isawaitable(result):
                await result
        except Exception:
            _LOGGER.exception(
                "Doubao ASR result callback failed request_id=%s response_type=%s",
                request_id,
                response.response_type.name,
            )

    async def _notify_metrics(
        self,
        callback: AsrMetricsCallback | None,
        metrics: dict[str, Any],
        request_id: str,
    ) -> None:
        if callback is None:
            return
        try:
            result = callback(dict(metrics))
            if inspect.isawaitable(result):
                await result
        except Exception:
            _LOGGER.exception(
                "Doubao ASR metrics callback failed request_id=%s",
                request_id,
            )

    def _record_error_metrics(
        self,
        request_id: str,
        phase: str,
        started: float,
        *,
        audio_bytes: int,
    ) -> None:
        self._last_metrics = {
            "request_id": request_id,
            "phase": phase,
            "audio_bytes": audio_bytes,
            "frames": 0,
            "audio_duration_ms": 0,
            "total_latency_ms": _elapsed_ms(started),
        }

    def _ws_url(self, credentials: DeviceCredentials) -> str:
        return f"{WEBSOCKET_URL}?{urlencode(_frontier_query(credentials))}"

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": USER_AGENT,
            "proto-version": PROTO_VERSION,
            "x-custom-keepalive": "true",
            "Host": FRONTIER_HOST,
        }


def _frontier_query(credentials: DeviceCredentials) -> dict[str, str]:
    """Return the identity query parameters for the websocket connection."""
    return {
        "uid": "0",
        "aid": str(AID),
        "app_name": APP_NAME,
        "did": credentials.device_id,
        "device_id": credentials.device_id,
        "iid": credentials.install_id,
        "install_id": credentials.install_id,
        "channel": CHANNEL,
        "os_version": OS_VERSION,
        "version_code": str(VERSION_CODE),
        "update_version_code": str(VERSION_CODE),
        "version_name": VERSION_NAME,
        "device_platform": DEVICE_PLATFORM,
        "device_type": DEVICE_TYPE,
        "device_brand": DEVICE_BRAND,
        "ac": ACCESS,
        "ip": "0",
        "user_agent": "",
        "forwarded": "",
        "target": "",
        "mobile": "",
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


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def _audio_duration_ms(frames: int) -> int:
    return max(0, int(frames)) * FRAME_DURATION_MS


def _audio_send_metrics(
    frames: int,
    *,
    send_started: float,
    request_started: float,
    first_frame_started: float | None = None,
) -> dict[str, Any]:
    send_elapsed_ms = _elapsed_ms(send_started)
    audio_duration_ms = _audio_duration_ms(frames)
    if first_frame_started is None and frames > 0:
        first_frame_started = send_started
    actual_send_elapsed_ms = (
        _elapsed_ms(first_frame_started) if first_frame_started is not None else 0
    )
    first_audio_latency_ms = (
        int((first_frame_started - request_started) * 1000)
        if first_frame_started is not None
        else None
    )
    source_wait_ms = (
        int((first_frame_started - send_started) * 1000)
        if first_frame_started is not None
        else None
    )
    return {
        "audio_duration_ms": audio_duration_ms,
        "audio_send_elapsed_ms": send_elapsed_ms,
        "audio_send_actual_elapsed_ms": actual_send_elapsed_ms,
        "audio_send_completed_latency_ms": _elapsed_ms(request_started),
        "first_audio_frame_latency_ms": first_audio_latency_ms,
        "audio_source_wait_ms": source_wait_ms,
        "audio_send_realtime_ratio": (
            round(audio_duration_ms / actual_send_elapsed_ms, 3)
            if actual_send_elapsed_ms > 0
            else None
        ),
    }


def _streaming_progress_metrics(progress: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in (
        "first_audio_frame_latency_ms",
        "audio_source_wait_ms",
    ):
        if key in progress:
            result[key] = progress[key]
    return result


def _post_audio_latency_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    send_completed = metrics.get("audio_send_completed_latency_ms")
    first_latency = metrics.get("first_result_latency_ms")
    final_latency = metrics.get("final_result_latency_ms")
    result: dict[str, Any] = {}
    if isinstance(send_completed, int) and isinstance(first_latency, int):
        result["post_audio_first_result_latency_ms"] = first_latency - send_completed
    if isinstance(send_completed, int) and isinstance(final_latency, int):
        result["post_audio_final_result_latency_ms"] = final_latency - send_completed
    return result
