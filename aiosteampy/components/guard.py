import time

from ..utils import gen_auth_code, generate_confirmation_key, async_throttle, generate_device_id

from ..id import SteamID


class SteamGuardComponent:
    __slots__ = (
        "_steam_id",
        "_shared_secret",
        "_identity_secret",
        "_device_id",
    )

    def __init__(
        self,
        steam_id: SteamID,
        shared_secret: str,
        identity_secret: str,
        device_id: str | None = None,
    ):
        """"""

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
