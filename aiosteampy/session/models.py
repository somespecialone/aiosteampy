import json
from base64 import b64decode
from dataclasses import dataclass, field
from datetime import datetime
from typing import Self, TypedDict

from ..id import SteamID

ALTCHARS = b"-_"


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
    raw: str = field(repr=False)
    """Raw encoded JWT token."""
    header: JWTHeader
    """JWT header."""
    claims: SteamJWTClaims
    """Known Steam JWT claims from token payload."""
    signature: bytes = field(repr=False)
    """JWT signature."""

    subject: SteamID = field(init=False)
    """Parsed token subject."""

    def __post_init__(self):
        self.subject = SteamID(self.claims["sub"])

    @property
    def audiences(self) -> list[str]:
        """List of audiences (e.g. 'web:store')."""
        return self.claims["aud"]

    @property
    def expire_at(self) -> datetime:
        """Expiration ``datetime``."""
        return datetime.fromtimestamp(self.claims["exp"])

    @property
    def expired(self) -> bool:
        """If current token has been expired."""
        return self.expire_at <= datetime.now()

    @property
    def issued_at(self) -> datetime:
        return datetime.fromtimestamp(self.claims["iat"])

    @property
    def cookie_value(self) -> str:
        """Encoded token as cookie value for `Steam`."""
        return self.claims["sub"] + "%7C%7C" + self.raw  # steam id 64 || encoded token

    @staticmethod
    def _restore_padding(segment: str) -> str:
        return segment + "=" * (-len(segment) % 4)

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
        return "mobile" in self.audiences

    @property
    def for_client(self) -> bool:
        """Issued for `Steam Client` platform."""
        return "client" in self.audiences

    @property
    def for_web(self):
        """Issued for `web` (browser) platform."""
        return not self.for_mobile and not self.for_client and "web" in self.audiences
