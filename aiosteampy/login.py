import asyncio
from typing import TYPE_CHECKING
from http.cookies import SimpleCookie
from base64 import b64encode

from aiohttp import ClientResponseError
from rsa import PublicKey, encrypt

from .exceptions import LoginError, ApiError
from .constants import STEAM_URL
from .utils import get_cookie_value_from_session, generate_session_id

if TYPE_CHECKING:
    from .client import SteamCommunityMixin

__all__ = ("LoginMixin", "REFERER_HEADER")

REFERER_HEADER = {"Referer": str(STEAM_URL.COMMUNITY) + "/"}
API_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "sec-fetch-site": "cross-site",
    "sec-fetch-mode": "cors",
    "sec-fetch-dest": "empty",
}


class LoginMixin:
    """Mixin with login logic methods."""

    __slots__ = ()

    _is_logged: bool
    _refresh_token: str | None
    # Almost useless, but ...
    # https://github.com/DoctorMcKay/node-steam-session/blob/698469cdbad3e555dda10c81f580f1ee3960156f/src/LoginSession.ts#L230
    _access_token: str | None

    def __init__(self, *args, refresh_token: str = None, access_token: str = None, **kwargs):
        self._is_logged = False
        self._refresh_token = refresh_token
        self._access_token = access_token

        super().__init__(*args, **kwargs)

    @property
    def is_logged(self) -> bool:
        return self._is_logged

    @property
    def session_id(self: "SteamCommunityMixin") -> str | None:
        return get_cookie_value_from_session(self.session, STEAM_URL.COMMUNITY, "sessionid")

    async def is_session_alive(self: "SteamCommunityMixin") -> bool:
        r = await self.session.get(STEAM_URL.COMMUNITY)
        rt = await r.text()
        return self.username.lower() in rt.lower()

    async def login(self: "SteamCommunityMixin", *, init_data=True, init_session=True):
        """
        Perform login.
        Populate `api_key`, `trade_token`, `wallet_country`, `wallet_currency` fields if it is required.

        :param init_data: fetch initial required data (api key, trade token, wallet_currency/wallet_country)
        :param init_session: init session before start auth process.
            Set this to False if you already make requests to steam from current client.
        :raises ApiError: when failed to obtain rsa key, update steam guard code
        :raises LoginError: other login process errors
        """

        # https://github.com/bukson/steampy/blob/fe0433c8cf7020318cfbbc22e79028a7576374ee/steampy/login.py#L67
        # https://github.com/DoctorMcKay/node-steam-session/blob/698469cdbad3e555dda10c81f580f1ee3960156f/examples/login-to-web-with-2fa.ts#L13
        init_session and await self.session.get(STEAM_URL.COMMUNITY)

        session_data = await self._begin_auth_session_with_credentials()
        await self._update_auth_session_with_steam_guard_code(session_data)
        await self._poll_auth_session_status(session_data)
        fin_data = await self._finalize_login()  # there can be retrieved steam id

        # https://github.com/DoctorMcKay/node-steam-session/blob/64463d7468c1c860afb80164b8c5831e629f657f/src/LoginSession.ts#L845
        loop = asyncio.get_event_loop()
        transfers = [
            loop.create_task(self._perform_transfer(d, fin_data["steamID"])) for d in fin_data["transfer_info"]
        ]
        done, _ = await asyncio.wait(transfers, return_when=asyncio.FIRST_COMPLETED)

        # Transfers exception check ?

        self._set_web_cookies(done.pop().result())

        init_data and await self._init_data()

        self._is_logged = True

    async def _perform_transfer(self: "SteamCommunityMixin", data: dict, steam_id: str | int = None) -> SimpleCookie:
        """
        Perform a transfer of params and tokens to steam login endpoints.
        Similar behavior to arrow function from link below.

        .. seealso:: https://github.com/DoctorMcKay/node-steam-session/blob/698469cdbad3e555dda10c81f580f1ee3960156f/src/LoginSession.ts#L845-L868
        """

        r = await self.session.post(data["url"], data={**data["params"], "steamID": steam_id or self.steam_id})
        # https://github.com/DoctorMcKay/node-steam-session/blob/698469cdbad3e555dda10c81f580f1ee3960156f/src/LoginSession.ts#L864
        # make sure that `steamLoginSecure` cookie is present
        if not r.cookies.get("steamLoginSecure"):
            raise ApiError("No `steamLoginSecure` cookie in result.")

        return r.cookies

    def _set_web_cookies(self: "SteamCommunityMixin", cookie: SimpleCookie):
        """
        Set web cookies to session for main steam urls.

        .. seealso:: https://github.com/DoctorMcKay/node-steamcommunity/blob/7c564c1453a5ac413d9312b8cf8fe86e7578b309/index.js#L153-L175
        """

        # ensure that sessionid cookie is presented
        # https://github.com/DoctorMcKay/node-steam-session/blob/698469cdbad3e555dda10c81f580f1ee3960156f/src/LoginSession.ts#L872-L873
        if not cookie.get("sessionid"):
            cookie["sessionid"] = generate_session_id()

        for k, morsel in cookie.items():
            for url in (STEAM_URL.STORE, STEAM_URL.COMMUNITY, STEAM_URL.HELP):
                c = SimpleCookie()
                m = morsel.copy()
                m["domain"] = url.host
                c[k] = m
                self.session.cookie_jar.update_cookies(c, response_url=url)

    async def _begin_auth_session_with_credentials(self: "SteamCommunityMixin") -> dict:
        pub_key, ts = await self._get_rsa_key()
        # for web browser
        # https://github.com/DoctorMcKay/node-steam-session/blob/64463d7468c1c860afb80164b8c5831e629f657f/src/AuthenticationClient.ts#L390
        # https://github.com/DoctorMcKay/node-steam-session/blob/64463d7468c1c860afb80164b8c5831e629f657f/src/enums-steam/EAuthTokenPlatformType.ts
        platform_data = {
            "website_id": "Community",
            "device_details": {
                "device_friendly_name": self.user_agent,
                "platform_type": 2,
            },
        }

        data = {
            "account_name": self.username,
            "encrypted_password": b64encode(encrypt(self._password.encode("utf-8"), pub_key)).decode(),
            "encryption_timestamp": ts,
            "remember_login": "true",
            "persistence": "1",
            **platform_data,
        }
        r = await self.session.post(
            STEAM_URL.API.IAuthService.BeginAuthSessionViaCredentials,
            data=data,
            headers=REFERER_HEADER,
        )
        return await r.json()

    async def _update_auth_session_with_steam_guard_code(self: "SteamCommunityMixin", session_data: dict):
        # Doesn't check allowed confirmations, but it's probably not needed
        # as steam accounts suited for trading must have a steam guard and device code.

        # https://github.com/DoctorMcKay/node-steam-session/blob/64463d7468c1c860afb80164b8c5831e629f657f/src/LoginSession.ts#L735
        # https://github.com/DoctorMcKay/node-steam-session/blob/64463d7468c1c860afb80164b8c5831e629f657f/src/enums-steam/EAuthSessionGuardType.ts
        data = {
            "client_id": session_data["response"]["client_id"],
            "steamid": session_data["response"]["steamid"],
            "code_type": 3,
            "code": self.two_factor_code,
        }

        try:
            await self.session.post(
                STEAM_URL.API.IAuthService.UpdateAuthSessionWithSteamGuardCode,
                data=data,
                headers=REFERER_HEADER,
            )
        except ClientResponseError:
            raise ApiError("Error updating steam guard code")

    async def _poll_auth_session_status(self: "SteamCommunityMixin", session_resp: dict):
        data = {
            "client_id": session_resp["response"]["client_id"],
            "request_id": session_resp["response"]["request_id"],
        }
        r = await self.session.post(
            STEAM_URL.API.IAuthService.PollAuthSessionStatus,
            data=data,
            headers=REFERER_HEADER,
        )
        rj = await r.json()
        if rj.get("response", {"had_remote_interaction": True})["had_remote_interaction"]:
            raise ApiError("Error polling auth session status.", rj)

        self._refresh_token = rj["response"]["refresh_token"]
        self._access_token = rj["response"]["access_token"]

    async def _finalize_login(self: "SteamCommunityMixin") -> dict:
        data = {
            "nonce": self._refresh_token,
            "sessionid": self.session_id,
            "redir": str(STEAM_URL.COMMUNITY / "login/home/?goto="),
        }
        r = await self.session.post(
            STEAM_URL.LOGIN / "jwt/finalizelogin",
            data=data,
            headers={**API_HEADERS, **REFERER_HEADER},
        )
        rj: dict = await r.json()

        if rj and rj.get("error"):
            raise LoginError("Get error response when performing login finalization.", rj)
        elif not rj or not rj.get("transfer_info"):
            raise LoginError("Malformed login response.", rj)

        return rj

    async def _get_rsa_key(self: "SteamCommunityMixin") -> tuple[PublicKey, int]:
        r = await self.session.get(STEAM_URL.API.IAuthService.GetPasswordRSAPublicKey % {"account_name": self.username})
        rj = await r.json()
        try:
            rsa_mod = int(rj["response"]["publickey_mod"], 16)
            rsa_exp = int(rj["response"]["publickey_exp"], 16)
            rsa_timestamp = int(rj["response"]["timestamp"])

            return PublicKey(rsa_mod, rsa_exp), rsa_timestamp

        except KeyError:
            raise ApiError("Could not obtain rsa-key.", rj)

    async def logout(self: "SteamCommunityMixin") -> None:
        await self.session.post(
            STEAM_URL.COMMUNITY / "login/logout/",
            data={**REFERER_HEADER, "sessionid": self.session_id},
        )
        self._is_logged = False

    # async def refresh_access_token(self: "SteamCommunityMixin") -> str:
    #     """"""
    #
    #     # TODO this
    #     r = await self.session.post(
    #         STEAM_URL.API.IAuthService.GenerateAccessTokenForApp,
    #         data={"refresh_token": self._refresh_token, "steamid": self.steam_id},
    #         headers={**API_HEADERS, **REFERER_HEADER},
    #     )
    #     rj = await r.json()
    #
    #     try:
    #         self._access_token = rj["response"]["access_token"]
    #     except KeyError:
    #         raise ApiError("Can't renew access token.", rj)
    #
    #     return self._access_token
