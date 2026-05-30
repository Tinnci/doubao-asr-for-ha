from wyoming_doubao_asr.audio import iter_pcm_frames


def test_iter_pcm_frames_splits_to_20ms_at_16khz_mono_s16le() -> None:
    one_sample = b"\x01\x00"
    pcm = one_sample * 640

    frames = list(iter_pcm_frames([pcm], sample_rate=16000, channels=1, width=2))

    assert frames == [one_sample * 320, one_sample * 320]


def test_iter_pcm_frames_keeps_partial_tail_for_final_frame() -> None:
    one_sample = b"\x01\x00"
    pcm = one_sample * 330

    frames = list(iter_pcm_frames([pcm], sample_rate=16000, channels=1, width=2))

    assert frames == [one_sample * 320, one_sample * 10]
