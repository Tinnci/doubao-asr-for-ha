"""Endpoint summary derived from Doubao ASR request metrics."""

from __future__ import annotations

from typing import Any

IN_PROGRESS_PHASES = {"starting", "connect", "streaming", "send_audio"}


def endpoint_summary(metrics: dict[str, Any]) -> dict[str, Any]:
    """Return a compact endpoint state for callers that should not parse counters."""
    phase = str(metrics.get("phase") or "")
    interim_results = _optional_int(metrics.get("interim_results")) or 0
    final_results = _optional_int(metrics.get("final_results")) or 0
    speech_started = (
        metrics.get("vad_start_seen") is True
        or interim_results > 0
        or final_results > 0
    )
    endpoint_detected = metrics.get("vad_finished_seen") is True or final_results > 0
    error_kind = str(metrics.get("error_kind") or "")

    return {
        "state": _endpoint_state(
            phase=phase,
            speech_started=speech_started,
            endpoint_detected=endpoint_detected,
            interim_results=interim_results,
            error_kind=error_kind,
        ),
        "speech_started": speech_started,
        "endpoint_detected": endpoint_detected,
        "interrupt_ready": phase in IN_PROGRESS_PHASES
        and speech_started
        and not endpoint_detected,
        "terminal": _endpoint_terminal(phase=phase, error_kind=error_kind),
        "reason": _endpoint_reason(
            phase=phase,
            speech_started=speech_started,
            endpoint_detected=endpoint_detected,
            interim_results=interim_results,
            error_kind=error_kind,
        ),
        "failure_phase": str(metrics.get("failure_phase") or "") or None,
        "first_speech_latency_ms": _first_int(
            metrics.get("vad_start_latency_ms"),
            metrics.get("first_interim_latency_ms"),
            metrics.get("first_result_latency_ms"),
        ),
        "endpoint_latency_ms": _first_int(
            metrics.get("vad_finished_latency_ms"),
            metrics.get("final_result_latency_ms"),
        ),
    }


def _endpoint_state(
    *,
    phase: str,
    speech_started: bool,
    endpoint_detected: bool,
    interim_results: int,
    error_kind: str,
) -> str:
    if not phase:
        return "idle"
    if error_kind == "timeout":
        return "timeout"
    if error_kind == "provider_error":
        return "provider_error"
    if error_kind:
        return "error"
    if phase == "complete":
        return "complete"
    if phase not in IN_PROGRESS_PHASES:
        return "error"
    if endpoint_detected:
        return "endpoint_detected"
    if interim_results > 0:
        return "partial"
    if speech_started:
        return "speech_started"
    return "silence"


def _endpoint_terminal(*, phase: str, error_kind: str) -> bool:
    return (
        phase == "complete"
        or bool(error_kind)
        or bool(phase and phase not in IN_PROGRESS_PHASES)
    )


def _endpoint_reason(
    *,
    phase: str,
    speech_started: bool,
    endpoint_detected: bool,
    interim_results: int,
    error_kind: str,
) -> str:
    if not phase:
        return "no_active_request"
    if error_kind:
        return error_kind
    if phase == "complete":
        return "complete"
    if phase not in IN_PROGRESS_PHASES:
        return "unknown_phase"
    if endpoint_detected:
        return "endpoint_detected"
    if interim_results > 0:
        return "provider_partial"
    if speech_started:
        return "speech_detected"
    return "silence"


def _first_int(*values: object) -> int | None:
    for value in values:
        integer = _optional_int(value)
        if integer is not None:
            return integer
    return None


def _optional_int(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
