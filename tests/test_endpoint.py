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
        "terminal": False,
        "reason": "provider_partial",
        "failure_phase": None,
        "first_speech_latency_ms": 180,
        "endpoint_latency_ms": None,
    }


def test_endpoint_summary_marks_in_progress_silence() -> None:
    summary = endpoint_summary(
        {
            "phase": "streaming",
            "interim_results": 0,
            "final_results": 0,
            "vad_start_seen": False,
            "vad_finished_seen": False,
        }
    )

    assert summary["state"] == "silence"
    assert summary["speech_started"] is False
    assert summary["endpoint_detected"] is False
    assert summary["interrupt_ready"] is False
    assert summary["terminal"] is False
    assert summary["reason"] == "silence"


def test_endpoint_summary_marks_provider_vad_speech_start() -> None:
    summary = endpoint_summary(
        {
            "phase": "streaming",
            "interim_results": 0,
            "final_results": 0,
            "vad_start_seen": True,
            "vad_finished_seen": False,
            "vad_start_latency_ms": 95,
        }
    )

    assert summary["state"] == "speech_start"
    assert summary["speech_started"] is True
    assert summary["endpoint_detected"] is False
    assert summary["interrupt_ready"] is True
    assert summary["terminal"] is False
    assert summary["reason"] == "speech_detected"
    assert summary["first_speech_latency_ms"] == 95


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
    assert summary["terminal"] is False
    assert summary["reason"] == "endpoint_detected"
    assert summary["failure_phase"] is None
    assert summary["first_speech_latency_ms"] == 90
    assert summary["endpoint_latency_ms"] == 420


def test_endpoint_summary_distinguishes_timeout_failures() -> None:
    summary = endpoint_summary(
        {
            "phase": "read_transcript",
            "status": "error",
            "failure_phase": "read_transcript",
            "error_kind": "timeout",
        }
    )

    assert summary["state"] == "timeout"
    assert summary["terminal"] is True
    assert summary["reason"] == "timeout"
    assert summary["failure_phase"] == "read_transcript"
    assert summary["interrupt_ready"] is False


def test_endpoint_summary_distinguishes_provider_failures() -> None:
    summary = endpoint_summary(
        {
            "phase": "start_task",
            "status": "error",
            "failure_phase": "start_task",
            "error_kind": "provider_error",
        }
    )

    assert summary["state"] == "provider_error"
    assert summary["terminal"] is True
    assert summary["reason"] == "provider_error"
    assert summary["failure_phase"] == "start_task"
