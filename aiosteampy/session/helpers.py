import json

from pathlib import Path

from ..transport import Cookie
from ..id import SteamID

from .protobuf import EAuthTokenPlatformType
from .session import SteamLoginSession, STEAM_ACCESS_TOKEN_COOKIE, STEAM_REFRESH_TOKEN_COOKIE

LooseCookies = list[Cookie] | list[dict] | Path

MOBILE_COOKIES = {"mobileClientVersion", "mobileClient"}
TOKENS_COOKIES = {STEAM_ACCESS_TOKEN_COOKIE, STEAM_REFRESH_TOKEN_COOKIE}


async def restore_from_cookies(session: SteamLoginSession, cookies: LooseCookies, ensure_auth: bool = False):
    """
    Load cookies into ``session`` and try to restore ``session`` if possible.

    :param session: ``SteamLoginSession`` instance.
    :param cookies: cookies to load.
    :param ensure_auth: whether to check authentication status after loading cookies.
    """

    if isinstance(cookies, Path):
        with cookies.open("r") as f:
            cookies: list[dict] = json.load(f)

    steam_id: SteamID | None = None

    for cookie in cookies:
        cookie: Cookie

        if isinstance(cookie, dict):
            cookie = Cookie.from_dict(cookie)

        # check if mobile app platform specific cookies are present
        if (
            session.platform is not EAuthTokenPlatformType.k_EAuthTokenPlatformType_MobileApp
            and cookie.name in MOBILE_COOKIES
        ):
            raise ValueError(
                "Cookies for mobile app platform type are present while session has non-mobile platform type"
            )

        # compare steam ids from cookies
        if cookie.name in TOKENS_COOKIES:
            try:
                cookie_steam_id = SteamID(cookie.value.split("%7C%7C")[0])
            except Exception as e:
                raise ValueError("Failed to parse SteamID from cookie") from e
            if steam_id is None:
                steam_id = cookie_steam_id
            elif steam_id != cookie_steam_id:
                raise ValueError("Cookies belong to different Steam accounts")

        session._transport.add_cookie(cookie)

    # set steam_id if not set yet
    if not session.steam_id:
        session._steam_id = steam_id

    if (session.access_token is None or session.access_token.expired) or (
        ensure_auth and not await session.check_authenticated()
    ):
        await session.refresh_access_tokens()
