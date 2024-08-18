"""
Helper functions to restore/load, dump SteamClient client and components,
decorators to check instance attributes.
"""

from typing import TYPE_CHECKING

try:
    from aiohttp_socks import ProxyConnector
except ImportError:
    ProxyConnector = None

from .utils import JSONABLE_COOKIE_JAR, update_session_cookies, attribute_required

if TYPE_CHECKING:
    from .client import SteamClientBase

__all__ = (
    "restore_from_cookies",
    "currency_required",
    "identity_secret_required",
)


async def restore_from_cookies(cookies: JSONABLE_COOKIE_JAR, client: "SteamClientBase") -> bool:
    """
    Helper func. Restore client session from cookies. Login if session is not alive.
    Return `True` if cookies are valid and not expired.
    """

    update_session_cookies(client.session, cookies)

    if not (await client.is_session_alive()):  # session initiated here
        await client.login(init_session=False)
        return False
    else:
        return True


# TODO restore from object/dict, dump to object/dict


currency_required = attribute_required(
    "currency",
    "You must provide a currency to client or init data before use this method",
)

identity_secret_required = attribute_required(
    "_identity_secret",
    "You must provide identity secret to client before use this method",
)
