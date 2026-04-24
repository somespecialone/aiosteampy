from collections.abc import Sequence
from dataclasses import dataclass
from typing import Self

from yarl import URL

from .types import Content, Headers


@dataclass(slots=True, kw_only=True)
class TransportResponse:
    """Minimalistic HTTP response model."""

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
