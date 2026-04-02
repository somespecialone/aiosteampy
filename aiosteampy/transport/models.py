from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Literal, Self, Sequence, TypedDict

from yarl import URL

from ..constants import Platform
from .types import Content, Headers
from .utils import format_http_date, parse_http_date


@dataclass(slots=True)
class Cookie:
    """Minimal self-containing cookie data model supporting necessary **RFC 6265** attributes."""

    # https://www.rfc-editor.org/rfc/rfc6265#section-5.3
    # https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie

    name: str
    value: str
    domain: str  # browsers and aiohttp store origin url in domain + path so we
    path: str = "/"  # def value as path rarely used in real world

    expires: datetime | None = None  # transport should convert it from max-age if that has precedence

    # also safe defaults
    http_only: bool = True
    secure: bool = True
    same_site: Literal["Lax", "Strict", None] = None

    def to_dict(self) -> dict:
        """Convert current model to a json-safe dict."""

        data = asdict(self)
        if self.expires is not None:
            data["expires"] = format_http_date(self.expires)

        return data

    @classmethod
    def from_dict(cls, cookie: dict) -> Self:
        """Create ``Cookie`` from json-safe dict."""

        cookie = cls(**cookie)
        if cookie.expires is not None:
            cookie.expires = parse_http_date(cookie.expires)

        return cookie


@dataclass(slots=True, kw_only=True)
class TransportResponse:
    """Minimalistic HTTP response model."""

    # it is good to have light request info container (method, url, etc)
    url: URL
    """Requested URL."""
    status: int
    """HTTP status code."""
    reason: str | None = None
    """HTTP status message, if any."""

    headers: Headers
    """Parsed HTTP headers of response in **case-insensitive** mapping."""

    # decoded text, body bytes, parsed json, None in case of no read
    content: Content = None
    """Parsed response body."""

    history: Sequence[Self] = ()
    """History of redirect responses if occurred."""

    @property
    def ok(self) -> bool:
        """If response status is successful (<400)."""
        return self.status < 400


class Context(TypedDict, total=False):
    """Transport context that will be passed to a constructor."""

    user_agent: str | None
    platform: Platform
