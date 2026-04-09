import json
from base64 import b64decode
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Self, TypedDict

from ..constants import Platform
from ..id import SteamID

ALTCHARS = b"-_"
COOKIE_SEP = "%7C%7C"


class JWTHeader(TypedDict):
    alg: str
    typ: str


class SteamJWTClaims(TypedDict, total=False):
    iss: str
    sub: str  # steam id64
    aud: list[str]
    exp: int
    nbf: int
    iat: int
    jti: str
    oat: int
    rt_exp: int
    per: int
    ip_subject: str
    ip_confirmer: str


@dataclass(slots=True)
class SteamJWT:
    raw: str
    """Raw encoded JWT."""
    header: JWTHeader
    """JWT header."""
    claims: SteamJWTClaims
    """Known Steam JWT claims from payload."""
    signature: bytes
    """JWT signature."""

    subject: SteamID = field(init=False)
    """Parsed subject."""
    platform: Platform = field(init=False)
    """For which platform was issued."""
    expires_at: datetime = field(init=False)  # precompute as often used
    """When expires."""

    def __post_init__(self):
        self.subject = SteamID(self.claims["sub"])

        if "mobile" in self.audiences:
            self.platform = Platform.MOBILE
        else:  # web by default
            self.platform = Platform.WEB

        self.expires_at = datetime.fromtimestamp(self.claims["exp"], UTC)

        if self.for_client:
            import warnings

            warnings.warn("Client tokens are not supported", UserWarning)

    @property
    def audiences(self) -> list[str]:
        """List of audiences (e.g. 'web:store')."""
        return self.claims["aud"]

    @property
    def expired(self) -> bool:
        """If current token has been expired."""
        return self.expires_at <= datetime.now(UTC)

    @property
    def issued_at(self) -> datetime:
        """When was issued."""
        return datetime.fromtimestamp(self.claims["iat"], UTC)

    @property
    def cookie_value(self) -> str:
        """Encoded token as cookie value for `Steam`."""
        return self.claims["sub"] + COOKIE_SEP + self.raw  # steam id 64 || encoded token

    @staticmethod
    def _restore_padding(segment: str) -> str:
        return segment + "=" * (-len(segment) % 4)

    @classmethod
    def from_cookie_value(cls, cookie_value: str) -> Self:
        """Parse encoded JWT token from cookie value."""
        _, encoded_token = cookie_value.split(COOKIE_SEP)
        return cls.parse(encoded_token)

    @classmethod
    def parse(cls, encoded_token: str) -> Self:
        """Parse encoded JWT token."""

        try:
            header, claims, signature = encoded_token.split(".")
        except ValueError:
            raise ValueError("Invalid JWT token")

        header = json.loads(b64decode(cls._restore_padding(header), altchars=ALTCHARS))
        claims = json.loads(b64decode(cls._restore_padding(claims), altchars=ALTCHARS))
        signature = b64decode(cls._restore_padding(signature), altchars=ALTCHARS)

        return cls(encoded_token, header, claims, signature)

    @property
    def is_refresh_token(self) -> bool:
        """Is a `refresh` token."""
        return "derive" in self.audiences

    @property
    def is_access_token(self) -> bool:
        """Is an `access` token."""
        return not self.is_refresh_token

    @property
    def for_mobile(self) -> bool:
        """Issued for `mobile app` platform."""
        return self.platform is Platform.MOBILE

    @property
    def for_web(self):
        """Issued for `web (browser)` platform."""
        return self.platform is Platform.WEB

    @property
    def for_client(self) -> bool:
        """Issued for `Steam Client` platform (not supported)."""
        return "client" in self.audiences

    def __eq__(self, other):
        return isinstance(other, SteamJWT) and self.raw == other.raw

    def __repr__(self):
        return (
            f"{self.__class__.__name__}({self.subject}, {'Access' if self.is_access_token else 'Refresh'}/"
            f"{self.platform}, issued={self.issued_at.isoformat()}, expires={self.expires_at.isoformat()})"
        )
