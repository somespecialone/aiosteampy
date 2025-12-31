from datetime import datetime

from ..exceptions import SteamError

from .models import TransportResponse


# TODO __str__
class TransportError(Exception):
    """Connection, os, proxy, unexpected response status, etc."""

    def __init__(self, response: TransportResponse | None = None):
        self.response = response


class RateLimitExceeded(SteamError):
    """`Steam` decides you were in need of a bit of a rest."""

    # In hope that Steam will response with Retry-After or custom header sometime in future
    def __init__(self, response: TransportResponse):
        self.response = response


class ResourceNotModified(SteamError):
    """
    Special case when `If-Modified-Since` header included
    in request headers and `Steam` response with 304 status code.
    """

    def __init__(self, last_modified: datetime, expires: datetime):
        self.last_modified = last_modified
        self.expires = expires

    def __str__(self):
        return ""
