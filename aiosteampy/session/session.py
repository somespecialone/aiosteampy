import asyncio
import struct
import hmac
import hashlib
import re
import json

from enum import Enum, auto
from contextlib import asynccontextmanager
from base64 import b64encode, b64decode
from typing import Callable, Literal
from functools import wraps
from datetime import datetime, timedelta, timezone

from rsa import PublicKey, encrypt as rsa_encrypt
from yarl import URL
from betterproto2 import Message

from ..types import Coro
from ..constants import STEAM_URL
from ..id import SteamID
from ..transport import (
    BaseSteamTransport,
    AiohttpSteamTransport,
    Cookie,
    format_http_date,
    TransportError,
    ResponseMode,
    WebAPIMethod,
)
from ..transport.base import BASE_WEB_API_URL

from .utils import parse_qr_challenge_url, wait_coroutines
from .exceptions import *
from .protobuf import *
from .models import SteamJWT

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

LOGOUT_URLS_RE = re.compile(r"TransferLogout\(\s+(.+),\srgParameters")
LOGOUT_TOKEN_RE = re.compile(r"rgParameters.token =\s\"(.+)\";")
LOGOUT_AUTH_RE = re.compile(r"auth:\s\"(.+)\"")

PROFILE_LOCATION_HEADER_RE = re.compile(r"steamcommunity\.com(/(id|profiles)/[^/]+)/?")

WITH_GET_METHODS = {"GetPasswordRSAPublicKey"}


def mobile_platform(func):
    @wraps(func)
    def wrapper(self: "SteamLoginSession", *args, **kwargs):
        if self._platform_type is not EAuthTokenPlatformType.k_EAuthTokenPlatformType_MobileApp:
            raise ValueError("This method is only supported for session with mobile app platform type")
        return func(self, *args, **kwargs)

    return wrapper


