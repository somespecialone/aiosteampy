from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime
from http.cookies import Morsel
from typing import Any, Literal, Self

from yarl import URL

from .types import Content, Headers
from .utils import format_http_date, parse_http_date


@dataclass(slots=True)
class Cookie:
    """Universal cookie data model. **RFC 6265**."""

    # https://www.rfc-editor.org/rfc/rfc6265#section-5.3

    name: str
    value: str

    domain: str  # canonicalized host or domain attr
    path: str = "/"  # safe default
    host_only: bool = False  # if True cookie has been set with an empty domain, so it needs to be sent only to host

    expires: datetime | None = None  # transport should convert it from max-age if that has precedence

    # also safe defaults
    http_only: bool = False
    secure: bool = False
    same_site: Literal["Lax", "Strict", "None"] | None = None

    # https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie#partitioned
    partitioned: bool = False

    # meta
    comment: str = ""
    created_at: datetime | None = field(default_factory=lambda: datetime.now())
    last_accessed_at: datetime | None = None

    # non‑standard attributes or future RFCs
    extensions: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert current model to a json-safe dict."""

        data = asdict(self)
        if self.expires is not None:
            data["expires"] = format_http_date(self.expires)
        if self.created_at is not None:
            data["created_at"] = format_http_date(self.created_at)
        if self.last_accessed_at is not None:
            data["last_accessed_at"] = format_http_date(self.last_accessed_at)
        return data

    @classmethod
    def from_dict(cls, cookie: dict) -> Self:
        """Create ``Cookie`` from json-safe dict."""

        cookie = cookie.copy()
        inst = cls(
            cookie.pop("name"),
            cookie.pop("value"),
            cookie.pop("domain"),
            extensions=cookie.pop("extensions").copy(),
        )

        # safely set attr from dict if their fields are present at Cookie model
        does_not_exist = ()  # :)
        for name, value in cookie.items():
            if getattr(inst, name, does_not_exist) is not does_not_exist:
                setattr(inst, name, value)

        inst.expires = parse_http_date(inst.expires) if inst.expires else None
        inst.created_at = parse_http_date(inst.created_at) if inst.created_at else None
        inst.last_accessed_at = parse_http_date(inst.last_accessed_at) if inst.last_accessed_at else None

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
            expires=parse_http_date(m["expires"]),
            http_only=m["httponly"],
            secure=m["secure"],
            same_site=m["samesite"],
            comment=m["comment"],
        )


@dataclass(slots=True)
class TransportResponse:
    """Minimalistic HTTP response model."""

    url: URL
    """Requested URL."""
    status: int
    """HTTP status code."""
    reason: str | None = None
    """HTTP status message, if any."""

    headers: Headers = field(default_factory=dict)
    """Parsed HTTP headers of response."""

    # decoded text, body bytes, parsed json, None in case of no read
    content: Content = None
    """Response content."""

    redirects: tuple[Self, ...] = ()
    """Sequence of redirect responses if applicable."""

    @property
    def ok(self) -> bool:
        """If response status is successful (<400)."""
        return self.status < 400
