from typing import TYPE_CHECKING, overload, Literal
from dataclasses import asdict

from .exceptions import ApiError
from .models import (
    STEAM_URL,
    Game,
    GameType,
    EconItem,
    MarketListing,
    BuyOrder,
    SellOrderItem,
    MarketListingStatus,
)
from .utils import create_ident_code

if TYPE_CHECKING:
    from .client import SteamClient

__all__ = ("MarketMixin", "MARKET_URL")


MARKET_URL = STEAM_URL.COMMUNITY / "market/"


class MarketMixin:
    """
    Mixin with market related methods.
    Depends on `ConfirmationMixin`
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
        If `confirm` is True - return listing id of created and confirmed sell listing.
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
        headers = {"Referer": (self.profile_url / "inventory").human_repr()}
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
        headers = {"Referer": MARKET_URL}
        return self.session.post(MARKET_URL / f"removelisting/{listing_id}", data=data, headers=headers)

    # TODO fetch listings history (check steammarket page)

    async def fetch_my_listings(
        self, count=100
    ) -> tuple[tuple[MarketListing, ...], tuple[MarketListing, ...], tuple[BuyOrder, ...]]:
        """

        :param count:
        :return: tuples of active listings, listings to confirm, buy orders.
        """

        url = MARKET_URL / "mylistings/render/"
        params = {"norender": 1, "start": 0, "count": count}
        # pagination
        self
