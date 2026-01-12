from contextlib import suppress
from collections.abc import AsyncGenerator
from typing import overload, Callable


from ...types import AppMap, ItemDescriptionsMap
from ...id import SteamID
from ...app import App, AppContext
from ...constants import Language, STEAM_URL, EResult
from ...exceptions import EResultError, SteamError
from ...transport import BaseSteamTransport, TransportError
from ...utils import create_ident_code
from ...models import EconItem, AssetProperty, AssetAccessory

from .._common import EconMixin

# Steam current limit
INV_COUNT = 2000

InventoryItemData = tuple[list[EconItem], int, int | None]  # items, total count, last asset id for pagination

INVENTORY_URL = STEAM_URL.COMMUNITY / "inventory"


class InventoryPublicComponent(EconMixin):
    """Component with public `Steam Inventory` methods. Available without authentication."""

    __slots__ = ("_transport", "_language")

    def __init__(
        self,
        transport: BaseSteamTransport,
        language: Language = Language.ENGLISH,
    ):
        self._transport = transport
        self._language = language

    @property
    def transport(self) -> BaseSteamTransport:
        return self._transport

    @property
    def language(self) -> Language:
        return self._language

    @classmethod
    def _parse_inventory(
        cls,
        data: dict[str, list[dict]],
        owner_id: SteamID,
        item_descriptions_map: ItemDescriptionsMap,
        app_map: AppMap,
    ) -> list[EconItem]:
        for d_data in data["descriptions"]:
            key = create_ident_code(d_data["instanceid"], d_data["classid"], d_data["appid"])
            if key not in item_descriptions_map:
                item_descriptions_map[key] = cls._create_item_descr(d_data, app_map)

        properties_map: dict[str, tuple[AssetProperty, ...]] = {}
        accessories_map: dict[str, tuple[AssetAccessory, ...]] = {}
        for properties_data in data.get("asset_properties", ()):
            properties_map[properties_data["assetid"]] = cls._parse_asset_properties(properties_data)
            accessories_map[properties_data["assetid"]] = cls._parse_asset_accessories(properties_data)

        return [
            EconItem(
                context_id=int(a_data["contextid"]),
                asset_id=int(a_data["assetid"]),
                owner_id=owner_id,
                amount=int(a_data["amount"]),
                description=item_descriptions_map[
                    create_ident_code(a_data["instanceid"], a_data["classid"], a_data["appid"])
                ],
                properties=properties_map.get(a_data["assetid"], ()),
                accessories=accessories_map.get(a_data["assetid"], ()),
            )
            for a_data in data["assets"]
        ]

    async def get_user_inventory(
        self,
        user_id: SteamID,
        app_ctx: AppContext,
        *,
        start_asset_id: int | None = None,
        count: int = INV_COUNT,
        _app_map: AppMap | None = None,
        _item_descriptions_map: ItemDescriptionsMap | None = None,
    ) -> InventoryItemData:
        """
        Get `user` inventory.

        .. note:: Pagination can be achieved by passing ``start_asset_id`` arg.

        :param user_id: ``SteamID`` of user which inventory is requested.
        :param app_ctx: ``AppContext`` of requested inventory.
        :param start_asset_id: for partial inventory fetch.
        :param count: page size.
        :return: list of ``EconItem``, total count of items in inventory, `last asset id` of the list.
        :raises SteamError: inventory is private.
        :raises EResultError: ordinary reasons.
        :raises TransportError: arbitrary reasons.
        """

        inv_url = INVENTORY_URL / f"{user_id.id64}/"
        params = {
            "l": self._language.value,
            "count": count,
            "raw_asset_properties": 1,  # as browser + save some network traffic
            "preserve_bbcode": 1,  # ?
        }
        if start_asset_id:
            params["start_assetid"] = start_asset_id

        headers = {"Referer": str(inv_url)}

        try:
            r = await self.transport.request(
                "GET",
                inv_url / f"{app_ctx.app.id}/{app_ctx.context_id}",
                params=params,
                headers=headers,
                response_mode="json",
            )

        except TransportError as e:
            if e.response and e.response.status == 403:
                # https://github.com/DoctorMcKay/node-steamcommunity/blob/d3e90f6fd3bea65b1ebc1bdaec754f99dcc8ddb3/components/users.js#L603
                raise SteamError("Steam user inventory is private") from e
            else:
                raise

        rj: dict = r.content

        EResultError.check_data(rj)

        total_count: int = rj["total_inventory_count"]
        last_asset_id = int(rj["last_assetid"]) if "last_assetid" in rj else None

        if "descriptions" not in rj:  # for old reasons, but let it be
            return [], total_count, last_asset_id

        _app_map = {} if _app_map is None else _app_map
        _item_descriptions_map = {} if _item_descriptions_map is None else _item_descriptions_map

        _app_map[app_ctx.app.id] = app_ctx.app  # no need to extract apps from data, we can share passed one

        items = self._parse_inventory(rj, user_id, _item_descriptions_map, _app_map)

        return items, total_count, last_asset_id

    async def user_inventory(
        self,
        user_id: SteamID,
        app_ctx: AppContext,
        *,
        start_asset_id: int | None = None,
        count: int = INV_COUNT,
    ) -> AsyncGenerator[InventoryItemData, None]:
        """
        Get async iterator of user inventory pages.

        :param user_id: ``SteamID`` of user which inventory is requested.
        :param app_ctx: ``AppContext`` of requested inventory.
        :param start_asset_id: for partial inventory fetch.
        :param count: page size.
        :return: ``AsyncGenerator`` that yields list of ``EconItem``, total count of items in inventory,
            `last asset id` of the list.
        :raises SteamError: inventory is private.
        :raises EResultError: ordinary reasons.
        :raises TransportError: arbitrary reasons.
        """

        _item_descriptions_map = {}  # shared descriptions instances across calls

        more_items = True
        while more_items:
            # browser does the first request with count=75,
            # receiving data with last_assetid if there are more items (and no assets for some apps, ex. CS2)
            # avoid excess destructuring
            inventory_data = await self.get_user_inventory(
                user_id,
                app_ctx,
                start_asset_id=start_asset_id,
                count=count,
                _item_descriptions_map=_item_descriptions_map,
            )
            start_asset_id = inventory_data[2]
            more_items = bool(inventory_data[2])

            yield inventory_data

    @overload
    async def get_user_inventory_item(
        self,
        user_id: SteamID,
        app_ctx: AppContext,
        obj: int,
    ) -> EconItem | None: ...

    @overload
    async def get_user_inventory_item(
        self,
        user_id: SteamID,
        app_ctx: AppContext,
        obj: Callable[[EconItem], bool],
    ) -> EconItem | None: ...

    # unfortunately, option with start_asset_id as asset_id does not work
    async def get_user_inventory_item(
        self,
        user_id: SteamID,
        app_ctx: AppContext,
        obj: int | Callable[[EconItem], bool],
    ) -> EconItem | None:
        """
        Fetch and iterate over inventory item pages of user until find one that satisfies passed arguments.

        :param user_id: ``SteamID`` of user which inventory is requested.
        :param app_ctx: ``AppContext`` of requested inventory.
        :param obj: `asset id` or `predicate` function.
        :return: ``EconItem`` or ``None`` if nothing found.
        :raises SteamError: inventory is private.
        :raises EResultError: ordinary reasons.
        :raises TransportError: arbitrary reasons.
        """

        if callable(obj):
            predicate = obj
        else:

            def predicate(i: EconItem):
                return i.asset_id == obj

        async for data in self.user_inventory(user_id, app_ctx):
            with suppress(StopIteration):
                return next(filter(predicate, data[0]))
