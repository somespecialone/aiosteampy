from dataclasses import dataclass, field
from typing import NamedTuple
from datetime import datetime

from yarl import URL

from .constants import (
    STEAM_URL,
    TRADABLE_AFTER_DATE_FORMAT,
    App,
    AppContext,
    Currency,
    ConfirmationType,
    MarketHistoryEventType,
    MarketListingStatus,
    TradeOfferStatus,
)
from .utils import create_ident_code, account_id_to_steam_id, make_inspect_url


class ItemAction(NamedTuple):
    link: str
    name: str


class ItemDescriptionEntry(NamedTuple):
    value: str
    color: str | None  # hexadecimal


class ItemTag(NamedTuple):
    category: str
    internal_name: str
    localized_category_name: str
    localized_tag_name: str
    color: str | None  # hexadecimal


@dataclass(eq=False, slots=True, frozen=True, kw_only=True)
class ItemDescription:
    """
    `EconItem` description representation.
    `id` or `ident_code` field is guaranteed unique within whole Steam Economy.
    """

    id: str = field(init=False, default="")  # optimization 🚀
    """Unique identifier of the `ItemDescription` within `Steam Economy`"""

    class_id: int
    instance_id: int

    d_id: int | None = field(init=False, default=None)  # optional CSGO inspect id

    app: App

    name: str
    market_name: str
    market_hash_name: str

    type: str | None = None

    name_color: str | None = None  # hexadecimal
    background_color: str | None = None

    icon: str
    icon_large: str | None = None

    actions: tuple[ItemAction, ...] = ()
    market_actions: tuple[ItemAction, ...] = ()
    owner_actions: tuple[ItemAction, ...] = ()
    tags: tuple[ItemTag, ...] = ()
    descriptions: tuple[ItemDescriptionEntry, ...] = ()
    owner_descriptions: tuple[ItemDescriptionEntry, ...] = ()

    fraud_warnings: tuple[str, ...] = ()

    commodity: bool  # item use buy orders on market
    tradable: bool  # item can be traded
    marketable: bool
    # days for which the item will be untradable after being sold on the market.
    market_tradable_restriction: int | None = None
    market_buy_country_restriction: str | None = None
    market_fee_app: int | None = None
    market_marketable_restriction: int | None = None  # same as `market_tradable_restriction` but for market

    def __post_init__(self):
        self._set_ident_code()
        self._set_d_id()

    def _set_ident_code(self):
        object.__setattr__(self, "id", create_ident_code(self.instance_id, self.class_id, self.app.value))

    def _set_d_id(self):
        if self.app is App.CS2:
            if (i_action := next(filter(lambda a: "Inspect" in a.name, self.actions), None)) is not None:
                object.__setattr__(self, "d_id", int(i_action.link.split("%D")[1]))

    @property
    def ident_code(self) -> str:
        """Alias for `id`"""
        return self.id

    @property
    def icon_url(self) -> URL:
        return STEAM_URL.STATIC / f"economy/image/{self.icon}/96fx96f"

    @property
    def icon_large_url(self) -> URL | None:
        return (STEAM_URL.STATIC / f"economy/image/{self.icon_large}/330x192") if self.icon_large is not None else None

    @property
    def market_url(self) -> URL:
        return STEAM_URL.MARKET / f"listings/{self.app.value}/{self.market_hash_name}"

    def __eq__(self, other):
        if isinstance(other, ItemDescription):
            return self.id == other.id
        return False

    def __hash__(self):
        return hash(self.id)


@dataclass(eq=False, slots=True, kw_only=True)
class EconItem:
    """
    Represents unique copy of a `Steam Economy` item, ala `Asset`.
    `id` or `ident_code` field is guaranteed unique within whole Steam Economy.
    """

    id: str = field(init=False, default="")  # optimization 🚀
    """Unique identifier of the `EconItem` within `Steam Economy`"""

    asset_id: int  # The item's unique ID within its app+context
    owner_id: int

    app_context: AppContext

    amount: int  # if stackable

    description: ItemDescription
    tradable_after: datetime | None = field(init=False, default=None)

    def __post_init__(self):
        self._set_ident_code()
        self._set_tradable_after()

    def _set_ident_code(self):
        self.id = create_ident_code(self.asset_id, self.app_context.context, self.app_context.app.value)

    def _set_tradable_after(self):
        if self.description.market_tradable_restriction:
            sep = "Tradable/Marketable After "
            t_a_descr = next(filter(lambda d: sep in d.value, self.description.owner_descriptions or ()), None)
            if t_a_descr is not None:
                date_string = t_a_descr.value.split(sep)[1]
                self.tradable_after = datetime.strptime(date_string, TRADABLE_AFTER_DATE_FORMAT)

    @property
    def ident_code(self) -> str:
        """Alias for `id`"""
        return self.id

    @property
    def inspect_url(self) -> str | None:
        if self.description.d_id:
            return make_inspect_url(owner_id=self.owner_id, asset_id=self.asset_id, d_id=self.description.d_id)

    def __eq__(self, other):
        if isinstance(other, EconItem):
            return self.id == other.id
        return False

    def __hash__(self):
        return hash(self.id)


