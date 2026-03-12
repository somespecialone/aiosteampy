"""A module for interacting with the `Steam Web API`."""

from collections.abc import Awaitable
from typing import Any, Literal

from .constants import STEAM_URL
from .exceptions import EResultError
from .transport import AiohttpSteamTransport, BaseSteamTransport, Headers, Params, Payload, ResponseMode, TransportError

HttpMethod = Literal["GET", "POST"]
# TODO rewrite to specs with dot notation
# can be generated from https://steamapi.xpaw.me/#ISteamWebAPIUtil/GetSupportedAPIList
InterfaceMethod = Literal[
    # IEconService
    "IEconService/GetTradeHistory",
    "IEconService/GetTradeHoldDurations",
    "IEconService/GetTradeOffer",
    "IEconService/GetTradeOffers",
    "IEconService/GetTradeOffersSummary",
    "IEconService/GetTradeStatus",
    # IAuthenticationService
    "IAuthenticationService/BeginAuthSessionViaCredentials",
    "IAuthenticationService/BeginAuthSessionViaQR",
    "IAuthenticationService/GetPasswordRSAPublicKey",
    "IAuthenticationService/UpdateAuthSessionWithSteamGuardCode",
    "IAuthenticationService/PollAuthSessionStatus",
    "IAuthenticationService/GenerateAccessTokenForApp",
    "IAuthenticationService/GetAuthSessionInfo",
    "IAuthenticationService/UpdateAuthSessionWithMobileConfirmation",
    # ITwoFactorService
    "ITwoFactorService/AddAuthenticator",
    "ITwoFactorService/FinalizeAddAuthenticator",
    "ITwoFactorService/RemoveAuthenticator",
    "ITwoFactorService/QueryTime",
]
Version = Literal["v1"]


class SteamWebAPI:
    __slots__ = ("_transport", "_access_token", "_api_key")

    def __init__(
        self,
        transport: BaseSteamTransport | None = None,
        proxy: str | None = None,
        access_token: str | None = None,
        api_key: str | None = None,
    ):
        """
        `Steam Web API` client.

        :param transport: custom transport.
        :param proxy: proxy to use.
        :param access_token: access token to use for authenticated requests.
        :param api_key: `Steam Web API` key to use for authenticated requests.
        """

        if transport is not None and proxy is not None:
            raise ValueError("Proxy is not supported for custom transport")

        self._transport: BaseSteamTransport = transport or AiohttpSteamTransport(proxy=proxy)

        self._access_token = access_token
        self._api_key = api_key

    @property
    def transport(self) -> BaseSteamTransport:
        return self._transport

    @property
    def authenticated(self) -> bool:
        """Whether this client has credentials to make authenticated requests."""
        return self._access_token is not None or self._api_key is not None

    async def request(
        self,
        http_method: HttpMethod,
        api_interface_method: InterfaceMethod | str,
        api_version: Version = "v1",
        *,
        params: Params | None = None,
        data: Payload | None = None,
        # there is no api methods that accept json data supposedly
        multipart: Payload | None = None,
        headers: Headers | None = None,
        response_mode: ResponseMode = "json",
        auth: bool = False,
    ) -> bytes | str | Any | None:
        """
        Perform request.

        .. seealso:: https://steamapi.xpaw.me.

        :param http_method: HTTP method.
        :param api_interface_method: API interface & method in format `Interface/Method`.
        :param api_version: API version.
        :param auth: send credentials in request body.
        :param params: query string parameters.
        :param data: `application/x-www-form-urlencoded` payload.
        :param multipart: multipart form data payload.
        :param headers: specific HTTP headers for this request.
        :param response_mode: return response body in specified format.
        :return: response body in specified format.
        :raises TransportError: unable to process response.
        :raises EResultError: got response result code indicating error.
        """

        if auth:
            params = {**params} if params is not None else {}

            if self._access_token:  # prefer access token over api key as wider scoped
                params["access_token"] = self._access_token
            elif self._api_key:
                params["key"] = self._api_key
            else:
                raise ValueError("Auth was requested but no access token or api key is set")

        r = await self._transport.request(
            http_method,
            STEAM_URL.WEB_API / f"{api_interface_method}/{api_version}",
            params=params,
            data=data,
            multipart=multipart,
            headers=headers,
            redirects=False,
            raise_for_status=True,
            response_mode=response_mode,
        )

        if r.status < 200 or r.status >= 300:  # redirect means error
            raise TransportError(r)

        EResultError.check_headers(r.headers, "Error calling Steam Web Api")

        return r.content

    # "call" name method is reserved for future implementation with api endpoint specs

    def close(self) -> Awaitable[None]:
        return self._transport.close()
