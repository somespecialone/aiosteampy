from re import search as re_search
from json import loads
from typing import AsyncIterator, overload, Callable, final, TYPE_CHECKING

from aiohttp import ClientSession
from aiohttp.client import _RequestContextManager

from .constants import STEAM_URL, Currency, AppContext, Language, T_PARAMS, T_HEADERS, EResult
from .typed import WalletInfo, FundWalletInfo
from .exceptions import EResultError, SessionExpired, SteamError
from .utils import account_id_to_steam_id, generate_device_id
from .models import Notifications, EconItem

from .mixins.public import SteamCommunityPublicMixin, INV_COUNT, INV_ITEM_DATA, T_SHARED_DESCRIPTIONS
from .mixins.profile import ProfileMixin
from .mixins.trade import TradeMixin
from .mixins.market import MarketMixin


DEF_COUNTRY = "UA"
DEF_TZ_OFFSET = "10800,0"


class SteamPublicClientBase(SteamCommunityPublicMixin):
    __slots__ = ()

    SLOTS = ("session", "currency", "country")

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
        """
        Base `Steam Public Community` client class.
        Implements construction method.

        .. note:: Subclass this if you want to make your custom public client

        :param language: language of `Steam` descriptions, responses, etc... Will be set to a cookie
        :param currency: currency of market data in `Steam` responses
        :param country: country of market data in `Steam` responses
        :param tz_offset: timezone offset. Will be set to a cookie
        :param session: session instance. Must be created with `raise_for_status=True` for client to work properly
        :param proxy: proxy url as string. Can be in format `scheme://username:password@host:port` or `scheme://host:port`
        :param user_agent: user agent header value. Strongly advisable to set this
        """

        self.session = self._session_helper(session, proxy)

        if user_agent:
            self.user_agent = user_agent

        self.language = language
        self.tz_offset = tz_offset
        self.currency = currency
        self.country = country

    def __repr__(self) -> str:
        return f"{type(self).__name__}(language={self.language}, tz_offset={self.tz_offset}, currency={self.currency}, country={self.country})"


