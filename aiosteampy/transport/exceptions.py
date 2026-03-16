from datetime import datetime

from ..exceptions import SteamError
from .models import TransportResponse


class TransportError(Exception):
    """Generic transport error."""


class NetworkError(TransportError):
    """Unspecific network error."""


class TransportResponseError(TransportError):
    """Bad response status code."""

    def __init__(self, response: TransportResponse):
        self.response = response

    def __str__(self):
        return f"Got {self.response.status} - {self.response.reason}."


class RateLimitExceeded(SteamError):
    """`Steam` decides you were in need of a bit of a rest."""

    # In hope that Steam will response with Retry-After or custom header sometime in future
    def __init__(self, response: TransportResponse):
        self.response = response

    def __str__(self):
        return "Rest a bit."


class ResourceNotModified(SteamError):
    """
    Special case when `If-Modified-Since` header included
    in request headers and `Steam` response with 304 status code.
    """

    def __init__(self, last_modified: datetime, expires: datetime):
        self.last_modified = last_modified
        self.expires = expires

    def __str__(self):
        return f"Resource not modified. Last modified: {self.last_modified}, Expires: {self.expires}."
