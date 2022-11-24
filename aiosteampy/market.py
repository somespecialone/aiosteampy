from typing import TYPE_CHECKING, overload, Literal, TypeAlias, Type, Callable
from datetime import datetime
from math import floor

from aiohttp import ClientResponseError
from yarl import URL

from .exceptions import ApiError, SessionExpired
from .models import (
    EconItem,
    MyMarketListing,
    BuyOrder,
    ItemClass,
    MarketListingItem,
    MarketHistoryEvent,
    MarketHistoryListing,
    MarketHistoryListingItem,
    PriceHistoryEntry,
    MarketListing,
)
from .constants import STEAM_URL, GameType, MarketListingStatus, MarketHistoryEventType
from .utils import create_ident_code

if TYPE_CHECKING:
    from .client import SteamClient

__all__ = ("MarketMixin",)

MY_LISTINGS: TypeAlias = tuple[list[MyMarketListing], list[MyMarketListing], list[BuyOrder]]
PREDICATE: TypeAlias = Callable[[MarketHistoryEvent], bool]
PRICE_HISTORY_ENTRY_DATE_FORMAT = "%b %d %Y"


class MarketMixin:
    """
    Mixin with market related methods.

    Depends on :class:`aiosteampy.confirmation.ConfirmationMixin`,
    :class:`aiosteampy.public.SteamPublicMixin`.
    """

    __slots__ = ()

    @overload
    async def place_sell_listing(self, asset: EconItem, *, price: float) -> int:
        ...

    @overload
    async def place_sell_listing(self, asset: EconItem, *, price: float, confirm: Literal[False] = ...) -> None:
        ...

    @overload
    async def place_sell_listing(self, asset: EconItem, *, to_receive: float) -> int:
        ...

    @overload
    async def place_sell_listing(self, asset: EconItem, *, to_receive: float, confirm: Literal[False] = ...) -> None:
        ...

    @overload
    async def place_sell_listing(self, asset: int, game: GameType, *, price: float) -> int:
        ...

    @overload
    async def place_sell_listing(
        self, asset: int, game: GameType, *, price: float, confirm: Literal[False] = ...
    ) -> None:
        ...

    @overload
    async def place_sell_listing(self, asset: int, game: GameType, *, to_receive: float) -> int:
        ...

    @overload
    async def place_sell_listing(
        self, asset: int, game: GameType, *, to_receive: float, confirm: Literal[False] = ...
    ) -> None:
        ...

    async def place_sell_listing(
        self: "SteamClient",
        asset: EconItem | int,
        game: GameType = None,
        *,
        price: float = None,
        to_receive: float = None,
        confirm=True,
    ) -> int | None:
        """
        Create and place sell listing.
        If `confirm` is True - return listing id of created and confirmed sell listing,
        if this requires confirmation. If not - return None.
        Money should be only and only in account wallet currency.

        :param asset: `EconItem` that you want to list on market or asset id
        :param game: game of item
        :param price: money that buyer must pay
        :param to_receive: money that you wand to receive
        :param confirm: confirm listing or not if steam demands mobile confirmation
        :return: sell listing id or None
        :raises ApiError:
        """

        if isinstance(asset, EconItem):
            asset_id = asset.id
            game = asset.class_.game
        else:
            asset_id = asset

        if to_receive is None:
            to_receive = price * (1 - (self._steam_fee + self._publisher_fee))

        data = {
            "assetid": asset_id,
            "sessionid": self.session_id,
            "contextid": game[1],
            "appid": game[0],
            "amount": 1,
            "price": int(to_receive * 100),
        }
        headers = {"Referer": str(STEAM_URL.COMMUNITY / f"profiles/{self.steam_id}/inventory")}
        r = await self.session.post(STEAM_URL.MARKET / "sellitem/", data=data, headers=headers)
        rj: dict[str, ...] = await r.json()
        if not rj.get("success"):
            raise ApiError("Failed to place sell listing.", rj)

        if rj.get("needs_mobile_confirmation") and confirm:
            return await self.confirm_sell_listing(asset_id, game)

    def cancel_sell_listing(self: "SteamClient", obj: MyMarketListing | int):
        """
        Just cancel sell listing.

        :param obj: `MyMarketListing` or listing id
        """

        listing_id: int = obj.id if isinstance(obj, MyMarketListing) else obj
        data = {"sessionid": self.session_id}
        headers = {"Referer": str(STEAM_URL.MARKET)}
        return self.session.post(STEAM_URL.MARKET / f"removelisting/{listing_id}", data=data, headers=headers)

    @overload
    async def place_buy_order(self, obj: ItemClass, *, price: float, quantity: int) -> int:
        ...

    @overload
    async def place_buy_order(self, obj: str, game: GameType, *, price: float, quantity: int) -> int:
        ...

    async def place_buy_order(
        self: "SteamClient",
        obj: str | ItemClass,
        game: GameType = None,
        *,
        price: float,
        quantity: int,
    ) -> int:
        """
        Place buy order on market.

        :param obj: `ItemClass` or market hash name
        :param game: `Game` if `obj` is market hash name
        :param price: price of single item
        :param quantity: just quantity
        :return: buy order id
        :raises ApiError:
        """

        if isinstance(obj, ItemClass):
            name = obj.market_hash_name
            game = obj.game
        else:
            name = obj

        data = {
            "sessionid": self.session_id,
            "currency": self._wallet_currency.value,
            "appid": game[0],
            "market_hash_name": name,
            "price_total": int(price * quantity * 100),
            "quantity": quantity,
        }

        headers = {"Referer": str(STEAM_URL.MARKET / f"listings/{game[0]}/{name}")}
        r = await self.session.post(STEAM_URL.MARKET / "createbuyorder/", data=data, headers=headers)
        rj: dict[str, ...] = await r.json()
        if not rj.get("success"):
            raise ApiError("Failed to create buy order.", rj)

        return int(rj["buy_orderid"])

    async def cancel_buy_order(self: "SteamClient", order: int | BuyOrder):
        """
        Just cancel buy order.

        :param order: `BuyOrder` or buy order id
        :raises ApiError:
        """

        if isinstance(order, BuyOrder):
            order_id = order.id
        else:
            order_id = order

        data = {"sessionid": self.session_id, "buy_orderid": order_id}
        headers = {"Referer": str(STEAM_URL.MARKET)}
        r = await self.session.post(STEAM_URL.MARKET / "cancelbuyorder/", data=data, headers=headers)
        rj = await r.json()
        if not rj.get("success"):
            raise ApiError(f"Failed to cancel buy order [{order_id}].", rj)

    async def get_my_listings(self: "SteamClient", *, page_size=100) -> MY_LISTINGS:
        """
        Fetch users market listings.

        :param page_size: listings per page. Steam do not accept greater than 100
        :return: active listings, listings to confirm, buy orders
        :raises ApiError:
        :raises SessionExpired:
        """

        url = STEAM_URL.MARKET / "mylistings"
        params = {"norender": 1, "start": 0, "count": page_size}
        active = []
        to_confirm = []
        buy_orders = []
        classes_map = {}  # ident code: ... , shared classes within whole listings

        # pagination only for active listings. Don't know how to be with others
        more_listings = True
        while more_listings:
            data = await self._fetch_listings(url, params)
            if data["num_active_listings"] > data["pagesize"]:
                more_listings = True
                params["start"] += data["pagesize"]
                params["count"] = data["pagesize"]
            else:
                more_listings = False

            self._parse_item_classes_for_listings(data["assets"], classes_map)
            active.extend(self._parse_listings(data["listings"], classes_map))
            to_confirm.extend(self._parse_listings(data["listings_to_confirm"], classes_map))
            buy_orders.extend(self._parse_buy_orders(data["buy_orders"], classes_map))

        return active, to_confirm, buy_orders

    async def _fetch_listings(self: "SteamClient", url: URL, params: dict) -> dict[str, ...]:
        try:
            r = await self.session.get(url, params=params)
        except ClientResponseError as e:
            raise SessionExpired if e.status == 400 else e

        rj: dict[str, ...] = await r.json()
        if not rj.get("success"):
            raise ApiError("Failed to fetch user listings.", rj)

        return rj

    @classmethod
    def _parse_item_classes_for_listings(
        cls: Type["SteamClient"],
        assets: dict[str, dict[str, dict[str, dict[str, ...]]]],
        classes_map: dict[str, ItemClass],
    ):
        for app_id, app_data in assets.items():
            for context_id, context_data in app_data.items():
                for a_data in context_data.values():
                    key = create_ident_code(a_data["classid"], app_id)
                    if key not in classes_map:
                        classes_map[key] = cls._create_item_class_from_data(a_data, (a_data,))  # some trick

    def _parse_listings(
        self: "SteamClient",
        listings: list[dict[str, ...]],
        classes_map: dict[str, ItemClass],
    ) -> tuple[MyMarketListing, ...]:
        return tuple(
            MyMarketListing(
                id=int(l_data["listingid"]),
                price=l_data["price"] / 100,
                lister_steam_id=self.steam_id,
                time_created=datetime.fromtimestamp(l_data["time_created"]),
                item=MarketListingItem(
                    id=int(l_data["asset"]["id"]),
                    unowned_id=int(l_data["asset"]["unowned_id"]) if "unowned_id" in l_data["asset"] else None,
                    owner_id=self.steam_id,
                    market_id=int(l_data["listingid"]),
                    unowned_context_id=int(l_data["asset"]["unowned_contextid"])
                    if "unowned_contextid" in l_data["asset"]
                    else None,
                    class_=classes_map[create_ident_code(l_data["asset"]["classid"], l_data["asset"]["appid"])],
                    amount=int(l_data["asset"]["amount"]),
                ),
                status=MarketListingStatus(l_data["status"]),
                active=bool(l_data["active"]),
                item_expired=l_data["item_expired"],
                cancel_reason=l_data["cancel_reason"],
                time_finish_hold=l_data["time_finish_hold"],
            )
            for l_data in listings
        )

    @classmethod
    def _parse_buy_orders(
        cls: Type["SteamClient"],
        orders: list[dict[str, ...]],
        classes_map: dict[str, ItemClass],
    ) -> list[BuyOrder, ...]:
        orders_list = []
        for o_data in orders:
            class_ident_key = create_ident_code(o_data["description"]["classid"], o_data["description"]["appid"])
            if class_ident_key not in classes_map:
                classes_map[class_ident_key] = cls._create_item_class_from_data(
                    o_data["description"], (o_data["description"],)
                )  # same some trick
            orders_list.append(
                BuyOrder(
                    id=int(o_data["buy_orderid"]),
                    price=int(o_data["price"]) / 100,
                    item_class=classes_map[class_ident_key],
                    quantity=int(o_data["quantity"]),
                    quantity_remaining=int(o_data["quantity_remaining"]),
                )
            )

        return orders_list

    @overload
    async def buy_market_listing(
        self,
        listing: MarketListing,
    ) -> float:
        ...

    @overload
    async def buy_market_listing(
        self,
        listing: int,
        price: float,
        market_hash_name: str,
        game: GameType,
        *,
        fee: int = ...,
    ) -> float:
        ...

    async def buy_market_listing(
        self: "SteamClient",
        listing: int | MarketListing,
        price: float = None,
        market_hash_name: str = None,
        game: GameType = None,
        *,
        fee: float = None,
    ) -> float:
        """
        Buy item listing from market.
        Unfortunately, Steam requires referer header to buy item,
        so `market hash name` and `game` is mandatory args.

        .. note:: Make sure that listing converted currency is wallet currency!

        :param listing: id for listing itself (aka market id) or `MarketListing`
        :param price: price in `1.24` format, can be found on listing data in
            Steam under field `converted_price` divided by 100
        :param market_hash_name: as arg name
        :param game: as arg name&type
        :param fee: if fee of listing is different from default one,
            can be found on listing data in Steam under field `converted_fee` divided by 100.
            If you don't know what is this - then you definitely do not need it
        :return: wallet balance
        :raises ApiError: for regular reasons
        :raises ValueError:
        """

        if isinstance(listing, MarketListing):
            if listing.converted_currency is self.currency:
                raise ValueError(
                    f"Currency of listing [{listing.converted_currency}] is "
                    f"different from wallet [{self.currency}] one!"
                )

            listing_id = listing.id
            price = listing.converted_price
            fee = listing.converted_fee
            market_hash_name = listing.item.class_.market_hash_name
            game = listing.item.class_.game
        else:
            listing_id = listing

        price = int(price * 100)
        if fee is None:
            steam_fee = floor(price * self._steam_fee) or 1
            publ_fee = floor(price * self._publisher_fee) or 1
            fee = steam_fee + publ_fee
        else:
            fee = int(fee * 100)

        total = price + fee
        data = {
            "sessionid": self.session_id,
            "currency": self._wallet_currency.value,
            "subtotal": price,
            "fee": fee,
            "total": total,
            "quantity": 1,
        }
        headers = {"Referer": str(STEAM_URL.MARKET / f"listings/{game[0]}/{market_hash_name}")}
        r = await self.session.post(STEAM_URL.MARKET / f"buylisting/{listing_id}", data=data, headers=headers)
        rj: dict[str, dict[str, str]] = await r.json()
        if not rj.get("wallet_info", {}).get("success"):
            raise ApiError(
                f"Failed to buy listing [{listing_id}] of `{market_hash_name}` "
                f"for {total / 100} {self._wallet_currency.name}.",
                rj,
            )

        return int(rj["wallet_info"]["wallet_balance"]) / 100

    async def get_my_market_history(
        self: "SteamClient",
        *,
        predicate: PREDICATE = None,
        page_size=500,
    ) -> list[MarketHistoryEvent]:
        url = STEAM_URL.MARKET / "myhistory"
        params = {"norender": 1, "start": 0, "count": page_size}
        events = []
        classes_map = {}  # ident code: ... , shared classes within whole listings
        assets_map = {}  # ident code: ...
        listings_map = {}  # listings id / listing_purchase id

        more_listings = True
        while more_listings:
            data = await self._fetch_listings(url, params)
            if data["total_count"] > data["pagesize"]:
                more_listings = True
                params["start"] += data["pagesize"]
                params["count"] = data["pagesize"]
            else:
                more_listings = False

            self._parse_item_classes_for_listings(data["assets"], classes_map)
            self._parse_assets_for_history_listings(data["assets"], classes_map, assets_map)
            self._parse_history_listings(data, assets_map, listings_map)
            events.extend(self._parse_history_events(data, listings_map))

        return list(e for e in events if predicate(e)) if predicate else events

    @staticmethod
    def _parse_assets_for_history_listings(
        data: dict[str, dict[str, dict[str, dict[str, ...]]]],
        classes_map: dict[str, ItemClass],
        assets_map: dict[str, MarketHistoryListingItem],
    ):
        for app_id, app_data in data.items():
            for context_id, context_data in app_data.items():
                for a_data in context_data.values():
                    key = create_ident_code(a_data["id"], app_id, context_id)
                    if key not in assets_map:
                        assets_map[key] = MarketHistoryListingItem(
                            id=int(a_data["id"]),
                            class_=classes_map[create_ident_code(a_data["classid"], app_id)],
                            unowned_id=int(a_data["unowned_id"]),
                            unowned_context_id=int(a_data["unowned_contextid"]),
                            rollback_new_id=int(a_data["rollback_new_id"]) if "rollback_new_id" in a_data else None,
                            rollback_new_context_id=int(a_data["rollback_new_contextid"])
                            if "rollback_new_contextid" in a_data
                            else None,
                        )

    @staticmethod
    def _parse_history_listings(
        data: dict[str, dict[str, dict[str, ...]]],
        assets_map: dict[str, MarketHistoryListingItem],
        listings_map: dict[str, MarketHistoryListing],
    ):
        for l_id, l_data in data["listings"].items():
            if l_id not in listings_map:
                listings_map[l_id] = MarketHistoryListing(
                    id=int(l_data["listingid"]),
                    price=int(l_data["price"]) / 100,
                    item=assets_map[
                        create_ident_code(
                            l_data["asset"]["id"],
                            l_data["asset"]["appid"],
                            l_data["asset"]["contextid"],
                        )
                    ],
                    original_price=int(l_data["original_price"]) / 100,
                    cancel_reason=l_data.get("cancel_reason"),
                )

        for p_id, p_data in data["purchases"].items():
            if p_id not in listings_map:
                listing = MarketHistoryListing(
                    id=int(p_data["listingid"]),
                    item=assets_map[
                        create_ident_code(
                            p_data["asset"]["id"],
                            p_data["asset"]["appid"],
                            p_data["asset"]["contextid"],
                        )
                    ],
                    purchase_id=int(p_data["purchaseid"]),
                    steamid_purchaser=int(p_data["steamid_purchaser"]),
                    received_amount=int(p_data["received_amount"]) / 100,
                )
                listing.item.new_id = int(p_data["asset"]["new_id"])
                listing.item.new_context_id = int(p_data["asset"]["new_contextid"])

                listings_map[p_id] = listing

    @staticmethod
    def _parse_history_events(
        data: dict[str, list[dict[str, ...]] | dict[str, dict[str, ...]]],
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
    async def fetch_price_history(self, obj: EconItem) -> list[PriceHistoryEntry]:
        ...

    @overload
    async def fetch_price_history(self, obj: ItemClass) -> list[PriceHistoryEntry]:
        ...

    @overload
    async def fetch_price_history(self, obj: str, app_id: int) -> list[PriceHistoryEntry]:
        ...

    async def fetch_price_history(self: "SteamClient", obj: str, app_id: int = None) -> list[PriceHistoryEntry]:
        """
        Fetch price history.
        Prices always will be same currency as a wallet.

        .. seealso:: https://github.com/Revadike/InternalSteamWebAPI/wiki/Get-Market-Price-History

        .. warning:: This request is rate limited by Steam.

        :param obj: `EconItem` or `ItemClass` or market hash name
        :param app_id:
        :return: list of `PriceHistoryEntry`
        :raises ApiError:
        """

        if isinstance(obj, EconItem):
            name = obj.class_.market_hash_name
            app_id = obj.class_.game.app_id
        elif isinstance(obj, ItemClass):
            name = obj.market_hash_name
            app_id = obj.game.app_id
        else:  # str
            name = obj

        params = {"appid": app_id, "market_hash_name": name}
        r = await self.session.get(STEAM_URL.MARKET / "pricehistory", params=params)
        rj: dict[str, list[list]] = await r.json()
        if not rj.get("success"):
            raise ApiError(f"Failed to fetch `{name}` price history.", rj)

        return [
            PriceHistoryEntry(
                date=datetime.strptime(e_data[0], PRICE_HISTORY_ENTRY_DATE_FORMAT),
                price=e_data[1],
                daily_volume=int(e_data[2]),
            )
            for e_data in rj["prices"]
        ]
