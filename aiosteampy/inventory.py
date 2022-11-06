from typing import overload

from aiohttp import ClientSession, ClientResponseError

from .models import STEAM_URL, Game, ItemDescription, ItemTag, ItemClass, InventoryItem
from .exceptions import ApiError


class InventoryMixin:
    __slots__ = ()

    session: ClientSession

    username: str
    steam_id: int
    trade_token: str

    _password: str
    _shared_secret: str
    _identity_secret: str
    _api_key: str

    @overload
    async def get_inventory(self, game: Game, *, count=...) -> tuple[InventoryItem, ...]:
        ...

    @overload
    async def get_inventory(self, app_id: int, context_id: int, *, count=...) -> tuple[InventoryItem, ...]:
        ...

    def get_inventory(self, game=None, context_id=None, *, count=5000):
        app_id = game
        if type(game) is Game:
            app_id = game.app_id
            context_id = game.context_id
        return self.get_user_inventory(self.steam_id, app_id, context_id, count=count)

    @overload
    async def get_user_inventory(self, steam_id: int, game: Game, *, count=...) -> tuple[InventoryItem, ...]:
        ...

    @overload
    async def get_user_inventory(
        self, steam_id: int, app_id: int, context_id: int, *, count=...
    ) -> tuple[InventoryItem, ...]:
        ...

    async def get_user_inventory(self, steam_id, game=None, context_id=None, *, count=5000):
        app_id = game
        if type(game) is Game:
            app_id = game.app_id
            context_id = game.context_id

        inv_url = STEAM_URL.COMMUNITY / f"inventory/{steam_id}/"
        url = (inv_url / f"{app_id}/{context_id}").with_query({"l": "english", "count": count})
        try:
            resp = await self.session.get(url, headers={"Referer": str(inv_url)})
        except ClientResponseError as e:
            if e.status == 403:
                raise ApiError("User inventory is private.")
            else:
                raise

        resp_json: dict[str, list[dict] | int] = await resp.json()
        if not resp_json.get("success"):
            raise ApiError(f"Can't fetch inventory. Resp: [{resp_json}]")

        return self._parse_items(resp_json, steam_id)

    @staticmethod
    def _find_d_id(actions: list[dict[str, str]]) -> int | None:
        for action in actions:
            if "Inspect" in action["name"]:
                return int(action["link"].split("%D")[1])

    @classmethod
    def _parse_items(cls, data: dict[str, list[dict]], steam_id: int) -> tuple[InventoryItem, ...]:
        classes_map: dict[str, ItemClass] = {
            d_data["classid"]: ItemClass(
                game=Game(d_data["appid"]),
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
                d_id=cls._find_d_id(d_data["actions"]),
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
                    if de_data["value"]
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
