from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime
from http.cookies import Morsel
from typing import Any, Literal, Self

from .types import JSON_SAFE_COOKIE_DICT, Headers
from .utils import format_http_date


# TODO date fields better be datetime
@dataclass(slots=True, eq=False)
class Cookie:
    """Universal cookie data model. **RFC 6265**."""

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
    created_at: str | None = field(default_factory=lambda: format_http_date(datetime.now()))
    last_accessed_at: str | None = None

    # non‑standard attributes or future RFCs
    extensions: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> JSON_SAFE_COOKIE_DICT:
        """Convert current model to a json-safe dict."""

        return asdict(self)

    @classmethod
    def from_dict(cls, cookie: JSON_SAFE_COOKIE_DICT) -> Self:
        """Create ``Cookie`` from json-safe dict."""

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
    def from_morsel(cls, m: Morsel, host_only: bool = True) -> Self:
        """Create ``Cookie`` from Morsel."""

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


@dataclass(slots=True, eq=False)
class TransportResponse:
    """HTTP response model."""

    status: int
    """HTTP status code."""
    status_message: str | None = None
    """HTTP status message, if any."""

    headers: Headers = field(default_factory=dict)
    """Parsed HTTP headers of response."""

    content: str | bytes | Any | None = None  # decoded text, body bytes, parsed json, None in case of no read
    """Response content."""

    @property
    def ok(self) -> bool:
        """If response status is successful (<400)."""
        return self.status < 400
