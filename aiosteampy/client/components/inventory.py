"""Components with functionality responsible for user inventory handling."""

from collections.abc import Callable, Sequence, AsyncIterator
from contextlib import contextmanager, suppress
from typing import NamedTuple, overload
from yarl import URL

from ...constants import SteamURL
from ...exceptions import EResultError, SteamError, Unauthenticated
from ...id import SteamID
from ...session import SteamSession
from ...transport import BaseSteamTransport, TransportResponseError
from ..app import AppContext
from ..econ import (
    AssetAccessory,
    AssetProperty,
    EconItem,
    EconMixin,
    ItemDescriptionsMap,
    create_ident_code,
)
from ..state import PublicSteamState, SteamState
from .trade import make_trade_url
from .trade.trade import TRADE_NEW_URL

# Steam current limit
INV_COUNT = 2000

INVENTORY_URL = SteamURL.COMMUNITY / "inventory"


class Inventory(NamedTuple):
    """Container of inventory data."""

    items: Sequence[EconItem]
    """Inventory items."""
    total: int
    """Total count of *items in inventory*."""
    last_asset_id: int | None
    """Last `asset id` of the list returned by `Steam`."""


class InventoryPublicComponent(EconMixin):
    """Component with public `Steam Inventory` methods. Available without authentication."""

    __slots__ = ("_transport", "_state")

    def __init__(self, transport: BaseSteamTransport, state: PublicSteamState):
        self._transport = transport
        self._state = state

    @classmethod
    def _parse_inventory(
        cls,
        data: dict[str, list[dict]],
        owner_id: SteamID,
        item_descriptions_map: ItemDescriptionsMap,
    ) -> tuple[EconItem, ...]:
        for d_data in data["descriptions"]:
            key = create_ident_code(d_data["instanceid"], d_data["classid"], d_data["appid"])
            if key not in item_descriptions_map:
                item_descriptions_map[key] = cls._create_item_descr(d_data)

        properties_map: dict[str, tuple[AssetProperty, ...]] = {}
        accessories_map: dict[str, tuple[AssetAccessory, ...]] = {}
        for properties_data in data.get("asset_properties", ()):
            properties_map[properties_data["assetid"]] = cls._parse_asset_properties(properties_data)
            accessories_map[properties_data["assetid"]] = cls._parse_asset_accessories(properties_data)

        return tuple(
            EconItem(
                context_id=int(a_data["contextid"]),
                asset_id=int(a_data["assetid"]),
                owner=owner_id,
                amount=int(a_data["amount"]),
                description=item_descriptions_map[
                    create_ident_code(a_data["instanceid"], a_data["classid"], a_data["appid"])
                ],
                properties=properties_map.get(a_data["assetid"], ()),
                accessories=accessories_map.get(a_data["assetid"], ()),
            )
            for a_data in data["assets"]
        )

    async def get_user_inventory(
        self,
        user_id: SteamID,
        app_ctx: AppContext,
        *,
        start_asset_id: int | None = None,
        count: int = INV_COUNT,
        _item_descriptions_map: ItemDescriptionsMap | None = None,
    ) -> Inventory:
        """
        Get `user` inventory.

        .. note:: Pagination can be achieved by passing ``start_asset_id`` arg.

        :param user_id: ``SteamID`` of user which inventory is requested.
        :param app_ctx: ``AppContext`` of requested inventory.
        :param start_asset_id: for partial inventory fetch.
        :param count: page size.
        :return: Container with sequence of ``EconItem``, total count of items in inventory, `last asset id` of the list.
        :raises SteamError: inventory is private.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        """

        inv_url = INVENTORY_URL / f"{user_id}/"
        params = {
            "l": self._state.language,
            "count": count,
            "raw_asset_properties": 1,  # as browser + save some network traffic
            "preserve_bbcode": 1,  # preserve date format in owner descriptions
        }
        if start_asset_id:
            params["start_assetid"] = start_asset_id

        try:
            r = await self._transport.request(
                "GET",
                inv_url / f"{app_ctx.app.id}/{app_ctx.context_id}",
                params=params,
                headers={"Referer": str(inv_url)},
                response_mode="json",
            )

        except TransportResponseError as e:
            if e.status == 403:
                # https://github.com/DoctorMcKay/node-steamcommunity/blob/d3e90f6fd3bea65b1ebc1bdaec754f99dcc8ddb3/components/users.js#L603
                raise SteamError(f"User ({user_id}) inventory is private") from e
            else:
                raise e

        rj: dict = r.content

        EResultError.check_data(rj)

        total_count: int = rj.get("total_inventory_count", 0)
        last_asset_id = int(rj.get("last_assetid", 0)) or None

        if "descriptions" not in rj:
            return Inventory([], total_count, last_asset_id)

        _item_descriptions_map = {} if _item_descriptions_map is None else _item_descriptions_map

        return Inventory(self._parse_inventory(rj, user_id, _item_descriptions_map), total_count, last_asset_id)

    async def user_inventory(
        self,
        user_id: SteamID,
        app_ctx: AppContext,
        *,
        start_asset_id: int | None = None,
        count: int = INV_COUNT,
    ) -> AsyncIterator[Sequence[EconItem]]:
        """
        Get async iterator of user inventory pages.

        :param user_id: ``SteamID`` of user which inventory is requested.
        :param app_ctx: ``AppContext`` of requested inventory.
        :param start_asset_id: for partial inventory fetch.
        :param count: page size.
        :return: ``AsyncIterator`` that yields sequence of ``EconItem``.
        :raises SteamError: inventory is private.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        """

        _item_descriptions_map = {}  # shared descriptions instances across calls

        more_items = True
        while more_items:
            # browser does the first request with count=75,
            # receiving data with last_assetid if there are more items (and no assets for some apps, ex. CS2)
            inventory = await self.get_user_inventory(
                user_id,
                app_ctx,
                start_asset_id=start_asset_id,
                count=count,
                _item_descriptions_map=_item_descriptions_map,
            )
            start_asset_id = inventory.last_asset_id
            more_items = bool(start_asset_id)

            yield inventory.items

    @overload
    async def get_user_item(
        self,
        user_id: SteamID,
        app_ctx: AppContext,
        obj: int,
    ) -> EconItem | None: ...

    @overload
    async def get_user_item(
        self,
        user_id: SteamID,
        app_ctx: AppContext,
        obj: Callable[[EconItem], bool],
    ) -> EconItem | None: ...

    # unfortunately, option with start_asset_id as asset_id does not work
    async def get_user_item(
        self,
        user_id: SteamID,
        app_ctx: AppContext,
        obj: int | Callable[[EconItem], bool],
    ) -> EconItem | None:
        """
        Get and iterate over inventory item pages of user until find one that satisfies passed arguments.

        :param user_id: ``SteamID`` of user which inventory is requested.
        :param app_ctx: ``AppContext`` of requested inventory.
        :param obj: `asset id` or `predicate` function.
        :return: ``EconItem`` or ``None`` if nothing found.
        :raises SteamError: inventory is private.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        """

        if callable(obj):
            predicate = obj
        else:

            def predicate(i: EconItem):
                return i.asset_id == obj

        async for items in self.user_inventory(user_id, app_ctx):
            with suppress(StopIteration):
                return next(filter(predicate, items))


