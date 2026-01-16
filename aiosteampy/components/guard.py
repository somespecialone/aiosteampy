"""All available things and functionality related to `Steam Guard`."""

import time
import hmac
import hashlib
import struct

from base64 import b64decode, b64encode

from ..utils import async_throttle

from ..id import SteamID


# It works, however it's different that one generated from mobile app
def generate_device_id(steam_id64: int) -> str:
    """
    Generate mobile android device id.
    :param steam_id64: 64bit representation of `Steam ID`.
    """

    hexed_steam_id = hashlib.sha1(str(steam_id64).encode("ascii")).hexdigest()
    return "android:" + "-".join(
        [hexed_steam_id[:8], hexed_steam_id[8:12], hexed_steam_id[12:16], hexed_steam_id[16:20], hexed_steam_id[20:32]]
    )


def gen_auth_code(shared_secret: str, timestamp: int | None = None) -> str:
    """Generate two-factor (one-time/TOTP) auth code."""

    timestamp = int(time.time()) if timestamp is None else timestamp

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


def generate_confirmation_key(identity_secret: str, tag: str, timestamp: int | None = None) -> str:
    """Generate confirmation key."""

    timestamp = int(time.time()) if timestamp is None else timestamp

    buff = struct.pack(">Q", timestamp) + tag.encode("ascii")
    return b64encode(hmac.new(b64decode(identity_secret), buff, digestmod=hashlib.sha1).digest()).decode()


class SteamGuardComponent:
    """Contain functionality related to `Steam Guard`."""

    __slots__ = ("_steam_id", "_shared_secret", "_identity_secret", "_device_id")

    def __init__(
        self,
        steam_id: SteamID,
        shared_secret: str,
        identity_secret: str,
        device_id: str | None = None,
    ):
        self._steam_id = steam_id
        self._shared_secret = shared_secret
        self._identity_secret = identity_secret
        # next field belongs to Guard?
        self._device_id = generate_device_id(steam_id.id64) if device_id is None else device_id

    @property
    def steam_id(self) -> SteamID:
        return self._steam_id

    @property
    def device_id(self) -> str:
        return self._device_id

    def gen_auth_code(self) -> str:
        """Generate two-factor (one-time/TOTP) auth code."""

        return gen_auth_code(self._shared_secret)

    @async_throttle(1, arg_name="tag")
    # @identity_secret_required
    async def gen_confirmation_key(self, *, tag: str) -> tuple[str, int]:
        """
        Generate confirmation key.

        .. note:: Can wait up to 1s between calls with same tag to prevent code collisions.

        :return: confirmation key and timestamp.
        """

        ts = int(time.time())
        return generate_confirmation_key(self._identity_secret, tag, ts), ts

    # TODO methods to enable/disable[optional] steam guard
    #  generally, flow from newly registered acc to a fully prepared for trade activity
