import asyncio

from wyoming.asr import Transcribe, Transcript
from wyoming.audio import AudioChunk, AudioStop
from wyoming.info import Describe

from wyoming_doubao_asr.handler import DoubaoEventHandler, build_info


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
