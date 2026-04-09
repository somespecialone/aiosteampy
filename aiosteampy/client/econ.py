"""`Steam Economy` related models and functionality."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, NamedTuple

from yarl import URL

from ..constants import SteamURL
from ..id import SteamID
from .app import App, AppContext

if TYPE_CHECKING:  # optional app item context
    from .cs2 import DescriptionContext as CS2DescriptionContext
    from .cs2 import ItemContext as CS2ItemContext

TRADABLE_AFTER_DATE_FORMAT = "%b %d, %Y (%H:%M:%S) %Z"


def create_ident_code(*ids, sep=":"):
    """
    Create unique ident code for ``EconItem`` or ``ItemDescription`` within whole `Steam Economy`.

    .. seealso:: https://dev.doctormckay.com/topic/332-identifying-steam-items/
    """

    return sep.join(reversed(list(str(i) for i in filter(lambda i: i is not None, ids))))


class ItemAction(NamedTuple):
    link: str
    name: str


class ItemDescriptionEntry(NamedTuple):
    value: str
    type: str | None  # html, bbcode
    name: str | None
    color: str | None  # hexadecimal


class ItemTag(NamedTuple):
    category: str
    internal_name: str
    localized_category_name: str
    localized_tag_name: str
    color: str | None  # hexadecimal


# these two probably cs2 only props, so we store them raw delegating parsing to cs2.py
class AssetProperty(NamedTuple):
    id: int
    value: str
    # name: str | None


class AssetAccessory(NamedTuple):
    class_id: int
    parent_relationship_properties: tuple[AssetProperty, ...]
    standalone_properties: tuple[AssetProperty, ...]


@dataclass(slots=True, kw_only=True)
class BaseEntityWithIdentCode:
    id: str = field(init=False, default="")
    """Unique identifier within whole `Steam Economy`."""

    def __post_init__(self):
        self._set_ident_code()

    # optimization 🚀
    def _set_ident_code(self):
        raise NotImplementedError

    @property
    def ident_code(self) -> str:
        """Alias for ``id``."""
        return self.id

    def __eq__(self, other):
        return isinstance(other, BaseEntityWithIdentCode) and self.id == other.id

    def __hash__(self):
        return hash(self.id)


@dataclass(slots=True, kw_only=True)
class ItemDescription(BaseEntityWithIdentCode):
    """
    ``EconItem`` `description` representation embodies item *class* merged with *instance*.
    Items can share same `description`.

    .. note:: ``id`` or (``ident_code``) field is guaranteed unique within whole `Steam Economy`.
    """

    # As even Steam does not separate class from instance in response data, so are we

    class_id: int
    """Unique identifier within item's `App`."""
    instance_id: int
    """Unique identifier within item's `Class+App`."""

    app: App

    name: str
    market_name: str
    market_hash_name: str

    type: str | None = None

    name_color: str | None = None  # hexadecimal
    background_color: str | None = None

    icon_key: str
    """Icon CDN asset key."""
    icon_large_key: str | None = None
    """Large icon CDN asset key."""

    tags: tuple[ItemTag, ...] = ()  # listing item does not show tags
    descriptions: tuple[ItemDescriptionEntry, ...] = ()

    fraud_warnings: tuple[str, ...] = ()  # ?

    commodity: bool
    """Item use sell and buy orders on market and does not have listings."""

    market_tradable_restriction: int = 0
    """Period **in days** when item will be *untradable* after being purchased on the market."""
    market_buy_country_restriction: str | None = None
    market_fee_app: App | None = None
    market_marketable_restriction: int = 0
    """Period **in days** when item will be *unmarketable* after being purchased on the market."""

    # class instance fields
    owner_descriptions: tuple[ItemDescriptionEntry, ...] = ()
    """Descriptions available only to item owner."""
    actions: tuple[ItemAction, ...] = ()
    market_actions: tuple[ItemAction, ...] = ()
    owner_actions: tuple[ItemAction, ...] = ()

    tradable: bool
    """If item available for trade at the current moment."""
    marketable: bool
    """If item can be sold on market at the current moment."""

    # helper fields
    hold_until: datetime | None = field(init=False, default=None)
    """`Steam Market` hold end time."""
    protected_until: datetime | None = field(init=False, default=None)
    """`Trade Protection` protection end time."""

    # currency: int  # ?
    sealed: bool
    """If item under `Trade Protection` at the current moment."""

    _cs2_ctx: "CS2DescriptionContext | None" = field(init=False, default=None)  # cached

    def __post_init__(self):
        super(ItemDescription, self).__post_init__()
        self.owner_descriptions and self._set_restrictions_end_time()

    def _set_ident_code(self):
        self.id = create_ident_code(self.instance_id, self.class_id, self.app.id)

    def _set_restrictions_end_time(self):
        if self.market_tradable_restriction or self.market_marketable_restriction:
            # find tradable after description
            sep = "Tradable/Marketable After "
            if (t_a_descr := next(filter(lambda d: sep in d.value, self.owner_descriptions), None)) is not None:
                date_string = t_a_descr.value.split(sep)[1]
                self.hold_until = datetime.strptime(date_string, TRADABLE_AFTER_DATE_FORMAT)

        elif self.sealed:
            sep = "This item is trade-protected and cannot be consumed, modified, or transferred until "
            if (t_a_descr := next(filter(lambda d: sep in d.value, self.owner_descriptions), None)) is not None:
                date_string = t_a_descr.value.split(sep)[1]
                self.protected_until = datetime.strptime(date_string, TRADABLE_AFTER_DATE_FORMAT)

    @property
    def cs2(self) -> "CS2DescriptionContext | None":
        """`CS2` specific item description data."""

        if self.app is App.CS2:
            if self._cs2_ctx is None:
                from . import cs2

                self._cs2_ctx = cs2.DescriptionContext.from_description(self)

            return self._cs2_ctx

    @property
    def icon(self) -> URL:
        return SteamURL.STATIC / f"economy/image/{self.icon_key}/96fx96f"

    @property
    def icon_large(self) -> URL | None:
        return (
            (SteamURL.STATIC / f"economy/image/{self.icon_large_key}/330x192")
            if self.icon_large_key is not None
            else None
        )

    @property
    def market_url(self) -> URL:
        """URL of item page on `Steam Market`."""
        return SteamURL.COMMUNITY / f"market/listings/{self.app.id}/{self.market_hash_name}"


