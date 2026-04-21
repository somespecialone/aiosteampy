"""
`Steam` auth session implementation. Handles authentication process with tokens negotiation.
"""

# reexport
from ..exceptions import ConfirmationRequired, EResultError, RateLimitExceeded, SteamError
from ..transport import NetworkError, ProxyError, TransportError, TransportResponseError
from .exceptions import (
    AuthCodeExpired,
    BadCredentials,
    GuardConfirmationRequired,
    LoginError,
    TooManyAttempts,
)
from .jwt import SteamJWT
from .session import Platform, SteamSession
from .utils import generate_session_id, parse_qr_challenge_url
