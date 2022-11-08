from typing import TYPE_CHECKING, overload

from .exceptions import ApiError
from .models import STEAM_URL, Game, GameType, InventoryItem

if TYPE_CHECKING:
    from .client import SteamClient


class MarketMixin:
    __slots__ = ()

    @overload
    async def place_sell_order(self, asset: InventoryItem, *, price: float, confirm: bool = ...):
        ...

    @overload
    async def place_sell_order(self, asset: InventoryItem, *, to_receive: float, confirm: bool = ...):
        ...

    @overload
    async def place_sell_order(self, asset: int, game: GameType, *, price: float, confirm: bool = ...):
        ...

    @overload
    async def place_sell_order(self, asset: int, game: GameType, *, to_receive: float, confirm: bool = ...):
        ...

    async def place_sell_order(
        self: "SteamClient",
        asset,
        game: GameType = None,
        *,
        price=None,
        to_receive=None,
        confirm=True,
    ):
        """

        :param asset:
        :param game:
        :param price: money that buyer must pay
        :param to_receive: money that you wand to receive
        :param confirm: confirm order or not
        :return:
        """
        # TODO autoconfirm=True/False for optimizing confirm requests(can fetch many confirmations at once).
        #   inventory item arg, overload

        if isinstance(asset, InventoryItem):
            asset_id = asset.asset_id
            game = asset.class_.game
        else:
            asset_id = asset

        to_receive = to_receive if to_receive is not None else price - (price * (self._steam_fee + self._publisher_fee))

        data = {
            "assetid": asset_id,
            "sessionid": self.session_id,
            "contextid": game[1],
            "appid": game[0],
            "amount": 1,
            "price": int(to_receive * 100),
        }
        headers = {"Referer": (self.profile_url / "inventory").human_repr()}
        resp = await self.session.post(STEAM_URL.COMMUNITY / "market/sellitem/", data=data, headers=headers)
        resp_json = await resp.json()
        if not resp_json["success"]:
            raise ApiError("Failed to create sell order", resp_json)

        if resp_json.get("needs_email_confirmation"):
            raise ApiError("Creating sell order needs email confirmation.")
        elif resp_json.get("needs_mobile_confirmation") and confirm:
            await self.confirm_sell_listing(asset_id)
