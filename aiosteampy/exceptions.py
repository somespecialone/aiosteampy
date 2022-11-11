from typing import TypeAlias

_json_types: TypeAlias = dict[str, ...] | list | str | int


class _BaseExc(Exception):
    def __init__(self, msg=""):
        self.msg = msg


class ApiError(_BaseExc):
    """Raises when there is a problem with calling steam web/api methods (mostly due to `success` field),
    exclude response statuses."""

    def __init__(self, msg: str, resp: _json_types = None):
        super().__init__(msg)
        self.resp = resp


class CaptchaRequired(Exception):
    """Just when steam requires captcha, simple."""


class LoginError(ApiError):
    """When failed to do login."""


class ConfirmationError(_BaseExc):
    """Errors of all related to confirmation."""


class SessionExpired(Exception):
    """Raised when session is expired, and you need to do login"""
