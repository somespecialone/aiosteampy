from ..exceptions import SteamError

from .protobuf import CAuthenticationAllowedConfirmation, EAuthSessionGuardType


class LoginError(SteamError):
    """Problem with login process has been occurred."""


class ConfirmationRequired(LoginError):
    """User action (confirmation) is required to complete login process."""

    def __init__(
        self,
        confirmations: list[CAuthenticationAllowedConfirmation],
        allowed_guard_types: set[EAuthSessionGuardType],
    ):
        self.confirmations = confirmations
        self._allowed_guard_types = allowed_guard_types

    @property
    def device_code(self) -> bool:
        return EAuthSessionGuardType.k_EAuthSessionGuardType_DeviceCode in self._allowed_guard_types

    @property
    def email_code(self) -> bool:
        return EAuthSessionGuardType.k_EAuthSessionGuardType_EmailCode in self._allowed_guard_types

    @property
    def device_conf(self) -> bool:
        return EAuthSessionGuardType.k_EAuthSessionGuardType_DeviceConfirmation in self._allowed_guard_types

    @property
    def email_conf(self) -> bool:
        return EAuthSessionGuardType.k_EAuthSessionGuardType_EmailConfirmation in self._allowed_guard_types

    # machine token and legacy machine auth guard types should never be received so no need to handle them
