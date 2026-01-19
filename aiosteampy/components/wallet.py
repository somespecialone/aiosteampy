"""Component responsible for `Steam` profile wallet logic."""

import re
import json

from typing import NamedTuple

from ..constants import Currency
from ..exceptions import EResultError
from ..session import SteamLoginSession

from .profile import ProfileComponent

WALLET_INFO_RE = re.compile(r"g_rgWalletInfo = (.+);")


class WalletInfo(NamedTuple):
    wallet_currency: Currency
    wallet_country: str
    wallet_state: str
    wallet_fee: int
    wallet_fee_minimum: int
    wallet_fee_percent: float
    wallet_publisher_fee_percent_default: float
    wallet_fee_base: int
    wallet_balance: int
    wallet_delayed_balance: int
    wallet_max_balance: int
    wallet_trade_max_balance: int


class WalletComponent:
    """Handle wallet-related actions."""

    __slots__ = ("_session", "_profile")

    def __init__(self, session: SteamLoginSession, profile: ProfileComponent):
        self._session = session
        self._profile = profile

    async def get_wallet_info(self) -> WalletInfo:
        """
        Get wallet current user wallet info.

        :return: wallet info.
        :raises EResultError: ordinary reasons.
        :raises TransportError: arbitrary reasons.
        """

        r = await self._session.transport.request(
            "GET",
            self._profile.url / "inventory",
            headers={"Referer": str(self._profile.url)},
            redirects=True,  # handle redirects if profile alias unset
            response_mode="text",
        )
        rt: str = r.content

        data = json.loads(WALLET_INFO_RE.search(rt).group(1))

        EResultError.check_data(data)

        return WalletInfo(
            Currency(data["wallet_currency"]),
            data["wallet_country"],
            data["wallet_state"],
            int(data["wallet_fee"]),
            int(data["wallet_fee_minimum"]),
            float(data["wallet_fee_percent"]),
            float(data["wallet_publisher_fee_percent_default"]),
            int(data["wallet_fee_base"]),
            int(data["wallet_balance"]),
            int(data["wallet_delayed_balance"]),
            int(data["wallet_max_balance"]),
            int(data["wallet_trade_max_balance"]),
        )

    # it would be good to have add funds method
