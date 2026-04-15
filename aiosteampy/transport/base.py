from abc import ABCMeta, abstractmethod
from collections.abc import Iterable, Sequence
from typing import TypedDict, overload

from yarl import URL

from ..constants import Platform
from .cookie import Cookie
from .exceptions import ResourceNotModified, TooManyRequests, TransportError, TransportResponseError, Unauthorized
from .resp import TransportResponse
from .types import Headers, HttpMethod, Params, Payload, ResponseMode


class Context(TypedDict, total=False):
    """Transport context that will be passed to a constructor."""

    user_agent: str | None
    platform: Platform


class BaseSteamTransport(metaclass=ABCMeta):
    """
    Wrapper around a concrete `HTTP client`.
    Intended to use only to make request to `Steam` within library.

    This class defines the contract for `HTTP transports`, standardizing how requests are sent
    and how cookies is managed.

    **Responsibilities for Subclasses:**

    1. **Cookie Management**:

    - Transport is responsible for parsing `Set-Cookie` headers from
      responses and storing them for subsequent requests.
    - Cookies must be persisted internally.

    2. **Request Execution**:

    - The ``request`` method (public API) handles argument validation and error wrapping,
      delegating actual network I/O work to ``_request`` method, that subclasses must implement.
    - Response body must be returned according to ``response_mode`` argument if `status` code
      is less than 300, otherwise raw body ``bytes`` are expected.

    3. **Resource Management**:
    - Should override ``close`` method to release resources (connections, sessions) if necessary.
    """

    __slots__ = ()

    @abstractmethod
    def __init__(self, *, proxy: str | None, ctx: Context) -> None: ...

    @property
    @abstractmethod
    def proxy(self) -> str | None:
        """Proxy URL."""

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

    def has_cookie(self, url: URL, name: str) -> bool:
        """Check if HTTP cookie exists."""
        return self.get_cookie(url, name) is not None

    @abstractmethod
    def get_cookies(self) -> Sequence[Cookie]:
        """Get all HTTP cookies from transport internal storage."""

    def get_serialized_cookies(self) -> list[dict]:
        """Get all serialized cookies from transport internal storage."""
        return [c.serialize() for c in self.get_cookies()]

    def update_cookies(self, cookies: Iterable[Cookie]) -> None:
        """Update internal storage HTTP cookies. Replace existing."""

        for cookie in cookies:
            self.add_cookie(cookie)

    def update_serialized_cookies(self, cookies: Iterable[dict]) -> None:
        """Update internal storage HTTP cookies from serialized. Replace existing."""

        for cookie in cookies:
            self.add_cookie(Cookie.deserialize(cookie))

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
        redirects: bool,
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
        2.  **Header Management**: Merge the request-specific ``headers`` argument with the
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
        redirects: bool = ...,
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
        redirects: bool = ...,
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
        redirects: bool = ...,
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
        redirects: bool = False,
        raise_for_status: bool = True,
        response_mode: ResponseMode = "text",
    ) -> TransportResponse:
        """
        Perform HTTP request.

        .. note:: This method along with transport intended to use only to make request to `Steam`.

        :param method: HTTP method verb.
        :param url: target `URL`.
        :param params: query string parameters.
        :param data: `application/x-www-form-urlencoded` payload.
        :param json: JSON serializable payload.
        :param multipart: multipart form data payload.
        :param headers: specific HTTP headers for this request.
        :param redirects: automatically follow redirects.
        :param raise_for_status: raise exception if response status indicates error.
        :param response_mode: return response body (as ``TransportResponse.content`` attribute) in specified format.
        :return: filled ``TransportResponse`` object.
        :raises TransportError: ordinary reasons.
        :raises NetworkError: for network-related issues.
        :raises ResourceNotModified: 304 status code.
        :raises TooManyRequests: rate limit has been hit.
        :raises TransportResponseError: bad error code.
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
                redirects=redirects,
                response_mode=response_mode,
            )

        except TransportError:
            raise  # re-raise transport errors deliberately
        except Exception as e:
            raise TransportError from e

        if raise_for_status:
            # Steam logic
            # resource not modified. We would get this when "If-Modified-Since" header is provided
            if resp.status == 304:
                raise ResourceNotModified.from_response(resp)
            elif (300 <= resp.status < 400) and "/login" in (resp.headers.get("Location") or ()):
                raise Unauthorized.from_response(resp)
            elif resp.status == 401:  # for web api
                raise Unauthorized.from_response(resp)
            elif resp.status == 429:
                raise TooManyRequests.from_response(resp)
            elif not resp.ok:  # handle other >=400 codes
                raise TransportResponseError.from_response(resp)

        return resp

    async def close(self) -> None:
        """Close current transport and release resources."""
        pass
