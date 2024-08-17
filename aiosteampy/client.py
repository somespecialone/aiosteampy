from re import search as re_search
from json import loads
from typing import AsyncIterator, overload, Callable, final

from aiohttp import ClientSession
from aiohttp.client import _RequestContextManager

from .constants import STEAM_URL, Currency, GameType, Language, T_PARAMS, T_HEADERS, EResult
from .typed import WalletInfo, FundWalletInfo
from .exceptions import EResultError, SessionExpired, SteamError
from .utils import account_id_to_steam_id, generate_device_id
from .models import Notifications, EconItem

from .mixins.public import SteamCommunityPublicMixin, INV_COUNT, INV_ITEM_DATA
from .mixins.profile import ProfileMixin
from .mixins.trade import TradeMixin
from .mixins.market import MarketMixin


DEF_COUNTRY = "UA"
DEF_TZ_OFFSET = "10800,0"


class SteamPublicClientBase(SteamCommunityPublicMixin):
    """
    Base `Steam Public Community` client class.
    Implements construction method.

    .. note:: Subclass this if you want to make your custom public client
    """

    __slots__ = ()

    @overload
    def __init__(
        self,
        *,
        language: Language = ...,
        tz_offset: str = ...,
        currency: Currency = ...,
        country: str = ...,
        session: ClientSession = ...,
        user_agent: str = ...,
    ):
        ...

    @overload
    def __init__(
        self,
        *,
        language: Language = ...,
        tz_offset: str = ...,
        currency: Currency = ...,
        country: str = ...,
        proxy: str = ...,
        user_agent: str = ...,
    ):
        ...

    def __init__(
        self,
        *,
        language=Language.ENGLISH,
        tz_offset=DEF_TZ_OFFSET,
        currency=Currency.USD,
        country=DEF_COUNTRY,
        session: ClientSession = None,
        proxy: str = None,
        user_agent: str = None,
    ):
        """TODO"""

        self.session = self._session_helper(session, proxy)

        if user_agent:
            self.user_agent = user_agent

        self.language = language
        self.tz_offset = tz_offset
        self.currency = currency
        self.country = country


