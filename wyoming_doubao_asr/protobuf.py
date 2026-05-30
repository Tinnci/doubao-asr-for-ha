"""Small protobuf helpers for the Doubao ASR messages.

The protocol uses a tiny proto3 schema, so manual encoding keeps the package
free of generated-code build steps.
"""

from collections.abc import Iterator

WIRE_VARINT = 0
WIRE_LENGTH_DELIMITED = 2


def encode_varint(value: int) -> bytes:
    chunks = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            chunks.append(byte | 0x80)
        else:
            chunks.append(byte)
            return bytes(chunks)


def decode_varint(data: bytes, offset: int) -> tuple[int, int]:
    shift = 0
    value = 0

    while offset < len(data):
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, offset
        shift += 7

    raise ValueError("unterminated varint")


def encode_key(field_number: int, wire_type: int) -> bytes:
    return encode_varint((field_number << 3) | wire_type)


def encode_string(field_number: int, value: str) -> bytes:
    if not value:
        return b""

    raw = value.encode("utf-8")
    return encode_key(field_number, WIRE_LENGTH_DELIMITED) + encode_varint(len(raw)) + raw


def encode_bytes(field_number: int, value: bytes) -> bytes:
    if not value:
        return b""

    return (
        encode_key(field_number, WIRE_LENGTH_DELIMITED)
        + encode_varint(len(value))
        + value
    )


def encode_int32(field_number: int, value: int) -> bytes:
    if value == 0:
        return b""

    return encode_key(field_number, WIRE_VARINT) + encode_varint(value)


def iter_fields(data: bytes) -> Iterator[tuple[int, int, bytes | int]]:
    offset = 0

    while offset < len(data):
        key, offset = decode_varint(data, offset)
        field_number = key >> 3
        wire_type = key & 0x07

        if wire_type == WIRE_VARINT:
            value, offset = decode_varint(data, offset)
            yield field_number, wire_type, value
            continue

        if wire_type == WIRE_LENGTH_DELIMITED:
            length, offset = decode_varint(data, offset)
            end = offset + length
            yield field_number, wire_type, data[offset:end]
            offset = end
            continue

        raise ValueError(f"unsupported protobuf wire type: {wire_type}")
