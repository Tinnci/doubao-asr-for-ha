"""Audio helpers for Doubao ASR."""

from collections.abc import AsyncIterable, AsyncIterator, Iterable, Iterator

from .constants import FRAME_DURATION_MS


def iter_pcm_frames(
    chunks: Iterable[bytes],
    *,
    sample_rate: int,
    channels: int,
    width: int,
) -> Iterator[bytes]:
    bytes_per_frame = int(sample_rate * FRAME_DURATION_MS / 1000) * channels * width
    if bytes_per_frame <= 0:
        raise ValueError("invalid audio format")

    pending = bytearray()

    for chunk in chunks:
        pending.extend(chunk)
        while len(pending) >= bytes_per_frame:
            yield bytes(pending[:bytes_per_frame])
            del pending[:bytes_per_frame]

    if pending:
        yield bytes(pending)


async def async_iter_pcm_frames(
    chunks: AsyncIterable[bytes],
    *,
    sample_rate: int,
    channels: int,
    width: int,
) -> AsyncIterator[bytes]:
    bytes_per_frame = int(sample_rate * FRAME_DURATION_MS / 1000) * channels * width
    if bytes_per_frame <= 0:
        raise ValueError("invalid audio format")

    pending = bytearray()

    async for chunk in chunks:
        pending.extend(chunk)
        while len(pending) >= bytes_per_frame:
            yield bytes(pending[:bytes_per_frame])
            del pending[:bytes_per_frame]

    if pending:
        yield bytes(pending)
