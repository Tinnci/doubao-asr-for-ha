"""Command line entry point."""

from __future__ import annotations

import argparse
import asyncio
import logging
from functools import partial
from pathlib import Path

from wyoming.server import AsyncServer, AsyncTcpServer

from .client import DoubaoAsrClient
from .device import CredentialStore
from .handler import DoubaoEventHandler, build_info


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", required=True, help="Wyoming URI, e.g. tcp://0.0.0.0:10300")
    parser.add_argument(
        "--credentials-file",
        default="/data/doubao_credentials.json",
        help="Path to persisted Doubao device credentials",
    )
    parser.add_argument(
        "--zeroconf",
        nargs="?",
        const="doubao-asr",
        help="Enable Home Assistant Wyoming discovery with optional name",
    )
    parser.add_argument(
        "--response-timeout-s",
        type=float,
        default=15.0,
        help="Timeout for Doubao websocket responses",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level))

    credential_store = CredentialStore(Path(args.credentials_file))
    doubao_client = DoubaoAsrClient(
        credentials_provider=credential_store.get,
        refresh_credentials=credential_store.refresh_token,
        response_timeout_s=args.response_timeout_s,
    )
    wyoming_info = build_info()
    server = AsyncServer.from_uri(args.uri)

    if args.zeroconf:
        if not isinstance(server, AsyncTcpServer):
            raise ValueError("zeroconf discovery requires a tcp:// URI")

        from wyoming.zeroconf import HomeAssistantZeroconf

        zeroconf = HomeAssistantZeroconf(
            name=args.zeroconf,
            host=server.host,
            port=server.port,
        )
        await zeroconf.register_server()

    logging.getLogger(__name__).info("Ready")
    await server.run(partial(DoubaoEventHandler, wyoming_info, doubao_client))


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        pass
