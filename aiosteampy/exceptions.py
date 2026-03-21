from datetime import datetime
from typing import TYPE_CHECKING, Any, Mapping

from .constants import EResult

if TYPE_CHECKING:
    from .transport import Content, Headers


class SteamError(Exception):
    """All errors coming from `Steam` side (even if cause of the error is ours)."""


class EResultError(SteamError):
    """`Steam` response with error result code."""

    def __init__(self, result: EResult, msg: str | None, data: "Content" = None):
        self.result = result
        self.msg = msg
        self.data = data

    def __str__(self):
        return f"{self.result.value} - {self.msg or self.result.name}"

    @classmethod
    def check_data(cls, data: dict):
        """Check if ``data`` contains error response from `Steam` API and raise ``EResultError`` if needed."""

        if (res := EResult(data.get("success", 0))) is not EResult.OK:
            raise cls(res, data.get("message"), data)

    @classmethod
    def check_headers(cls, headers: "Headers", data: "Content" = None):
        """Check if ``headers`` contains error response from `Steam` API and raise ``EResultError`` if needed."""

        # Valves will not be Valves if they not to forgot send header in some API endpoints
        # So OK by default if not present
        res = EResult(int(headers.get("X-eresult", 1)))
        if res is not EResult.OK:
            raise cls(res, headers.get("X-error_message"), data)


class ConfirmationRequired(SteamError):
    """Any confirmation is required to continue."""


# TODO those two need to be refactored
class NeedMobileConfirmation(ConfirmationRequired):
    """Mobile confirmation is required."""

    def __init__(self, conf_key: int | str):
        self.conf_key = conf_key


class NeedEmailConfirmation(ConfirmationRequired):
    """Email confirmation is required."""
