from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from typing import TYPE_CHECKING, NamedTuple, TypedDict

from ...app import App, AppContext
from ...id import SteamID
from ...models import EconItem, ItemDescription
from ...utils import create_ident_code

if TYPE_CHECKING:
    from ...cs2 import ItemContext as CS2ItemContext


# https://github.com/SteamRE/SteamKit/blob/master/Resources/SteamLanguage/enums.steamd
class TradeOfferStatus(IntEnum):
    INVALID = 1
    ACTIVE = 2
    ACCEPTED = 3
    COUNTERED = 4
    EXPIRED = 5
    CANCELED = 6
    DECLINED = 7
    INVALID_ITEMS = 8
    CREATED_NEEDS_CONFIRMATION = 9
    CANCELED_BY_SECOND_FACTOR = 10
    IN_ESCROW = 11
    REVERTED = 12


@dataclass(slots=True, kw_only=True)
class BaseTradeOfferItem(EconItem):
    description: ItemDescription | None  # non-active trade offers have no description on items

    app: App  # duplicate in case of description absence

    owner: SteamID = None  # will be set after trade offer creation

    def _set_ident_code(self):
        self.id = create_ident_code(self.asset_id, self.context_id, self.app.id)

    @property
    def app_context(self):
        return self.app.with_context(self.context_id)

    @property
    def cs2(self) -> "CS2ItemContext | None":
        if self.description is not None and self.description.app is App.CS2:
            if self._cs2_ctx is None:
                from ... import cs2

                self._cs2_ctx = cs2.ItemContext.from_item(self)

            return self._cs2_ctx


@dataclass(slots=True, kw_only=True)
class TradeOfferItem(BaseTradeOfferItem):
    missing: bool
    est_usd: int


@dataclass(eq=False, slots=True, kw_only=True)
class BaseTradeOffer:
    trade_id: int | None
    """Separate special numeric ID of *accepted* offer."""

    status: TradeOfferStatus
    """Current status of the offer."""

    querier: SteamID  # just in case
    """Who queries this particular offer."""

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
        return self.status in (TradeOfferStatus.CANCELED, TradeOfferStatus.CANCELED_BY_SECOND_FACTOR)

    @property
    def countered(self):
        return self.status is TradeOfferStatus.COUNTERED

    @property
    def id(self) -> int:
        raise NotImplementedError

    def __hash__(self):
        return self.id

    def __eq__(self, other):
        return isinstance(other, BaseTradeOffer) and self.id == other.id


TradeOfferItems = tuple[TradeOfferItem, ...]


# TODO mental model docs explanation (client agnostic)
@dataclass(slots=True, kw_only=True)
class TradeOffer(BaseTradeOffer):
    """User agnostic `Steam Trade Offer` entity."""

    trade_offer_id: int
    """Trade offer's unique numeric ID."""

    creator: SteamID
    """Offer creator's (sender/owner)."""
    partner: SteamID
    """Offer partner's (receiver/recipient)."""

    expires: datetime
    created_at: datetime
    updated_at: datetime

    message: str | None = None

    to_partner: TradeOfferItems
    """Items sent from ``creator`` to ``partner``."""
    to_creator: TradeOfferItems
    """Items sent from ``partner`` to ``creator``."""

    def __post_init__(self):
        for i in self.to_partner:
            i.owner = self.creator

        for i in self.to_creator:
            i.owner = self.partner

    # for convenience
    @property
    def from_partner(self) -> TradeOfferItems:
        """Items received by ``creator`` from ``partner``."""
        return self.to_creator

    @property
    def from_creator(self) -> TradeOfferItems:
        """Items received by ``partner`` from ``creator``."""
        return self.to_partner

    @property
    def id(self):
        """Alias for ``trade_offer_id``."""
        return self.trade_offer_id


class TradeOffers(NamedTuple):
    """Container for `trade offers` data."""

    sent: list[TradeOffer]
    """Offers sent by `queriers user` to others."""
    received: list[TradeOffer]
    """Offers received by `queriers user` from others."""
    cursor: int
    """Next cursor to paginate over results."""


class TradeOffersSummary(NamedTuple):
    pending_received: int
    new_received: int
    updated_received: int
    historical_received: int
    pending_sent: int
    newly_accepted_sent: int
    updated_sent: int
    historical_sent: int
    escrow_received: int
    escrow_sent: int


@dataclass(slots=True, kw_only=True)
class HistoryTradeOfferItem(BaseTradeOfferItem):
    new_asset_id: int
    new_context_id: int

    new_owner: SteamID = None  # also will be set after creation

    def _set_ident_code(self):  # new ident code
        self.id = create_ident_code(self.new_asset_id, self.new_context_id, self.app.id)

    @property
    def new_app_context(self) -> AppContext:
        return self.app.with_context(self.new_context_id)


HistoryTradeOfferItems = tuple[HistoryTradeOfferItem, ...]


@dataclass(slots=True, kw_only=True)
class HistoryTradeOffer(BaseTradeOffer):
    """User agnostic `Steam Trade Offer` entity from the history of trades."""

    trade_id: int

    init: datetime

    partners: tuple[SteamID, SteamID]
    """Both partners of the trade."""

    to_partner_a: HistoryTradeOfferItems
    """Items sent from ``partner_b`` to ``partner_a``."""
    to_partner_b: HistoryTradeOfferItems
    """Items sent from ``partner_a`` to ``partner_b``."""

    settlement: datetime | None
    mod: datetime | None  # ?

    def __post_init__(self):
        for i in self.to_partner_a:
            i.owner = self.partner_b
            i.new_owner = self.partner_a

        for i in self.to_partner_b:
            i.owner = self.partner_a
            i.new_owner = self.partner_b

    @property
    def id(self) -> int:
        """Alias for ``trade_id``."""
        return self.trade_id

    @property
    def partner_a(self) -> SteamID:
        return self.partners[0]

    @property
    def partner_b(self) -> SteamID:
        return self.partners[1]

    @property
    def from_partner_a(self) -> HistoryTradeOfferItems:
        """Items received by ``partner_b`` from ``partner_a``."""
        return self.to_partner_b

    @property
    def from_partner_b(self) -> HistoryTradeOfferItems:
        """Items received by ``partner_a`` from ``partner_b``."""
        return self.to_partner_a

    def __eq__(self, other):
        return isinstance(other, HistoryTradeOffer) and self.trade_id == other.trade_id


class HistoryTradeOffers(NamedTuple):
    """Container for history of `trade offers` data."""

    trades: list[HistoryTradeOffer]
    """List of `history offers`."""
    total: int
    """Total count of `history offers`."""
    next_trade_id: int | None
    """Next `trade ID` to paginate over results."""
    next_time: int | None
    """Next `timestamp` to paginate over results."""
    more: bool
    """Whether there are more results to paginate over."""


class TradeAssetData(TypedDict):
    appid: int
    contextid: str
    amount: str
    assetid: str
