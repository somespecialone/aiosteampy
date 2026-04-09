from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum, StrEnum
from typing import NamedTuple

from ....id import SteamID
from ...app import App, AppContext
from ...constants import Currency
from ...econ import EconItem, ItemDescription


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


@dataclass(slots=True)
class CachedResponse:
    last_modified: datetime
    """When `data` was last modified (value of ``Last-Modified`` header)."""


@dataclass(slots=True)
class ItemOrdersHistogram(CachedResponse):
    sell_order_count: int
    sell_order_price: int | None
    sell_order_table: tuple[SellOrderTableEntry, ...]
    buy_order_count: int
    buy_order_price: int | None
    buy_order_table: tuple[BuyOrderTableEntry, ...]
    highest_buy_order: int | None
    lowest_sell_order: int | None

    buy_order_graph: tuple[OrderGraphEntry, ...]
    sell_order_graph: tuple[OrderGraphEntry, ...]

    graph_max_y: int
    graph_min_x: int  # in cents
    graph_max_x: int  # in cents
    # price_prefix: str | None
    # price_suffix: str | None


class ActivityType(StrEnum):
    BUY_ORDER = "BuyOrder"
    SELL_ORDER = "SellOrder"
    SELL_ORDER_CANCEL = "SellOrderCancel"
    BUY_ORDER_CANCEL = "BuyOrderCancel"


class ActivityEntry(NamedTuple):
    type: ActivityType
    quantity: int
    price: int
    time: datetime
    avatar_buyer: str | None
    avatar_medium_buyer: str | None
    persona_buyer: str | None
    avatar_seller: str | None
    avatar_medium_seller: str | None
    persona_seller: str | None


@dataclass(slots=True)
class ItemOrdersActivity(CachedResponse):
    activity: tuple[ActivityEntry, ...]
    time: datetime


@dataclass(slots=True)
class PriceOverview(CachedResponse):
    lowest_price: int
    volume: int
    median_price: int


class MarketListingStatus(IntEnum):
    NEED_CONFIRMATION = 17
    ACTIVE = 1


@dataclass(slots=True, kw_only=True)
class MarketListingItem(EconItem):
    """Representation of ``EconItem`` with additional fields for market listings and orders."""

    market_id: int  # listing id

    unowned_id: int
    unowned_context_id: int

    amount: int = 1  # listing item always have amount eq 1
    # always 0 for listings from market, we can set user id for user listings, but let it be None
    owner: None = None
    accessories: None = None  # no data

    @property
    def unowned_app_context(self) -> AppContext:
        return self.description.app.with_context(self.unowned_context_id)


@dataclass(slots=True, kw_only=True)
class BaseOrder:
    id: int
    """Order id. Can be either `listing id` or `buy/sell order id`."""

    def __hash__(self):
        return self.id

    def __eq__(self, other):
        return isinstance(other, BaseOrder) and self.id == other.id


@dataclass(slots=True)
class BaseValues:
    currency: Currency
    """Values currency."""

    steam_fee: int
    """`Steam` part of combined ``fee``."""
    publisher_fee: int
    """`Publisher` part of combined ``fee``."""


@dataclass(slots=True)
class ListingValues(BaseValues):
    """Representation of market listing values, like a price, fee, etc."""

    price: int
    """Price of listing without fee. This is what lister will receive when someone buys listing."""
    fee: int
    """Combined final fee of listing."""

    # absent in market listing data
    # price_per_unit: int | None = None
    # fee_per_unit: int | None = None
    # steam_fee_per_unit: int | None = None
    # publisher_fee_per_unit: int | None = None

    @property
    def total_cost(self) -> int:
        """Full cost of current listing for buyer."""
        return self.price + self.fee


@dataclass(slots=True, kw_only=True)
class BaseMarketListing(BaseOrder):
    """Base class for market listings."""

    item: MarketListingItem

    original: ListingValues
    """Values of current listing in **original** currency."""
    converted: ListingValues
    """Values of current listing in **converted** to requested currency."""

    def __post_init__(self):
        if not self.item.market_id:
            self.item.market_id = self.id


@dataclass(slots=True, kw_only=True)
class MarketListing(BaseMarketListing):
    """Representation of listing entity (`lot` of the item for sale) at `Steam Market`."""

    # converted values missed in data if listing has been sold
    converted: ListingValues | None = None

    @property
    def sold(self) -> bool:
        """If current listing has been *sold* and unavailable for purchase."""
        return self.converted is None


@dataclass(slots=True)
class MarketListings(CachedResponse):
    """Container for `market listings` data."""

    listings: list[MarketListing]
    """List of `market listings`."""
    total: int
    """Total count of `market listings`."""


@dataclass(slots=True)
class NewlyListedItems(CachedResponse):
    """Container for newly listed items data."""

    listings: list[MarketListing]
    """List of newly listed items."""


class MarketSearchItem(NamedTuple):
    """Entry from `Steam Market` search result list."""

    sell_listings: int
    sell_price: int
    sell_price_text: str
    sale_price_text: str

    description: ItemDescription


