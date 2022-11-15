import platform
import asyncio

import pytest
import pytest_asyncio
from aiohttp import ClientSession

from aiosteampy import SteamClient

from .data import CREDENTIALS, UA


@pytest.fixture(scope="session")
def event_loop():
    """Prevent warning on Windows"""
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    # loop.close() # don't know why but this throws many warnings about destroying pending tasks


@pytest_asyncio.fixture(scope="session", autouse=False)
async def client() -> SteamClient:
    sess = ClientSession(headers={"User-Agent": UA}, raise_for_status=True)
    c = SteamClient(**CREDENTIALS, session=sess)
    await c.login()

    yield c

    await c.logout()
    await sess.close()
