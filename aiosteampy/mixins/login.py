import asyncio
from datetime import datetime, timedelta
from base64 import b64encode
from time import time as time_time

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
    add_cookie_to_session,
)
from .http import SESSION_ID_COOKIE
from .guard import SteamGuardMixin

# Import protobuf for new Steam auth API
try:
    from .. import auth_pb2

    PROTOBUF_AVAILABLE = True
except ImportError:
    PROTOBUF_AVAILABLE = False


REFERER_HEADER = {"Referer": str(STEAM_URL.COMMUNITY) + "/"}
# https://github.com/DoctorMcKay/node-steam-session/blob/698469cdbad3e555dda10c81f580f1ee3960156f/src/helpers.ts#L17
API_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "sec-fetch-site": "cross-site",
    "sec-fetch-mode": "cors",
    "sec-fetch-dest": "empty",
}
STEAM_SECURE_COOKIE = "steamLoginSecure"
STEAM_REFRESH_COOKIE = "steamRefresh_steam"


class LoginMixin(SteamGuardMixin):
    """
    Mixin with login logic methods.
    Depends on `SteamGuardMixin`.
    """

    __slots__ = ()

    # required instance attributes
    username: str
    _password: str

    # better to cache it somehow
    @property
    def access_token(self) -> str | None:
        """
        Encoded `JWT access token` as cookie value for `Steam Community` domain (https://steamcommunity.com).
        Can be used to make requests to a `Steam Web API`
        """

        return self.get_access_token()

    @access_token.setter
    def access_token(self, token: str | None):
        self.set_access_token(token)

    @property
    def access_token_decoded(self) -> JWTToken | None:
        if token := self.access_token:
            return decode_jwt(token)

    @property
    def is_access_token_expired(self) -> bool:
        """If access token has expired. Also returns `True` if token is not yet set"""
        if token := self.access_token_decoded:
            return token["exp"] <= int(time_time())  # truncate fractions
        else:
            return True

    def get_access_token(self, domain=STEAM_URL.COMMUNITY) -> str | None:
        """Get encoded `JWT access token` as cookie value for `Steam Domain`"""

        if token := get_cookie_value_from_session(self.session, domain, STEAM_SECURE_COOKIE):
            return token.split("%7C%7C")[1]  # ||

    def set_access_token(self, token: str | None, domain=STEAM_URL.COMMUNITY):
        if token is None:
            remove_cookie_from_session(self.session, domain, STEAM_SECURE_COOKIE)
        else:
            # checks from
            # https://github.com/DoctorMcKay/node-steam-session/blob/811dadd2bfcc11de7861fff7442cb4a44ab61955/src/LoginSession.ts#L232

            decoded = decode_jwt(token)

            if "derive" in decoded["aud"]:
                raise ValueError("Provided token is a refresh token, not an access token!")
            if int(decoded["sub"]) != self.steam_id:
                raise ValueError(f"Provided token belongs to a different account [{decoded['sub']}]")

            # aud must contain "web:[domain]" entries, like "web:community" for community and this better be checked

            if "%7C%7C" not in token:  # raw token
                token = decoded["sub"] + "%7C%7C" + token

            add_cookie_to_session(
                self.session,
                STEAM_URL.COMMUNITY,
                STEAM_SECURE_COOKIE,
                token,
                # 5 years as steam default for access token
                expires=format_time(datetime.now() + timedelta(days=365 * 5)),
                samesite="None",
                secure=True,
                httponly=True,
            )

    @property
    def refresh_token(self) -> str | None:
        return self.get_refresh_token()

    @refresh_token.setter
    def refresh_token(self, token: str | None):
        self.set_refresh_token(token)

    @property
    def refresh_token_decoded(self) -> JWTToken | None:
        if token := self.refresh_token:
            return decode_jwt(token)

    @property
    def is_refresh_token_expired(self) -> bool:
        """If refresh token has expired. Also returns `True` if token is not yet set"""
        if token := self.refresh_token_decoded:
            return token["exp"] <= int(time_time())  # truncate fractions
        else:
            return True

    def get_refresh_token(self) -> str | None:
        if token := get_cookie_value_from_session(self.session, STEAM_URL.LOGIN, STEAM_REFRESH_COOKIE):
            return token.split("%7C%7C")[1]  # ||

    def set_refresh_token(self, token: str | None):
        if token is None:
            remove_cookie_from_session(self.session, STEAM_URL.LOGIN, STEAM_REFRESH_COOKIE)
        else:
            # checks from
            # https://github.com/DoctorMcKay/node-steam-session/blob/811dadd2bfcc11de7861fff7442cb4a44ab61955/src/LoginSession.ts#L281

            decoded = decode_jwt(token)

            if "derive" not in decoded["aud"]:
                raise ValueError("Provided token is an access token, not a refresh token!")
            if "web" not in decoded["aud"]:
                raise ValueError("Token platform type is different from web browser!")
            if int(decoded["sub"]) != self.steam_id:
                raise ValueError(f"Provided token belongs to a different account [{decoded['sub']}]")

            if "%7C%7C" not in token:  # raw token
                token = decoded["sub"] + "%7C%7C" + token

            add_cookie_to_session(
                self.session,
                STEAM_URL.LOGIN,
                STEAM_REFRESH_COOKIE,
                token,
                # one year as steam default for refresh token
                expires=format_time(datetime.now() + timedelta(days=365)),
                samesite="None",
                secure=True,
                httponly=True,
            )

    async def is_session_alive(self, domain=STEAM_URL.COMMUNITY) -> bool:
        """Check if session is alive for `Steam` domain"""

        # we can also check https://steamcommunity.com/my for redirect to profile page as indicator
        # https://github.com/DoctorMcKay/node-steamcommunity/blob/1067d4572ee9d467e8f686951901c51028c5c995/index.js#L290

        # ensure that redirects is allowed and access token can be refreshed
        r = await self.session.get(domain, allow_redirects=True)
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
        try:
            client_id = session_data["response"]["client_id"]
            request_id = session_data["response"]["request_id"]
            steam_id = session_data["response"]["steamid"]  # steam id, if it needs to be retrieved
        except KeyError:
            raise LoginError("Could not obtain login data", session_data) from None

        await self._update_auth_session_with_steam_guard_code(client_id, steam_id)
        access_token, refresh_token = await self._poll_auth_session_status(client_id, request_id)
        fin_data = await self._finalize_login(nonce=refresh_token)

        fin_data_steam_id = fin_data["steamID"]
        transfer_datas: list[dict] = fin_data["transfer_info"]

        # https://github.com/DoctorMcKay/node-steam-session/blob/64463d7468c1c860afb80164b8c5831e629f657f/src/LoginSession.ts#L845
        loop = asyncio.get_event_loop()
        transfers = [
            loop.create_task(self._perform_transfer(d["url"], d["params"], fin_data_steam_id)) for d in transfer_datas
        ]
        # there is no guarantee that first completed transfer will be to community and
        # steamLoginSecure cookie will be not present yet, so better to wait until all transfers completed,
        # and we can be sure that login process to community domain is done
        # moreover, steam domains (store, community, help, tv, login) has own access tokens
        await asyncio.wait(transfers, return_when=asyncio.ALL_COMPLETED)

        if self.refresh_token is None:
            raise LoginError("Refresh token cookie is not presented after login attempt")

    async def _perform_transfer(self, url: str, params: dict, steam_id: str | int = None):
        """Perform a transfer of params and tokens to steam login endpoints"""

        r = await self.session.post(url, data={**params, "steamID": steam_id or self.steam_id})
        # https://github.com/DoctorMcKay/node-steam-session/blob/698469cdbad3e555dda10c81f580f1ee3960156f/src/LoginSession.ts#L864
        # make sure that `steamLoginSecure` cookie is present
        if not r.cookies.get(STEAM_SECURE_COOKIE):
            raise LoginError("Access token cookie is not present in result", r.cookies)

        # ensure that sessionid cookie is presented
        # https://github.com/DoctorMcKay/node-steam-session/blob/698469cdbad3e555dda10c81f580f1ee3960156f/src/LoginSession.ts#L872-L873
        if not r.cookies.get(SESSION_ID_COOKIE):
            add_cookie_to_session(
                self.session,
                r.real_url,
                SESSION_ID_COOKIE,
                generate_session_id(),
                samesite="None",
                secure=True,
            )

    async def _begin_auth_session_with_credentials(self) -> dict:
        pub_key, ts = await self._get_rsa_key()

        if not PROTOBUF_AVAILABLE:
            raise LoginError(
                "Protobuf library is required for Steam authentication. Install it with: pip install protobuf"
            )

        # Create device details message
        device_details = auth_pb2.CAuthentication_BeginAuthSessionViaCredentials_Request.DeviceDetails()
        device_details.device_friendly_name = self.user_agent if self.user_agent else "Unknown"
        device_details.platform_type = auth_pb2.k_EAuthTokenPlatformType_WebBrowser

        # Create auth session request
        session_request = auth_pb2.CAuthentication_BeginAuthSessionViaCredentials_Request()
        session_request.account_name = self.username
        session_request.encrypted_password = b64encode(encrypt(self._password.encode("utf-8"), pub_key)).decode()
        session_request.encryption_timestamp = ts
        session_request.remember_login = 1
        session_request.persistence = 1
        session_request.website_id = "Community"
        session_request.device_details.CopyFrom(device_details)
        session_request.additional_field = 8  # New required field by Steam

        # Encode to protobuf and base64
        encoded = b64encode(session_request.SerializeToString()).decode("utf-8")

        # Send request with protobuf encoding
        r = await self.session.post(
            STEAM_URL.API.IAuthService.BeginAuthSessionViaCredentials,
            data={
                "input_protobuf_encoded": encoded,
            },
            headers=REFERER_HEADER,
        )

        # Handle response (could be JSON or protobuf)
        if r.status == 200:
            if r.content_type == "application/json":
                return await r.json()
            elif r.content_type == "application/x-protobuf" or r.content_type == "application/octet-stream":
                binary_content = await r.read()
                response = auth_pb2.CAuthentication_BeginAuthSessionViaCredentials_Response()
                response.ParseFromString(binary_content)
                return {
                    "response": {
                        "client_id": response.client_id,
                        "request_id": response.request_id,  # Keep as bytes
                        "steamid": str(response.steamid),
                    }
                }

        raise LoginError(f"Unexpected response: {r.status} {r.content_type}")

    async def _update_auth_session_with_steam_guard_code(self, client_id: str | int, steam_id: str | int):
        # Doesn't check allowed confirmations, but it's probably not needed
        # as steam accounts suited for trading must have a steam guard and device code.

        # https://github.com/DoctorMcKay/node-steam-session/blob/64463d7468c1c860afb80164b8c5831e629f657f/src/LoginSession.ts#L735
        # https://github.com/DoctorMcKay/node-steam-session/blob/64463d7468c1c860afb80164b8c5831e629f657f/src/enums-steam/EAuthSessionGuardType.ts
        data = {
            "client_id": client_id,
            "steamid": steam_id,
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

    async def _poll_auth_session_status(self, client_id: str | int, request_id: str | bytes) -> tuple[str, str]:
        """Get current auth session status from steam, return access_token and refresh_token"""

        if not PROTOBUF_AVAILABLE:
            raise LoginError(
                "Protobuf library is required for Steam authentication. Install it with: pip install protobuf"
            )

        # Create poll request
        poll_req = auth_pb2.CAuthentication_PollAuthSessionStatus_Request()
        poll_req.client_id = client_id
        # request_id might be bytes from protobuf response
        if isinstance(request_id, bytes):
            poll_req.request_id = request_id
        else:
            poll_req.request_id = str(request_id).encode()

        # Encode to protobuf and base64
        encoded = b64encode(poll_req.SerializeToString()).decode("utf-8")

        # Send request
        r = await self.session.post(
            STEAM_URL.API.IAuthService.PollAuthSessionStatus,
            data={
                "input_protobuf_encoded": encoded,
            },
            headers=REFERER_HEADER,
        )

        # Handle response
        if r.status == 200:
            if r.content_type == "application/json":
                rj = await r.json()
                if rj.get("response", {"had_remote_interaction": True})["had_remote_interaction"]:
                    raise LoginError("Error polling auth session status", rj)
                return rj["response"]["access_token"], rj["response"]["refresh_token"]
            elif r.content_type == "application/x-protobuf" or r.content_type == "application/octet-stream":
                binary_content = await r.read()
                response = auth_pb2.CAuthentication_PollAuthSessionStatus_Response()
                response.ParseFromString(binary_content)
                return response.access_token, response.refresh_token

        raise LoginError(f"Unexpected response during poll: {r.status} {r.content_type}")

    async def _finalize_login(self, nonce: str) -> dict:
        data = {
            "nonce": nonce,
            "sessionid": self.session_id,
            "redir": str(STEAM_URL.COMMUNITY / "login/home/?goto="),
        }
        r = await self.session.post(
            STEAM_URL.LOGIN / "jwt/finalizelogin",
            data=data,
            headers={**API_HEADERS, **REFERER_HEADER, "Origin": str(STEAM_URL.COMMUNITY)},
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

    # TODO to remove in 0.8.0
    async def get_store_access_token_from_steam(self) -> str | None:
        """
        Fetch access token for `Steam Store` domain (https://store.steampowered.com/).
        Return token only if you logged in store domain.

        :return: raw token string or `None`
        :raises EResultError: for ordinary reasons
        """

        from warnings import warn

        warn(
            "`get_store_access_token_from_steam` method of `LoginMixin` is deprecated. Use `get_access_token(STEAM_URL.STORE)` instead",
            DeprecationWarning,
            stacklevel=2,
        )

        r = await self.session.get(STEAM_URL.STORE / "pointssummary/ajaxgetasyncconfig")
        rj = await r.json()
        success = EResult(rj.get("success"))
        if success is not EResult.OK:
            raise EResultError("Failed to fetch store access token", success, rj)

        return rj["data"]["webapi_token"] if rj["data"] else None

    async def refresh_access_token(self) -> str:
        """Request to refresh access token by web browser method"""

        await self.session.get(
            STEAM_URL.LOGIN / "jwt/refresh" % {"redir": str(STEAM_URL.COMMUNITY)},
            allow_redirects=True,
        )

        # option from above still works, anyway this is new browser behavior
        # POST to STEAM_URL.LOGIN / jwt/ajaxrefresh % {"redir": str(STEAM_URL.COMMUNITY)}
        # j_resp, check for success
        # POST to 'login_url' from resp, data is {**j_resp, "prior": self.access_token}
        # j_resp, check for success

        return self.access_token