class MarketSearchResult(NamedTuple):
    """Container for `market search result` data."""

    items: list[MarketSearchItem]
    total: int
    """Total count of `search results`."""


@dataclass(slots=True, kw_only=True)
class UserMarketListing(BaseMarketListing):
    """Representation of listing created by current user at `Steam Market`."""

    lister: SteamID  # there is "steamid_lister" in data so let it be
    """``SteamID`` of `lister`."""

    created_at: datetime
    """When `listing` was created."""

    status: MarketListingStatus
    """Current status of the `listing`."""
    active: bool
    """If `listing` is still active."""

    # fields that can be useful
    # item_expired: int
    # cancel_reason: int
    # time_finish_hold: int


@dataclass(slots=True, kw_only=True)
class BuyOrder(BaseOrder):
    """Representation of buy order entity placed by current user at `Steam Market`."""

    price: int
    """How much current user will pay per item."""

    item_description: ItemDescription

    quantity: int
    """Quantity of items current user want to buy."""
    quantity_remaining: int
    """Quantity of items left to fulfill order."""


class UserListings(NamedTuple):
    """User market listings container."""

    active: list[UserMarketListing]
    """Active (standing) listings."""
    to_confirm: list[UserMarketListing]
    """Listings awaiting for confirmation."""
    buy_orders: list[BuyOrder]
    """Standing buy orders placed by current user."""
    total: int
    """Total count of `active listings`."""


class BuyOrderStatus(NamedTuple):
    # from pending
    need_confirmation: bool = False

    # from confirmed
    active: bool = False
    purchased: bool = False
    # purchases: list[...]  # ?
    quantity: int = 0
    quantity_remaining: int = 0


@dataclass(slots=True, kw_only=True)
class MarketHistoryListingItem(MarketListingItem):
    market_id: None = None

    # purchase fields
    new_asset_id: int | None = None
    new_context_id: int | None = None

    rollback_new_asset_id: int | None = None
    rollback_new_context_id: int | None = None

    @property
    def new_app_context(self) -> AppContext | None:
        if self.new_context_id is not None:
            return self.description.app.with_context(self.new_context_id)

    @property
    def rollback_new_app_context(self) -> AppContext | None:
        if self.rollback_new_context_id is not None:
            return self.description.app.with_context(self.rollback_new_context_id)


@dataclass(slots=True, kw_only=True)
class MarketHistoryListing(BaseOrder):
    item: MarketHistoryListingItem

    values: ListingValues

    # purchase fields
    purchase_id: int | None = None
    steamid_purchaser: int | None = None
    received_amount: int | None = None
    received_currency: Currency | None = None
    time_sold: datetime | None = None
    paid_amount: int | None = None
    paid_fee: int | None = None

    # unknown fields
    # failed
    # needs_rollback
    # funds_held
    # time_funds_held_until
    # funds_revoked
    # funds_returned

    # listing fields
    # price: int | None = None
    # fee: int | None = None
    original_price: int | None = None
    cancel_reason: str | None = None


class MarketHistoryEventType(IntEnum):
    CREATED = 1
    CANCELED = 2
    SOLD = 3
    PURCHASED = 4


class MarketHistoryEvent(NamedTuple):
    """
    Event entity in market history. Represents event linked with related listing.
    Snapshot of listing and asset data (state) at event time,
    `asset id`, `context id` of asset may change since..
    """

    type: MarketHistoryEventType
    time: datetime
    listing: MarketHistoryListing


class UserMarketHistory(NamedTuple):
    """User market history container."""

    events: list[MarketHistoryEvent]
    """List of market history events."""
    total: int
    """Total count of `market history events`."""


class PriceHistoryEntry(NamedTuple):
    price: int
    """Parsed ``int`` price in cents."""
    price_raw: float
    """Raw ``float`` price."""

    date: datetime
    daily_volume: int


@dataclass(slots=True)
class PurchaseInfoValues(BaseValues):
    paid_amount: int
    """How much buyer paid for listing without fees."""
    paid_fee: int
    """Combined paid final fee of listing."""

    @property
    def total_paid(self) -> int:
        """Full amount of money paid for listing."""
        return self.paid_amount + self.paid_fee


@dataclass(slots=True)
class PurchaseInfo(BaseOrder):
    listing_id: int  # listing is empty so no need to store it
    item: MarketListingItem  # MarketListingItem has "sold" property which must be always True here, but who cares

    original: PurchaseInfoValues
    converted: PurchaseInfoValues


class MarketSearchSuggestion(NamedTuple):
    app: App
    listing_count: int
    market_name: str
    market_hash_name: str
    market_type: str
    min_price: float
    search_score: int


class MarketEligibility(NamedTuple):
    allowed: bool
    time_checked: datetime
    new_device_cooldown_days: int
    steamguard_required_days: int
    allowed_at_time: datetime | None = None
    expiration: datetime | None = None
    reason: int | None = None


class MarketAvailability(NamedTuple):
    available: bool
    tips: list[str]
    """List of tips for current user."""
    when: datetime | None
    """When market will be available if applicable."""
