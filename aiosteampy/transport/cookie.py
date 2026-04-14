from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Literal, Self

from .utils import format_http_date, parse_http_date


@dataclass(slots=True)
class Cookie:
    """Minimal self-containing cookie data model supporting necessary **RFC 6265** attributes."""

    # https://www.rfc-editor.org/rfc/rfc6265#section-5.3
    # https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie

    name: str
    value: str = field(repr=False)
    domain: str  # browsers and aiohttp store origin url in domain + path so we
    path: str = "/"  # def value as path rarely used in real world

    expires: datetime | None = None  # transport should convert it from max-age if that has precedence

    # also safe defaults
    http_only: bool = True
    secure: bool = True
    same_site: Literal["Lax", "Strict", None] = None

    def serialize(self) -> dict:
        """Convert to a `JSON-safe` dict."""

        data = asdict(self)
        if self.expires is not None:
            data["expires"] = format_http_date(self.expires)

        return data

    @classmethod
    def deserialize(cls, serialized: dict) -> Self:
        """Create ``Cookie`` from `JSON-safe` dict."""

        serialized = serialized.copy()
        if serialized["expires"] is not None:
            serialized["expires"] = parse_http_date(serialized["expires"])

        return cls(**serialized)
