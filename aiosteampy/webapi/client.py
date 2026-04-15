from base64 import b64encode
from collections.abc import Awaitable
from typing import Any, Literal

import betterproto2

from ..constants import LIB_ID, Platform, SteamURL
from ..exceptions import EResultError
from ..transport import (
    BaseSteamTransport,
    Cookie,
    DefaultSteamTransport,
    Headers,
    Params,
    Payload,
    ResponseMode,
    TransportResponseError,
)

HttpMethod = Literal["GET", "POST"]

API_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "cross-site",
}

COMMUNITY_ORIGIN = str(SteamURL.COMMUNITY)
BROWSER_HEADERS = {
    "Referer": COMMUNITY_ORIGIN + "/",
    "Origin": COMMUNITY_ORIGIN,
}


class SteamWebAPIClient:
    __slots__ = ("_platform", "_transport", "_access_token", "_api_key")

    def __init__(
        self,
        platform: Platform = Platform.WEB,
        transport: BaseSteamTransport | None = None,
        proxy: str | None = None,
        access_token: str | None = None,
        api_key: str | None = None,
    ):
        """
        `Steam Web API` client.

        :param platform: platform type for which client is being initialized.
            If `mobile` type is specified, specific headers and cookies will be added to transport.
        :param transport: custom transport.
        :param proxy: proxy to use.
        :param access_token: access token to use for authenticated requests.
        :param api_key: `Steam Web API` key to use for authenticated requests.
        """

        if transport is not None and proxy is not None:
            raise ValueError("Proxy is not supported for custom transport")

        self._platform = platform

        self._transport = transport or DefaultSteamTransport(
            proxy=proxy,
            ctx={"platform": platform, "user_agent": LIB_ID},
        )

        self._access_token = access_token
        self._api_key = api_key

        if self.is_mobile:
            # mobile user agent is "okhttp/4.9.2" just in case we need it
            self._transport.add_cookie(Cookie("mobileClientVersion", "777777 3.10.3", SteamURL.WEB_API.host))
            self._transport.add_cookie(Cookie("mobileClient", "android", SteamURL.WEB_API.host))

    @property
    def transport(self) -> BaseSteamTransport:
        """HTTP transport instance in use to make requests."""
        return self._transport

    @property
    def platform(self) -> Platform:
        """Platform type for which this client is initialized."""
        return self._platform

    @property
    def is_web(self) -> bool:
        """Whether this client is configured for web platform."""
        return self._platform is Platform.WEB

    @property
    def is_mobile(self) -> bool:
        """Whether this client is configured for mobile platform."""
        return self._platform is Platform.MOBILE

    @property
    def authenticated(self) -> bool:
        """Whether this client has credentials to make authenticated requests."""
        return self._access_token is not None or self._api_key is not None

    async def call(
        self,
        interface: str,
        method: str,
        version: int = 1,
        http_method: HttpMethod = "GET",
        *,
        params: Params | None = None,
        data: Payload | None = None,  # multipart by default
        # there is no api methods that accept json data supposedly
        urlencoded: Payload | None = None,
        protobuf: betterproto2.Message | bytes | None = None,
        headers: Headers | None = None,
        response_mode: ResponseMode = "json",
        # There are some methods working only with api key and vice versa, and that better be handled
        auth: bool = False,
    ) -> bytes | str | Any | None:
        """
        Perform request.

        .. seealso:: https://steamapi.xpaw.me.

        :param http_method: HTTP method.
        :param interface: API interface.
        :param method: API method.
        :param version: API version.
        :param auth: send credentials in request body.
        :param params: query string parameters.
        :param data: `multipart/form-data` payload.
        :param urlencoded: `application/x-www-form-urlencoded` data payload.
        :param protobuf: protobuf payload. If specified, will be merged with ``data`` or ``urlencoded`` payload.
            Also, ``response_mode`` will be set to ``bytes`` if it is not ``meta``.
        :param headers: specific HTTP headers for this request.
        :param response_mode: return response body in specified format.
        :return: response body in specified format.
        :raises TransportError: ordinary reasons.
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

        get_method = http_method == "GET"

        if get_method:
            params = {**params} if params is not None else {}
            # https://github.com/DoctorMcKay/node-steam-session/blob/3ac0f34fd964b3f886ba18ef4824ac43c942e030/src/transports/WebApiTransport.ts#L48
            if self.is_mobile:
                params["origin"] = "SteamMobile"
            else:  # web
                params["origin"] = COMMUNITY_ORIGIN

        if protobuf is not None:
            if response_mode != "meta":
                response_mode = "bytes"
            protobuf = b64encode(bytes(protobuf)).decode()
            if get_method:
                params["input_protobuf_encoded"] = protobuf
            else:  # POST
                if data is not None:  # send with multipart
                    data = {**data, "input_protobuf_encoded": protobuf}
                else:
                    urlencoded = {**(urlencoded or {}), "input_protobuf_encoded": protobuf}

        headers = {**(headers or {}), **API_HEADERS}
        if self.is_web:
            headers |= BROWSER_HEADERS

        r = await self._transport.request(
            http_method,
            SteamURL.WEB_API / f"{interface}/{method}/v{version}",
            params=params,
            data=urlencoded,
            multipart=data,
            headers=headers,
            redirects=False,
            raise_for_status=True,
            response_mode=response_mode,
        )

        if r.status < 200 or r.status >= 300:  # redirect means error
            raise TransportResponseError.from_response(r)

        EResultError.check_headers(r.headers, r.content)

        return r.content
