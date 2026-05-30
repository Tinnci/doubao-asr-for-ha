from pathlib import Path

from wyoming_doubao_asr import device
from wyoming_doubao_asr.device import CredentialStore, DeviceCredentials


async def test_credential_store_refresh_token_clears_and_persists_new_token(
    tmp_path: Path,
    monkeypatch,
) -> None:
    credentials_path = tmp_path / "credentials.json"
    old_credentials = DeviceCredentials(
        device_id="device-1",
        install_id="install-1",
        cdid="cdid-1",
        openudid="open-1",
        clientudid="client-1",
        token="expired-token",
    )
    old_credentials.save(credentials_path)

    refresh_calls = []

    async def fake_get_asr_token(credentials: DeviceCredentials) -> None:
        refresh_calls.append(credentials.token)
        credentials.token = "fresh-token"

    monkeypatch.setattr(device, "get_asr_token", fake_get_asr_token)

    store = CredentialStore(credentials_path)
    refreshed = await store.refresh_token()
    persisted = DeviceCredentials.load(credentials_path)

    assert refresh_calls == [""]
    assert refreshed.token == "fresh-token"
    assert persisted.token == "fresh-token"
