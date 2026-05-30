# Roadmap

This project is currently an MVP. The next work should focus on proving the
integration in real Home Assistant environments before expanding features.

## Phase 1: Runtime validation

- Build the add-on image on `amd64` and `aarch64`.
- Install the add-on in Home Assistant OS and Home Assistant Supervised.
- Confirm Wyoming discovery from Home Assistant.
- Run an end-to-end Assist pipeline with short Chinese commands.
- Capture logs for successful and failed upstream sessions.

Exit criteria:

- A Home Assistant Assist pipeline can transcribe live audio through this add-on.
- Setup steps and known failure modes are documented.

## Phase 2: Protocol hardening

- Compare live request and response behavior against the upstream reference
  project after real sessions.
- Add tests for additional upstream response shapes observed in the field.
- Improve websocket timeout, retry, and error reporting.
- Decide whether token refresh should happen automatically on ASR failures.

Exit criteria:

- Common upstream failures produce actionable add-on logs.
- Token/device state can recover without manual file deletion where possible.

## Phase 3: Add-on usability

- Add configuration options for response timeout, zeroconf name, and optional
  debug logging.
- Document privacy implications clearly in Home Assistant-facing text.
- Add troubleshooting guidance for no discovery, no transcript, and upstream
  authentication failures.
- Add release notes and versioning discipline for add-on updates.

Exit criteria:

- A new user can install, configure, test, and diagnose the add-on from the
  repository documentation alone.

## Phase 4: CI and release quality

- Add GitHub Actions for tests.
- Add container build checks when practical.
- Publish tagged releases.
- Consider Home Assistant add-on repository validation tooling.

Exit criteria:

- Every pull request runs tests automatically.
- Release artifacts and changelog entries are reproducible.

## Non-goals for now

- Bypassing access controls or paid service restrictions.
- Claiming official Doubao or ByteDance API support.
- Storing or analyzing user voice data beyond what is needed for transcription.
- Adding non-ASR features such as TTS or wake-word detection.
