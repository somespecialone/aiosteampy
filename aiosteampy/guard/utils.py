import hashlib
import hmac
import struct
import time
from base64 import b64decode, b64encode


def generate_device_id(steam_id64: int) -> str:
    """
    Generate mobile android device id.

    :param steam_id64: 64bit representation of `Steam ID`.
    """

    hexed_steam_id = hashlib.sha1(str(steam_id64).encode("ascii")).hexdigest()
    return "android:" + "-".join(
        [
            hexed_steam_id[:8],
            hexed_steam_id[8:12],
            hexed_steam_id[12:16],
            hexed_steam_id[16:20],
            hexed_steam_id[20:32],
        ]
    )


def generate_auth_code(shared_secret: str, timestamp: int) -> str:
    """
    Generate 5 character alphanumeric `Steam` two-factor (TOTP) auth code.

    :param shared_secret: shared secret of account.
    :param timestamp: timestamp to use.
    """

    time_buffer = struct.pack(">Q", timestamp // 30)  # pack as Big endian, uint64
    time_hmac = hmac.new(b64decode(shared_secret), time_buffer, digestmod=hashlib.sha1).digest()
    begin = ord(time_hmac[19:20]) & 0xF
    full_code = struct.unpack(">I", time_hmac[begin : begin + 4])[0] & 0x7FFFFFFF  # unpack as Big endian uint32
    chars = "23456789BCDFGHJKMNPQRTVWXY"
    code = ""

    for _ in range(5):
        full_code, i = divmod(full_code, len(chars))
        code += chars[i]

    return code


def generate_confirmation_key(identity_secret: str, tag: str, timestamp) -> str:
    """
    Generate confirmation key.

    :param identity_secret: identity secret of account.
    :param tag: confirmation tag.
    :param timestamp: timestamp to use.
    """

    buff = struct.pack(">Q", timestamp) + tag.encode("ascii")
    return b64encode(hmac.new(b64decode(identity_secret), buff, digestmod=hashlib.sha1).digest()).decode()


def sing_auth_request(steam_id64: int, shared_secret: str, version: int, client_id: int) -> bytes:
    """Make signature for auth request."""

    signature_data = bytearray(18)
    struct.pack_into("<H", signature_data, 0, version)
    struct.pack_into("<Q", signature_data, 2, client_id)
    struct.pack_into("<Q", signature_data, 10, steam_id64)
    return hmac.new(shared_secret.encode("utf-8"), bytes(signature_data), hashlib.sha256).digest()
