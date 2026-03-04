import asyncio
import hashlib
import hmac
import json
import re
import struct
import time
from base64 import b64decode, b64encode
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from enum import Enum, auto
from functools import wraps
from typing import TYPE_CHECKING, Callable, Literal

from betterproto2 import Message
from rsa import PublicKey
from rsa import encrypt as rsa_encrypt
from yarl import URL

from ..constants import STEAM_URL, EResult
from ..exceptions import EResultError
from ..id import SteamID
from ..transport import (
    AiohttpSteamTransport,
    BaseSteamTransport,
    Cookie,
    ResponseMode,
    TransportError,
    format_http_date,
)
from ..types import Coro
from .exceptions import *
from .models import SteamJWT
from .protobuf import *
from .utils import generate_session_id, parse_qr_challenge_url

# https://github.com/DoctorMcKay/node-steam-session/blob/a13bdf1e9c9a42c17a13db2b6be269e0c740fb07/src/helpers.ts#L17
API_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "cross-site",
}

BROWSER_HEADERS = {
    "Referer": str(STEAM_URL.COMMUNITY) + "/",
    "Origin": str(STEAM_URL.COMMUNITY),
}

STEAM_ACCESS_TOKEN_COOKIE = "steamLoginSecure"
STEAM_REFRESH_TOKEN_COOKIE = "steamRefresh_steam"

# LOGOUT_URLS_RE = re.compile(r"TransferLogout\(\s+(.+),\srgParameters")
# LOGOUT_TOKEN_RE = re.compile(r"rgParameters.token =\s\"(.+)\";")
# LOGOUT_AUTH_RE = re.compile(r"auth:\s\"(.+)\"")

I_AUTH_API_BASE_URL = STEAM_URL.WEB_API / "IAuthenticationService"
LOGIN_URL = URL("https://login.steampowered.com")
SESSION_ID_COOKIE = "sessionid"

AuthWebAPIMethod = Literal[
    "BeginAuthSessionViaCredentials",
    "BeginAuthSessionViaQR",
    "GetPasswordRSAPublicKey",
    "UpdateAuthSessionWithSteamGuardCode",
    "PollAuthSessionStatus",
    "GenerateAccessTokenForApp",
    "GetAuthSessionInfo",
    "UpdateAuthSessionWithMobileConfirmation",
]


def mobile_platform(func):
    @wraps(func)
    def wrapper(self: "SteamSession", *args, **kwargs):
        if self._platform_type is not EAuthTokenPlatformType.k_EAuthTokenPlatformType_MobileApp:
            raise ValueError("This method is only supported for session with mobile app platform type")
        return func(self, *args, **kwargs)

    return wrapper


