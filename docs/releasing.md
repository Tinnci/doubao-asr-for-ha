# Releasing / 发布

The next planned release is **0.1.9**. The household container labelled
`v0.1.8-privacy1` has the same Python source as maintained commit `6e2bc88`,
including removal of transcript text from INFO logs. The project and add-on
versions remain 0.1.8 until the automatic release workflow bumps them together.

```sh
uv sync --locked --group dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
docker build -t doubao-asr:check .
```

CI and containers use Python 3.13. The container obtains it through uv, including
when Home Assistant supplies the Debian base image in `build.yaml`. CI and the
image share uv 0.12.5; dependencies and Ruff are locked. The Python package still
declares its existing compatibility range for library consumers.

After reviewing and pushing the commit, run **Release** from `main` with `patch`.
The workflow reuses CI tests, Ruff and a local Docker build before changing a
version or pushing a tag. It updates `pyproject.toml`, `config.yaml` and `uv.lock`,
pushes commit/tag atomically, and publishes amd64/arm64 images and GitHub notes.
Direct tag releases run the same verification before publication.

This is a Wyoming server and HA add-on, not a HACS integration. It keeps its
add-on metadata and multi-architecture container workflow; no fake `hacs.json`
or integration manifest is added. Image import/CLI checks do not contact the ASR
provider or prove recognition quality.

发布前验证重用本仓库 CI。版本保护只检查版本字段，常规依赖或说明更新不会被当成
手工发版；真正的识别体验仍需后续语音链路实机验证。
