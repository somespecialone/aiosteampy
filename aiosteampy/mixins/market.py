from contextlib import suppress
from typing import overload, Literal, TypeAlias, AsyncIterator, Callable
from datetime import datetime
from re import search as re_search

from aiohttp import ClientResponseError
from aiohttp.client import _RequestContextManager

from ..typed import WalletInfo
from ..constants import (
    STEAM_URL,
    App,
    AppContext,
    MarketListingStatus,
    MarketHistoryEventType,
    T_PARAMS,
    T_PAYLOAD,
    T_HEADERS,
    EResult,
    Currency,
)
from ..models import (
    EconItem,
    MyMarketListing,
    BuyOrder,
    ItemDescription,
    MarketListingItem,
    MarketHistoryEvent,
    MarketHistoryListing,
    MarketHistoryListingItem,
    PriceHistoryEntry,
    MarketListing,
)
from ..helpers import currency_required
from ..exceptions import EResultError, SessionExpired
from ..utils import create_ident_code, buyer_pays_to_receive, calc_market_listing_fee
from .public import SteamCommunityPublicMixin, T_SHARED_DESCRIPTIONS
from .confirmation import ConfirmationMixin


MY_LISTINGS_DATA: TypeAlias = tuple[list[MyMarketListing], list[MyMarketListing], list[BuyOrder], int]
MY_MARKET_HISTORY_DATA: TypeAlias = tuple[list[MarketHistoryEvent], int]


