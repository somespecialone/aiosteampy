"""Component responsible for `Steam` profile wallet logic."""

from typing import Awaitable

from ..session import SteamSession
from .state import SteamState, WalletInfo


class WalletComponent:
    """Wallet-related actions."""

    __slots__ = ("_session", "_state")

    def __init__(self, session: SteamSession, state: SteamState):
        self._session = session
        self._state = state

    def get_wallet_info(self) -> Awaitable[WalletInfo]:
        """
        Get wallet current user wallet info.

        .. note:: Will implicitly update `state` wallet info.

        :return: wallet info.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        """

        return self._state.sync_wallet_info()