# https://github.com/DoctorMcKay/node-steamcommunity/wiki/CConfirmation
@dataclass(eq=False, slots=True)
class Confirmation:
    id: int
    nonce: str  # conf key
    creator_id: int  # trade/listing id
    creation_time: datetime

    type: ConfirmationType

    icon: str
    multi: bool  # ?
    headline: str
    summary: str
    warn: str | None  # ?

    details: dict[str, ...] | None = None  # TODO need typing

    @property
    def listing_item_ident_code(self) -> str | None:
        """`MarketListingItem` ident code if `details` is present"""
        if self.details is not None:
            return create_ident_code(self.details["id"], self.details["contextid"], self.details["appid"])


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
class MarketListingItem(EconItem):
    """Presented only on active listing."""

    market_id: int  # listing id

    unowned_id: int | None
    unowned_context_id: int | None

    amount: int = 1  # item on listing always have amount eq 1
    owner_id: int = 0

    @property
    def inspect_url(self) -> str | None:
        if self.description.d_id:
            return make_inspect_url(market_id=self.market_id, asset_id=self.asset_id, d_id=self.description.d_id)


@dataclass(eq=False, slots=True)
class BaseOrder:
    id: int  # listing/buy order id

    price: int

    def __hash__(self):
        return self.id


@dataclass(eq=False, slots=True)
class MyMarketListing(BaseOrder):
    lister_steam_id: int
    time_created: datetime

    item: MarketListingItem

    status: MarketListingStatus
    active: bool  # ?

    # fields that can be useful
    item_expired: int
    cancel_reason: int
    time_finish_hold: int

    @property
    def listing_id(self) -> int:
        return self.id


@dataclass(eq=False, slots=True)
class BuyOrder(BaseOrder):
    item_description: ItemDescription

    quantity: int
    quantity_remaining: int

    @property
    def buy_order_id(self) -> int:
        return self.id


@dataclass(eq=False, slots=True, kw_only=True)
class MarketHistoryListingItem(MarketListingItem):
    market_id: None = None

    # purchase fields
    new_asset_id: int | None = None
    new_context_id: int | None = None
    rollback_new_asset_id: int | None = None
    rollback_new_context_id: int | None = None

    @property
    def inspect_link(self) -> None:
        """Always `None`, because we can't be sure that asset id has not been changed."""
        return None


@dataclass(eq=False, slots=True, kw_only=True)
class MarketHistoryListing(BaseOrder):
    item: MarketHistoryListingItem

    currency: Currency

    # purchase fields
    purchase_id: int | None = None
    steamid_purchaser: int | None = None
    received_amount: int | None = None
    received_currency: Currency | None = None
    time_sold: datetime | None = None
    paid_amount: int | None = None
    paid_fee: int | None = None
    steam_fee: int | None = None
    publisher_fee: int | None = None

    # unknown fields
    # failed
    # needs_rollback
    # funds_held
    # time_funds_held_until
    # funds_revoked
    # funds_returned

    # listing fields
    price: int | None = None
    fee: int | None = None
    original_price: int | None = None
    cancel_reason: str | None = None

    @property
    def listing_id(self) -> int:
        return self.id


@dataclass(eq=False, slots=True)
class MarketHistoryEvent:
    """
    Event entity in market history. Represents event linked with related listing.
    Note that this is just a snapshot of listing, asset data for event fire moment time
    and `asset id`, `context id` of asset may change already.
    """

    listing: MarketHistoryListing
    time_event: datetime
    type: MarketHistoryEventType


@dataclass(eq=False, slots=True)
class PriceHistoryEntry:
    date: datetime
    price: float  # float from steam
    daily_volume: int


@dataclass(eq=False, slots=True)
class MarketListing(BaseOrder):
    item: MarketListingItem

    currency: Currency  # original currency
    fee: int
    steam_fee: int
    publisher_fee: int

    # converted values are not presented in data if listing is sold
    converted_currency: Currency | None
    converted_price: int
    converted_fee: int
    converted_steam_fee: int
    converted_publisher_fee: int

    converted_price_per_unit: int
    converted_fee_per_unit: int
    converted_steam_fee_per_unit: int
    converted_publisher_fee_per_unit: int

    def __post_init__(self):
        if not self.item.market_id:
            self.item.market_id = self.id

    @property
    def listing_id(self) -> int:
        return self.id

    @property
    def total_cost(self) -> int:
        return self.price + self.fee

    @property
    def total_converted_cost(self) -> int:
        return self.converted_price + self.converted_fee

    @property
    def is_sold(self) -> bool:
        """If listing is sold and unavailable for purchase"""
        return self.steam_fee == 0 and self.converted_fee == 0


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
    def inspect_url(self) -> str | None:
        if self.description is not None and self.description.d_id:  # can't do super().inspect_url due to an error
            return make_inspect_url(owner_id=self.owner_id, asset_id=self.asset_id, d_id=self.description.d_id)


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


class SellOrderTableEntry(NamedTuple):
    price: int
    price_with_fee: int
    quantity: int


class BuyOrderTableEntry(NamedTuple):
    price: int
    quantity: int


class OrderGraphEntry(NamedTuple):
    price: int
    quantity: int
    repr: str


@dataclass(eq=False, slots=True)
class ItemOrdersHistogram:
    sell_order_count: int
    sell_order_price: int | None
    sell_order_table: list[SellOrderTableEntry]
    buy_order_count: int
    buy_order_price: int | None
    buy_order_table: list[BuyOrderTableEntry]
    highest_buy_order: int | None
    lowest_sell_order: int | None

    # prices in integers (cents)!
    buy_order_graph: list[OrderGraphEntry]
    sell_order_graph: list[OrderGraphEntry]

    graph_max_y: int
    graph_min_x: int  # in cents
    graph_max_x: int  # in cents
    # price_prefix: str | None
    # price_suffix: str | None


@dataclass(eq=False, slots=True)
class MarketSearchItem:
    sell_listings: int
    sell_price: int
    sell_price_text: str
    sale_price_text: str

    app_icon: str
    app_name: str

    description: ItemDescription
