import platform
import asyncio
import json
from typing import TYPE_CHECKING
from pathlib import Path

import pytest
import pytest_asyncio
from aiohttp import ClientSession

from aiosteampy import SteamClient
from aiosteampy.models import EconItem
from aiosteampy.utils import restore_from_cookies


from data import CREDENTIALS, UA, GAME, ASSET_ID, TEST_COOKIE_FILE_PATH

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
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    # loop.close() # don't know why but this throws many warnings about destroying pending tasks


@pytest.fixture(scope="session")
async def client():
    sess = ClientSession(headers={"User-Agent": UA}, raise_for_status=True)
    c = SteamClient(**CREDENTIALS, session=sess)
    cookie_path = Path(TEST_COOKIE_FILE_PATH)
    if cookie_path.is_file():
        with cookie_path.open("r") as f:
            cookies = json.load(f)
        await restore_from_cookies(cookies, c)
    else:
        await c.login()

    yield c

    await c.logout()
    await sess.close()


@pytest_asyncio.fixture(scope="session")
async def inventory(client):
    client: SteamClient

    def predicate(i: EconItem):
        # get all marketable items and passed asset id if possible
        return i.class_.marketable and (i.id == ASSET_ID) if ASSET_ID else True

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
