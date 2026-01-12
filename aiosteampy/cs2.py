"""`CS2` app specific context."""

import re

from dataclasses import dataclass
from enum import StrEnum, IntEnum
from typing import NamedTuple, Self, overload, TYPE_CHECKING

from .app import App

if TYPE_CHECKING:  # little dirty
    from .models import AssetAccessory, ItemDescription, EconItem
    from .components.market.models import MarketListingItem


# search sticker and charm data
CS2_APPLICABLE_DATA_RE = re.compile(r'<img\s+[^>]*src="([^"]*)"[^>]*title="([^"]*)"[^>]*>')


@overload
def make_inspect_link(*, owner_id: int, asset_id: int, d_id: int) -> str: ...
@overload
def make_inspect_link(*, market_id: int, asset_id: int, d_id: int) -> str: ...
def make_inspect_link(*, market_id: int = None, owner_id: int = None, asset_id: int, d_id: int) -> str:
    """Create `Inspect in game` link for `CS2` item."""

    base = "steam://rungame/730/76561202255233023/+csgo_econ_action_preview%20"
    if market_id:
        return f"{base}M{market_id}A{asset_id}D{d_id}"
    else:
        return f"{base}S{owner_id}A{asset_id}D{d_id}"


class AssetPropertyId(IntEnum):
    PATTERN_TEMPLATE = 1  # items only
    WEAR_RATING = 2  # float value
    CHARM_PATTERN_TEMPLATE = 3
    STICKER_WEAR_RATING = 4  # from asset accessories
    NAME_TAG = 5
    ITEM_CERTIFICATE = 6  # what is this?


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


@dataclass(eq=False, slots=True)
class DescriptionContext:
    """Representation of `CS2` specific ``ItemDescription`` data."""

    # from descriptions
    inspect_id: int | None  # d id
    """Special `inspect id`."""
    stickers: tuple[ItemAccessoryMeta, ...]
    """List of `stickers` metadata."""
    charm: ItemAccessoryMeta | None
    """Charm metadata."""
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
            raise ValueError("Passed description is not from `CS2` app.")

        # find inspect action, language agnostic (safe) option
        d_id = None
        if (i_action := next(filter(lambda a: "action_preview" in a.link, descr.actions), None)) is not None:
            d_id = int(i_action.link.split("%D")[1])

        stickers = ()
        if (s_descr := next(filter(lambda d: d.name == "sticker_info", descr.descriptions), None)) is not None:
            stickers = tuple(ItemAccessoryMeta(t, s) for s, t in CS2_APPLICABLE_DATA_RE.findall(s_descr.value))

        charm = None
        if (c_descr := next(filter(lambda d: d.name == "keychain_info", descr.descriptions), None)) is not None:
            search = CS2_APPLICABLE_DATA_RE.search(c_descr.value)
            charm = ItemAccessoryMeta(name=search.group(1), icon=search.group(2))

        collection = None
        if (cl_descr := next(filter(lambda d: d.name == "itemset_name", descr.descriptions), None)) is not None:
            collection = cl_descr.value

        # safe to get from descriptions in any case
        exterior = None
        if (e_descr := next(filter(lambda d: d.name == "exterior_wear", descr.descriptions), None)) is not None:
            exterior = ItemExterior.from_description(e_descr.value)

        stattrak_score = None
        if (s_descr := next(filter(lambda d: d.name == "stattrak_score", descr.descriptions), None)) is not None:
            stattrak_score = int(s_descr.value.split(": ")[1])  # let's hope that this option is lang safe

        return cls(d_id, stickers, charm, collection, exterior, stattrak_score)


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

    inspect_link: str | None
    wear_rating: float | None  # so called float value
    pattern_template: int | None
    name_tag: str | None

    @staticmethod
    def _create_sticker(sticker_meta: ItemAccessoryMeta, accessory: "AssetAccessory") -> Sticker:
        w_prop = accessory.parent_relationship_properties[0]

        assert AssetPropertyId(w_prop.id) is AssetPropertyId.STICKER_WEAR_RATING

        # float will round to 16 digits from original 18
        return Sticker(class_id=accessory.class_id, meta=sticker_meta, wear=float(w_prop.value))

    @classmethod
    def from_item(cls, item: "EconItem | MarketListingItem") -> Self:
        if item.description.app is not App.CS2:
            raise ValueError("Passed `item` is not from `CS2` app.")

        descr_ctx = item.description.cs2

        inspect_link = None
        if descr_ctx.inspect_id:
            if market_id := getattr(item, "market_id", None) is not None:  # market listing
                inspect_link = make_inspect_link(
                    market_id=market_id,
                    asset_id=item.asset_id,
                    d_id=descr_ctx.inspect_id,
                )
            else:  # econ item
                inspect_link = make_inspect_link(
                    owner_id=item.owner_id.id64,
                    asset_id=item.asset_id,
                    d_id=descr_ctx.inspect_id,
                )

        stickers = ()
        if item.accessories and descr_ctx.stickers:
            stickers = tuple(cls._create_sticker(m, a) for m, a in zip(descr_ctx.stickers, item.accessories))

        charm = None
        if item.accessories and descr_ctx.charm is not None:
            accs = item.accessories[-1]
            if not accs.standalone_properties:
                raise ValueError(
                    "Charm accessory has no standalone properties or, highly likely, is not at the end of the list."
                )

            p_prop = accs.standalone_properties[0]
            if not AssetPropertyId(p_prop.id) is AssetPropertyId.CHARM_PATTERN_TEMPLATE:
                raise ValueError("Charm property has no pattern or, highly likely, is not at the 0 index of the list.")

            charm = Charm(class_id=accs.class_id, meta=descr_ctx.charm, pattern=int(p_prop.value))

        wear_rating = None
        if (
            w_prop := next(
                filter(
                    lambda p: AssetPropertyId(p.id) is AssetPropertyId.WEAR_RATING,
                    item.properties,
                ),
                None,
            )
        ) is not None:
            wear_rating = float(w_prop.value)  # will round to 16 digits from original 18

        pattern = None
        if (
            p_prop := next(
                filter(
                    lambda p: AssetPropertyId(p.id) is AssetPropertyId.PATTERN_TEMPLATE,
                    item.properties,
                ),
                None,
            )
        ) is not None:
            pattern = int(p_prop.value)

        name_tag = None
        if (
            t_prop := next(
                filter(lambda p: AssetPropertyId(p.id) is AssetPropertyId.NAME_TAG, item.properties),
                None,
            )
        ) is not None:
            name_tag = t_prop.value

        return cls(descr_ctx, stickers, charm, inspect_link, wear_rating, pattern, name_tag)
