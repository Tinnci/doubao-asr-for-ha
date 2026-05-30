# Notices

## Upstream API and protocol reference

This project implements a Home Assistant Wyoming ASR add-on using Doubao ASR
protocol definitions and behavior inferred from upstream open source projects.

The concrete ASR endpoint constants, client flow, protobuf message structure,
session lifecycle, device registration behavior, and audio framing are derived
from:

- `EvanDbg/doubao-ime-win`: https://github.com/EvanDbg/doubao-ime-win
- `src/asr/client.rs`: https://github.com/EvanDbg/doubao-ime-win/blob/main/src/asr/client.rs
- `src/asr/constants.rs`: https://github.com/EvanDbg/doubao-ime-win/blob/main/src/asr/constants.rs

The upstream README states that its implementation is based on analysis of the
Doubao input method client protocol and is not an official API. This repository
preserves that context and does not claim official affiliation with Doubao,
ByteDance, or any related product.

## License compatibility

The upstream `EvanDbg/doubao-ime-win` README declares MIT License. This project
is also released under MIT License. See `LICENSE`.
