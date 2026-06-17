import json

from wyoming_doubao_asr.constants import (
    APP_NAME,
    SERVICE_NAME,
    VERSION_CODE,
    VERSION_NAME,
)
from wyoming_doubao_asr.protocol import (
    FRAME_STATE_FIRST,
    FRAME_STATE_UNSPECIFIED,
    ResponseType,
    build_start_session,
    build_start_task,
    build_task_request,
    decode_request,
    encode_response,
    parse_response,
)


def test_build_start_task_encodes_auth_fields() -> None:
    data = build_start_task("request-1", "token-1")

    request = decode_request(data)

    assert request["token"] == "token-1"
    assert request["service_name"] == SERVICE_NAME
    assert request["method_name"] == "StartTask"
    assert request["request_id"] == "request-1"
    assert request["frame_state"] == FRAME_STATE_UNSPECIFIED


def test_build_start_session_encodes_json_session_config() -> None:
    data = build_start_session("request-1", "token-1", "device-1")

    request = decode_request(data)
    payload = json.loads(request["payload"])

    assert request["method_name"] == "StartSession"
    assert payload["audio_info"] == {
        "channel": 1,
        "format": "speech_opus",
        "sample_rate": 16000,
    }
    assert payload["extra"]["did"] == "device-1"
    assert payload["extra"]["app_name"] == APP_NAME
    assert payload["extra"]["version_code"] == str(VERSION_CODE)
    assert payload["extra"]["version_name"] == VERSION_NAME
    assert payload["extra"]["enable_asr_twopass"] is True


def test_build_task_request_encodes_audio_and_timestamp() -> None:
    data = build_task_request("request-1", b"opus", FRAME_STATE_FIRST, 1234)

    request = decode_request(data)
    payload = json.loads(request["payload"])

    assert request["method_name"] == "TaskRequest"
    assert request["audio_data"] == b"opus"
    assert request["frame_state"] == FRAME_STATE_FIRST
    assert payload["timestamp_ms"] == 1234


def test_parse_response_returns_final_text_when_vad_finished() -> None:
    response_bytes = encode_response(
        message_type="",
        result_json=json.dumps(
            {
                "results": [
                    {
                        "text": "打开客厅灯",
                        "is_interim": False,
                        "is_vad_finished": True,
                    }
                ],
                "extra": {"packet_number": 7},
            },
            ensure_ascii=False,
        ),
    )

    response = parse_response(response_bytes)

    assert response.response_type is ResponseType.FINAL_RESULT
    assert response.text == "打开客厅灯"
    assert response.is_final is True
    assert response.vad_finished is True
    assert response.packet_number == 7


def test_parse_response_reports_task_failed_status_message() -> None:
    response_bytes = encode_response(
        message_type="TaskFailed",
        status_message="bad token",
    )

    response = parse_response(response_bytes)

    assert response.response_type is ResponseType.ERROR
    assert response.error_msg == "bad token"
