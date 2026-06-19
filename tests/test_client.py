import json
from urllib.parse import parse_qs, urlparse

from wyoming_doubao_asr.client import DoubaoAsrClient, DoubaoAsrError
from wyoming_doubao_asr.constants import APP_NAME, PROTO_VERSION, VERSION_CODE
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


class SequenceTransport:
    def __init__(self, websockets: list[FakeWebSocket]) -> None:
        self.websockets = websockets
        self.connect_calls = []

    async def connect(self, url: str, headers: dict[str, str]) -> FakeWebSocket:
        self.connect_calls.append((url, headers))
        return self.websockets.pop(0)


class FailingTransport:
    async def connect(self, url: str, headers: dict[str, str]) -> FakeWebSocket:
        raise OSError("network down")


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
    query = parse_qs(urlparse(transport.connect_calls[0][0]).query)
    assert query["aid"] == ["401734"]
    assert query["app_name"] == [APP_NAME]
    assert query["did"] == ["device-1"]
    assert query["device_id"] == ["device-1"]
    assert query["iid"] == ["install-1"]
    assert query["install_id"] == ["install-1"]
    assert query["version_code"] == [str(VERSION_CODE)]
    assert query["update_version_code"] == [str(VERSION_CODE)]
    assert transport.connect_calls[0][1]["proto-version"] == PROTO_VERSION


async def test_transcribe_pcm_reports_interim_and_final_results() -> None:
    websocket = FakeWebSocket()
    websocket.responses = [
        encode_response(message_type="TaskStarted"),
        encode_response(message_type="SessionStarted"),
        encode_response(
            message_type="",
            result_json=json.dumps(
                {
                    "results": [
                        {
                            "text": "打开",
                            "is_interim": True,
                            "is_vad_finished": False,
                        }
                    ],
                    "extra": {"packet_number": 1},
                },
                ensure_ascii=False,
            ),
        ),
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
                    "extra": {"packet_number": 2},
                },
                ensure_ascii=False,
            ),
        ),
        encode_response(message_type="SessionFinished"),
    ]
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
    results = []

    async def on_result(response) -> None:
        results.append((response.response_type, response.text, response.packet_number))

    text = await client.transcribe_pcm(
        [b"\x01\x00" * 640],
        language="zh",
        on_result=on_result,
    )

    assert text == "打开客厅灯"
    assert results == [
        (ResponseType.INTERIM_RESULT, "打开", 1),
        (ResponseType.FINAL_RESULT, "打开客厅灯", 2),
    ]
    metrics = client.last_metrics
    assert metrics["phase"] == "complete"
    assert metrics["request_id"] == "request-1"
    assert metrics["audio_bytes"] == 1280
    assert metrics["frames"] == 2
    assert metrics["response_events"] == 3
    assert metrics["interim_results"] == 1
    assert metrics["final_results"] == 1
    assert metrics["vad_start_seen"] is False
    assert metrics["vad_finished_seen"] is True
    assert metrics["vad_start_latency_ms"] is None
    assert isinstance(metrics["vad_finished_latency_ms"], int)
    assert isinstance(metrics["first_interim_latency_ms"], int)
    assert isinstance(metrics["final_result_latency_ms"], int)
    assert metrics["final_packet_number"] == 2
    assert metrics["transcript_chars"] == 5
    assert isinstance(metrics["total_latency_ms"], int)


async def test_transcribe_pcm_tracks_provider_vad_start_metrics() -> None:
    websocket = FakeWebSocket()
    websocket.responses = [
        encode_response(message_type="TaskStarted"),
        encode_response(message_type="SessionStarted"),
        encode_response(
            message_type="",
            result_json=json.dumps(
                {"extra": {"packet_number": 1, "vad_start": True}},
                ensure_ascii=False,
            ),
        ),
        encode_response(
            message_type="",
            result_json=json.dumps(
                {
                    "results": [
                        {
                            "text": "打开",
                            "is_interim": True,
                            "is_vad_finished": False,
                        }
                    ],
                    "extra": {"packet_number": 2},
                },
                ensure_ascii=False,
            ),
        ),
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
                    "extra": {"packet_number": 3},
                },
                ensure_ascii=False,
            ),
        ),
        encode_response(message_type="SessionFinished"),
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
        request_id_factory=lambda: "request-1",
        time_ms_factory=lambda: 1000,
    )

    text = await client.transcribe_pcm([b"\x01\x00" * 640])

    metrics = client.last_metrics
    assert text == "打开客厅灯"
    assert metrics["response_events"] == 4
    assert metrics["vad_events"] == 1
    assert metrics["vad_start_seen"] is True
    assert metrics["vad_finished_seen"] is True
    assert isinstance(metrics["vad_start_latency_ms"], int)
    assert isinstance(metrics["vad_finished_latency_ms"], int)
    assert isinstance(metrics["first_interim_latency_ms"], int)
    assert isinstance(metrics["final_result_latency_ms"], int)
    assert metrics["final_packet_number"] == 3


