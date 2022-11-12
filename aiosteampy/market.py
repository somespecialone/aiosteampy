from typing import TYPE_CHECKING, overload, Literal, TypeAlias, Type
from datetime import datetime

from aiohttp import ClientResponseError
from yarl import URL

from .exceptions import ApiError, SessionExpired
from .models import (
    STEAM_URL,
    Game,
    GameType,
    EconItem,
    MarketListing,
    BuyOrder,
    ItemClass,
    ItemAction,
    ItemTag,
    ItemDescription,
    MarketListingItem,
    MarketListingStatus,
    Currency,
)
from .utils import create_ident_code

if TYPE_CHECKING:
    from .client import SteamClient

__all__ = ("MarketMixin", "MARKET_URL")

MARKET_URL = STEAM_URL.COMMUNITY / "market/"
MY_LISTINGS: TypeAlias = tuple[list[MarketListing], list[MarketListing], list[BuyOrder]]


class MarketMixin:
    """
    Mixin with market related methods.
    Depends on `ConfirmationMixin`, `InventoryMixin`
    """

    __slots__ = ()

    # TODO check if I can check that required mixins in MRO or something near

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
        headers = {"Referer": str(self.profile_url / "inventory")}
        r = await self.session.post(MARKET_URL / "sellitem/", data=data, headers=headers)
        rj: dict[str, ...] = await r.json()
        if not rj.get("success"):
            raise ApiError("Failed to place sell listing", rj)

        if rj.get("needs_email_confirmation"):
            raise ApiError("Creating sell listing needs email confirmation.")
        elif rj.get("needs_mobile_confirmation") and confirm:
            return await self.confirm_sell_listing(asset_id, game)

    def cancel_sell_listing(self: "SteamClient", obj: MarketListing | int):
        """
        Just cancel sell listing.

        :param obj: `MarketListing` or listing id
        """

        listing_id: int = obj.id if isinstance(obj, MarketListing) else obj
        data = {"sessionid": self.session_id}
        headers = {"Referer": str(MARKET_URL)}
        return self.session.post(MARKET_URL / f"removelisting/{listing_id}", data=data, headers=headers)

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
            name = ItemClass.market_hash_name
            game = ItemClass.game
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

        headers = {"Referer": str(MARKET_URL / f"listings/{game[0]}/{name}")}
        r = await self.session.post(MARKET_URL / "createbuyorder/", data=data, headers=headers)
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
        headers = {"Referer": str(MARKET_URL)}
        r = await self.session.post(MARKET_URL / "cancelbuyorder/", data=data, headers=headers)
        rj = await r.json()
        if not rj.get("success"):
            raise ApiError(f"Failed to cancel buy order [{order_id}].", rj)

    # TODO fetch listings history (check steammarket page)
    #  orders activity https://steamcommunity.com/market/itemordersactivity?country=RU&language=ukrainian&currency=5&item_nameid=176321160&two_factor=0
    #  orders hist https://steamcommunity.com/market/itemordershistogram?country=RU&language=ukrainian&currency=5&item_nameid=176321160&two_factor=0

    async def get_my_listings(self: "SteamClient", *, page_size=100) -> MY_LISTINGS:
        """
        Fetch listings.

        :param page_size: listings per page. Steam do not accept greater than 100
        :return: tuples of active listings, listings to confirm, buy orders
        :raises ApiError:
        :raises SessionExpired:
        """

        url = MARKET_URL / "mylistings"
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
    ) -> tuple[MarketListing, ...]:
        return tuple(
            MarketListing(
                id=int(l_data["listingid"]),
                price=l_data["price"] / 100,
                currency=Currency(int(l_data["currencyid"][-1:])),
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
        classes_map: dict[str],
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
                    currency=Currency(o_data["wallet_currency"]),
                    item_class=classes_map[class_ident_key],
                    quantity=int(o_data["quantity"]),
                    quantity_remaining=int(o_data["quantity_remaining"]),
                )
            )

        return orders_list
