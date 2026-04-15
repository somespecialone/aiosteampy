from ..exceptions import ConfirmationRequired, RateLimitExceeded, SteamError
from ..webapi.protobufs.auth import CAuthenticationAllowedConfirmation, EAuthSessionGuardType


class LoginError(SteamError):
    """Problem with login process has been occurred."""


class BadCredentials(LoginError):
    """Provided credentials are invalid."""


class AuthCodeExpired(BadCredentials):
    """Provided `Steam Guard` code has expired."""


class TooManyAttempts(RateLimitExceeded, LoginError):
    """Too many failed login attempts."""


# If we don't need allowed confs we can separate this to 4 different exceptions at library top level
class GuardConfirmationRequired(ConfirmationRequired):
    """Confirmation is required to complete login process."""

    def __init__(
        self,
        confirmations: list[CAuthenticationAllowedConfirmation],
        allowed_guard_types: tuple[EAuthSessionGuardType, ...],
    ):
        self.confirmations = confirmations
        self._allowed_guard_types = allowed_guard_types

    @property
    def device_code(self) -> bool:
        """Requires device `Steam Guard` code."""
        return EAuthSessionGuardType.k_EAuthSessionGuardType_DeviceCode in self._allowed_guard_types

    @property
    def email_code(self) -> bool:
        """Requires email `Steam Guard` code."""
        return EAuthSessionGuardType.k_EAuthSessionGuardType_EmailCode in self._allowed_guard_types

    @property
    def device_conf(self) -> bool:
        """Requires device confirmation."""
        return EAuthSessionGuardType.k_EAuthSessionGuardType_DeviceConfirmation in self._allowed_guard_types

    @property
    def email_conf(self) -> bool:
        """Requires email confirmation."""
        return EAuthSessionGuardType.k_EAuthSessionGuardType_EmailConfirmation in self._allowed_guard_types

    # machine token and legacy machine auth guard types should never be received so no need to handle them
