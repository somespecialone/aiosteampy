import time
from collections.abc import Awaitable

from ..id import SteamID
from ..webapi import SteamWebAPIClient
from ..webapi.services.twofactor import CTwoFactorTimeResponse, TwoFactorServiceClient
from .secrets import IdentitySecret, SharedSecret
from .utils import get_server_time_offset


class TwoFactorSigner:
    __slots__ = ("_service", "_steam_id", "_shared_secret", "_identity_secret", "time_offset", "synced")

    def __init__(
        self,
        steam_id: SteamID,
        *,  # to prevent secrets mix up
        shared_secret: bytes | str,
        identity_secret: bytes | str,
        webapi: SteamWebAPIClient | None = None,
        time_offset: int | None = None,
    ):
        """
        Crypto functionality of `Steam Guard`.

        :param shared_secret: `shared secret` of an account in `bytes` or `base64 encoded` string.
        :param identity_secret: `identity secret` of an account in `bytes` or `base64 encoded` string.
        :param webapi: client instance to make requests from.
        :param time_offset: known `offset` in seconds from server time.
        """

        api = webapi or SteamWebAPIClient()
        self._service = TwoFactorServiceClient(api)

        self._steam_id = steam_id

        self._shared_secret = SharedSecret(shared_secret)
        self._identity_secret = IdentitySecret(identity_secret)

        self.time_offset: int = time_offset or 0
        """Time offset in seconds from server time."""
        self.synced: bool = True if time_offset is not None else False
        """Whether time offset is synced with `Steam` servers."""

    @property
    def service(self) -> TwoFactorServiceClient:
        """TwoFactor service client."""
        return self._service

    @property
    def shared_secret(self) -> SharedSecret:
        """Shared secret of the current account with activated `Steam Guard`."""
        return self._shared_secret

    @property
    def identity_secret(self) -> IdentitySecret:
        """Identity secret of the current account with activated `Steam Guard`."""
        return self._identity_secret

    def get_server_time(self) -> Awaitable[CTwoFactorTimeResponse]:
        """Query `Steam` servers for current time."""
        return self._service.query_time()

    async def sync_time(self):
        """Sync time offset with `Steam` servers."""

        self.time_offset = await get_server_time_offset(service=self._service)
        self.synced = True

    def _calc_server_time(self) -> int:
        """Calculate server time."""
        return int(time.time()) + self.time_offset

    def gen_auth_code(self) -> str:
        """Generate 5-character alphanumeric `Steam` two-factor (TOTP) auth code."""
        return self._shared_secret.generate_auth_code(self._calc_server_time())

    def gen_confirmation_key(self, tag: str) -> tuple[str, int]:
        """
        Generate confirmation key.

        :param tag: confirmation tag.
        :return: confirmation key and used timestamp.
        """

        ts = self._calc_server_time()
        return self._identity_secret.generate_confirmation_key(tag, ts), ts

    def sign_auth_request(self, version: int, client_id: int) -> bytes:
        """
        Make signature for auth request (login approval).

        :param version: version. Can be extracted from challenge QR.
        :param client_id: client id. Also can be extracted from challenge QR.
        """

        return self._shared_secret.sign_auth_request(self._steam_id, version, client_id)
