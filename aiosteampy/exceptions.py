from datetime import datetime

from .constants import EResult


class SteamError(Exception):
    """All errors related to Steam"""


class EResultError(SteamError):
    """Raised when Steam response data contain `success` field with error code"""

    def __init__(self, msg: str, result: EResult, data=None):
        self.msg = msg
        self.result = result
        self.data = data

    def __str__(self):
        return self.msg


class LoginError(SteamError):
    """Raised when a problem with login process occurred"""


# TODO What about
#  https://github.com/DoctorMcKay/node-steamcommunity/blob/1067d4572ee9d467e8f686951901c51028c5c995/components/http.js#L94
class SessionExpired(SteamError):
    """Raised when session is expired, and you need to do login"""


class RateLimitExceeded(SteamError):
    """Raised when Steam decided you were in need of a bit of a rest :)"""


class ResourceNotModified(SteamError):
    """
    Special case when `If-Modified-Since` header included
    in request headers and Steam response with 304 status code
    """

    def __init__(self, last_modified: datetime, expires: datetime):
        self.last_modified = last_modified
        self.expires = expires

    def __str__(self):
        return ""


# class InsufficientBalance(SteamError):
#     """"""
