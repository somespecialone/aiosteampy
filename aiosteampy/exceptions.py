from datetime import datetime

from .constants import EResult


class SteamError(Exception):
    """All errors coming from `Steam` side (even if cause of the error is ours)."""


class EResultError(SteamError):
    """`Steam` API response with error."""

    def __init__(self, result: EResult, msg: str):
        self.result = result
        self.msg = msg

    def __str__(self):
        return f"{self.result}: {self.msg}"


# https://github.com/DoctorMcKay/node-steamcommunity/blob/d3e90f6fd3bea65b1ebc1bdaec754f99dcc8ddb3/components/http.js#L100
class SessionExpired(SteamError):
    """Session is expired. *Login* or *refresh of access tokens* needed."""


# TODO probably better option is to reduce next to single exception
class NeedConfirmation(SteamError):
    """Confirmation is required to complete market or trade action."""


class NeedMobileConfirmation(NeedConfirmation):
    """Mobile confirmation is required."""

    def __init__(self, conf_key: int | str):
        self.conf_key = conf_key


# Honestly, don't know how this will work
class NeedEmailConfirmation(NeedConfirmation):
    """Email confirmation is required."""
