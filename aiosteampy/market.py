from typing import TYPE_CHECKING, overload

from .exceptions import ApiError
from .models import STEAM_URL, Game, GameType, InventoryItem

if TYPE_CHECKING:
    from .client import SteamClient


class MarketMixin:
    __slots__ = ()

    async def place_sell_order(self: "SteamClient", assetid: int, game: GameType, price: float, *, confirm=True):
        """

        :param assetid:
        :param game:
        :param price: money that you wand to receive
        :param confirm: confirm order or not
        :return:
        """
        # TODO autoconfirm=True/False for optimizing confirm requests(can fetch many confirmations at once).
        #   inventory item arg, overload
        data = {
            "assetid": assetid,
            "sessionid": self.session_id,
            "contextid": game[1],
            "appid": game[0],
            "amount": 1,
            "price": int(price * 100),
        }
        headers = {"Referer": str(STEAM_URL.COMMUNITY / f"profiles/{self.steam_id}/inventory")}
        resp = await self.session.post(STEAM_URL.COMMUNITY / "market/sellitem/", data=data, headers=headers)
        resp_json = await resp.json()
        if not resp_json["success"]:
            raise ApiError("Failed to create sell order", resp_json)

        if resp_json.get("needs_email_confirmation"):
            raise ApiError("Creating sell order needs email confirmation.")
        elif resp_json.get("needs_mobile_confirmation") and confirm:
            await self.confirm_sell_listing(assetid)
