"""`Steam` HTTP transport layer implementing a bridge between `Steam API` and library's core."""

from typing import cast

from .base import BaseSteamTransport, Cookies
from .exceptions import (
    NetworkError,
    RateLimitExceeded,
    ResourceNotModified,
    TransportError,
    TransportResponseError,
    Unauthenticated,
)
from .impl.aiohttp import AiohttpTransport  # export default transport
from .models import Cookie, TransportResponse
from .types import Content, Headers, HttpMethod, Params, Payload, ResponseMode
from .utils import format_http_date, parse_http_date

DefaultSteamTransport = cast(type[BaseSteamTransport], AiohttpTransport)

try:
    from .impl.wreq import WreqTransport
except ImportError:
    pass
else:
    DefaultSteamTransport = cast(type[BaseSteamTransport], WreqTransport)
