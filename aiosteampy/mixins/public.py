from contextlib import suppress
from typing import TypeAlias, overload, AsyncIterator, Literal, Callable
from datetime import datetime
from re import compile as re_compile

from aiohttp import ClientResponseError

from ..constants import STEAM_URL, App, AppContext, Currency, T_PARAMS, T_HEADERS, EResult
from ..helpers import currency_required
from ..typed import ItemOrdersHistogramData, ItemOrdersActivity, PriceOverview
from ..exceptions import EResultError, SteamError, RateLimitExceeded, ResourceNotModified
from ..utils import (
    create_ident_code,
    find_item_nameid_in_text,
    parse_time,
    format_time,
)
from ..models import (
    ItemDescriptionEntry,
    ItemTag,
    ItemDescription,
    EconItem,
    ItemAction,
    MarketListing,
    MarketListingItem,
    ItemOrdersHistogram,
    SellOrderTableEntry,
    BuyOrderTableEntry,
    OrderGraphEntry,
)
from .http import SteamHTTPTransportMixin


# steam limit rules
INV_COUNT = 5000
LISTING_COUNT = 10

INVENTORY_URL = STEAM_URL.COMMUNITY / "inventory"

# listings, total count, last modified
T_MARKET_ITEM_LISTINGS_DATA: TypeAlias = tuple[list[MarketListing], int, datetime]
INV_ITEM_DATA: TypeAlias = tuple[list[EconItem], int, int | None]  # items, total count, last asset id for pagination

ITEM_ORDER_HIST_PRICE_RE = re_compile(r"[^\d\s]*([\d,]+(?:\.\d+)?)[^\d\s]*")  # Author: ChatGPT

T_SHARED_DESCRIPTIONS: TypeAlias = dict[str, ItemDescription]  # ident code : descr


