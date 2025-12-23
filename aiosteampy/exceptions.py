from datetime import datetime

from .constants import EResult


class SteamError(Exception):
    """All errors related to `Steam`."""


class EResultError(SteamError):
    """Raised when `Steam` response with error."""

    def __init__(self, result: EResult, msg: str):
        self.result = result
        self.msg = msg

    def __str__(self):
        return f"{self.result}: {self.msg}"


class LoginError(SteamError):
    """Raised when a problem with login process occurred."""


# https://github.com/DoctorMcKay/node-steamcommunity/blob/d3e90f6fd3bea65b1ebc1bdaec754f99dcc8ddb3/components/http.js#L100
class SessionExpired(SteamError):
    """Raised when session is expired, and you need to refresh access tokens."""


class RateLimitExceeded(SteamError):
    """Raised when Steam decides you were in need of a bit of a rest."""


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


# class InsufficientBalance(SteamError):
#     """"""
