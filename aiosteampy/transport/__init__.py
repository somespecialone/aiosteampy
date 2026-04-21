"""`Steam` HTTP transport layer implementing a bridge between `Steam API` and library's core."""

from contextlib import suppress
from typing import cast

from .base import BaseSteamTransport
from .cookie import Cookie
from .exceptions import (
    NetworkError,
    ProxyError,
    ResourceNotModified,
    TooManyRequests,
    TransportError,
    TransportResponseError,
    Unauthorized,
)
from .impl.aiohttp import AiohttpTransport
from .resp import TransportResponse
from .types import Content, Headers, HttpMethod, JsonContent, Params, Payload, ResponseMode
from .utils import format_http_date, parse_http_date

DefaultSteamTransport = cast(type[BaseSteamTransport], AiohttpTransport)

with suppress(ImportError):
    from .impl.wreq import WreqTransport

    DefaultSteamTransport = cast(type[BaseSteamTransport], WreqTransport)
