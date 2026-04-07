import time
from uuid import uuid4

from ..webapi.client import SteamWebAPIClient
from ..webapi.services.twofactor import TwoFactorServiceClient


def generate_device_id() -> str:
    """Generate standardized mobile android device ID."""
    return f"android:{uuid4()}"


async def get_server_time_offset(*, service: TwoFactorServiceClient | None = None) -> int:
    """Helper method to get offset for the `local machine` from `server` time."""

    if service is None:
        service = TwoFactorServiceClient(SteamWebAPIClient())

    server_time = await service.query_time()

    return server_time.server_time - int(time.time())
