import platform
import asyncio
from dataclasses import dataclass

import pytest
from aiohttp import ClientSession
from aiohttp_socks import ProxyConnector

from asyncsteampy.client import SteamClient

from .data import CREDENTIALS, HEADERS


@dataclass
class Credentials:
    api_key: str
    login: str
    password: str

    steam_guard: dict[str, str]

    proxy_addr: str


@pytest.fixture(scope="session")
def event_loop():
    """Prevent warning on Windows"""
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    # loop.close() # don't know why but this throws many warnings about destroying pending tasks


@pytest.fixture(scope="session")
def credentials() -> Credentials:
    return Credentials(**CREDENTIALS)


@pytest.fixture(scope="session", autouse=False)
async def client(credentials) -> SteamClient:
    client = SteamClient(
        credentials.api_key,
        session=ClientSession(connector=ProxyConnector.from_url(credentials.proxy_addr), headers=HEADERS),
    )
    await client.login(credentials.login, credentials.password, credentials.steam_guard)

    yield client

    await client.close()
