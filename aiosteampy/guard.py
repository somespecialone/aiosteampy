from typing import TYPE_CHECKING
from time import time as time_time

from .utils import gen_two_factor_code, generate_confirmation_key, generate_device_id, async_throttle

if TYPE_CHECKING:
    from .client import SteamClient


class SteamGuardMixin:
    __slots__ = ()

    _device_id: str | None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._device_id = None

    @property
    def two_factor_code(self: "SteamClient") -> str:
        return gen_two_factor_code(self._shared_secret)

    @property
    def device_id(self) -> str | None:
        return self._device_id

    @async_throttle(1, arg_name="tag")
    async def _gen_confirmation_key(self: "SteamClient", *, tag: str) -> tuple[str, int]:
        """

        :param tag:
        :return: confirmation key, used timestamp
        """
        ts = int(time_time())
        return generate_confirmation_key(self._identity_secret, tag, ts), ts

    def _gen_device_id(self: "SteamClient") -> str:
        return generate_device_id(self.steam_id)
