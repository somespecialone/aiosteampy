from re import compile, search as re_search
from urllib.parse import quote
from json import loads
from http.cookies import SimpleCookie

from aiohttp import ClientSession
from aiohttp.client import _RequestContextManager
from yarl import URL

from .models import Notifications, EconItem
from .typed import WalletInfo, FundWalletInfo
from .constants import STEAM_URL, Currency, GameType, Language, EResult
from .exceptions import EResultError, SessionExpired, SteamError
from .utils import get_cookie_value_from_session, steam_id_to_account_id, account_id_to_steam_id

from .http import SteamHTTPTransportMixin
from .guard import SteamGuardMixin
from .confirmation import ConfirmationMixin
from .login import LoginMixin
from .trade import TradeMixin
from .market import MarketMixin
from .public import SteamPublicMixin, INV_PAGE_SIZE, PREDICATE

API_KEY_RE = compile(r"<p>Key: (?P<api_key>[0-9A-F]+)</p>")
STEAM_GUARD_REQ_CHECK_RE = compile(r"Your account requires (<a [^>]+>)?Steam Guard Mobile Authenticator")

STEAM_LANG_COOKIE = "Steam_Language"
DEF_COUNTRY = "UA"


class SteamCommunityMixin(
    SteamGuardMixin,
    ConfirmationMixin,
    LoginMixin,
    MarketMixin,
    TradeMixin,
    SteamPublicMixin,
    SteamHTTPTransportMixin,
):
    """
    Mixin class, but with `__init__`. Inherits all other mixins.
    Needed in case you want to use multiple inheritance with `__slots__`.
    """

    __slots__ = ()

    username: str
    steam_id: int | None
    trade_token: str

    def __init__(
        self,
        username: str,
        password: str,
        # It is possible to get steam id from the cookie and then arg will not be necessary,
        # but typical use case of the library means that the user already knows the steam id
        steam_id: int,
        *,
        shared_secret: str,
        identity_secret: str = None,
        refresh_token: str = None,
        access_token: str = None,
        api_key: str = None,
        trade_token: str = None,
        wallet_currency: Currency = None,
        wallet_country=DEF_COUNTRY,
        lang=Language.ENGLISH,
        tz_offset=0.0,
        session: ClientSession = None,
        proxy: str = None,
        user_agent: str = None,
    ):
        self.username = username
        self.steam_id = account_id_to_steam_id(steam_id) if steam_id < 4294967296 else steam_id  # steam id64
        self.trade_token = trade_token

        self._password = password
        self._shared_secret = shared_secret
        self._identity_secret = identity_secret
        self._api_key = api_key
        self._wallet_currency = wallet_currency

        self._wallet_country = wallet_country

        super().__init__(
            session=session,
            user_agent=user_agent,
            access_token=access_token,
            refresh_token=refresh_token,
            proxy=proxy,
        )

        self._set_init_cookies(lang, tz_offset)

    @property
    def account_id(self) -> int:
        """Steam id32."""
        return steam_id_to_account_id(self.steam_id)

    @property
    def trade_url(self) -> URL:
        return STEAM_URL.TRADE / "new/" % {"partner": self.account_id, "token": self.trade_token or ""}

    @property
    def profile_url(self) -> URL:
        return STEAM_URL.COMMUNITY / f"profiles/{self.steam_id}"

    @property
    def language(self) -> Language:
        """Language of Steam html pages, json info, descriptions, etc."""
        return Language(get_cookie_value_from_session(self.session, STEAM_URL.STORE, STEAM_LANG_COOKIE))

    @property
    def country(self) -> str:
        """Just wallet country. Needed for public methods."""
        return self._wallet_country

    @property
    def currency(self) -> Currency:
        """Alias for wallet currency. Needed for public methods."""
        return self._wallet_currency

    def _set_init_cookies(self, lang: str, tz_offset: float):
        urls = (STEAM_URL.COMMUNITY, STEAM_URL.STORE, STEAM_URL.HELP)
        for url in urls:
            c = SimpleCookie()
            c[STEAM_LANG_COOKIE] = lang
            c[STEAM_LANG_COOKIE]["path"] = "/"
            c[STEAM_LANG_COOKIE]["domain"] = url.host
            c[STEAM_LANG_COOKIE]["secure"] = True

            self.session.cookie_jar.update_cookies(cookies=c, response_url=url)

        # Is it needed?
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
            self._api_key = await self.fetch_api_key()
            not self._api_key and await self.register_new_api_key()

        if not self.trade_token:
            self.trade_token = await self._fetch_trade_token()
            not self.trade_token and await self.register_new_trade_url()

        if not self._wallet_currency:
            wallet_info = await self.fetch_wallet_info()
            self._wallet_country = wallet_info["wallet_country"]
            self._wallet_currency = Currency(wallet_info["wallet_currency"])

    async def fetch_wallet_info(self) -> WalletInfo:
        """
        Get wallet info from inventory page.

        .. warning:: May reset new items notifications count.

        :return: wallet info
        :raises EResultError:
        """

        r = await self.session.get(self.profile_url / "inventory", headers={"Referer": str(self.profile_url)})
        rt = await r.text()
        info: WalletInfo = loads(re_search(r"g_rgWalletInfo = (?P<info>.+);", rt)["info"])
        success = EResult(info.get("success"))
        if success is not EResult.OK:
            raise EResultError(info.get("message", "Failed to fetch wallet info from inventory"), success, info)

        return info

    async def get_wallet_balance(self) -> int:
        """
        Fetch wallet balance.

        :raises EResultError:
        """

        # Why is this endpoint do not work sometimes?
        r = await self.session.get(STEAM_URL.STORE / "api/getfundwalletinfo")
        rj: FundWalletInfo = await r.json()
        success = EResult(rj.get("success"))
        if success is not EResult.OK:
            raise EResultError(rj.get("message", "Failed to fetch wallet balance"), success, rj)

        if not self._wallet_currency:
            self._wallet_currency = Currency.by_name(rj["user_wallet"]["currency"])

        return int(rj["user_wallet"]["amount"])

    async def register_new_trade_url(self) -> URL:
        """Register new trade url. Cache token."""

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

        search = re_search(r"\d+&token=(?P<token>.+)\" readonly", rt)
        return search["token"] if search else None

    async def fetch_api_key(self) -> str:
        """
        Fetch Steam Web Api Key, cache it and return.

        :raises SteamError:
        """

        # https://github.com/DoctorMcKay/node-steamcommunity/blob/b58745c8b74963eae808d33e558dbba6840c7053/components/webapi.js#L18
        r = await self.session.get(STEAM_URL.COMMUNITY / "dev/apikey", params={"l": "english"}, allow_redirects=False)
        rt = await r.text()

        if "You must have a validated email address to create a Steam Web API key" in rt:
            raise SteamError("Validated email address required to create a Steam Web API key")
        elif STEAM_GUARD_REQ_CHECK_RE.search(rt):
            raise SteamError("")
        elif "<h2>Access Denied</h2>" in rt:
            raise SteamError("Access to Steam Web Api page is denied")

        search = API_KEY_RE.search(rt)
        if not search:
            raise SteamError("Failed to get Steam Web API key", rt)

        self._api_key = search["api_key"]
        return self._api_key

    def revoke_api_key(self) -> _RequestContextManager:
        """Revoke old Steam Web API Key."""

        data = {
            "sessionid": self.session_id,
            "Revoke": "Revoke My Steam Web API Key",
        }
        return self.session.post(STEAM_URL.COMMUNITY / "dev/revokekey", data=data, allow_redirects=False)

    async def register_new_api_key(self, domain="github.com/somespecialone/aiosteampy") -> str:
        """
        Request registration of a new api key, confirm, cache it and return.

        :param domain: on which domain api key will be registered. Strongly recommended to pass non-default value
        :return: Steam Web Api Key
        :raises EResultError:
        """

        # https://github.com/DoctorMcKay/node-steamcommunity/blob/b58745c8b74963eae808d33e558dbba6840c7053/components/webapi.js#L78

        await self.revoke_api_key()  # revoke old one as website do

        data = {
            "domain": domain,
            "request_id": 0,
            "sessionid": self.session_id,
            "agreeToTerms": "true",
        }
        r = await self.session.post(STEAM_URL.COMMUNITY / "dev/requestkey", data=data)
        rj: dict[str, str | int] = await r.json()
        success = EResult(rj.get("success"))

        if success is EResult.PENDING and rj.get("requires_confirmation"):
            await self.confirm_api_key_request(rj["request_id"])
            r = await self.session.post(STEAM_URL.COMMUNITY / "dev/requestkey", data=data)
            rj: dict[str, str | int] = await r.json()
            success = EResult(rj.get("success"))

        if success is not EResult.OK or not rj["api_key"]:
            raise EResultError(rj.get("message", "Failed to get Steam Web Api Key"), success, rj)

        self._api_key = rj["api_key"]
        return self._api_key

    async def get_notifications(self) -> Notifications:
        """Get notifications count."""

        headers = {"Referer": str(self.profile_url)}
        r = await self.session.get(STEAM_URL.COMMUNITY / "actions/GetNotificationCounts", headers=headers)
        rj = await r.json()
        return Notifications(*(rj["notifications"][str(i)] for i in range(1, 12) if i != 7))

    def reset_items_notifications(self) -> _RequestContextManager:
        """
        Fetches self inventory page, which resets new items notifications to 0.

        .. seealso:: https://github.com/DoctorMcKay/node-steamcommunity/blob/7c564c1453a5ac413d9312b8cf8fe86e7578b309/index.js#L275
        """

        return self.session.get(self.profile_url / "inventory/")

    async def get_inventory(
        self,
        game: GameType,
        *,
        predicate: PREDICATE = None,
        page_size=INV_PAGE_SIZE,
    ) -> list[EconItem]:
        """
        Fetches self inventory.

        :param game: just Steam Game
        :param page_size: max items on page. Current Steam limit is 2000
        :param predicate: callable with single arg `EconItem`, must return bool
        :return: list of `EconItem`
        :raises EResultError: for ordinary reasons
        :raises SessionExpired:
        """

        try:
            inv = await self.get_user_inventory(self.steam_id, game, predicate=predicate, page_size=page_size)
        except SteamError as e:
            raise SessionExpired if "private" in e.args[0] else e  # self inventory can't be private
        return inv


class SteamClient(SteamCommunityMixin):
    """Ready to use client class with all inherited methods."""

    __slots__ = (
        "_is_logged",
        "_refresh_token",
        "_access_token",
        "session",
        "username",
        "steam_id",
        "_password",
        "_shared_secret",
        "_identity_secret",
        "_api_key",
        "trade_token",
        "device_id",
        "_wallet_currency",
        "_wallet_country",
    )


class SteamPublicClient(SteamPublicMixin, SteamHTTPTransportMixin):
    """Class for public methods that do not require login."""

    __slots__ = ("session", "language", "currency", "country")

    def __init__(
        self,
        *,
        language=Language.ENGLISH,
        currency=Currency.USD,
        country=DEF_COUNTRY,
        session: ClientSession = None,
        proxy: str = None,
        user_agent: str = None,
    ):
        self.language = language
        self.currency = currency
        self.country = country

        super().__init__(session=session, user_agent=user_agent, proxy=proxy)
