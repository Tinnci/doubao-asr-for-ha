"""Doubao ASR protocol constants.

Values mirror the public reference implementation in EvanDbg/doubao-ime-win.
"""

REGISTER_URL = "https://log.snssdk.com/service/2/device_register/"
SETTINGS_URL = "https://is.snssdk.com/service/settings/v3/"
WEBSOCKET_URL = "wss://frontier-audio-ime-ws.doubao.com/ocean/api/v1/ws"

AID = 401734
APP_NAME = "oime"
VERSION_CODE = 100102018
VERSION_NAME = "1.1.2"
CHANNEL = "official"
PACKAGE = "com.bytedance.android.doubaoime"

DEVICE_PLATFORM = "android"
OS = "android"
OS_API = "34"
OS_VERSION = "16"
DEVICE_TYPE = "Pixel 7 Pro"
DEVICE_BRAND = "google"
DEVICE_MODEL = "Pixel 7 Pro"
RESOLUTION = "1080*2400"
DPI = "420"
LANGUAGE = "zh"
TIMEZONE = 8
ACCESS = "wifi"
ROM = "UP1A.231005.007"
ROM_VERSION = "UP1A.231005.007"

USER_AGENT = (
    "com.bytedance.android.doubaoime/100102018 "
    "(Linux; U; Android 16; en_US; Pixel 7 Pro; "
    "Build/BP2A.250605.031.A2; Cronet/TTNetVersion:94cf429a 2025-11-17 "
    "QuicVersion:1f89f732 2025-05-08)"
)

SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2
FRAME_DURATION_MS = 20
SERVICE_NAME = "ASR"
