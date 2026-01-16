import json

from pathlib import Path

from ..transport import Cookie
from ..id import SteamID

from .protobuf import EAuthTokenPlatformType
from .session import SteamLoginSession, STEAM_ACCESS_TOKEN_COOKIE, STEAM_REFRESH_TOKEN_COOKIE

LooseCookies = Cookie | list[dict] | Path

MOBILE_COOKIES = {"mobileClientVersion", "mobileClient"}
TOKENS_COOKIES = {STEAM_ACCESS_TOKEN_COOKIE, STEAM_REFRESH_TOKEN_COOKIE}


async def restore_from_cookies(session: SteamLoginSession, cookies: LooseCookies):
    """Load cookies into ``session`` and try to restore ``session`` if possible."""

    if isinstance(cookies, Path):
        with cookies.open("r") as f:
            cookies: list[dict] = json.load(f)

    steam_id: SteamID | None = None

    for cookie in cookies:
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

    if not await session.check_authenticated():
        refresh_token = session.refresh_token
        if refresh_token is None or refresh_token.expired:
            raise ValueError("Session cannot be restored from cookies as refresh token is not present or expired")

        await session.refresh_access_tokens()
