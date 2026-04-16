import asyncio
from collections.abc import Awaitable
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Self

from yarl import URL

from ..constants import LIB_ID, EResult, Platform, SteamURL
from ..exceptions import EResultError
from ..id import SteamID
from ..transport import BaseSteamTransport, Cookie, TransportError, TransportResponse, Unauthorized
from ..webapi import SteamWebAPIClient
from ..webapi.client import API_HEADERS, BROWSER_HEADERS, COMMUNITY_ORIGIN
from ..webapi.services.auth import (
    AuthenticationServiceClient,
    CAuthenticationAllowedConfirmation,
    CAuthenticationGetAuthSessionInfoResponse,
    CAuthenticationPollAuthSessionStatusResponse,
    EAuthSessionGuardType,
    GuardCodeTypes,
)
from .exceptions import AuthCodeExpired, BadCredentials, GuardConfirmationRequired, LoginError, TooManyAttempts
from .jwt import SteamJWT
from .utils import encrypt_password, generate_session_id, parse_qr_challenge_url

ACCESS_TOKEN_COOKIE = "steamLoginSecure"
REFRESH_TOKEN_COOKIE = "steamRefresh_steam"
SESSION_ID_COOKIE = "sessionid"

QRChallengeUrl = URL | str | tuple[int, int]


# https://typing.python.org/en/latest/guides/libraries.html#annotating-decorators
def mobile_platform[F: Callable[..., Any]](func: F) -> F:
    @wraps(func)
    def wrapper(self: "SteamSession", *args, **kwargs):
        if not self.is_mobile:
            raise ValueError("This method is only supported for session with mobile app platform type")
        return func(self, *args, **kwargs)

    return wrapper


def refresh_token_required[F: Callable[..., Any]](func: F) -> F:
    @wraps(func)
    def wrapper(self: "SteamSession", *args, **kwargs):
        if self._refresh_token is None:
            raise RuntimeError("Refresh token is not set")
        return func(self, *args, **kwargs)

    return wrapper