class SteamLoginSession:
    __slots__ = (
        "_platform_type",
        "_transport",
        "_request_id",
        "_client_id",
        "_poll_interval",
        "_phase",
        "_steam_id",
    )

    def __init__(
        self,
        platform_type: EAuthTokenPlatformType = EAuthTokenPlatformType.k_EAuthTokenPlatformType_WebBrowser,
        *,
        transport: BaseSteamTransport | None = None,
        proxy: str | None = None,
    ):
        """
        Authentication session with specified platform type, HTTP transport, and proxy settings.

        This class manages the full "begin -> confirm -> finalize" process and stores the resulting
        web cookies/tokens in the underlying ``BaseSteamTransport`` cookie jar.

        .. note::
            Current implementation is made specifically for HTTP transport
            and used mostly within `Steam Community`.

        Two primary ways to start a session:

        1) **Credentials flow**
           - Call ``with_credentials`` with account name and password.
           - Depending on account security settings, additional confirmation may be required.
           - After the confirmation was made, call ``finalize``.

        2) **QR flow**
           - Call ``with_qr`` to obtain a QR challenge URL.
           - Scan QR with mobile app and approve or pass it to a mobile-app session using ``approve_session``.
           - After the QR is approved, call ``finalize``.

        After successful finalization, the session has web cookies and tokens set and can be used
        to access `Steam Community` endpoints. You can retrieve token values using ``access_token``
        and ``refresh_token``.

        :param platform_type: The platform type for which the client is being initialized.
            Defaults to ``EAuthTokenPlatformType.k_EAuthTokenPlatformType_WebBrowser``.
            Must not be ``EAuthTokenPlatformType.k_EAuthTokenPlatformType_SteamClient``.
        :param transport: A custom transport instance implementing the required
            HTTP communication interface. If provided, ``proxy`` cannot also be set.
        :param proxy: A proxy URL to route HTTP requests through when using the default HTTP transport.
        :raises ValueError: If unsupported platform type is used or invalid argument combinations are provided.
        """

        if platform_type is EAuthTokenPlatformType.k_EAuthTokenPlatformType_SteamClient:
            raise ValueError("`SteamClient` platform type is not supported")
        if transport is not None and proxy is not None:
            raise ValueError("`proxy` argument is not supported for custom transport")

        self._platform_type = platform_type

        self._transport: BaseSteamTransport = transport or AiohttpSteamTransport(proxy=proxy)

        # add mobile app specific user agent and cookie
        if platform_type is EAuthTokenPlatformType.k_EAuthTokenPlatformType_MobileApp:
            # https://github.com/DoctorMcKay/node-steam-session/blob/a13bdf1e9c9a42c17a13db2b6be269e0c740fb07/src/AuthenticationClient.ts#L412
            self._transport.user_agent = "okhttp/4.9.2"
            self._transport.add_cookie(Cookie("mobileClientVersion", "777777 3.10.3", BASE_WEB_API_URL.host))
            self._transport.add_cookie(Cookie("mobileClient", "android", BASE_WEB_API_URL.host))

        # set transient internal state
        self._set_state()

        self._steam_id = SteamID()

    @property
    def platform(self) -> EAuthTokenPlatformType:
        return self._platform_type

    @property
    def transport(self) -> BaseSteamTransport:
        return self._transport

    @property
    def steam_id(self) -> SteamID:
        """`Steam ID` of the authenticated account. Will be populated after successful authentication."""
        return self._steam_id

    @property
    def access_token(self) -> SteamJWT | None:
        """Encoded JWT `access token` for `Community` domain. Can be used to make requests to a `Steam Web API`."""
        return self.get_access_token(STEAM_URL.COMMUNITY)

    def _get_raw_token(self, domain: URL, token_cookie_name: str) -> str | None:
        if token_cookie_val := self._transport.get_cookie_value(domain, token_cookie_name):
            return token_cookie_val.split("%7C%7C")[1]  # ||

    def get_access_token(self, domain: URL) -> SteamJWT | None:
        """Get encoded JWT *access token* string for `Steam` ``domain``."""

        if raw_token := self._get_raw_token(domain, STEAM_ACCESS_TOKEN_COOKIE):
            return SteamJWT.parse(raw_token)

    def set_access_token(self, token: str | SteamJWT | None, domain: URL):
        """Set JWT *access token* for `Steam` ``domain``. Populate ``steam_id`` if it is not yet set."""

        if token is None:
            self._transport.remove_cookie(domain, STEAM_ACCESS_TOKEN_COOKIE)
        else:  # str or SteamJWT
            if not isinstance(token, SteamJWT):
                token = SteamJWT.parse(token)

            token_subject = token.subject

            if token.expired:  # we do not allow expired access tokens as they can be renewed with refresh token
                raise ValueError("Provided access token is expired")
            # https://github.com/DoctorMcKay/node-steam-session/blob/a13bdf1e9c9a42c17a13db2b6be269e0c740fb07/src/LoginSession.ts#L232
            if "derive" in token.aud:
                raise ValueError("Provided token is a refresh token, not an access token!")
            if self._steam_id and token_subject != self._steam_id:
                raise ValueError(f"Provided token belongs to a different account: {token.sub}")

            if not self._steam_id:
                self._steam_id = token_subject

            # aud must contain "web:[domain]" entries, like "web:community" for community and this better be checked

            now = datetime.now()
            cookie = Cookie(
                STEAM_ACCESS_TOKEN_COOKIE,
                token.cookie_value,
                domain.host,
                expires=format_http_date(now + timedelta(days=400)),  # from browser
                host_only=True,
                http_only=True,
                secure=True,
                same_site="None",
                created_at=format_http_date(now),
            )

            self._transport.add_cookie(cookie)

    @property
    def refresh_token(self) -> SteamJWT | None:
        """Encoded JWT `refresh token`."""

        if raw_token := self._get_raw_token(STEAM_URL.LOGIN, STEAM_REFRESH_TOKEN_COOKIE):
            return SteamJWT.parse(raw_token)

    def set_refresh_token(self, token: str | SteamJWT | None):
        if token is None:
            self._transport.remove_cookie(STEAM_URL.LOGIN, STEAM_REFRESH_TOKEN_COOKIE)
        else:
            if not isinstance(token, SteamJWT):
                token = SteamJWT.parse(token)

            token_subject = token.subject

            if token.expired:
                import warnings

                # issue a warning for now as early measure
                warnings.warn("Provided refresh token is expired, are you sure you want to use it?", RuntimeWarning)

            # https://github.com/DoctorMcKay/node-steam-session/blob/a13bdf1e9c9a42c17a13db2b6be269e0c740fb07/src/LoginSession.ts#L281
            if "derive" not in token.aud:
                raise ValueError("Provided token is an access token, not a refresh token!")

            if self._platform_type is EAuthTokenPlatformType.k_EAuthTokenPlatformType_WebBrowser:
                required_aud = "web"
            else:
                required_aud = "mobile"
            if required_aud not in token.aud:
                raise ValueError("Token platform type is different from created session!")

            if self._steam_id and token_subject != self._steam_id:
                raise ValueError(f"Provided token belongs to a different account: {token.sub}")

            if not self._steam_id:
                self._steam_id = token_subject

            now = datetime.now()
            cookie = Cookie(
                STEAM_REFRESH_TOKEN_COOKIE,
                token.sub + "%7C%7C" + token.raw,
                STEAM_URL.LOGIN.host,
                expires=format_http_date(now + timedelta(days=365)),  # also from browser
                host_only=True,
                http_only=True,
                secure=True,
                same_site="None",
                created_at=format_http_date(now),
            )

            self._transport.add_cookie(cookie)

    def _set_state(self, request_id=b"", client_id=0, poll_interval=0.0):
        self._request_id = request_id
        self._client_id = client_id
        self._poll_interval = poll_interval

    async def _init(self):
        """
        Fetch main `Steam Community` page to obtain cookies (`sessionid`) following real behavior of user with browser.
        """

        try:
            await self._transport.request("GET", STEAM_URL.COMMUNITY, response_mode="meta")
        except TransportError as e:
            raise LoginError("Could not initialize session") from e

        if self._transport.session_id is None:
            raise LoginError("Could not initialize session")

    async def _call_auth_web_api(
        self,
        api_method: WebAPIMethod,
        protobuf: Message,
        response_mode: ResponseMode = "bytes",
    ) -> bytes:
        """Wrapper method. Intended only to call `IAuthenticationService` methods."""

        params = None
        multipart = None

        protobuf_data = {"input_protobuf_encoded": b64encode(bytes(protobuf)).decode()}

        if api_method in WITH_GET_METHODS:  # GET
            http_method = "GET"
            params = {**(params or {}), **protobuf_data}
            # https://github.com/DoctorMcKay/node-steam-session/blob/a13bdf1e9c9a42c17a13db2b6be269e0c740fb07/src/transports/WebApiTransport.ts#L48
            if self._platform_type is EAuthTokenPlatformType.k_EAuthTokenPlatformType_MobileApp:
                params |= {"origin": "SteamMobile"}

        else:  # POST
            http_method = "POST"
            multipart = {**(multipart or {}), **protobuf_data}

        headers = {**API_HEADERS}
        if self._platform_type is EAuthTokenPlatformType.k_EAuthTokenPlatformType_WebBrowser:
            headers |= BROWSER_HEADERS

        r = await self._transport.call_web_api(
            http_method,
            "IAuthenticationService",
            api_method,
            params=params,
            multipart=multipart,
            headers=headers,
            response_mode=response_mode,
        )

        return r

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
            r = await self._call_auth_web_api("GetPasswordRSAPublicKey", msg)
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
            await self._call_auth_web_api("UpdateAuthSessionWithSteamGuardCode", msg, "meta")
        except Exception as e:
            raise LoginError("Could not update auth session with Steam Guard code") from e

    async def _get_status(self) -> CAuthenticationPollAuthSessionStatusResponse:
        """Get current session status from `Steam`."""

        msg = CAuthenticationPollAuthSessionStatusRequest(client_id=self._client_id, request_id=self._request_id)

        try:
            r = await self._call_auth_web_api("PollAuthSessionStatus", msg)
        except Exception as e:
            raise LoginError("Could not get auth session status") from e

        return CAuthenticationPollAuthSessionStatusResponse.parse(r)

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
            r = await self._call_auth_web_api("GetAuthSessionInfo", msg)
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
            await self._call_auth_web_api("UpdateAuthSessionWithMobileConfirmation", msg, "meta")
        except Exception as e:
            raise LoginError("Could not update auth session with mobile confirmation") from e

    @mobile_platform
    async def approve_session(
        self,
        login_session: "SteamLoginSession",
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
        :param shared_secret: shared secret of current session authenticated account, `Steam Guard` must be enabled.
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
        await self.perform_session_mobile_confirmation(qr_url, shared_secret, approve=True, persistence=persistence)
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

        await self._init()

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
            r = await self._call_auth_web_api("BeginAuthSessionViaCredentials", msg)
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

        await self._init()

        _, device_details_data = self._get_platform_data()

        msg = CAuthenticationBeginAuthSessionViaQrRequest(
            device_details=CAuthenticationDeviceDetails(**device_details_data),
        )

        try:
            r = await self._call_auth_web_api("BeginAuthSessionViaQR", msg)
        except Exception as e:
            raise LoginError("Could not start auth session via qr") from e

        begin_session_data = CAuthenticationBeginAuthSessionViaQrResponse.parse(r)

        self._set_state(begin_session_data.request_id, begin_session_data.client_id, begin_session_data.interval)

        return URL(begin_session_data.challenge_url)  # or str?

    async def _perform_transfer(self, url: str, params: dict, steam_id: str):
        url = URL(url)
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

    async def _obtain_auth_cookies(self, refresh_token: str):
        """Using passed refresh token obtain auth cookies for `Steam` domains."""

        data = {
            "nonce": refresh_token,
            "sessionid": self._transport.session_id,
            "redir": str(STEAM_URL.COMMUNITY / "login/home/?goto="),
        }
        # here we get refresh token cookie, if it is already present Steam return same refresh token
        r = await self._transport.request(
            "POST",
            STEAM_URL.LOGIN / "jwt/finalizelogin",
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
            self._steam_id = SteamID(fin_data_steam_id)

        # perform transfers to dedicated urls in parallel to obtain access token web cookies
        await wait_coroutines(self._perform_transfer(d["url"], d["params"], fin_data_steam_id) for d in transfer_datas)

    async def _poll_status(self) -> CAuthenticationPollAuthSessionStatusResponse:
        """
        Poll session status from `Steam` until response contains auth tokens.
        Use ``asyncio.wait_for`` with ``timeout`` argument to prevent indefinite polling.
        """

        while True:
            session_status = await self._get_status()
            if session_status.refresh_token:
                return session_status

            await asyncio.sleep(self._poll_interval)  # respect steam poll interval

    async def finalize(self):
        """
        Finalize login process for current session.
        Perform `Steam` domains transfers to obtain auth web cookies.
        Must be called **after a performed action**
        or **after the current session has been approved by another login session**.
        Fill ``steam_id`` if it was not provided during initialization.

        :raises LoginError: for ordinary reasons.
        :raises ValueError: when session is not ready for finalization.
        """

        if not self._client_id or not self._request_id:
            raise ValueError("Session is not ready for finalization")

        # assume that Steam need some time to process things, just to make sure
        # N poll times + 0.15 for each attempt seconds for I/O as max wait time
        n = 2
        timeout = (self._poll_interval * n) + (0.15 * n)

        try:
            session_status = await asyncio.wait_for(self._poll_status(), timeout)
        except asyncio.TimeoutError:
            raise LoginError("Polling session status does not return tokens")
        except Exception:
            raise

        await self._obtain_auth_cookies(session_status.refresh_token)
        self._set_state()  # clear state as unneeded

    async def refresh_access_tokens(self):
        """Refreshes or obtain `access tokens` (auth cookies) for `Steam` domains. ``refresh_token`` must be present."""

        refresh_token = self.refresh_token
        if refresh_token is None or refresh_token.expired:
            raise ValueError("Refresh token is not present or expired")

        await self._obtain_auth_cookies(refresh_token.raw)

        # Backup options in case the one from above will no longer work or we decide to change behavior:
        #
        # 1. Old browser behavior:
        # GET to STEAM_URL.LOGIN / "jwt/refresh" with params {"redir": steam domain} and redirects turned on
        #
        # 2. Current browser behavior:
        # POST to STEAM_URL.LOGIN / "jwt/ajaxrefresh", with multipart {"redir": steam domain}
        # check json response for success
        # POST to 'login_url' from resp, data is {**json response, "prior": access token???}
        #
        # Steam domains: [STEAM_URL.COMMUNITY, STEAM_URL.STORE, STEAM_URL.HELP, STEAM_URL.CHECKOUT, STEAM_URL.TV]

    # @mobile_platform
    # async def renew_refresh_token(self):
    #     pass

    async def logout(self):
        """
        Perform logout of the current session.
        `Access` tokens will be invalidated while `refresh token` persist.
        """

        refresh_token = self.refresh_token
        if refresh_token is None or refresh_token.expired:
            raise ValueError("Refresh token is not present or expired")

        r = await self._transport.request(
            "POST",
            STEAM_URL.COMMUNITY / "login/logout/",
            data={"sessionid": self._transport.session_id},
            response_mode="text",
        )

        # can be the same urls from finalization
        logout_urls = [URL(url) for url in json.loads(LOGOUT_URLS_RE.search(r.content).group(1))]
        token = LOGOUT_TOKEN_RE.search(r.content).group(1)
        auth = LOGOUT_AUTH_RE.search(r.content).group(1)  # some auth code, idk

        data = {"in_transfer": 1, "auth": auth, "token": token}

        await wait_coroutines(
            self._transport.request("POST", url, data=data, response_mode="meta") for url in logout_urls
        )

    def close(self) -> Coro[None]:
        return self._transport.close()

    async def check_authenticated(self) -> bool:
        """
        Check if the current `Steam` login session is authenticated against `Steam Community` domain,
        by making request to the `Steam Community`.
        """

        if (access_token := self.access_token) is None or access_token.expired:
            return False

        r = await self._transport.request(
            "GET",
            STEAM_URL.COMMUNITY / "my",
            redirects=False,
            raise_for_status=False,
            response_mode="meta",
        )

        if r.status == 403:  # parental lock
            return True
        if r.status == 302:
            return bool(PROFILE_LOCATION_HEADER_RE.search(r.headers.get("Location", "")))

        return False
