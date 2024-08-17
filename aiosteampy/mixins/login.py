import asyncio
from datetime import datetime, timedelta
from base64 import b64encode
from http.cookies import SimpleCookie
from time import time as time_time

from yarl import URL
from aiohttp import ClientResponseError
from aiohttp.client import _RequestContextManager
from rsa import PublicKey, encrypt

from ..constants import STEAM_URL, EResult
from ..typed import JWTToken
from ..exceptions import LoginError, EResultError
from ..utils import (
    generate_session_id,
    get_cookie_value_from_session,
    remove_cookie_from_session,
    format_time,
    decode_jwt,
)
from .http import SESSION_ID_COOKIE
from .guard import SteamGuardMixin


REFERER_HEADER = {"Referer": str(STEAM_URL.COMMUNITY) + "/"}
# https://github.com/DoctorMcKay/node-steam-session/blob/698469cdbad3e555dda10c81f580f1ee3960156f/src/helpers.ts#L17
API_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "sec-fetch-site": "cross-site",
    "sec-fetch-mode": "cors",
    "sec-fetch-dest": "empty",
}
STEAM_SECURE_COOKIE = "steamLoginSecure"


class LoginMixin(SteamGuardMixin):
    """
    Mixin with login logic methods.
    Depends on `SteamGuardMixin`.
    """

    __slots__ = ()

    # required instance attributes
    username: str
    _password: str
    _refresh_token: str | None

    # better to cache it somehow
    @property
    def access_token(self) -> str | None:
        """
        Encoded `JWT access token` as cookie value for `Steam Community` domain (https://steamcommunity.com).
        Can be used to make requests to a `Steam Web API`
        """

        return self.get_access_token(STEAM_URL.COMMUNITY)

    # https://github.com/DoctorMcKay/node-steam-session/blob/698469cdbad3e555dda10c81f580f1ee3960156f/src/LoginSession.ts#L231
    @access_token.setter
    def access_token(self, token: str | None):
        if token is None:
            remove_cookie_from_session(self.session, STEAM_URL.COMMUNITY, STEAM_SECURE_COOKIE)
        else:
            # accept only community token as project intent to be a "steam community" representation
            # TODO checks
            # https://github.com/DoctorMcKay/node-steam-session/blob/698469cdbad3e555dda10c81f580f1ee3960156f/src/LoginSession.ts#L231

            c = SimpleCookie()
            c[STEAM_SECURE_COOKIE] = token
            c[STEAM_SECURE_COOKIE]["path"] = "/"
            c[STEAM_SECURE_COOKIE]["domain"] = STEAM_URL.COMMUNITY.host
            c[STEAM_SECURE_COOKIE]["expires"] = format_time(datetime.now() + timedelta(days=365 * 5))
            c[STEAM_SECURE_COOKIE]["samesite"] = "None"
            c[STEAM_SECURE_COOKIE]["secure"] = True
            c[STEAM_SECURE_COOKIE]["httponly"] = True

            self.session.cookie_jar.update_cookies(cookies=c, response_url=STEAM_URL.COMMUNITY)

    @property
    def access_token_decoded(self) -> JWTToken | None:
        if token := self.access_token:
            return decode_jwt(token)

    @property
    def is_access_token_expired(self) -> bool:
        """If access token has expired. Also returns `True` if token is not yet set"""
        if token := self.access_token_decoded:
            return (token["exp"]) <= int(time_time())
        else:
            return True

    def get_access_token(self, domain: URL) -> str | None:
        """Get encoded `JWT access token` as cookie value for `Steam Domain`"""

        if token := get_cookie_value_from_session(self.session, domain, STEAM_SECURE_COOKIE):
            return token.split("%7C%7C")[1]  # ||

    @property
    def refresh_token(self) -> str | None:
        return self._refresh_token

    @refresh_token.setter
    def refresh_token(self, token: str | None):
        # TODO checks
        # https://github.com/DoctorMcKay/node-steam-session/blob/698469cdbad3e555dda10c81f580f1ee3960156f/src/LoginSession.ts#L280
        self._refresh_token = token

    @property
    def refresh_token_decoded(self) -> JWTToken | None:
        if token := self._refresh_token:
            return decode_jwt(token)

    @property
    def is_refresh_token_expired(self) -> bool:
        """If refresh token has expired. Also returns `True` if token is not yet set"""
        if token := self.refresh_token_decoded:
            return (token["exp"]) <= int(time_time())
        else:
            return True

    async def is_session_alive(self, domain=STEAM_URL.COMMUNITY) -> bool:
        """Check if session is alive for `Steam` domain"""

        # we can also check https://steamcommunity.com/my for redirect to profile page as indicator
        # https://github.com/DoctorMcKay/node-steamcommunity/blob/1067d4572ee9d467e8f686951901c51028c5c995/index.js#L290

        r = await self.session.get(domain)
        rt = await r.text()
        return self.username in rt

    async def login(self, init_session=True):
        """
        Perform login for main `Steam` domains:
            * https://steamcommunity.com
            * https://store.steampowered.com
            * https://help.steampowered.com

        :param init_session: init session before start auth process.
            Set this to False if you already make requests to `Steam` from current client
        :raises EResultError: when failed to obtain rsa key, update steam guard code
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
        # there is no guarantee that first completed transfer will be to community and
        # steamLoginSecure cookie will be not present yet, so better to wait until all transfers completed,
        # and we can be sure that login process to community domain is done
        # moreover, steam domains (store, community, help, tv, login) has own access tokens
        await asyncio.wait(transfers, return_when=asyncio.ALL_COMPLETED)

        # Transfers exception check ?

    async def _perform_transfer(self, data: dict, steam_id: str | int = None):
        """Perform a transfer of params and tokens to steam login endpoints"""

        r = await self.session.post(data["url"], data={**data["params"], "steamID": steam_id or self.steam_id})
        # https://github.com/DoctorMcKay/node-steam-session/blob/698469cdbad3e555dda10c81f580f1ee3960156f/src/LoginSession.ts#L864
        # make sure that `steamLoginSecure` cookie is present
        if not r.cookies.get("steamLoginSecure"):
            raise LoginError("'steamLoginSecure' cookie is not present in result", r.cookies)

        # ensure that sessionid cookie is presented
        # https://github.com/DoctorMcKay/node-steam-session/blob/698469cdbad3e555dda10c81f580f1ee3960156f/src/LoginSession.ts#L872-L873
        if not r.cookies.get(SESSION_ID_COOKIE):
            session_id = generate_session_id()

            c = SimpleCookie()
            c[SESSION_ID_COOKIE] = session_id
            c[SESSION_ID_COOKIE]["path"] = "/"
            c[SESSION_ID_COOKIE]["domain"] = r.real_url.host
            c[SESSION_ID_COOKIE]["samesite"] = "None"
            c[SESSION_ID_COOKIE]["secure"] = True

            self.session.cookie_jar.update_cookies(cookies=c, response_url=STEAM_URL.COMMUNITY)

    async def _begin_auth_session_with_credentials(self) -> dict:
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

    async def _update_auth_session_with_steam_guard_code(self, session_data: dict):
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
        except ClientResponseError as e:
            raise LoginError("Error updating steam guard code") from e

    async def _poll_auth_session_status(self, session_resp: dict):
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
            raise LoginError("Error polling auth session status", rj)

        self._refresh_token = rj["response"]["refresh_token"]
        # access token already presented in cookie, btw this token has "web" aud unlike others
        # self.access_token = rj["response"]["access_token"]

    async def _finalize_login(self) -> dict:
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
            raise LoginError("Get error response when performing login finalization", rj)
        elif not rj or not rj.get("transfer_info"):
            raise LoginError("Malformed login response", rj)

        return rj

    async def _get_rsa_key(self) -> tuple[PublicKey, int]:
        r = await self.session.get(
            STEAM_URL.API.IAuthService.GetPasswordRSAPublicKey,
            params={"account_name": self.username},
        )
        rj = await r.json()
        try:
            rsa_mod = int(rj["response"]["publickey_mod"], 16)
            rsa_exp = int(rj["response"]["publickey_exp"], 16)
            rsa_timestamp = int(rj["response"]["timestamp"])

            return PublicKey(rsa_mod, rsa_exp), rsa_timestamp

        except KeyError:
            raise LoginError("Could not obtain rsa-key", rj)

    def logout(self) -> _RequestContextManager:
        return self.session.post(
            STEAM_URL.COMMUNITY / "login/logout/",
            data={**REFERER_HEADER, "sessionid": self.session_id},
            allow_redirects=False,
        )

    async def get_store_access_token_from_steam(self) -> str | None:
        """
        Fetch access token for `Steam Store` domain (https://store.steampowered.com/).
        Return token only if you logged in store domain.

        :return: raw token string or `None`
        :raises EResultError: for ordinary reasons
        """

        r = await self.session.get(STEAM_URL.STORE / "pointssummary/ajaxgetasyncconfig")
        rj = await r.json()
        success = EResult(rj.get("success"))
        if success is not EResult.OK:
            raise EResultError("Failed to fetch store access token", success, rj)

        return rj["data"]["webapi_token"] if rj["data"] else None

    # async def refresh_access_token(self) -> str:
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
    #         raise EResultError("Can't renew access token.", rj)
    #
    #     return self._access_token
