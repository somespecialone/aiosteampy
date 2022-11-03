import platform
import asyncio
from dataclasses import dataclass
from typing import Dict

import pytest
import pytest_asyncio
from aiohttp import ClientSession

from asyncsteampy.client import SteamClient

from .data import CREDENTIALS, HEADERS


@dataclass
class Credentials:
    api_key: str
    login: str
    password: str

    steam_guard: Dict[str, str]

    # proxy_addr: str


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


@pytest_asyncio.fixture(scope="session", autouse=False)
async def client(credentials) -> SteamClient:
    client = SteamClient(
        credentials.login,
        credentials.password,
        credentials.steam_guard,
        api_key=credentials.api_key,
        session=ClientSession(headers=HEADERS),
    )
    await client.login()

    yield client

    await client.close(logout=True)
