from wyoming_doubao_asr.endpoint import endpoint_summary


def test_endpoint_summary_marks_partial_speech_interrupt_ready() -> None:
    summary = endpoint_summary(
        {
            "phase": "streaming",
            "interim_results": 1,
            "final_results": 0,
            "vad_start_seen": False,
            "vad_finished_seen": False,
            "first_interim_latency_ms": 180,
        }
    )

    assert summary == {
        "state": "partial",
        "speech_started": True,
        "endpoint_detected": False,
        "interrupt_ready": True,
        "first_speech_latency_ms": 180,
        "endpoint_latency_ms": None,
    }


def test_endpoint_summary_marks_final_endpoint_not_interrupt_ready() -> None:
    summary = endpoint_summary(
        {
            "phase": "streaming",
            "interim_results": 1,
            "final_results": 1,
            "vad_start_seen": True,
            "vad_finished_seen": True,
            "vad_start_latency_ms": 90,
            "vad_finished_latency_ms": 420,
        }
    )

    assert summary["state"] == "endpoint_detected"
    assert summary["speech_started"] is True
    assert summary["endpoint_detected"] is True
    assert summary["interrupt_ready"] is False
    assert summary["first_speech_latency_ms"] == 90
    assert summary["endpoint_latency_ms"] == 420
