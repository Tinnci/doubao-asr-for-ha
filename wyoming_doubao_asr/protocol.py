"""Doubao ASR websocket message builders and parsers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

from .constants import AID, APP_NAME, SERVICE_NAME, VERSION_CODE, VERSION_NAME
from .protobuf import encode_bytes, encode_int32, encode_string, iter_fields

FRAME_STATE_UNSPECIFIED = 0
FRAME_STATE_FIRST = 1
FRAME_STATE_MIDDLE = 3
FRAME_STATE_LAST = 9


class ResponseType(Enum):
    TASK_STARTED = auto()
    SESSION_STARTED = auto()
    SESSION_FINISHED = auto()
    VAD_START = auto()
    INTERIM_RESULT = auto()
    FINAL_RESULT = auto()
    HEARTBEAT = auto()
    ERROR = auto()
    UNKNOWN = auto()


@dataclass
class AsrResponse:
    response_type: ResponseType = ResponseType.UNKNOWN
    text: str = ""
    is_final: bool = False
    vad_start: bool = False
    vad_finished: bool = False
    packet_number: int = -1
    error_msg: str = ""
    raw_json: dict[str, Any] | None = None


def build_start_task(request_id: str, token: str) -> bytes:
    return _encode_request(
        token=token,
        service_name=SERVICE_NAME,
        method_name="StartTask",
        request_id=request_id,
    )


def build_start_session(request_id: str, token: str, device_id: str) -> bytes:
    payload = json.dumps(_session_config(device_id), ensure_ascii=False)
    return _encode_request(
        token=token,
        service_name=SERVICE_NAME,
        method_name="StartSession",
        payload=payload,
        request_id=request_id,
    )


def build_finish_session(request_id: str, token: str) -> bytes:
    return _encode_request(
        token=token,
        service_name=SERVICE_NAME,
        method_name="FinishSession",
        request_id=request_id,
    )


def build_task_request(
    request_id: str,
    audio_data: bytes,
    frame_state: int,
    timestamp_ms: int,
) -> bytes:
    payload = json.dumps({"extra": {}, "timestamp_ms": timestamp_ms})
    return _encode_request(
        service_name=SERVICE_NAME,
        method_name="TaskRequest",
        payload=payload,
        audio_data=audio_data,
        request_id=request_id,
        frame_state=frame_state,
    )


def parse_response(data: bytes) -> AsrResponse:
    pb = decode_response(data)
    message_type = pb["message_type"]

    if message_type == "TaskStarted":
        return AsrResponse(response_type=ResponseType.TASK_STARTED)
    if message_type == "SessionStarted":
        return AsrResponse(response_type=ResponseType.SESSION_STARTED)
    if message_type == "SessionFinished":
        return AsrResponse(response_type=ResponseType.SESSION_FINISHED)
    if message_type in {"TaskFailed", "SessionFailed"}:
        return AsrResponse(
            response_type=ResponseType.ERROR,
            error_msg=pb["status_message"],
        )

    result_json = pb["result_json"]
    if not result_json:
        return AsrResponse()

    try:
        json_data = json.loads(result_json)
    except json.JSONDecodeError:
        return AsrResponse()

    extra = json_data.get("extra") or {}
    packet_number = int(extra.get("packet_number", -1))

    if extra.get("vad_start") is True:
        return AsrResponse(
            response_type=ResponseType.VAD_START,
            vad_start=True,
            packet_number=packet_number,
            raw_json=json_data,
        )

    if "results" not in json_data:
        return AsrResponse(
            response_type=ResponseType.HEARTBEAT,
            packet_number=packet_number,
            raw_json=json_data,
        )

    text = ""
    is_interim = True
    vad_finished = False
    nonstream_result = False

    for result in json_data.get("results") or []:
        text = result.get("text") or text
        if result.get("is_interim") is False:
            is_interim = False
        if result.get("is_vad_finished") is True:
            vad_finished = True
        if (result.get("extra") or {}).get("nonstream_result") is True:
            nonstream_result = True

    if nonstream_result or ((not is_interim) and vad_finished):
        return AsrResponse(
            response_type=ResponseType.FINAL_RESULT,
            text=text,
            is_final=True,
            vad_finished=vad_finished,
            packet_number=packet_number,
            raw_json=json_data,
        )

    return AsrResponse(
        response_type=ResponseType.INTERIM_RESULT,
        text=text,
        packet_number=packet_number,
        raw_json=json_data,
    )


def decode_request(data: bytes) -> dict[str, Any]:
    request: dict[str, Any] = {
        "token": "",
        "service_name": "",
        "method_name": "",
        "payload": "",
        "audio_data": b"",
        "request_id": "",
        "frame_state": FRAME_STATE_UNSPECIFIED,
    }

    for field_number, _wire_type, value in iter_fields(data):
        if field_number == 2:
            request["token"] = _as_string(value)
        elif field_number == 3:
            request["service_name"] = _as_string(value)
        elif field_number == 5:
            request["method_name"] = _as_string(value)
        elif field_number == 6:
            request["payload"] = _as_string(value)
        elif field_number == 7:
            request["audio_data"] = value
        elif field_number == 8:
            request["request_id"] = _as_string(value)
        elif field_number == 9:
            request["frame_state"] = value

    return request


def decode_response(data: bytes) -> dict[str, Any]:
    response: dict[str, Any] = {
        "request_id": "",
        "task_id": "",
        "service_name": "",
        "message_type": "",
        "status_code": 0,
        "status_message": "",
        "result_json": "",
        "unknown_field_9": 0,
    }

    for field_number, _wire_type, value in iter_fields(data):
        if field_number == 1:
            response["request_id"] = _as_string(value)
        elif field_number == 2:
            response["task_id"] = _as_string(value)
        elif field_number == 3:
            response["service_name"] = _as_string(value)
        elif field_number == 4:
            response["message_type"] = _as_string(value)
        elif field_number == 5:
            response["status_code"] = value
        elif field_number == 6:
            response["status_message"] = _as_string(value)
        elif field_number == 7:
            response["result_json"] = _as_string(value)
        elif field_number == 9:
            response["unknown_field_9"] = value

    return response


def encode_response(
    *,
    request_id: str = "",
    task_id: str = "",
    service_name: str = SERVICE_NAME,
    message_type: str,
    status_code: int = 0,
    status_message: str = "",
    result_json: str = "",
    unknown_field_9: int = 0,
) -> bytes:
    return b"".join(
        (
            encode_string(1, request_id),
            encode_string(2, task_id),
            encode_string(3, service_name),
            encode_string(4, message_type),
            encode_int32(5, status_code),
            encode_string(6, status_message),
            encode_string(7, result_json),
            encode_int32(9, unknown_field_9),
        )
    )


def _encode_request(
    *,
    token: str = "",
    service_name: str,
    method_name: str,
    payload: str = "",
    audio_data: bytes = b"",
    request_id: str,
    frame_state: int = FRAME_STATE_UNSPECIFIED,
) -> bytes:
    return b"".join(
        (
            encode_string(2, token),
            encode_string(3, service_name),
            encode_string(5, method_name),
            encode_string(6, payload),
            encode_bytes(7, audio_data),
            encode_string(8, request_id),
            encode_int32(9, frame_state),
        )
    )


def _session_config(device_id: str) -> dict[str, Any]:
    return {
        "audio_info": {
            "channel": 1,
            "format": "speech_opus",
            "sample_rate": 16000,
        },
        "enable_punctuation": True,
        "enable_speech_rejection": False,
        "extra": {
            "aid": str(AID),
            "app_name": APP_NAME,
            "cell_compress_rate": 8,
            "did": device_id,
            "enable_asr_threepass": True,
            "enable_asr_twopass": True,
            "input_mode": "tool",
            "update_version_code": str(VERSION_CODE),
            "version_code": str(VERSION_CODE),
            "version_name": VERSION_NAME,
        },
    }


def _as_string(value: bytes | int) -> str:
    if isinstance(value, int):
        return str(value)
    return value.decode("utf-8")
