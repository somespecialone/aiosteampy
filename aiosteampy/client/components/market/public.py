import re
from collections.abc import AsyncGenerator, Mapping, Sequence
from datetime import datetime
from typing import Literal, overload

from ....constants import SteamURL
from ....exceptions import EResultError
from ....transport import BaseSteamTransport, format_http_date, parse_http_date
from ....webapi.client import COMMUNITY_ORIGIN
from ...app import ADD_NEW_MEMBERS, App
from ...constants import Currency
from ...econ import EconMixin, ItemDescription, ItemDescriptionsMap, create_ident_code
from ...state import PublicSteamState
from .models import (
    ActivityEntry,
    ActivityType,
    BuyOrderTableEntry,
    ItemOrdersActivity,
    ItemOrdersHistogram,
    ListingValues,
    MarketListing,
    MarketListingItem,
    MarketListings,
    MarketSearchItem,
    MarketSearchResult,
    MarketSearchSuggestion,
    NewlyListedItems,
    OrderGraphEntry,
    PriceOverview,
    PurchaseInfo,
    PurchaseInfoValues,
    SellOrderTableEntry,
)
from .utils import extract_icon_hash_from_app_icon_link

ITEM_ORDER_HIST_PRICE_RE = re.compile(r"[^\d\s]*([\d,]+(?:\.\d+)?)[^\d\s]*")  # Author: ChatGPT
ITEM_NAME_ID_RE = re.compile(r"Market_LoadOrderSpread\(\s?(\d+)\s?\)")

# Steam current limit
LISTING_COUNT = 10
SEARCH_COUNT = 10

SortColumn = Literal["price", "name", "quantity", "popular", "default"]
SortDir = Literal["asc", "desc"]

MARKET_URL = SteamURL.COMMUNITY / "market/"
SEARCH_URL = MARKET_URL / "search"
SEARCH_RENDER_URL = SEARCH_URL / "render/"


CUSTOM_API_HEADERS = {"X-Prototype-Version": "1.7", "X-Requested-With": "XMLHttpRequest"}