class SteamClientBase(SteamPublicClientBase, ProfileMixin, MarketMixin, TradeMixin):
    __slots__ = ()

    SLOTS = (
        *SteamPublicClientBase.SLOTS,
        "username",
        "steam_id",
        "_password",
        "_shared_secret",
        "_identity_secret",
        "_api_key",
        "trade_token",
        "device_id",
    )

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
        """
        Base `Steam Community` client class.
        Implements construction, util, account (inventory, wallet) methods.

        .. note:: Subclass this if you want to make your custom client

        :param steam_id: steam id (id64) or account id (id32)
        :param username:
        :param password:
        :param shared_secret:
        :param identity_secret: required for confirmations
        :param access_token: encoded JWT token string
        :param refresh_token: encoded JWT token string
        :param api_key: `Steam Web API` key to have access to `Steam Web API`. Can be used instead of `access_token`
        :param trade_token: trade token of account. Needed to create a trade url
        :param language: language of `Steam` descriptions, responses, etc... Will be set to a cookie
        :param wallet_currency: currency of account wallet. Market methods requires this to be set
        :param wallet_country: country of account wallet. Market methods requires this to be set
        :param tz_offset: timezone offset. Will be set to a cookie
        :param session: session instance. Must be created with `raise_for_status=True` for client to work properly
        :param proxy: proxy url as string. Can be in format `scheme://username:password@host:port` or `scheme://host:port`
        :param user_agent: user agent header value. Strongly advisable to set this
        """

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
        if access_token is not None:
            self.access_token = access_token
        if refresh_token is not None:
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

    async def prepare(self, api_key_domain: str = None, *, force=False):
        """
        Prepares client to work by loading main attributes (trade token, currency and country, optionally api key)
        from `Steam`. Register trade token and api key (optionally) if there is none.
        Edit privacy settings of inventory and related staff to be public

        :param api_key_domain: domain to register `Steam Web Api` key.
            If not passed, api key will not be fetched and registered.
        :param force: force to reload all data even if it presented on client
        """

        if (not self._api_key or force) and api_key_domain:
            await self.get_api_key()
            not self._api_key and await self.register_new_api_key(api_key_domain)

        if not self.trade_token or force:
            await self.get_trade_token()
            not self.trade_token and await self.register_new_trade_url()

        if (not self.currency or not self.country) or force:
            wallet_info = await self.get_wallet_info()
            self.country = wallet_info["wallet_country"]
            self.currency = Currency(wallet_info["wallet_currency"])

        # avoid unnecessary privacy editing
        profile_data = await self.get_profile_data()
        if (
            profile_data["Privacy"]["PrivacySettings"]["PrivacyInventory"] != 3
            or profile_data["Privacy"]["PrivacySettings"]["PrivacyInventoryGifts"] != 3
            or profile_data["Privacy"]["PrivacySettings"]["PrivacyProfile"] != 3
        ):
            await self.edit_privacy_settings(inventory=3, inventory_gifts=True, profile=3)

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

        .. note:: `Steam Store` domain uses own and different one access token from `Steam Community`,
            so it can be expired easily as it not used much in `aiosteampy`

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
        app_context: AppContext,
        *,
        last_assetid: int = None,
        count=INV_COUNT,
        start_assetid: int = None,
        params: T_PARAMS = {},
        headers: T_HEADERS = {},
        _item_descriptions_map: T_SHARED_DESCRIPTIONS = None,
    ) -> INV_ITEM_DATA:
        """
        Fetches self inventory.

        .. note:: You can paginate by yourself passing `start_assetid` arg

        :param app_context: `Steam` app+context
        :param last_assetid:
        :param count: page size
        :param start_assetid: start_assetid for partial inv fetch
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
                app_context,
                last_assetid=last_assetid,
                count=count,
                start_assetid=start_assetid,
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
        app_context: AppContext,
        *,
        last_assetid: int = None,
        count=INV_COUNT,
        start_assetid: int = None,
        params: T_PARAMS = {},
        headers: T_HEADERS = {},
        _item_descriptions_map: T_SHARED_DESCRIPTIONS = None,
    ) -> AsyncIterator[INV_ITEM_DATA]:
        """
        Fetches self inventory. Return async iterator to paginate over inventory pages.

        :param app_context: `Steam` app+context
        :param last_assetid:
        :param count: page size
        :param start_assetid: start_assetid for partial inv fetch
        :param params: extra params to pass to url
        :param headers: extra headers to send with request
        :return: `AsyncIterator` that yields list of `EconItem`, total count of items in inventory, last asset id of the list
        :raises EResultError: for ordinary reasons
        :raises RateLimitExceeded: when you hit rate limit
        :raises SessionExpired:
        """

        return self.user_inventory(
            self.steam_id,
            app_context,
            last_assetid=last_assetid,
            count=count,
            start_assetid=start_assetid,
            params=params,
            headers=headers,
            _item_descriptions_map=_item_descriptions_map,
        )

    @overload
    async def get_inventory_item(
        self,
        app_context: AppContext,
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
        app_context: AppContext,
        obj: Callable[[EconItem], bool],
        *,
        params: T_PARAMS = ...,
        headers: T_HEADERS = ...,
    ) -> EconItem | None:
        ...

    async def get_inventory_item(
        self,
        app_context: AppContext,
        obj: int | Callable[[EconItem], bool] = None,
        *,
        params: T_PARAMS = {},
        headers: T_HEADERS = {},
        _item_descriptions_map: T_SHARED_DESCRIPTIONS = None,
        **item_attrs,
    ) -> EconItem | None:
        """
        Fetch and iterate over inventory item pages of self until find one that satisfies passed arguments.

        :param app_context: `Steam` app+context
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
                app_context,
                obj,
                params=params,
                headers=headers,
                _item_descriptions_map=_item_descriptions_map,
                **item_attrs,
            )
        except SteamError as e:
            if "private" in e.args[0]:  # self inventory can't be private
                raise SessionExpired from e
            else:
                raise e

    def __repr__(self) -> str:
        return f"{type(self).__name__}(steam_id={self.steam_id}, username={self.username})"


@final
class SteamClient(SteamClientBase):
    __slots__ = SteamClientBase.SLOTS

    if TYPE_CHECKING:  # for PyCharm pop-up

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
            steam_id: int,
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
            """
            Ready to use client class with inherited methods from all mixins. Must be logged in.

            :param steam_id: steam id (id64) or account id (id32)
            :param username:
            :param password:
            :param shared_secret:
            :param identity_secret: required for confirmations
            :param access_token: encoded JWT token string
            :param refresh_token: encoded JWT token string
            :param api_key: `Steam Web API` key to have access to `Steam Web API`. Can be used instead of `access_token`
            :param trade_token: trade token of account. Needed to create a trade url
            :param language: language of `Steam` descriptions, responses, etc... Will be set to a cookie
            :param wallet_currency: currency of account wallet. Market methods requires this to be set
            :param wallet_country: country of account wallet. Market methods requires this to be set
            :param tz_offset: timezone offset. Will be set to a cookie
            :param session: session instance. Must be created with `raise_for_status=True` for client to work properly
            :param proxy: proxy url as string. Can be in format `scheme://username:password@host:port` or `scheme://host:port`
            :param user_agent: user agent header value. Strongly advisable to set this
            """


@final
class SteamPublicClient(SteamPublicClientBase):
    __slots__ = SteamPublicClientBase.SLOTS

    if TYPE_CHECKING:  # for PyCharm pop-up

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
            """
            Client contains public methods that do not require authentication.

            :param language: language of `Steam` descriptions, responses, etc... Will be set to a cookie
            :param currency: currency of market data in `Steam` responses
            :param country: country of market data in `Steam` responses
            :param tz_offset: timezone offset. Will be set to a cookie
            :param session: session instance. Must be created with `raise_for_status=True` for client to work properly
            :param proxy: proxy url as string. Can be in format `scheme://username:password@host:port` or `scheme://host:port`
            :param user_agent: user agent header value. Strongly advisable to set this
            """
