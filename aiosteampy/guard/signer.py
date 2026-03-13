import time

from ..id import SteamID
from ..webapi import SteamWebAPIClient
from .models import ServerTime
from .utils import generate_auth_code, generate_confirmation_key, generate_device_id, sing_auth_request


class TwoFactorSigner:
    __slots__ = ("_api", "_steam_id", "_shared_secret", "_identity_secret", "time_offset", "synced")

    def __init__(
        self,
        steam_id: SteamID,
        shared_secret: str,
        identity_secret: str,
        webapi: SteamWebAPIClient | None = None,
        time_offset: int = 0,
    ):
        """
        Crypto functionality of `Steam Guard`.

        :param shared_secret: shared secret of account.
        :param identity_secret: identity secret of account.
        :param webapi: client instance to make requests to.
        :param time_offset: known offset in seconds from server time.
        """

        self._api = webapi or SteamWebAPIClient()

        self._steam_id = steam_id
        self._shared_secret = shared_secret
        self._identity_secret = identity_secret

        self.time_offset = time_offset
        """Time offset in seconds from server time."""
        self.synced = bool(time_offset)  # assume that if some offset is passed, it's synced
        """Whether time offset is synced with `Steam` servers."""

    @property
    def webapi(self) -> SteamWebAPIClient:
        """`Steam Web API` client."""
        return self._api

    async def get_server_time(self) -> ServerTime:
        """Query `Steam` servers for current time."""

        r: dict = await self._api.request("POST", "ITwoFactorService/QueryTime")
        return ServerTime(**{k: int(v) for k, v in r["response"].items()})

    async def sync_time(self):
        """Sync time offset with `Steam` servers."""

        serv_time = await self.get_server_time()
        self.time_offset = serv_time.server_time - int(time.time())
        self.synced = True

    def gen_auth_code(self) -> str:
        """Generate 5 character alphanumeric `Steam` two-factor (TOTP) auth code."""

        return generate_auth_code(self._shared_secret, int(time.time()) + self.time_offset)

    def gen_confirmation_key(self, tag: str) -> tuple[str, int]:
        """
        Generate confirmation key.

        :param tag: confirmation tag.
        :return: confirmation key and used timestamp.
        """

        ts = int(time.time()) + self.time_offset
        return generate_confirmation_key(self._identity_secret, tag, ts), ts

    def sign_auth_request(self, version: int, client_id: int) -> bytes:
        """
        Make signature for auth request (login approval).

        :param version: version. Can be extracted from challenge QR.
        :param client_id: client id. Also can be extracted from challenge QR.
        """

        return sing_auth_request(self._steam_id.id64, self._shared_secret, version, client_id)