class MarketPublicComponent(EconMixin):
    """Component with public `Steam Market` methods. Available without authentication."""

    __slots__ = ("_transport", "_state")

    def __init__(self, transport: BaseSteamTransport, state: PublicSteamState):
        self._transport = transport

        self._state = state

    @staticmethod
    def _parse_quantity(text: str | int) -> int:
        if type(text) is int:
            return text
        elif "." in text:
            count_raw = text.replace(".", "")
        elif "," in text:  # to be sure
            count_raw = text.replace(",", "")
        else:
            count_raw = text

        return int(count_raw)

    @staticmethod
    def _parse_price_with_currency(text: str | None) -> int | None:
        if text is None:  # to make caller code cleaner
            return None

        raw_price = ITEM_ORDER_HIST_PRICE_RE.search(text.replace(" ", "")).group(1)

        if "." not in raw_price and "," not in raw_price:
            price = int(raw_price) * 100  # add cents
        else:  # 163,46₴ £2.69 $1,000.00
            price = raw_price.replace(",", "").replace(".", "")

        return int(price)

    @staticmethod
    def _prepare_if_modified_since(headers: dict[str, str], if_modified_since: datetime | str | None):
        if if_modified_since is not None:
            if isinstance(if_modified_since, datetime):
                headers["If-Modified-Since"] = format_http_date(if_modified_since)
            else:  # str
                headers["If-Modified-Since"] = if_modified_since

    async def get_orders_histogram(
        self,
        item_name_id: int,
        *,
        if_modified_since: datetime | str | None = None,
    ) -> ItemOrdersHistogram:
        """
        Get item orders histogram from `Steam Market`..

        .. seealso::
            * https://github.com/Revadike/InternalSteamWebAPI/wiki/Get-Market-Item-Orders-Histogram.
            * https://github.com/somespecialone/steam-item-name-ids - open source list of known item name ids.

        .. note:: This request is rate limited by `Steam`. It is **strongly advised** to use ``if_modified_since``.

        :param item_name_id: special id of item class. Can be found only on listings page.
        :param if_modified_since: `If-Modified-Since` header value.
        :return: ``ItemOrdersHistogram`` model, datetime object when resource was last modified.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        :raises TooManyRequests: rate limit has been hit.
        :raises ResourceNotModified: 304 status code.
        """

        params = {
            "norender": 1,
            "language": self._state.language,
            "currency": self._state.currency,
            "item_nameid": item_name_id,
        }
        headers = {}
        self._prepare_if_modified_since(headers, if_modified_since)

        r = await self._transport.request(
            "GET",
            MARKET_URL / "itemordershistogram",
            params=params,
            headers=headers,
            response_mode="json",
        )
        rj: dict = r.content

        EResultError.check_data(rj)

        return ItemOrdersHistogram(
            sell_order_count=self._parse_quantity(rj["sell_order_count"]),
            sell_order_price=self._parse_price_with_currency(rj["sell_order_price"]),
            sell_order_table=tuple(
                SellOrderTableEntry(
                    self._parse_price_with_currency(d["price"]),
                    self._parse_price_with_currency(d["price_with_fee"]),
                    self._parse_quantity(d["quantity"]),
                )
                for d in rj["sell_order_table"] or ()
            ),
            buy_order_count=self._parse_quantity(rj["buy_order_count"]),
            buy_order_price=self._parse_price_with_currency(rj["buy_order_price"]),
            buy_order_table=tuple(
                BuyOrderTableEntry(
                    self._parse_price_with_currency(d["price"]),
                    self._parse_quantity(d["quantity"]),
                )
                for d in rj["buy_order_table"] or ()
            ),
            highest_buy_order=int(rj["highest_buy_order"]) if rj["highest_buy_order"] is not None else None,
            lowest_sell_order=int(rj["lowest_sell_order"]) if rj["lowest_sell_order"] is not None else None,
            buy_order_graph=tuple(OrderGraphEntry(int(d[0] * 100), d[1], d[2]) for d in rj["buy_order_graph"]),
            sell_order_graph=tuple(OrderGraphEntry(int(d[0] * 100), d[1], d[2]) for d in rj["sell_order_graph"]),
            graph_max_y=rj["graph_max_y"],
            graph_min_x=int(rj["graph_min_x"] * 100),
            graph_max_x=int(rj["graph_max_x"] * 100),
            last_modified=parse_http_date(r.headers["Last-Modified"]),
        )

    async def get_orders_activity(
        self,
        item_name_id: int,
        *,
        if_modified_since: datetime | str | None = None,
    ) -> ItemOrdersActivity:
        """
        Get orders activity of particular item.

        .. seealso::
            * https://github.com/Revadike/InternalSteamWebAPI/wiki/Get-Market-Item-Orders-Activity.
            * https://github.com/somespecialone/steam-item-name-ids - open source list of known item name ids.

        .. note:: This request is rate limited by `Steam`. It is **strongly advised** to use ``if_modified_since``.

        :param item_name_id: special id of item class. Can be found only on listings page.
        :param if_modified_since: `If-Modified-Since` header value.
        :return: ``ItemOrdersActivity`` model, datetime object when resource was last modified.
        :raises TransportError: ordinary reasons.
        :raises EResultError: ordinary reasons.
        :raises ResourceNotModified: 304 status code.
        """

        params = {
            "norender": 1,
            "language": self._state.language,
            "country": self._state.country,
            "currency": self._state.currency,
            "item_nameid": item_name_id,
        }
        headers = {}
        self._prepare_if_modified_since(headers, if_modified_since)

        # Can we hit a rate limit there?
        r = await self._transport.request(
            "GET",
            MARKET_URL / "itemordersactivity",
            params=params,
            headers=headers,
            response_mode="json",
        )
        rj: dict = r.content

        EResultError.check_data(rj)

        return ItemOrdersActivity(
            activity=tuple(
                ActivityEntry(
                    type=ActivityType(a["type"]),
                    quantity=self._parse_quantity(a["quantity"]),
                    price=self._parse_price_with_currency(a["price"]),
                    time=datetime.fromtimestamp(a["time"]),
                    avatar_buyer=a.get("avatar_buyer"),
                    avatar_medium_buyer=a.get("avatar_medium_buyer"),
                    persona_buyer=a.get("persona_buyer"),
                    avatar_seller=a.get("avatar_seller"),
                    avatar_medium_seller=a.get("avatar_medium_seller"),
                    persona_seller=a.get("persona_seller"),
                )
                for a in rj["activity"]
            ),
            time=datetime.fromtimestamp(rj["timestamp"]),
            last_modified=parse_http_date(r.headers["Last-Modified"]),
        )

    @overload
    async def get_price_overview(
        self,
        obj: ItemDescription,
        *,
        if_modified_since: datetime | str | None = ...,
    ) -> PriceOverview: ...

    @overload
    async def get_price_overview(
        self,
        obj: str,
        app: App,
        *,
        if_modified_since: datetime | str | None = ...,
    ) -> PriceOverview: ...

    async def get_price_overview(
        self,
        obj: str | ItemDescription,
        app: App | None = None,
        *,
        if_modified_since: datetime | str | None = None,
    ) -> PriceOverview:
        """
        Get price data of particular item.

        .. note:: This request is rate limited by `Steam`. It is **strongly advised** to use ``if_modified_since``.

        :param obj: `market hash name` of the item or ``ItemDescription``.
        :param app: `Steam` app.
        :param if_modified_since: `If-Modified-Since` header value.
        :return: ``PriceOverview`` model, datetime object when resource was last modified.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        :raises ResourceNotModified: 304 status code.
        """

        if isinstance(obj, ItemDescription):
            name = obj.market_hash_name
            app = obj.app
        else:  # str
            name = obj

        params = {
            "country": self._state.country,
            "currency": self._state.currency,
            "market_hash_name": name,
            "appid": app.id,
        }
        # referer header is profile alias / inventory, good that it is not mandatory
        headers = {}
        self._prepare_if_modified_since(headers, if_modified_since)

        r = await self._transport.request(
            "GET",
            MARKET_URL / "priceoverview",
            params=params,
            headers=headers,
            response_mode="json",
        )
        rj: dict = r.content

        EResultError.check_data(rj)

        return PriceOverview(
            lowest_price=self._parse_price_with_currency(rj["lowest_price"]),
            volume=self._parse_quantity(rj["volume"]),
            median_price=self._parse_price_with_currency(rj["lowest_price"]),
            last_modified=parse_http_date(r.headers["Last-Modified"]),
        )

    @staticmethod
    def _parse_apps_from_app_data(data: dict[str, dict[str, int | str]]):
        """Extract `apps` from data and create if they are not present in ``App.__members__``."""
        if ADD_NEW_MEMBERS:  # if caching is disabled then we do not need to do work
            for _, app_data in data.items():
                if not App.get(app_data["appid"]):
                    App(
                        app_data["appid"],
                        app_data["name"],
                        extract_icon_hash_from_app_icon_link(app_data["icon"]),
                    )

    @staticmethod
    def _get_market_item_from_map_by_ident_code(
        data: dict,
        items_map: dict[str, MarketListingItem],
    ) -> MarketListingItem:
        return items_map[
            create_ident_code(
                data["asset"]["id"],
                data["asset"]["contextid"],
                data["asset"]["appid"],
            )
        ]

    @classmethod
    def _create_market_listings(cls, data: dict, items_map: dict[str, MarketListingItem]) -> list[MarketListing]:
        # casting to integers just to make sure that Steam didn't give us a surprise
        return [
            MarketListing(
                id=int(l_data["listingid"]),
                item=cls._get_market_item_from_map_by_ident_code(l_data, items_map),
                original=ListingValues(
                    currency=Currency(int(l_data["currencyid"]) - 2000),
                    price=int(l_data["price"]),
                    fee=int(l_data["fee"]),
                    steam_fee=int(l_data.get("steam_fee", 0)),
                    publisher_fee=int(l_data.get("publisher_fee", 0)),
                ),
                converted=ListingValues(
                    currency=Currency(int(l_data["converted_currencyid"]) - 2000),
                    price=int(l_data.get("converted_price", 0)),
                    fee=int(l_data.get("converted_fee", 0)),
                    steam_fee=int(l_data.get("converted_steam_fee", 0)),
                    publisher_fee=int(l_data.get("converted_publisher_fee", 0)),
                )
                if "converted_currencyid" in l_data
                else None,
            )
            for l_data in data["listinginfo"].values()
        ]

    @classmethod
    def _parse_descriptions_from_market_assets(
        cls,
        assets: dict[str, dict[str, dict[str, dict]]],
        item_descriptions_map: ItemDescriptionsMap,
    ):
        """Extract item descriptions from market assets data to ``item_descriptions_map`` dict."""

        for app_id, app_data in assets.items():
            for context_id, context_data in app_data.items():
                for asset_id, mixed_data in context_data.items():  # asset+descr data
                    key = create_ident_code(mixed_data["instanceid"], mixed_data["classid"], app_id)
                    if key not in item_descriptions_map:
                        item_descriptions_map[key] = cls._create_item_descr(mixed_data)

    @classmethod
    def _parse_market_listing_items(
        cls,
        data: dict[str, dict[str, dict[str, dict]]],
        item_descriptions_map: ItemDescriptionsMap,
        items_map: dict[str, MarketListingItem],
    ):
        """Extract ``MarketListingItem`` from market assets data to ``items_map`` dict."""

        for app_id, app_data in data.items():
            for context_id, context_data in app_data.items():
                for a_data in context_data.values():
                    key = create_ident_code(a_data["id"], context_id, app_id)
                    if key not in items_map:
                        descr_key = create_ident_code(a_data["instanceid"], a_data["classid"], app_id)
                        items_map[key] = MarketListingItem(
                            context_id=int(context_id),
                            asset_id=int(a_data["id"]),
                            market_id=0,  # will be set in MarketListing.__post_init__
                            unowned_id=int(a_data["unowned_id"]),
                            unowned_context_id=int(a_data["unowned_contextid"]),
                            description=item_descriptions_map[descr_key],
                            properties=cls._parse_asset_properties(a_data),
                        )

    @overload
    async def get_listings(
        self,
        obj: ItemDescription,
        *,
        query: str = ...,
        start: int = ...,
        count: int = ...,
        if_modified_since: datetime | str | None = ...,
    ) -> MarketListings: ...

    @overload
    async def get_listings(
        self,
        obj: str,
        app: App,
        *,
        query: str = ...,
        start: int = ...,
        count: int = ...,
        if_modified_since: datetime | str | None = ...,
    ) -> MarketListings: ...

    async def get_listings(
        self,
        obj: str | ItemDescription,
        app: App | None = None,
        *,
        query: str = "",
        start: int = 0,
        count: int = LISTING_COUNT,
        if_modified_since: datetime | str | None = None,
        # share mapping with iterator method
        _item_descriptions_map: ItemDescriptionsMap | None = None,
        _market_econ_items_map: dict[str, MarketListingItem] | None = None,
    ) -> MarketListings:
        """
        Get item listings from `Steam Market`.

        .. note::
            * Pagination can be achieved by passing ``start`` arg.
            * This request is rate limited by `Steam`. It is **strongly advised** to use ``if_modified_since``.

        :param obj: `market hash name` of item or ``ItemDescription``.
        :param app: `Steam` app.
        :param count: page size.
        :param start: offset position.
        :param query: raw search query.
        :param if_modified_since: `If-Modified-Since` header value.
        :return: list of ``MarketListing`` as response page, total listings count,
            datetime object when resource was last modified.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        :raises TooManyRequests: rate limit has been hit.
        :raises ResourceNotModified: 304 status code.
        """

        if isinstance(obj, ItemDescription):
            if obj.commodity:
                raise ValueError("Commodity items does not have listings on Steam Market")

            name = obj.market_hash_name
            app = obj.app
        else:  # str
            name = obj

        base_url = MARKET_URL / f"listings/{app.id}/{name}"
        params = {
            "filter": query,
            "query": "",  # as web browser
            "country": self._state.country,
            "currency": self._state.currency,
            "start": start,
            "count": count,
            "language": self._state.language,
        }
        headers = {"Referer": str(base_url), **CUSTOM_API_HEADERS}
        self._prepare_if_modified_since(headers, if_modified_since)

        r = await self._transport.request(
            "GET",
            base_url / "render/",
            params=params,
            headers=headers,
            response_mode="json",
        )
        rj: dict = r.content

        EResultError.check_data(rj)

        last_modified = parse_http_date(r.headers["Last-Modified"])

        if not rj["total_count"] or not rj["assets"]:
            return MarketListings(listings=[], total=0, last_modified=last_modified)

        _item_descriptions_map = {} if _item_descriptions_map is None else _item_descriptions_map
        _market_econ_items_map = {} if _market_econ_items_map is None else _market_econ_items_map

        self._parse_descriptions_from_market_assets(rj["assets"], _item_descriptions_map)
        # Do we need to share items?
        self._parse_market_listing_items(rj["assets"], _item_descriptions_map, _market_econ_items_map)

        return MarketListings(
            listings=self._create_market_listings(rj, _market_econ_items_map),
            total=rj["total_count"],
            last_modified=last_modified,
        )

    # without "async" for proper type hinting in VsCode and PyCharm
    @overload
    def listings(
        self,
        obj: ItemDescription,
        *,
        query: str = ...,
        start: int = ...,
        count: int = ...,
        if_modified_since: datetime | str | None = ...,
    ) -> AsyncGenerator[MarketListings, None]: ...

    @overload
    def listings(
        self,
        obj: str,
        app: App,
        *,
        query: str = ...,
        start: int = ...,
        count: int = ...,
        if_modified_since: datetime | str | None = ...,
    ) -> AsyncGenerator[MarketListings, None]: ...

    async def listings(
        self,
        obj: str | ItemDescription,
        app: App | None = None,
        *,
        query: str = "",
        start: int = 0,
        count: int = LISTING_COUNT,
        if_modified_since: datetime | str | None = None,
    ) -> AsyncGenerator[list[MarketListing], None]:
        """
        Get iterator of item listings from `Steam Market`.

        .. note:: This request is rate limited by `Steam`. It is **strongly advised** to use ``if_modified_since``.

        :param obj: `market hash name` of item or ``ItemDescription``.
        :param app: `Steam` app.
        :param count: page size.
        :param start: offset position.
        :param query: raw search query.
        :param if_modified_since: `If-Modified-Since` header value.
        :return: ``AsyncGenerator`` that yields list of ``MarketListing``.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        :raises TooManyRequests: rate limit has been hit.
        :raises ResourceNotModified: 304 status code.
        """

        _item_descriptions_map: ItemDescriptionsMap = {}
        _market_econ_items_map: dict[str, MarketListingItem] = {}

        total_count: int = 10000000  # simplify logic for initial iteration
        while total_count > start:
            # browser loads first batch from document request and not json api point, but anyway
            listings = await self.get_listings(  # avoid excess destructuring
                obj,
                app,
                query=query,
                count=count,
                if_modified_since=if_modified_since,
                _item_descriptions_map=_item_descriptions_map,
                _market_econ_items_map=_market_econ_items_map,
                start=start,
            )
            total_count = listings.total
            start += count

            yield listings.listings

    @overload
    async def get_item_name_id(self, obj: ItemDescription) -> int: ...

    @overload
    async def get_item_name_id(self, obj: str, app: App) -> int: ...

    async def get_item_name_id(self, obj: str | ItemDescription, app: App | None = None) -> int:
        """
        Get `item name id`, a special market of *item class*.

        .. seealso:: https://github.com/somespecialone/steam-item-name-ids.

        :param obj: `market hash name` of item or ``ItemDescription``.
        :param app: `Steam` app.
        :return: `item name id`.
        :raises TooManyRequests: rate limit has been hit.
        :raises ValueError: failed to find `item name id` on page.
        :raises TransportError: ordinary reasons.
        """

        if isinstance(obj, ItemDescription):
            url = obj.market_url
        else:  # str and app
            url = MARKET_URL / f"listings/{app.id}/{obj}"

        r = await self._transport.request(
            "GET",
            url,
            headers={"Referer": COMMUNITY_ORIGIN},
            response_mode="text",
        )

        search = ITEM_NAME_ID_RE.search(r.content)  # lang safe
        res = int(search.group(1)) if search is not None else search
        if not res:
            raise ValueError(f"Failed to find item name id")

        return res

    # TODO models, FilterSequence constructor or something
    async def get_search_app_filters(self, app: App) -> dict[str, ...]:
        """
        Get `Steam App` filter facets for `Steam Market` search.

        .. note::
            Filter facets structure can be seen when clicking on **"Show advanced options..."**
            button under search input field on `Steam` market page.
        """

        r = await self._transport.request(
            "GET",
            MARKET_URL / f"appfilters/{app.id}",
            headers={"Referer": str(SEARCH_URL % {"appid": str(app.id)})},
            response_mode="json",
        )
        rj: dict[str, dict | int] = r.content

        EResultError.check_data(rj)

        return rj["facets"]

    async def get_search_app_accessories(self, app: App) -> dict[str, ...]:
        """
        Get `Steam App` accessory filter facets for `Steam Market` search.

        .. note::
            Filter facets structure can be seen when clicking on **"Show advanced options..."**
            button under search input field on `Steam` market page.
        """

        r = await self._transport.request(
            "GET",
            MARKET_URL / f"appaccessories/{app.id}",
            headers={"Referer": str(SEARCH_URL % {"appid": str(app.id)})},
            response_mode="json",
        )
        rj: dict[str, dict | int] = r.content

        EResultError.check_data(rj)

        return rj["facets"]

    # TODO check new search
    async def search(
        self,
        query="",
        app: App | None = None,
        *,
        start: int = 0,
        count: int = SEARCH_COUNT,
        descriptions: bool = False,
        sort_column: SortColumn = "default",
        sort_dir: SortDir = "desc",
        filters: str | Mapping[str, str | Sequence[str]] = "",
        # share mapping with iterator method
        _item_descriptions_map: ItemDescriptionsMap | None = None,
    ) -> MarketSearchResult:
        """
        Get search results from `Steam Market`.

        .. note::
            Filters structure alongside examples can be found by investigating how browser sends requests to a
            https://steamcommunity.com/market/search/render/ endpoint with enabled at least one option from
            `advanced options` window.

            Example for `CS2`, with `Collection` as `The Anubis Collection` will look like:
                * `get_market_search_results(app=App.CS2, filters={"category_730_ItemSet[]": "tag_set_anubis"})`.

        .. note:: This request is rate limited by `Steam`.

        :param query: raw search query.
        :param app: `Steam` app.
        :param start: start result position.
        :param count: total count of results on page.
        :param descriptions: search in descriptions.
        :param sort_column: column to sort by.
        :param sort_dir: direction to sort by.
        :param filters: app search filters.
        :return: list of ``MarketSearchItem``, total results count.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        :raises TooManyRequests: rate limit has been hit.
        """

        req_params = {
            "norender": 1,
            "query": query,  # empty, like in browser's request
            "start": start,
            "count": count,
            "sort_column": sort_column,
            "sort_dir": sort_dir,
            "search_descriptions": int(descriptions),
        }

        referer_params = {
            "q": query,
            "sort_column": sort_column,
            "sort_dir": sort_dir,
        }

        if app is not None:
            req_params["appid"] = referer_params["appid"] = str(app.id)
        if descriptions:
            referer_params["descriptions"] = "1"

        r = await self._transport.request(
            "GET",
            SEARCH_RENDER_URL % req_params % filters,
            headers={"Referer": str(SEARCH_URL % referer_params % filters)},
            response_mode="json",
        )
        rj: dict[str, int | list[dict[str, str | int | dict[str, str | int]]]] = r.content

        EResultError.check_data(rj)

        if not rj["total_count"] or not rj["results"]:
            return MarketSearchResult([], 0)

        _item_descriptions_map = {} if _item_descriptions_map is None else _item_descriptions_map

        items = []
        for item_data in rj["results"]:
            descr_ident_code = create_ident_code(
                item_data["asset_description"]["instanceid"],
                item_data["asset_description"]["classid"],
                item_data["asset_description"]["appid"],
            )

            if descr_ident_code in _item_descriptions_map:
                description = _item_descriptions_map[descr_ident_code]
            else:
                if ADD_NEW_MEMBERS and App.get(int(item_data["asset_description"]["appid"])) is None:
                    App(
                        int(item_data["asset_description"]["appid"]),
                        item_data["app_name"],
                        extract_icon_hash_from_app_icon_link(item_data["app_icon"]),
                    )  # will cache app

                description = self._create_item_descr(item_data["asset_description"])
                _item_descriptions_map[descr_ident_code] = description

            item = MarketSearchItem(
                sell_listings=item_data["sell_listings"],
                sell_price=item_data["sell_price"],
                sell_price_text=item_data["sell_price_text"],
                sale_price_text=item_data["sale_price_text"],
                description=description,
            )
            items.append(item)

        return MarketSearchResult(items, rj["total_count"])

    async def search_results(
        self,
        query: str = "",
        app: App | None = None,
        *,
        start: int = 0,
        count: int = SEARCH_COUNT,
        descriptions: bool = False,
        sort_column: SortColumn = "default",
        sort_dir: SortDir = "desc",
        filters: str | Mapping[str, str | Sequence[str]] = "",
    ) -> AsyncGenerator[list[MarketSearchItem], None]:
        """
        Get search results from `Steam Market`.
        Return async iterator to paginate over market search result pages.

        .. note::
            Filters structure alongside examples can be found by investigating how browser sends requests to a
            https://steamcommunity.com/market/search/render/ endpoint with enabled at least one option from
            `advanced options` window.

            Example for `CS2`, with `Collection` as `The Anubis Collection` will look like:
                * `get_market_search_results(app=App.CS2, filters={"category_730_ItemSet[]": "tag_set_anubis"})`.

        .. note:: This request is rate limited by `Steam`.

        :param query: raw search query.
        :param app: `Steam` app.
        :param start: start result position.
        :param count: total count of results on page.
        :param descriptions: search in descriptions.
        :param sort_column: column to sort by.
        :param sort_dir: direction to sort by.
        :param filters: app search filters.
        :return: ``AsyncGenerator`` that yields list of ``MarketSearchItem``, total results count.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        :raises TooManyRequests: rate limit has been hit.
        """

        _item_descriptions_map = {}

        total_count: int = 10000000  # simplify logic for initial iteration
        while total_count > start:
            # browser loads first batch from document request and not json api point, but anyway
            search_results = await self.search(
                query,
                app,
                count=count,
                descriptions=descriptions,
                sort_column=sort_column,
                sort_dir=sort_dir,
                _item_descriptions_map=_item_descriptions_map,
                start=start,
                filters=filters,
            )
            total_count = search_results.total
            start += count

            yield search_results.items

    async def get_newly_listed(self, *, if_modified_since: datetime | str | None = None) -> NewlyListedItems:
        """
        Get *newly listed items* from `Steam Market`.
        Can be seen on main market page.

        .. note:: It is **strongly advised** to use ``if_modified_since``.

        :param if_modified_since: `If-Modified-Since` header value.
        :return: list of ``MarketListing`` and datetime object when resource was last modified.
        """

        params = {
            "country": self._state.country,
            "language": self._state.language,
            "currency": self._state.currency,
        }
        headers = {"Referer": str(MARKET_URL), **CUSTOM_API_HEADERS}
        self._prepare_if_modified_since(headers, if_modified_since)

        r = await self._transport.request(
            "GET",
            MARKET_URL / "recent",
            params=params,
            headers=headers,
            response_mode="json",
        )
        rj: dict = r.content

        EResultError.check_data(rj)

        _item_descriptions_map = {}
        _market_econ_items_map = {}

        self._parse_apps_from_app_data(rj["app_data"])
        self._parse_descriptions_from_market_assets(rj["assets"], _item_descriptions_map)
        self._parse_market_listing_items(rj["assets"], _item_descriptions_map, _market_econ_items_map)

        # unknow fields: last_time, last_listing

        return NewlyListedItems(
            listings=self._create_market_listings(rj, _market_econ_items_map),
            last_modified=parse_http_date(r.headers["Last-Modified"]),
        )

    @classmethod
    def _create_purchase_infos(
        cls,
        data: dict[str, dict[str, dict]],
        items_map: dict[str, MarketListingItem],
    ) -> list[PurchaseInfo]:
        return [
            PurchaseInfo(
                id=int(p_data["purchaseid"]),
                listing_id=int(p_data["listingid"]),
                # get assets from mapped listings due to missing?? assets in purchase data
                item=cls._get_market_item_from_map_by_ident_code(data["listinginfo"][p_data["listingid"]], items_map),
                original=PurchaseInfoValues(
                    currency=Currency(int(p_data["currencyid"]) - 2000),
                    paid_amount=int(p_data["paid_amount"]),
                    paid_fee=int(p_data["paid_fee"]),
                    steam_fee=int(p_data["steam_fee"]),
                    publisher_fee=int(p_data["publisher_fee"]),
                ),
                converted=PurchaseInfoValues(
                    currency=Currency(int(p_data["converted_currencyid"]) - 2000),
                    paid_amount=int(p_data["paid_amount"]),
                    paid_fee=int(p_data["paid_fee"]),
                    steam_fee=int(p_data["converted_steam_fee"]),
                    publisher_fee=int(p_data["converted_publisher_fee"]),
                ),
            )
            for p_data in data["purchaseinfo"].values()
        ]

    async def get_recently_sold(self) -> list[PurchaseInfo]:
        """Get *recently sold items* from `Steam Market`. Can be seen on main market page."""

        params = {
            "country": self._state.country,
            "language": self._state.language,
            "currency": self._state.currency,
        }

        r = await self._transport.request(
            "GET",
            MARKET_URL / "recentcompleted",
            params=params,
            headers={"Referer": str(MARKET_URL), **CUSTOM_API_HEADERS},
            response_mode="json",
        )
        rj: dict = r.content

        EResultError.check_data(rj)

        _item_descriptions_map: ItemDescriptionsMap = {}
        _market_econ_items_map: dict[str, MarketListingItem] = {}

        self._parse_apps_from_app_data(rj["app_data"])
        self._parse_descriptions_from_market_assets(rj["assets"], _item_descriptions_map)
        self._parse_market_listing_items(rj["assets"], _item_descriptions_map, _market_econ_items_map)

        # unknow fields: last_time, last_listing

        return self._create_purchase_infos(rj, _market_econ_items_map)

    # having get_popular_items will be good, but there is no api endpoint (or unknown) to get them
    # and we definitely don't want to parse html

    async def get_search_suggestions(self, query: str, app: App | None = None) -> list[MarketSearchSuggestion]:
        """
        Get market search suggestions.

        :param query: raw search query.
        :param app: `Steam` app.
        :return: list of search suggestions.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        """

        params = {"q": query}
        if app is not None:
            app_param = {"appid": str(app.id)}
            params |= app_param
            headers = {"Referer": str(SEARCH_URL % app_param)}
        else:
            headers = {"Referer": str(MARKET_URL)}

        r = await self._transport.request(
            "GET",
            MARKET_URL / "searchsuggestionsresults",
            params=params,
            headers=headers,
            response_mode="json",
        )

        rj: dict = r.content

        return [
            MarketSearchSuggestion(
                app=App(data["app_id"], data["app_name"], extract_icon_hash_from_app_icon_link(data["icon_url"]))
                if app is None
                else app,
                listing_count=data["listing_count"],
                market_name=data["market_name"],
                market_hash_name=data["market_hash_name"],
                market_type=data["market_type"],
                min_price=data["min_price"],
                search_score=data["search_score"],
            )
            for data in rj["results"]
        ]