@dataclass(slots=True, kw_only=True)
class EconItem(BaseEntityWithIdentCode):
    """
    Represents unique copy of `Steam Economy` item, ala `Asset`.

    .. note:: ``id`` or (``ident_code``) field is guaranteed unique within whole `Steam Economy`.
    """

    context_id: int
    """Unique identifier within item `App`."""
    asset_id: int
    """Unique identifier within item `App+Context`."""
    owner: SteamID  # absent in data, will be set in methods, if possible
    """Item owner."""

    amount: int  # if stackable, otherwise always 1
    """Amount of items in the stack."""

    description: ItemDescription

    properties: tuple[AssetProperty, ...] = ()
    accessories: tuple[AssetAccessory, ...] = ()  # only stickers wear here is meaningful

    _cs2_ctx: "CS2ItemContext | None" = field(init=False, default=None)  # cached

    # optimization 🚀
    def __post_init__(self):
        super(EconItem, self).__post_init__()

    def _set_ident_code(self):
        self.id = create_ident_code(self.asset_id, self.context_id, self.description.app.id)

    @property
    def app_context(self) -> AppContext:
        return self.description.app.with_context(self.context_id)

    @property
    def cs2(self) -> "CS2ItemContext | None":
        """`CS2` specific item data."""

        if self.description.app is App.CS2:
            if self._cs2_ctx is None:
                from . import cs2

                self._cs2_ctx = cs2.ItemContext.from_item(self)

            return self._cs2_ctx


ItemDescriptionsMap = dict[str, ItemDescription]  # ident code : descr