class SteamCommunityPublicMixin(SteamHTTPTransportMixin):
    """
    Contains methods that do not require authentication.
    Depends on `SteamHTTPTransportMixin`.
    """

    __slots__ = ()

    # required instance attributes
    currency: Currency | None
    country: str

    async def get_user_inventory(
        self,
        steam_id: int,
        app_context: AppContext,
        *,
        last_assetid: int = None,
        count=INV_COUNT,
        params: T_PARAMS = {},
        headers: T_HEADERS = {},
        _item_descriptions_map: T_SHARED_DESCRIPTIONS = None,
    ) -> INV_ITEM_DATA:
        """
        Fetches inventory of user.

        .. note::
            * You can paginate by yourself passing `last_assetid` arg
            * `count` arg value that less than 2000 lead to responses with strange amount of assets

        :param steam_id: steamid64 of user
        :param app_context: `Steam` app+context
        :param last_assetid:
        :param count: page size
        :param params: extra params to pass to url
        :param headers: extra headers to send with request
        :return: list of `EconItem`, total count of items in inventory, last asset id of the list
        :raises SteamError: if inventory is private
        :raises EResultError: for ordinary reasons
        :raises RateLimitExceeded: when you hit rate limit
        """

        inv_url = INVENTORY_URL / f"{steam_id}/"
        params = {"l": self.language, "count": count, **params}
        if last_assetid:
            params["last_assetid"] = last_assetid
        headers = {"Referer": str(inv_url), **headers}

        try:
            r = await self.session.get(
                inv_url / f"{app_context.app.value}/{app_context.context}",
                params=params,
                headers=headers,
            )
        except ClientResponseError as e:
            if e.status == 403:
                # https://github.com/DoctorMcKay/node-steamcommunity/blob/master/components/users.js#L603
                raise SteamError("Steam user inventory is private") from e
            elif e.status == 429:  # never faced this, but let it be
                raise RateLimitExceeded("You have been rate limited, rest for a while!") from e
            else:
                raise e

        rj: dict[str, list[dict] | int] = await r.json()
        success = EResult(rj.get("success"))
        if success is not EResult.OK:
            raise EResultError(rj.get("message", "Failed to fetch inventory"), success, rj)

        total_count = rj["total_inventory_count"]
        last_assetid_return = int(rj["last_assetid"]) if "last_assetid" in rj else None

        if "descriptions" not in rj:  # count<=101, last_assetid=None and we got there
            return [], total_count, last_assetid_return

        if _item_descriptions_map is None:
            _item_descriptions_map = {}

        items = self._parse_inventory(rj, steam_id, _item_descriptions_map)

        return items, total_count, last_assetid_return

    @classmethod
    def _parse_inventory(
        cls,
        data: dict[str, list[dict]],
        steam_id: int,
        descrs_map: dict[str, ItemDescription],
    ) -> list[EconItem]:
        for d_data in data["descriptions"]:
            key = create_ident_code(d_data["instanceid"], d_data["classid"], d_data["appid"])
            if key not in descrs_map:
                descrs_map[key] = cls._create_item_descr(d_data)

        return [
            EconItem(
                asset_id=int(a_data["assetid"]),
                owner_id=steam_id,
                amount=int(a_data["amount"]),
                description=descrs_map[create_ident_code(a_data["instanceid"], a_data["classid"], a_data["appid"])],
                app_context=AppContext((App(int(a_data["appid"])), int(a_data["contextid"]))),
            )
            for a_data in data["assets"]
        ]

    @classmethod
    def _create_item_actions(cls, actions: list[dict]) -> tuple[ItemAction, ...]:
        return tuple(ItemAction(a_data["link"], a_data["name"]) for a_data in actions)

    @classmethod
    def _create_item_tags(cls, tags: list[dict]) -> tuple[ItemTag, ...]:
        return tuple(
            ItemTag(
                t_data["category"],
                t_data["internal_name"],
                t_data["localized_category_name"],
                t_data["localized_tag_name"],
                t_data.get("color"),
            )
            for t_data in tags
        )

    @classmethod
    def _create_item_descr_entries(cls, descriptions: list[dict]) -> tuple[ItemDescriptionEntry, ...]:
        return tuple(
            ItemDescriptionEntry(de_data["value"], de_data.get("color"))
            for de_data in descriptions
            if de_data["value"] != " "  # ha, surprise!
        )

    @classmethod
    def _create_item_descr(cls, data: dict) -> ItemDescription:
        return ItemDescription(
            class_id=int(data["classid"]),
            instance_id=int(data["instanceid"]),
            app=App(data["appid"]),
            name=data["name"],
            market_name=data["market_name"],
            market_hash_name=data["market_hash_name"],
            name_color=data.get("name_color") or None,
            background_color=data.get("name_color") or None,
            type=data["type"] or None,
            icon=data["icon_url"],
            icon_large=data.get("icon_url_large"),
            commodity=bool(data["commodity"]),
            tradable=bool(data["tradable"]),
            marketable=bool(data["marketable"]),
            market_tradable_restriction=data.get("market_tradable_restriction"),
            market_buy_country_restriction=data.get("market_buy_country_restriction"),
            market_fee_app=data.get("market_fee_app"),
            market_marketable_restriction=data.get("market_marketable_restriction"),
            actions=cls._create_item_actions(data["actions"]) if "actions" in data else (),
            market_actions=cls._create_item_actions(data["market_actions"]) if "market_actions" in data else (),
            owner_actions=cls._create_item_actions(data["owner_actions"]) if "owner_actions" in data else (),
            tags=cls._create_item_tags(data["tags"]) if "tags" in data else (),
            descriptions=cls._create_item_descr_entries(data["descriptions"]) if "descriptions" in data else (),
            owner_descriptions=cls._create_item_descr_entries(data["owner_descriptions"])
            if "owner_descriptions" in data
            else (),
            fraud_warnings=tuple(data.get("fraudwarnings", ())),
        )

    async def user_inventory(
        self,
        steam_id: int,
        app_context: AppContext,
        *,
        last_assetid: int = None,
        count=INV_COUNT,
        params: T_PARAMS = {},
        headers: T_HEADERS = {},
        _item_descriptions_map: T_SHARED_DESCRIPTIONS = None,
    ) -> AsyncIterator[INV_ITEM_DATA]:
        """
        Fetches inventory of user. Return async iterator to paginate over inventory pages.

        .. note:: `count` arg value that less than 2000 lead to responses with strange amount of assets

        :param steam_id: steamid64 of user
        :param app_context: `Steam` app+context
        :param last_assetid:
        :param count: page size
        :param params: extra params to pass to url
        :param headers: extra headers to send with request
        :return: `AsyncIterator` that yields list of `EconItem`, total count of items in inventory, last asset id of the list
        :raises EResultError: for ordinary reasons
        :raises RateLimitExceeded: when you hit rate limit
        :raises SteamError: if inventory is private
        """

        if _item_descriptions_map is None:  # shared descriptions instances across calls
            _item_descriptions_map = {}

        more_items = True
        while more_items:
            # browser do first request with count=75, receiving data with `last_assetid` only
            # avoid excess destructuring
            inventory_data = await self.get_user_inventory(
                steam_id,
                app_context,
                last_assetid=last_assetid,
                count=count,
                params=params,
                headers=headers,
                _item_descriptions_map=_item_descriptions_map,
            )
            last_assetid = inventory_data[2]
            # let's assume that field "last_assetid" always present with "more_items" so we can depend on it
            more_items = bool(last_assetid)

            yield inventory_data

    @overload
    async def get_user_inventory_item(
        self,
        steam_id: int,
        app_context: AppContext,
        obj: int = ...,
        *,
        params: T_PARAMS = ...,
        headers: T_HEADERS = ...,
        **item_attrs,
    ) -> EconItem | None:
        ...

    @overload
    async def get_user_inventory_item(
        self,
        steam_id: int,
        app_context: AppContext,
        obj: Callable[[EconItem], bool],
        *,
        params: T_PARAMS = ...,
        headers: T_HEADERS = ...,
    ) -> EconItem | None:
        ...

    async def get_user_inventory_item(
        self,
        steam_id: int,
        app_context: AppContext,
        obj: int | Callable[[EconItem], bool] = None,
        *,
        params: T_PARAMS = {},
        headers: T_HEADERS = {},
        _item_descriptions_map: T_SHARED_DESCRIPTIONS = None,
        **item_attrs,
    ) -> EconItem | None:
        """
        Fetch and iterate over inventory item pages of user until find one that satisfies passed arguments.

        :param steam_id: steamid64 of user
        :param app_context: `Steam` app+context
        :param obj: asset id or predicate function
        :param params: extra params to pass to url
        :param headers: extra headers to send with request
        :param item_attrs: additional item attributes and values
        :return: `EconItem` or `None`
        :raises EResultError: for ordinary reasons
        :raises RateLimitExceeded: when you hit rate limit
        :raises SteamError: if inventory is private
        """

        if callable(obj):
            predicate = obj
        else:

            def predicate(i: EconItem):
                if obj is not None and i.asset_id != obj:
                    return False

                for attr, value in item_attrs.items():
                    if getattr(i, attr, None) != value:
                        return False

                return True

        if _item_descriptions_map is None:
            _item_descriptions_map = {}

        async for data in self.user_inventory(
            steam_id,
            app_context,
            params=params,
            headers=headers,
            _item_descriptions_map=_item_descriptions_map,
        ):
            with suppress(StopIteration):
                return next(filter(predicate, data[0]))

    @overload
    async def get_item_orders_histogram(
        self,
        item_nameid: int,
        *,
        if_modified_since: datetime | str = ...,
        params: T_PARAMS = ...,
        headers: T_HEADERS = ...,
    ) -> ItemOrdersHistogram:
        ...

    @overload
    async def get_item_orders_histogram(
        self,
        item_nameid: int,
        *,
        raw: Literal[True] = ...,
        if_modified_since: datetime | str = ...,
        params: T_PARAMS = ...,
        headers: T_HEADERS = ...,
    ) -> ItemOrdersHistogramData:
        ...

    @currency_required
    async def get_item_orders_histogram(
        self,
        item_nameid: int,
        *,
        raw: bool = False,
        if_modified_since: datetime | str = None,
        params: T_PARAMS = {},
        headers: T_HEADERS = {},
    ) -> ItemOrdersHistogramData | ItemOrdersHistogram:
        """
        Do what described in method name.

        .. seealso::
            * https://github.com/Revadike/InternalSteamWebAPI/wiki/Get-Market-Item-Orders-Histogram
            * https://github.com/somespecialone/steam-item-name-ids

        .. note:: This request is rate limited by Steam. It is strongly recommended to use `if_modified_since`

        :param item_nameid: special id of item class. Can be found only on listings page.
        :param raw: if `True`, return `ItemOrdersHistogramData` dict instead of `ItemOrdersHistogram` model
        :param if_modified_since: `If-Modified-Since` header value
        :param params: extra params to pass to url
        :param headers: extra headers to send with request
        :return: `ItemOrdersHistogramData` dict if `raw` is `True` or `ItemOrdersHistogram` model
        :raises EResultError: for ordinary reasons
        :raises RateLimitExceeded: when you hit rate limit
        :raises ResourceNotModified: when `if_modified_since` header passed and Steam response with 304 status code
        """

        params = {
            "norender": 1,
            "language": self.language,
            "country": self.country,
            "currency": self.currency,
            "item_nameid": item_nameid,
            **params,
        }
        headers = {**headers}
        if if_modified_since:
            if isinstance(if_modified_since, datetime):
                headers["If-Modified-Since"] = format_time(if_modified_since)
            else:  # str
                headers["If-Modified-Since"] = if_modified_since

        try:
            r = await self.session.get(STEAM_URL.MARKET / "itemordershistogram", params=params, headers=headers)
        except ClientResponseError as e:
            if e.status == 429:
                raise RateLimitExceeded("You have been rate limited, rest for a while!") from e
            else:
                raise e

        if r.status == 304:  # not modified if header "If-Modified-Since" is provided
            raise ResourceNotModified

        rj: ItemOrdersHistogramData = await r.json()
        success = EResult(rj.get("success"))
        if success is not EResult.OK:
            raise EResultError(rj.get("message", "Failed to fetch items order histogram"), success, rj)

        if raw:
            return rj

        # model parsing
        return ItemOrdersHistogram(
            sell_order_count=self._parse_item_order_histogram_count(rj["sell_order_count"]),
            sell_order_price=self._parse_item_order_histogram_price(rj["sell_order_price"]),
            sell_order_table=[
                SellOrderTableEntry(
                    self._parse_item_order_histogram_price(d["price"]),
                    self._parse_item_order_histogram_price(d["price_with_fee"]),
                    self._parse_item_order_histogram_count(d["quantity"]),
                )
                for d in rj["sell_order_table"]
            ],
            buy_order_count=self._parse_item_order_histogram_count(rj["buy_order_count"]),
            buy_order_price=self._parse_item_order_histogram_price(rj["buy_order_price"]),
            buy_order_table=[
                BuyOrderTableEntry(
                    self._parse_item_order_histogram_price(d["price"]),
                    self._parse_item_order_histogram_count(d["quantity"]),
                )
                for d in rj["buy_order_table"]
            ],
            highest_buy_order=int(rj["highest_buy_order"]),
            lowest_sell_order=int(rj["lowest_sell_order"]),
            buy_order_graph=[OrderGraphEntry(int(d[0] * 100), d[1], d[2]) for d in rj["buy_order_graph"]],
            sell_order_graph=[OrderGraphEntry(int(d[0] * 100), d[1], d[2]) for d in rj["sell_order_graph"]],
            graph_max_y=rj["graph_max_y"],
            graph_min_x=int(rj["graph_min_x"] * 100),
            graph_max_x=int(rj["graph_max_x"] * 100),
        )

    @staticmethod
    def _parse_item_order_histogram_count(text: str) -> int:
        if "." in text:
            count_raw = text.replace(".", "")
        elif "," in text:  # to be sure
            count_raw = text.replace(",", "")
        else:
            count_raw = text

        return int(count_raw)

    @staticmethod
    def _parse_item_order_histogram_price(text: str) -> int:
        raw_price = ITEM_ORDER_HIST_PRICE_RE.search(text).group(1)

        if "," in raw_price:  # 163,46₴
            price = raw_price.replace(",", "")
        elif "." in raw_price:  # £2.69
            price = raw_price.replace(".", "")
        else:
            price = int(raw_price) * 100  # add cents

        return int(price)

    @currency_required
    async def fetch_item_orders_activity(
        self,
        item_nameid: int,
        *,
        params: T_PARAMS = {},
        headers: T_HEADERS = {},
    ) -> ItemOrdersActivity:
        """
        Do what described in method name.

        .. seealso::
            * https://github.com/Revadike/InternalSteamWebAPI/wiki/Get-Market-Item-Orders-Activity
            * https://github.com/somespecialone/steam-item-name-ids

        :param item_nameid: special id of item class. Can be found only on listings page.
        :param params: extra params to pass to url
        :param headers: extra headers to send with request
        :return: `ItemOrdersActivity` dict
        :raises EResultError:
        """

        params = {
            "norender": 1,
            "language": self.language,
            "country": self.country,
            "currency": self.currency,
            "item_nameid": item_nameid,
            **params,
        }
        r = await self.session.get(STEAM_URL.MARKET / "itemordersactivity", params=params, headers=headers)
        # Can we hit a rate limit there?
        rj: ItemOrdersActivity = await r.json()
        success = EResult(rj.get("success"))
        if success is not EResult.OK:
            raise EResultError(rj.get("message", "Failed to fetch items order activity"), success, rj)

        return rj

    @overload
    async def fetch_price_overview(
        self,
        obj: ItemDescription,
        *,
        params: T_PARAMS = ...,
        headers: T_HEADERS = ...,
    ) -> PriceOverview:
        ...

    @overload
    async def fetch_price_overview(
        self,
        obj: str,
        app: App,
        *,
        params: T_PARAMS = ...,
        headers: T_HEADERS = ...,
    ) -> PriceOverview:
        ...

    @currency_required
    async def fetch_price_overview(
        self,
        obj: str | ItemDescription,
        app: App = None,
        *,
        params: T_PARAMS = {},
        headers: T_HEADERS = {},
    ) -> PriceOverview:
        """
        Fetch price data.

        .. note:: This request is rate limited by Steam.

        :param obj: `market hash name` ofr the `Steam` item or `ItemDescription`
        :param app:
        :param params: extra params to pass to url
        :param headers: extra headers to send with request
        :return: `PriceOverview` dict
        :raises EResultError:
        """

        if isinstance(obj, ItemDescription):
            name = obj.market_hash_name
            app = obj.app
        else:  # str
            name = obj

        params = {
            "country": self.country,
            "currency": self.currency,
            "market_hash_name": name,
            "appid": app.value,
            **params,
        }
        try:
            r = await self.session.get(STEAM_URL.MARKET / "priceoverview", params=params, headers=headers)
        except ClientResponseError as e:
            if e.status == 429:
                raise RateLimitExceeded("You have been rate limited, rest for a while!") from e
            else:
                raise e

        rj: PriceOverview = await r.json()
        success = EResult(rj.get("success"))
        if success is not EResult.OK:
            raise EResultError(rj.get("message", "Failed to fetch price overview"), success, rj)

        return rj

    @overload
    async def get_item_listings(
        self,
        obj: ItemDescription,
        *,
        query: str = ...,
        start: int = ...,
        count: int = ...,
        if_modified_since: datetime | str = ...,
        params: T_PARAMS = ...,
        headers: T_HEADERS = ...,
    ) -> T_MARKET_ITEM_LISTINGS_DATA:
        ...

    @overload
    async def get_item_listings(
        self,
        obj: str,
        app: App,
        *,
        query: str = ...,
        start: int = ...,
        count: int = ...,
        if_modified_since: datetime | str = ...,
        params: T_PARAMS = ...,
        headers: T_HEADERS = ...,
    ) -> T_MARKET_ITEM_LISTINGS_DATA:
        ...

    @currency_required
    async def get_item_listings(
        self,
        obj: str | ItemDescription,
        app: App = None,
        *,
        query: str = "",
        start: int = 0,
        count: int = LISTING_COUNT,
        if_modified_since: datetime | str = None,
        params: T_PARAMS = {},
        headers: T_HEADERS = {},
        _item_descriptions_map: T_SHARED_DESCRIPTIONS = None,
        _market_econ_items_map: dict[str, MarketListingItem] = None,
    ) -> T_MARKET_ITEM_LISTINGS_DATA:
        """
        Fetch item listings from market.

        .. note::
            * You can paginate by yourself passing `start` arg. or use `market_listings` method.
            * This request is rate limited by Steam. It is strongly recommended to use `if_modified_since`

        :param obj: `market hash name` ofr the `Steam` item or `ItemDescription`
        :param app:
        :param count: page size
        :param start: offset position
        :param query: raw search query
        :param if_modified_since: `If-Modified-Since` header value
        :param params: extra params to pass to url
        :param headers: extra headers to send with request
        :return: list of `MarketListing`, total listings count, datetime object when resource was last modified
        :raises EResultError: for ordinary reasons
        :raises RateLimitExceeded: when you hit rate limit
        :raises ResourceNotModified: when `if_modified_since` header passed and Steam response with 304 status code
        """

        if isinstance(obj, ItemDescription):
            name = obj.market_hash_name
            app = obj.app
        else:  # str
            name = obj

        base_url = STEAM_URL.MARKET / f"listings/{app.value}/{name}"
        params = {
            "filter": query,
            "country": self.country,
            "currency": self.currency,
            "start": start,
            "count": count,
            "language": self.language,
            **params,
        }
        headers = {"Referer": str(base_url), **headers}
        if if_modified_since:
            if isinstance(if_modified_since, datetime):
                headers["If-Modified-Since"] = format_time(if_modified_since)
            else:  # str
                headers["If-Modified-Since"] = if_modified_since

        try:
            r = await self.session.get(base_url / "render/", params=params, headers=headers)
        except ClientResponseError as e:
            if e.status == 429:
                raise RateLimitExceeded("You have been rate limited, rest for a while!") from e
            else:
                raise e

        if r.status == 304:  # not modified if header "If-Modified-Since" is provided
            raise ResourceNotModified

        last_modified = parse_time(r.headers["Last-Modified"])

        rj: dict[str, int | dict[str, dict]] = await r.json()
        success = EResult(rj.get("success"))
        if success is not EResult.OK:
            raise EResultError(rj.get("message", "Failed to fetch item listings"), success, rj)
        elif not rj["total_count"] or not rj["assets"]:
            return [], 0, last_modified

        if _item_descriptions_map is None:
            _item_descriptions_map = {}
        if _market_econ_items_map is None:
            _market_econ_items_map = {}

        self._parse_descriptions_from_market_assets(rj["assets"], _item_descriptions_map)
        # Do we need to share items?
        self._parse_market_listing_items(rj["assets"], _item_descriptions_map, _market_econ_items_map)

        return (
            [
                MarketListing(
                    id=int(l_data["listingid"]),
                    item=_market_econ_items_map[
                        create_ident_code(
                            l_data["asset"]["id"],
                            l_data["asset"]["contextid"],
                            l_data["asset"]["appid"],
                        )
                    ],
                    currency=Currency(int(l_data["currencyid"]) - 2000),
                    price=int(l_data["price"]),
                    fee=int(l_data["fee"]),
                    converted_currency=Currency(int(l_data["converted_currencyid"]) - 2000),
                    converted_fee=int(l_data["converted_fee"]),
                    converted_price=int(l_data["converted_price"]),
                )
                for l_data in rj["listinginfo"].values()
                # due to "0", ignore items with no amount and prices (supposedly purchased)
                if int(l_data["asset"]["amount"])
            ],
            rj["total_count"],
            last_modified,
        )

    @classmethod
    def _parse_descriptions_from_market_assets(
        cls,
        assets: dict[str, dict[str, dict[str, dict]]],
        item_descriptions_map: dict[str, ItemDescription],
    ):
        for app_id, app_data in assets.items():
            for context_id, context_data in app_data.items():
                for asset_id, mixed_data in context_data.items():  # asset+descr data
                    key = create_ident_code(mixed_data["instanceid"], mixed_data["classid"], app_id)
                    item_descriptions_map[key] = cls._create_item_descr(mixed_data)

    @staticmethod
    def _parse_market_listing_items(
        data: dict[str, dict[str, dict[str, dict]]],
        item_descriptions_map: dict[str, ItemDescription],
        items_map: dict[str, MarketListingItem],
    ):
        for app_id, app_data in data.items():
            for context_id, context_data in app_data.items():
                for a_data in context_data.values():
                    key = create_ident_code(a_data["id"], context_id, app_id)
                    if key not in items_map:
                        items_map[key] = MarketListingItem(
                            asset_id=int(a_data["id"]),
                            market_id=0,  # set in market listing post init
                            unowned_id=int(a_data["unowned_id"]),
                            unowned_context_id=int(a_data["unowned_contextid"]),
                            app_context=AppContext((App(int(a_data["appid"])), int(a_data["contextid"]))),
                            description=item_descriptions_map[
                                create_ident_code(
                                    a_data["instanceid"],
                                    a_data["classid"],
                                    app_id,
                                )
                            ],
                        )

    # without async for proper type hinting in VsCode and PyCharm at least with `async for`
    @overload
    def market_listings(
        self,
        obj: ItemDescription,
        *,
        query: str = ...,
        start: int = ...,
        count: int = ...,
        if_modified_since: datetime | str = ...,
        params: T_PARAMS = ...,
        headers: T_HEADERS = ...,
    ) -> AsyncIterator[T_MARKET_ITEM_LISTINGS_DATA]:
        ...

    @overload
    def market_listings(
        self,
        obj: str,
        app: App,
        *,
        query: str = ...,
        start: int = ...,
        count: int = ...,
        if_modified_since: datetime | str = ...,
        params: T_PARAMS = ...,
        headers: T_HEADERS = ...,
    ) -> AsyncIterator[T_MARKET_ITEM_LISTINGS_DATA]:
        ...

    async def market_listings(
        self,
        obj: str | ItemDescription,
        app: App = None,
        *,
        query: str = "",
        start: int = 0,
        count: int = LISTING_COUNT,
        if_modified_since: datetime | str = None,
        params: T_PARAMS = {},
        headers: T_HEADERS = {},
        _item_descriptions_map: T_SHARED_DESCRIPTIONS = None,
        _market_econ_items_map: dict[str, MarketListingItem] = None,
    ) -> AsyncIterator[T_MARKET_ITEM_LISTINGS_DATA]:
        """
        Fetch item listings from market. Return async iterator to paginate over listings pages.

        .. note:: This request is rate limited by Steam. It is strongly recommended to use `if_modified_since`

        :param obj: `market hash name` ofr the `Steam` item or `ItemDescription`
        :param app:
        :param count: page size
        :param start: offset position
        :param query: raw search query
        :param if_modified_since: `If-Modified-Since` header value
        :param params: extra params to pass to url
        :param headers: extra headers to send with request
        :return: `AsyncIterator` that yields list of `MarketListing`, total listings count, datetime object when resource was last modified
        :raises EResultError: for ordinary reasons
        :raises RateLimitExceeded: when you hit rate limit
        """

        if _item_descriptions_map is None:
            _item_descriptions_map = {}
        if _market_econ_items_map is None:
            _market_econ_items_map = {}

        total_count: int = 10e6  # simplify logic for initial iteration
        while total_count > start:
            # browser loads first batch from document request and not json api point, but anyway
            # avoid excess destructuring
            listings_data = await self.get_item_listings(
                obj,
                app,
                query=query,
                count=count,
                if_modified_since=if_modified_since,
                params=params,
                headers=headers,
                _item_descriptions_map=_item_descriptions_map,
                _market_econ_items_map=_market_econ_items_map,
                start=start,
            )
            total_count = listings_data[1]
            start += count

            yield listings_data

    @overload
    async def get_item_name_id(self, obj: ItemDescription, *, headers: T_HEADERS = ...) -> int:
        ...

    @overload
    async def get_item_name_id(self, obj: str, app: App, *, headers: T_HEADERS = ...) -> int:
        ...

    async def get_item_name_id(self, obj: str | ItemDescription, app: App = None, *, headers: T_HEADERS = {}) -> int:
        """
        Fetch item from `Steam Community Market` page, find and return `item_nameid`

        :param obj: `market hash name` ofr the `Steam` item or `ItemDescription`
        :param app:
        :param headers: extra headers to send with request
        :return: `item_nameid`

        .. seealso:: https://github.com/somespecialone/steam-item-name-ids
        """

        if isinstance(obj, ItemDescription):
            url = obj.market_url
        else:  # str
            url = STEAM_URL.MARKET / f"listings/{app.value}/{obj}"

        res = await self.session.get(url, headers=headers)
        text = await res.text()

        return find_item_nameid_in_text(text)

    # TODO market search method, pagination, auto-crawler in github runner for item-name-ids
