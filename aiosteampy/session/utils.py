import asyncio

from typing import Iterable, Coroutine
from base64 import b64encode
from secrets import token_hex

from yarl import URL


def parse_qr_challenge_url(url: URL | str) -> tuple[int, int]:
    """Parse QR challenge url. Return `version` and `client id`."""

    version, client_id = URL(url).path.split("/")
    return int(version), int(client_id)


# not needed anymore, but left it here for convenience
def generate_session_id() -> str:
    """Generate `Steam` like session id."""

    return token_hex(12)


async def wait_coroutines(coros: Iterable[Coroutine]):
    """Wait for coroutines to finish, cancel pending if error occurs."""

    loop = asyncio.get_running_loop()
    done, pending = await asyncio.wait([loop.create_task(c) for c in coros], return_when=asyncio.FIRST_EXCEPTION)
    for p in pending:  # cancel pending if error occurs
        p.cancel()

    for f in done:  # and raise first exception from tasks
        if exc := f.exception():
            raise exc