class SteamSession:
    __slots__ = (
        "_platform_type",
        "_transport",
        "_account_name",
        "_access_token",
        "_refresh_token",
        "_session_id",
        "_request_id",
        "_client_id",
        "_poll_interval",
        "_phase",
        "_steam_id",
    )

    def __init__(
        self,
        refresh_token: str | SteamJWT | None = None,
        *,
        platform_type: EAuthTokenPlatformType = EAuthTokenPlatformType.k_EAuthTokenPlatformType_WebBrowser,
        transport: BaseSteamTransport | None = None,
        proxy: str | None = None,
    ):
        """
        Authentication session.
        Manages the full *"begin -> confirm -> finalize"* process and stores resulting tokens.

        ---

        Ways of usage:

        1) **Credentials flow**
            - Call ``with_credentials`` with account name and password.
            - Depending on account security settings, additional confirmation may be required.
            - After the confirmation was made, call ``finalize``.

        2) **QR flow**
            - Call ``with_qr`` to obtain a QR challenge URL.
            - Scan QR with mobile app and approve or pass it to a mobile-app session using ``approve_session``.
            - After the QR is approved, call ``finalize``.

        3) **Restoration from refresh token**:
            - Create session instance with valid ``refresh_token``.

        After successful finalization, the *tokens* has been set and session
        can be used to obtain `Steam` websites cookies.

        :param refresh_token: previously obtained and valid `refresh token` for the account.
        :param platform_type: The platform type for which the client is being initialized.
            Defaults to ``EAuthTokenPlatformType.k_EAuthTokenPlatformType_WebBrowser``.
            Must not be ``EAuthTokenPlatformType.k_EAuthTokenPlatformType_SteamClient``.
        :param transport: A custom transport instance implementing the required
            HTTP communication interface. If provided, ``proxy`` cannot also be set.
        :param proxy: A proxy URL to route HTTP requests through when using the *default HTTP transport*.
        :raises ValueError: If unsupported platform type is used or invalid argument combinations are provided.
        """

        if platform_type is EAuthTokenPlatformType.k_EAuthTokenPlatformType_SteamClient:
            raise ValueError("Steam Client platform is not supported")
        if transport is not None and proxy is not None:
            raise ValueError("Proxy is not supported for custom transport")

        self._account_name: str | None = None
        self._access_token: SteamJWT | None = None
        self._refresh_token: SteamJWT | None = None
        self._session_id: str | None = None  # let's be less dependent on cookie and store value instead

        self._set_state()  # set transient internal state

        self._steam_id = SteamID()

        if refresh_token is not None:
            if not isinstance(refresh_token, SteamJWT):
                refresh_token = SteamJWT.parse(refresh_token)

            if refresh_token.expired:
                import warnings

                # issue a warning for now as early measure
                warnings.warn("Provided refresh token is expired. Are you sure you want to use it?", RuntimeWarning)

            # https://github.com/DoctorMcKay/node-steam-session/blob/a13bdf1e9c9a42c17a13db2b6be269e0c740fb07/src/LoginSession.ts#L281
            if not refresh_token.is_refresh_token:
                raise ValueError("Provided token is an access token, not a refresh token")

            if refresh_token.for_web:
                platform_type = EAuthTokenPlatformType.k_EAuthTokenPlatformType_WebBrowser
            elif refresh_token.for_mobile:
                platform_type = EAuthTokenPlatformType.k_EAuthTokenPlatformType_MobileApp
            else:  # client
                raise ValueError("Provided token issued for Steam Client platform which is not supported")

            self._steam_id = refresh_token.subject
            self._refresh_token = refresh_token

        self._platform_type = platform_type

        self._transport: BaseSteamTransport = transport or AiohttpSteamTransport(proxy=proxy)

        # add mobile app specific user agent and cookie
        if platform_type is EAuthTokenPlatformType.k_EAuthTokenPlatformType_MobileApp:
            # https://github.com/DoctorMcKay/node-steam-session/blob/a13bdf1e9c9a42c17a13db2b6be269e0c740fb07/src/AuthenticationClient.ts#L412
            self._transport.user_agent = "okhttp/4.9.2"
            self._transport.add_cookie(Cookie("mobileClientVersion", "777777 3.10.3", STEAM_URL.WEB_API.host))
            self._transport.add_cookie(Cookie("mobileClient", "android", STEAM_URL.WEB_API.host))

    @property
    def platform(self) -> EAuthTokenPlatformType:
        return self._platform_type

    @property
    def transport(self) -> BaseSteamTransport:
        return self._transport

    @property
    def steam_id(self) -> SteamID:
        """`Steam ID` of authenticated account. Will be populated after successful authentication."""
        return self._steam_id

    @property
    def account_name(self) -> str | None:
        """Account name of authenticated account. Will be populated after successful authentication."""
        return self._account_name

    @property
    def access_token(self) -> SteamJWT | None:
        """
        Access token issued by `Steam` during login process.
        At the current moment can be used only for `Steam Web API`.
        """
        return self._access_token

    @property
    def refresh_token(self) -> SteamJWT | None:
        """Refresh token. Required to renew `access token` or obtaining `auth cookies`."""
        return self._refresh_token

    # session id needed only at and after obtaining web cookies
    @property
    def session_id(self) -> str | None:
        """`sessionid` cookie value for `Community` domain."""
        return self._session_id

    def _set_state(self, request_id=b"", client_id=0, poll_interval=0.0):
        self._request_id = request_id
        self._client_id = client_id
        self._poll_interval = poll_interval

    async def _call_auth_web_api(
        self,
        http_method: Literal["GET", "POST"],
        api_method: AuthWebAPIMethod,
        protobuf: Message,
        response_mode: ResponseMode = "bytes",
    ) -> bytes:
        """Wrapper method. Intended only to call `IAuthenticationService` methods."""

        params = None
        multipart = None

        protobuf_data = {"input_protobuf_encoded": b64encode(bytes(protobuf)).decode()}

        if http_method == "GET":
            params = {**(params or {}), **protobuf_data}
            # https://github.com/DoctorMcKay/node-steam-session/blob/a13bdf1e9c9a42c17a13db2b6be269e0c740fb07/src/transports/WebApiTransport.ts#L48
            if self._platform_type is EAuthTokenPlatformType.k_EAuthTokenPlatformType_MobileApp:
                params |= {"origin": "SteamMobile"}

        else:  # POST
            multipart = {**(multipart or {}), **protobuf_data}

        headers = {**API_HEADERS}
        if self._platform_type is EAuthTokenPlatformType.k_EAuthTokenPlatformType_WebBrowser:
            headers |= BROWSER_HEADERS

        r = await self._transport.request(
            http_method,
            I_AUTH_API_BASE_URL / f"{api_method}/v1",
            params=params,
            multipart=multipart,
            headers=headers,
            response_mode=response_mode,
            redirects=False,
            raise_for_status=True,
        )

        if r.status < 200 or r.status >= 300:  # redirect means error
            raise TransportError(r)

        EResultError.check_headers(r.headers, "Error calling Steam Web Api")

        return r.content

    def _get_platform_data(self) -> tuple[str, dict]:
        """Get platform data for `Steam` authentication request. Return `website id` and `device details data`."""

        match self._platform_type:
            case EAuthTokenPlatformType.k_EAuthTokenPlatformType_WebBrowser:
                return "Community", {
                    "device_friendly_name": self._transport.user_agent or "Unknown",
                    "platform_type": self._platform_type,
                }
            # https://github.com/DoctorMcKay/node-steam-session/blob/a13bdf1e9c9a42c17a13db2b6be269e0c740fb07/src/AuthenticationClient.ts#L409
            case EAuthTokenPlatformType.k_EAuthTokenPlatformType_MobileApp:
                return "Mobile", {
                    "device_friendly_name": "Galaxy S25",
                    "platform_type": self._platform_type,
                    "os_type": -500,  # Android Unknown from EOSType,
                    "gaming_device_type": 528,
                }
            case _:
                raise ValueError(f"Unknown or unsupported platform type: {self._platform_type}")

    async def _get_rsa_data(self, account_name: str) -> tuple[int, int, int]:
        """Get rsa data (pub. key mod, pub. key exp, ts) from `Steam`."""

        msg = CAuthenticationGetPasswordRsaPublicKeyRequest(account_name=account_name)

        try:
            r = await self._call_auth_web_api("GET", "GetPasswordRSAPublicKey", msg)
            resp = CAuthenticationGetPasswordRsaPublicKeyResponse.parse(r)

        except Exception as e:
            raise LoginError("Could not obtain rsa data from Steam") from e

        return (
            int(resp.publickey_mod, 16),
            int(resp.publickey_exp, 16),
            resp.timestamp,
        )

    async def submit_steam_guard_code(
        self,
        auth_code: str,
        code_type: Literal[
            EAuthSessionGuardType.k_EAuthSessionGuardType_DeviceCode,
            EAuthSessionGuardType.k_EAuthSessionGuardType_EmailCode,
        ] = EAuthSessionGuardType.k_EAuthSessionGuardType_DeviceCode,
    ):
        """
        Update current session with `Steam Guard` code either email or device code.
        Equivalent of entering `Steam Guard` code during login process page and submitting after.

        :param auth_code: `Steam Guard` two-factor (TOTP) code.
        :param code_type: type of `Steam Guard` code to submit.
        :raises LoginError: for ordinary reasons.
        :raises ValueError: when session is not initialized.
        """

        if not self._client_id or not self._steam_id:
            raise ValueError("Session is not initialized")

        msg = CAuthenticationUpdateAuthSessionWithSteamGuardCodeRequest(
            client_id=self._client_id,
            steamid=self._steam_id.id64,
            code=auth_code,
            code_type=code_type,
        )

        try:
            await self._call_auth_web_api("POST", "UpdateAuthSessionWithSteamGuardCode", msg, "meta")
        except Exception as e:
            raise LoginError("Could not update auth session with Steam Guard code") from e

    @mobile_platform
    async def get_session_info(self, qr_challenge_url: URL | str) -> CAuthenticationGetAuthSessionInfoResponse:
        """
        Get info of the other login session from `Steam`.
        Equivalent of scanning QR with `Steam App` on a mobile device,
        therefore, *must be used only from session with mobile app platform type*.

        :param qr_challenge_url: url from QR of session to get info. Must be from the same account.
        :return: session info.
        :raises LoginError: for ordinary reasons.
        """

        _, client_id = parse_qr_challenge_url(qr_challenge_url)

        msg = CAuthenticationGetAuthSessionInfoRequest(client_id=client_id)

        try:
            r = await self._call_auth_web_api("POST", "GetAuthSessionInfo", msg)
        except Exception as e:
            raise LoginError("Could not get auth session info") from e

        return CAuthenticationGetAuthSessionInfoResponse.parse(r)

    @mobile_platform
    async def perform_session_mobile_confirmation(
        self,
        qr_challenge_url: URL | str,
        shared_secret: str,
        *,
        confirm: bool = True,
        persistence: bool = True,
    ):
        """
        Perform mobile confirmation of the other `login session`.
        Equivalent of scanning auth QR with Steam App on a mobile device and tapping "Approve" or "Decline" button
        as the next step.

        :param qr_challenge_url: qr url of session to perform confirmation. Must be from the same account.
        :param shared_secret: shared secret of authenticated account with enabled *Steam Guard*.
        :param confirm: whether to confirm the session or not.
        :param persistence: whether session should be persisted.
        :raises LoginError: for ordinary reasons.
        """

        if not self._steam_id:
            raise ValueError("Current session is not initialized")

        version, client_id = parse_qr_challenge_url(qr_challenge_url)

        # https://github.com/DoctorMcKay/node-steam-session/blob/a13bdf1e9c9a42c17a13db2b6be269e0c740fb07/src/LoginApprover.ts#L194
        signature_data = bytearray(18)
        struct.pack_into("<H", signature_data, 0, version)
        struct.pack_into("<Q", signature_data, 2, client_id)
        struct.pack_into("<Q", signature_data, 10, self._steam_id.id64)
        signature = hmac.new(shared_secret.encode("utf-8"), bytes(signature_data), hashlib.sha256).digest()

        msg = CAuthenticationUpdateAuthSessionWithMobileConfirmationRequest(
            version=version,
            client_id=client_id,
            steamid=self._steam_id.id64,
            signature=signature,
            confirm=confirm,
            persistence=ESessionPersistence(int(persistence)),
        )

        try:
            await self._call_auth_web_api("POST", "UpdateAuthSessionWithMobileConfirmation", msg, "meta")
        except Exception as e:
            raise LoginError("Could not update auth session with mobile confirmation") from e

    @mobile_platform
    async def approve_session(
        self,
        login_session: "SteamSession",
        shared_secret: str,
        *,
        persistence: bool = True,
    ):
        """
        Approve other login session.
        Equivalent of scanning auth QR with `Steam App` on a mobile device
        and tapping "Approve" button as the next step.
        Passed session must **not be initialized** and will be finalized, authenticated and ready to use after approval.

        :param login_session: session to approve. Must be from the same account and with non-mobile app platform type.
        :param shared_secret: shared secret of current session authenticated account.
        :param persistence: whether session should be persisted.
        :raises LoginError: for ordinary reasons.
        :raises ValueError: when passed session is already initialized or has non-mobile app platform type.
        """

        if login_session is self:
            raise ValueError("Cannot approve own session")
        if login_session._platform_type is EAuthTokenPlatformType.k_EAuthTokenPlatformType_MobileApp:
            raise ValueError("Only session with non-mobile app platform type can be approved")
        if login_session._steam_id:
            raise ValueError("Passed session is already initialized")

        qr_url = await login_session.with_qr()
        await self.perform_session_mobile_confirmation(qr_url, shared_secret, persistence=persistence)
        await login_session.finalize()

    async def with_credentials(
        self,
        account_name: str,
        password: str,
        persistence: bool = True,
        *,
        device_steam_guard_code: str | Callable[[], str] | None = None,
    ):
        """
        Begin authentication session with credentials.
        Equivalent of entering username and password on `Steam` website login page and submitting after.

        .. note:: If ``device_steam_guard_code`` argument is provided,
            `Steam Guard` code will be submitted automatically and session will be finalized after confirmation.
            Otherwise, ``ConfirmationRequired`` exception will be raised
            indicating that additional confirmation will be required.

        :param account_name: username.
        :param password: password.
        :param persistence: whether session should be persisted.
        :param device_steam_guard_code: two-factor (TOTP) code from `Steam Guard`.
            Can be generated using secrets or copied from the `Steam mobile app`.
            Preferably should be a ``callable`` as the device code will be generated as close to the submission moment
            as possible.
        :raises LoginError: for ordinary reasons.
        :raises ConfirmationRequired: when `Steam` requires performing  additional confirmation (email, device, etc.).
        """

        pub_mod, pub_exp, rsa_ts = await self._get_rsa_data(account_name)
        encrypted_password = b64encode(rsa_encrypt(password.encode("utf-8"), PublicKey(pub_mod, pub_exp))).decode()

        website_id, device_details_data = self._get_platform_data()

        msg = CAuthenticationBeginAuthSessionViaCredentialsRequest(
            account_name=account_name,
            encrypted_password=encrypted_password,
            encryption_timestamp=rsa_ts,
            remember_login=persistence,
            persistence=ESessionPersistence(int(persistence)),
            website_id=website_id,
            device_details=CAuthenticationDeviceDetails(**device_details_data),
        )

        try:
            r = await self._call_auth_web_api("POST", "BeginAuthSessionViaCredentials", msg)
        except Exception as e:
            raise LoginError("Could not begin auth session via credentials") from e

        begin_session_data = CAuthenticationBeginAuthSessionViaCredentialsResponse.parse(r)

        self._set_state(begin_session_data.request_id, begin_session_data.client_id, begin_session_data.interval)

        self._steam_id = SteamID(begin_session_data.steamid)

        if not begin_session_data.allowed_confirmations:
            raise LoginError("No allowed confirmations!")

        allowed_guard_types = {conf.confirmation_type for conf in begin_session_data.allowed_confirmations}

        if EAuthSessionGuardType.k_EAuthSessionGuardType_None in allowed_guard_types:  # confirmation isn't required
            await self.finalize()
            return

        if (
            EAuthSessionGuardType.k_EAuthSessionGuardType_DeviceCode in allowed_guard_types
        ) and device_steam_guard_code is not None:
            if callable(device_steam_guard_code):  # callback or factory
                device_steam_guard_code = device_steam_guard_code()

            await self.submit_steam_guard_code(device_steam_guard_code)
            await self.finalize()

        else:
            raise ConfirmationRequired(begin_session_data.allowed_confirmations, allowed_guard_types)

    async def with_qr(self) -> URL:
        """
        Begin authentication session with auth QR.
        Produce QR auth url that needs to be scanned with `Steam App` on a mobile device
        or using another login session (look at ``approve_session`` method).

        :return: QR challenge url.
        :raises LoginError: for ordinary reasons.
        :raises ValueError: when session has mobile app platform type.
        """

        if self._platform_type is EAuthTokenPlatformType.k_EAuthTokenPlatformType_MobileApp:
            raise ValueError("This method is not supported for mobile app platform type")

        _, device_details_data = self._get_platform_data()

        msg = CAuthenticationBeginAuthSessionViaQrRequest(
            device_details=CAuthenticationDeviceDetails(**device_details_data),
        )

        try:
            r = await self._call_auth_web_api("POST", "BeginAuthSessionViaQR", msg)
        except Exception as e:
            raise LoginError("Could not start auth session via qr") from e

        begin_session_data = CAuthenticationBeginAuthSessionViaQrResponse.parse(r)

        self._set_state(begin_session_data.request_id, begin_session_data.client_id, begin_session_data.interval)

        return URL(begin_session_data.challenge_url)  # or str?

    async def _get_status(self) -> CAuthenticationPollAuthSessionStatusResponse:
        """Get current session status."""

        msg = CAuthenticationPollAuthSessionStatusRequest(client_id=self._client_id, request_id=self._request_id)

        try:
            r = await self._call_auth_web_api("POST", "PollAuthSessionStatus", msg)
        except Exception as e:
            raise LoginError("Could not get auth session status") from e

        return CAuthenticationPollAuthSessionStatusResponse.parse(r)

    async def _poll_status(self):
        """
        Poll session status with interval. Will set `access and refresh tokens` on success.
        Use ``asyncio.wait_for`` with ``timeout`` to prevent infinite polling.
        """

        while True:
            start = time.monotonic()
            status = await self._get_status()
            if status.refresh_token:
                # there can be set account name
                self._account_name = status.account_name
                self._access_token = SteamJWT.parse(status.access_token)
                self._refresh_token = SteamJWT.parse(status.refresh_token)

                return

            end = time.monotonic()
            await asyncio.sleep(self._poll_interval - (end - start))  # respect steam interval and avoid shift

    # here we need to obtain tokens
    async def finalize(self) -> tuple[SteamJWT, SteamJWT]:
        """
        Finalize login process for current session by obtaining `tokens`.

        Must be called after a **performed action**
        or after the current session has been **approved** by another login session.
        Fill ``steam_id`` if it was not provided during initialization.

        :return: `access` and `refresh` tokens.
        :raises LoginError: for ordinary reasons.
        :raises ValueError: when session is not ready for finalization.
        """

        if not self._client_id or not self._request_id:
            raise ValueError("Session is not ready for finalization")

        # Let's assume that Steam need some time to process things, just to be safe
        timeout = (self._poll_interval * 2) + 0.1

        try:
            await asyncio.wait_for(self._poll_status(), timeout)
        except asyncio.TimeoutError:
            raise LoginError("Failed to get session status") from None
        except Exception:
            raise

        self._set_state()  # clear state as unneeded

        return self.access_token, self.refresh_token

    async def _perform_transfer(self, url: URL, params: dict, steam_id: str):
        for _ in range(3):  # little bit of tenacity here
            try:
                await self._transport.request(
                    "POST",
                    url,
                    multipart={**params, "steamID": steam_id},
                    response_mode="meta",
                )
                break

            except TransportError:
                await asyncio.sleep(0.55)

        else:
            raise LoginError(f"Could not perform transfer to '{url}' for '{steam_id}'")

    async def obtain_cookies(self) -> list[Cookie]:
        """
        Obtain auth web cookies for `Steam` websites using ``refresh_token``.
        Store resulting cookies in the underlying ``transport`` cookie jar.

        :return: list of auth cookies including session id.
        """

        if self._refresh_token is None:
            raise ValueError("Session is not finalized or refresh token is not set")

        # guess we don't required to make request to Steam
        # and instead can generate sessionid by ourselves
        if self._session_id is None:
            self._session_id = generate_session_id()

        # TODO node-steamcommunity return single access token for mobile platform
        #  for some reason. Need to test it, maybe that access token can be used
        #  for websites.
        if self._platform_type is EAuthTokenPlatformType.k_EAuthTokenPlatformType_MobileApp:
            raise NotImplementedError("Mobile app platform type is not supported yet")

        data = {
            "nonce": self._refresh_token.raw,
            "sessionid": self._session_id,
            "redir": str(STEAM_URL.COMMUNITY / "login/home/?goto="),
        }
        # here we get refresh token cookie, if it is already present Steam return same refresh token
        r = await self._transport.request(
            "POST",
            LOGIN_URL / "jwt/finalizelogin",
            multipart=data,
            headers={**API_HEADERS, **BROWSER_HEADERS},
            response_mode="json",
        )
        rj: dict = r.content
        if rj and (error_msg := rj.get("error")):
            raise LoginError(f"Get error response when performing login finalization: {error_msg}")
        if not rj or not rj.get("transfer_info") or not rj.get("steamID"):
            raise LoginError("Malformed login response", rj)

        fin_data_steam_id: str = rj["steamID"]
        transfer_datas: list[dict] = rj["transfer_info"]

        if not self._steam_id:
            self._steam_id = SteamID(fin_data_steam_id)  # or we can get it from token

        auth_urls = [URL(d["url"]) for d in transfer_datas]  # parse urls only once

        # perform transfers concurrently
        async with asyncio.TaskGroup() as tg:
            for url, d in zip(auth_urls, transfer_datas):
                tg.create_task(
                    self._perform_transfer(
                        url,
                        d["params"],
                        fin_data_steam_id,
                    )
                )

        cookies = []

        # rewrite sessionid, get auth cookies
        for url, d in zip(auth_urls, transfer_datas):
            session_id_cookie = Cookie(
                SESSION_ID_COOKIE,
                self._session_id,
                url.host,
                host_only=True,
                secure=True,
                same_site="None",
            )
            cookies.append(session_id_cookie)
            self._transport.add_cookie(session_id_cookie)

            cookies.append(self._transport.get_cookie(url.with_path("/"), STEAM_ACCESS_TOKEN_COOKIE))

        return cookies

    @mobile_platform
    async def refresh_tokens(self):
        """Refresh `access` and `refresh tokens`."""

        refresh_token = self.refresh_token
        if refresh_token is None:
            raise ValueError("Refresh token is not set")

        raise NotImplementedError
        # https://github.com/DoctorMcKay/node-steam-session/blob/3ac0f34fd964b3f886ba18ef4824ac43c942e030/src/AuthenticationClient.ts#L288

    # # Am I sure we need this?
    # async def logout(self):
    #     """
    #     Perform logout of the current session.
    #     `Access` tokens will be invalidated while `refresh token` persist.
    #     """
    #
    #     # technically, we can remove access tokens and be safe
    #
    #     if self.refresh_token is None:
    #         raise ValueError("Refresh token is not set")
    #
    #     r = await self._transport.request(
    #         "POST",
    #         STEAM_URL.COMMUNITY / "login/logout/",
    #         data={"sessionid": self.session_id},
    #         response_mode="text",
    #     )
    #
    #     # in theory can be the same urls from finalization
    #     logout_urls = [URL(url) for url in json.loads(LOGOUT_URLS_RE.search(r.content).group(1))]
    #     token = LOGOUT_TOKEN_RE.search(r.content).group(1)
    #     auth = LOGOUT_AUTH_RE.search(r.content).group(1)  # some auth code, idk
    #
    #     data = {"in_transfer": 1, "auth": auth, "token": token}
    #
    #     async with asyncio.TaskGroup() as tg:
    #         for url in logout_urls:
    #             tg.create_task(
    #                 self._transport.request(
    #                     "POST",
    #                     url,
    #                     data=data,
    #                     response_mode="meta",
    #                 )
    #             )

    def close(self) -> Coro[None]:
        return self._transport.close()
