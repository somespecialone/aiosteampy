from time import time as time_time

from ..helpers import identity_secret_required
from ..utils import (
    gen_two_factor_code,
    generate_confirmation_key,
    async_throttle,
    steam_id_to_account_id,
)
from .http import SteamHTTPTransportMixin


class SteamGuardMixin(SteamHTTPTransportMixin):
    """
    Mixin with Steam Guard related methods.
    Depends on `SteamHTTPTransportMixin`.
    """

    __slots__ = ()

    # required instance attributes
    steam_id: int
    device_id: str
    _shared_secret: str
    _identity_secret: str | None

    @property
    def account_id(self) -> int:
        """Steam id32."""
        return steam_id_to_account_id(self.steam_id)

    @property
    def two_factor_code(self) -> str:
        """Generate twofactor (onetime/TOTP) code."""
        return gen_two_factor_code(self._shared_secret)

    @async_throttle(1, arg_name="tag")
    @identity_secret_required
    async def _gen_confirmation_key(self, *, tag: str) -> tuple[str, int]:
        ts = int(time_time())
        return generate_confirmation_key(self._identity_secret, tag, ts), ts
