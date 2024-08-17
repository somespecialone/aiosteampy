from urllib.parse import quote
from re import search as re_search

from yarl import URL

from ..constants import STEAM_URL
from .login import LoginMixin


class ProfileMixin(LoginMixin):
    """
    Profile attributes and data related methods.
    Depends on `LoginMixin`.
    """

    __slots__ = ()

    # required instance attributes
    trade_token: str | None

    @property
    def trade_url(self) -> URL | None:
        if self.trade_token:
            return STEAM_URL.TRADE / "new/" % {"partner": self.account_id, "token": self.trade_token}

    @property
    def profile_url(self) -> URL:
        return STEAM_URL.COMMUNITY / f"profiles/{self.steam_id}"

    async def register_new_trade_url(self) -> URL:
        """Register new trade url. Cache token."""

        r = await self.session.post(
            self.profile_url / "tradeoffers/newtradeurl",
            data={"sessionid": self.session_id},
        )
        token: str = await r.json()

        self.trade_token = quote(token, safe="~()*!.'")  # https://stackoverflow.com/a/72449666/19419998
        return self.trade_url

    async def get_trade_token(self) -> str | None:
        """Fetch trade token from `Steam`."""

        r = await self.session.get(self.profile_url / "tradeoffers/privacy")
        rt = await r.text()

        search = re_search(r"\d+&token=(?P<token>.+)\" readonly", rt)
        return search["token"] if search else None

    # TODO change nickname method