class SteamClientBase(SteamPublicClientBase, ProfileMixin, MarketMixin, TradeMixin):
    """
    Base `Steam Community` client class.
    Implements construction, util, account (inventory, wallet) methods.

    .. note:: Subclass this if you want to make your custom client
    """

    __slots__ = ()

    @overload
    def __init__(
        self,
        steam_id: int,
        username: str,
        password: str,
        shared_secret: str,
        identity_secret: str = ...,
        *,
        access_token: str = ...,
        refresh_token: str = ...,
        api_key: str = ...,
        trade_token: str = ...,
        language: Language = ...,
        wallet_currency: Currency = ...,
        wallet_country: str = ...,
        tz_offset: str = ...,
        session: ClientSession = ...,
        user_agent: str = ...,
    ):
        ...

    @overload
    def __init__(
        self,
        steam_id: int,
        username: str,
        password: str,
        shared_secret: str,
        identity_secret: str = ...,
        *,
        access_token: str = ...,
        refresh_token: str = ...,
        api_key: str = ...,
        trade_token: str = ...,
        language: Language = ...,
        wallet_currency: Currency = ...,
        wallet_country: str = ...,
        tz_offset: str = ...,
        proxy: str = ...,
        user_agent: str = ...,
    ):
        ...

    def __init__(
        self,
        # It is possible to get steam id from the cookie and then arg will not be necessary,
        # but typical use case of the library means that the user already knows the steam id
        steam_id: int,  # first as intend to be mandatory
        username: str,
        password: str,
        shared_secret: str,
        identity_secret: str = None,
        *,
        access_token: str = None,
        refresh_token: str = None,
        api_key: str = None,
        trade_token: str = None,
        language=Language.ENGLISH,
        wallet_currency: Currency = None,
        wallet_country=DEF_COUNTRY,
        tz_offset=DEF_TZ_OFFSET,
        session: ClientSession = None,
        proxy: str = None,
        user_agent: str = None,
    ):
        """TODO"""

        super().__init__(
            language=language,
            tz_offset=tz_offset,
            currency=wallet_currency,
            country=wallet_country,
            session=session,
            proxy=proxy,
            user_agent=user_agent,
        )

        # guard
        self.steam_id = account_id_to_steam_id(steam_id) if steam_id < 4294967296 else steam_id  # steam id64
        self.device_id = generate_device_id(self.steam_id)

        self._shared_secret = shared_secret
        self._identity_secret = identity_secret

        # login
        self.username = username
        self._password = password
        self.access_token = access_token
        self.refresh_token = refresh_token

        # profile
        self.trade_token = trade_token

        # web api
        self._api_key = api_key

    # aliases for convenience
    @property
    def wallet_currency(self) -> Currency:
        return self.currency

    @property
    def wallet_country(self) -> str:
        return self.country

    # TODO remove this or rename to prepare and refactor
    async def init_data(self):
        if not self._api_key:
            self._api_key = await self.fetch_api_key()
            not self._api_key and await self.register_new_api_key()

        if not self.trade_token:
            self.trade_token = await self.get_trade_token()
            not self.trade_token and await self.register_new_trade_url()

        if not self.currency:
            wallet_info = await self.get_wallet_info()
            self.country = wallet_info["wallet_country"]
            self.currency = Currency(wallet_info["wallet_currency"])

    async def get_wallet_info(self) -> WalletInfo:
        """
        Fetch wallet info from inventory page.

        .. note:: May reset new items notifications count.

        :return: wallet info
        :raises EResultError: for ordinary reasons
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
        Fetch wallet info from inventory page, parse and return balance.

        .. note:: May reset new items notifications count.

        :return: wallet balance as integer
        :raises EResultError: for ordinary reasons
        """

        info = await self.get_wallet_info()
        return int(info["wallet_balance"])

    async def get_fund_wallet_info(self) -> FundWalletInfo:
        """
        Fetch fund wallet info from `Steam Store` domain.

        .. note:: TODO

        :return: `FundWalletInfo`
        :raises EResultError: for ordinary reasons
        """

        r = await self.session.get(STEAM_URL.STORE / "api/getfundwalletinfo")
        rj: FundWalletInfo = await r.json()
        success = EResult(rj.get("success"))
        if success is not EResult.OK:
            raise EResultError(rj.get("message", "Failed to fetch wallet balance"), success, rj)

        return rj

    async def get_notifications(self) -> Notifications:
        """Get notifications count."""

        headers = {"Referer": str(self.profile_url)}
        r = await self.session.get(STEAM_URL.COMMUNITY / "actions/GetNotificationCounts", headers=headers)
        rj = await r.json()
        return Notifications(*(rj["notifications"][str(i)] for i in range(1, 12) if i != 7))

    # https://github.com/DoctorMcKay/node-steamcommunity/blob/7c564c1453a5ac413d9312b8cf8fe86e7578b309/index.js#L275
    def reset_items_notifications(self) -> _RequestContextManager:
        """Fetches self inventory page, which resets new items notifications to 0."""

        return self.session.get(self.profile_url / "inventory/")

    async def get_inventory(
        self,
        game: GameType,
        *,
        last_assetid: int = None,
        count=INV_COUNT,
        params: T_PARAMS = {},
        headers: T_HEADERS = {},
        _item_descriptions_map: dict = None,
    ) -> INV_ITEM_DATA:
        """
        Fetches self inventory.

        .. note::
            * You can paginate by yourself passing `last_assetid` arg
            * `count` arg value that less than 2000 lead to responses with strange amount of assets

        :param game: Steam Game
        :param last_assetid:
        :param count: page size
        :param params: extra params to pass to url
        :param headers: extra headers to send with request
        :return: list of `EconItem`, total count of items in inventory, last asset id of the list
        :raises EResultError: for ordinary reasons
        :raises RateLimitExceeded: when you hit rate limit
        :raises SessionExpired:
        """

        try:
            return await self.get_user_inventory(
                self.steam_id,
                game,
                last_assetid=last_assetid,
                count=count,
                params=params,
                headers=headers,
                _item_descriptions_map=_item_descriptions_map,
            )
        except SteamError as e:
            if "private" in e.args[0]:  # self inventory can't be private
                raise SessionExpired from e
            else:
                raise e

    def inventory(
        self,
        game: GameType,
        *,
        last_assetid: int = None,
        count=INV_COUNT,
        params: T_PARAMS = {},
        headers: T_HEADERS = {},
    ) -> AsyncIterator[INV_ITEM_DATA]:
        """
        Fetches self inventory. Return async iterator to paginate over inventory pages.

        .. note:: `count` arg value that less than 2000 lead to responses with strange amount of assets

        :param game: Steam Game
        :param last_assetid:
        :param count: page size
        :param params: extra params to pass to url
        :param headers: extra headers to send with request
        :return: `AsyncIterator` that yields list of `EconItem`, total count of items in inventory, last asset id of the list
        :raises EResultError: for ordinary reasons
        :raises RateLimitExceeded: when you hit rate limit
        :raises SessionExpired:
        """

        return self.user_inventory(
            self.steam_id,
            game,
            last_assetid=last_assetid,
            count=count,
            params=params,
            headers=headers,
        )

    @overload
    async def get_inventory_item(
        self,
        game: GameType,
        obj: int = ...,
        *,
        params: T_PARAMS = ...,
        headers: T_HEADERS = ...,
        **item_attrs,
    ) -> EconItem | None:
        ...

    @overload
    async def get_inventory_item(
        self,
        game: GameType,
        obj: Callable[[EconItem], bool],
        *,
        params: T_PARAMS = ...,
        headers: T_HEADERS = ...,
    ) -> EconItem | None:
        ...

    async def get_inventory_item(
        self,
        game: GameType,
        obj: int | Callable[[EconItem], bool] = None,
        *,
        params: T_PARAMS = {},
        headers: T_HEADERS = {},
        **item_attrs,
    ) -> EconItem | None:
        """
        Fetch and iterate over inventory item pages of self until find one that satisfies passed arguments.

        :param game: `Steam` game
        :param obj: asset id or predicate function
        :param params: extra params to pass to url
        :param headers: extra headers to send with request
        :param item_attrs: additional item attributes and values
        :return: `EconItem` or `None`
        :raises EResultError: for ordinary reasons
        :raises RateLimitExceeded: when you hit rate limit
        :raises SessionExpired:
        """

        try:
            return await self.get_user_inventory_item(
                self.steam_id,
                game,
                obj,
                params=params,
                headers=headers,
                **item_attrs,
            )
        except SteamError as e:
            if "private" in e.args[0]:  # self inventory can't be private
                raise SessionExpired from e
            else:
                raise e


@final
class SteamClient(SteamClientBase):
    """Ready to use client class with all inherited methods."""

    __slots__ = (
        "_refresh_token",
        "session",
        "username",
        "steam_id",
        "_password",
        "_shared_secret",
        "_identity_secret",
        "_api_key",
        "trade_token",
        "device_id",
        "currency",
        "country",
    )


@final
class SteamPublicClient(SteamPublicClientBase):
    """Client contain public methods without authentication."""

    __slots__ = ("session", "currency", "country")
