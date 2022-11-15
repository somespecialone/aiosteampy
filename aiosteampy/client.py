from re import compile
from urllib.parse import quote
from json import loads
from http.cookies import SimpleCookie

from aiohttp import ClientSession
from yarl import URL

from .guard import SteamGuardMixin
from .confirmation import ConfirmationMixin
from .login import LoginMixin
from .trade import TradeMixin
from .market import MarketMixin
from .public import SteamPublicMixin, INV_PAGE_SIZE, PREDICATE, PRIVATE_USER_EXC_MSG

from .models import STEAM_URL, Currency, Notifications, GameType, EconItem
from .exceptions import ApiError, SessionExpired
from .utils import get_cookie_value_from_session

__all__ = ("SteamClient", "SteamPublicClient")

API_KEY_RE = compile(r"<p>Key: (?P<api_key>[0-9A-F]+)</p>")
WALLET_INFO_RE = compile(r"g_rgWalletInfo = (?P<info>.+);")
TRADE_TOKEN_RE = compile(r"\d+&token=(?P<token>.+)\" readonly")

API_KEY_CHECK_STR = "<h2>Access Denied</h2>"
API_KEY_CHECK_STR1 = "You must have a validated email address to create a Steam Web API key"
STEAM_LANG_COOKIE = "Steam_Language"


