"""`CS2` app specific context."""

import re
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from typing import TYPE_CHECKING, NamedTuple, Self

from .app import App

if TYPE_CHECKING:
    from .components.market.models import MarketListingItem
    from .components.trade.models import TradeOfferItem
    from .models import AssetAccessory, EconItem, ItemDescription


INSPECT_LINK_BASE = "steam://run/730//+csgo_econ_action_preview%20%"
# search sticker and charm data
CS2_APPLICABLE_DATA_RE = re.compile(r'<img\s+[^>]*src="([^"]*)"[^>]*title="([^"]*)"[^>]*>')


def make_inspect_link(inspect_key: str) -> str:
    """Create `Inspect in game` link for `CS2` item."""
    return INSPECT_LINK_BASE + inspect_key


# https://steamapi.xpaw.me/IEconService#GetAssetPropertySchema
class AssetPropertyId(IntEnum):
    PATTERN_TEMPLATE = 1  # seed
    WEAR_RATING = 2  # float value
    CHARM_TEMPLATE = 3  # charm seed(pattern)
    STICKER_SCRAPE_LEVEL = 4  # sticker wear
    NAME_TAG = 5
    ITEM_CERTIFICATE = 6  # now we know what this is
    """Inspect key of item."""
    FINISH_CATALOG = 7

    @classmethod
    def get(cls, value: int) -> Self | None:
        try:
            return cls(value)
        except KeyError:
            return None


class ItemAccessoryMeta(NamedTuple):
    name: str  # title
    icon: str


# these can be used as market search filters
class ItemExterior(StrEnum):
    FactoryNew = "Factory New"
    MinimalWear = "Minimal Wear"
    FieldTested = "Field-Tested"
    WellWorn = "Well-Worn"
    BattleScarred = "Battle-Scarred"
    NotPainted = "Not Painted"

    @classmethod
    def from_description(cls, description: str) -> Self:
        return cls(description.split(": ")[1])  # Exterior: <wear>


class DescriptionDescriptionName(StrEnum):  # lol
    Sticker = "sticker_info"
    Charm = "keychain_info"
    Collection = "itemset_name"
    Exterior = "exterior_wear"
    StattrakScore = "stattrak_score"
    # Description = "description"  # not meaningful

    @classmethod
    def get(cls, value: str) -> Self | None:
        try:
            return cls(value)
        except ValueError:
            return None


@dataclass(eq=False, slots=True)
class DescriptionContext:
    """Representation of `CS2` specific ``ItemDescription`` data."""

    # from descriptions
    stickers: tuple[ItemAccessoryMeta, ...]
    """List of `stickers` metadata."""
    charm: ItemAccessoryMeta | None
    """`Charm` metadata."""
    collection: str | None
    exterior: ItemExterior | None

    stattrak_score: int | None

    # fields from below will be not as much helpful as we can await, so implementing them is unnecessary
    # inventory only (from tags)
    # type: ...
    # quality: ...
    # rarity: ...

    # weapon: Weapon
    # sticker: StickerCategory, Tournament, TournamentTeam, StickerCapsule, ProPlayer

    @classmethod
    def from_description(cls, descr: "ItemDescription") -> Self:
        if descr.app is not App.CS2:
            raise ValueError("Passed 'description' are not belong to 'CS2' app.")

        stickers = ()
        charm = None
        collection = None
        exterior = None
        stattrak_score = None
        for d in descr.descriptions:
            match DescriptionDescriptionName.get(d.name):
                case DescriptionDescriptionName.Sticker:
                    stickers = tuple(ItemAccessoryMeta(t, s) for s, t in CS2_APPLICABLE_DATA_RE.findall(d.value))
                case DescriptionDescriptionName.Charm:
                    search = CS2_APPLICABLE_DATA_RE.search(d.value)
                    charm = ItemAccessoryMeta(name=search.group(1), icon=search.group(2))
                case DescriptionDescriptionName.Collection:
                    collection = d.value
                case DescriptionDescriptionName.Exterior:  # safe to get from descriptions in any case
                    exterior = ItemExterior.from_description(d.value)
                case DescriptionDescriptionName.StattrakScore:
                    stattrak_score = int(d.value.split(": ")[1])  # let's hope that this option is lang safe

        return cls(stickers, charm, collection, exterior, stattrak_score)


@dataclass(eq=False, slots=True)
class ItemAccessory:
    class_id: int
    meta: ItemAccessoryMeta


@dataclass(eq=False, slots=True)
class Sticker(ItemAccessory):
    wear: float


@dataclass(eq=False, slots=True)
class Charm(ItemAccessory):
    pattern: int


@dataclass(eq=False, slots=True)
class ItemContext:
    """Representation of `CS2` specific ``EconItem`` data."""

    description_ctx: DescriptionContext

    # absent in market listings data
    stickers: tuple[Sticker, ...]
    charm: Charm | None

    inspect_id: str | None
    """Unique key of item (`item certificate`), used to inspect item in game."""
    wear_rating: float | None
    """Wear rating of item skin, known as `float` or `floatvalue`."""
    pattern_template: int | None
    name_tag: str | None

    @property
    def inspect_link(self) -> str | None:
        """`Inspect in game` link."""
        return make_inspect_link(self.inspect_id) if self.inspect_id else None

    @staticmethod
    def _create_sticker(sticker_meta: ItemAccessoryMeta, accessory: "AssetAccessory") -> Sticker:
        w_prop = accessory.parent_relationship_properties[0]
        assert AssetPropertyId(w_prop.id) is AssetPropertyId.STICKER_SCRAPE_LEVEL

        # float will round to 16 digits from original 18
        return Sticker(class_id=accessory.class_id, meta=sticker_meta, wear=float(w_prop.value))

    @classmethod
    def from_item(cls, item: "EconItem | MarketListingItem | TradeOfferItem") -> Self:
        if item.description.app is not App.CS2:
            raise ValueError("Passed 'item' are not belong to 'CS2' app.")

        descr_ctx = item.description.cs2

        stickers = ()
        if item.accessories and descr_ctx.stickers:
            stickers = tuple(cls._create_sticker(m, a) for m, a in zip(descr_ctx.stickers, item.accessories))

        charm = None
        if item.accessories and descr_ctx.charm is not None:
            accs = item.accessories[-1]
            assert accs.standalone_properties

            p_prop = accs.standalone_properties[0]
            assert AssetPropertyId(p_prop.id) is AssetPropertyId.CHARM_TEMPLATE

            charm = Charm(class_id=accs.class_id, meta=descr_ctx.charm, pattern=int(p_prop.value))

        inspect_id = None
        wear_rating = None
        pattern = None
        name_tag = None
        for prop in item.properties:
            match AssetPropertyId.get(prop.id):
                case AssetPropertyId.ITEM_CERTIFICATE:
                    inspect_id = prop.value
                case AssetPropertyId.WEAR_RATING:
                    wear_rating = float(prop.value)  # will round to 16 digits from original 18
                case AssetPropertyId.PATTERN_TEMPLATE:
                    pattern = int(prop.value)
                case AssetPropertyId.NAME_TAG:
                    name_tag = prop.value

        return cls(descr_ctx, stickers, charm, inspect_id, wear_rating, pattern, name_tag)
