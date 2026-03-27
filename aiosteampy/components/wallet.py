"""Component responsible for `Steam` profile wallet logic."""

import json
import re
from typing import Awaitable, NamedTuple

from ..constants import Currency
from ..exceptions import EResultError
from ..session import SteamSession
from .state import StateComponent, WalletInfo


class WalletComponent:
    """Wallet-related actions."""

    __slots__ = ("_session", "_state")

    def __init__(self, session: SteamSession, state: StateComponent):
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

        return self._state.update_wallet_info()
