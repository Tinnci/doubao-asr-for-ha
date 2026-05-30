import json

from wyoming_doubao_asr.client import DoubaoAsrClient
from wyoming_doubao_asr.device import DeviceCredentials
from wyoming_doubao_asr.protocol import (
    FRAME_STATE_FIRST,
    FRAME_STATE_LAST,
    FRAME_STATE_MIDDLE,
    ResponseType,
    decode_request,
    encode_response,
)


class FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[bytes] = []
        self.responses = [
            encode_response(message_type="TaskStarted"),
            encode_response(message_type="SessionStarted"),
            encode_response(
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
                        "extra": {"packet_number": 1},
                    },
                    ensure_ascii=False,
                ),
            ),
            encode_response(message_type="SessionFinished"),
        ]
        self.closed = False

    async def send_bytes(self, data: bytes) -> None:
        self.sent.append(data)

    async def receive_bytes(self) -> bytes:
        return self.responses.pop(0)

    async def close(self) -> None:
        self.closed = True


class FakeTransport:
    def __init__(self, websocket: FakeWebSocket) -> None:
        self.websocket = websocket
        self.connect_calls = []

    async def connect(self, url: str, headers: dict[str, str]) -> FakeWebSocket:
        self.connect_calls.append((url, headers))
        return self.websocket


class FakeEncoder:
    def encode(self, pcm_frame: bytes) -> bytes:
        return b"opus:" + pcm_frame[:1]


async def test_transcribe_pcm_runs_doubao_session_sequence() -> None:
    websocket = FakeWebSocket()
    transport = FakeTransport(websocket)
    client = DoubaoAsrClient(
        credentials_provider=lambda: DeviceCredentials(
            device_id="device-1",
            install_id="install-1",
            cdid="cdid-1",
            openudid="open-1",
            clientudid="client-1",
            token="token-1",
        ),
        transport=transport,
        encoder_factory=lambda: FakeEncoder(),
        request_id_factory=lambda: "request-1",
        time_ms_factory=lambda: 1000,
    )

    text = await client.transcribe_pcm(
        [b"\x01\x00" * 640],
        language="zh",
    )

    requests = [decode_request(data) for data in websocket.sent]

    assert text == "打开客厅灯"
    assert requests[0]["method_name"] == "StartTask"
    assert requests[1]["method_name"] == "StartSession"
    assert requests[2]["method_name"] == "TaskRequest"
    assert requests[2]["frame_state"] == FRAME_STATE_FIRST
    assert requests[3]["method_name"] == "TaskRequest"
    assert requests[3]["frame_state"] == FRAME_STATE_MIDDLE
    assert requests[4]["method_name"] == "TaskRequest"
    assert requests[4]["frame_state"] == FRAME_STATE_LAST
    assert requests[5]["method_name"] == "FinishSession"
    assert websocket.closed is True
    assert "device_id=device-1" in transport.connect_calls[0][0]
    assert transport.connect_calls[0][1]["proto-version"] == "v2"


async def test_transcribe_pcm_raises_on_start_task_error() -> None:
    websocket = FakeWebSocket()
    websocket.responses = [
        encode_response(message_type="TaskFailed", status_message="bad token")
    ]
    client = DoubaoAsrClient(
        credentials_provider=lambda: DeviceCredentials(
            device_id="device-1",
            install_id="install-1",
            cdid="cdid-1",
            openudid="open-1",
            clientudid="client-1",
            token="token-1",
        ),
        transport=FakeTransport(websocket),
        encoder_factory=lambda: FakeEncoder(),
    )

    try:
        await client.transcribe_pcm([b"\x01\x00" * 320])
    except RuntimeError as err:
        assert "bad token" in str(err)
    else:
        raise AssertionError("expected RuntimeError")
