from typing import Literal, Any, Mapping, Self

from dataclasses import dataclass, asdict, field
from abc import ABCMeta, abstractmethod
from http.cookies import BaseCookie, Morsel

from yarl import URL

from ..constants import CORO


HttpMethod = Literal["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]  # will be used first two, however
Headers = Mapping[str, str]
Params = Mapping[str, Any]
Payload = Mapping[str, Any]


_JSON_SAFE_COOKIE_DICT = dict[str, str | int | bool | dict[str, Any] | None]


@dataclass(slots=True, eq=False)
class Cookie:
    """Universal cookie data model. RFC 6265"""

    # https://www.rfc-editor.org/rfc/rfc6265#section-5.3

    name: str
    value: str

    domain: str  # canonicalized host or domain attr
    path: str = "/"  # safe default
    host_only: bool = False  # if True cookie has been set with an empty domain, so it needs to be sent only to host

    expires: str | None = None  # transport should convert it from max-age if that has precedence

    # also safe defaults
    http_only: bool = False
    secure: bool = False
    same_site: Literal["Lax", "Strict", "None"] | None = None

    # https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie#partitioned
    partitioned: bool = False

    # meta
    comment: str = ""
    created_at: int | None = None
    last_accessed_at: int | None = None

    # non‑standard attributes or future RFCs
    extensions: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> _JSON_SAFE_COOKIE_DICT:
        """Convert current model to a json-safe dict"""

        return asdict(self)

    @classmethod
    def from_dict(cls, cookie: _JSON_SAFE_COOKIE_DICT) -> Self:
        """Create `Cookie` from json-safe dict"""

        cookie = cookie.copy()
        inst = cls(
            cookie.pop("name"),
            cookie.pop("value"),
            cookie.pop("domain"),
            extensions=cookie.pop("extensions").copy(),
        )

        does_not_exist = ()  # :)
        for name, value in cookie.items():
            if getattr(inst, name, does_not_exist) is not does_not_exist:
                setattr(inst, name, value)

        return inst

    @classmethod
    def from_morsel(cls, m: Morsel, host_only: bool = False) -> Self:
        """Create `Cookie` from Morsel"""

        return Cookie(
            m.key,
            m.value,
            m["domain"],
            m["path"],
            host_only=host_only,
            expires=m["expires"],
            http_only=m["httponly"],
            secure=m["secure"],
            same_site=m["samesite"],
            comment=m["comment"],
        )


Cookies = list[Cookie]


@dataclass(slots=True, eq=False)
class TransportResponse:
    """HTTP response model"""

    status: int
    """HTTP status code"""

    headers: Headers
    """Parsed HTTP headers of response"""

    status_message: str | None = None
    """HTTP status message, if any"""

    content: str | bytes | Any | None = None  # decoded text, body bytes, parsed json, None
    """Response content"""

    @property
    def ok(self) -> bool:
        """If response status is successful (<400)"""
        return self.status < 400

    def raise_for_status(self):
        """Raise exception if response status indicates error"""

        if not self.ok:
            raise TransportError(self)


class TransportError(Exception):
    """Raise when transport is unable to process request or response or get error status code"""

    def __init__(self, response: TransportResponse | None = None):
        self.response = response


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

    SLOTS = ("_proxy",)

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
        return_json: bool,
        return_text: bool,
        return_bytes: bool,
        return_none: bool,
    ) -> TransportResponse | None:
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
            according to the `return_*` arguments.
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
        return_json: bool = False,
        return_text: bool = False,
        return_bytes: bool = False,
        return_none: bool = False,
    ) -> TransportResponse | None:
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
        :param return_json: return parsed JSON response body in `TransportResponse.content`.
        :param return_text: return decoded text response body in `TransportResponse.content`.
        :param return_bytes: return raw bytes response body in `TransportResponse.content`.
        :param return_none: return None from method call.
        :return: filled `TransportResponse` object.
        :raises TransportError: if unable to process response.
        """

        if sum(map(bool, [data, json, multipart])) > 1:
            raise ValueError("`data`, `json` and `multipart` args are mutually exclusive")

        if sum([return_json, return_text, return_bytes, return_none]) > 1:
            raise ValueError("Must be specified single return type")

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
                return_json=return_json,
                return_text=return_text,
                return_bytes=return_bytes,
                return_none=return_none,
            )

        except TransportError:
            raise
        except Exception as e:
            raise TransportError from e

        raise_for_status and resp.raise_for_status()

        return resp

    def get(
        self,
        url: URL,
        *,
        params: Params | None = None,
        headers: Headers | None = None,
        follow_redirects: bool = True,
        raise_for_status: bool = True,
        return_json: bool = False,
        return_text: bool = False,
        return_bytes: bool = False,
        return_none: bool = False,
    ) -> CORO[TransportResponse]:
        return self.request(
            "GET",
            url,
            params=params,
            headers=headers,
            follow_redirects=follow_redirects,
            raise_for_status=raise_for_status,
            return_json=return_json,
            return_text=return_text,
            return_bytes=return_bytes,
            return_none=return_none,
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
        return_json: bool = False,
        return_text: bool = False,
        return_bytes: bool = False,
        return_none: bool = False,
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
            return_json=return_json,
            return_text=return_text,
            return_bytes=return_bytes,
            return_none=return_none,
        )

    async def close(self):
        """Close transport session and free resources"""
        pass
