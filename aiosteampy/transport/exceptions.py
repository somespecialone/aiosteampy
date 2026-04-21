import json
from datetime import datetime
from typing import Self

from yarl import URL

from ..exceptions import RateLimitExceeded, Unauthenticated
from .resp import TransportResponse
from .types import Headers, JsonContent
from .utils import parse_http_date


class TransportError(Exception):
    """Generic transport error."""


class NetworkError(TransportError):
    """Unspecific network error."""


class ProxyError(NetworkError):
    """Any error with proxy."""


class TransportResponseError(TransportError):
    """Bad response status code."""

    def __init__(
        self,
        url: URL,
        status: int,
        headers: Headers,
        reason: str | None = None,
        content: bytes | None = None,
    ):
        self.url = url
        self.status = status
        self.headers = headers
        self.reason = reason
        self.content = content

    def __str__(self):
        return f" [{self.status}{f' | {self.reason}' if self.reason else ''}]"

    def json(self) -> JsonContent:
        """Parse content of response as `JSON`."""
        return json.loads(self.text()) if self.content else None

    def text(self) -> str | None:
        """Decode content of response as `string`."""
        return self.content.decode() if self.content else None

    @classmethod
    def from_response(cls, resp: TransportResponse) -> Self:
        return cls(resp.url, resp.status, resp.headers, resp.reason, resp.content)


class TooManyRequests(RateLimitExceeded, TransportResponseError):
    """`Steam` decides you were in need of a bit of a rest."""


class ResourceNotModified(TransportResponseError):
    """
    Special case when `If-Modified-Since` header included
    in request headers and `Steam` response with 304 status code.
    """

    @property
    def last_modified(self) -> datetime:
        """Last modified time of the resource."""
        return parse_http_date(self.headers["Last-Modified"])

    @property
    def expires(self) -> datetime:
        """Expiration time of the resource."""
        return parse_http_date(self.headers["Expires"])

    def __str__(self):
        return f"Resource not modified. Last modified: {self.last_modified.isoformat()}, Expires: {self.expires.isoformat()}."


class Unauthorized(Unauthenticated, TransportResponseError):
    """The user is not authorized to perform this action."""
