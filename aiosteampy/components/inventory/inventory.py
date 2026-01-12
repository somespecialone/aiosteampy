from collections.abc import AsyncGenerator
from typing import overload, Callable


from ...constants import Language
from ...app import App, AppContext
from ...transport import BaseSteamTransport
from ...types import AppMap, ItemDescriptionsMap, CORO
from ...id import SteamID
from ...exceptions import SteamError, SessionExpired
from ...models import EconItem

from .public import INV_COUNT, InventoryItemData, InventoryPublicComponent


class InventoryComponent(InventoryPublicComponent):
    """Component responsible for working with current user inventory."""

    __slots__ = ("_steam_id",)

    def __init__(
        self,
        steam_id: SteamID,
        transport: BaseSteamTransport,
        language: Language = Language.ENGLISH,
    ):
        super().__init__(transport, language)

        self._steam_id = steam_id

    @property
    def steam_id(self) -> SteamID:
        return self._steam_id

    async def get_inventory(
        self,
        app_ctx: AppContext,
        *,
        start_asset_id: int | None = None,
        count: int = INV_COUNT,
        _app_map: AppMap | None = None,
        _item_descriptions_map: ItemDescriptionsMap | None = None,
    ) -> InventoryItemData:
        """
        Get current authenticated user inventory.

        .. note:: Pagination can be achieved by passing ``start_asset_id`` arg.

        :param user_id: ``SteamID`` of user which inventory is requested.
        :param app_ctx: ``AppContext`` of requested inventory.
        :param start_asset_id: for partial inventory fetch.
        :param count: page size.
        :return: list of ``EconItem``, total count of items in inventory, `last asset id` of the list.
        :raises SteamError: inventory is private.
        :raises EResultError: ordinary reasons.
        :raises TransportError: arbitrary reasons.
        :raises SessionExpired: current login session is expired.
        """

        try:
            return await self.get_user_inventory(
                self._steam_id,
                app_ctx,
                start_asset_id=start_asset_id,
                count=count,
                _app_map=_app_map,
                _item_descriptions_map=_item_descriptions_map,
            )
        except SteamError as e:
            raise SessionExpired from e  # inventory of self cannot be private

    def inventory(
        self,
        app_ctx: AppContext,
        *,
        start_asset_id: int | None = None,
        count: int = INV_COUNT,
    ) -> CORO[AsyncGenerator[InventoryItemData, None]]:
        """
        Get async iterator of current authenticated user inventory pages.

        :param app_ctx: ``AppContext`` of requested inventory.
        :param start_asset_id: for partial inventory fetch.
        :param count: page size.
        :return: ``AsyncGenerator`` that yields list of ``EconItem``, total count of items in inventory,
            `last asset id` of the list.
        :raises SteamError: inventory is private.
        :raises EResultError: ordinary reasons.
        :raises TransportError: arbitrary reasons.
        :raises SessionExpired: current login session is expired.
        """

        return self.user_inventory(self._steam_id, app_ctx, start_asset_id=start_asset_id, count=count)

    @overload
    async def get_inventory_item(self, app_ctx: AppContext, obj: int) -> EconItem | None: ...

    @overload
    async def get_inventory_item(self, app_ctx: AppContext, obj: Callable[[EconItem], bool]) -> EconItem | None: ...

    def get_inventory_item(self, app_ctx: AppContext, obj: int | Callable[[EconItem], bool]) -> CORO[EconItem | None]:
        """
        Fetch and iterate over inventory item pages of current authenticated
        user until find one that satisfies passed arguments.

        :param app_ctx: ``AppContext`` of requested inventory.
        :param obj: `asset id` or `predicate` function.
        :return: ``EconItem`` or ``None`` if nothing found.
        :raises SteamError: inventory is private.
        :raises EResultError: ordinary reasons.
        :raises TransportError: arbitrary reasons.
        :raises SessionExpired: current login session is expired.
        """

        return self.get_user_inventory_item(self._steam_id, app_ctx, obj)
