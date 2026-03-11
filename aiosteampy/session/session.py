import asyncio
from base64 import b64encode
from collections.abc import Awaitable
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Literal, TypeVar

from betterproto2 import Message
from yarl import URL

from ..constants import STEAM_URL
from ..id import SteamID
from ..transport import (
    BaseSteamTransport,
    Cookie,
    ResponseMode,
    TransportError,
    TransportResponse,
    format_http_date,
)
from ..web_api import HttpMethod, SteamWebAPI
from .exceptions import *
from .models import SteamJWT
from .protobuf import *
from .utils import encrypt_password, generate_session_id, parse_qr_challenge_url

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

I_AUTH_API_BASE_URL = STEAM_URL.WEB_API / "IAuthenticationService"
LOGIN_URL = URL("https://login.steampowered.com")
SESSION_ID_COOKIE = "sessionid"


# replace this with mobile_platform[F] syntax after updating python to 3.12
_F = TypeVar("_F", bound=Callable[..., Any])


def mobile_platform(func: _F) -> _F:
    @wraps(func)
    def wrapper(self: "SteamSession", *args, **kwargs):
        if not self.is_mobile:
            raise ValueError("This method is only supported for session with mobile app platform type")
        return func(self, *args, **kwargs)

    return wrapper


class SteamSession:
    __slots__ = (
        "_platform_type",
        "_api",
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
            - Call ``refresh_access_token`` to request new access token if you need it.

        After successful finalization or restoration, the *tokens* are set and session
        can be used to obtain `Steam` websites cookies with ``obtain_cookies`` method.

        :param refresh_token: previously obtained and valid `refresh token` for the account.
            If specified, ``steam_id`` and ``platform`` properties will be set automatically,
            while ``platform_type`` argument ignored.
        :param platform_type: The platform type for which the client is being initialized.
            Defaults to ``WebBrowser``. Must not be ``SteamClient``.
        :param transport: A custom transport instance implementing the required
            HTTP communication interface. If provided, ``proxy`` cannot also be set.
        :param proxy: A proxy URL to route HTTP requests through when using the *default HTTP transport*.
        :raises ValueError: If unsupported platform type is used or invalid argument combinations are provided.
        """

        if platform_type is EAuthTokenPlatformType.k_EAuthTokenPlatformType_SteamClient:
            raise ValueError("Steam Client platform is not supported")

        self._api = SteamWebAPI(transport=transport, proxy=proxy)

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

            if refresh_token.is_access_token:
                raise ValueError("Provided token is an access token, not a refresh token")

            if refresh_token.for_web:
                platform_type = EAuthTokenPlatformType.k_EAuthTokenPlatformType_WebBrowser

                self._set_refresh_token(refresh_token)

            elif refresh_token.for_mobile:
                platform_type = EAuthTokenPlatformType.k_EAuthTokenPlatformType_MobileApp
            else:  # client
                raise ValueError("Provided token issued for Steam Client platform which is not supported")

            self._steam_id = refresh_token.subject
            self._refresh_token = refresh_token

        self._platform_type = platform_type

        if self.is_mobile:  # add mobile app specific user agent and cookie
            self._api.transport.user_agent = "okhttp/4.9.2"
            self._api.transport.add_cookie(Cookie("mobileClientVersion", "777777 3.10.3", STEAM_URL.WEB_API.host))
            self._api.transport.add_cookie(Cookie("mobileClient", "android", STEAM_URL.WEB_API.host))

    @property
    def platform(self) -> EAuthTokenPlatformType:
        return self._platform_type

    @property
    def is_mobile(self) -> bool:
        """Whether session is initialized with mobile app platform type."""
        return self._platform_type is EAuthTokenPlatformType.k_EAuthTokenPlatformType_MobileApp

    @property
    def is_web(self) -> bool:
        """Whether session is initialized with web browser platform type."""
        return self._platform_type is EAuthTokenPlatformType.k_EAuthTokenPlatformType_WebBrowser

    @property
    def web_api(self) -> SteamWebAPI:
        return self._api

    @property
    def transport(self) -> BaseSteamTransport:
        return self._api.transport

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
        *Web* `access token` at the current moment can be used only for `Steam Web API`.
        """
        return self._access_token

    @property
    def refresh_token(self) -> SteamJWT | None:
        """Refresh token. Required to renew `access token` or obtaining `auth cookies`."""
        return self._refresh_token

    @property
    def session_id(self) -> str | None:
        """`sessionid` cookie value."""
        return self._session_id

    def _set_state(self, request_id=b"", client_id=0, poll_interval=0.0):
        self._request_id = request_id
        self._client_id = client_id
        self._poll_interval = poll_interval

    def _set_access_token(self, token: str | SteamJWT):
        """Parse access token string, set session and web api attributes."""

        if not isinstance(token, SteamJWT):
            token = SteamJWT.parse(token)

        self._access_token = token
        self._api._access_token = token

    def _set_refresh_token(self, token: str | SteamJWT):
        """Parse refresh token string, create cookie if necessary."""

        if not isinstance(token, SteamJWT):
            token = SteamJWT.parse(token)

        if token.for_web:  # set cookie if session is for web
            self._refresh_token = token
            cookie = Cookie(
                STEAM_REFRESH_TOKEN_COOKIE,
                token.cookie_value,
                LOGIN_URL.host,
                expires=format_http_date(token.expires_at),  # token expire value instead of 400 days from browser
                host_only=True,
                http_only=True,
                secure=True,
                same_site="None",
            )

            self._api.transport.add_cookie(cookie)

    async def _auth_web_api(
        self,
        http_method: HttpMethod,
        api_method: str,
        protobuf: Message,
        response_mode: ResponseMode = "bytes",
    ) -> bytes:
        params = None
        multipart = None

        protobuf_data = {"input_protobuf_encoded": b64encode(bytes(protobuf)).decode()}

        if http_method == "GET":
            params = {**(params or {}), **protobuf_data}
            if self.is_mobile:
                params |= {"origin": "SteamMobile"}

        else:  # POST
            multipart = {**(multipart or {}), **protobuf_data}

        headers = {**API_HEADERS}
        if self.is_web:
            headers |= BROWSER_HEADERS

        return await self._api.request(
            http_method,
            "IAuthenticationService/" + api_method,
            params=params,
            multipart=multipart,
            headers=headers,
            response_mode=response_mode,
        )

    def _get_platform_data(self, device_name: str | None) -> tuple[str, CAuthenticationDeviceDetails]:
        """Get platform data for `Steam` authentication request. Return `website id` and `device details`."""

        if device_name is None:
            from importlib.metadata import version

            device_name = f"Aiosteampy/{version('aiosteampy')}"

        if self.is_web:
            return "Community", CAuthenticationDeviceDetails(
                device_friendly_name=device_name,
                platform_type=self._platform_type,
            )
        else:
            return "Mobile", CAuthenticationDeviceDetails(
                device_friendly_name=device_name,
                platform_type=self._platform_type,
                os_type=-500,  # Android Unknown from EOSType,
                gaming_device_type=528,
            )

    async def _get_rsa_data(self, account_name: str) -> tuple[int, int, int]:
        """Get rsa data (pub. key mod, pub. key exp, ts) from `Steam`."""

        msg = CAuthenticationGetPasswordRsaPublicKeyRequest(account_name=account_name)

        try:
            r = await self._auth_web_api("GET", "GetPasswordRSAPublicKey", msg)
            resp = CAuthenticationGetPasswordRsaPublicKeyResponse.parse(r)

        except Exception as e:
            raise LoginError("Could not obtain rsa data from Steam") from e

        return (
            int(resp.publickey_mod, 16),
            int(resp.publickey_exp, 16),
            resp.timestamp,
        )

    async def _update_session_with_guard_code(
        self,
        auth_code: str,
        code_type: Literal[
            EAuthSessionGuardType.k_EAuthSessionGuardType_DeviceCode,
            EAuthSessionGuardType.k_EAuthSessionGuardType_EmailCode,
        ],
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
            await self._auth_web_api("POST", "UpdateAuthSessionWithSteamGuardCode", msg, "meta")
        except Exception as e:
            raise LoginError("Could not update auth session with Steam Guard code") from e

    def submit_device_code(self, auth_code: str) -> Awaitable[None]:
        """
        Update current session with `device Steam Guard` code.
        Equivalent of entering `Steam Guard` code during login process page and submitting after.

        :param auth_code: `Steam Guard` two-factor (TOTP) code.
        :raises LoginError: for ordinary reasons.
        :raises ValueError: when session is not initialized.
        """

        return self._update_session_with_guard_code(auth_code, EAuthSessionGuardType.k_EAuthSessionGuardType_DeviceCode)

    def submit_email_code(self, auth_code: str) -> Awaitable[None]:
        """
        Update current session with `email Steam Guard` code.
        Equivalent of entering `Steam Guard` code during login process page and submitting after.

        :param auth_code: `Steam Guard` two-factor (TOTP) code.
        :raises LoginError: for ordinary reasons.
        :raises ValueError: when session is not initialized.
        """

        return self._update_session_with_guard_code(auth_code, EAuthSessionGuardType.k_EAuthSessionGuardType_EmailCode)

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
            r = await self._auth_web_api("POST", "GetAuthSessionInfo", msg)
        except Exception as e:
            raise LoginError("Could not get auth session info") from e

        return CAuthenticationGetAuthSessionInfoResponse.parse(r)

    @mobile_platform
    async def update_session_with_mobile_confirmation(
        self,
        version: int,
        client_id: int,
        signature: bytes,
        *,
        confirm: bool = True,
        persistence: bool = True,
    ):
        """
        Send other `login session` confirmation to `Steam`.

        :param version: version. Can be extracted from challenge QR.
        :param client_id: client id. Also can be extracted from challenge QR.
        :param signature: required crypto signature. Can be made with ``TwoFactorSigner``.
        :param confirm: whether to confirm the session or not.
        :param persistence: should `session` be persistent.
        :raises LoginError: for ordinary reasons.
        """

        if not self._steam_id:
            raise ValueError("Current session must be authenticated")

        msg = CAuthenticationUpdateAuthSessionWithMobileConfirmationRequest(
            version=version,
            client_id=client_id,
            steamid=self._steam_id.id64,
            signature=signature,
            confirm=confirm,
            persistence=ESessionPersistence(int(persistence)),
        )

        try:
            await self._auth_web_api("POST", "UpdateAuthSessionWithMobileConfirmation", msg, "meta")
        except Exception as e:
            raise LoginError("Could not update auth session with mobile confirmation") from e

    async def with_credentials(
        self,
        account_name: str,
        password: str,
        *,
        persistence: bool = True,
        device_friendly_name: str | None = None,
    ):
        """
        Begin authentication `session` with credentials.
        If login attempt requires confirmation ``ConfirmationRequired`` exception will be raised.
        ``finalize`` method must be called after.

        Equivalent of entering ``username`` and ``password`` on `Steam` website login page and submitting after.

        :param account_name: username.
        :param password: password.
        :param persistence: should `session` be persistent.
        :param device_friendly_name: name of the device used for authentication.
            Should be unique, identifiable, and human readable. Used when managing account sessions.
        :raises LoginError: for ordinary reasons.
        :raises ConfirmationRequired: when `Steam` requires performing  additional confirmation (email, device, etc.).
        """

        pub_mod, pub_exp, rsa_ts = await self._get_rsa_data(account_name)
        website_id, device_details = self._get_platform_data(device_friendly_name)

        msg = CAuthenticationBeginAuthSessionViaCredentialsRequest(
            account_name=account_name,
            encrypted_password=encrypt_password(password, pub_mod, pub_exp),
            encryption_timestamp=rsa_ts,
            remember_login=persistence,
            persistence=ESessionPersistence(int(persistence)),
            website_id=website_id,
            device_details=device_details,
            # language=0,
            # qos_level=2,
        )

        try:
            r = await self._auth_web_api("POST", "BeginAuthSessionViaCredentials", msg)
        except Exception as e:
            raise LoginError("Could not begin auth session via credentials") from e

        res = CAuthenticationBeginAuthSessionViaCredentialsResponse.parse(r)
        if not res.allowed_confirmations:
            raise LoginError("No allowed confirmations!")

        self._steam_id = SteamID(res.steamid)  # required for submitting
        self._set_state(res.request_id, res.client_id, res.interval)

        allowed_guard_types = tuple(conf.confirmation_type for conf in res.allowed_confirmations)

        if EAuthSessionGuardType.k_EAuthSessionGuardType_None not in allowed_guard_types:  # confirmation required
            raise ConfirmationRequired(res.allowed_confirmations, allowed_guard_types)

    async def login_with_credentials(
        self,
        account_name: str,
        password: str,
        device_steam_guard_code: str | Callable[[], str],
        *,
        persistence: bool = True,
        device_friendly_name: str | None = None,
    ):
        """
        Perform full login process with credentials for account that requires `device code` confirmation.
        Will ``finalize`` current `session` on success.

        :param account_name: username.
        :param password: password.
        :param device_steam_guard_code: two-factor/auth code.
            Can be generated using ``TwoFactorSigner`` or copied from the `Steam mobile app`.
            A ``callable`` factory is preferred as the `device code` will be
            generated as close to the submission moment as possible.
        :param persistence: should `session` be persistent.
        :param device_friendly_name: name of the device used for authentication.
            Should be unique, identifiable, and human readable. Used when managing account sessions.
        :raises LoginError: for ordinary reasons.
        :raises ValueError: when `Steam` requires performing  additional confirmation (email, device, etc.).
        """

        try:
            await self.with_credentials(
                account_name,
                password,
                persistence=persistence,
                device_friendly_name=device_friendly_name,
            )
        except ConfirmationRequired as e:
            if e.device_code:
                if callable(device_steam_guard_code):  # callback or factory
                    device_steam_guard_code = device_steam_guard_code()

                await self.submit_device_code(device_steam_guard_code)
            else:
                raise ValueError("Confirmation other than device Steam Guard code is required") from e

        await self.finalize()  # if device code requested or nothing happens :)

    async def with_qr(
        self,
        device_friendly_name: str | None = None,
    ) -> tuple[int, int, list[CAuthenticationAllowedConfirmation], str]:
        """
        Begin authentication `session` with auth QR.
        Produce QR auth url that needs to be scanned with `Steam App` on a mobile device
        or using another `login session` (look at ``approve_session`` method).

        :param device_friendly_name: name of the device used for authentication.
            Should be unique, identifiable, and human readable. Used when managing account sessions.
        :return: version, client id, list of allowed confirmations, QR challenge url.
        :raises LoginError: for ordinary reasons.
        :raises ValueError: when `session` has mobile app platform type.
        """

        if self._platform_type is EAuthTokenPlatformType.k_EAuthTokenPlatformType_MobileApp:
            raise ValueError("This method is not supported for mobile app platform type")

        _, device_details = self._get_platform_data(device_friendly_name)

        msg = CAuthenticationBeginAuthSessionViaQrRequest(device_details=device_details)

        try:
            r = await self._auth_web_api("POST", "BeginAuthSessionViaQR", msg)
        except Exception as e:
            raise LoginError("Could not start auth session via qr") from e

        res = CAuthenticationBeginAuthSessionViaQrResponse.parse(r)

        self._set_state(res.request_id, res.client_id, res.interval)

        return res.version, res.client_id, res.allowed_confirmations, res.challenge_url

    async def _get_status(self) -> CAuthenticationPollAuthSessionStatusResponse:
        """Get current session status."""

        msg = CAuthenticationPollAuthSessionStatusRequest(client_id=self._client_id, request_id=self._request_id)

        try:
            r = await self._auth_web_api("POST", "PollAuthSessionStatus", msg)
        except Exception as e:
            raise LoginError("Could not get auth session status") from e

        return CAuthenticationPollAuthSessionStatusResponse.parse(r)

    async def _poll_status(self):
        """
        Poll session status with interval until response with refresh token wll be received.
        Will populate `access and refresh tokens`, `steam_id`.
        Use ``asyncio.wait_for`` with ``timeout`` to prevent infinite polling.
        """

        while True:
            loop = asyncio.get_running_loop()
            start = loop.time()
            status = await self._get_status()
            if status.refresh_token:
                self._account_name = status.account_name
                self._set_refresh_token(status.refresh_token)
                self._set_access_token(status.access_token)  # will throw error if there is no access token

                # if we start with qr we come here without id
                if not self._steam_id:
                    self._steam_id = self._refresh_token.subject

                return

            end = loop.time()
            await asyncio.sleep(self._poll_interval - (end - start))  # respect steam interval and avoid drift

    async def finalize(self) -> tuple[SteamJWT, SteamJWT]:
        """
        Finalize login process for current `session` by obtaining `tokens`.
        Fill ``steam_id`` if it was not provided during initialization.

        Must be called after a **performed action**
        or after the current `session` has been **approved**.

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

    async def _perform_transfer(self, url: URL, params: dict, steam_id: str) -> TransportResponse:
        i = 0
        while True:  # little bit of tenacity here
            try:
                return await self._api.transport.request(
                    "POST",
                    url,
                    multipart={**params, "steamID": steam_id},
                    response_mode="meta",
                )

            except TransportError as e:
                await asyncio.sleep(0.55)
                i += 1
                if i == 3:
                    raise LoginError(f"Could not perform transfer to '{url}' for '{steam_id}'") from e

    async def _finalize_login(self) -> list[Cookie]:
        """Finalize `Steam` websites login process. Obtain and return web auth cookies."""

        data = {
            "nonce": self._refresh_token.raw,
            "sessionid": self._session_id,
            "redir": str(STEAM_URL.COMMUNITY / "login/home/?goto="),
        }
        # Steam will set refresh token cookie there
        r = await self._api.transport.request(
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

        # rewrite sessionid, get auth cookies, set access token
        for url, d in zip(auth_urls, transfer_datas):
            cookies.append(self._set_session_id_cookie(url))

            access_token_cookie = self._api.transport.get_cookie(url.with_path("/"), STEAM_ACCESS_TOKEN_COOKIE)
            if access_token_cookie.domain == STEAM_URL.COMMUNITY.host:
                self._set_access_token(SteamJWT.from_cookie_value(access_token_cookie.value))

            cookies.append(access_token_cookie)

        return cookies

    def _set_session_id_cookie(self, domain: URL) -> Cookie:
        """Set session id cookie."""

        cookie = Cookie(
            SESSION_ID_COOKIE,
            self._session_id,
            domain.host,
            host_only=True,
            secure=True,
            same_site="None",
        )

        self._api.transport.add_cookie(cookie)

        return cookie

    def _set_access_token_cookie(self, domain: URL) -> Cookie:
        """Set access token cookie."""

        cookie = Cookie(
            STEAM_ACCESS_TOKEN_COOKIE,
            self._access_token.cookie_value,
            domain.host,
            expires=format_http_date(self._access_token.expires_at),
            host_only=True,
            http_only=True,
            secure=True,
            same_site="None",
        )

        self._api.transport.add_cookie(cookie)

        return cookie

    async def obtain_cookies(self) -> list[Cookie]:
        """
        Obtain auth cookies for `Steam` websites using ``refresh_token``.
        Rewrite existing ``access_token`` with a new one.
        Store resulting cookies in the underlying ``transport`` cookie jar.

        :return: list of auth cookies including session id.
        """

        if self._refresh_token is None:
            raise ValueError("Session is not finalized or refresh token is not set")

        if self._session_id is None:  # generate session id by ourselves to avoid another request
            self._session_id = generate_session_id()

        if self.is_web:
            return await self._finalize_login()

        else:
            if self._access_token is None or self._access_token.expired:
                await self._generate_access_token_for_app(False)

            cookies = []
            # presumably urls from _finalize_login
            for url in [STEAM_URL.COMMUNITY, STEAM_URL.STORE, STEAM_URL.HELP, STEAM_URL.CHECKOUT, STEAM_URL.TV]:
                cookies.append(self._set_session_id_cookie(url))
                cookies.append(self._set_access_token_cookie(url))

            return cookies

    async def _generate_access_token_for_web(self):
        """Request new `access` token for web platform."""

        r = await self._api.transport.request(
            "GET",
            LOGIN_URL / "jwt/refresh",
            params={"redir": str(STEAM_URL.COMMUNITY)},
            redirects=False,
        )
        location = URL(r.headers["Location"])

        await self._api.transport.request("GET", location, redirects=False)

        cookie = self._api.transport.get_cookie(location.with_path("/"), STEAM_ACCESS_TOKEN_COOKIE)
        self._set_access_token(SteamJWT.from_cookie_value(cookie.value))

    async def _generate_access_token_for_app(self, renew_refresh_token: bool = False):
        """
        Request new `access` token.
        If ``renew_refresh_token`` is set, renewal of `refresh` token will be requested.
        Whether a new `refresh` token will be actually issued is at the `Steam` discretion.
        Existed tokens will be overwritten.

        :return: `access` and `refresh` tokens.
        """

        msg = CAuthenticationAccessTokenGenerateForAppRequest(
            refresh_token=self._refresh_token.raw,
            steamid=self._steam_id.id64,
            renewal_type=ETokenRenewalType.k_ETokenRenewalType_Allow
            if renew_refresh_token
            else ETokenRenewalType.k_ETokenRenewalType_None,
        )

        r = await self._auth_web_api("POST", "GenerateAccessTokenForApp", msg)

        res = CAuthenticationAccessTokenGenerateForAppResponse.parse(r)

        self._set_access_token(res.access_token)
        if res.refresh_token and res.refresh_token != self._refresh_token.raw:
            self._set_refresh_token(res.refresh_token)

    async def refresh_access_token(self) -> SteamJWT:
        """Request new `access` token from `Steam`."""

        if self._refresh_token is None:
            raise ValueError("Refresh token is not set")

        if self.is_web:
            await self._generate_access_token_for_web()

        else:
            await self._generate_access_token_for_app(False)

        return self._access_token

    @mobile_platform
    async def renew_refresh_token(self) -> SteamJWT:
        """
        Request new `refresh` token alongside with `access` token.
        Whether a new token will be actually issued is at the `Steam` discretion.
        Existed tokens will be overwritten.

        :return: `refresh` token.
        """

        await self._generate_access_token_for_app(True)
        return self._refresh_token

    def close(self) -> Awaitable[None]:
        return self._api.transport.close()
