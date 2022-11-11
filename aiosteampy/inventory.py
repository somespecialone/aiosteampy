from typing import TYPE_CHECKING

from aiohttp import ClientResponseError

from .models import STEAM_URL, Game, GameType, ItemDescription, ItemTag, ItemClass, EconItem, ItemAction
from .exceptions import ApiError

if TYPE_CHECKING:
    from .client import SteamClient

__all__ = ("InventoryMixin",)

INV_COUNT = 2000  # steam new limit rule
DEF_ITER = ()


# TODO get inv from there https://steamcommunity.com/profiles/:steamid/inventory/json/:appid/:contextid
class InventoryMixin:
    """
    Mixin with steam inventory related methods.
    """

    __slots__ = ()

    def get_inventory(self: "SteamClient", game: GameType, *, page_size=INV_COUNT):
        return self.get_user_inventory(self.steam_id, game, page_size=page_size)

    async def get_user_inventory(
        self: "SteamClient", steam_id: int, game: GameType, *, page_size=INV_COUNT
    ) -> tuple[EconItem, ...]:
        inv_url = STEAM_URL.COMMUNITY / f"inventory/{steam_id}/"
        params = {"l": "english", "count": page_size}
        headers = {"Referer": inv_url.human_repr()}
        try:
            r = await self.session.get(inv_url / f"{game[0]}/{game[1]}", params=params, headers=headers)
        except ClientResponseError as e:
            if e.status == 403:
                raise ApiError("User inventory is private.")
            else:
                raise

        # TODO pagination
        rj: dict[str, list[dict] | int] = await r.json()
        if not rj.get("success"):
            raise ApiError(f"Can't fetch inventory.", rj)

        return self._parse_items(rj, steam_id)

    @staticmethod
    def _find_game(description_data: dict[str, int], assets: list[dict[str, int | str]]) -> GameType:
        try:
            return Game(description_data["appid"])
        except ValueError:
            for asset in assets:
                if asset["classid"] == description_data["classid"]:
                    return asset["appid"], int(asset["contextid"])

    @classmethod
    def _parse_items(cls, data: dict[str, list[dict]], steam_id: int) -> tuple[EconItem, ...]:
        classes_map: dict[str, ItemClass] = {
            d_data["classid"]: ItemClass(
                id=int(d_data["classid"]),
                instance_id=int(d_data["instanceid"]),
                game=cls._find_game(d_data, data["assets"]),
                name=d_data["name"],
                market_name=d_data["market_name"],
                market_hash_name=d_data["market_hash_name"],
                name_color=d_data["name_color"] or None,
                background_color=d_data.get("name_color") or None,
                type=d_data["type"] or None,
                icon=d_data["icon_url"],
                icon_large=d_data.get("icon_url_large"),
                commodity=bool(d_data["commodity"]),
                tradable=bool(d_data["tradable"]),
                marketable=bool(d_data["marketable"]),
                market_tradable_restriction=d_data.get("market_tradable_restriction"),
                market_buy_country_restriction=d_data.get("market_buy_country_restriction"),
                market_fee_app=d_data.get("market_fee_app"),
                market_marketable_restriction=d_data.get("market_marketable_restriction"),
                actions=tuple(ItemAction(a_data["link"], a_data["name"]) for a_data in d_data.get("actions", DEF_ITER)),
                market_actions=tuple(
                    ItemAction(a_data["link"], a_data["name"]) for a_data in d_data.get("market_actions", DEF_ITER)
                ),
                owner_actions=tuple(
                    ItemAction(a_data["link"], a_data["name"]) for a_data in d_data.get("owner_actions", DEF_ITER)
                ),
                tags=tuple(
                    ItemTag(
                        category=t_data["category"],
                        internal_name=t_data["internal_name"],
                        localized_category_name=t_data["localized_category_name"],
                        localized_tag_name=t_data["localized_tag_name"],
                        color=t_data.get("color"),
                    )
                    for t_data in d_data.get("tags", DEF_ITER)
                ),
                descriptions=tuple(
                    ItemDescription(
                        value=de_data["value"],
                        color=de_data.get("color"),
                    )
                    for de_data in d_data.get("descriptions", DEF_ITER)
                    if de_data["value"] != " "  # ha, surprise!
                ),
                fraud_warnings=tuple(d_data.get("fraudwarnings", DEF_ITER)),
            )
            for d_data in data["descriptions"]
        }

        return tuple(
            EconItem(
                id=int(asset_data["assetid"]),
                owner_id=steam_id,
                class_=classes_map[asset_data["classid"]],
                amount=int(asset_data["amount"]),
            )
            for asset_data in data["assets"]
        )