class SteamSession:
    __slots__ = (
        "_platform",
        "_service",
        "_account_name",
        "_access_token",
        "_refresh_token",
        "_session_id",
        "_request_id",
        "_client_id",
        "_poll_interval",
        "_steam_id",
    )

    def __init__(
        self,
        access_token: str | SteamJWT | None = None,
        refresh_token: str | SteamJWT | None = None,
        *,
        platform: Platform = Platform.WEB,
        transport: BaseSteamTransport | None = None,
        proxy: str | None = None,
        _ignore_expired: bool = False,
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
            - Call ``refresh_access_token`` to request new access token if needed.

        4) **Restoration with both tokens**
            - Create session instance with valid ``access_token`` and ``refresh_token``.
            - Use it.

        After successful finalization or restoration, the *tokens* are set and session
        can be used to obtain `Steam` websites cookies with ``obtain_cookies`` method.

        :param access_token: previously obtained and valid `access token` for the account.
        :param refresh_token: previously obtained and valid `refresh token` for the account.
            If specified, ``steam_id`` and ``platform`` properties will be set automatically.
        :param platform: The platform type for which the client is being initialized.
            Defaults to `Web Browser`. Will be ignored if at least one `token` is provided.
        :param transport: A custom transport instance implementing the required
            HTTP communication interface. If provided, ``proxy`` cannot also be set.
        :param proxy: A proxy URL to route HTTP requests through when using the *default HTTP transport*.
        """

        api = SteamWebAPIClient(platform=platform, transport=transport, proxy=proxy)
        self._service = AuthenticationServiceClient(api)

        self._account_name: str | None = None
        self._access_token: SteamJWT | None = None
        self._refresh_token: SteamJWT | None = None
        self._session_id: str | None = None  # let's be less dependent on cookie and store value instead

        self._set_state()  # set transient internal state

        self._steam_id = SteamID()

        if access_token is not None and refresh_token is not None:
            # parse tokens
            if not isinstance(access_token, SteamJWT):
                access_token = SteamJWT.parse(access_token)
            if not isinstance(refresh_token, SteamJWT):
                refresh_token = SteamJWT.parse(refresh_token)

            if (access_token.for_web and refresh_token.for_mobile) or (
                access_token.for_mobile and refresh_token.for_web
            ):
                raise ValueError("Access token and refresh token are for different platforms")

            if access_token.subject != refresh_token.subject:
                raise ValueError("Access token and refresh token are for different accounts")

        if access_token is not None:
            if not isinstance(access_token, SteamJWT):
                access_token = SteamJWT.parse(access_token)

            if not _ignore_expired and access_token.expired:
                raise ValueError("Provided access token is expired")

            if access_token.is_refresh_token:
                raise ValueError("Provided access token is a refresh token")

            platform = access_token.platform
            if access_token.for_client:
                raise ValueError("Access token issued for Steam Client platform which is not supported")

            self._steam_id = access_token.subject
            self._set_access_token(access_token)

        if refresh_token is not None:
            if not isinstance(refresh_token, SteamJWT):
                refresh_token = SteamJWT.parse(refresh_token)

            if not _ignore_expired and refresh_token.expired:
                import warnings

                # issue a warning for now as early measure
                warnings.warn("Provided refresh token is expired. Are you sure you want to use it?", UserWarning)

            if refresh_token.is_access_token:
                raise ValueError("Provided refresh token is an access token")

            platform = refresh_token.platform
            if refresh_token.for_client:
                raise ValueError("Refresh token issued for Steam Client platform which is not supported")

            self._steam_id = refresh_token.subject
            self._set_refresh_token(refresh_token)

        self._platform = platform

    @property
    def platform(self) -> Platform:
        """Platform type of the session."""
        return self._platform

    @property
    def is_mobile(self) -> bool:
        """Whether session is initialized with mobile app platform type."""
        return self._platform is Platform.MOBILE

    @property
    def is_web(self) -> bool:
        """Whether session is initialized with web browser platform type."""
        return self._platform is Platform.WEB

    @property
    def service(self) -> AuthenticationServiceClient:
        """Authentication service client."""
        return self._service

    @property
    def webapi(self) -> SteamWebAPIClient:
        """`Steam Web API` client."""
        return self._service.webapi

    @property
    def transport(self) -> BaseSteamTransport:
        """HTTP transport instance."""
        return self._service.webapi.transport

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
        self._service.webapi._access_token = token.raw

    def _set_refresh_token(self, token: str | SteamJWT):
        """Parse refresh token string, create cookie if necessary."""

        if not isinstance(token, SteamJWT):
            token = SteamJWT.parse(token)

        self._refresh_token = token

        if token.for_web:  # set cookie if session is for web
            cookie = Cookie(
                REFRESH_TOKEN_COOKIE,
                token.cookie_value,
                SteamURL.LOGIN_URL.host,
                SteamURL.LOGIN_URL.path,
                expires=token.expires_at,  # token expire value instead of 400 days from browser
            )

            self._service.webapi.transport.add_cookie(cookie)

    async def _get_rsa_data(self, account_name: str) -> tuple[int, int, int]:
        """Get rsa data (public key modulus, public key exponent, ts) from `Steam`."""

        resp = await self._service.get_password_rsa_public_key(account_name)
        return (
            int(resp.publickey_mod, 16),
            int(resp.publickey_exp, 16),
            resp.timestamp,
        )

    async def submit_auth_code(self, auth_code: str, code_type: GuardCodeTypes = "device"):
        """
        Update current session with `Steam Guard` either email or device code.
        Equivalent of entering `Steam Guard` code during login process page and submitting after.

        :param auth_code: `Steam Guard` two-factor (TOTP) code.
        :param code_type: type of `Steam Guard` code to submit.
        :raises TransportError: ordinary reasons.
        :raises LoginError: ordinary reasons.
        :raises BadCredentials: when `Steam` rejects auth code.
        :raises AuthCodeExpired: when `Steam` rejects auth code due to expiration.
        """

        if not self._client_id or not self._steam_id:
            raise ValueError("Session is not initialized")
        try:
            await self._service.update_auth_session_with_steam_guard_code(
                self._client_id,
                self._steam_id,
                auth_code,
                code_type,
            )
        except EResultError as e:
            match e.result:
                case EResult.INVALID_LOGIN_AUTH_CODE | EResult.TWO_FACTOR_CODE_MISMATCH:
                    raise BadCredentials
                case EResult.EXPIRED_LOGIN_AUTH_CODE | EResult.EXPIRED:
                    raise AuthCodeExpired
                # https://github.com/SteamRE/SteamKit/blob/1061d28668437be68ed6e627f7c3024022cd33f3/SteamKit2/SteamKit2/Steam/Authentication/CredentialsAuthSession.cs#L46
                case EResult.DUPLICATE_REQUEST:
                    pass
                case other:
                    raise LoginError(f"Unknown EResult: {other.name}") from e

    @mobile_platform
    def get_session_info(self, qr: QRChallengeUrl) -> Awaitable[CAuthenticationGetAuthSessionInfoResponse]:
        """
        Get info of the other login session from `Steam`.
        Equivalent of scanning QR with `Steam App` on a mobile device,
        therefore, *must be used only from session with mobile app platform type*.

        :param qr: url from QR of session to get info. Must be from the same account.
        :return: session info.
        :raises TransportError: ordinary reasons.
        """

        if isinstance(qr, (URL, str)):
            _, client_id = parse_qr_challenge_url(qr)
        else:
            _, client_id = qr

        return self._service.get_auth_session_info(client_id)

    async def with_credentials(
        self,
        account_name: str,
        password: str,
        *,
        persistence: bool = True,
        device_friendly_name: str = LIB_ID,
    ):
        """
        Begin authentication `session` with credentials.
        If login attempt requires confirmation ``GuardConfirmationRequired`` exception will be raised.
        ``finalize`` method must be called after.

        Equivalent of entering ``username`` and ``password`` on `Steam` website login page and submitting after.

        :param account_name: username.
        :param password: password.
        :param persistence: should `session` be persistent.
        :param device_friendly_name: name of the device used for authentication.
            Should be unique, identifiable, and human readable. Used when managing account sessions.
        :raises TransportError: ordinary reasons.
        :raises LoginError: ordinary reasons.
        :raises BadCredentials: when `Steam` rejects credentials.
        :raises TooManyAttempts: when `Steam` rejects credentials due to too many attempts.
        :raises GuardConfirmationRequired: when `Steam` requires performing  additional confirmation (email, device, etc.).
        """

        pub_mod, pub_exp, rsa_ts = await self._get_rsa_data(account_name)

        try:
            resp = await self._service.begin_auth_session_via_credentials(
                account_name,
                encrypt_password(password, pub_mod, pub_exp),
                rsa_ts,
                persistence,
                device_friendly_name,
            )
        except EResultError as e:
            match e.result:
                case EResult.INVALID_PASSWORD:
                    raise BadCredentials
                case EResult.RATE_LIMIT_EXCEEDED:
                    raise TooManyAttempts
                case unknown:
                    raise LoginError(f"Unknown EResult: {unknown.name}") from e

        if not resp.allowed_confirmations:
            raise LoginError("No allowed confirmations!")

        self._steam_id = SteamID(resp.steamid)  # required for submitting
        self._set_state(resp.request_id, resp.client_id, resp.interval)

        allowed_guard_types = tuple(conf.confirmation_type for conf in resp.allowed_confirmations)

        if EAuthSessionGuardType.k_EAuthSessionGuardType_None not in allowed_guard_types:  # confirmation required
            raise GuardConfirmationRequired(resp.allowed_confirmations, allowed_guard_types)

    async def login_with_credentials(
        self,
        account_name: str,
        password: str,
        device_steam_guard_code: str | Callable[[], str],
        *,
        persistence: bool = True,
        device_friendly_name: str = LIB_ID,
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
        :raises TransportError: ordinary reasons.
        :raises BadCredentials: when `Steam` rejects credentials.
        :raises TooManyAttempts: when `Steam` rejects credentials due to too many attempts.
        :raises LoginError: ordinary reasons.
            When `Steam` requires performing  additional confirmation (email, device, etc.).
        """

        try:
            await self.with_credentials(
                account_name,
                password,
                persistence=persistence,
                device_friendly_name=device_friendly_name,
            )
        except GuardConfirmationRequired as e:
            if e.device_code:
                if callable(device_steam_guard_code):  # callback or factory
                    device_steam_guard_code = device_steam_guard_code()

                await self.submit_auth_code(device_steam_guard_code)
            else:
                raise LoginError("Confirmation other than device Steam Guard code is required") from e

        await self.finalize()  # if device code requested or nothing happens :)

    async def with_qr(
        self,
        device_friendly_name: str = LIB_ID,
    ) -> tuple[int, int, list[CAuthenticationAllowedConfirmation], str]:
        """
        Begin authentication `session` with auth QR.
        Produce QR auth url that needs to be scanned with `Steam App` on a mobile device
        or using another `login session` (look at ``approve_session`` method).

        :param device_friendly_name: name of the device used for authentication.
            Should be unique, identifiable, and human readable. Used when managing account sessions.
        :return: version, client id, list of allowed confirmations, QR challenge url.
        :raises TransportError: ordinary reasons.
        :raises LoginError: ordinary reasons.
        :raises BadCredentials: when `Steam` rejects credentials.
        :raises TooManyAttempts: when `Steam` rejects credentials due to too many attempts.
        """

        if self.is_mobile:
            raise ValueError("This method is not supported for mobile app platform type")

        try:
            resp = await self._service.begin_auth_session_via_qr(device_friendly_name)
        except EResultError as e:
            match e.result:
                case EResult.RATE_LIMIT_EXCEEDED:
                    raise TooManyAttempts
                case unknown:
                    raise LoginError(f"Unknown EResult: {unknown.name}") from e

        self._set_state(resp.request_id, resp.client_id, resp.interval)

        return resp.version, resp.client_id, resp.allowed_confirmations, resp.challenge_url

    def _get_status(self) -> Awaitable[CAuthenticationPollAuthSessionStatusResponse]:
        """Get current session status."""
        return self._service.poll_auth_session_status(self._client_id, self._request_id)

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

    async def finalize(self, *, timeout: float = 0) -> tuple[SteamJWT, SteamJWT]:
        """
        Finalize login process for current `session` by obtaining `tokens`.
        Fill ``steam_id`` if it was not provided during initialization.

        Must be called after a **performed action**
        or after the current `session` has been **approved**.

        :param timeout: max. time to spend on status polling.
            Will be based on `poll interval` received from `Steam` if not provided.
        :return: `access` and `refresh` tokens.
        :raises LoginError: timeout has been exceeded when polling for refresh token.
        """

        if not self._client_id or not self._request_id:
            raise RuntimeError("Session is not ready for finalization")

        if not timeout:
            # Let's assume that Steam need some time to process things, just to be safe
            n = 3
            timeout = (self._poll_interval * n) + (0.1 * n)

        try:
            await asyncio.wait_for(self._poll_status(), timeout)
        except asyncio.TimeoutError:
            raise LoginError(f"Timeout ({timeout}s) has been exceeded") from None

        self._set_state()  # clear state as unneeded

        return self._access_token, self._refresh_token

    async def _perform_transfer(self, url: URL, params: dict, steam_id: str) -> TransportResponse:
        i = 0
        while True:  # little bit of tenacity here
            try:
                return await self._service.webapi.transport.request(
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
            "redir": str(SteamURL.COMMUNITY / "login/home/?goto="),
        }
        # here Steam will rewrite refresh token cookie again without expiration
        r = await self._service.webapi.transport.request(
            "POST",
            SteamURL.LOGIN_URL / "jwt/finalizelogin",
            multipart=data,
            headers={**API_HEADERS, **BROWSER_HEADERS},
            response_mode="json",
        )
        rj: dict = r.content
        if rj and (error_msg := rj.get("error")):
            raise LoginError(f"Get error response when performing login finalization", error_msg)
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

        # compare stored and received refresh token and rewrite just in case
        refresh_token_cookie = self.transport.get_cookie_value(SteamURL.LOGIN_URL, REFRESH_TOKEN_COOKIE)
        if refresh_token_cookie != self.refresh_token.cookie_value:
            self._set_refresh_token(SteamJWT.from_cookie_value(refresh_token_cookie))
        else:
            self._set_refresh_token(self._refresh_token)  # rewrite cookie with expiration

        cookies = []

        # rewrite sessionid, get auth cookies, set access token
        for url, d in zip(auth_urls, transfer_datas):
            url = url.with_path("/")

            cookies.append(self._set_session_id_cookie(url))  # set & add session id cookie

            # access token cookie flow
            cookie = self.transport.get_cookie(url, ACCESS_TOKEN_COOKIE)
            token = SteamJWT.from_cookie_value(cookie.value)

            # replace expiration date of cookie (~5 years) with token expiration
            cookie.expires = token.expires_at

            self.transport.add_cookie(cookie)

            if cookie.domain == SteamURL.COMMUNITY.host:  # choose community token as main
                self._set_access_token(token)

            cookies.append(cookie)

        return cookies

    def _set_session_id_cookie(self, domain: URL) -> Cookie:
        """Set session id cookie."""

        cookie = Cookie(
            SESSION_ID_COOKIE,
            self._session_id,
            domain.host,
            domain.path,
        )

        self._service.webapi.transport.add_cookie(cookie)

        return cookie

    def _set_access_token_cookie(self, domain: URL) -> Cookie:
        """Set access token cookie."""

        cookie = Cookie(
            ACCESS_TOKEN_COOKIE,
            self._access_token.cookie_value,
            domain.host,
            domain.path,
            expires=self._access_token.expires_at,
        )

        self._service.webapi.transport.add_cookie(cookie)

        return cookie

    @refresh_token_required
    async def obtain_cookies(self) -> list[Cookie]:
        """
        Obtain auth cookies for `Steam` websites using ``refresh_token``.
        Rewrite the existing ``access_token`` with a new one if required.
        Store resulting cookies in the underlying ``transport`` cookie jar.

        :return: list of auth cookies including session id.
        :raises TransportError: ordinary reasons.
        :raises LoginError: ordinary reasons.
        """

        if self._session_id is None:  # generate session id by ourselves to avoid another request
            self._session_id = generate_session_id()

        if self.is_web:
            return await self._finalize_login()

        else:
            if self._access_token is None or self._access_token.expired:
                await self._generate_access_token_for_app(False)

            cookies = []
            # presumably urls from _finalize_login
            for url in SteamURL.DOMAINS:
                cookies.append(self._set_session_id_cookie(url))
                cookies.append(self._set_access_token_cookie(url))

            return cookies

    @property
    def cookies_are_valid(self) -> bool:
        """Check whether auth web cookies are valid (set and not expired)."""

        # potential weak point: if Steam changes login urls we can find ourselves in a situation
        # where DOMAINS > urls from Steam and cookies_are_valid will always return False
        for url in SteamURL.DOMAINS:
            access_token_cookie = self.transport.get_cookie(url, ACCESS_TOKEN_COOKIE)
            if access_token_cookie is None or (
                access_token_cookie.expires
                and access_token_cookie.expires < datetime.now(access_token_cookie.expires.tzinfo)
            ):
                return False
            if self.transport.has_cookie(url, SESSION_ID_COOKIE) is None:
                return False

        return True

    async def _generate_access_token_for_web(self) -> SteamJWT:
        """Request new `access` token for web platform."""

        try:
            r = await self._service.webapi.transport.request(
                "GET",
                SteamURL.LOGIN_URL / "jwt/refresh",
                params={"redir": COMMUNITY_ORIGIN},
                headers={**API_HEADERS, **BROWSER_HEADERS},
                redirects=False,
                response_mode="meta",
            )
        except Unauthorized as e:
            headers = e.headers
        else:
            headers = r.headers

        location = URL(headers["Location"])

        await self._service.webapi.transport.request("GET", location, redirects=False, response_mode="meta")

        cookie = self._service.webapi.transport.get_cookie(location.with_path("/"), ACCESS_TOKEN_COOKIE)
        self._set_access_token(SteamJWT.from_cookie_value(cookie.value))

        return self._access_token

    async def _generate_access_token_for_app(self, renew_refresh_token: bool = False) -> SteamJWT:
        """
        Request new `access` token.
        If ``renew_refresh_token`` is set, renewal of `refresh` token will be requested.
        Whether a new `refresh` token will be actually issued is at the `Steam` discretion.
        Existed tokens will be overwritten.
        """

        res = await self._service.generate_access_token_for_app(
            self.refresh_token.raw,
            self._steam_id,
            renew_refresh_token,
        )

        self._set_access_token(res.access_token)
        if res.refresh_token and res.refresh_token != self._refresh_token.raw:
            self._set_refresh_token(res.refresh_token)

        return self._access_token

    @refresh_token_required
    def refresh_access_token(self) -> Awaitable[SteamJWT]:
        """
        Request new `access` token from `Steam`.

        :return: `access` token.
        :raises TransportError: ordinary reasons.
        """

        if self.is_web:
            return self._generate_access_token_for_web()
        else:
            return self._generate_access_token_for_app(False)

    @mobile_platform
    @refresh_token_required
    def renew_refresh_token(self) -> Awaitable[SteamJWT]:
        """
        Request a new `refresh` token alongside with `access` token.
        Whether a new token will be actually issued is at the `Steam` discretion.
        Existed tokens will be overwritten.

        :return: `refresh` token.
        :raises TransportError: ordinary reasons.
        """

        return self._generate_access_token_for_app(True)

    def __repr__(self):
        return (
            f"{self.__class__.__name__}({self._steam_id}/{self._account_name}, {self._platform}, "
            f"{self._access_token}, {self._refresh_token})"
        )

    def serialize(self) -> dict:
        """Serialize only auth-related (tokens, cookies) `session` state to a `JSON-safe` dict."""

        return {
            "platform": self._platform,
            "access_token": self._access_token.raw if self._access_token is not None else None,
            "refresh_token": self._refresh_token.raw if self._refresh_token is not None else None,
            "steam_id": self._steam_id,
            "account_name": self._account_name,
            "session_id": self._session_id,
            "cookies": self.transport.get_serialized_cookies(),
        }

    @classmethod
    def deserialize(
        cls,
        serialized: dict,
        transport: BaseSteamTransport | None = None,
        proxy: str | None = None,
    ) -> Self:
        """Create `session` from `serialized` data. This will not verify tokens and cookies validity."""

        session = cls(
            serialized["access_token"],
            serialized["refresh_token"],
            platform=Platform(serialized["platform"]),
            transport=transport,
            proxy=proxy,
            _ignore_expired=True,
        )

        session._steam_id = SteamID(serialized["steam_id"])
        session._account_name = serialized["account_name"]
        session._session_id = serialized["session_id"]

        session.transport.update_serialized_cookies(serialized["cookies"])

        return session
