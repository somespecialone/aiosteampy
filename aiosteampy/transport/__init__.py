"""`Steam` HTTP transport layer implementing a bridge between `Steam API` and library's core."""

from contextlib import suppress
from typing import cast

from .base import BaseSteamTransport
from .exceptions import (
    NetworkError,
    RateLimitExceeded,
    ResourceNotModified,
    TransportError,
    TransportResponseError,
    Unauthenticated,
)
from .impl.aiohttp import AiohttpTransport
from .models import Cookie, TransportResponse
from .types import Content, Headers, HttpMethod, Params, Payload, ResponseMode
from .utils import format_http_date, parse_http_date

DefaultSteamTransport = cast(type[BaseSteamTransport], AiohttpTransport)

with suppress(ImportError):
    from .impl.wreq import WreqTransport

    DefaultSteamTransport = cast(type[BaseSteamTransport], WreqTransport)
