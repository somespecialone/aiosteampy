from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum, StrEnum
from typing import TYPE_CHECKING, NamedTuple

from yarl import URL

from .app import App, AppContext
from .constants import (
    STEAM_URL,
    Currency,
    TradeOfferStatus,
)
from .id import SteamID
from .utils import create_ident_code

if TYPE_CHECKING:
    from .cs2 import DescriptionContext as CS2DescriptionContext
    from .cs2 import ItemContext as CS2ItemContext


TRADABLE_AFTER_DATE_FORMAT = "%b %d, %Y (%H:%M:%S) %Z"


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
        return STEAM_URL.STATIC / f"economy/image/{self.icon_key}/96fx96f"

    @property
    def icon_large(self) -> URL | None:
        return (
            (STEAM_URL.STATIC / f"economy/image/{self.icon_large_key}/330x192")
            if self.icon_large_key is not None
            else None
        )

    @property
    def market_url(self) -> URL:
        """URL of item page on `Steam Market`."""
        return STEAM_URL.COMMUNITY / f"market/listings/{self.app.id}/{self.market_hash_name}"


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
    owner_id: SteamID  # absent in data, will be set in methods, if possible
    """The item's owner's ``SteamID``."""

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


class Notifications(NamedTuple):
    trades: int  # 1
    game_turns: int  # 2
    moderator_messages: int  # 3
    comments: int  # 4
    items: int  # 5
    invites: int  # 6
    # 7 missing
    gifts: int  # 8
    chats: int  # 9
    help_request_replies: int  # 10
    account_alerts: int  # 11


@dataclass(eq=False, slots=True, kw_only=True)
class BaseTradeOfferItem(EconItem):
    description: ItemDescription | None  # not active trade offers have no description on items

    def _set_tradable_after(self):
        if self.description is not None and self.description.market_tradable_restriction:
            sep = "Tradable/Marketable After "
            # cannot do super()._set_tradable_after() due to super exception
            t_a_descr = next(
                filter(lambda d: sep in d.value, self.description.owner_descriptions or ()),
                None,
            )
            if t_a_descr is not None:
                date_string = t_a_descr.value.split(sep)[1]
                self.tradable_after = datetime.strptime(date_string, TRADABLE_AFTER_DATE_FORMAT)

    @property
    def inspect_link(self) -> str | None:
        if self.description is not None and self.description.d_id:  # can't do super().inspect_url due to an error
            return make_inspect_link(owner_id=self.owner_id.id64, asset_id=self.asset_id, d_id=self.description.d_id)


@dataclass(eq=False, slots=True, kw_only=True)
class TradeOfferItem(BaseTradeOfferItem):
    missing: bool
    est_usd: int

    owner_id: int = 0


@dataclass(eq=False, slots=True)
class BaseTradeOffer:
    owner_id: int  # steam id64 of entity owner acc (SteamClient)
    partner_id: int  # id32

    status: TradeOfferStatus

    @property
    def partner_id64(self) -> int:
        return account_id_to_steam_id(self.partner_id)

    # TODO to remove in 0.8.0
    @property
    def is_active(self) -> bool:
        from warnings import warn

        warn(
            "`is_active` property of `BaseTradeOffer` is deprecated. Use `active` instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.active

    # shorthands
    @property
    def active(self) -> bool:
        return self.status is TradeOfferStatus.ACTIVE

    @property
    def accepted(self):
        return self.status is TradeOfferStatus.ACCEPTED

    @property
    def declined(self):
        return self.status is TradeOfferStatus.DECLINED

    @property
    def canceled(self):
        return self.status is TradeOfferStatus.CANCELED

    @property
    def countered(self):
        return self.status is TradeOfferStatus.COUNTERED


@dataclass(eq=False, slots=True)
class TradeOffer(BaseTradeOffer):
    """Steam Trade Offer entity."""

    trade_offer_id: int
    """The trade offer's unique numeric ID"""
    trade_id: int | None
    """A numeric trade ID, if the offer was accepted"""

    is_our_offer: bool

    expiration_time: datetime
    time_created: datetime
    time_updated: datetime

    items_to_give: list[TradeOfferItem]
    items_to_receive: list[TradeOfferItem]

    message: str = ""

    def __post_init__(self):
        for i in self.items_to_give:
            i.owner_id = self.owner_id

        for i in self.items_to_receive:
            i.owner_id = self.partner_id64

    def __hash__(self):
        return self.trade_offer_id

    @property
    def id(self) -> int:
        """Alias for `trade_offer_id`"""
        return self.trade_offer_id

    @property
    def sender(self) -> int:
        """Steam id64 of sender."""
        return self.owner_id if self.is_our_offer else self.partner_id64

    @property
    def receiver(self) -> int:
        """Steam id64 of receiver."""
        return self.partner_id64 if self.is_our_offer else self.owner_id


@dataclass(eq=False, slots=True, kw_only=True)
class HistoryTradeOfferItem(BaseTradeOfferItem):
    new_asset_id: int
    new_context_id: int

    owner_id: None = None


@dataclass(eq=False, slots=True)
class HistoryTradeOffer(BaseTradeOffer):
    """Accepted trade offer entity from the history of trades."""

    trade_id: int
    """A numeric trade ID of an accepted offer"""

    time_init: datetime

    assets_received: list[HistoryTradeOfferItem]
    assets_given: list[HistoryTradeOfferItem]

    def __hash__(self):
        return self.trade_id

    @property
    def id(self) -> int:
        """Alias for `trade_id`"""
        return self.trade_id
