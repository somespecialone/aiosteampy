from dataclasses import dataclass, field
from typing import NamedTuple
from datetime import datetime
from enum import StrEnum, IntEnum

from ...id import SteamID
from ...constants import Currency
from ...utils import make_inspect_link
from ...models import ItemDescription, EconItem


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


@dataclass(eq=False, slots=True)
class ItemOrdersActivity:
    activity: list[ActivityEntry]
    timestamp: int

    time: datetime = field(init=False, default=None)

    def __post_init__(self):
        self.time = datetime.fromtimestamp(self.timestamp)


class PriceOverview(NamedTuple):
    lowest_price: int
    volume: int
    median_price: int


class MarketListingStatus(IntEnum):
    NEED_CONFIRMATION = 17
    ACTIVE = 1


@dataclass(eq=False, slots=True, kw_only=True)
class MarketListingItem(EconItem):
    """Representation of ``EconItem`` with additional fields for market listings and orders."""

    market_id: int  # listing id

    unowned_id: int
    unowned_context_id: int

    amount: int = 1  # listing item always have amount eq 1

    owner_id: SteamID = SteamID()  # always 0 for listings from market, so let it be blank by default

    @property
    def inspect_link(self) -> str | None:
        """`Inspect in game` link for `CS2` item, if available."""
        if self.description.d_id:
            return make_inspect_link(market_id=self.market_id, asset_id=self.asset_id, d_id=self.description.d_id)


@dataclass(eq=False, slots=True, kw_only=True)
class BaseOrder:
    id: int
    """Order id. Can be either `listing id` or `buy/sell order id`."""

    def __hash__(self):
        return self.id

    def __eq__(self, other):
        return isinstance(other, BaseOrder) and self.id == other.id


@dataclass(eq=False, slots=True)
class BaseValues:
    currency: Currency
    """Values currency."""

    steam_fee: int
    """`Steam` part of combined ``fee``."""
    publisher_fee: int
    """`Publisher` part of combined ``fee``."""


@dataclass(eq=False, slots=True)
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


@dataclass(eq=False, slots=True, kw_only=True)
class BaseMarketListing(BaseOrder):
    """Base class for market listings."""

    item: MarketListingItem

    original: ListingValues
    """Values of current listing in **original** currency."""
    converted: ListingValues
    """Values of current listing in **converted** to account wallet currency."""

    def __post_init__(self):
        if not self.item.market_id:
            self.item.market_id = self.id


@dataclass(eq=False, slots=True, kw_only=True)
class MarketListing(BaseMarketListing):
    """Representation of listing entity (`lot` of the item for sale) at `Steam Market`."""

    # converted values missed in data if listing has been sold
    converted: ListingValues | None = None

    @property
    def sold(self) -> bool:
        """If current listing has been *sold* and unavailable for purchase."""
        # TODO need to test/check listing with same currency as requested
        return self.converted is None
        # return self.steam_fee == 0 and self.converted_fee == 0


@dataclass(eq=False, slots=True, kw_only=True)
class MarketSearchItem:
    """Entry from `Steam Market` search result list."""

    sell_listings: int
    sell_price: int
    sell_price_text: str
    sale_price_text: str

    app_icon: str
    app_name: str

    description: ItemDescription


@dataclass(eq=False, slots=True, kw_only=True)
class MyMarketListing(BaseMarketListing):
    """Representation of listing created by current user at `Steam Market`."""

    lister: SteamID  # there is "steamid_lister" in data so let it be
    """``SteamID`` of listing `lister`."""

    created_at: datetime
    """When market listing was created."""

    status: MarketListingStatus
    active: bool

    # fields that can be useful
    # item_expired: int
    # cancel_reason: int
    # time_finish_hold: int


@dataclass(eq=False, slots=True, kw_only=True)
class BuyOrder(BaseOrder):
    """Representation of buy order entity placed by current user at `Steam Market`."""

    price: int
    """How much current user will pay per item."""

    item_description: ItemDescription

    quantity: int
    """Quantity of items current user want to buy."""
    quantity_remaining: int
    """Quantity of items left to fulfill order."""


# multiple inheritance will be a good option, if it works with dataclasses slots...
@dataclass(eq=False, slots=True)
class BuyOrderStatus:
    # from pending
    need_confirmation: bool = False

    # from confirmed
    active: bool = False
    purchased: bool = False
    # purchases: list[...]  # ?
    quantity: int = 0
    quantity_remaining: int = 0


@dataclass(eq=False, slots=True)
class WalletInfo:
    balance: int
    country: str
    currency: Currency
    currency_increment: int  # ?
    delayed_balance: int  # ?
    fee: int
    fee_base: int
    fee_minimum: int
    fee_percent: float
    market_minimum: int  # ?
    max_balance: int
    publisher_fee_percent_default: float
    # state: str  # ?
    trade_max_balance: int  # ?


@dataclass(eq=False, slots=True, kw_only=True)
class MarketHistoryListingItem(MarketListingItem):
    market_id: None = None

    # purchase fields
    new_asset_id: int | None = None
    new_context_id: int | None = None
    rollback_new_asset_id: int | None = None
    rollback_new_context_id: int | None = None

    # always None, because we can't be sure that asset id has not been changed
    inspect_link: None = None


@dataclass(eq=False, slots=True, kw_only=True)
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
    LISTING_CREATED = 1
    LISTING_CANCELED = 2
    LISTING_SOLD = 3
    LISTING_PURCHASED = 4


@dataclass(eq=False, slots=True)
class MarketHistoryEvent:
    """
    Event entity in market history. Represents event linked with related listing.
    Snapshot of listing and asset data (state) at event time,
    `asset id`, `context id` of asset may change since..
    """

    type: MarketHistoryEventType
    time: datetime
    listing: MarketHistoryListing


@dataclass(eq=False, slots=True)
class PriceHistoryEntry:
    price: int
    """Parsed ``int`` price in cents."""
    price_raw: float
    """Raw ``float`` price."""

    date: datetime
    daily_volume: int


@dataclass(eq=False, slots=True)
class PurchaseInfoValues(BaseValues):
    paid_amount: int
    """How much buyer paid for listing without fees."""
    paid_fee: int
    """Combined paid final fee of listing."""

    @property
    def total_paid(self) -> int:
        """Full amount of money paid for listing."""
        return self.paid_amount + self.paid_fee


@dataclass(eq=False, slots=True)
class PurchaseInfo(BaseOrder):
    listing_id: int  # listing is empty so no need to store it
    item: MarketListingItem

    original: PurchaseInfoValues
    converted: PurchaseInfoValues