@contextmanager
def private_inventory_ctx():
    """Convert ``SteamError`` raised in case of private inventory to a ``Unauthenticated`` exception."""
    try:
        yield
    except SteamError as e:
        if "private" in (e.args[0] if e.args else ()):
            raise Unauthenticated from e  # inventory of self cannot be private
        else:
            raise e


class TradeInventory(NamedTuple):
    """Container of inventory data fetched trough `trade url`."""

    items: Sequence[EconItem] = ()
    """Inventory items."""

    more: bool = False


class InventoryComponent(InventoryPublicComponent):
    """Component responsible for working with current user inventory."""

    __slots__ = ("_session",)

    _state: SteamState

    def __init__(self, session: SteamSession, state: SteamState):
        super().__init__(session.transport, state)

        self._session = session

    async def get(
        self,
        app_ctx: AppContext,
        *,
        start_asset_id: int | None = None,
        count: int = INV_COUNT,
        _item_descriptions_map: ItemDescriptionsMap | None = None,
    ) -> Inventory:
        """
        Get current authenticated user inventory.

        .. note:: Pagination can be achieved by passing ``start_asset_id`` arg.

        :param app_ctx: ``AppContext`` of requested inventory.
        :param start_asset_id: for partial inventory fetch.
        :param count: page size.
        :return: list of ``EconItem``, total count of items in inventory, `last asset id` of the list.
        :raises SteamError: inventory is private.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        :raises Unauthenticated: auth cookies or token are missing, expired, or invalid.
        """

        with private_inventory_ctx():
            return await self.get_user_inventory(
                self._session.steam_id,
                app_ctx,
                start_asset_id=start_asset_id,
                count=count,
                _item_descriptions_map=_item_descriptions_map,
            )

    async def inventory(
        self,
        app_ctx: AppContext,
        *,
        start_asset_id: int | None = None,
        count: int = INV_COUNT,
    ) -> AsyncIterator[Sequence[EconItem]]:
        """
        Get async iterator of current authenticated user inventory pages.

        :param app_ctx: ``AppContext`` of requested inventory.
        :param start_asset_id: for partial inventory fetch.
        :param count: page size.
        :return: ``AsyncIterator`` that yields sequence of ``EconItem``, total count of items in inventory,
            `last asset id` of the sequence.
        :raises SteamError: inventory is private.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        :raises Unauthenticated: auth cookies or token are missing, expired, or invalid.
        """

        with private_inventory_ctx():
            async for items in self.user_inventory(
                self._session.steam_id,
                app_ctx,
                start_asset_id=start_asset_id,
                count=count,
            ):
                yield items

    @overload
    async def get_inventory_item(self, app_ctx: AppContext, obj: int) -> EconItem | None: ...

    @overload
    async def get_inventory_item(self, app_ctx: AppContext, obj: Callable[[EconItem], bool]) -> EconItem | None: ...

    async def get_inventory_item(
        self,
        app_ctx: AppContext,
        obj: int | Callable[[EconItem], bool],
    ) -> EconItem | None:
        """
        Fetch and iterate over inventory item pages of current authenticated
        user until find one that satisfies passed arguments.

        :param app_ctx: ``AppContext`` of requested inventory.
        :param obj: `asset id` or `predicate` function.
        :return: ``EconItem`` or ``None`` if nothing found.
        :raises SteamError: inventory is private.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        :raises Unauthenticated: auth cookies or token are missing, expired, or invalid.
        """

        with private_inventory_ctx():
            return await self.get_user_item(self._session.steam_id, app_ctx, obj)

    @classmethod
    def _parse_trade_inventory(
        cls,
        data: dict[str, dict[str, dict[str, dict | list[dict]]]],
        owner_id: SteamID,
        item_descriptions_map: ItemDescriptionsMap,
        app_ctx: AppContext,
    ) -> tuple[EconItem, ...]:
        for _, d_data in data["rgDescriptions"].items():
            key = create_ident_code(d_data["instanceid"], d_data["classid"], d_data["appid"])
            if key not in item_descriptions_map:
                item_descriptions_map[key] = cls._create_item_descr(d_data)

        properties_map: dict[str, tuple[AssetProperty, ...]] = {}
        for prop_parent_asset_id, properties_data in data["rgAssetProperties"].items():
            properties_map[prop_parent_asset_id] = tuple(cls._create_property(p_data) for p_data in properties_data)

        accessories_map: dict[str, tuple[AssetAccessory, ...]] = {}
        for acc_parent_asset_id, accessories_data in data["rgAssetAccessories"].items():
            accessories_map[acc_parent_asset_id] = tuple(
                cls._create_accessory(acc_data) for acc_data in accessories_data
            )

        return tuple(
            EconItem(
                # pos: int
                # hide_in_china: int(bool)
                context_id=int(app_ctx.context_id),
                asset_id=int(asset_id),
                owner=owner_id,
                amount=int(a_data["amount"]),
                description=item_descriptions_map[
                    create_ident_code(
                        a_data["instanceid"],
                        a_data["classid"],
                        app_ctx.app.id,
                    )
                ],
                properties=properties_map.get(asset_id, ()),
                accessories=accessories_map.get(asset_id, ()),
            )
            for asset_id, a_data in data["rgInventory"].items()
        )

    async def get_partner_inventory(
        self,
        obj: str | URL | tuple[SteamID, str],
        app_ctx: AppContext,
        *,
        start: int = 0,
        page: int = 0,
        _item_descriptions_map: ItemDescriptionsMap | None = None,
    ) -> TradeInventory:
        """
        Get `partner` inventory (`Their inventory`) trough `Steam Trade Offers`.

        .. note:: Pagination can be achieved by passing ``start`` arg.

        :param obj: `trade url` or partner ``SteamID` and `trade token`.
        :param app_ctx: ``AppContext`` of requested inventory.
        :param start: partial inventory fetch.
        :param page: number of ``page`` to be requested. **Starts from 0**.
        :return: Container with sequence of ``EconItem``, boolean if there is more items to fetch.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        """

        if page and start:
            raise ValueError("Page and start args are mutually exclusive")

        if page:
            start = INV_COUNT * page

        if isinstance(obj, (str, URL)):
            trade_url = URL(obj)
            partner = SteamID(trade_url.query["partner"])
        else:
            trade_url = make_trade_url(*obj)
            partner = obj[0]

        headers = {"Referer": str(trade_url)}
        params = {
            "sessionid": self._session.session_id,
            "partner": partner,
            "appid": app_ctx.app.id,
            "contextid": app_ctx.context_id,
        }
        if start:
            params["start"] = start

        r = await self._transport.request(
            "GET",
            TRADE_NEW_URL / "partnerinventory/",
            params=params,
            headers=headers,
            response_mode="json",
        )

        rj: dict = r.content

        EResultError.check_data(rj)

        if not rj.get("rgInventory") or not rj.get("rgDescriptions"):
            return TradeInventory()

        _item_descriptions_map = {} if _item_descriptions_map is None else _item_descriptions_map

        return TradeInventory(
            self._parse_trade_inventory(
                rj,
                partner,
                _item_descriptions_map,
                app_ctx,
            ),
            rj["more"],
        )

    async def partner_inventory(
        self,
        obj: str | URL | tuple[SteamID, str],
        app_ctx: AppContext,
        *,
        start: int = 0,
        page: int = 0,
    ) -> AsyncIterator[Sequence[EconItem]]:
        """
        Get async iterator of `partner` inventory pages.

        :param obj: `trade url` or partner ``SteamID` and `trade token`.
        :param app_ctx: ``AppContext`` of requested inventory.
        :param start: partial inventory fetch.
        :param page: number of ``page`` to be requested. **Starts from 0**.
        :return: ``AsyncIterator`` that yields sequence of ``EconItem``.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        """

        _item_descriptions_map = {}  # shared descriptions instances across calls

        more_items = True
        while more_items:
            inventory = await self.get_partner_inventory(
                obj,
                app_ctx,
                start=start,
                page=page,
                _item_descriptions_map=_item_descriptions_map,
            )
            more_items = inventory.more

            yield inventory.items


# TODO get available inventories
