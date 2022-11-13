from typing import TYPE_CHECKING, Callable, TypeAlias

from aiohttp import ClientResponseError
from yarl import URL

from .models import STEAM_URL, Game, GameType, ItemDescription, ItemTag, ItemClass, EconItem, ItemAction
from .exceptions import ApiError, SessionExpired

if TYPE_CHECKING:
    from .client import SteamClient

__all__ = ("InventoryMixin", "INVENTORY_URL")

INV_PAGE_SIZE = 2000  # steam new limit rule
INVENTORY_URL = STEAM_URL.COMMUNITY / "inventory"
PREDICATE: TypeAlias = Callable[[EconItem], bool]


class InventoryMixin:
    """
    Mixin with steam inventory related methods.
    """

    __slots__ = ()

    def get_inventory(
        self: "SteamClient",
        game: GameType,
        *,
        predicate: PREDICATE = None,
        page_size=INV_PAGE_SIZE,
    ):
        """Fetches self inventory. Shorthand for `get_user_inventory(self.steam_id, ...)`."""

        return self.get_user_inventory(self.steam_id, game, predicate=predicate, page_size=page_size)

    async def get_user_inventory(
        self: "SteamClient",
        steam_id: int,
        game: GameType,
        *,
        predicate: PREDICATE = None,
        page_size=INV_PAGE_SIZE,
    ) -> list[EconItem]:
        """
        Fetches inventory of user.

        :param steam_id: steamid64 of user
        :param game: just Steam Game
        :param page_size: max items on page. Current Steam limit 2000
        :param predicate: callable with single arg `EconItem`, must return bool
        :return: tuple of `EconItem`
        :raises ApiError: if response data `success` is False or user inventory is private
        :raises SessionExpired: if auth session has been expired
        """

        inv_url = INVENTORY_URL / f"{steam_id}/"
        params = {"l": self.language, "count": page_size}
        headers = {"Referer": str(inv_url)}
        url = inv_url / f"{game[0]}/{game[1]}"

        classes_map = {}  # shared classes within whole game context inventory
        items = []
        more_items = True
        last_assetid = None
        while more_items:
            params_pag = {**params, "start_assetid": last_assetid} if last_assetid else params
            data = await self._fetch_inventory(url, params_pag, headers, steam_id)
            more_items = data.get("more_items", False)
            if more_items:
                last_assetid = data.get("last_assetid")

            items.extend(self._parse_items(data, steam_id, classes_map))

        return list(i for i in items if predicate(i)) if predicate else items

    async def _fetch_inventory(
        self: "SteamClient",
        url: URL,
        params: dict,
        headers: dict,
        steam_id: int,
    ) -> dict[str, list[dict] | int]:
        try:
            r = await self.session.get(url, params=params, headers=headers)
        except ClientResponseError as e:
            if e.status == 403:  # self inventory can't be private
                raise SessionExpired if self.steam_id == steam_id else ApiError("User inventory is private.", str(url))
            raise

        rj: dict[str, list[dict] | int] = await r.json()
        if not rj.get("success"):
            raise ApiError(f"Can't fetch inventory.", rj)

        return rj

    @staticmethod
    def _find_game(description_data: dict[str, int], assets: list[dict[str, int | str]]) -> GameType:
        try:
            return Game(description_data["appid"])
        except ValueError:
            for asset in assets:
                if asset["classid"] == description_data["classid"]:
                    return asset["appid"], int(asset["contextid"])

    @classmethod
    def _parse_items(
        cls,
        data: dict[str, list[dict]],
        steam_id: int,
        classes_map: dict[str, ItemClass],
    ) -> tuple[EconItem, ...]:
        for d_data in data["descriptions"]:
            key = d_data["classid"]
            if key not in classes_map:
                classes_map[key] = cls._create_item_class_from_data(d_data, data["assets"])

        return tuple(
            EconItem(
                id=int(asset_data["assetid"]),
                owner_id=steam_id,
                class_=classes_map[asset_data["classid"]],
                amount=int(asset_data["amount"]),
            )
            for asset_data in data["assets"]
        )

    @classmethod
    def _create_item_class_from_data(cls, data: dict, assets: list[dict[str, int | str]]) -> ItemClass:
        return ItemClass(
            id=int(data["classid"]),
            instance_id=int(data["instanceid"]),
            game=cls._find_game(data, assets),
            name=data["name"],
            market_name=data["market_name"],
            market_hash_name=data["market_hash_name"],
            name_color=data["name_color"] or None,
            background_color=data.get("name_color") or None,
            type=data["type"] or None,
            icon=data["icon_url"],
            icon_large=data.get("icon_url_large"),
            commodity=bool(data["commodity"]),
            tradable=bool(data["tradable"]),
            marketable=bool(data["marketable"]),
            market_tradable_restriction=data.get("market_tradable_restriction"),
            market_buy_country_restriction=data.get("market_buy_country_restriction"),
            market_fee_app=data.get("market_fee_app"),
            market_marketable_restriction=data.get("market_marketable_restriction"),
            actions=tuple(ItemAction(a_data["link"], a_data["name"]) for a_data in data.get("actions", ())),
            market_actions=tuple(
                ItemAction(a_data["link"], a_data["name"]) for a_data in data.get("market_actions", ())
            ),
            owner_actions=tuple(ItemAction(a_data["link"], a_data["name"]) for a_data in data.get("owner_actions", ())),
            tags=tuple(
                ItemTag(
                    category=t_data["category"],
                    internal_name=t_data["internal_name"],
                    localized_category_name=t_data["localized_category_name"],
                    localized_tag_name=t_data["localized_tag_name"],
                    color=t_data.get("color"),
                )
                for t_data in data.get("tags", ())
            ),
            descriptions=tuple(
                ItemDescription(
                    value=de_data["value"],
                    color=de_data.get("color"),
                )
                for de_data in data.get("descriptions", ())
                if de_data["value"] != " "  # ha, surprise!
            ),
            fraud_warnings=tuple(data.get("fraudwarnings", ())),
        )
