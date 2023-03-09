import platform
import asyncio
import json
import os
from typing import TYPE_CHECKING
from pathlib import Path

import pytest
import pytest_asyncio
from aiohttp import ClientSession
from dotenv import load_dotenv

from aiosteampy import SteamClient
from aiosteampy.models import EconItem
from aiosteampy.utils import restore_from_cookies, get_jsonable_cookies

# env variables
# required
# TEST_USERNAME
# TEST_PASSWORD
# TEST_STEAMID
# TEST_SHARED_SECRET
# TEST_IDENTITY_SECRET

# optional
# TEST_GAME_APP_ID
# TEST_GAME_CONTEXT_ID
# TEST_ASSET_ID
# TEST_COOKIE_FILE_PATH

load_dotenv()

TEST_COOKIE_FILE_PATH = os.getenv("TEST_COOKIE_FILE_PATH", "")

CREDENTIALS = {
    "username": os.getenv("TEST_USERNAME", ""),
    "password": os.getenv("TEST_PASSWORD", ""),
    "steam_id": int(os.getenv("TEST_STEAMID", 0)),
    "shared_secret": os.getenv("TEST_SHARED_SECRET", ""),
    "identity_secret": os.getenv("TEST_IDENTITY_SECRET", ""),
}

GAME = (int(os.getenv("TEST_GAME_APP_ID", 730)), int(os.getenv("TEST_GAME_CONTEXT_ID", 2)))  # def CSGO
ASSET_ID = int(os.getenv("TEST_ASSET_ID", 0))

UA = "Mozilla/5.0 (X11; CrOS x86_64 8172.45.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.64 Safari/537.36"

# https://docs.pytest.org/en/latest/example/simple.html#incremental-testing-test-steps
_test_failed_incremental: dict[str, dict[tuple[int, ...], str]] = {}


def pytest_runtest_makereport(item, call):
    if "incremental" in item.keywords:
        # incremental marker is used
        if call.excinfo is not None:
            # the test has failed
            # retrieve the class name of the test
            cls_name = str(item.cls)
            # retrieve the index of the test (if parametrize is used in combination with incremental)
            parametrize_index = tuple(item.callspec.indices.values()) if hasattr(item, "callspec") else ()
            # retrieve the name of the test function
            test_name = item.originalname or item.name
            # store in _test_failed_incremental the original name of the failed test
            _test_failed_incremental.setdefault(cls_name, {}).setdefault(parametrize_index, test_name)


def pytest_runtest_setup(item):
    if "incremental" in item.keywords:
        # retrieve the class name of the test
        cls_name = str(item.cls)
        # check if a previous test has failed for this class
        if cls_name in _test_failed_incremental:
            # retrieve the index of the test (if parametrize is used in combination with incremental)
            parametrize_index = tuple(item.callspec.indices.values()) if hasattr(item, "callspec") else ()
            # retrieve the name of the first test function to fail for this class name and index
            test_name = _test_failed_incremental[cls_name].get(parametrize_index, None)
            # if name found, test has failed for the combination of class name & test name
            if test_name is not None:
                pytest.xfail(f"previous test failed ({test_name})")


@pytest.fixture(scope="session")
def event_loop():
    # Prevent warning on Windows
    platform.system() == "Windows" and asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    # loop.close() # don't know why but this throws many warnings about destroying pending tasks


@pytest.fixture(scope="session")
async def client():
    sess = ClientSession(headers={"User-Agent": UA}, raise_for_status=True)
    c = SteamClient(**CREDENTIALS, session=sess)
    cookie_file = Path(TEST_COOKIE_FILE_PATH)
    try:
        if cookie_file.is_file():
            with cookie_file.open("r") as f:
                cookies = json.load(f)
            await restore_from_cookies(cookies, c)
        else:
            await c.login()

        yield c

    finally:
        if cookie_file.is_file():
            with cookie_file.open("w") as f:
                json.dump(get_jsonable_cookies(sess), f, indent=2)
        else:
            await c.logout()

        await sess.close()


@pytest_asyncio.fixture(scope="session")
async def inventory(client):
    client: SteamClient

    def predicate(i: EconItem):
        # get all marketable items and passed asset id if possible
        return i.marketable and (i.asset_id == ASSET_ID) if ASSET_ID else True

    inv = await client.get_inventory(GAME, predicate=predicate)
    assert inv

    return inv


@pytest.fixture(scope="session")
def context() -> dict[str, ...]:
    return {}


if TYPE_CHECKING:  # for PyCharm type hints

    @pytest.fixture()
    def inventory() -> list[EconItem]:
        ...
