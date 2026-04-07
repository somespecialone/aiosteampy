import hashlib
import hmac
import time
from base64 import b64decode, b64encode
from typing import Self


class TwoFactorSecret(bytes):
    __slots__ = ()

    def __new__(cls, o: str | bytes) -> Self:
        if isinstance(o, cls):
            return o
        elif isinstance(o, bytes):
            return super().__new__(cls, o)
        elif isinstance(o, str):
            return cls.deserialize(o)
        else:
            raise TypeError(f'Unknown secret input type: "{type(o)}"')

    def __str__(self):  # preventing user from accidentally leaking secret
        return repr(self)

    def __repr__(self):
        return f"{self.__class__.__name__}(...)"

    def serialize(self) -> str:
        """Serialize the `secret` into string."""
        return b64encode(self).decode()

    @classmethod
    def deserialize(cls, data: str) -> Self:
        """Deserialize the `secret` from `base64 encoded` string."""
        return cls(b64decode(data))


class SharedSecret(TwoFactorSecret):
    """Shared secret. Used to generate auth codes (TOTP, request signature)."""

    __slots__ = ()

    _CODE_ALPHABET = "23456789BCDFGHJKMNPQRTVWXY"

    def __new__(cls, o: str | bytes) -> Self:
        if isinstance(o, IdentitySecret):
            raise TypeError(f'Shared secret cannot be created from "{type(o)}"')

        return super().__new__(cls, o)

    def generate_auth_code(self, timestamp: int | None = None) -> str:
        """
        Generate 5-character alphanumeric `Steam` two-factor (TOTP) auth code.
        Will use current time if ``timestamp`` is not provided.
        """

        if not timestamp:
            timestamp = int(time.time())

        msg = (timestamp // 30).to_bytes(8)  # new code every 30 seconds
        mac = hmac.new(self, msg, digestmod=hashlib.sha1)
        hashed = mac.digest()

        b = hashed[19] & 0xF
        code_point = int.from_bytes(hashed[b : b + 4]) & 0x7FFFFFFF

        code = [""] * 5
        for i in range(5):
            code_point, idx = divmod(code_point, len(self._CODE_ALPHABET))
            code[i] = self._CODE_ALPHABET[idx]

        return "".join(code)

    def sign_auth_request(self, steamid: int, version: int, client_id: int) -> bytes:
        """Make signature for auth request."""

        mac = hmac.new(self, digestmod=hashlib.sha256)
        mac.update(version.to_bytes(2, "little"))
        mac.update(client_id.to_bytes(8, "little"))
        mac.update(steamid.to_bytes(8, "little"))

        return mac.digest()


class IdentitySecret(TwoFactorSecret):
    """Identity secret. Used to generate confirmation hashes."""

    __slots__ = ()

    def __new__(cls, o: str | bytes) -> Self:
        if isinstance(o, SharedSecret):
            raise TypeError(f'Identity secret cannot be created from "{type(o)}"')

        return super().__new__(cls, o)

    def generate_confirmation_key(self, tag: str, timestamp: int | None = None) -> str:
        """
        Generate `confirmation` key that can only be used once.
        Will use current time if ``timestamp`` is not provided.
        """

        if not timestamp:
            timestamp = int(time.time())

        mac = hmac.new(self, digestmod=hashlib.sha1)
        mac.update(timestamp.to_bytes(8))
        mac.update(tag.encode())
        hashed = mac.digest()

        return b64encode(hashed).decode()
