import json

from urllib.parse import quote, unquote
from datetime import datetime
from base64 import b64decode, b64encode
from typing import Self, TypedDict, ClassVar
from dataclasses import dataclass, field, asdict

from ..id import SteamID


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


@dataclass(eq=False, slots=True)
class SteamJWT:
    ALTCHARS: ClassVar[bytes] = b"-_"

    raw: str = field(repr=False)
    """Raw encoded JWT token."""
    header: JWTHeader
    """JWT header."""
    claims: SteamJWTClaims
    """Known Steam JWT claims from token payload."""
    signature: bytes = field(repr=False)
    """JWT signature."""

    @property
    def sub(self) -> str:
        return self.claims["sub"]

    @property
    def aud(self) -> list[str]:
        """List of audiences (e.g. 'web:store')."""
        return self.claims["aud"]

    @property
    def exp(self) -> int:
        """Expiration ts."""
        return self.claims["exp"]

    @property
    def expiration(self) -> datetime:
        """Parsed expiration datetime."""
        return datetime.fromtimestamp(self.exp)

    @property
    def subject(self) -> SteamID:
        """Parsed token subject."""
        return SteamID(self.sub)

    @property
    def expired(self) -> bool:
        """If current token has been expired."""
        return self.expiration <= datetime.now()

    @property
    def cookie_value(self) -> str:
        """Encoded token as cookie value for *Steam* domain."""
        return self.sub + "%7C%7C" + self.raw  # steam id 64 || encoded token

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

        header = json.loads(b64decode(cls._restore_padding(header), altchars=cls.ALTCHARS))
        claims = json.loads(b64decode(cls._restore_padding(claims), altchars=cls.ALTCHARS))
        signature = b64decode(cls._restore_padding(signature), altchars=cls.ALTCHARS)

        return cls(encoded_token, header, claims, signature)
