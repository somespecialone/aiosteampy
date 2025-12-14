from typing import Literal
from abc import ABCMeta, abstractmethod

from yarl import URL

from .types import Headers, Payload, Params, HttpMethod
from .exceptions import TransportError
from .models import Cookie, TransportResponse

from ..constants import CORO


Cookies = list[Cookie]
ResponseMode = Literal["bytes", "json", "text", "meta"]  # Enum is not worth it


class BaseHTTPTransport(metaclass=ABCMeta):
    """
    Agnostic and abstract wrapper around a concrete HTTP client.

    This class defines the contract for HTTP transports, standardizing how requests are sent
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
      -   The `request` method (public API) handles argument validation and error wrapping,
          delegating actual network I/O work to `_request` method, that subclasses must implement.

    4.  **Resource Management**:
      -   Should override `close()` to release resources (connections, sessions) if necessary.
    """

    __slots__ = ()

    def __init__(self, *, proxy: str | URL | None = None):
        self._proxy = URL(proxy) if proxy is not None else None

    @property
    def proxy(self) -> URL | None:
        """Proxy URL"""
        return self._proxy

    @property
    def user_agent(self) -> str | None:
        """Get user agent HTTP header"""
        return self.get_header("User-Agent")

    @user_agent.setter
    def user_agent(self, value: str | None):
        """Set user agent HTTP header"""
        self.set_header("User-Agent", value)

    @abstractmethod
    def get_headers(self) -> Headers:
        """Get HTTP headers mapping"""

    @abstractmethod
    def set_headers(self, headers: Headers):
        """Set HTTP headers. Replace existing mapping"""

    def get_header(self, name: str) -> str | None:
        """Get header value"""

        return self.get_headers().get(name)

    def set_header(self, name: str, value: str | None):
        """Set header value. If `value` is None, header will be removed"""

        headers = {**self.get_headers()}
        if value is None:
            headers.pop(name, None)
        else:
            headers[name] = value

        self.set_headers(headers)

    @abstractmethod
    def get_cookie(self, url: URL, name: str) -> Cookie | None:
        """Get HTTP cookie"""

    @abstractmethod
    def add_cookie(self, cookie: Cookie):
        """Set HTTP cookie. Replace existing"""

    @abstractmethod
    def remove_cookie(self, url: URL, name: str):
        """Remove HTTP cookie from transport internal storage"""

    def get_cookie_value(self, url: URL, name: str) -> str | None:
        """Get optional HTTP cookie value"""

        if cookie := self.get_cookie(url, name):
            return cookie.value

    @abstractmethod
    def get_cookies(self) -> Cookies:
        """Get all HTTP cookies from transport internal storage"""

    def add_cookies(self, cookies: Cookies):
        """Add HTTP cookies from list. Replace existing"""

        for cookie in cookies:
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
        you must implement this method to bridge the abstract `BaseHTTPTransport` interface
        with a concrete HTTP client library (like `aiohttp`, `httpx`, etc.).

        **Responsibilities for Subclasses:**

        1.  **Request Execution**: Perform the HTTP request using `method`, `url`, and payloads
            (`data`, `json`, `multipart`).
        2.  **Header Management**: Merge the request-specific `headers` argument with the
            transport's global headers.
        3.  **Cookie Persistence**: Ensure that cookies received in the response are persisted
            to transport's state by syncing them with the underlying client's cookie jar.
        4.  **Proxy Support**: Respect the `self.proxy` setting if configured.
        5.  **Response Formatting**: return filled `TransportResponse` object containing the processed response body
            according to the `response_mode*` argument.
        """

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
        follow_redirects: bool = True,
        raise_for_status: bool = True,
        response_mode: ResponseMode = "bytes",
    ) -> TransportResponse:
        """
        Perform HTTP request.

        :param method: HTTP method verb.
        :param url: target URL.
        :param params: query string parameters.
        :param data: 'application/x-www-form-urlencoded' payload
        :param json: JSON serializable payload.
        :param multipart: multipart form data payload.
        :param headers: specific HTTP headers for this request.
        :param follow_redirects: automatically follow redirects.
        :param raise_for_status: raise exception if response status indicates error.
        :param response_mode: return response body (as `content` attribute) in specified format.
        :return: filled `TransportResponse` object.
        :raises TransportError: if unable to process response.
        """

        if sum(map(bool, [data, json, multipart])) > 1:
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

        if raise_for_status and not resp.ok:
            raise TransportError(resp)

        return resp

    def get(
        self,
        url: URL,
        *,
        params: Params | None = None,
        headers: Headers | None = None,
        follow_redirects: bool = True,
        raise_for_status: bool = True,
        response_mode: ResponseMode = "bytes",
    ) -> CORO[TransportResponse]:
        return self.request(
            "GET",
            url,
            params=params,
            headers=headers,
            follow_redirects=follow_redirects,
            raise_for_status=raise_for_status,
            response_mode=response_mode,
        )

    def post(
        self,
        url: URL,
        *,
        data: Payload | None = None,
        json: Payload | None = None,
        multipart: Payload | None = None,
        headers: Headers | None = None,
        follow_redirects: bool = True,
        raise_for_status: bool = True,
        response_mode: ResponseMode = "bytes",
    ) -> CORO[TransportResponse]:
        return self.request(
            "POST",
            url,
            data=data,
            json=json,
            multipart=multipart,
            headers=headers,
            follow_redirects=follow_redirects,
            raise_for_status=raise_for_status,
            response_mode=response_mode,
        )

    async def close(self):
        """Close transport session and free resources"""
        pass