class EconMixin:
    """``ItemDescription``, ``EconItem`` creation related methods."""

    __slots__ = ()

    @staticmethod
    def _parse_item_actions(actions: Iterable[dict]) -> tuple[ItemAction, ...]:
        return tuple(ItemAction(a_data["link"], a_data["name"]) for a_data in actions)

    @staticmethod
    def _parse_item_tags(tags: Iterable[dict]) -> tuple[ItemTag, ...]:
        return tuple(
            ItemTag(
                t_data["category"],
                t_data["internal_name"],
                t_data["localized_category_name"],
                t_data["localized_tag_name"],
                t_data.get("color"),
            )
            for t_data in tags
        )

    @staticmethod
    def _parse_item_descr_entries(descriptions: Iterable[dict]) -> tuple[ItemDescriptionEntry, ...]:
        return tuple(
            ItemDescriptionEntry(
                d_data["value"],
                d_data.get("type"),
                d_data.get("name"),
                d_data.get("color"),
            )
            for d_data in descriptions
            if (d_data["value"] != " " and d_data["value"])  # let's omit "blank" descriptions
        )

    @classmethod
    def _create_item_descr(cls, data: dict) -> ItemDescription:
        return ItemDescription(
            class_id=int(data["classid"]),
            instance_id=int(data["instanceid"]),
            app=App(data["appid"]),
            name=data["name"],
            market_name=data["market_name"],
            market_hash_name=data["market_hash_name"],
            name_color=data.get("name_color") or None,  # ignore " "
            background_color=data.get("name_color") or None,
            type=data["type"] or None,
            icon_key=data["icon_url"],
            icon_large_key=data.get("icon_url_large"),
            commodity=bool(data["commodity"]),
            tradable=bool(data["tradable"]),
            # market search page descriptions may miss this so True by default
            marketable=bool(data.get("marketable", True)),
            market_tradable_restriction=data.get("market_tradable_restriction", 0),
            market_buy_country_restriction=data.get("market_buy_country_restriction"),
            market_fee_app=App(data["market_fee_app"]) if "market_fee_app" in data else None,
            market_marketable_restriction=data.get("market_marketable_restriction", 0),
            actions=cls._parse_item_actions(data.get("actions", ())),
            market_actions=cls._parse_item_actions(data.get("market_actions", ())),
            owner_actions=cls._parse_item_actions(data.get("owner_actions", ())),
            tags=cls._parse_item_tags(data.get("tags", ())),
            descriptions=cls._parse_item_descr_entries(data.get("descriptions", ())),
            owner_descriptions=(cls._parse_item_descr_entries(data.get("owner_descriptions", ()))),
            fraud_warnings=tuple(data.get("fraudwarnings", ())),
            sealed=bool(data["sealed"]),
        )

    @staticmethod
    def _create_property(data: dict[str, str | int]) -> AssetProperty:
        _, value = next(filter(lambda kv: kv[0].endswith("_value"), data.items()))

        return AssetProperty(
            data["propertyid"],
            value,
            # data.get("name"),
        )

    @classmethod
    def _parse_asset_properties(cls, data: dict) -> tuple[AssetProperty, ...]:
        """Extract ``AssetProperty`` from data."""

        # avoid iterating over present None, that's Steam
        return tuple(cls._create_property(p_data) for p_data in (data.get("asset_properties", ()) or ()))

    @classmethod
    def _create_accessory(cls, data: dict) -> AssetAccessory:
        parent_props = tuple(cls._create_property(pd) for pd in data.get("parent_relationship_properties", ()))
        standalone_props = tuple(cls._create_property(pd) for pd in data.get("standalone_properties", ()))

        return AssetAccessory(int(data["classid"]), parent_props, standalone_props)

    @classmethod
    def _parse_asset_accessories(cls, data: dict) -> tuple[AssetAccessory, ...]:
        return tuple(cls._create_accessory(a_data) for a_data in data.get("asset_accessories", ()) or ())