class MarketMixin(ConfirmationMixin, SteamCommunityPublicMixin):
    """
    Mixin with market related methods.
    Depends on `ConfirmationMixin`, `SteamCommunityPublicMixin`.
    """

    __slots__ = ()

    # nice list
    @overload
    async def place_sell_listing(
        self,
        obj: EconItem,
        *,
        price: int,
        payload: T_PAYLOAD = ...,
        headers: T_HEADERS = ...,
    ) -> int:
        ...

    @overload
    async def place_sell_listing(
        self,
        obj: EconItem,
        *,
        price: int,
        confirm: Literal[False] = ...,
        payload: T_PAYLOAD = ...,
        headers: T_HEADERS = ...,
    ) -> None:
        ...

    @overload
    async def place_sell_listing(
        self,
        obj: EconItem,
        *,
        to_receive: int,
        payload: T_PAYLOAD = ...,
        headers: T_HEADERS = ...,
    ) -> int:
        ...

    @overload
    async def place_sell_listing(
        self,
        obj: EconItem,
        *,
        to_receive: int,
        confirm: Literal[False] = ...,
        payload: T_PAYLOAD = ...,
        headers: T_HEADERS = ...,
    ) -> None:
        ...

    @overload
    async def place_sell_listing(
        self,
        obj: int,
        app_context: AppContext,
        *,
        price: int,
        payload: T_PAYLOAD = ...,
        headers: T_HEADERS = ...,
    ) -> int:
        ...

    @overload
    async def place_sell_listing(
        self,
        obj: int,
        app_context: AppContext,
        *,
        price: int,
        confirm: Literal[False] = ...,
        payload: T_PAYLOAD = ...,
        headers: T_HEADERS = ...,
    ) -> None:
        ...

    @overload
    async def place_sell_listing(
        self,
        obj: int,
        app_context: AppContext,
        *,
        to_receive: int,
        payload: T_PAYLOAD = ...,
        headers: T_HEADERS = ...,
    ) -> int:
        ...

    @overload
    async def place_sell_listing(
        self,
        obj: int,
        app_context: AppContext,
        *,
        to_receive: int,
        confirm: Literal[False] = ...,
        payload: T_PAYLOAD = ...,
        headers: T_HEADERS = ...,
    ) -> None:
        ...

    @overload
    async def place_sell_listing(
        self,
        obj: EconItem,
        *,
        price: int,
        fetch: Literal[True] = ...,
        confirm: bool = ...,
        payload: T_PAYLOAD = ...,
        headers: T_HEADERS = ...,
    ) -> MyMarketListing:
        ...

    @overload
    async def place_sell_listing(
        self,
        obj: EconItem,
        *,
        to_receive: int,
        fetch: Literal[True] = ...,
        confirm: bool = ...,
        payload: T_PAYLOAD = ...,
        headers: T_HEADERS = ...,
    ) -> MyMarketListing:
        ...

    @overload
    async def place_sell_listing(
        self,
        obj: int,
        app_context: AppContext,
        *,
        price: int,
        fetch: Literal[True] = ...,
        confirm: bool = ...,
        payload: T_PAYLOAD = ...,
        headers: T_HEADERS = ...,
    ) -> MyMarketListing:
        ...

    @overload
    async def place_sell_listing(
        self,
        obj: int,
        app_context: AppContext,
        *,
        to_receive: int,
        fetch: Literal[True] = ...,
        confirm: bool = ...,
        payload: T_PAYLOAD = ...,
        headers: T_HEADERS = ...,
    ) -> MyMarketListing:
        ...

    async def place_sell_listing(
        self,
        obj: EconItem | int,
        app_context: AppContext = None,
        *,
        price: int = None,
        to_receive: int = None,
        fetch=False,
        confirm=True,
        payload: T_PAYLOAD = {},
        headers: T_HEADERS = {},
        _item_descriptions_map: T_SHARED_DESCRIPTIONS = None,
    ) -> int | MyMarketListing | None:
        """
        Create and place sell listing.
        If `confirm` is `True` - return listing id of created and confirmed sell listing,
        if this requires confirmation. If not - return `None`.

        .. note::
            * Money should be only and only in account wallet currency
            * `price` or `to_receive` is integers equal to cents

        :param obj: `EconItem` that you want to list on market or asset id
        :param app_context: `Steam` app+context
        :param price: money that buyer must pay. Include fees
        :param to_receive: money that you want to receive
        :param fetch: make request and return a listing
        :param confirm: confirm listing or not if steam demands mobile confirmation
        :param payload: extra payload data
        :param headers: extra headers to send with request
        :return: sell listing id, `MyMarketListing` or `None`
        :raises TypeError:
        :raises EResultError: for ordinary reasons
        """

        if isinstance(obj, EconItem):
            asset_id = obj.asset_id
            app_context = obj.app_context
        else:
            asset_id = obj

        # prevent user from mistake and potentially money loss
        if to_receive and price:
            raise TypeError("The `price` and `to_receive` arguments are mutually exclusive!")
        elif type(price) is float or type(to_receive) is float:
            raise TypeError(
                "The `price` and `to_receive` arguments should be integers. Did you forget to convert price to cents?"
            )

        to_receive = to_receive or buyer_pays_to_receive(price)[2]

        data = {
            "assetid": asset_id,
            "sessionid": self.session_id,
            "contextid": app_context.context,
            "appid": app_context.app.value,
            "amount": 1,
            "price": to_receive,
            **payload,
        }
        headers = {"Referer": str(STEAM_URL.COMMUNITY / f"profiles/{self.steam_id}/inventory"), **headers}
        r = await self.session.post(STEAM_URL.MARKET / "sellitem/", data=data, headers=headers)
        rj: dict = await r.json()
        success = EResult(rj.get("success"))
        if success is not EResult.OK:
            raise EResultError(rj.get("message", "Failed to place sell listing"), success, rj)

        to_return = None

        if rj.get("needs_mobile_confirmation") and confirm:
            conf = await self.confirm_sell_listing(asset_id, app_context)
            to_return = conf.creator_id

        if fetch:
            to_return = await self.get_my_sell_listing(asset_id=asset_id, _item_descriptions_map=_item_descriptions_map)

        return to_return

    @overload
    async def get_my_sell_listing(
        self,
        obj: int = ...,
        *,
        price: int = ...,
        need_confirmation: bool = ...,
        asset_id: int = ...,
        market_hash_name: str = ...,
        ident_code: str = ...,
        app_context: AppContext = ...,
        params: T_PARAMS = ...,
        headers: T_HEADERS = ...,
        **listing_item_attrs,
    ) -> MyMarketListing | None:
        ...

    @overload
    async def get_my_sell_listing(
        self,
        obj: Callable[[MyMarketListing], bool],
        *,
        params: T_PARAMS = ...,
        headers: T_HEADERS = ...,
    ) -> MyMarketListing | None:
        ...

    async def get_my_sell_listing(
        self,
        obj: int | Callable[[MyMarketListing], bool] = None,
        *,
        price: int = None,
        need_confirmation: bool = False,
        asset_id: int = None,
        market_hash_name: str = None,
        ident_code: str = None,
        app_context: AppContext = None,
        params: T_PARAMS = {},
        headers: T_HEADERS = {},
        _item_descriptions_map: T_SHARED_DESCRIPTIONS = None,
        **listing_item_attrs,
    ) -> MyMarketListing | None:
        """
        Fetch and iterate over sell listings pages until find one that satisfies passed arguments.

        :param obj: listing id or predicate function
        :param price: listing price
        :param need_confirmation: get listing from `to_confirm` list
        :param asset_id: asset id of listing item
        :param market_hash_name: market hash name of listing item
        :param ident_code: ident code of listing item
        :param app_context: `Steam` app+context
        :param params: extra params to pass to url
        :param headers: extra headers to send with request
        :param listing_item_attrs: additional listing item attributes and values
        :return: `MyMarketListing` or `None`
        :raises EResultError: for ordinary reasons
        :raises SessionExpired:
        """

        if callable(obj):
            predicate = obj
        else:

            def predicate(l: MyMarketListing):
                if obj is not None and l.id != obj:
                    return False
                if price is not None and l.price != price:
                    return False
                if asset_id is not None and l.item.asset_id != asset_id:
                    return False
                if market_hash_name is not None and l.item.description.market_hash_name != market_hash_name:
                    return False
                if ident_code is not None and l.item.id != ident_code:
                    return False
                if app_context is not None and l.item.app_context is not app_context:
                    return False

                for attr, value in listing_item_attrs.items():
                    if getattr(l.item, attr, None) != value:
                        return False

                return True

        async for listings, to_confirm, _, _ in self.my_listings(
            params=params,
            headers=headers,
            _item_descriptions_map=_item_descriptions_map,
        ):
            with suppress(StopIteration):
                return next(filter(predicate, to_confirm if need_confirmation else listings))

    def cancel_sell_listing(
        self,
        obj: MyMarketListing | int,
        *,
        payload: T_PAYLOAD = {},
        headers: T_HEADERS = {},
    ) -> _RequestContextManager:
        """
        Simply cancel sell listing.

        :param obj: `MyMarketListing` or listing id
        :param payload: extra payload data
        :param headers: extra headers to send with request
        """

        listing_id: int = obj.id if isinstance(obj, MyMarketListing) else obj
        data = {"sessionid": self.session_id, **payload}
        headers = {"Referer": str(STEAM_URL.MARKET), **headers}
        return self.session.post(STEAM_URL.MARKET / f"removelisting/{listing_id}", data=data, headers=headers)

    @overload
    async def place_buy_order(
        self,
        obj: ItemDescription,
        *,
        price: int,
        quantity: int = ...,
        payload: T_PAYLOAD = ...,
        headers: T_HEADERS = ...,
    ) -> int:
        ...

    @overload
    async def place_buy_order(
        self,
        obj: str,
        app: App,
        *,
        price: int,
        quantity: int = ...,
        payload: T_PAYLOAD = ...,
        headers: T_HEADERS = ...,
    ) -> int:
        ...

    @overload
    async def place_buy_order(
        self,
        obj: ItemDescription,
        *,
        price: int,
        quantity: int = ...,
        fetch: Literal[True] = ...,
        payload: T_PAYLOAD = ...,
        headers: T_HEADERS = ...,
    ) -> BuyOrder:
        ...

    @overload
    async def place_buy_order(
        self,
        obj: str,
        app: App,
        *,
        price: int,
        quantity: int = ...,
        fetch: Literal[True] = ...,
        payload: T_PAYLOAD = ...,
        headers: T_HEADERS = ...,
    ) -> BuyOrder:
        ...

    @currency_required
    async def place_buy_order(
        self,
        obj: str | ItemDescription,
        app: App = None,
        *,
        price: int,
        quantity=1,
        fetch=False,
        payload: T_PAYLOAD = {},
        headers: T_HEADERS = {},
        _item_descriptions_map: T_SHARED_DESCRIPTIONS = None,
    ) -> int | BuyOrder:
        """
        Place buy order on market.

        :param obj: `ItemDescription` or market hash name
        :param app: `Steam` app if `obj` is market hash name
        :param price: price of single item
        :param quantity: just quantity
        :param fetch: make request and return buy order
        :param payload: extra payload data
        :param headers: extra headers to send with request
        :return: buy order id or `BuyOrder`
        :raises EResultError: for ordinary reasons
        """

        if isinstance(obj, ItemDescription):
            name = obj.market_hash_name
            app = obj.app
        else:
            name = obj

        data = {
            "sessionid": self.session_id,
            "currency": self.currency.value,
            "appid": app.value,
            "market_hash_name": name,
            "price_total": price * quantity,
            "quantity": quantity,
            **payload,
        }
        headers = {"Referer": str(STEAM_URL.MARKET / f"listings/{app.value}/{name}"), **headers}
        r = await self.session.post(STEAM_URL.MARKET / "createbuyorder/", data=data, headers=headers)
        rj: dict = await r.json()
        success = EResult(rj.get("success"))
        if success is not EResult.OK:
            raise EResultError(rj.get("message", "Failed to create buy order"), success, rj)

        to_return = int(rj["buy_orderid"])
        if fetch:
            to_return = await self.get_my_buy_order(to_return, _item_descriptions_map=_item_descriptions_map)

        return to_return

    @overload
    async def get_my_buy_order(
        self,
        obj: int = ...,
        *,
        price: int = ...,
        quantity: int = ...,
        market_hash_name: str = ...,
        ident_code: str = ...,
        app: App = ...,
        params: T_PARAMS = ...,
        headers: T_HEADERS = ...,
        **item_description_attrs,
    ) -> BuyOrder | None:
        ...

    @overload
    async def get_my_buy_order(
        self,
        obj: Callable[[BuyOrder], bool],
        *,
        params: T_PARAMS = ...,
        headers: T_HEADERS = ...,
    ) -> BuyOrder | None:
        ...

    async def get_my_buy_order(
        self,
        obj: int | Callable[[BuyOrder], bool] = None,
        *,
        price: int = None,
        quantity: int = None,
        market_hash_name: str = None,
        ident_code: str = None,
        app: App = None,
        params: T_PARAMS = {},
        headers: T_HEADERS = {},
        _item_descriptions_map: T_SHARED_DESCRIPTIONS = None,
        **item_description_attrs,
    ) -> BuyOrder | None:
        """
        Fetch and iterate over buy order pages until find one that satisfies passed arguments.

        :param obj: order id or predicate function
        :param price: order price
        :param quantity: order quantity
        :param market_hash_name: name of item description
        :param ident_code: ident code of item description
        :param app: `Steam` app
        :param params: extra params to pass to url
        :param headers: extra headers to send with request
        :param item_description_attrs: additional item description attributes and values
        :return: `BuyOrder` or `None`
        :raises EResultError: for ordinary reasons
        :raises SessionExpired:
        """

        if callable(obj):
            predicate = obj
        else:

            def predicate(o: BuyOrder):
                if obj is not None and o.id != obj:
                    return False
                if price is not None and o.price != price:
                    return False
                if quantity is not None and o.quantity != quantity:
                    return False
                if market_hash_name is not None and o.item_description.market_hash_name != market_hash_name:
                    return False
                if ident_code is not None and o.item_description.id != ident_code:
                    return False
                if app is not None and o.item_description.app is not app:
                    return False

                for attr, value in item_description_attrs.items():
                    if getattr(o.item_description, attr, None) != value:
                        return False

                return True

        # count 1 to reduce unnecessary work, better check this
        data = await self.get_my_listings(
            count=1,
            params=params,
            headers=headers,
            _item_descriptions_map=_item_descriptions_map,
        )
        return next(filter(predicate, data[2]), None)

    async def cancel_buy_order(self, order: int | BuyOrder, *, payload: T_PAYLOAD = {}, headers: T_HEADERS = {}):
        """
        Just cancel buy order.

        :param order: `BuyOrder` or buy order id
        :param payload: extra payload data
        :param headers: extra headers to send with request
        :raises EResultError: for ordinary reasons
        """

        if isinstance(order, BuyOrder):
            order_id = order.id
        else:
            order_id = order

        data = {"sessionid": self.session_id, "buy_orderid": order_id, **payload}
        headers = {"Referer": str(STEAM_URL.MARKET), **headers}
        r = await self.session.post(STEAM_URL.MARKET / "cancelbuyorder/", data=data, headers=headers)
        rj = await r.json()
        success = EResult(rj.get("success"))
        if success is not EResult.OK:
            raise EResultError(rj.get("message", "Failed to cancel buy order"), success, rj)

    async def get_my_listings(
        self,
        *,
        start: int = 0,
        count: int = 100,
        params: T_PARAMS = {},
        headers: T_HEADERS = {},
        _item_descriptions_map: T_SHARED_DESCRIPTIONS = None,
    ) -> MY_LISTINGS_DATA:
        """
        Fetch users market listings.

        .. note:: you can paginate active listings by yourself passing `start` arg

        :param start: start index
        :param count: listings per page. `Steam` do not accept value greater than 100
        :param params: extra params to pass to url
        :param headers: extra headers to send with request
        :return: active listings, listings to confirm, buy orders, total count of active listings
        :raises EResultError: for ordinary reasons
        :raises SessionExpired:
        """

        params = {"norender": 1, "start": start, "count": count, **params}

        try:
            r = await self.session.get(STEAM_URL.MARKET / "mylistings", params=params, headers=headers)
        except ClientResponseError as e:
            raise SessionExpired if e.status == 400 else e  # Are we sure that there status code 400 and not 403?

        rj: dict = await r.json()
        success = EResult(rj.get("success"))
        if success is not EResult.OK:
            raise EResultError(rj.get("message", "Failed to fetch user listings"), success, rj)

        # no need to check `assets` or `total_count`

        if _item_descriptions_map is None:
            _item_descriptions_map = {}

        self._parse_item_descrs_from_my_listings_or_market_history(rj, _item_descriptions_map)

        active = self._parse_my_listings(rj["listings"], _item_descriptions_map)
        to_confirm = self._parse_my_listings(rj["listings_to_confirm"], _item_descriptions_map)
        buy_orders = self._parse_buy_orders(rj["buy_orders"], _item_descriptions_map)

        return active, to_confirm, buy_orders, rj["num_active_listings"]

    async def my_listings(
        self,
        *,
        start: int = 0,
        count: int = 100,
        params: T_PARAMS = {},
        headers: T_HEADERS = {},
        _item_descriptions_map: T_SHARED_DESCRIPTIONS = None,
    ) -> AsyncIterator[list[MyMarketListing]]:
        """
        Fetch users market listings. Return async iterator to paginate over listing pages.

        .. note:: paginates only over active listing pages.
            If you need to get orders or listings to confirm use `get_my_listings` method

        :param start: start index
        :param count: listings per page. Steam do not accept value greater than 100
        :param params: extra params to pass to url
        :param headers: extra headers to send with request
        :return: `AsyncIterator` that yields list of active `MyMarketListing`
        :raises EResultError: for ordinary reasons
        :raises SessionExpired:
        """

        if _item_descriptions_map is None:
            _item_descriptions_map = {}

        more_listings = True
        while more_listings:
            # avoid excess destructuring
            listings_data = await self.get_my_listings(
                start=start,
                count=count,
                params=params,
                headers=headers,
                _item_descriptions_map=_item_descriptions_map,
            )
            start += count
            more_listings = listings_data[3] > start

            yield listings_data[0]

    @classmethod
    def _parse_item_descrs_from_my_listings_or_market_history(
        cls,
        data: dict[str, dict | list[dict]],
        item_descrs_map: T_SHARED_DESCRIPTIONS,
    ):
        # assets field, has descriptions for listings, so we can not parse descrs from listings
        for app_id, app_data in (data["assets"] or {}).items():  # thanks Steam for an empty list instead of a dict
            for context_id, context_data in app_data.items():
                for asset_id, mixed_data in context_data.items():
                    key = create_ident_code(mixed_data["instanceid"], mixed_data["classid"], app_id)
                    if key not in item_descrs_map:
                        item_descrs_map[key] = cls._create_item_descr(mixed_data)

        for listing_data in data.get("listings_to_confirm", ()):
            mixed_data = listing_data["asset"]
            key = create_ident_code(mixed_data["instanceid"], mixed_data["classid"], mixed_data["appid"])
            if key not in item_descrs_map:
                item_descrs_map[key] = cls._create_item_descr(mixed_data)

        for order_data in data.get("buy_orders", ()):
            descr_data = order_data["description"]
            key = create_ident_code(descr_data["instanceid"], descr_data["classid"], descr_data["appid"])
            if key not in item_descrs_map:
                item_descrs_map[key] = cls._create_item_descr(descr_data)

    def _parse_my_listings(self, listings: list[dict], item_descrs_map: T_SHARED_DESCRIPTIONS) -> list[MyMarketListing]:
        return [
            MyMarketListing(
                id=int(l_data["listingid"]),
                price=l_data["price"],
                lister_steam_id=self.steam_id,
                time_created=datetime.fromtimestamp(l_data["time_created"]),
                item=MarketListingItem(
                    asset_id=int(l_data["asset"]["id"]),
                    unowned_id=int(l_data["asset"]["unowned_id"]) if "unowned_id" in l_data["asset"] else None,
                    owner_id=self.steam_id,
                    market_id=int(l_data["listingid"]),
                    unowned_context_id=int(l_data["asset"]["unowned_contextid"])
                    if "unowned_contextid" in l_data["asset"]
                    else None,
                    amount=int(l_data["asset"]["amount"]),
                    app_context=AppContext((App(int(l_data["asset"]["appid"])), int(l_data["asset"]["contextid"]))),
                    description=item_descrs_map[
                        create_ident_code(
                            l_data["asset"]["instanceid"],
                            l_data["asset"]["classid"],
                            l_data["asset"]["appid"],
                        )
                    ],
                ),
                status=MarketListingStatus(l_data["status"]),
                active=bool(l_data["active"]),
                item_expired=l_data["item_expired"],
                cancel_reason=l_data["cancel_reason"],
                time_finish_hold=l_data["time_finish_hold"],
            )
            for l_data in listings
        ]

    @classmethod
    def _parse_buy_orders(cls, orders: list[dict], item_descrs_map: T_SHARED_DESCRIPTIONS) -> list[BuyOrder]:
        return [
            BuyOrder(
                id=int(o_data["buy_orderid"]),
                price=int(o_data["price"]),
                item_description=item_descrs_map[
                    create_ident_code(
                        o_data["description"]["instanceid"],
                        o_data["description"]["classid"],
                        o_data["description"]["appid"],
                    )
                ],
                quantity=int(o_data["quantity"]),
                quantity_remaining=int(o_data["quantity_remaining"]),
            )
            for o_data in orders
        ]

    @overload
    async def buy_market_listing(
        self,
        obj: MarketListing,
        *,
        payload: T_PAYLOAD = ...,
        headers: T_HEADERS = ...,
    ) -> WalletInfo:
        ...

    @overload
    async def buy_market_listing(
        self,
        obj: int,
        price: int,
        market_hash_name: str,
        app: App,
        *,
        fee: int = ...,
        payload: T_PAYLOAD = ...,
        headers: T_HEADERS = ...,
    ) -> WalletInfo:
        ...

    @currency_required
    async def buy_market_listing(
        self,
        obj: int | MarketListing,
        price: int = None,
        market_hash_name: str = None,
        app: App = None,
        *,
        fee: int = None,
        payload: T_PAYLOAD = {},
        headers: T_HEADERS = {},
    ) -> WalletInfo:
        """
        Buy item listing from market.
        Unfortunately, `Steam` requires `referer` header to buy item,
        so `market_hash_name` and `app` is mandatory args in case of `obj` being a market id.

        .. note:: Make sure that listing converted currency same as wallet currency!

        :param obj: id for listing itself (aka market id) or `MarketListing`
        :param price: Can be found on listing data in `Steam` under field `converted_price`
        :param market_hash_name: market hash name of item. Needed for `Referer` header value
        :param app: `Steam` app
        :param fee: if fee of listing is different from default one,
            can be found on listing data in `Steam` under field `converted_fee`.
            If you don't know what this is - then you definitely do not need it
        :param payload: extra payload data
        :param headers: extra headers to send with request
        :return: wallet info
        :raises EResultError: for regular reasons
        :raises ValueError: if converted currency of `MarketListing` is different from wallet currency
        """

        if isinstance(obj, MarketListing):
            if obj.converted_currency is None:
                raise ValueError("Listing must contain converted currency!")
            elif obj.converted_currency is not self.currency:
                raise ValueError(
                    f"Currency of listing ({obj.converted_currency.value}) is "
                    f"different from wallet ({self.currency.value}) one!"
                )

            listing_id = obj.id
            price = obj.converted_price
            fee = obj.converted_fee
            market_hash_name = obj.item.description.market_hash_name
            app = obj.item.app_context.app
        else:
            listing_id = obj

            if app is None or market_hash_name is None or price is None:
                raise ValueError("`app`, `market_hash_name` and `price` arguments must be provided")

        fee = fee or calc_market_listing_fee(price)
        data = {
            "sessionid": self.session_id,
            "currency": self.currency.value,
            "subtotal": price,
            "fee": fee,
            "total": price + fee,
            "quantity": 1,
            **payload,
        }
        headers = {"Referer": str(STEAM_URL.MARKET / f"listings/{app.value}/{market_hash_name}"), **headers}
        r = await self.session.post(
            STEAM_URL.MARKET / f"buylisting/{listing_id}",
            data=data,
            headers=headers,
            raise_for_status=False,
        )
        # ClientResponseError with code 502 [Bad Gateway] will be raised in case of insufficient balance, need
        # to do something with this somehow ...
        rj: dict[str, dict[str, str]] = await r.json()
        wallet_info: WalletInfo = rj.get("wallet_info", {})
        success = EResult(wallet_info.get("success"))
        if success is not EResult.OK:
            raise EResultError(rj.get("message", wallet_info.get("message", "Failed to buy listing")), success, rj)

        # how about to return remaining balance only?
        return wallet_info

    async def get_my_market_history(
        self,
        *,
        start: int = 0,
        count: int = 100,
        params: T_PARAMS = {},
        headers: T_HEADERS = {},
        _item_descriptions_map: T_SHARED_DESCRIPTIONS = None,
        _market_history_econ_items_map: dict[str, MarketHistoryListingItem] = None,
        _market_history_listings_map: dict[int, MarketHistoryListing] = None,
    ) -> MY_MARKET_HISTORY_DATA:
        """
        Fetch market history of self.

        .. note:: You can paginate by yourself passing `start` arg

        :param start: start index
        :param count: listings per page. Steam do not accept value greater than 100
        :param params: extra params to pass to url
        :param headers: extra headers to send with request
        :return: list of `MarketHistoryEvent`, total_count
        :raises EResultError: for ordinary reasons
        :raises SessionExpired:
        """

        params = {"norender": 1, "start": start, "count": count, **params}

        try:
            r = await self.session.get(STEAM_URL.MARKET / "myhistory", params=params, headers=headers)
        except ClientResponseError as e:
            raise SessionExpired if e.status == 400 else e

        rj: dict = await r.json()
        success = EResult(rj.get("success"))
        if success is not EResult.OK:
            raise EResultError(rj.get("message", "Failed to fetch user listings"), success, rj)

        if not rj["total_count"] or not rj["assets"]:  # safe
            return [], 0

        if _item_descriptions_map is None:
            _item_descriptions_map = {}
        if _market_history_econ_items_map is None:
            _market_history_econ_items_map = {}
        if _market_history_listings_map is None:
            _market_history_listings_map = {}

        self._parse_item_descrs_from_my_listings_or_market_history(rj, _item_descriptions_map)
        self._parse_assets_for_history_listings(rj["assets"], _item_descriptions_map, _market_history_econ_items_map)
        self._parse_history_listings(rj, _market_history_econ_items_map, _market_history_listings_map)

        return self._parse_history_events(rj, _market_history_listings_map), rj["total_count"]

    async def my_market_history(
        self,
        *,
        start: int = 0,
        count: int = 100,
        params: T_PARAMS = {},
        headers: T_HEADERS = {},
        _item_descriptions_map: T_SHARED_DESCRIPTIONS = None,
        _market_history_econ_items_map: dict[str, MarketHistoryListingItem] = None,
        _market_history_listings_map: dict[int, MarketHistoryListing] = None,
    ) -> AsyncIterator[MY_MARKET_HISTORY_DATA]:
        """
        Fetch market history of self. Return async iterator to paginate over history event pages.

        :param start: start index
        :param count: listings per page. Steam do not accept value greater than 100
        :param params: extra params to pass to url
        :param headers: extra headers to send with request
        :return: `AsyncIterator` that yields list of `MarketHistoryEvent`, total_count
        :raises EResultError: for ordinary reasons
        :raises SessionExpired:
        """

        if _item_descriptions_map is not None:
            _item_descriptions_map = {}
        if _market_history_econ_items_map is not None:
            _market_history_econ_items_map = {}
        if _market_history_listings_map is not None:
            _market_history_listings_map = {}

        more_listings = True
        while more_listings:
            # avoid excess destructuring
            history_data = await self.get_my_market_history(
                start=start,
                count=count,
                params=params,
                headers=headers,
                _item_descriptions_map=_item_descriptions_map,
                _market_history_econ_items_map=_market_history_econ_items_map,
                _market_history_listings_map=_market_history_listings_map,
            )
            start += count
            more_listings = history_data[1] > start

            yield history_data

    @staticmethod
    def _parse_assets_for_history_listings(
        data: dict[str, dict[str, dict[str, dict]]],
        item_descrs_map: T_SHARED_DESCRIPTIONS,
        econ_item_map: dict[str, MarketHistoryListingItem],
    ):
        for app_id, app_data in data.items():
            for context_id, context_data in app_data.items():
                for a_data in context_data.values():
                    # because I don't know why in data `id` and `unowned_id` combinations and how that suppose to work
                    key_id = create_ident_code(a_data["id"], context_id, app_id)
                    key_unowned_id = create_ident_code(a_data["unowned_id"], context_id, app_id)
                    if key_id not in item_descrs_map or key_unowned_id not in item_descrs_map:
                        econ_item = MarketHistoryListingItem(
                            asset_id=int(a_data["id"]),
                            unowned_id=int(a_data["unowned_id"]),
                            unowned_context_id=int(a_data["unowned_contextid"]),
                            rollback_new_asset_id=int(a_data["rollback_new_id"])
                            if "rollback_new_id" in a_data
                            else None,
                            rollback_new_context_id=int(a_data["rollback_new_contextid"])
                            if "rollback_new_contextid" in a_data
                            else None,
                            app_context=AppContext((App(int(a_data["appid"])), int(a_data["contextid"]))),
                            description=item_descrs_map[
                                create_ident_code(
                                    a_data["instanceid"],
                                    a_data["classid"],
                                    app_id,
                                )
                            ],
                        )
                        if key_id not in econ_item_map:
                            econ_item_map[key_id] = econ_item
                        if key_unowned_id not in econ_item_map:
                            econ_item_map[key_unowned_id] = econ_item

    @staticmethod
    def _parse_history_listings(
        data: dict[str, dict[str, dict]],
        econ_item_map: dict[str, MarketHistoryListingItem],
        listings_map: dict[str, MarketHistoryListing],
    ):
        for l_id, l_data in data["listings"].items():  # sell listings
            if l_id not in listings_map:
                listings_map[l_id] = MarketHistoryListing(
                    id=int(l_data["listingid"]),
                    currency=Currency(int(l_data["currencyid"]) - 2000),
                    price=int(l_data["price"]),
                    fee=int(l_data["fee"]),
                    item=econ_item_map[
                        create_ident_code(
                            l_data["asset"]["id"],
                            l_data["asset"]["contextid"],
                            l_data["asset"]["appid"],
                        )
                    ],
                    original_price=int(l_data["original_price"]),
                    cancel_reason=l_data.get("cancel_reason"),
                )

        for p_id, p_data in data["purchases"].items():  # purchases :)
            if p_id not in listings_map:
                listing = MarketHistoryListing(
                    id=int(p_data["listingid"]),
                    currency=Currency(int(p_data["currencyid"]) - 2000),
                    received_currency=Currency(int(p_data["received_currencyid"]) - 2000),
                    paid_amount=int(p_data["paid_amount"]),
                    paid_fee=int(p_data["paid_fee"]),
                    steam_fee=int(p_data["steam_fee"]),
                    publisher_fee=int(p_data["publisher_fee"]),
                    time_sold=datetime.fromtimestamp(p_data["time_sold"]),
                    item=econ_item_map[
                        create_ident_code(
                            p_data["asset"]["id"],
                            p_data["asset"]["contextid"],
                            p_data["asset"]["appid"],
                        )
                    ],
                    purchase_id=int(p_data["purchaseid"]),
                    steamid_purchaser=int(p_data["steamid_purchaser"]),
                    received_amount=int(p_data["received_amount"]),
                )
                listing.item.new_asset_id = int(p_data["asset"]["new_id"])
                listing.item.new_context_id = int(p_data["asset"]["new_contextid"])

                listings_map[p_id] = listing

    @staticmethod
    def _parse_history_events(
        data: dict[str, list[dict] | dict[str, dict]],
        listings_map: dict[str, MarketHistoryListing],
    ) -> list[MarketHistoryEvent]:
        events = []
        for e_data in data["events"]:
            listing_key = e_data["listingid"]
            if "purchaseid" in e_data:
                listing_key += "_" + e_data["purchaseid"]

            events.append(
                MarketHistoryEvent(
                    listing=listings_map[listing_key],
                    time_event=datetime.fromtimestamp(e_data["time_event"]),
                    type=MarketHistoryEventType(e_data["event_type"]),
                )
            )

        return events

    @overload
    async def fetch_price_history(
        self,
        obj: ItemDescription,
        *,
        params: T_PARAMS = ...,
        headers: T_HEADERS = ...,
    ) -> list[PriceHistoryEntry]:
        ...

    @overload
    async def fetch_price_history(
        self,
        obj: str,
        app: App,
        *,
        params: T_PARAMS = ...,
        headers: T_HEADERS = ...,
    ) -> list[PriceHistoryEntry]:
        ...

    async def fetch_price_history(
        self,
        obj: str | ItemDescription,
        app: App = None,
        *,
        params: T_PARAMS = {},
        headers: T_HEADERS = {},
    ) -> list[PriceHistoryEntry]:
        """
        Fetch price history.
        Prices always will be same currency as a wallet.

        .. seealso:: https://github.com/Revadike/InternalSteamWebAPI/wiki/Get-Market-Price-History

        .. note:: This request is rate limited by Steam.

        :param obj: `ItemDescription` or market hash name
        :param app: `Steam` app
        :param params: extra params to pass to url
        :param headers: extra headers to send with request
        :return: list of `PriceHistoryEntry`
        :raises EResultError:
        """

        if isinstance(obj, ItemDescription):
            name = obj.market_hash_name
            app = obj.app
        else:  # str
            name = obj

        params = {"appid": app.value, "market_hash_name": name, **params}
        r = await self.session.get(STEAM_URL.MARKET / "pricehistory", params=params, headers=headers)
        rj: dict[str, list[list]] = await r.json()
        success = EResult(rj.get("success"))
        if success is not EResult.OK:
            raise EResultError(rj.get("message", "Failed to fetch price history"), success, rj)

        return [
            PriceHistoryEntry(
                date=datetime.strptime(e_data[0].replace("+0", "+0000"), "%b %d %Y %H: %z"),
                price=e_data[1],
                daily_volume=int(e_data[2]),
            )
            for e_data in rj["prices"]
        ]

    async def get_market_availability_info(self) -> tuple[bool, datetime | None]:
        """
        Return market status of whether it is available or not and, if possible, "when" the market will be available

        .. seealso:: https://help.steampowered.com/en/faqs/view/451E-96B3-D194-50FC
        """

        r = await self.session.get(STEAM_URL.MARKET, headers={"Referer": str(STEAM_URL.STORE)})
        rt = await r.text()

        available = True
        when: datetime | None = None

        if "The Market is unavailable for the following reason" in rt:
            available = False

            if "dateCanUseMarket" in rt:
                when = datetime.strptime(
                    re_search(r"var dateCanUseMarket = new Date\(\"(?P<date>.+)\"\);", rt).group("date"),
                    "%a, %d %b %Y %H:%M:%S %z",
                )

        # it would be nice if we can retrieve purchase history from https://store.steampowered.com/account/history/
        # domain (not steamcommunity, unfortunately, so cookies are separated), parse it and calc estimate market block
        # datetime, depends on last store purchase

        return available, when

    async def is_market_available(self) -> bool:
        info = await self.get_market_availability_info()
        return info[0]
