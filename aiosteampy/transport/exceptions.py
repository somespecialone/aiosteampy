from datetime import datetime

from ..exceptions import SteamError
from .models import TransportResponse
from .utils import parse_http_date


class TransportError(Exception):
    """Generic transport error."""


class NetworkError(TransportError):
    """Unspecific network error."""


class TransportResponseError(TransportError):
    """Bad response status code."""

    def __init__(self, response: TransportResponse):
        self.response = response

    def __str__(self):
        return f"Got {self.response.status} - {self.response.reason}"


class RateLimitExceeded(TransportResponseError):
    """`Steam` decides you were in need of a bit of a rest."""

    def __str__(self):
        return "Rest a bit"


class ResourceNotModified(TransportResponseError):
    """
    Special case when `If-Modified-Since` header included
    in request headers and `Steam` response with 304 status code.
    """

    def __init__(self, response: TransportResponse):
        super().__init__(response)

        self.last_modified = parse_http_date(response.headers["Last-Modified"])
        self.expires = parse_http_date(response.headers["Expires"])

    def __str__(self):
        return f"Resource not modified. Last modified: {self.last_modified}, Expires: {self.expires}."


class Unauthenticated(TransportResponseError):
    """Auth cookies or token are missing, expired or invalid."""

    def __init__(self, response: TransportResponse | None = None):
        self.response = response

    def __str__(self):
        return "Auth cookies or token are missing, expired or invalid"