async def test_transcribe_pcm_defaults_provider_vad_metrics_when_absent() -> None:
    websocket = FakeWebSocket()
    websocket.responses = [
        encode_response(message_type="TaskStarted"),
        encode_response(message_type="SessionStarted"),
        encode_response(
            message_type="",
            result_json=json.dumps(
                {
                    "results": [
                        {
                            "text": "打开灯",
                            "is_interim": False,
                            "extra": {"nonstream_result": True},
                        }
                    ],
                    "extra": {"packet_number": 1},
                },
                ensure_ascii=False,
            ),
        ),
        encode_response(message_type="SessionFinished"),
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
        request_id_factory=lambda: "request-1",
        time_ms_factory=lambda: 1000,
    )

    text = await client.transcribe_pcm([b"\x01\x00" * 640])

    metrics = client.last_metrics
    assert text == "打开灯"
    assert metrics["vad_start_seen"] is False
    assert metrics["vad_finished_seen"] is False
    assert metrics["vad_start_latency_ms"] is None
    assert metrics["vad_finished_latency_ms"] is None
    assert metrics["first_interim_latency_ms"] is None
    assert isinstance(metrics["final_result_latency_ms"], int)


async def test_transcribe_pcm_ignores_result_callback_errors() -> None:
    websocket = FakeWebSocket()
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
        request_id_factory=lambda: "request-1",
        time_ms_factory=lambda: 1000,
    )

    def on_result(_response) -> None:
        raise RuntimeError("lock screen offline")

    text = await client.transcribe_pcm(
        [b"\x01\x00" * 640],
        language="zh",
        on_result=on_result,
    )

    assert text == "打开客厅灯"


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
    except DoubaoAsrError as err:
        assert err.phase == "start_task"
        assert "bad token" in str(err)
        assert "token-1" not in str(err)
    else:
        raise AssertionError("expected DoubaoAsrError")


async def test_transcribe_pcm_wraps_connect_errors_with_phase() -> None:
    client = DoubaoAsrClient(
        credentials_provider=lambda: DeviceCredentials(
            device_id="device-1",
            install_id="install-1",
            cdid="cdid-1",
            openudid="open-1",
            clientudid="client-1",
            token="token-1",
        ),
        transport=FailingTransport(),
        encoder_factory=lambda: FakeEncoder(),
        request_id_factory=lambda: "request-1",
    )

    try:
        await client.transcribe_pcm([b"\x01\x00" * 320])
    except DoubaoAsrError as err:
        assert err.phase == "connect"
        assert err.request_id == "request-1"
        assert "network down" in str(err)
        assert "token-1" not in str(err)
    else:
        raise AssertionError("expected DoubaoAsrError")

    assert client.last_metrics["phase"] == "connect"
    assert client.last_metrics["request_id"] == "request-1"
    assert client.last_metrics["audio_bytes"] == 640


async def test_transcribe_pcm_refreshes_token_once_on_auth_start_task_error() -> None:
    first_websocket = FakeWebSocket()
    first_websocket.responses = [
        encode_response(message_type="TaskFailed", status_message="bad token")
    ]
    second_websocket = FakeWebSocket()
    transport = SequenceTransport([first_websocket, second_websocket])
    credentials = DeviceCredentials(
        device_id="device-1",
        install_id="install-1",
        cdid="cdid-1",
        openudid="open-1",
        clientudid="client-1",
        token="expired-token",
    )
    refresh_calls = []

    async def refresh_credentials() -> DeviceCredentials:
        refresh_calls.append(credentials.token)
        credentials.token = "fresh-token"
        return credentials

    client = DoubaoAsrClient(
        credentials_provider=lambda: credentials,
        refresh_credentials=refresh_credentials,
        transport=transport,
        encoder_factory=lambda: FakeEncoder(),
        request_id_factory=lambda: "request-1",
        time_ms_factory=lambda: 1000,
    )

    text = await client.transcribe_pcm(iter([b"\x01\x00" * 320]))

    first_start_task = decode_request(first_websocket.sent[0])
    second_start_task = decode_request(second_websocket.sent[0])
    second_methods = [
        decode_request(data)["method_name"] for data in second_websocket.sent
    ]

    assert text == "打开客厅灯"
    assert refresh_calls == ["expired-token"]
    assert first_start_task["token"] == "expired-token"
    assert second_start_task["token"] == "fresh-token"
    assert "TaskRequest" in second_methods
    assert first_websocket.closed is True
    assert second_websocket.closed is True
    assert len(transport.connect_calls) == 2
