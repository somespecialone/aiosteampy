import re

from contextlib import suppress
from collections.abc import AsyncGenerator
from typing import overload, Literal, Callable, TYPE_CHECKING
from datetime import datetime

from ...types import Coro, AppMap
from ...app import App, AppContext
from ...constants import Currency, STEAM_URL, EResult
from ...exceptions import (
    EResultError,
    SessionExpired,
    NeedMobileConfirmation,
    NeedEmailConfirmation,
)
from ...utils import create_ident_code
from ...models import ItemDescription, EconItem
from ...id import SteamID
from ...transport import BaseSteamTransport, TransportError, TransportResponse
from ...session import SteamLoginSession

if TYPE_CHECKING:  # make market component independent from confirmation component
    from ..confirmation import ConfirmationComponent, Confirmation

from .utils import buyer_pays_to_receive, calc_market_listing_fee
from .exceptions import InsufficientBalance, ListingRemoved
from .models import (
    MarketListingStatus,
    MarketListingItem,
    ListingValues,
    MyMarketListing,
    BuyOrder,
    MarketListing,
    BuyOrderStatus,
    WalletInfo,
    MarketHistoryListingItem,
    MarketHistoryListing,
    MarketHistoryEventType,
    MarketHistoryEvent,
    PriceHistoryEntry,
)
from .public import MARKET_URL, ItemDescriptionsMap, MarketPublicComponent


UserListingData = tuple[list[MyMarketListing], list[MyMarketListing], list[BuyOrder], int]
UserMarketHistoryData = tuple[list[MarketHistoryEvent], int]


