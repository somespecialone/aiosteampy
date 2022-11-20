from dataclasses import dataclass, field
from typing import Literal, TypeAlias
from datetime import datetime

from .constants import (
    STEAM_URL,
    GameType,
    Currency,
    ConfirmationType,
    MarketHistoryEventType,
    MarketListingStatus,
    TradeOfferStatus,
)
from .utils import create_ident_code, account_id_to_steam_id


@dataclass(eq=False, slots=True)
class ItemAction:
    link: str
    name: str


@dataclass(eq=False, slots=True)
class ItemDescription:
    value: str
    type: Literal["html"] = "html"  # just because
    color: str | None = None  # hexadecimal


@dataclass(eq=False, slots=True)
class ItemTag:
    category: str
    internal_name: str
    localized_category_name: str
    localized_tag_name: str
    color: str | None = None  # hexadecimal


@dataclass(eq=False, slots=True)
class ItemClass:
    """
    `EconItem` description representation.
    `ident_code` field is guaranteed unique within whole Steam Economy.
    """

    id: int  # classid
    instance_id: int

    game: GameType

    name: str
    market_name: str
    market_hash_name: str

    type: str | None

    name_color: str | None  # hexadecimal
    background_color: str | None

    icon: str
    icon_large: str | None

    actions: tuple[ItemAction, ...]
    market_actions: tuple[ItemAction, ...]
    owner_actions: tuple[ItemAction, ...]
    tags: tuple[ItemTag, ...]
    descriptions: tuple[ItemDescription, ...]

    fraud_warnings: tuple[str]

    commodity: bool  # ?
    tradable: bool
    marketable: bool
    market_tradable_restriction: int | None = None
    market_buy_country_restriction: str | None = None
    market_fee_app: int | None = None
    market_marketable_restriction: int | None = None

    # optimization 🚀
    ident_code: str = field(init=False, default=None)

    def __post_init__(self):
        self._set_ident_code()

    def _set_ident_code(self):
        self.ident_code = create_ident_code(self.id, self.game[0])

    @property
    def d_id(self) -> int | None:
        """Optional CSGO attr"""
        for action in self.actions:
            if "Inspect" in action.name:
                return int(action.link.split("%D")[1])

    @property
    def class_id(self) -> int:
        return self.id

    @property
    def icon_url(self) -> str:
        return str(STEAM_URL.STATIC / f"economy/image/{self.icon}/96fx96f")

    @property
    def icon_large_url(self) -> str | None:
        return str(STEAM_URL.STATIC / f"economy/image/{self.icon_large}/330x192") if self.icon_large else None

    def __eq__(self, other: "ItemClass"):
        return (self.id == other.id) and (self.game[0] == other.game[0]) and (self.game[1] == other.game[1])

    def __hash__(self):
        return self.id


EconItemTuple: TypeAlias = tuple[int, int, int, int]


@dataclass(eq=False, slots=True, kw_only=True)
class EconItem:
    """
    Represents Steam economy item (inventories).
    `ident_code` field is guaranteed unique within whole Steam Economy.
    """

    id: int  # The item's unique ID within its app+context.
    owner_id: int

    class_: ItemClass

    amount: int

    ident_code: str = field(init=False, default=None)  # optimization 🚀
    _args_tuple_: EconItemTuple = field(init=False, default=(), repr=False)

    def __post_init__(self):
        self._set_ident_code()
        self._set_args_tuple()

    def _set_ident_code(self):
        self.ident_code = create_ident_code(self.id, *self.class_.game)

    def _set_args_tuple(self):
        self._args_tuple_ = (self.class_.game[0], self.class_.game[1], self.amount, self.id)

    @property
    def inspect_link(self) -> str | None:
        for action in self.class_.actions:
            if "Inspect" in action.name:
                return action.link.replace("%assetid%", str(self.id)).replace("%owner_steamid%", str(self.owner_id))

    @property
    def asset_id(self) -> int:
        return self.id

    def __getitem__(self, index: int) -> int:  # some magic
        return self._args_tuple_[index]

    def __iter__(self):
        return iter(self._args_tuple_)

    def __eq__(self, other: "EconItem"):
        return (self.id == other.id) and (self.class_ == other.class_)

    def __hash__(self):
        return hash(self.ident_code)


EconItemType: TypeAlias = EconItem | EconItemTuple


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

    asset_ident_code: str | None = None  # only to map confirmation to sell listing without id


@dataclass(eq=False, slots=True)
class Notifications:
    trades: int = 0  # 1
    game_turns: int = 0  # 2
    moderator_messages: int = 0  # 3
    comments: int = 0  # 4
    items: int = 0  # 5
    invites: int = 0  # 6
    # 7 missing
    gifts: int = 0  # 8
    chats: int = 0  # 9
    help_request_replies: int = 0  # 10
    account_alerts: int = 0  # 11


