"""`CS2` app specific context."""

import re
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from typing import TYPE_CHECKING, NamedTuple, Self

import betterproto2

from .app import App

if TYPE_CHECKING:
    from .components.market import MarketListingItem
    from .components.trade import TradeOfferItem
    from .econ import AssetAccessory, EconItem, ItemDescription


INSPECT_LINK_BASE = "steam://run/730//+csgo_econ_action_preview%20%"
# search sticker and charm data
CS2_APPLICABLE_DATA_RE = re.compile(r'<img\s+[^>]*src="([^"]*)"[^>]*title="([^"]*)"[^>]*>')


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


# https://github.com/SteamTracking/Protobufs/blob/e0029427a75d9247e8d15b11d812cf6c00519304/csgo/cstrike15_gcmessages.proto#L915
@dataclass(eq=False, repr=False)
class CEconItemPreviewDataBlock(betterproto2.Message):
    accountid: "int" = betterproto2.field(1, betterproto2.TYPE_UINT32)
    itemid: "int" = betterproto2.field(2, betterproto2.TYPE_UINT64)
    defindex: "int" = betterproto2.field(3, betterproto2.TYPE_UINT32)
    paintindex: "int" = betterproto2.field(4, betterproto2.TYPE_UINT32)
    rarity: "int" = betterproto2.field(5, betterproto2.TYPE_UINT32)
    quality: "int" = betterproto2.field(6, betterproto2.TYPE_UINT32)
    paintwear: "int" = betterproto2.field(7, betterproto2.TYPE_UINT32)
    paintseed: "int" = betterproto2.field(8, betterproto2.TYPE_UINT32)
    killeaterscoretype: "int" = betterproto2.field(9, betterproto2.TYPE_UINT32)
    killeatervalue: "int" = betterproto2.field(10, betterproto2.TYPE_UINT32)
    customname: "str" = betterproto2.field(11, betterproto2.TYPE_STRING)
    stickers: "list[CEconItemPreviewDataBlockSticker]" = betterproto2.field(
        12, betterproto2.TYPE_MESSAGE, repeated=True
    )
    inventory: "int" = betterproto2.field(13, betterproto2.TYPE_UINT32)
    origin: "int" = betterproto2.field(14, betterproto2.TYPE_UINT32)
    questid: "int" = betterproto2.field(15, betterproto2.TYPE_UINT32)
    dropreason: "int" = betterproto2.field(16, betterproto2.TYPE_UINT32)
    musicindex: "int" = betterproto2.field(17, betterproto2.TYPE_UINT32)
    entindex: "int" = betterproto2.field(18, betterproto2.TYPE_INT32)
    petindex: "int" = betterproto2.field(19, betterproto2.TYPE_UINT32)
    keychains: "list[CEconItemPreviewDataBlockSticker]" = betterproto2.field(
        20, betterproto2.TYPE_MESSAGE, repeated=True
    )
    style: "int" = betterproto2.field(21, betterproto2.TYPE_UINT32)
    variations: "list[CEconItemPreviewDataBlockSticker]" = betterproto2.field(
        22, betterproto2.TYPE_MESSAGE, repeated=True
    )
    upgrade_level: "int" = betterproto2.field(23, betterproto2.TYPE_UINT32)

    @classmethod
    def from_certificate(cls, certificate: str) -> Self:
        """Parse `item certificate` and create an instance."""

        buffer = bytearray.fromhex(certificate)

        if buffer[0] != 0:  # unmask
            mask = buffer[0]
            for i in range(1, len(buffer) - 3):
                buffer[i] ^= mask

        return cls.parse(buffer[1:-4])


@dataclass(eq=False, repr=False)
class CEconItemPreviewDataBlockSticker(betterproto2.Message):
    slot: "int" = betterproto2.field(1, betterproto2.TYPE_UINT32)
    sticker_id: "int" = betterproto2.field(2, betterproto2.TYPE_UINT32)
    wear: "float" = betterproto2.field(3, betterproto2.TYPE_FLOAT)
    scale: "float" = betterproto2.field(4, betterproto2.TYPE_FLOAT)
    rotation: "float" = betterproto2.field(5, betterproto2.TYPE_FLOAT)
    tint_id: "int" = betterproto2.field(6, betterproto2.TYPE_UINT32)
    offset_x: "float" = betterproto2.field(7, betterproto2.TYPE_FLOAT)
    offset_y: "float" = betterproto2.field(8, betterproto2.TYPE_FLOAT)
    offset_z: "float" = betterproto2.field(9, betterproto2.TYPE_FLOAT)
    pattern: "int" = betterproto2.field(10, betterproto2.TYPE_UINT32)
    highlight_reel: "int" = betterproto2.field(11, betterproto2.TYPE_UINT32)
    wrapped_sticker: "int" = betterproto2.field(12, betterproto2.TYPE_UINT32)


@dataclass(eq=False, slots=True)
class ItemContext:
    """Representation of `CS2` specific ``EconItem`` data."""

    description_ctx: DescriptionContext

    # absent in market listings data
    stickers: tuple[Sticker, ...]
    charm: Charm | None

    certificate: str | None
    """Encoded `inspect` preview data."""
    wear_rating: float | None
    """Paint wear rating, known as `float` or `floatvalue`."""
    pattern_template: int | None
    name_tag: str | None

    _inspect_data: CEconItemPreviewDataBlock | None = None

    @property
    def inspect_link(self) -> str | None:
        """`Inspect in Game...` link."""
        return (INSPECT_LINK_BASE + self.certificate) if self.certificate else None

    @property
    def inspect_data(self) -> CEconItemPreviewDataBlock | None:
        """Item preview data."""

        if self.certificate:
            if self._inspect_data is None:
                self._inspect_data = CEconItemPreviewDataBlock.from_certificate(self.certificate)

            return self._inspect_data

    @staticmethod
    def _create_sticker(sticker_meta: ItemAccessoryMeta, accessory: "AssetAccessory") -> Sticker:
        w_prop = accessory.parent_relationship_properties[0]
        assert AssetPropertyId(w_prop.id) is AssetPropertyId.STICKER_SCRAPE_LEVEL

        # float will round to 16 digits from original 18
        return Sticker(class_id=accessory.class_id, meta=sticker_meta, wear=float(w_prop.value))

    @classmethod
    def from_item(cls, item: "EconItem | MarketListingItem | TradeOfferItem") -> Self:
        if item.description.app is not App.CS2:
            raise ValueError("Passed item is not belongs to CS2 app.")

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
