from typing import TYPE_CHECKING

from aiohttp import ClientResponseError

from .models import STEAM_URL, Game, GameType, ItemDescription, ItemTag, ItemClass, InventoryItem
from .exceptions import ApiError

if TYPE_CHECKING:
    from .client import SteamClient


class InventoryMixin:
    __slots__ = ()

    _inventories: dict[str, InventoryItem]  # hash(str((app_id:int, context_id:int)))
    # TODO maybe I need container class inventory, maybe I don't need this states at all.

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._inventories = {}

    def get_inventory(self: "SteamClient", game: GameType, *, count=5000):
        return self.get_user_inventory(self.steam_id, game, count=count)

    async def get_user_inventory(
        self: "SteamClient", steam_id: int, game: GameType, *, count=5000
    ) -> tuple[InventoryItem, ...]:
        inv_url = STEAM_URL.COMMUNITY / f"inventory/{steam_id}/"
        try:
            resp = await self.session.get(
                inv_url / f"{game[0]}/{game[1]}",
                params={"l": "english", "count": count},
                headers={"Referer": str(inv_url)},
            )
        except ClientResponseError as e:
            if e.status == 403:
                raise ApiError("User inventory is private.")
            else:
                raise

        resp_json: dict[str, list[dict] | int] = await resp.json()
        if not resp_json.get("success"):
            raise ApiError(f"Can't fetch inventory.", resp_json)

        return self._parse_items(resp_json, steam_id)

    @staticmethod
    def _find_d_id(actions: list[dict[str, str]]) -> int | None:
        for action in actions:
            if "Inspect" in action["name"]:
                return int(action["link"].split("%D")[1])

    @staticmethod
    def _find_game(description_data: dict[str, int], assets: list[dict[str, int | str]]) -> GameType:
        try:
            return Game(description_data["appid"])
        except ValueError:
            for asset in assets:
                if asset["classid"] == description_data["classid"]:
                    return asset["appid"], int(asset["contextid"])

    @classmethod
    def _parse_items(cls, data: dict[str, list[dict]], steam_id: int) -> tuple[InventoryItem, ...]:
        classes_map: dict[str, ItemClass] = {
            d_data["classid"]: ItemClass(
                game=cls._find_game(d_data, data["assets"]),
                name=d_data["name"],
                name_color=d_data["name_color"],
                market_name=d_data["market_name"],
                market_hash_name=d_data["market_hash_name"],
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
                d_id=cls._find_d_id(d_data["actions"]) if "actions" in d_data else None,
                tags=tuple(
                    ItemTag(
                        category=t_data["category"],
                        internal_name=t_data["internal_name"],
                        localized_category_name=t_data["localized_category_name"],
                        localized_tag_name=t_data["localized_tag_name"],
                        color=t_data.get("color"),
                    )
                    for t_data in d_data["tags"]
                ),
                descriptions=tuple(
                    ItemDescription(
                        value=de_data["value"],
                        color=de_data.get("color"),
                    )
                    for de_data in d_data["descriptions"]
                    if de_data["value"] != " "  # ha, surprise!
                ),
            )
            for d_data in data["descriptions"]
        }

        return tuple(
            InventoryItem(
                asset_id=int(asset_data["assetid"]),
                instance_id=int(asset_data["instanceid"]),
                owner_id=steam_id,
                class_=classes_map[asset_data["classid"]],
            )
            for asset_data in data["assets"]
        )
