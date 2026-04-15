from ..exceptions import ConfirmationRequired, RateLimitExceeded, SteamError


class AuthenticatorError(SteamError):
    """Generic authenticator error."""


# no need in specific error for absence of verified phone


class AuthenticatorAlreadyPresent(AuthenticatorError):
    """Authenticator is already present."""


class TooManyAttempts(RateLimitExceeded, AuthenticatorError):
    """Too many failed attempts."""


class SmsConfirmationRequired(ConfirmationRequired):
    """SMS confirmation is required."""

    def __init__(self, phone_hint: str):
        self.phone_hint = phone_hint

    def __str__(self):
        return f"A code has been sent to phone number ending in {self.phone_hint}"


class TwoFactorCodeMismatch(AuthenticatorError):
    """Two-factor code mismatch."""

    def __init__(self, attempts_left: int | None = None):
        self.attempts_left = attempts_left
        """How many attempts left to remove `Guard`."""

    def __str__(self):
        if self.attempts_left is not None:
            return f"Revocation attempt failed. {self.attempts_left} attempts left"
        return "Two-factor code mismatch"
