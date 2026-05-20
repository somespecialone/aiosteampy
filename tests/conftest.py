import pytest
import pytest_asyncio
from yarl import URL


@pytest.fixture(params=["aiohttp", "wreq"])
def transport_type(request):
    """Parameterized fixture to test both transport implementations."""
    return request.param


@pytest_asyncio.fixture
async def transport(transport_type):
    """
    Factory fixture that creates transport instances for both implementations.
    Automatically handles cleanup.
    """
    if transport_type == "aiohttp":
        from aiosteampy.transport import AiohttpTransport

        t = AiohttpTransport()
    else:  # wreq
        from aiosteampy.transport import WreqTransport

        t = WreqTransport()

    yield t

    # Cleanup
    await t.close()


@pytest.fixture
def test_url():
    """Base URL for test requests."""
    return URL("https://api.apify.com/v2/browser-info")


@pytest.fixture
def steam_login_url():
    """Steam login URL for cookie testing."""
    return URL("https://steamcommunity.com/login")


@pytest.fixture
def sample_cookie_data(steam_login_url):
    """Sample cookie data for testing."""
    return {
        "name": "test_cookie",
        "value": "test_value",
        "domain": steam_login_url.host,
        "path": steam_login_url.path,
        "expires": None,
        "secure": True,
        "http_only": False,
        "same_site": "Lax",
    }