class SteamClient(SteamGuardMixin, ConfirmationMixin, LoginMixin, MarketMixin, SteamPublicMixin):
    """
    Base class in hierarchy ...
    """

    __slots__ = (
        "_is_logged",
        "session",
        "username",
        "steam_id",
        "_password",
        "_shared_secret",
        "_identity_secret",
        "_api_key",
        "trade_token",
        "_device_id",
        "_listings_confs_ident",
        "_listings_confs",
        "_trades_confs",
        "_steam_fee",
        "_publisher_fee",
        "_wallet_currency",
        "_wallet_balance",
        "_wallet_country",
    )

    def __init__(
        self,
        username: str,
        password: str,
        steam_id: int,
        *,
        shared_secret: str,
        identity_secret: str,
        api_key: str = None,
        trade_token: str = None,
        wallet_currency: Currency = None,
        wallet_country="UA",
        steam_fee=0.05,
        publisher_fee=0.1,
        tz_offset=0.0,
        session: ClientSession = None,
    ):

        self.session = session or ClientSession(raise_for_status=True)
        # admit about raise for status and strange behaviour if opposite in docs.
        self.username = username
        self.steam_id = steam_id  # steam id64
        self.trade_token = trade_token

        self._password = password
        self._shared_secret = shared_secret
        self._identity_secret = identity_secret
        self._api_key = api_key
        self._steam_fee = steam_fee
        self._publisher_fee = publisher_fee
        self._wallet_currency = wallet_currency

        self._wallet_country = wallet_country
        self._wallet_balance = 0.0

        super().__init__()

        self._set_init_cookies(tz_offset)

    @property
    def steam_id32(self) -> int:
        return self.steam_id & 0xFFFFFFFF

    @property
    def trade_url(self) -> URL | None:
        if self.trade_token:
            return (STEAM_URL.COMMUNITY / "tradeoffer/new/").with_query(
                {"partner": self.steam_id32, "token": self.trade_token}
            )

    @property
    def profile_url(self) -> URL:
        return STEAM_URL.COMMUNITY / f"profiles/{self.steam_id}"

    @property
    def language(self) -> str:
        """Language of Steam html pages, json info, descriptions, etc..."""
        return get_cookie_value_from_session(self.session, STEAM_URL.STORE.host, STEAM_LANG_COOKIE)

    @property
    def wallet_balance(self) -> float:
        """
        Cached wallet balance.
        Updates when you buy market listing, fetch wallet balance.
        """
        return self._wallet_balance

    @property
    def country(self) -> str:
        """Just wallet country. Needed for public methods."""
        return self._wallet_country

    @property
    def currency(self) -> Currency | None:
        """Alias for wallet currency. Needed for public methods."""
        return self._wallet_currency

    def _set_init_cookies(self, tz_offset: float):
        urls = (STEAM_URL.COMMUNITY, STEAM_URL.STORE, STEAM_URL.HELP)
        for url in urls:
            c = SimpleCookie()
            c[STEAM_LANG_COOKIE] = "english"
            c[STEAM_LANG_COOKIE]["path"] = "/"
            c[STEAM_LANG_COOKIE]["domain"] = url.host
            c[STEAM_LANG_COOKIE]["secure"] = True

            self.session.cookie_jar.update_cookies(cookies=c, response_url=url)

        c_key = "timezoneOffset"
        for url in urls:
            c = SimpleCookie()
            c[c_key] = str(tz_offset).replace(".", ",")
            c[c_key]["path"] = "/"
            c[c_key]["domain"] = url.host
            c[c_key]["SameSite"] = True

            self.session.cookie_jar.update_cookies(cookies=c, response_url=url)

    async def _init_data(self):
        if not self._api_key:
            self._api_key = await self._fetch_api_key()
            not self._api_key and await self.register_new_api_key()

        if not self.trade_token:
            self.trade_token = await self._fetch_trade_token()
            not self.trade_token and await self.register_new_trade_url()

        if not self._steam_fee or not self._publisher_fee or not self._wallet_currency:
            wallet_info = await self._fetch_wallet_info()
            self._wallet_balance = int(wallet_info["wallet_balance"]) / 100
            self._wallet_country = wallet_info["wallet_country"]
            if not self._steam_fee:
                self._steam_fee = float(wallet_info["wallet_fee_percent"])
            if not self._publisher_fee:
                self._publisher_fee = float(wallet_info["wallet_publisher_fee_percent_default"])
            if not self._wallet_currency:
                self._wallet_currency = Currency(wallet_info["wallet_currency"])

    async def _fetch_wallet_info(self) -> dict[str, str | int]:
        # fetching inventory may reset new items notifs count
        r = await self.session.get(self.profile_url / "inventory", headers={"Referer": str(self.profile_url)})
        rt = await r.text()
        info: dict = loads(WALLET_INFO_RE.search(rt)["info"])
        if not info.get("success"):
            raise ApiError("Failed to fetch wallet info from inventory.", info)

        return info

    async def get_wallet_balance(self) -> tuple[float, Currency]:
        """
        Fetch wallet balance and currency. Cache data.

        :return: tuple of balance and `Currency`
        """

        r = await self.session.get(STEAM_URL.STORE / "api/getfundwalletinfo")
        rj = await r.json()
        if not rj.get("success"):
            raise ApiError("Failed to fetch wallet info.", rj)

        self._wallet_currency = Currency.by_name(rj["user_wallet"]["currency"])
        self._wallet_balance = int(rj["user_wallet"]["amount"]) / 100
        return self._wallet_balance, self._wallet_currency

    async def register_new_trade_url(self) -> URL:
        """
        Register new trade url. Cache token.

        :return: trade url
        """

        r = await self.session.post(
            self.profile_url / "tradeoffers/newtradeurl",
            data={"sessionid": self.session_id},
        )
        token: str = await r.json()

        self.trade_token = quote(token, safe="~()*!.'")  # https://stackoverflow.com/a/72449666/19419998
        return self.trade_url

    async def _fetch_trade_token(self) -> str | None:
        r = await self.session.get(self.profile_url / "tradeoffers/privacy")
        rt = await r.text()

        search = TRADE_TOKEN_RE.search(rt)
        return search["token"] if search else None

    async def _fetch_api_key(self) -> str | None:
        r = await self.session.get(STEAM_URL.COMMUNITY / "dev/apikey")
        rt = await r.text()
        if API_KEY_CHECK_STR in rt or API_KEY_CHECK_STR1 in rt:
            raise ApiError(API_KEY_CHECK_STR1)

        search = API_KEY_RE.search(rt)
        return search["api_key"] if search else None

    async def register_new_api_key(self, domain: str = str(STEAM_URL.COMMUNITY)) -> str:
        """
        Register new api key, cache it and return.

        :param domain: On which domain api key will be registered. Default - `steamcommunity`
        :return: api key
        """

        data = {
            "domain": domain,
            "agreeToTerms": "agreed",
            "sessionid": self.session_id,
            "Submit": "Register",
        }
        r = await self.session.post(STEAM_URL.COMMUNITY / "dev/registerkey", data=data)
        rt = await r.text()

        self._api_key = API_KEY_RE.search(rt)["api_key"]
        return self._api_key

    async def get_notifications(self) -> Notifications:
        """Get notifications count."""

        headers = {"Referer": str(self.profile_url)}
        r = await self.session.get(STEAM_URL.COMMUNITY / "actions/GetNotificationCounts", headers=headers)
        rj = await r.json()
        return Notifications(*(rj["notifications"][str(i)] for i in range(1, 12) if i != 7))

    # https://github.com/DoctorMcKay/node-steamcommunity/blob/851c14bd93008579e7a308ea8ecda873996baa1f/index.js#L405
    def reset_items_notifications(self):
        """Fetching your inventory page, which resets new items notifications to 0."""

        return self.session.get(self.profile_url / "inventory/")

    async def get_inventory(
        self,
        game: GameType,
        *,
        predicate: PREDICATE = None,
        page_size=INV_PAGE_SIZE,
    ) -> list[EconItem]:
        """
        Fetches self inventory. Shorthand for `get_user_inventory(self.steam_id, ...)`.

        :param game: just Steam Game
        :param page_size: max items on page. Current Steam limit is 2000
        :param predicate: callable with single arg `EconItem`, must return bool
        :return: tuple of `EconItem`
        :raises ApiError: for ordinary reasons
        :raises SessionExpired:
        """

        try:
            inv = await self.get_user_inventory(self.steam_id, game, predicate=predicate, page_size=page_size)
        except ApiError as e:
            raise SessionExpired if e.msg == PRIVATE_USER_EXC_MSG else e  # self inventory can't be private

        return inv


# TODO solve problem with class vars or another def values
class SteamPublicClient(SteamPublicMixin):
    __slots__ = ("session",)

    def __init__(
        self,
        *,
        session: ClientSession = None,
    ):
        self.session = session or ClientSession(raise_for_status=True)
