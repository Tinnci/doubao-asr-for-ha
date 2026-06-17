"""Device registration and ASR token management."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import aiohttp

from .constants import (
    ACCESS,
    AID,
    APP_NAME,
    CHANNEL,
    DEVICE_BRAND,
    DEVICE_MODEL,
    DEVICE_PLATFORM,
    DEVICE_TYPE,
    DPI,
    LANGUAGE,
    OS,
    OS_API,
    OS_VERSION,
    PACKAGE,
    REGISTER_URL,
    RESOLUTION,
    ROM,
    ROM_VERSION,
    SETTINGS_URL,
    TIMEZONE,
    USER_AGENT,
    VERSION_CODE,
    VERSION_NAME,
)


@dataclass
class DeviceCredentials:
    device_id: str
    install_id: str
    cdid: str
    openudid: str
    clientudid: str
    token: str

    @classmethod
    def generated(cls) -> DeviceCredentials:
        return cls(
            device_id="",
            install_id="",
            cdid=str(uuid.uuid4()),
            openudid=uuid.uuid4().hex[:16],
            clientudid=str(uuid.uuid4()),
            token="",
        )

    @property
    def is_complete(self) -> bool:
        return bool(self.device_id and self.token)

    @classmethod
    def load(cls, path: Path) -> DeviceCredentials:
        return cls(**json.loads(path.read_text(encoding="utf-8")))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


class CredentialStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._credentials: DeviceCredentials | None = None

    async def get(self) -> DeviceCredentials:
        if self._credentials is None:
            self._credentials = (
                DeviceCredentials.load(self.path)
                if self.path.exists()
                else DeviceCredentials.generated()
            )

        if not self._credentials.device_id:
            await register_device(self._credentials)
            self._credentials.save(self.path)

        if not self._credentials.token:
            await get_asr_token(self._credentials)
            self._credentials.save(self.path)

        return self._credentials

    async def refresh_token(self) -> DeviceCredentials:
        """Clear the cached ASR token and fetch a fresh one."""
        if self._credentials is None:
            self._credentials = (
                DeviceCredentials.load(self.path)
                if self.path.exists()
                else DeviceCredentials.generated()
            )

        if not self._credentials.device_id:
            await register_device(self._credentials)

        self._credentials.token = ""
        await get_asr_token(self._credentials)
        self._credentials.save(self.path)
        return self._credentials


async def register_device(credentials: DeviceCredentials) -> None:
    header = _device_register_header(credentials)
    body = {
        "magic_tag": "ss_app_log",
        "header": header,
        "_gen_time": current_time_ms(),
    }

    async with (
        aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session,
        session.post(
            REGISTER_URL,
            params=_common_params(credentials),
            json=body,
        ) as response,
    ):
        response.raise_for_status()
        data = await response.json()

    device_id = int(data.get("device_id") or 0)
    install_id = int(data.get("install_id") or 0)
    if device_id <= 0:
        raise RuntimeError("device registration returned invalid device_id")

    credentials.device_id = str(device_id)
    credentials.install_id = str(install_id)


async def get_asr_token(credentials: DeviceCredentials) -> None:
    body = "body=null"
    params = _common_params(credentials)
    params["device_id"] = credentials.device_id

    x_ss_stub = hashlib.md5(body.encode(), usedforsecurity=False).hexdigest().upper()
    async with (
        aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session,
        session.post(
            SETTINGS_URL,
            params=params,
            data=body,
            headers={"x-ss-stub": x_ss_stub},
        ) as response,
    ):
        response.raise_for_status()
        data = await response.json()

    token = (
        data.get("data", {})
        .get("settings", {})
        .get("asr_config", {})
        .get("app_key", "")
    )
    if not token:
        raise RuntimeError("settings response did not contain asr_config.app_key")

    credentials.token = token


def current_time_ms() -> int:
    return int(time.time() * 1000)


def _common_params(credentials: DeviceCredentials) -> dict[str, str]:
    return {
        "device_platform": DEVICE_PLATFORM,
        "os": OS,
        "ssmix": "a",
        "_rticket": str(current_time_ms()),
        "cdid": credentials.cdid,
        "channel": CHANNEL,
        "aid": str(AID),
        "app_name": APP_NAME,
        "version_code": str(VERSION_CODE),
        "version_name": VERSION_NAME,
        "manifest_version_code": str(VERSION_CODE),
        "update_version_code": str(VERSION_CODE),
        "resolution": RESOLUTION,
        "dpi": DPI,
        "device_type": DEVICE_TYPE,
        "device_brand": DEVICE_BRAND,
        "language": LANGUAGE,
        "os_api": OS_API,
        "os_version": OS_VERSION,
        "ac": ACCESS,
    }


def _device_register_header(credentials: DeviceCredentials) -> dict[str, Any]:
    return {
        "device_id": 0,
        "install_id": 0,
        "aid": AID,
        "app_name": APP_NAME,
        "version_code": VERSION_CODE,
        "version_name": VERSION_NAME,
        "manifest_version_code": VERSION_CODE,
        "update_version_code": VERSION_CODE,
        "channel": CHANNEL,
        "package": PACKAGE,
        "device_platform": DEVICE_PLATFORM,
        "os": OS,
        "os_api": OS_API,
        "os_version": OS_VERSION,
        "device_type": DEVICE_TYPE,
        "device_brand": DEVICE_BRAND,
        "device_model": DEVICE_MODEL,
        "resolution": RESOLUTION,
        "dpi": DPI,
        "language": LANGUAGE,
        "timezone": TIMEZONE,
        "access": ACCESS,
        "rom": ROM,
        "rom_version": ROM_VERSION,
        "openudid": credentials.openudid,
        "clientudid": credentials.clientudid,
        "cdid": credentials.cdid,
        "region": "CN",
        "tz_name": "Asia/Shanghai",
        "tz_offset": 28800,
        "sim_region": "cn",
        "carrier_region": "cn",
        "cpu_abi": "arm64-v8a",
        "build_serial": "unknown",
        "not_request_sender": 0,
        "sig_hash": "",
        "google_aid": "",
        "mc": "",
        "serial_number": "",
    }
