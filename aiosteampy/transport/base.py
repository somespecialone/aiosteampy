from typing import Literal, Any, overload
from abc import ABCMeta, abstractmethod
from datetime import datetime

from yarl import URL

from ..constants import CORO, EResult, STEAM_URL
from ..exceptions import EResultError, SessionExpired

from .types import Headers, Payload, Params, HttpMethod, ResponseMode, WebAPIInterface, WebAPIMethod, WebAPIVersion
from .exceptions import TransportError, ResourceNotModified, RateLimitExceeded
from .utils import format_http_date, parse_http_date
from .models import Cookie, TransportResponse

Cookies = list[Cookie]

SESSION_ID_COOKIE = "sessionid"

BASE_WEB_API_URL = URL("https://api.steampowered.com")


class BaseSteamTransport(metaclass=ABCMeta):
    """
    Wrapper around a concrete `HTTP client`.
    Intended to use only to make request to `Steam` within library.

    This class defines the contract for `HTTP transports`, standardizing how requests are sent
    and how session state (cookies and headers) is managed.

    **Responsibilities for Subclasses:**
    1.  **Cookie Management**:
      -   Transport is responsible for parsing `Set-Cookie` headers from responses
          and storing them for subsequent requests.
      -   Cookies must be persisted internally or synchronized with the underlying client's cookie jar.
    2.  **Header Management**:
      -   Transport is responsible for storing global headers (e.g. `User-Agent`)
          and merging global headers with request-specific headers.
    3.  **Request Execution**:
      -   The ``request`` method (public API) handles argument validation and error wrapping,
          delegating actual network I/O work to ``_request`` method, that subclasses must implement.
    4.  **Resource Management**:
      -   Should override ``close`` method to release resources (connections, sessions) if necessary.
    """

    __slots__ = ()

    def __init__(self, *, proxy: str | URL | None = None):
        self._proxy = URL(proxy) if proxy is not None else None

    @property
    def proxy(self) -> URL | None:
        """Proxy URL."""
        return self._proxy

    @property
    def user_agent(self) -> str | None:
        """Get user agent HTTP header."""
        return self.get_header("User-Agent")

    @user_agent.setter
    def user_agent(self, value: str | None):
        """Set user agent HTTP header."""
        self.set_header("User-Agent", value)

    @abstractmethod
    def get_headers(self) -> Headers:
        """Get HTTP headers mapping."""

    @abstractmethod
    def set_headers(self, headers: Headers) -> None:
        """Set HTTP headers. Replace existing mapping."""

    def get_header(self, name: str) -> str | None:
        """Get header value."""

        return self.get_headers().get(name)

    def set_header(self, name: str, value: str | None) -> None:
        """Set header value. If ``value`` is None, header will be removed."""

        headers = {**self.get_headers()}
        if value is None:
            headers.pop(name, None)
        else:
            headers[name] = value

        self.set_headers(headers)

    @abstractmethod
    def get_cookie(self, url: URL, name: str) -> Cookie | None:
        """Get HTTP cookie."""

    @abstractmethod
    def add_cookie(self, cookie: Cookie) -> None:
        """Set HTTP cookie. Replace existing."""

    @abstractmethod
    def remove_cookie(self, url: URL, name: str) -> None:
        """Remove HTTP cookie from transport internal storage."""

    def get_cookie_value(self, url: URL, name: str) -> str | None:
        """Get optional HTTP cookie value."""

        if cookie := self.get_cookie(url, name):
            return cookie.value

    @abstractmethod
    def get_cookies(self) -> Cookies:
        """Get all HTTP cookies from transport internal storage."""

    def add_cookies(self, cookies: Cookies) -> None:
        """Add HTTP cookies from list. Replace existing."""

        for cookie in cookies:
            self.add_cookie(cookie)

    @property
    def session_id(self) -> str | None:
        """`sessionid` cookie value for `Community` domain."""
        return self.get_session_id(STEAM_URL.COMMUNITY)

    # can't have domain literals (community, store, etc.) as url cannot be literal value :(
    # https://github.com/DoctorMcKay/node-steamcommunity/blob/d3e90f6fd3bea65b1ebc1bdaec754f99dcc8ddb3/index.js#L181
    def get_session_id(self, domain: URL) -> str | None:
        """Get `sessionid` cookie value for `Steam` ``domain``."""
        return self.get_cookie_value(domain, SESSION_ID_COOKIE)

    def set_session_id(self, value: str | None, domain: URL):
        """Set `sessionid` cookie value for `Steam` ``domain``."""

        if value is None:
            self.remove_cookie(domain, SESSION_ID_COOKIE)
        else:
            cookie = Cookie(
                SESSION_ID_COOKIE,
                value,
                domain.host,
                host_only=True,
                secure=True,
                same_site="None",
                created_at=format_http_date(datetime.now()),
            )

            self.add_cookie(cookie)

    @abstractmethod
    async def _request(
        self,
        method: HttpMethod,
        url: URL,
        *,
        params: Params | None,
        data: Payload | None,
        json: Payload | None,
        multipart: Payload | None,
        headers: Headers,
        follow_redirects: bool,
        response_mode: ResponseMode,
    ) -> TransportResponse:
        """
        Internal abstract method implementing actual HTTP request logic.

        This method is the core of the transport layer. When creating a custom transport,
        you must implement this method to bridge the abstract ``BaseSteamTransport`` interface
        with a concrete HTTP client library (like `aiohttp`, `httpx`, etc.).

        **Responsibilities for Subclasses:**

        1.  **Request Execution**: Perform the HTTP request using ``method``, ``url``, and payloads
            (``data``, ``json``, ``multipart``).
        2.  **Header Management**: Merge the request-specific `headers` argument with the
            transport's global headers.
        3.  **Cookie Persistence**: Ensure that cookies received in the response are persisted
            to transport's state by syncing them with the underlying client's cookie jar.
        4.  **Proxy Support**: Respect the ``self.proxy`` setting if configured.
        5.  **Response Formatting**: return filled ``TransportResponse`` object containing the processed response body
            according to the ``response_mode`` argument.
        """

    @overload
    async def request(
        self,
        method: HttpMethod,
        url: URL,
        *,
        params: Params | None = ...,
        data: Payload | None = ...,
        headers: Headers = ...,
        follow_redirects: bool = ...,
        raise_for_status: bool = ...,
        response_mode: ResponseMode = ...,
    ) -> TransportResponse: ...

    @overload
    async def request(
        self,
        method: HttpMethod,
        url: URL,
        *,
        params: Params | None = ...,
        json: Payload | None = ...,
        headers: Headers = ...,
        follow_redirects: bool = ...,
        raise_for_status: bool = ...,
        response_mode: ResponseMode = ...,
    ) -> TransportResponse: ...

    @overload
    async def request(
        self,
        method: HttpMethod,
        url: URL,
        *,
        params: Params | None = ...,
        multipart: Payload | None = ...,
        headers: Headers = ...,
        follow_redirects: bool = ...,
        raise_for_status: bool = ...,
        response_mode: ResponseMode = ...,
    ) -> TransportResponse: ...

    async def request(
        self,
        method: HttpMethod,
        url: URL,
        *,
        params: Params | None = None,
        data: Payload | None = None,
        json: Payload | None = None,
        multipart: Payload | None = None,
        headers: Headers = None,
        follow_redirects: bool = False,
        raise_for_status: bool = True,
        response_mode: ResponseMode = "text",
    ) -> TransportResponse:
        """
        Perform HTTP request.

        .. note:: This method along with transport intended to use only to make request to `Steam`.

        :param method: HTTP method verb.
        :param url: target URL.
        :param params: query string parameters.
        :param data: `application/x-www-form-urlencoded` payload
        :param json: JSON serializable payload.
        :param multipart: multipart form data payload.
        :param headers: specific HTTP headers for this request.
        :param follow_redirects: automatically follow redirects.
        :param raise_for_status: raise exception if response status indicates error.
        :param response_mode: return response body (as ``TransportResponse.content`` attribute) in specified format.
        :return: filled ``TransportResponse`` object.
        :raises TransportError: if unable to process response.
        :raises SessionExpired: if current login session is expired.
        """

        if sum(map(bool, (data, json, multipart))) > 1:
            raise ValueError("`data`, `json` and `multipart` args are mutually exclusive")

        try:
            resp = await self._request(
                method,
                url,
                params=params,
                data=data,
                json=json,
                multipart=multipart,
                headers=headers,
                follow_redirects=follow_redirects,
                response_mode=response_mode,
            )

        except TransportError:
            raise
        except Exception as e:
            raise TransportError from e

        # resource not modified. We would get this when "If-Modified-Since" header is provided
        if resp.status == 304 and "If-Modified-Since" in (headers or {}):
            last_modified = parse_http_date(resp.headers["Last-Modified"])
            expires = parse_http_date(resp.headers["Expires"])

            raise ResourceNotModified(last_modified, expires)

        if not follow_redirects and 300 <= resp.status < 400 and "/login" in (resp.headers.get("Location") or ()):
            raise SessionExpired from TransportError(resp)

        if resp.status == 429:
            raise RateLimitExceeded(resp)

        if raise_for_status and not resp.ok:  # handle other >=400 codes
            raise TransportError(resp)

        return resp

    async def call_web_api(
        self,
        http_method: HttpMethod,
        interface: WebAPIInterface | str,
        method: WebAPIMethod | str,
        version: WebAPIVersion = "v1",
        *,
        params: Params | None = None,
        data: Payload | None = None,
        json: Payload | None = None,
        multipart: Payload | None = None,
        headers: Headers | None = None,
        response_mode: ResponseMode = "json",
    ) -> bytes | str | Any | None:
        """
        Perform `Steam Web API` request.

        .. seealso:: https://steamapi.xpaw.me.

        :param http_method: HTTP method verb.
        :param interface: API interface name.
        :param method: API method name.
        :param version: API version. Currently only `v1` version is supported by `Steam`.
        :param params: query string parameters.
        :param data: `application/x-www-form-urlencoded` payload
        :param json: JSON serializable payload.
        :param multipart: multipart form data payload.
        :param headers: specific HTTP headers for this request.
        :param response_mode: return response body in specified format.
        :return: response body in specified format.
        :raises TransportError: if unable to process response.
        :raises SessionExpired: if current login session is expired.
        """

        try:
            r = await self.request(
                http_method,
                BASE_WEB_API_URL / interface / method / version,
                params=params,
                data=data,
                json=json,
                multipart=multipart,
                headers=headers,
                follow_redirects=False,
                raise_for_status=True,
                response_mode=response_mode,
            )
        except TransportError as e:
            if e.response and e.response.status == 403:
                raise SessionExpired from e  # also will be raised if api key or access token invalid which sad

            raise

        if r.status < 200 or r.status >= 300:
            raise TransportError(r)

        eresult = EResult(int(r.headers.get("X-eresult", 0)))

        if eresult is not EResult.OK:
            eresult_err_msg = r.headers.get("X-error_message", "Error calling Steam Web Api")
            raise EResultError(eresult, eresult_err_msg)

        return r.content

    async def close(self) -> None:
        """Close transport session and free resources."""
        pass
