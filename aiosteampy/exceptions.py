from datetime import datetime
from typing import Mapping

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

    @classmethod
    def check_data(cls, data: dict, def_msg: str = ""):
        """Check if ``data`` contains error response from `Steam` API and raise ``EResultError`` if needed."""

        if (eresult := EResult(data.get("success", 0))) is not EResult.OK:
            raise cls(eresult, data.get("message", def_msg))

    @classmethod
    def check_headers(cls, headers: Mapping[str, str], def_msg: str = ""):
        """Check if ``headers`` contains error response from `Steam` API and raise ``EResultError`` if needed."""

        if (eres := EResult(int(headers.get("X-eresult", 0)))) is not EResult.OK:
            err_msg = headers.get("X-error_message", def_msg)
            raise EResultError(eres, err_msg)


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