@dataclass(eq=False, slots=True, kw_only=True)
class MarketListingItem(EconItem):
    # presented only on active listing
    market_id: int  # listing id

    unowned_id: int | None
    unowned_context_id: int | None

    amount: int = 1  # item on listing always have 1 amount
    owner_id: int = 0

    @property
    def inspect_link(self) -> str | None:
        for action in self.class_.market_actions:
            if "Inspect" in action.name:
                return action.link.replace("%assetid%", str(self.id)).replace("%listingid%", str(self.market_id))


@dataclass(eq=False, slots=True)
class BaseOrder:
    id: int  # listing/buy order id

    price: float

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
    item_class: ItemClass

    quantity: int
    quantity_remaining: int

    @property
    def buy_order_id(self) -> int:
        return self.id


@dataclass(eq=False, slots=True, kw_only=True)
class MarketHistoryListingItem(MarketListingItem):
    market_id: None = None

    # purchase fields
    new_id: int | None = None
    new_context_id: int | None = None
    rollback_new_id: int | None = None
    rollback_new_context_id: int | None = None

    @property
    def inspect_link(self) -> None:
        """Always `None`, because we can't be sure that asset id has not been changed."""
        return None


@dataclass(eq=False, slots=True, kw_only=True)
class MarketHistoryListing(BaseOrder):
    item: MarketHistoryListingItem

    price: float | None = None

    # purchase fields
    purchase_id: int | None = None
    steamid_purchaser: int | None = None
    received_amount: float | None = None

    # listing fields
    original_price: float | None = None
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
    price: float
    daily_volume: int


@dataclass(eq=False, slots=True)
class MarketListing(BaseOrder):
    item: MarketListingItem

    currency: Currency  # original currency
    fee: float

    converted_currency: Currency
    converted_price: float
    converted_fee: float

    def __post_init__(self):
        if not self.item.market_id:
            self.item.market_id = self.id

    @property
    def listing_id(self) -> int:
        return self.id

    @property
    def total_price(self) -> float:
        return self.price + self.fee

    @property
    def total_converted_price(self) -> float:
        return self.converted_price + self.converted_fee


@dataclass(eq=False, slots=True, kw_only=True)
class BaseTradeOfferItem(EconItem):
    class_id: int
    game: GameType

    class_: ItemClass | None  # old trades don't have descriptions for asset due to Steam :)

    def _set_ident_code(self):
        self.ident_code = create_ident_code(self.id, *self.game)

    def _set_args_tuple(self):
        self._args_tuple_ = (self.game[0], self.game[1], self.amount, self.id)

    @property
    def inspect_link(self) -> None:
        return None


@dataclass(eq=False, slots=True, kw_only=True)
class TradeOfferItem(BaseTradeOfferItem):
    missing: bool
    est_usd: int

    owner_id: int = 0

    def __eq__(self, other: "EconItem | TradeOfferItem"):
        if isinstance(other, EconItem):
            game = other.class_.game
            class_id = other.class_.id
        else:
            game = other.game
            class_id = other.class_id

        return (
            (self.id == other.id)
            and (self.game[0] == game[0])
            and (self.game[1] == game[1])
            and (self.class_id == class_id)
        )


@dataclass(eq=False, slots=True)
class BaseTradeOffer:
    id: int

    owner: int  # steam id64 of entity owner acc (SteamClient)
    partner_id: int  # id32

    status: TradeOfferStatus

    @property
    def trade_offer_id(self) -> int:
        return self.id

    @property
    def partner_id64(self) -> int:
        return account_id_to_steam_id(self.partner_id)

    @property
    def is_active(self) -> bool:
        return self.status is TradeOfferStatus.ACTIVE


@dataclass(eq=False, slots=True)
class TradeOffer(BaseTradeOffer):
    """Steam Trade Offer entity."""

    is_our_offer: bool

    expiration_time: datetime
    time_created: datetime
    time_updated: datetime

    items_to_give: list[TradeOfferItem]
    items_to_receive: list[TradeOfferItem]

    message: str = ""

    def __post_init__(self):
        for i in self.items_to_give:
            i.owner_id = self.owner

        for i in self.items_to_receive:
            i.owner_id = self.partner_id64

    @property
    def sender(self) -> int:
        """Steam id64 of sender."""
        return self.owner if self.is_our_offer else self.partner_id64

    @property
    def receiver(self) -> int:
        """Steam id64 of receiver."""
        return self.partner_id64 if self.is_our_offer else self.owner


@dataclass(eq=False, slots=True, kw_only=True)
class HistoryTradeOfferItem(BaseTradeOfferItem):
    new_asset_id: int
    new_context_id: int

    owner_id: None = None


@dataclass(eq=False, slots=True)
class HistoryTradeOffer(BaseTradeOffer):
    time_init: datetime

    assets_received: tuple[HistoryTradeOfferItem, ...]
    assets_given: tuple[HistoryTradeOfferItem, ...]
