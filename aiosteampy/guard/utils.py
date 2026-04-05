import hashlib
import hmac
import time
from base64 import b64encode
from uuid import uuid4

STEAM_GUARD_CODE_CHARS = "23456789BCDFGHJKMNPQRTVWXY"


def generate_device_id() -> str:
    """Generate standardized mobile android device ID."""
    return f"android:{uuid4()}"


def generate_auth_code(shared_secret: bytes, timestamp: int | None = None) -> str:
    """
    Generate 5-character alphanumeric `Steam` two-factor (TOTP) auth code.
    Will use current time if ``timestamp`` is not provided.
    """

    if not timestamp:
        timestamp = int(time.time())

    msg = (timestamp // 30).to_bytes(8)  # new code every 30 seconds
    mac = hmac.new(shared_secret, msg, digestmod=hashlib.sha1)
    hashed = mac.digest()

    b = hashed[19] & 0xF
    code_point = int.from_bytes(hashed[b : b + 4]) & 0x7FFFFFFF

    code = [""] * 5
    for i in range(5):
        code_point, idx = divmod(code_point, len(STEAM_GUARD_CODE_CHARS))
        code[i] = STEAM_GUARD_CODE_CHARS[idx]

    return "".join(code)


def generate_confirmation_key(identity_secret: bytes, tag: str, timestamp: int | None = None) -> str:
    """
    Generate `confirmation` key that can only be used once.
    Will use current time if ``timestamp`` is not provided.
    """

    if not timestamp:
        timestamp = int(time.time())

    mac = hmac.new(identity_secret, digestmod=hashlib.sha1)
    mac.update(timestamp.to_bytes(8))
    mac.update(tag.encode())
    hashed = mac.digest()

    return b64encode(hashed).decode()


def sign_auth_request(steam_id64: int, shared_secret: bytes, version: int, client_id: int) -> bytes:
    """Make signature for auth request."""

    mac = hmac.new(shared_secret, digestmod=hashlib.sha256)
    mac.update(version.to_bytes(2, "little"))
    mac.update(client_id.to_bytes(8, "little"))
    mac.update(steam_id64.to_bytes(8, "little"))

    return mac.digest()