class MarketComponent(MarketPublicComponent):
    """Component for working with `Steam Market`. Requires authentication."""

    __slots__ = ("_session", "_conf")

    def __init__(
        self,
        session: SteamLoginSession,
        country: str = "UA",
        currency: Currency = Currency.USD,
        confirmation: "ConfirmationComponent | None" = None,
    ):
        super().__init__(session.transport, country, currency)

        self._session = session

        self._conf = confirmation

    @overload
    async def confirm_sell_listing(self, obj: int, app_ctx: AppContext) -> "Confirmation": ...

    @overload
    async def confirm_sell_listing(self, obj: MyMarketListing | EconItem | int) -> "Confirmation": ...

    async def confirm_sell_listing(
        self,
        obj: MyMarketListing | EconItem | int,
        app_ctx: AppContext | None = None,
    ) -> "Confirmation":
        """
        Perform sell listing confirmation.

        :param obj: ``MyMarketListing``, ``EconItem`` that you listed, `listing id` or `asset id`.
        :param app_ctx: ``AppContext`` of item. Required when ``obj`` is `asset id`.
        :return: processed ``Confirmation``.
        :raises KeyError: if confirmation not found.
        :raises EResultError: ordinary reasons.
        :raises TransportError: arbitrary reasons.
        :raises SessionExpired: current login session is expired.
        :raises ValueError: if ``ConfirmationComponent`` is not provided.
        """

        if self._conf is None:
            raise ValueError("Confirmation component is required to use this method")

        details_for_listing_type = False  # avoid unnecessary requests
        if isinstance(obj, MyMarketListing):
            key = obj.id
        elif isinstance(obj, EconItem):
            key = obj.id
            details_for_listing_type = True
        else:  # int and app ctx
            if app_ctx is not None:  # asset id & app context
                key = create_ident_code(obj, app_ctx.context_id, app_ctx.app.id)
                details_for_listing_type = True
            else:  # listing id
                key = obj

        if conf := await self._conf.get_confirmation(key, details_for_listing_type=details_for_listing_type):
            await self._conf.allow_confirmation(conf)
            return conf
        else:
            raise KeyError(f"No confirmation found for listing: {key}")

    @classmethod
    def _parse_descriptions_from_my_listings_or_market_history(
        cls,
        data: dict[str, dict | list[dict]],
        item_descriptions_map: ItemDescriptionsMap,
        app_map: AppMap,
    ):
        """
        Extract item descriptions from user listings data or market history data to ``item_descriptions_map`` dict.
        """

        for app_id, app_data in (data["assets"] or {}).items():  # thanks to Steam for an empty list instead of a dict
            app_id_int = int(app_id)
            if app_id_int not in app_map:
                app_map[app_id_int] = App(app_id_int)

            for context_id, context_data in app_data.items():
                for asset_id, mixed_data in context_data.items():
                    key = create_ident_code(mixed_data["instanceid"], mixed_data["classid"], app_id)
                    if key not in item_descriptions_map:
                        item_descriptions_map[key] = cls._create_item_descr(mixed_data, app_map)

                    # there can be retrieved app ico, but

        for listing_data in data.get("listings_to_confirm", ()):
            mixed_data = listing_data["asset"]

            app_id_int = int(mixed_data["appid"])
            if app_id_int not in app_map:
                app_map[app_id_int] = App(app_id_int)

            key = create_ident_code(mixed_data["instanceid"], mixed_data["classid"], mixed_data["appid"])
            if key not in item_descriptions_map:
                item_descriptions_map[key] = cls._create_item_descr(mixed_data, app_map)

        for order_data in data.get("buy_orders", ()):
            descr_data = order_data.get("description")
            if not descr_data:  # ignore orders with invalid outdated descriptions
                continue

            app_id_int = int(descr_data["appid"])
            if app_id_int not in app_map:
                app_map[app_id_int] = App(app_id_int)

            key = create_ident_code(descr_data["instanceid"], descr_data["classid"], descr_data["appid"])
            if key not in item_descriptions_map:
                item_descriptions_map[key] = cls._create_item_descr(descr_data, app_map)

    def _parse_my_listings(
        self,
        listings: list[dict],
        item_descriptions_map: ItemDescriptionsMap,
    ) -> list[MyMarketListing]:
        return [
            MyMarketListing(
                id=int(l_data["listingid"]),
                lister=self._session.steam_id,  # no need to parse data again
                created_at=datetime.fromtimestamp(l_data["time_created"]),
                item=MarketListingItem(
                    context_id=int(l_data["asset"]["contextid"]),
                    asset_id=int(l_data["asset"]["id"]),
                    unowned_id=int(l_data["asset"]["unowned_id"]) if "unowned_id" in l_data["asset"] else None,
                    # owner_id=self.steam_id,
                    market_id=int(l_data["listingid"]),
                    unowned_context_id=(
                        int(l_data["asset"]["unowned_contextid"]) if "unowned_contextid" in l_data["asset"] else None
                    ),
                    amount=int(l_data["asset"]["amount"]),
                    description=item_descriptions_map[
                        create_ident_code(
                            l_data["asset"]["instanceid"],
                            l_data["asset"]["classid"],
                            l_data["asset"]["appid"],
                        )
                    ],
                    properties=self._parse_asset_properties(l_data["asset"]),
                ),
                status=MarketListingStatus(l_data["status"]),
                active=bool(l_data["active"]),
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
                ),
            )
            for l_data in listings
        ]

    @classmethod
    def _parse_buy_orders(cls, orders: list[dict], item_descriptions_map: ItemDescriptionsMap) -> list[BuyOrder]:
        return [
            BuyOrder(
                id=int(o_data["buy_orderid"]),
                price=int(o_data["price"]),
                item_description=item_descriptions_map[
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

    async def get_my_listings(
        self,
        *,
        start: int = 0,
        count: int = 100,
        # share mapping with iterator method
        _app_map: AppMap | None = None,
        _item_descriptions_map: ItemDescriptionsMap | None = None,
    ) -> UserListingData:
        """
        Get current user market listings.

        .. note:: Pagination of active listings can be achieved by passing ``start`` arg.

        :param start: start index.
        :param count: listings per page.
        :return: active listings, listings to confirm, buy orders, total count of active listings.
        :raises EResultError: ordinary reasons.
        :raises TransportError: arbitrary reasons.
        :raises SessionExpired: current login session is expired.
        """

        try:
            r = await self._transport.request(
                "GET",
                MARKET_URL / "mylistings",
                params={"norender": 1, "start": start, "count": count},
                response_mode="json",
            )
        except TransportError as e:
            if e.response and e.response.status == 400:  # We sure that there are code 400
                raise SessionExpired
            else:
                raise

        rj: dict = r.content

        EResultError.check_data(rj)

        # no need to check `assets` or `total_count`

        _app_map = {} if _app_map is None else _app_map
        _item_descriptions_map = {} if _item_descriptions_map is None else _item_descriptions_map

        # we get only app id here, so func below will do the work
        self._parse_descriptions_from_my_listings_or_market_history(rj, _item_descriptions_map, _app_map)

        active = self._parse_my_listings(rj["listings"], _item_descriptions_map)
        # what is "listings_on_hold"?
        to_confirm = self._parse_my_listings(rj["listings_to_confirm"], _item_descriptions_map)
        buy_orders = self._parse_buy_orders(rj["buy_orders"], _item_descriptions_map)

        return active, to_confirm, buy_orders, rj["num_active_listings"]

    async def my_listings(self, *, start: int = 0, count: int = 100) -> AsyncGenerator[UserListingData, None]:
        """
        Get current user market listings as async generator to paginate over.

        :param start: start index.
        :param count: listings per page.
        :return: ``AsyncGenerator`` that yields list of active listings as page,
            listings to confirm, buy orders, total count of active listings.
        :raises EResultError: ordinary reasons.
        :raises TransportError: arbitrary reasons.
        :raises SessionExpired: current login session is expired.
        """

        _app_map = {}
        _item_descriptions_map = {}

        more_listings = True
        while more_listings:
            # avoid excess destructuring
            listings_data = await self.get_my_listings(
                start=start,
                count=count,
                _app_map=_app_map,
                _item_descriptions_map=_item_descriptions_map,
            )
            start += count
            more_listings = listings_data[3] > start

            yield listings_data[0]

    @overload
    async def get_my_sell_listing(
        self,
        obj: int = ...,
        *,
        need_confirmation: bool = ...,
        asset_id: int = ...,
        ident_code: str = ...,
    ) -> MyMarketListing | None: ...

    @overload
    async def get_my_sell_listing(self, obj: Callable[[MyMarketListing], bool]) -> MyMarketListing | None: ...

    async def get_my_sell_listing(
        self,
        obj: int | Callable[[MyMarketListing], bool] | None = None,
        *,
        need_confirmation: bool = False,
        asset_id: int | None = None,
        ident_code: str | None = None,
    ) -> MyMarketListing | None:
        """
        Iterate over current user sell listings pages
        until find *first one* that satisfies passed arguments.

        :param obj: `listing id` or `predicate` function.
        :param need_confirmation: get listing from `to_confirm` list.
        :param asset_id: asset id of listing item.
        :param ident_code: ident code of listing item.
        :return: ``MyMarketListing`` or ``None``.
        :raises EResultError: ordinary reasons.
        :raises TransportError: arbitrary reasons.
        :raises SessionExpired: current login session is expired.
        :raises ValueError: required arguments not provided.
        """

        if not sum(map(bool, (obj, need_confirmation, asset_id, ident_code))):
            raise ValueError("At least one of arguments must be provided")

        if callable(obj):
            predicate = obj
        else:

            def predicate(listing: MyMarketListing):
                if obj is not None and listing.id != obj:
                    return False
                if asset_id is not None and listing.item.asset_id != asset_id:
                    return False
                if ident_code is not None and listing.item.id != ident_code:
                    return False

                return True

        async for listings, to_confirm, _, _ in self.my_listings():
            with suppress(StopIteration):  # iterate until find first one that satisfies predicate
                return next(filter(predicate, to_confirm if need_confirmation else listings))

    async def get_my_buy_order(self, obj: int | Callable[[BuyOrder], bool]) -> BuyOrder | None:
        """
        Get current user buy orders and return *first one* that satisfies passed arguments.

        :param obj: `order id` or predicate function.
        :return: ``BuyOrder`` or ``None``.
        :raises EResultError: ordinary reasons.
        :raises TransportError: arbitrary reasons.
        :raises SessionExpired: current login session is expired.
        """

        if callable(obj):
            predicate = obj
        else:

            def predicate(order: BuyOrder):
                return order.id == obj

        # count 1 to reduce unnecessary work as we only need buy orders
        _, _, orders, _ = await self.get_my_listings(count=1)
        return next(filter(predicate, orders), None)

    @overload
    async def place_sell_listing(
        self,
        obj: EconItem,
        *,
        price: int,
    ) -> int | None: ...

    @overload
    async def place_sell_listing(
        self,
        obj: EconItem,
        *,
        to_receive: int,
    ) -> int | None: ...

    @overload
    async def place_sell_listing(
        self,
        obj: int,
        app_ctx: AppContext,
        *,
        price: int,
    ) -> int | None: ...

    @overload
    async def place_sell_listing(
        self,
        obj: int,
        app_ctx: AppContext,
        *,
        to_receive: int,
    ) -> int | None: ...

    async def place_sell_listing(
        self,
        obj: EconItem | int,
        app_ctx: AppContext | None = None,
        *,
        price: int | None = None,
        to_receive: int | None = None,
    ) -> int | None:
        """
        Create and place sell listing.

        .. note::
            * Money should be only and **only in account wallet currency**.
            * ``price`` or ``to_receive`` is integers equal to cents.

        :param obj: ``EconItem`` that you want to list on market or it's `asset id`.
        :param app_ctx: ``AppContext`` of item.
        :param price: money that *buyer must pay*, including fees.
        :param to_receive: money that listener will *receive*.
        :return: `listing id` or ``None``.
        :raises ValueError: item is not marketable, wrong arguments combination or types.
        :raises EResultError: ordinary reasons.
        :raises TransportError: arbitrary reasons.
        :raises NeedConfirmation: market action requires confirmation.
        """

        # flow: place sell listing -> listing created but not active -> allow confirmation -> listing activated

        if isinstance(obj, EconItem):
            asset_id = obj.asset_id
            app_ctx = obj.app_context

            if not obj.description.marketable:
                raise ValueError("Item is not marketable")

        else:
            asset_id = obj

        # prevent user from mistake and potentially money loss
        if to_receive and price:
            raise ValueError("The `price` and `to_receive` arguments are mutually exclusive!")
        elif type(price) is float or type(to_receive) is float:
            raise ValueError(
                "The `price` and `to_receive` arguments should be integers. Did you forget to convert price to cents?"
            )

        to_receive = to_receive or buyer_pays_to_receive(price)[2]

        data = {
            "assetid": asset_id,
            "sessionid": self._transport.session_id,
            "contextid": app_ctx.context_id,
            "appid": app_ctx.app.id,
            "amount": 1,
            "price": to_receive,
        }
        r = await self._transport.request(
            "POST",
            MARKET_URL / "sellitem/",
            data=data,
            # there must be profile alias, but who cares
            headers={"Referer": str(STEAM_URL.COMMUNITY / f"profiles/{self._session.steam_id.id64}/inventory")},
            response_mode="json",
        )
        rj: dict = r.content

        if rj.get("needs_mobile_confirmation"):
            if self._conf is None:
                conf_key = create_ident_code(asset_id, app_ctx.context_id, app_ctx.app.id)
                raise NeedMobileConfirmation(conf_key)

            conf = await self.confirm_sell_listing(asset_id, app_ctx)
            return conf.creator_id  # listing id

        elif rj.get("needs_email_confirmation"):
            raise NeedEmailConfirmation

        EResultError.check_data(rj)

    async def cancel_sell_listing(self, obj: MyMarketListing | int) -> Coro[TransportResponse]:
        """
        Cancel current user active sell listing.

        :param obj: ``MyMarketListing`` or `listing id`.
        """

        listing_id = obj.id if isinstance(obj, MyMarketListing) else obj
        return self._transport.request(
            "POST",
            MARKET_URL / f"removelisting/{listing_id}",
            data={"sessionid": self._transport.session_id},
            headers={"Referer": str(MARKET_URL)},
            response_mode="meta",
        )

    @overload
    async def place_buy_order(
        self,
        obj: ItemDescription,
        *,
        price: int,
        quantity: int = ...,
        confirmation_id: int = ...,
    ) -> int: ...

    @overload
    async def place_buy_order(
        self,
        obj: str,
        app: App,
        *,
        price: int,
        quantity: int = ...,
        confirmation_id: int = ...,
    ) -> int: ...

    async def place_buy_order(
        self,
        obj: str | ItemDescription,
        app: App | None = None,
        *,
        price: int,
        quantity: int = 1,
        confirmation_id: int = 0,
    ) -> int:
        """
        Place buy order.

        :param obj: ``ItemDescription`` or `market hash name` of item that needs to be bought.
        :param app: `Steam` app.
        :param price: how much will be paid for single item.
        :param quantity: how much items need to be bought.
        :param confirmation_id: `confirmation id` of order.
        :return: `buy order id` or ``BuyOrder``.
        :raises EResultError: ordinary reasons.
        :raises TransportError: arbitrary reasons.
        :raises NeedConfirmation: market action requires confirmation.
        """

        # flow:
        # place buy order
        # -> get "need_confirmation" data with conf id
        # (browser repeat create buy order request with conf id every few seconds)
        # -> allow confirmation
        # -> placing buy order return success
        # -> browser get order status

        if isinstance(obj, ItemDescription):
            name = obj.market_hash_name
            app = obj.app
        else:
            name = obj

        data = {
            "sessionid": self._transport.session_id,
            "currency": self._currency.value,
            "appid": app.id,
            "market_hash_name": name,
            "price_total": price * quantity,
            "quantity": quantity,
            "confirmation": confirmation_id,
        }

        try:
            r = await self._transport.request(
                "POST",
                MARKET_URL / "createbuyorder/",
                data=data,
                headers={"Referer": str(MARKET_URL / f"listings/{app.id}/{name}")},
                response_mode="json",
            )
        except TransportError as e:
            if e.response and e.response.status == 406:  # need confirmation
                r = e.response
            else:
                raise

        rj: dict = r.content

        if rj.get("need_confirmation"):
            confirmation_id = int(rj["confirmation"]["confirmation_id"])

            if self._conf is None:
                raise NeedMobileConfirmation(confirmation_id)

            conf = await self._conf.get_confirmation(confirmation_id)
            await self._conf.allow_confirmation(conf)

            return await self.place_buy_order(
                obj,
                app,
                price=price,
                quantity=quantity,
                confirmation_id=confirmation_id,
            )

        EResultError.check_data(rj)

        return int(rj["buy_orderid"])

    async def get_buy_order_status(self, obj: BuyOrder | int) -> BuyOrderStatus:
        """
        Get buy order status.

        :param obj: ``BuyOrder`` or `buy order id`.
        :return: ``BuyOrderStatus``.
        :raises EResultError: ordinary reasons.
        :raises TransportError: arbitrary reasons.
        """

        if isinstance(obj, BuyOrder):
            buy_order_id = obj.id
            headers = {"Referer": str(obj.item_description.market_url)}  # at least there
        else:
            buy_order_id = obj
            headers = None

        try:
            r = await self._transport.request(
                "GET",
                MARKET_URL / "getbuyorderstatus/",
                params={"sessionid": self._transport.session_id, "buy_orderid": buy_order_id},
                headers=headers,
                response_mode="json",
            )
        except TransportError as e:
            if e.response and e.response.status == 406:  # also need confirmation
                r = e.response
            else:
                raise

        rj: dict = r.content

        if rj.get("need_confirmation"):
            return BuyOrderStatus(need_confirmation=True)

        EResultError.check_data(rj)

        return BuyOrderStatus(
            active=bool(rj["active"]),
            purchased=bool(rj["purchased"]),
            quantity=int(rj["quantity"]),
            quantity_remaining=int(rj["quantity_remaining"]),
        )

    def cancel_buy_order(self, order: int | BuyOrder) -> Coro[TransportResponse]:
        """
        Cancel current user active buy order.

        :param order: ``BuyOrder`` or `buy order id`.
        :raises TransportError: arbitrary reasons.
        """

        if isinstance(order, BuyOrder):
            order_id = order.id
        else:
            order_id = order

        return self._transport.request(
            "POST",
            MARKET_URL / "cancelbuyorder/",
            data={"sessionid": self._transport.session_id, "buy_orderid": order_id},
            headers={"Referer": str(MARKET_URL)},
            response_mode="meta",
        )

    @overload
    async def buy_market_listing(
        self,
        obj: MarketListing,
        *,
        confirmation_id: int = ...,
    ) -> WalletInfo: ...

    @overload
    async def buy_market_listing(
        self,
        obj: int,
        price: int,
        market_hash_name: str,
        app: App,
        *,
        fee: int = ...,
        confirmation_id: int = ...,
    ) -> WalletInfo: ...

    async def buy_market_listing(
        self,
        obj: int | MarketListing,
        price: int | None = None,
        market_hash_name: str | None = None,
        app: App | None = None,
        *,
        fee: int | None = None,
        confirmation_id: int = 0,
    ) -> WalletInfo:
        """
        Buy item listing from market.
        Unfortunately, `Steam` requires `Referer` header to buy item,
        so ``market_hash_name`` and ``app`` is mandatory args in case of ``obj`` being a market id.

        :param obj: `listing id` (aka `market id`) or ``MarketListing``.
        :param price: price of listing in *converted currency*.
        :param market_hash_name: `market hash name` of item.
        :param app: `Steam` app.
        :param fee: fee in *converted currency*.
            If you don't know what this is - then you definitely do not need it.
        :param confirmation_id: `confirmation id` of order.
        :return: ``WalletInfo``.
        :raises EResultError: ordinary reasons.
        :raises TransportError: arbitrary reasons.
        :raises ValueError: listing already sold,
            converted currency of ``MarketListing`` is different from wallet currency.
        :raises InsufficientBalance: not enough money in wallet.
        :raises ListingRemoved: listing has been removed from market.
        :raises NeedMobileConfirmation: market action requires confirmation.
        """

        # flow: same as in creating buy order

        if isinstance(obj, MarketListing):
            if obj.sold:
                raise ValueError("Listing is already sold")

            if obj.converted.currency is not self._currency:
                raise ValueError(
                    f"Currency of listing ({obj.converted.currency!r}) is "
                    f"different from wallet ({self._currency!r}) one"
                )

            listing_id = obj.id
            price = obj.converted.price
            fee = obj.converted.fee
            market_hash_name = obj.item.description.market_hash_name
            app = obj.item.description.app
        else:
            listing_id = obj

            if not all([app, market_hash_name, price]):
                raise ValueError("`app`, `market_hash_name` and `price` arguments must be provided")

        fee = fee or calc_market_listing_fee(price)
        data = {
            "sessionid": self._transport.session_id,
            "currency": self._currency.value,
            "subtotal": price,
            "fee": fee,
            "total": price + fee,
            "quantity": 1,
            "confirmation": confirmation_id,
        }

        try:
            r = await self._transport.request(
                "POST",
                MARKET_URL / f"buylisting/{listing_id}",
                data=data,
                headers={"Referer": str(MARKET_URL / f"listings/{app.id}/{market_hash_name}")},  # mandatory
                response_mode="json",
            )
        except TransportError as e:  # ugly
            if e.response:
                if e.response.status == 406:  # need confirmation
                    r = e.response
                elif e.response.status == 502:
                    if e.response.content:
                        if "listing may have been removed" in e.response.content["message"]:
                            raise ListingRemoved
                        else:
                            # there content tells us that somebody bought listing before us, lol
                            raise InsufficientBalance
                    else:
                        raise
                else:
                    raise
            else:
                raise

        rj: dict = r.content

        if rj.get("need_confirmation"):
            confirmation_id = int(rj["confirmation"]["confirmation_id"])

            if self._conf is None:
                raise NeedMobileConfirmation(confirmation_id)

            conf = await self._conf.get_confirmation(confirmation_id)
            await self._conf.allow_confirmation(conf)

            return await self.buy_market_listing(
                obj,
                price,
                market_hash_name,
                app,
                fee=fee,
                confirmation_id=confirmation_id,
            )

        rj: dict = rj["wallet_info"]

        EResultError.check_data(rj)

        return WalletInfo(
            balance=int(rj["wallet_balance"]),
            country=rj["wallet_country"],
            currency=Currency(rj["wallet_currency"]),
            currency_increment=int(rj["wallet_currency_increment"]),
            delayed_balance=int(rj["wallet_delayed_balance"]),
            fee=int(rj["wallet_fee"]),
            fee_base=int(rj["wallet_fee_base"]),
            fee_minimum=int(rj["wallet_fee_minimum"]),
            fee_percent=float(rj["wallet_fee_percent"]),
            market_minimum=int(rj["wallet_market_minimum"]),
            max_balance=int(rj["wallet_max_balance"]),
            publisher_fee_percent_default=float(rj["wallet_publisher_fee_percent_default"]),
            trade_max_balance=int(rj["wallet_trade_max_balance"]),
        )

    @classmethod
    def _parse_assets_for_history_listings(
        cls,
        data: dict[str, dict[str, dict[str, dict]]],
        item_descriptions_map: ItemDescriptionsMap,
        econ_item_map: dict[str, MarketHistoryListingItem],
    ):
        for app_id, app_data in data.items():
            for context_id, context_data in app_data.items():
                for a_data in context_data.values():
                    # because I don't know why in data `id` and `unowned_id` combinations and how that suppose to work
                    key_id = create_ident_code(a_data["id"], context_id, app_id)
                    key_unowned_id = create_ident_code(a_data["unowned_id"], context_id, app_id)
                    if key_id not in item_descriptions_map or key_unowned_id not in item_descriptions_map:
                        econ_item = MarketHistoryListingItem(
                            context_id=int(a_data["contextid"]),
                            asset_id=int(a_data["id"]),
                            unowned_id=int(a_data["unowned_id"]),
                            unowned_context_id=int(a_data["unowned_contextid"]),
                            rollback_new_asset_id=(
                                int(a_data["rollback_new_id"]) if "rollback_new_id" in a_data else None
                            ),
                            rollback_new_context_id=(
                                int(a_data["rollback_new_contextid"]) if "rollback_new_contextid" in a_data else None
                            ),
                            description=item_descriptions_map[
                                create_ident_code(
                                    a_data["instanceid"],
                                    a_data["classid"],
                                    app_id,
                                )
                            ],
                            properties=cls._parse_asset_properties(a_data),
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
                    values=ListingValues(
                        currency=Currency(int(l_data["currencyid"]) - 2000),
                        price=int(l_data["price"]),
                        fee=int(l_data["fee"]),
                        steam_fee=0,
                        publisher_fee=0,
                    ),
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
                    values=ListingValues(
                        currency=Currency(int(p_data["currencyid"]) - 2000),
                        price=0,
                        fee=0,
                        steam_fee=int(p_data["steam_fee"]),
                        publisher_fee=int(p_data["publisher_fee"]),
                    ),
                    received_currency=Currency(int(p_data["received_currencyid"]) - 2000),
                    paid_amount=int(p_data["paid_amount"]),
                    paid_fee=int(p_data["paid_fee"]),
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
                    time=datetime.fromtimestamp(e_data["time_event"]),
                    type=MarketHistoryEventType(e_data["event_type"]),
                )
            )

        return events

    async def get_my_market_history(
        self,
        *,
        start: int = 0,
        count: int = 100,
        # share mapping with iterator method
        _app_map: AppMap | None = None,
        _item_descriptions_map: ItemDescriptionsMap | None = None,
        _market_history_econ_items_map: dict[str, MarketHistoryListingItem] | None = None,
        _market_history_listings_map: dict[int, MarketHistoryListing] | None = None,
    ) -> UserMarketHistoryData:
        """
        Get market history of current user.

        .. note:: Pagination can be achieved by passing ``start`` arg.

        :param start: start index.
        :param count: listings per page.
        :return: list of ``MarketHistoryEvent``, total_count.
        :raises EResultError: ordinary reasons.
        :raises TransportError: arbitrary reasons.
        """

        # empty lists if session is expired
        r = await self._transport.request(
            "GET",
            MARKET_URL / "myhistory",
            params={"norender": 1, "start": start, "count": count},
            headers={"Referer": str(MARKET_URL)},
            response_mode="json",
        )
        rj: dict = r.content

        EResultError.check_data(rj)

        if not rj["total_count"] or not rj["assets"]:  # safe
            return [], 0

        _app_map = {} if _app_map is None else _app_map
        _item_descriptions_map = {} if _item_descriptions_map is None else _item_descriptions_map
        _market_history_econ_items_map = (
            {} if _market_history_econ_items_map is None else _market_history_econ_items_map
        )
        _market_history_listings_map = {} if _market_history_listings_map is None else _market_history_listings_map

        self._parse_descriptions_from_my_listings_or_market_history(rj, _item_descriptions_map, _app_map)
        self._parse_assets_for_history_listings(rj["assets"], _item_descriptions_map, _market_history_econ_items_map)
        self._parse_history_listings(rj, _market_history_econ_items_map, _market_history_listings_map)

        return self._parse_history_events(rj, _market_history_listings_map), rj["total_count"]

    async def my_market_history(
        self,
        *,
        start: int = 0,
        count: int = 100,
    ) -> AsyncGenerator[UserMarketHistoryData, None]:
        """
        Get market history of current user.
        Return async generator to paginate over history event pages.

        :param start: start index.
        :param count: listings per page.
        :return: `AsyncGenerator` that yields list of ``MarketHistoryEvent``, total_count.
        :raises EResultError: ordinary reasons.
        :raises TransportError: arbitrary reasons.
        """

        _app_map = {}
        _item_descriptions_map = {}
        _market_history_econ_items_map = {}
        _market_history_listings_map = {}

        more_listings = True
        while more_listings:
            # avoid excess destructuring
            history_data = await self.get_my_market_history(
                start=start,
                count=count,
                _app_map=_app_map,
                _item_descriptions_map=_item_descriptions_map,
                _market_history_econ_items_map=_market_history_econ_items_map,
                _market_history_listings_map=_market_history_listings_map,
            )
            start += count
            more_listings = history_data[1] > start

            yield history_data

    @overload
    async def get_price_history(self, obj: ItemDescription) -> list[PriceHistoryEntry]: ...

    @overload
    async def get_price_history(self, obj: str, app: App) -> list[PriceHistoryEntry]: ...

    async def get_price_history(self, obj: str | ItemDescription, app: App = None) -> list[PriceHistoryEntry]:
        """
        Get price history of item.
        Prices will be the *same currency as a wallet*.

        .. note:: This request is rate limited by `Steam`.

        .. seealso:: https://github.com/Revadike/InternalSteamWebAPI/wiki/Get-Market-Price-History.

        :param obj: ``ItemDescription`` or `market hash name`.
        :param app: `Steam` app.
        :return: list of ``PriceHistoryEntry``.
        :raises EResultError: ordinary reasons.
        :raises TransportError: arbitrary reasons.
        """

        if isinstance(obj, ItemDescription):
            name = obj.market_hash_name
            app = obj.app
        else:  # str
            name = obj

        try:
            r = await self._transport.request(
                "GET",
                MARKET_URL / "pricehistory",
                params={"appid": app.id, "market_hash_name": name},
                response_mode="json",
            )
        except TransportError as e:
            if e.response and e.response.status == 400:
                raise SessionExpired
            else:
                raise

        rj: dict = r.content

        EResultError.check_data(rj)

        return [
            PriceHistoryEntry(
                price=round(e_data[1] * 100),  # as in Steam chart
                price_raw=e_data[1],
                date=datetime.strptime(e_data[0].replace("+0", "+0000"), "%b %d %Y %H: %z"),
                daily_volume=int(e_data[2]),
            )
            for e_data in rj["prices"]
        ]

    # need rework
    async def get_market_availability_info(self) -> tuple[bool, datetime | None]:
        """
        Return market status of whether it is available or not.
        If possible "when"  market will be available will be returned also.

        .. seealso:: https://help.steampowered.com/en/faqs/view/451E-96B3-D194-50FC.
        """

        r = await self._transport.request(
            "GET",
            MARKET_URL,
            headers={"Referer": str(STEAM_URL.STORE)},
            response_mode="text",
        )
        rt = r.content

        available = True
        when: datetime | None = None

        if "The Market is unavailable for the following reason" in rt:  # language unsafe
            available = False

            if "dateCanUseMarket" in rt:
                when = datetime.strptime(
                    re.search(r"var dateCanUseMarket = new Date\(\"(?P<date>.+)\"\);", rt).group("date"),
                    "%a, %d %b %Y %H:%M:%S %z",
                )

        # in theory we can retrieve purchase history from https://store.steampowered.com/account/history/
        # and evaluate estimate market block time that must depends on last wallet deposit or app purchase
        # as at time of writing: last app purchase older than year and market still available

        return available, when

    # TODO get asset prices, also access token instead of api key
    # https://api.steampowered.com/ISteamEconomy/GetAssetPrices/v1/?key=<API KEY>&appid=...
